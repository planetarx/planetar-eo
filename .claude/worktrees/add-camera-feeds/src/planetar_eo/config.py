from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CACHE_DIR = Path(os.environ.get("PLANETAR_EO_CACHE", "data/eo")).resolve()
DEFAULT_BROKER = os.environ.get("PLANETAR_BROKER", "127.0.0.1:12001")
DEFAULT_MODEL = os.environ.get("PLANETAR_EO_MODEL", "yolo11n.pt")


@dataclass(frozen=True)
class SourceSpec:
    id: str
    name: str
    kind: str
    url: str
    fps: float = 1.0
    location: tuple[float, float] | None = None
    notes: str = ""
    extra: dict[str, Any] | None = None


def load_sources(path: str | Path) -> list[SourceSpec]:
    p = Path(path)
    with p.open() as f:
        doc = yaml.safe_load(f)
    out: list[SourceSpec] = []
    for s in doc.get("sources", []):
        loc = s.get("location")
        out.append(
            SourceSpec(
                id=s["id"],
                name=s["name"],
                kind=s["kind"],
                url=s["url"],
                fps=float(s.get("fps", 1.0)),
                location=tuple(loc) if loc else None,
                notes=s.get("notes", ""),
                extra={k: v for k, v in s.items() if k not in {"id", "name", "kind", "url", "fps", "location", "notes"}} or None,
            )
        )
    return out
