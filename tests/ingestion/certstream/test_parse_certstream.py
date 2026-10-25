import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from ingestion.certstream.parse import ParseError, dlq_record, parse_message

ROOT = Path(__file__).resolve().parents[3]
FRAMES = json.loads((ROOT / "tests/fixtures/certstream/frames.json").read_text(encoding="utf-8"))
RAW = Draft202012Validator(
    json.loads((ROOT / "contracts/kafka/ct.raw.schema.json").read_text(encoding="utf-8"))
)
DLQ = Draft202012Validator(
    json.loads((ROOT / "contracts/kafka/ct.dlq.schema.json").read_text(encoding="utf-8"))
)
CERTS = [f for f in FRAMES if f["message_type"] == "certificate_update"]
TS = 1792830800123


def parse(frame):
    return parse_message(json.dumps(frame), TS, "test-1")


@pytest.mark.parametrize("frame", CERTS, ids=lambda f: f["data"]["leaf_cert"]["all_domains"][0])
def test_valid_frames_match_ct_raw_schema(frame):
    rec = parse(frame)
    assert list(RAW.iter_errors(rec)) == []


def test_fields_converted():
    rec = parse(CERTS[0])
    assert rec["seen_ts"] == TS and rec["collector_id"] == "test-1"
    assert rec["sha256"] == "01" * 32  # hạ chữ thường, bỏ dấu hai chấm
    assert rec["not_before"] == 1792827253000 and rec["not_after"] == 1800603252000
    assert rec["ct_seen"] == 1792830766506
    assert rec["submission_ts"] == 1792830764088
    assert rec["all_domains"] == ["www.example.com"]


def test_bytes_input():
    assert parse_message(json.dumps(CERTS[0]).encode(), TS, "c")["sha256"] == "01" * 32


def test_heartbeat_returns_none():
    assert parse({"message_type": "heartbeat"}) is None


def test_optional_fields_may_be_absent():
    frame = json.loads(json.dumps(CERTS[0]))
    for k in ("cert_link", "seen", "submission_timestamp"):
        frame["data"].pop(k)
    for k in ("subject", "issuer", "extensions", "serial_number", "fingerprint", "is_ca"):
        frame["data"]["leaf_cert"].pop(k)
    rec = parse(frame)
    assert rec["ct_seen"] is None and rec["extensions"] is None
    assert list(RAW.iter_errors(rec)) == []


def _mutated(path, value):
    frame = json.loads(json.dumps(CERTS[0]))
    obj = frame
    for k in path[:-1]:
        obj = obj[k]
    if value is KeyError:
        del obj[path[-1]]
    else:
        obj[path[-1]] = value
    return frame


@pytest.mark.parametrize(
    "path,value,error_type",
    [
        (["data", "leaf_cert", "all_domains"], KeyError, "missing_field"),
        (["data", "leaf_cert", "sha256"], KeyError, "missing_field"),
        (["data", "source"], KeyError, "missing_field"),
        (["data", "leaf_cert", "not_before"], KeyError, "missing_field"),
        (["data", "leaf_cert", "sha256"], "zz:zz", "invalid_field"),
        (["data", "leaf_cert", "all_domains"], "example.com", "invalid_field"),
        (["data", "leaf_cert", "all_domains"], ["example.com", ""], "invalid_field"),
        (["data", "leaf_cert", "not_after"], "soon", "invalid_field"),
        (["data", "cert_index"], -1, "invalid_field"),
        (["data", "update_type"], "Other", "invalid_field"),
        (["message_type"], "something_else", "invalid_field"),
    ],
)
def test_invalid_frames_raise(path, value, error_type):
    with pytest.raises(ParseError) as e:
        parse(_mutated(path, value))
    assert e.value.error_type == error_type


@pytest.mark.parametrize("raw", ["not json", "{", "", "[1,2]", "null", b"\xff\xfe"])
def test_invalid_json_raises(raw):
    with pytest.raises(ParseError) as e:
        parse_message(raw, TS, "c")
    assert e.value.error_type == "invalid_json"


def test_dlq_record_matches_schema():
    raw = '{"message_type": "certificate_update"}'
    with pytest.raises(ParseError) as e:
        parse_message(raw, TS, "c")
    rec = dlq_record(raw, e.value, TS, "c")
    assert list(DLQ.iter_errors(rec)) == []
    assert rec["error_type"] == "missing_field" and rec["payload"] == raw
    assert rec["payload_truncated"] is False


def test_dlq_payload_truncated_and_bytes_decoded():
    err = ParseError("invalid_json", "x")
    rec = dlq_record(b"a" * 70000, err, TS, "c")
    assert len(rec["payload"]) == 65536 and rec["payload_truncated"] is True
    assert list(DLQ.iter_errors(rec)) == []
    assert dlq_record(b"\xff", err, TS, "c")["payload"] == "�"
