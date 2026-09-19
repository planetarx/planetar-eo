# planetar-eo

Electro-optical (camera-feed) → AI boat detection → re-identification microservice.

Pulls public webcam streams from the Victoria, BC area, runs a YOLO-based
vessel detector over each frame, and publishes detections to `planetar-broker`
as native `zmesg` envelopes. Built for the CH13 v2 proposal flagship demo
(dark-vessel detection over the Salish Sea) and slots in alongside `planetar-sat`
(SAR) as the EO lane of the multi-modal fusion stack.

## Layout

```
planetar-eo/
├── src/planetar_eo/
│   ├── sources/      # Camera adapters: youtube_hls, http_snapshot, rtsp
│   ├── detect/       # YOLO-based vessel detector (COCO boat class + extensions)
│   ├── reid/         # (stub) cross-camera re-identification
│   ├── bus/          # zmesg encoder + TCP publisher (mirrors planetar-sat)
│   ├── cli.py        # `planetar-eo sources|probe|run`
│   └── config.py
├── configs/
│   └── sources.victoria.yaml   # Source registry — Victoria POC
├── tests/
└── docs/
```

## Quickstart

```bash
make install-all                                           # opencv + yt-dlp + torch + ultralytics
.venv/bin/planetar-eo sources -c configs/sources.victoria.yaml
.venv/bin/planetar-eo probe   -c configs/sources.victoria.yaml -s hakai.victoria_wharf -n 5
.venv/bin/planetar-eo run     -c configs/sources.victoria.yaml --no-broker -v   # stdout pub
.venv/bin/planetar-eo run     -c configs/sources.victoria.yaml --broker 127.0.0.1:12001
```

`probe` saves annotated JPEGs to `data/probe/` so you can visually verify the
detector is firing before plugging into the bus. `run` is the long-running
microservice.

## Victoria, BC POC source candidates

| Source id                  | Kind          | Vantage point                                  | Status |
|----------------------------|---------------|-------------------------------------------------|--------|
| `bcferries.swartzbay.cam1` | HTTP snapshot | Swartz Bay terminal apron                       | ✅ live |
| `bcferries.swartzbay.cam2` | HTTP snapshot | Swartz Bay → Tsawwassen traffic                 | ✅ live |
| `bcferries.swartzbay.cam3` | HTTP snapshot | Swartz Bay → Gulf Islands traffic               | ✅ live |
| `hakai.victoria_wharf`     | HTTP snapshot | Hakai Institute wharf cam, Inner Harbour        | ✅ live (2688×1512) |
| `chek.victoria_harbour`    | YouTube live  | CHEK News — Victoria Harbour 24/7               | ✅ live (1920×1080) |
| `chek.inner_harbour`       | YouTube live  | CHEK × GVHA — Inner Harbour 24/7                | ✅ live |
| `cruiseport.ogden_point`   | YouTube live  | Ogden Point deep-water terminal, harbour mouth  | ⏳ seasonal standby |

Six sources are verified live; `cruiseport.ogden_point` is a real channel
that streams only around cruise-ship calls (~Apr–Oct). See `docs/SOURCES.md`
for the full verification log — including the sources investigated and ruled
out (ONC subsea cams, SkylineWebcams, BC Ferries placeholder cams). Verify
any source by hand with the `probe` subcommand before trusting it.

## Bus topics published

| Topic           | Schema                                                                                  | Emitted by         |
|-----------------|-----------------------------------------------------------------------------------------|--------------------|
| `eo.frame`      | JSON: `{source_id, ts_ns, seq, width, height, n_detections}`                            | `cli:run`          |
| `eo.detection`  | JSON: `{source_id, ts_ns, frame_seq, cls, cls_name, conf, bbox_xyxy}`                   | `detect/yolo.py`   |
| `eo.reid`       | (planned) JSON: `{source_id, track_id, embed, gallery_match: {source_id, track_id, sim}}` | `reid/` (stub)     |

Wire framing matches the broker: 4-byte **big-endian** (network byte order)
length prefix, then a little-endian `zmesg` envelope. The broker reads the
prefix with `ntohl()`; only the prefix is big-endian, the envelope body
stays little-endian (see `src/planetar_eo/bus/publisher.py` and
`src/planetar_eo/bus/zmesg.py` — pure-Python mirror of
`~/github/sness23/zmesg/zmesg.h`).

## Detector

Default model: **YOLO11n** (`yolo11n.pt`, COCO-pretrained, boat = class 8).
Override with `--model` to point at a marine-fine-tuned checkpoint
(e.g. SeaShips, ABOships, or a custom Salish Sea fine-tune).

## Datasets / training (CH13 1a relevant)

- **SeaShips** — labeled in-harbour vessel detection (visible-light)
- **ABOships / FishEye-AdaSet** — pier-mounted webcam-style imagery
- **xView3** — primarily SAR, but its co-located AIS labels make it useful for
  EO–SAR correspondence experiments via `planetar-sat`

See `~/github/planetarx/planetar/05-DATASETS.md` for the full modality list
across the proposal.

## Status

- **2026-05-14** — scaffold landed AND hooked up to real Victoria data:
  - Verified live sources: `bcferries.swartzbay.cam{1,2,3}`, `hakai.victoria_wharf`,
    `chek.victoria_harbour`, `chek.inner_harbour` (see `docs/SOURCES.md`).
  - YOLO11n end-to-end: 5 `boat` detections per frame on the Hakai 2688×1512
    wharf cam, ~5s cadence, GPU-accelerated.
  - `run --no-broker` emits `eo.frame` + `eo.detection` envelopes as expected.
  - Broker BE-prefix bug pre-fixed (mirrored from planetar-sat lesson).
- **2026-05-15** — camera-feed search:
  - Added `cruiseport.ogden_point` (Victoria Cruise Port @ Ogden Point) —
    the harbour-mouth vantage for large-vessel traffic. Seasonal: live only
    around cruise-ship calls, otherwise YouTube standby.
  - Ruled out ONC (subsea cams, wrong modality), SkylineWebcams (token-gated
    + ToS), BC Ferries SWB cam4–8 (placeholder images), Esquimalt Anglers
    (dead stream). Rationale logged in `docs/SOURCES.md`.
- **Next** — point at a live `planetar-broker`, fill in `reid/` for cross-camera
  vessel id, re-probe `cruiseport.ogden_point` during a cruise-ship call,
  optionally fine-tune YOLO on SeaShips/ABOships for higher confidence on the
  low-res BC Ferries angles.

## Relationship to other planetar siblings

| Sibling           | Role in the demo                                       |
|-------------------|--------------------------------------------------------|
| `planetar-broker` | C bus that consumes our envelopes (12001 TCP publish)  |
| `planetar-sat`    | SAR lane — same envelope shape, different modality     |
| `planetar-ui`     | React shell that subscribes to `eo.*` for the demo UI  |

The proposal's "verifiable spine" treats every detector as an independent
microservice that emits structured envelopes; `planetar-eo` is the visual /
camera lane of that spine.

## Licensing

Licensed under **GPL-3.0-or-later** (see [`LICENSE`](LICENSE)) — a single
licence for everyone, no CLA. Paid add-on services (support, hosting,
integration, defence contracts) are available — contact `sness@sness.net`.
