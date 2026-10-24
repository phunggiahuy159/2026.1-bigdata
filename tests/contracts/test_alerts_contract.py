"""Kiểm tra hợp đồng alerts.v1 (Kafka) so với collection alerts (MongoDB) và hợp đồng Redis."""

import json
import re
from pathlib import Path

import pytest

CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"


def load(rel):
    return json.loads((CONTRACTS / rel).read_text(encoding="utf-8"))


def text(rel):
    return (CONTRACTS / rel).read_text(encoding="utf-8")


ALERTS = load("kafka/alerts.v1.schema.json")
MONGO_ALERTS = load("mongodb/alerts.schema.json")
SHARED = ["domain", "brand_id", "score", "reasons", "fqdn", "alert_ts"]
KAFKA_ONLY = {"alert_type", "prev_score", "sha256", "first_seen_ts", "cert_count", "rule_version"}


def test_alerts_schema_well_formed():
    assert ALERTS["$schema"].startswith("https://json-schema.org/")
    assert ALERTS["$id"] == "alerts.v1.schema.json"
    assert ALERTS["type"] == "object"
    assert set(ALERTS["required"]) <= set(ALERTS["properties"])
    for name, prop in ALERTS["properties"].items():
        assert "type" in prop, name


@pytest.mark.parametrize("name", SHARED)
def test_shared_fields_match_mongo(name):
    kafka, mongo = ALERTS["properties"][name], MONGO_ALERTS["properties"][name]
    assert kafka["type"] == mongo["type"], name
    for key in ("pattern", "minimum", "maximum"):
        assert kafka.get(key) == mongo.get(key), (name, key)


def test_mongo_required_fields_are_in_alerts_v1():
    mongo_needs = set(MONGO_ALERTS["required"]) - {"_id", "created_at"}
    assert mongo_needs <= set(ALERTS["required"])


def test_every_mongo_field_comes_from_kafka():
    derived = {"_id", "created_at"}  # P3 dựng từ domain, alert_ts khi ghi
    assert set(MONGO_ALERTS["properties"]) - derived <= set(ALERTS["properties"])
    assert KAFKA_ONLY <= set(ALERTS["properties"])
    assert not KAFKA_ONLY & set(MONGO_ALERTS["properties"])  # Mongo additionalProperties=false


def test_alerts_v1_field_semantics():
    p = ALERTS["properties"]
    assert p["alert_ts"]["type"] == "integer" and p["first_seen_ts"]["type"] == "integer"
    assert (p["score"]["minimum"], p["score"]["maximum"]) == (0, 100)
    assert p["reasons"]["type"] == "array"
    assert set(p["alert_type"]["enum"]) == {"new_domain", "score_increase"}
    assert (
        p["sha256"]["pattern"]
        == load("kafka/ct.raw.schema.json")["properties"]["sha256"]["pattern"]
    )
    domain = re.compile(p["domain"]["pattern"])
    assert domain.match("xn--vit-nam-abc.com.vn") and not domain.match("ABC.com")


def test_kafka_readme_lists_alerts_v1():
    row = next(ln for ln in text("kafka/README.md").splitlines() if ln.startswith("| `alerts.v1`"))
    cells = [c.strip() for c in row.strip("|").split("|")]
    assert cells[2:5] == ["3", "7 ngày", "zstd"]
    assert cells[5] == "`alerts.v1.schema.json`"


def test_redis_keys_documented():
    readme = text("redis/README.md")
    for key in ("cnt:{brand}:{minute}", "top:suspicious:1h"):
        assert f"`{key}`" in readme
    assert "172800" in readme  # 48 giờ
    assert "ZADD top:suspicious:1h GT" in readme
    assert "INCR" in readme and "không dùng `INCR`" in readme  # ghi idempotent


def test_redis_minute_format_and_brand_ids():
    assert re.fullmatch(r"cnt:[a-z0-9_]+:\d{12}", "cnt:momo:202610241137")
    assert not re.fullmatch(r"cnt:[a-z0-9_]+:\d{12}", "cnt:mo:mo:202610241137")
