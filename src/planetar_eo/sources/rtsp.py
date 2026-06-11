"""RTSP / generic VideoCapture adapter (OpenCV).

Works for RTSP, RTMP, MJPEG, local files, and `cv2.VideoCapture`-supported URLs.
Decimates to spec.fps by skipping decoded frames so we don't drown the
detector with 30 fps when 1 fps is plenty for vessels.
"""
from __future__ import annotations

import logging
import time
from typing import Iterator

from planetar_eo.sources.base import Frame, Source

log = logging.getLogger(__name__)


class RtspSource(Source):
    def iter_frames(self) -> Iterator[Frame]:
        import cv2  # type: ignore[import-not-found]

        cap = cv2.VideoCapture(self.spec.url)
        if not cap.isOpened():
            raise RuntimeError(f"source {self.spec.id}: cannot open {self.spec.url}")
        try:
            interval = 1.0 / max(self.spec.fps, 0.01)
            last_emit = 0.0
            while True:
                ok, img = cap.read()
                if not ok:
                    log.warning("source %s: read failure, reconnecting in 2s", self.spec.id)
                    time.sleep(2.0)
                    cap.release()
                    cap = cv2.VideoCapture(self.spec.url)
                    if not cap.isOpened():
                        raise RuntimeError(f"source {self.spec.id}: reconnect failed")
                    continue
                now = time.monotonic()
                if now - last_emit >= interval:
                    last_emit = now
                    yield self._next_frame(img)
        finally:
            cap.release()
