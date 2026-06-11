from planetar_eo.config import SourceSpec
from planetar_eo.sources.base import Frame, Source
from planetar_eo.sources.http_snapshot import HttpSnapshotSource
from planetar_eo.sources.rtsp import RtspSource
from planetar_eo.sources.youtube_hls import YoutubeHlsSource


def create_source(spec: SourceSpec) -> Source:
    kind = spec.kind.lower()
    if kind in {"http_snapshot", "snapshot", "jpeg"}:
        return HttpSnapshotSource(spec)
    if kind in {"rtsp"}:
        return RtspSource(spec)
    if kind in {"youtube_hls", "youtube", "hls"}:
        return YoutubeHlsSource(spec)
    raise ValueError(f"unknown source kind: {spec.kind!r} (id={spec.id})")


__all__ = ["Frame", "Source", "create_source",
           "HttpSnapshotSource", "RtspSource", "YoutubeHlsSource"]
