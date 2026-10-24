import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2] / "contracts" / "mongodb"
COLLECTIONS = ["domains", "alerts", "campaigns"]


def load(name):
    return json.loads((ROOT / name).read_text())


@pytest.mark.parametrize("coll", COLLECTIONS)
def test_schema_is_valid(coll):
    Draft202012Validator.check_schema(load(f"{coll}.schema.json"))


def test_domain_with_speed_and_batch_valid():
    v = Draft202012Validator(load("domains.schema.json"))
    doc = {
        "_id": "abc.example",
        "brand_id": "vietcombank",
        "speed": {"score": 80, "reasons": ["typosquat"], "updated_ts": 1760000000000},
        "batch": {
            "score": 91,
            "reasons": ["typosquat", "new_asn"],
            "scored_date": "2026-10-24",
            "model_version": "v1",
            "updated_ts": 1760000001000,
        },
    }
    assert not list(v.iter_errors(doc))
    doc["speed"]["score"] = 101
    assert list(v.iter_errors(doc))


def test_alert_requires_fields():
    v = Draft202012Validator(load("alerts.schema.json"))
    assert list(v.iter_errors({"_id": "x|1"}))


def _field_exists(schema, path):
    node = schema
    for part in path.split("."):
        props = node.get("properties", {})
        if part not in props:
            return False
        node = props[part]
    return True


@pytest.mark.parametrize("coll", COLLECTIONS)
def test_index_keys_exist_in_schema(coll):
    schema = load(f"{coll}.schema.json")
    for idx in load("indexes.json")[coll]:
        for key in idx["keys"]:
            assert key == "_id" or _field_exists(schema, key), f"{coll}.{idx['name']}: {key}"


def test_index_names_unique_per_collection():
    for idxs in load("indexes.json").values():
        names = [i["name"] for i in idxs]
        assert len(names) == len(set(names))
