from datetime import UTC, date

import pytest
from pyspark.sql import functions as F

from jobs.batch_silver.contract import table_columns
from jobs.batch_silver.job import compute_updates
from jobs.batch_silver.transforms import OUTPUT_COLUMNS, build_cert_domains

D0, D1, D2, D3 = (date(2026, 10, d) for d in (20, 21, 22, 23))


@pytest.fixture(scope="module")
def full(bronze, norm):
    return build_cert_domains(bronze, norm, D0, D2).cache()


def one(df, fqdn):
    rows = df.where(F.col("fqdn") == fqdn).collect()
    assert len(rows) == 1, (fqdn, len(rows))
    return rows[0]


def test_fixture_follows_bronze_contract(bronze):
    assert [f.name for f in bronze.schema.fields] == [
        c[0] for c in table_columns("bronze.ct_certs")
    ]
    assert 300 <= bronze.count() < 1000


def test_output_matches_silver_ddl(full):
    ddl = table_columns("silver.cert_domains")
    assert [c[0] for c in ddl] == OUTPUT_COLUMNS
    assert [(f.name, f.dataType.simpleString()) for f in full.schema.fields] == [
        (n, t.lower()) for n, t, _ in ddl
    ]
    for name, _, not_null in ddl:
        if not_null:
            assert full.where(F.col(name).isNull()).count() == 0, name


def test_one_row_per_cert_and_fqdn(full):
    assert full.count() == full.dropDuplicates(["cert_key", "fqdn"]).count()


def test_registered_domain_columns_are_punycode_lowercase(full):
    bad = full.where(
        ~F.col("registered_domain").rlike(r"^[a-z0-9]([a-z0-9.-]*[a-z0-9])?$")
        | ~F.col("fqdn").rlike(r"^[a-z0-9_.-]+$")
    )
    assert bad.count() == 0
    assert full.where(~F.col("fqdn").endswith(F.col("registered_domain"))).count() == 0


def test_split_columns_for_multi_label_suffix(full):
    rows = full.where(F.col("tld") == "com.vn").collect()
    assert rows
    for r in rows:
        assert r.registered_domain.endswith(".com.vn") and r.registered_domain.count(".") == 2
        assert r.fqdn == (
            f"{r.subdomain}.{r.registered_domain}" if r.subdomain else r.registered_domain
        )


def test_dirty_names_normalised_or_dropped(full):
    mixed = one(full, "www.mixed-case.fixture-acme.com")  # hoa/thường, dấu chấm cuối được chuẩn hoá
    assert mixed.registered_domain == "fixture-acme.com" and mixed.subdomain == "www.mixed-case"
    assert mixed.san_count == 4  # đếm cả tên bị loại (IP, localhost, com.vn); chỉ bỏ tên rỗng
    for dropped in ("1.2.3.4", "localhost", "com.vn", ""):
        assert full.where(F.col("fqdn") == dropped).count() == 0


def test_idn_becomes_punycode(full):
    r = one(full, "xn--bnh-fixture-k7a.vn")
    assert r.registered_domain == "xn--bnh-fixture-k7a.vn" and r.subdomain is None
    assert one(full, "www.xn--bnh-fixture-k7a.vn").registered_domain == "xn--bnh-fixture-k7a.vn"


def test_precert_and_final_merge_into_one_row(full, bronze):
    pairs = full.where(F.col("has_precert") & F.col("has_final_cert"))
    assert pairs.count() > 50
    r = pairs.limit(1).collect()[0]
    assert len(r.cert_sha256s) == 2
    only_pre = full.where(F.col("has_precert") & ~F.col("has_final_cert"))
    # fixture: mọi precert có cert cuối trong D0..D2, trừ `late` (cert cuối đến ngày D3)
    assert {r.fqdn for r in only_pre.collect()} == {"late.fixture-acme.com"}


def test_duplicate_collectors_are_deduplicated(full):
    # fixture: collector c2 thấy lại cùng bản ghi (cùng sha) nhưng sha không bị đếm hai lần
    assert full.where(F.size("cert_sha256s") > 2).count() == 0
    singles = full.where(~F.col("has_precert") & (F.size("cert_sha256s") != 1))
    assert singles.count() == 0


def test_missing_serial_uses_sha256_key(full):
    rows = full.where(F.col("fqdn") == "noserial.fixture-acme.net").collect()
    assert sorted(r.cert_key for r in rows) == ["sha256:" + "a" * 64, "sha256:" + "b" * 64]
    assert all(len(r.cert_sha256s) == 1 for r in rows)  # bản c2 của sha a khử trùng


def test_serial_case_does_not_split_precert_and_cert(full):
    r = one(full, "boundary.fixture-acme.com")
    assert r.cert_key == "Fixture CA R1|B0"
    assert r.has_precert and r.has_final_cert


def test_wildcard_and_base_name_in_same_cert(full):
    r = one(full, "both.fixture-acme.com")
    assert r.is_wildcard is True and r.san_count == 2


def test_date_range_excludes_outside_and_requires_order(bronze, norm, full):
    assert full.where(F.col("fqdn") == "outside-range.fixture-acme.com").count() == 0
    wide = build_cert_domains(bronze, norm, D0, date(2026, 10, 26))
    assert wide.where(F.col("fqdn") == "outside-range.fixture-acme.com").count() == 1
    with pytest.raises(ValueError):
        build_cert_domains(bronze, norm, D2, D0)


def test_lookback_pairs_precert_from_previous_day(bronze, norm):
    # chạy chỉ ngày D2: precert nằm ở D1 (23:59:58), cert cuối ở D2 (00:00:03)
    r = one(build_cert_domains(bronze, norm, D2, D2), "boundary.fixture-acme.com")
    assert r.has_precert and r.has_final_cert
    # cert_ts thuộc ngày của precert (D1, 23:59:58 UTC), không nhảy sang D2
    got = build_cert_domains(bronze, norm, D2, D2).where(
        F.col("fqdn") == "boundary.fixture-acme.com"
    )
    assert got.select(F.col("cert_ts").cast("date").alias("d")).collect()[0].d == D1
    assert got.select(F.date_format("cert_ts", "HH:mm:ss").alias("t")).collect()[0].t == "23:59:58"


def keyed(df):
    return {(r.cert_key, r.fqdn): r.asDict() for r in df.collect()}


def run_day(spark, silver, bronze, norm, day):
    """Một lần chạy job cho `day`: đúng đường `run_iceberg` (compute_updates) rồi MERGE.

    MERGE thay cả dòng có cùng (cert_key, fqdn) và chèn dòng mới. `silver` là toàn bộ bảng đích,
    không lọc, đúng như job đọc.
    """
    rows = compute_updates(bronze, silver, norm, day, day)
    kept = silver.join(rows.select("cert_key", "fqdn"), ["cert_key", "fqdn"], "left_anti")
    out = kept.unionByName(rows)
    # cắt lineage: bảng silver mẫu nhỏ, đọc về rồi tạo lại như một bảng đã ghi
    return spark.createDataFrame(out.collect(), out.schema)


def run_days(spark, bronze, norm, schema, days):
    silver = spark.createDataFrame([], schema)
    for day in days:
        silver = run_day(spark, silver, bronze, norm, day)
    return silver


@pytest.fixture(scope="module")
def full_all(bronze, norm):
    return build_cert_domains(bronze, norm, D0, D3).cache()


def test_day_by_day_equals_single_run(spark, bronze, norm, full_all):
    silver = run_days(spark, bronze, norm, full_all.schema, (D0, D1, D2, D3))
    got, want = keyed(silver), keyed(full_all)
    assert got.keys() == want.keys()
    for k in want:
        assert got[k] == want[k], k


def test_midnight_pair_survives_following_days(spark, bronze, norm, full_all):
    """Hồi quy: chạy ngày 21, 22, 23. Lần chạy ngày 23 đọc lại bronze ngày 22 (chỉ cert cuối)
    nhưng không được làm mất cờ precert, sha thứ hai và cert_ts của dòng đã ghi."""
    silver = spark.createDataFrame([], full_all.schema)
    seen = []
    for day in (D1, D2, D3):
        silver = run_day(spark, silver, bronze, norm, day)
        r = one(silver, "boundary.fixture-acme.com")
        seen.append((day, r.has_precert, r.has_final_cert, len(r.cert_sha256s)))
        assert r.cert_ts.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S") == "2026-10-21 23:59:58"
    assert seen == [(D1, True, False, 1), (D2, True, True, 2), (D3, True, True, 2)]


def test_final_cert_arriving_days_after_precert_is_merged(spark, bronze, norm, full_all):
    silver = run_days(spark, bronze, norm, full_all.schema, (D0, D1, D2, D3))
    r = one(silver, "late.fixture-acme.com")
    assert r.has_precert and r.has_final_cert and len(r.cert_sha256s) == 2
    assert r.cert_ts.astimezone(UTC).strftime("%Y-%m-%d") == "2026-10-20"  # ngày của precert


def test_rerun_any_day_is_idempotent(spark, bronze, norm, full_all):
    silver = run_days(spark, bronze, norm, full_all.schema, (D0, D1, D2, D3, D3, D1, D2, D0, D3))
    assert keyed(silver) == keyed(full_all)
