"""Kiểm tra cấu trúc JSON Schema MongoDB bằng stdlib và đối chiếu tên trường với DDL Iceberg."""

import json
import re
from pathlib import Path

import pytest

CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"
MONGO = CONTRACTS / "mongodb"
COLLECTIONS = ["domains", "alerts", "campaigns"]


def load(name):
    return json.loads((MONGO / name).read_text(encoding="utf-8"))


def ddl_columns(table):
    sql = (CONTRACTS / "iceberg" / f"{table}.sql").read_text(encoding="utf-8")
    body = sql.split("CREATE TABLE", 1)[1].split("USING iceberg")[0]
    return set(re.findall(r"^\s{2}(\w+)\s", body, flags=re.M))


def walk(schema):
    yield schema
    for sub in schema.get("properties", {}).values():
        yield from walk(sub)
    if isinstance(schema.get("items"), dict):
        yield from walk(schema["items"])


def has_field(schema, path):
    node = schema
    for part in path.split("."):
        if part not in node.get("properties", {}):
            return False
        node = node["properties"][part]
    return True


@pytest.mark.parametrize("coll", COLLECTIONS)
def test_schema_well_formed(coll):
    s = load(f"{coll}.schema.json")
    assert s["$schema"].startswith("https://json-schema.org/")
    assert s["$id"] == f"{coll}.schema.json"
    assert s["type"] == "object"
    assert "_id" in s["required"]
    for node in walk(s):
        assert set(node.get("required", [])) <= set(node.get("properties", {}))
        for name, prop in node.get("properties", {}).items():
            assert "type" in prop, name


@pytest.mark.parametrize("coll", COLLECTIONS)
def test_index_keys_exist_in_schema(coll):
    schema = load(f"{coll}.schema.json")
    names = []
    for idx in load("indexes.json")[coll]:
        names.append(idx["name"])
        for key in idx["keys"]:
            assert key == "_id" or has_field(schema, key), f"{coll}.{idx['name']}: {key}"
    assert len(names) == len(set(names))


def test_domain_ids_are_ascii_punycode_lowercase():
    pattern = re.compile(load("domains.schema.json")["properties"]["_id"]["pattern"])
    assert pattern.match("xn--vit-nam-abc.com.vn")
    assert not pattern.match("việt.vn")
    assert not pattern.match("ABC.com")
    campaigns = load("campaigns.schema.json")
    assert campaigns["properties"]["domains"]["items"]["pattern"] == pattern.pattern
    assert load("alerts.schema.json")["properties"]["domain"]["pattern"] == pattern.pattern


def test_enrichment_arrays_match_iceberg():
    enrichment = load("domains.schema.json")["properties"]["batch"]["properties"]["enrichment"]
    props = enrichment["properties"]
    for name in ("asn", "asn_org", "country"):
        assert props[name]["type"] == "array", name
        assert "null" in props[name]["items"]["type"], name
    assert set(props) <= ddl_columns("silver.enrichment")


def test_batch_fields_match_domain_scores():
    batch = load("domains.schema.json")["properties"]["batch"]["properties"]
    shared = {"score_date", "score", "reasons", "model_version", "scored_ts"}
    assert shared <= set(batch)
    assert shared <= ddl_columns("gold.domain_scores")
    assert batch["score"]["maximum"] == 100 and batch["score"]["minimum"] == 0


def test_campaign_fields_match_gold_campaigns():
    props = set(load("campaigns.schema.json")["properties"]) - {"_id"}
    assert props == ddl_columns("gold.campaigns") - {"campaign_id"}


def test_timestamps_are_integer_millis():
    domains = load("domains.schema.json")["properties"]
    for key in ("first_seen_ts", "last_seen_ts", "updated_ts"):
        assert domains["speed"]["properties"][key]["type"] == "integer"
    assert domains["batch"]["properties"]["scored_ts"]["type"] == "integer"
    assert load("alerts.schema.json")["properties"]["alert_ts"]["type"] == "integer"


def test_ttl_field_is_bson_date_and_required():
    alerts = load("alerts.schema.json")
    assert alerts["properties"]["created_at"]["x-bsonType"] == "date"
    assert "created_at" in alerts["required"]
    ttl = [i for i in load("indexes.json")["alerts"] if "expireAfterSeconds" in i]
    assert [list(i["keys"]) for i in ttl] == [["created_at"]]


def test_readme_upsert_rule_keeps_filter_on_id_only():
    readme = (MONGO / "README.md").read_text(encoding="utf-8")
    assert "E11000" in readme
    assert '{"_id": domain}, [{"$set": {"batch"' in readme


def test_batch_block_always_carries_nullable_links():
    batch = load("domains.schema.json")["properties"]["batch"]
    for name in ("campaign_id", "anomaly_cluster"):
        assert name in batch["required"]
        assert "null" in batch["properties"][name]["type"]
