# Source verification log

Each entry in `configs/sources.victoria.yaml` needs hands-on verification
before we trust it for the demo. This file is the running log.

## Status as of 2026-05-15

| Source id                     | Status     | Resolution  | Notes |
|-------------------------------|------------|-------------|-------|
| `bcferries.swartzbay.cam2`    | ✅ verified | 320×240    | AXIS P1365 Mk II; ferry apron toward Tsawwassen |
| `bcferries.swartzbay.cam1`    | ✅ verified | 320×180    | AXIS P3265-LVE; terminal apron |
| `bcferries.swartzbay.cam3`    | ✅ verified | 352×240    | Gulf Islands traffic angle |
| `hakai.victoria_wharf`        | ✅ verified | 2688×1512  | Wide harbour shot, 5-6+ boats typically in frame |
| `chek.victoria_harbour`       | ✅ verified | 1920×1080  | Live YouTube HLS, Empress / Inner Harbour view |
| `chek.inner_harbour`          | ✅ url-ok  | (untested)  | Co-branded CHEK × GVHA stream |
| `cruiseport.ogden_point`      | ⏳ pending  | —          | Ogden Point harbour mouth; YouTube live in standby (seasonal) |

Sources investigated and **left out** (see "Sources ruled out" below): ONC
(subsea cameras, wrong modality), SkylineWebcams (token-gated HLS, ToS),
BC Ferries SWB cam4–8 (placeholder images), Esquimalt Anglers (dead stream).

## Verification recipe

```bash
# 1. List
.venv/bin/planetar-eo sources -c configs/sources.victoria.yaml

# 2. Probe with detector off — confirms the URL gives us frames at all
.venv/bin/planetar-eo -v probe -c configs/sources.victoria.yaml \
    -s <id> -n 3 --no-detect

# 3. Probe with detector on — confirms the framing makes vessels detectable
.venv/bin/planetar-eo -v probe -c configs/sources.victoria.yaml \
    -s <id> -n 10
```

If step 2 fails: open the landing page in a browser, inspect the network
panel for the .jpg / .m3u8 / RTSP URL, edit `configs/sources.victoria.yaml`.

## Notes from initial verification (2026-05-14)

- **BC Ferries** publishes via `ccimg.bcferries.com/cc/support/terminals/`
  with a `camN_TERMINAL.jpg` convention. Five terminal codes seen so far:
  DUK, NAN, TSA, LNG, SWB. The SWB cams refresh every ~30s.
- **Hakai Institute** publishes a beefy 2688×1512 wharf shot at
  `hecate.hakai.org/webcams/images/victoria/wharf/current.jpg` with a banner
  timestamp burned into the image. Canadian marine-research-institute
  provenance — best single source for proposal demos.
- **CHEK News** runs two distinct Victoria livestreams (`ZvqDwjNoN7Y` for
  the broader harbour view, `LrVKmClo8ik` for the CHEK × GVHA Inner Harbour
  co-branded cam). yt-dlp resolves both reliably; pinning to the specific
  watch-URL is more stable than channel-handle resolution.
- **GVHA** has no separate verified endpoint — the GVHA Inner Harbour HD
  cam is delivered as the CHEK × GVHA YouTube stream, so we collapsed the
  two registry entries.

## Camera-feed search — 2026-05-15

Searched broadly for additional Victoria Harbour video feeds. One genuinely
new vantage was found and added; the rest were ruled out.

### Added

- **`cruiseport.ogden_point`** — the `@VictoriaCruisePort` YouTube channel
  runs a cam at the Ogden Point deep-water terminal (the southern mouth of
  Victoria Harbour). This is the only source that watches large-vessel
  traffic — cruise ships, coast guard, cable-repair ships — entering and
  leaving the harbour, a coverage gap left by the Inner-Harbour / Swartz Bay
  cams. **Seasonal:** `@VictoriaCruisePort/live` resolves to a real live
  video, but between cruise-ship calls it sits in YouTube standby ("this
  live event will begin in a few moments") and `probe` returns no frames.
  Re-probe when a ship is in port (cruise season is ~Apr–Oct).

### Sources ruled out

- **BC Ferries SWB cam4–8** — `camN_SWB.jpg` for N=4..8 all return HTTP 200
  but a 730-byte placeholder image, not a live camera. Only cam1/2/3 are
  real. Hakai has only one Victoria webcam (`victoria/wharf/`).
- **SkylineWebcams** — token-gated HLS; yt-dlp's `SkylineWebcams` extractor
  fails ("Unable to extract stream url"). Their ToS also forbids
  redistribution. Not viable; use an upstream operator if the wide angle is
  wanted.
- **Ocean Networks Canada** — ONC's "live cameras" are all *subsea*
  (seafloor / marine-life observatory feeds), not surface vessel cams. Wrong
  modality for EO boat detection. ONC's value to planetar is its hydrophones
  → that belongs to the `planetar-acoustic` lane, not here.
- **Esquimalt Anglers ramp (CamStreamer)** — AXIS P1487-LE cam on Fleming
  Beach; its backing YouTube stream (`5lCuts58xbY`) was removed by the
  uploader. No resolvable endpoint as of 2026-05-15.
- **webcamtaxi / Swans Hotel cams** — fully JS-rendered pages, no
  programmatically resolvable stream endpoint; blocked automated fetches.

## Legal / ToS notes

- **CHEK** — publicly broadcast; treat as a public source. Honor robots.txt
  on the channel page if scraping. No rate-limit issues at 1 fps.
- **BC Ferries** — official public webcam, but the operator (Crown corp) may
  restrict commercial use. For a research POC this is fine; for a production
  deployment, confirm with BC Ferries.
- **GVHA / CHEK Inner Harbour** — same caveat as BC Ferries on commercial use.
- **Hakai Institute** — open data under their institutional terms; cite
  "Hakai Institute, Victoria Wharf webcam" in any derived product.
- **Victoria Cruise Port / Ogden Point** — publicly broadcast YouTube
  livestream; same public-source / commercial-use caveat as the CHEK cams.
- **ONC** — Ocean Networks Canada data is open under their terms; cite per
  their attribution policy (not used as an EO source — see above).
- **SkylineWebcams** — third-party tourism aggregator; their ToS typically
  forbids redistribution. Prefer the upstream operator's URL if discoverable.
