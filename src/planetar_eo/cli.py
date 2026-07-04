"""planetar-eo CLI.

Subcommands:
    sources     List configured sources from a YAML registry.
    probe       Pull a few frames from one source, run detection, save annotated JPEGs.
    run         Pump frames from every source through the detector and publish
                envelopes to planetar-broker (or stdout if --no-broker).
"""
from __future__ import annotations

import json
import logging
import pathlib
import signal
import sys
from typing import Any

import click

from planetar_eo.bus.zmesg import Envelope, uuid_str
from planetar_eo.config import DEFAULT_BROKER, DEFAULT_MODEL, load_sources

log = logging.getLogger("planetar_eo")


def _frame_envelope(source_id: str, frame: Any, n_detections: int) -> Envelope:
    """Envelope for one grabbed frame. Its id becomes the `causation_id` of
    every detection derived from it (distributed tracing); `correlation_id`
    groups all traffic from one camera."""
    return Envelope(
        topic="eo.frame",
        schema_name="planetar.eo.frame.v1",
        schema_version=1,
        correlation_id=source_id,
        payload=json.dumps({
            "source_id": source_id,
            "ts_ns": frame.ts_ns,
            "seq": frame.seq,
            "height": int(frame.image.shape[0]),
            "width": int(frame.image.shape[1]),
            "n_detections": n_detections,
        }).encode("utf-8"),
    )


def _detection_envelope(source_id: str, det: Any, causation_id: str) -> Envelope:
    """Envelope for one detection; `causation_id` is the dashed-UUID id of the
    eo.frame envelope the detection came from."""
    return Envelope(
        topic="eo.detection",
        schema_name="planetar.eo.detection.v1",
        schema_version=1,
        correlation_id=source_id,
        causation_id=causation_id,
        payload=json.dumps(det.as_dict()).encode("utf-8"),
    )


@click.group()
@click.option("-v", "--verbose", count=True, help="Increase log verbosity (-v INFO, -vv DEBUG).")
def main(verbose: int) -> None:
    """planetar-eo: camera-feed vessel detection microservice."""
    level = logging.WARNING - 10 * min(verbose, 2)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


@main.command("sources")
@click.option("--config", "-c", required=True, type=click.Path(exists=True), help="YAML source registry.")
def cmd_sources(config: str) -> None:
    """List configured sources."""
    specs = load_sources(config)
    print(f"{len(specs)} source(s) in {config}\n")
    for s in specs:
        loc = f"({s.location[0]:.4f},{s.location[1]:.4f})" if s.location else "-"
        print(f"  {s.id:30s} kind={s.kind:14s} fps={s.fps:>5.2f}  loc={loc}")
        print(f"  {'':30s} {s.name}")
        if s.notes:
            first = s.notes.strip().splitlines()[0]
            print(f"  {'':30s} note: {first}")
        print()


@main.command("probe")
@click.option("--config", "-c", required=True, type=click.Path(exists=True))
@click.option("--source", "-s", "source_id", required=True, help="Source id to probe.")
@click.option("--frames", "-n", default=5, show_default=True, help="Number of frames to grab.")
@click.option("--model", default=DEFAULT_MODEL, show_default=True, help="YOLO weights path.")
@click.option("--no-detect", is_flag=True, help="Just dump frames; skip the detector.")
@click.option("--out", "out_dir", default="data/probe", show_default=True, type=click.Path())
def cmd_probe(config: str, source_id: str, frames: int, model: str, no_detect: bool, out_dir: str) -> None:
    """Grab N frames from one source, optionally run the detector, save JPEGs."""
    import cv2  # type: ignore[import-not-found]

    from planetar_eo.sources import create_source

    specs = {s.id: s for s in load_sources(config)}
    if source_id not in specs:
        raise click.BadParameter(f"unknown source '{source_id}'. known: {sorted(specs)}")
    spec = specs[source_id]
    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    detector = None
    if not no_detect:
        from planetar_eo.detect import YoloVesselDetector
        detector = YoloVesselDetector(model=model)

    src = create_source(spec)
    count = 0
    try:
        for frame in src.iter_frames():
            count += 1
            jpg = out / f"{spec.id}.{frame.seq:04d}.jpg"
            dets: list[Any] = []
            img = frame.image
            if detector is not None:
                dets = detector.infer(spec.id, frame.ts_ns, frame.seq, img)
                for d in dets:
                    h, w = img.shape[:2]
                    x1, y1, x2, y2 = d.bbox_xyxy
                    p1 = (int(x1 * w), int(y1 * h))
                    p2 = (int(x2 * w), int(y2 * h))
                    cv2.rectangle(img, p1, p2, (0, 255, 0), 2)
                    cv2.putText(img, f"{d.cls_name} {d.conf:.2f}", (p1[0], p1[1] - 6),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA)
            cv2.imwrite(str(jpg), img)
            print(f"frame {frame.seq:>4} {img.shape[1]}x{img.shape[0]} dets={len(dets)} -> {jpg}")
            for d in dets:
                print(f"    {json.dumps(d.as_dict())}")
            if count >= frames:
                break
    finally:
        src.close()


@main.command("run")
@click.option("--config", "-c", required=True, type=click.Path(exists=True))
@click.option("--broker", default=DEFAULT_BROKER, show_default=True,
              help="planetar-broker TCP publish endpoint host:port.")
@click.option("--no-broker", is_flag=True, help="Print envelopes to stdout instead of connecting.")
@click.option("--model", default=DEFAULT_MODEL, show_default=True)
@click.option("--source", "only", multiple=True,
              help="Restrict to specific source id(s); repeat to allow several.")
def cmd_run(config: str, broker: str, no_broker: bool, model: str, only: tuple[str, ...]) -> None:
    """Pull frames → detect → publish to the broker. Multi-source in threads."""
    import threading

    from planetar_eo.bus import Publisher
    from planetar_eo.bus.publisher import StdoutPublisher
    from planetar_eo.detect import YoloVesselDetector
    from planetar_eo.sources import create_source

    specs = load_sources(config)
    if only:
        specs = [s for s in specs if s.id in only]
        if not specs:
            raise click.BadParameter(f"no sources match {only!r}")
    detector = YoloVesselDetector(model=model)
    pub: Any = StdoutPublisher() if no_broker else Publisher.from_endpoint(broker)
    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())

    lock = threading.Lock()

    def worker(spec) -> None:
        try:
            src = create_source(spec)
        except Exception as e:
            log.error("source %s: failed to construct: %s", spec.id, e)
            return
        try:
            for frame in src.iter_frames():
                if stop.is_set():
                    break
                dets = detector.infer(spec.id, frame.ts_ns, frame.seq, frame.image)
                frame_env = _frame_envelope(spec.id, frame, len(dets))
                frame_id = uuid_str(frame_env.id)
                with lock:
                    pub.publish(frame_env)
                    for d in dets:
                        pub.publish(_detection_envelope(spec.id, d, frame_id))
        except Exception as e:
            log.error("source %s: worker crashed: %s", spec.id, e)
        finally:
            src.close()

    threads = [threading.Thread(target=worker, args=(s,), name=f"src-{s.id}", daemon=True) for s in specs]
    with pub:
        for t in threads:
            t.start()
        try:
            while not stop.is_set() and any(t.is_alive() for t in threads):
                stop.wait(timeout=0.5)
        except KeyboardInterrupt:
            stop.set()
    print("planetar-eo: shutting down", file=sys.stderr)
