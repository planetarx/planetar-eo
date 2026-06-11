from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterator

import numpy as np

from planetar_eo.config import SourceSpec


@dataclass
class Frame:
    source_id: str
    ts_ns: int
    image: np.ndarray  # BGR uint8 HxWx3
    seq: int = 0

    @property
    def shape(self) -> tuple[int, int, int]:
        return self.image.shape  # type: ignore[return-value]


class Source(ABC):
    """A camera source. Yields BGR frames at roughly spec.fps."""

    def __init__(self, spec: SourceSpec) -> None:
        self.spec = spec
        self._seq = 0

    @property
    def id(self) -> str:
        return self.spec.id

    @abstractmethod
    def iter_frames(self) -> Iterator[Frame]:
        """Yield frames until the stream closes or the caller breaks out."""

    def _next_frame(self, img: np.ndarray) -> Frame:
        self._seq += 1
        return Frame(
            source_id=self.spec.id,
            ts_ns=time.time_ns(),
            image=img,
            seq=self._seq,
        )

    def close(self) -> None:
        pass

    def __enter__(self) -> "Source":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
