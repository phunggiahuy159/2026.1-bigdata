"""Chạy: python -m ingestion.certstream --sink jsonl:data/raw/certstream [--seconds 120]"""

from __future__ import annotations

import argparse
import asyncio
import logging
import time

from .client import DEFAULT_URL, Collector
from .sinks import make_sink


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--url", default=DEFAULT_URL)
    p.add_argument("--sink", default="stdout", help="stdout | jsonl:<thư mục> | kafka:<bootstrap>")
    p.add_argument("--collector-id")
    p.add_argument("--seconds", type=float, help="dừng sau ngần này giây (mặc định chạy mãi)")
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sink = make_sink(args.sink)
    col = Collector(sink, url=args.url, collector_id=args.collector_id)
    t0 = time.monotonic()
    try:
        asyncio.run(col.run(args.seconds))
    except KeyboardInterrupt:
        pass
    finally:
        sink.close()
        dt = time.monotonic() - t0
        s = col.stats
        logging.info(
            "xong %.0fs: certs=%d (%.0f/s) dlq=%d heartbeat=%d connects=%d reconnects=%d",
            dt,
            s.certs,
            s.certs / dt if dt else 0,
            s.dlq,
            s.heartbeats,
            s.connects,
            s.reconnects,
        )


if __name__ == "__main__":
    main()
