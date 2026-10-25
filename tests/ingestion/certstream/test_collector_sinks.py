import json
from pathlib import Path

import pytest

from ingestion.certstream.client import Collector, backoff_delay
from ingestion.certstream.sinks import (
    DLQ,
    RAW,
    JsonlSink,
    KafkaSink,
    kafka_producer_config,
    make_sink,
)

ROOT = Path(__file__).resolve().parents[3]
FRAMES = json.loads((ROOT / "tests/fixtures/certstream/frames.json").read_text(encoding="utf-8"))


class ListSink:
    def __init__(self):
        self.items = []
        self.flushed = 0

    def emit(self, topic, key, value):
        self.items.append((topic, key, value))

    def flush(self):
        self.flushed += 1

    def close(self):
        pass


def make_collector(sink):
    return Collector(sink, collector_id="t-1", clock=lambda: 42)


def test_handle_routes_raw_dlq_and_heartbeat():
    sink = ListSink()
    col = make_collector(sink)
    for f in FRAMES:
        col.handle(json.dumps(f))
    col.handle("garbage")
    topics = [t for t, _, _ in sink.items]
    assert topics == [RAW] * 5 + [DLQ]
    assert (col.stats.certs, col.stats.heartbeats, col.stats.dlq) == (5, 1, 1)
    topic, key, rec = sink.items[0]
    assert key == rec["sha256"] and rec["seen_ts"] == 42 and rec["collector_id"] == "t-1"
    assert sink.items[-1][1] is None and sink.items[-1][2]["error_type"] == "invalid_json"


def test_jsonl_sink_writes_one_file_per_topic(tmp_path):
    sink = JsonlSink(tmp_path / "out")
    col = make_collector(sink)
    for f in FRAMES:
        col.handle(json.dumps(f))
    col.handle("garbage")
    sink.close()
    raw = (tmp_path / "out" / "ct.raw.jsonl").read_text(encoding="utf-8").splitlines()
    dlq = (tmp_path / "out" / "ct.dlq.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(raw) == 5 and len(dlq) == 1
    assert json.loads(raw[0])["all_domains"] == ["www.example.com"]


def test_make_sink(tmp_path):
    assert make_sink(f"jsonl:{tmp_path}").__class__ is JsonlSink
    assert make_sink("stdout").__class__.__name__ == "StdoutSink"
    for bad in ("", "jsonl:", "kafka", "ftp:x"):
        with pytest.raises(ValueError):
            make_sink(bad)


def test_kafka_config_follows_contract():
    cfg = kafka_producer_config("k:9092")
    assert cfg["enable.idempotence"] is True
    assert cfg["acks"] == "all" and cfg["compression.type"] == "zstd"
    assert kafka_producer_config("k:9092", **{"linger.ms": 5})["linger.ms"] == 5


class FakeProducer:
    def __init__(self, full_times=0):
        self.sent, self.full_times, self.polls = [], full_times, 0

    def produce(self, topic, key, value, on_delivery):
        if self.full_times:
            self.full_times -= 1
            raise BufferError
        self.sent.append((topic, key, json.loads(value)))

    def poll(self, t):
        self.polls += 1

    def flush(self, t):
        return 0


def test_kafka_sink_key_and_backpressure():
    prod = FakeProducer(full_times=2)
    sink = KafkaSink("unused", producer=prod)
    sink.emit(RAW, "ab" * 32, {"x": 1})
    sink.emit(DLQ, None, {"y": 2})
    assert prod.sent == [(RAW, b"ab" * 32, {"x": 1}), (DLQ, None, {"y": 2})]
    sink.close()


def test_backoff_bounds():
    assert backoff_delay(0, rng=lambda: 1.0) == 1.0
    assert backoff_delay(3, rng=lambda: 1.0) == 8.0
    assert backoff_delay(20, rng=lambda: 1.0) == 60.0
    assert backoff_delay(5, rng=lambda: 0.0) == 0.0
