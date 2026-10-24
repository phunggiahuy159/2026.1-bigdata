"""Kiểm tra cấu trúc JSON Schema Kafka bằng stdlib (chưa có jsonschema trong dev deps)."""

import json
from pathlib import Path

import pytest

KAFKA = Path(__file__).resolve().parents[2] / "contracts" / "kafka"
SCHEMAS = sorted(KAFKA.glob("*.schema.json"))


def test_schemas_found():
    assert {p.name for p in SCHEMAS} == {
        "ct.raw.schema.json",
        "ct.dlq.schema.json",
        "alerts.v1.schema.json",
    }


@pytest.mark.parametrize("path", SCHEMAS, ids=lambda p: p.name)
def test_schema_well_formed(path):
    s = json.loads(path.read_text(encoding="utf-8"))
    assert s["$schema"].startswith("https://json-schema.org/")
    assert s["type"] == "object"
    assert s["$id"] == path.name
    assert set(s["required"]) <= set(s["properties"])
    for name, prop in s["properties"].items():
        assert "type" in prop or "$ref" in prop, name


def test_ct_raw_core_fields():
    s = json.loads((KAFKA / "ct.raw.schema.json").read_text(encoding="utf-8"))
    assert {"sha256", "seen_ts", "collector_id"} <= set(s["required"])
    assert s["properties"]["seen_ts"]["type"] == "integer"
    assert s["properties"]["sha256"]["pattern"] == "^[0-9a-f]{64}$"


def test_ct_dlq_error_types():
    s = json.loads((KAFKA / "ct.dlq.schema.json").read_text(encoding="utf-8"))
    assert "invalid_json" in s["properties"]["error_type"]["enum"]
    assert {"payload", "error_type", "collector_id"} <= set(s["required"])
