"""Client WebSocket CertStream lite, tự kết nối lại có backoff."""

from __future__ import annotations

import asyncio
import logging
import os
import random
import socket
import time
from dataclasses import dataclass

from .parse import ParseError, dlq_record, parse_message
from .sinks import DLQ, RAW, Sink

log = logging.getLogger("certstream")

DEFAULT_URL = "wss://api.certstream.dev/lite"


def default_collector_id() -> str:
    return f"{socket.gethostname()}-{os.getpid()}"


def backoff_delay(attempt: int, base: float = 1.0, cap: float = 60.0, rng=random.random) -> float:
    """Exponential backoff với full jitter: attempt=0 → ≤ base."""
    return rng() * min(cap, base * (2**attempt))


@dataclass
class Stats:
    certs: int = 0
    dlq: int = 0
    heartbeats: int = 0
    connects: int = 0
    reconnects: int = 0


class Collector:
    def __init__(
        self,
        sink: Sink,
        url: str = DEFAULT_URL,
        collector_id: str | None = None,
        stable_after: float = 30.0,
        clock=lambda: int(time.time() * 1000),
    ):
        self.sink = sink
        self.url = url
        self.collector_id = collector_id or default_collector_id()
        self.stable_after = stable_after  # kết nối sống đủ lâu thì reset backoff
        self.clock = clock
        self.stats = Stats()

    def handle(self, raw: str | bytes) -> None:
        ts = self.clock()
        try:
            rec = parse_message(raw, ts, self.collector_id)
        except ParseError as e:
            self.stats.dlq += 1
            self.sink.emit(DLQ, None, dlq_record(raw, e, ts, self.collector_id))
            return
        if rec is None:
            self.stats.heartbeats += 1
            return
        self.stats.certs += 1
        self.sink.emit(RAW, rec["sha256"], rec)

    async def run(self, max_seconds: float | None = None) -> None:
        import websockets  # nhập muộn để test parse không cần gói này

        deadline = None if max_seconds is None else time.monotonic() + max_seconds
        attempt = 0
        while deadline is None or time.monotonic() < deadline:
            started = time.monotonic()
            try:
                self.stats.connects += 1
                async with websockets.connect(self.url, max_size=None, open_timeout=20) as ws:
                    log.info("đã kết nối %s", self.url)
                    while True:
                        left = None if deadline is None else deadline - time.monotonic()
                        timeout = None if left is None else max(0.1, left)
                        raw = await asyncio.wait_for(ws.recv(), timeout)
                        self.handle(raw)
            except TimeoutError:
                if deadline is not None and time.monotonic() >= deadline:
                    break
                log.warning("quá hạn chờ khung")
            except (websockets.ConnectionClosed, OSError, websockets.InvalidHandshake) as e:
                log.warning("mất kết nối: %s", e)
            finally:
                self.sink.flush()
            if time.monotonic() - started >= self.stable_after:
                attempt = 0
            delay = backoff_delay(attempt)
            attempt += 1
            self.stats.reconnects += 1
            log.info("kết nối lại sau %.1fs (lần %d)", delay, self.stats.reconnects)
            await asyncio.sleep(delay)
