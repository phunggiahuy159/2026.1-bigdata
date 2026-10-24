"""Sink cắm được cho collector: stdout, JSONL local, Kafka."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Protocol

RAW = "ct.raw"
DLQ = "ct.dlq"


class Sink(Protocol):
    def emit(self, topic: str, key: str | None, value: dict) -> None: ...
    def flush(self) -> None: ...
    def close(self) -> None: ...


def _dumps(value: dict) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


class StdoutSink:
    """In `topic<TAB>json` ra stdout."""

    def emit(self, topic, key, value):
        sys.stdout.write(f"{topic}\t{_dumps(value)}\n")

    def flush(self):
        sys.stdout.flush()

    def close(self):
        self.flush()


class JsonlSink:
    """Ghi append `<dir>/<topic>.jsonl`, mỗi dòng một bản ghi."""

    def __init__(self, directory: str | Path):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self._files = {}

    def _file(self, topic):
        if topic not in self._files:
            self._files[topic] = open(self.dir / f"{topic}.jsonl", "a", encoding="utf-8")
        return self._files[topic]

    def emit(self, topic, key, value):
        self._file(topic).write(_dumps(value) + "\n")

    def flush(self):
        for f in self._files.values():
            f.flush()

    def close(self):
        for f in self._files.values():
            f.close()
        self._files.clear()


def kafka_producer_config(bootstrap: str, **extra) -> dict:
    """Cấu hình producer theo hợp đồng: idempotent, acks=all, zstd."""
    cfg = {
        "bootstrap.servers": bootstrap,
        "enable.idempotence": True,
        "acks": "all",
        "compression.type": "zstd",
        "linger.ms": 50,
        "batch.size": 262144,
    }
    cfg.update(extra)
    return cfg


class KafkaSink:
    """Producer confluent-kafka; key = sha256. Chưa dùng được đến khi Kafka có trên cụm."""

    def __init__(self, bootstrap: str, producer=None, **extra):
        if producer is None:
            from confluent_kafka import Producer  # nhập muộn: chỉ cần khi dùng Kafka

            producer = Producer(kafka_producer_config(bootstrap, **extra))
        self.producer = producer
        self.errors = 0

    def _on_delivery(self, err, _msg):
        if err is not None:
            self.errors += 1

    def emit(self, topic, key, value):
        while True:
            try:
                self.producer.produce(
                    topic,
                    key=key.encode() if key else None,
                    value=_dumps(value).encode(),
                    on_delivery=self._on_delivery,
                )
                break
            except BufferError:  # hàng đợi đầy: chờ gửi bớt rồi thử lại
                self.producer.poll(0.5)
        self.producer.poll(0)

    def flush(self):
        self.producer.flush(30)

    def close(self):
        self.flush()


def make_sink(spec: str) -> Sink:
    """`stdout`, `jsonl:<thư mục>` hoặc `kafka:<bootstrap>`."""
    if spec == "stdout":
        return StdoutSink()
    kind, _, arg = spec.partition(":")
    if kind == "jsonl" and arg:
        return JsonlSink(arg)
    if kind == "kafka" and arg:
        return KafkaSink(arg)
    raise ValueError(f"sink không hợp lệ: {spec!r}")
