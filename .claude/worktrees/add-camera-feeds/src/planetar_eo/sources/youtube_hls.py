"""YouTube-live adapter.

Resolves a YouTube live-stream URL to its current HLS manifest with yt-dlp,
then hands off to OpenCV/PyAV via the RTSP-style VideoCapture path. Useful for
public 24/7 cams like CHEK's Victoria Harbour Cam.
"""
from __future__ import annotations

import logging
import time
from typing import Iterator

from planetar_eo.sources.base import Frame, Source

log = logging.getLogger(__name__)


def resolve_hls_url(youtube_url: str) -> str:
    """Return the current HLS m3u8 URL for a YouTube live stream."""
    try:
        from yt_dlp import YoutubeDL  # type: ignore[import-not-found]
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "yt-dlp not installed. `pip install -e .[streams]` to enable YouTube sources."
        ) from e
    opts = {"quiet": True, "skip_download": True, "format": "best[protocol^=m3u8]/best"}
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(youtube_url, download=False)
    url = info.get("url")
    if not url:
        # Walk requested formats if top-level url isn't directly an HLS manifest.
        for f in info.get("formats", []):
            if f.get("protocol", "").startswith("m3u8") and f.get("url"):
                url = f["url"]
                break
    if not url:
        raise RuntimeError(f"could not resolve HLS URL from {youtube_url}")
    return url


class YoutubeHlsSource(Source):
    def iter_frames(self) -> Iterator[Frame]:
        import cv2  # type: ignore[import-not-found]

        hls = resolve_hls_url(self.spec.url)
        log.info("source %s: resolved HLS %s", self.spec.id, hls[:80] + ("…" if len(hls) > 80 else ""))
        cap = cv2.VideoCapture(hls)
        if not cap.isOpened():
            raise RuntimeError(f"source {self.spec.id}: cannot open HLS stream")
        try:
            interval = 1.0 / max(self.spec.fps, 0.01)
            last_emit = 0.0
            consecutive_failures = 0
            while True:
                ok, img = cap.read()
                if not ok:
                    consecutive_failures += 1
                    log.warning(
                        "source %s: read failure (%d), refreshing HLS in 5s",
                        self.spec.id, consecutive_failures,
                    )
                    time.sleep(5.0)
                    cap.release()
                    hls = resolve_hls_url(self.spec.url)
                    cap = cv2.VideoCapture(hls)
                    if not cap.isOpened():
                        raise RuntimeError(f"source {self.spec.id}: re-resolve failed")
                    continue
                consecutive_failures = 0
                now = time.monotonic()
                if now - last_emit >= interval:
                    last_emit = now
                    yield self._next_frame(img)
        finally:
            cap.release()
