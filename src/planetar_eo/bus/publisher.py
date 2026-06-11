"""TCP publisher to planetar-broker.

Connects to the broker's publish port (default 127.0.0.1:12001), then writes
length-prefixed zmesg frames matching the broker's TCP wire format:

    [4-byte BIG-ENDIAN envelope length][envelope bytes]

Wire-framing gotcha: the broker reads the prefix with ntohl() — network byte
order. The zmesg envelope contents stay little-endian, but the *prefix* is
big-endian. Using `<I` here will cause the broker to silently drop frames.
"""
from __future__ import annotations

import logging
import socket
import struct
import time

from planetar_eo.bus.zmesg import Envelope

log = logging.getLogger(__name__)

FRAME_MAX = 1 << 20  # broker rejects > 1 MiB


class Publisher:
    def __init__(self, host: str = "127.0.0.1", port: int = 12001, connect_timeout: float = 2.0):
        self.host = host
        self.port = port
        self.connect_timeout = connect_timeout
        self._sock: socket.socket | None = None

    @classmethod
    def from_endpoint(cls, endpoint: str) -> "Publisher":
        host, _, port_s = endpoint.partition(":")
        return cls(host=host or "127.0.0.1", port=int(port_s or 12001))

    def connect(self) -> None:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(self.connect_timeout)
        s.connect((self.host, self.port))
        s.settimeout(None)
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self._sock = s
        log.info("connected to planetar-broker at %s:%d", self.host, self.port)

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            finally:
                self._sock = None

    def publish(self, env: Envelope) -> int:
        """Serialize and ship one envelope. Returns bytes written (including 4-byte prefix)."""
        if self._sock is None:
            self.connect()
        env.published_at_ns = time.time_ns()
        frame = env.serialize()
        if len(frame) > FRAME_MAX:
            raise ValueError(f"envelope {len(frame)} B exceeds FRAME_MAX={FRAME_MAX}")
        prefix = struct.pack(">I", len(frame))  # network byte order — see module docstring
        assert self._sock is not None
        self._sock.sendall(prefix + frame)
        return len(prefix) + len(frame)

    def __enter__(self) -> "Publisher":
        self.connect()
        return self

    def __exit__(self, *exc) -> None:
        self.close()


class StdoutPublisher:
    """Drop-in for Publisher that prints envelope headers to stdout.

    Used as a fallback when the broker isn't running yet (planetar-broker is
    still a placeholder at the workspace root). Lets the rest of the pipeline
    be exercised end-to-end without a live bus.
    """

    def __init__(self) -> None:
        self.count = 0

    def connect(self) -> None:
        pass

    def close(self) -> None:
        pass

    def publish(self, env: Envelope) -> int:
        env.published_at_ns = time.time_ns()
        frame = env.serialize()
        self.count += 1
        print(
            f"[stdout-pub] #{self.count} topic={env.topic} bytes={len(frame)} "
            f"schema={env.schema_name}@{env.schema_version} corr={env.correlation_id or '-'}"
        )
        return len(frame) + 4

    def __enter__(self) -> "StdoutPublisher":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
