import json
import re
from pathlib import Path

import pytest

from serving.app.data import SAMPLE_DIR, SampleRepository, effective, fmt_ts, is_vn

MONGO = Path(__file__).resolve().parents[2] / "contracts" / "mongodb"
JSON_TYPES = {
    "string": str,
    "object": dict,
    "array": list,
    "boolean": bool,
    "null": type(None),
    "integer": int,
    "number": (int, float),
}


def check(schema, value, path="$"):
    """Kiểm tra tối thiểu: type, required, pattern, khoảng giá trị, additionalProperties."""
    types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
    assert any(
        isinstance(value, JSON_TYPES[t])
        and not (t in {"integer", "number"} and isinstance(value, bool))
        for t in types
    ), f"{path}: {value!r} không thuộc {types}"
    if isinstance(value, dict):
        assert set(schema.get("required", [])) <= set(value), f"{path}: thiếu trường bắt buộc"
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            assert set(value) <= set(props), f"{path}: trường lạ {set(value) - set(props)}"
        for key, sub in value.items():
            if key in props:
                check(props[key], sub, f"{path}.{key}")
    if isinstance(value, list) and "items" in schema:
        for i, item in enumerate(value):
            check(schema["items"], item, f"{path}[{i}]")
    if isinstance(value, str) and "pattern" in schema:
        assert re.search(schema["pattern"], value), f"{path}: {value!r} sai pattern"
    if isinstance(value, int) and not isinstance(value, bool):
        assert schema.get("minimum", value) <= value <= schema.get("maximum", value), path


def schema(name):
    return json.loads((MONGO / f"{name}.schema.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", ["domains", "alerts"])
def test_sample_data_conforms_to_mongo_contract(name):
    docs = json.loads((SAMPLE_DIR / f"{name}.json").read_text(encoding="utf-8"))
    assert docs
    for doc in docs:
        check(schema(name), doc)


def test_alert_ids_follow_contract():
    for alert in SampleRepository().alerts():
        assert alert["_id"] == f"{alert['domain']}|{alert['alert_ts']}"


def test_alerts_sorted_newest_first():
    stamps = [a["alert_ts"] for a in SampleRepository().alerts()]
    assert stamps == sorted(stamps, reverse=True)


def test_effective_score_batch_overrides_speed():
    docs = {d["_id"]: d for d in SampleRepository().domains()}
    with_batch = docs["bank-demo-xacthuc.vn"]
    assert effective(with_batch)[0] == with_batch["batch"]["score"]
    assert effective(with_batch)[2] == "batch"
    speed_only = docs["xn--demo-bidv-9xa.net"]
    assert effective(speed_only) == (
        speed_only["speed"]["score"],
        speed_only["speed"]["reasons"],
        "speed",
    )


def test_loader_reads_custom_directory(tmp_path):
    (tmp_path / "alerts.json").write_text("[]")
    (tmp_path / "domains.json").write_text("[]")
    repo = SampleRepository(tmp_path)
    assert repo.alerts() == [] and repo.domains() == []


def test_is_vn():
    assert is_vn("abc.vn") and is_vn("abc.com.vn")
    assert not is_vn("abc.com") and not is_vn("vn-abc.com")


def test_fmt_ts_is_utc():
    assert fmt_ts(0) == "1970-01-01 00:00"
