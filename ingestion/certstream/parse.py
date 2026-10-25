"""Parse một khung WebSocket của CertStream lite thành bản ghi `ct.raw`.

Hàm thuần, không I/O; dùng chung cho collector stream và backfill để cùng schema.
"""

from __future__ import annotations

import json
from typing import Any

HEARTBEAT = "heartbeat"


class ParseError(Exception):
    """Khung không thành bản ghi ct.raw hợp lệ; `error_type` khớp enum của ct.dlq."""

    def __init__(self, error_type: str, message: str):
        super().__init__(message)
        self.error_type = error_type
        self.message = message


def normalize_sha256(value: str) -> str:
    h = value.replace(":", "").lower()
    if len(h) != 64 or any(c not in "0123456789abcdef" for c in h):
        raise ParseError("invalid_field", f"sha256 không hợp lệ: {value!r}")
    return h


def to_ms(seconds: Any, field: str) -> int:
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)):
        raise ParseError("invalid_field", f"{field} không phải số: {seconds!r}")
    return round(seconds * 1000)


def _require(obj: dict, key: str, where: str) -> Any:
    if not isinstance(obj, dict) or key not in obj or obj[key] is None:
        raise ParseError("missing_field", f"thiếu {where}.{key}")
    return obj[key]


def parse_message(raw: str | bytes, seen_ts: int, collector_id: str) -> dict | None:
    """Trả bản ghi ct.raw, hoặc None với heartbeat. Lỗi → ParseError."""
    try:
        msg = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as e:
        raise ParseError("invalid_json", str(e)) from e
    if not isinstance(msg, dict):
        raise ParseError("invalid_json", "khung không phải object")

    mtype = msg.get("message_type")
    if mtype == HEARTBEAT:
        return None
    if mtype != "certificate_update":
        raise ParseError("invalid_field", f"message_type lạ: {mtype!r}")

    data = _require(msg, "data", "msg")
    leaf = _require(data, "leaf_cert", "data")
    update_type = _require(data, "update_type", "data")
    if update_type not in ("X509LogEntry", "PrecertLogEntry"):
        raise ParseError("invalid_field", f"update_type lạ: {update_type!r}")

    cert_index = _require(data, "cert_index", "data")
    if isinstance(cert_index, bool) or not isinstance(cert_index, int) or cert_index < 0:
        raise ParseError("invalid_field", f"cert_index không hợp lệ: {cert_index!r}")

    source = _require(data, "source", "data")
    domains = _require(leaf, "all_domains", "leaf_cert")
    if not isinstance(domains, list) or not all(isinstance(d, str) and d for d in domains):
        raise ParseError("invalid_field", "all_domains phải là list chuỗi không rỗng")

    rec = {
        "sha256": normalize_sha256(_require(leaf, "sha256", "leaf_cert")),
        "seen_ts": seen_ts,
        "collector_id": collector_id,
        "message_type": mtype,
        "update_type": update_type,
        "cert_index": cert_index,
        "cert_link": data.get("cert_link"),
        "ct_seen": to_ms(data["seen"], "seen") if data.get("seen") is not None else None,
        "submission_ts": (
            to_ms(data["submission_timestamp"], "submission_timestamp")
            if data.get("submission_timestamp") is not None
            else None
        ),
        "source": {
            "name": _require(source, "name", "source"),
            "url": _require(source, "url", "source"),
        },
        "not_before": to_ms(_require(leaf, "not_before", "leaf_cert"), "not_before"),
        "not_after": to_ms(_require(leaf, "not_after", "leaf_cert"), "not_after"),
        "serial_number": leaf.get("serial_number"),
        "fingerprint": leaf.get("fingerprint"),
        "signature_algorithm": leaf.get("signature_algorithm"),
        "is_ca": leaf.get("is_ca"),
        "subject": leaf.get("subject"),
        "issuer": leaf.get("issuer"),
        "all_domains": domains,
        "extensions": leaf.get("extensions"),
    }
    return rec


def dlq_record(
    raw: str | bytes, err: ParseError, seen_ts: int, collector_id: str, limit: int = 65536
) -> dict:
    text = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw
    return {
        "seen_ts": seen_ts,
        "collector_id": collector_id,
        "error_type": err.error_type,
        "error_message": err.message,
        "payload": text[:limit],
        "payload_truncated": len(text) > limit,
    }
