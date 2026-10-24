"""Kiểm tra DDL Iceberg bằng stdlib: đủ bảng, khớp ct.raw, partition đúng hợp đồng."""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2] / "contracts"
ICEBERG = ROOT / "iceberg"

TABLES = {
    "bronze.ct_certs": "days(seen_ts)",
    "silver.cert_domains": "days(cert_ts), bucket(32, registered_domain)",
    "silver.domain_features": "feature_date",
    "silver.enrichment": "bucket(32, registered_domain)",
    "silver.labels": "bucket(32, registered_domain)",
    "gold.domain_history": "bucket(32, registered_domain)",
    "gold.domain_scores": "score_date",
    "gold.campaigns": "run_date",
    "gold.brand_daily": "days(day)",
    "gold.vn_daily": "days(day)",
}

# trường ct.raw -> cột bronze khi tên khác hoặc làm phẳng; None = không lưu
RAW_TO_BRONZE = {
    "message_type": None,
    "extensions": None,
    "subject": "subject_cn",
    "issuer": "issuer_cn",
    "source": "source_name",
}
RAW_TS_MS = {"seen_ts", "not_before", "not_after", "ct_seen", "submission_ts"}


def columns(table):
    sql = (ICEBERG / f"{table}.sql").read_text(encoding="utf-8")
    body = sql[sql.index("(") : sql.index(")\nUSING")]
    cols = {}
    for line in body.splitlines():
        m = re.match(r"\s+(\w+)\s+([A-Z]+(?:<.*?>)?)", line)
        if m:
            cols[m.group(1)] = (m.group(2), "NOT NULL" in line)
    return cols


def test_all_tables_have_ddl():
    found = {p.stem for p in ICEBERG.glob("*.sql")} - {"00_namespaces"}
    assert found == set(TABLES)


@pytest.mark.parametrize("table,spec", TABLES.items())
def test_partition_spec(table, spec):
    sql = (ICEBERG / f"{table}.sql").read_text(encoding="utf-8")
    assert f"PARTITIONED BY ({spec})" in sql
    assert "USING iceberg" in sql
    assert "'format-version' = '2'" in sql


@pytest.mark.parametrize("table", TABLES)
def test_columns_parse_and_partition_columns_exist(table):
    cols = columns(table)
    assert cols
    sql = (ICEBERG / f"{table}.sql").read_text(encoding="utf-8")
    spec = re.search(r"PARTITIONED BY \((.*)\)", sql).group(1)
    for ref in re.findall(r"(\w+)(?:\)|,|$)", spec.replace("32, ", "")):
        if ref not in {"days", "bucket"}:
            assert ref in cols, (table, ref)


def test_bronze_matches_ct_raw():
    raw = json.loads((ROOT / "kafka" / "ct.raw.schema.json").read_text(encoding="utf-8"))
    bronze = columns("bronze.ct_certs")
    for name in raw["properties"]:
        target = RAW_TO_BRONZE.get(name, name)
        if target is None:
            assert name not in bronze
            continue
        assert target in bronze, f"ct.raw.{name} thiếu cột {target}"
        if name in RAW_TS_MS:
            assert bronze[target][0] == "TIMESTAMP", name
    for name in raw["required"]:
        target = RAW_TO_BRONZE.get(name, name)
        assert bronze[target][1], f"{target} phải NOT NULL vì ct.raw.{name} là required"
    assert "serial_number" in bronze and not bronze["serial_number"][1]  # ct.raw cho phép null


def test_domain_key_is_registered_domain():
    for table in TABLES:
        cols = columns(table)
        assert "domain" not in cols, table


def ddl(table):
    return (ICEBERG / f"{table}.sql").read_text(encoding="utf-8")


@pytest.mark.parametrize("table", ["gold.domain_history", "silver.enrichment", "silver.labels"])
def test_bucket_only_tables_document_merge_only(table):
    sql = ddl(table)
    assert "days(" not in sql.split("USING iceberg")[1].split("TBLPROPERTIES")[0]
    assert "MERGE INTO" in sql and "KHÔNG overwritePartitions" in sql


def test_cert_domains_documents_late_precert_and_missing_serial():
    sql = ddl("silver.cert_domains")
    assert "MERGE INTO" in sql and "lùi 1 ngày" in sql
    assert "sha256:" in sql


@pytest.mark.parametrize(
    "table,column",
    [
        ("silver.cert_domains", "fqdn"),
        ("silver.cert_domains", "registered_domain"),
        ("silver.enrichment", "registered_domain"),
        ("silver.labels", "registered_domain"),
        ("gold.domain_history", "registered_domain"),
        ("gold.domain_scores", "registered_domain"),
        ("silver.domain_features", "registered_domain"),
    ],
)
def test_domain_columns_are_ascii_punycode(table, column):
    line = next(ln for ln in ddl(table).splitlines() if ln.strip().startswith(column + " "))
    assert "punycode" in line


def test_enrichment_ip_arrays_cover_a_and_aaaa():
    sql = ddl("silver.enrichment")
    for col in ("asn", "asn_org", "country"):
        line = next(ln for ln in sql.splitlines() if ln.strip().startswith(col + " "))
        assert "aaaa_records" in line, col


def test_readme_requires_utc_session_timezone():
    readme = (ICEBERG / "README.md").read_text(encoding="utf-8")
    assert "spark.sql.session.timeZone=UTC" in readme
