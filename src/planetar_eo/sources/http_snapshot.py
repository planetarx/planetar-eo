"""Polling adapter for cameras that publish a single JPEG/PNG URL.

Many tourism / harbour webcams refresh a single image every few seconds on the
hosting page. This adapter GETs that URL on a fixed interval and decodes the
image into a BGR ndarray.
"""
from __future__ import annotations

import logging
import time
from typing import Iterator

import httpx
import numpy as np

from planetar_eo.sources.base import Frame, Source

log = logging.getLogger(__name__)


class HttpSnapshotSource(Source):
    def iter_frames(self) -> Iterator[Frame]:
        # Lazy import so the package loads even when opencv is missing.
        import cv2  # type: ignore[import-not-found]

        interval = 1.0 / max(self.spec.fps, 0.01)
        headers = {"User-Agent": "planetar-eo/0.1 (+https://zaxanalytics.example)"}
        with httpx.Client(timeout=10.0, headers=headers, follow_redirects=True) as client:
            while True:
                t0 = time.monotonic()
                try:
                    r = client.get(self.spec.url)
                    r.raise_for_status()
                    arr = np.frombuffer(r.content, dtype=np.uint8)
                    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                    if img is None:
                        log.warning("source %s: failed to decode %d bytes", self.spec.id, len(r.content))
                    else:
                        yield self._next_frame(img)
                except httpx.HTTPError as e:
                    log.warning("source %s: http error %s", self.spec.id, e)
                dt = time.monotonic() - t0
                if dt < interval:
                    time.sleep(interval - dt)
