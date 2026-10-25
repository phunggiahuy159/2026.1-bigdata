"""Dựng dữ liệu hiển thị cho từng trang. Mọi domain đi qua `display_domain` ở đây,
nên trang Streamlit không bao giờ nhận domain thô."""

from __future__ import annotations

from serving.app.data import Doc, effective, fmt_ts, is_vn
from serving.app.defang import display_domain


def feed_rows(alerts: list[Doc], *, min_score: int = 0, brand: str | None = None) -> list[dict]:
    rows = []
    for alert in alerts:
        if alert["score"] < min_score or (brand and alert.get("brand_id") != brand):
            continue
        rows.append(
            {
                "Thời điểm (UTC)": fmt_ts(alert["alert_ts"]),
                "Domain": display_domain(alert["domain"]),
                "Thương hiệu": alert.get("brand_id") or "",
                "Điểm": alert["score"],
                "Lý do": ", ".join(alert["reasons"]),
            }
        )
    return rows


def domain_options(domains: list[Doc]) -> dict[str, str]:
    """Nhãn hiển thị (đã vô hiệu hoá) sang `_id` thật, sắp theo điểm giảm dần."""
    ordered = sorted(domains, key=lambda d: effective(d)[0], reverse=True)
    return {display_domain(d["_id"]): d["_id"] for d in ordered}


def domain_detail(doc: Doc) -> dict:
    score, reasons, source = effective(doc)
    batch = doc.get("batch") or {}
    enrichment = batch.get("enrichment") or {}
    return {
        "domain": display_domain(doc["_id"]),
        "brand": doc.get("brand_id") or "",
        "score": score,
        "source": source,
        "reasons": reasons,
        "speed_score": doc["speed"]["score"],
        "batch_score": batch.get("score"),
        "first_seen": fmt_ts(doc["speed"]["first_seen_ts"])
        if "first_seen_ts" in doc["speed"]
        else "",
        "campaign_id": batch.get("campaign_id"),
        "enrichment": {
            "ips": [*enrichment.get("a_records", []), *enrichment.get("aaaa_records", [])],
            "nameservers": enrichment.get("ns_records", []),
            "asn": enrichment.get("asn", []),
            "asn_org": enrichment.get("asn_org", []),
            "country": enrichment.get("country", []),
            "dns_status": enrichment.get("dns_status"),
        },
    }


def vn_rows(domains: list[Doc]) -> list[dict]:
    rows = []
    for doc in domains:
        if not is_vn(doc["_id"]):
            continue
        score, reasons, source = effective(doc)
        rows.append(
            {
                "Domain": display_domain(doc["_id"]),
                "Thương hiệu": doc.get("brand_id") or "",
                "Điểm": score,
                "Nguồn điểm": source,
                "Lý do": ", ".join(reasons),
            }
        )
    return sorted(rows, key=lambda r: r["Điểm"], reverse=True)
