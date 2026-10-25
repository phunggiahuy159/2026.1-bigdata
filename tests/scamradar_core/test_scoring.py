"""Hàm điểm: tập 50 domain mẫu tự đặt, official/other_domains, khớp alerts.v1. Không cần mạng."""

import csv
import json
import re
from pathlib import Path

import pytest
from scamradar_core import (
    Scorer,
    edit_distance,
    entropy,
    lexical_features,
    load_brands,
    match_brand,
)
from scamradar_core.matching import build_index

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BRANDS = load_brands()
SCORER = Scorer(BRANDS)
ROWS = list(csv.DictReader((HERE / "sample_domains.csv").open(encoding="utf-8")))


def test_sample_has_50_domains():
    assert len(ROWS) >= 50


@pytest.mark.parametrize("row", ROWS, ids=lambda r: r["domain"])
def test_sample_domain(row):
    r = SCORER.score(row["domain"])  # CSV lưu dạng vô hiệu hoá a[.]b, thư viện tự refang
    assert int(row["min_score"]) <= r.score <= int(row["max_score"]), (r.score, r.reasons)
    assert (r.brand_id or "") == row["brand_id"], r.reasons


def test_official_domains_never_flagged():
    for b in BRANDS:
        for d in b.official_domains:
            for host in (d, f"www.{d}", f"login-secure.otp.{d}"):
                r = SCORER.score(host)
                assert r.score == 0 and r.reasons == ["official_domain"], host


def test_other_domains_exempt_but_distinguishable():
    others = [(b, d) for b in BRANDS for d in b.other_domains]
    assert others
    for b, d in others:
        r = SCORER.score(f"login.{d}")
        assert r.score == 0 and r.reasons == ["other_domain_unverified"], d
        assert r.brand_id == b.brand_id


def test_optional_brands_off_by_default():
    assert "paypal" not in {b.brand_id for b in BRANDS}
    with_opt = Scorer(load_brands(include_optional=True))
    assert with_opt.score("paypal-login.top").brand_id == "paypal"
    assert SCORER.score("paypal-login.top").brand_id is None


def test_alert_fields_match_alerts_v1_schema():
    schema = json.loads((ROOT / "contracts/kafka/alerts.v1.schema.json").read_text("utf-8"))
    props = schema["properties"]
    domain_re = re.compile(props["domain"]["pattern"])
    for row in ROWS:
        f = SCORER.score(row["domain"]).as_alert_fields()
        assert set(f) <= set(props)
        assert isinstance(f["score"], int) and 0 <= f["score"] <= 100
        assert all(isinstance(x, str) for x in f["reasons"])
        assert f["brand_id"] is None or isinstance(f["brand_id"], str)
        assert domain_re.match(f["domain"]), f["domain"]


def test_score_is_deterministic_and_clamped():
    a = SCORER.score("mbbank-capnhat-taikhoan-otp-secure-login-verify.xyz")
    assert a == SCORER.score("mbbank-capnhat-taikhoan-otp-secure-login-verify.xyz")
    assert 0 <= a.score <= 100


def test_non_brand_domains_are_capped():
    r = SCORER.score("dangnhap-xacthuc-taikhoan-update-secure-login-2024-2025.icu")
    assert r.brand_id is None and r.score <= 60


def test_default_scorer_uses_repo_brands():
    from scamradar_core import score_domain

    assert score_domain("momo.vn").score == 0
    assert score_domain("momo-khuyenmai.top").brand_id == "momo"


def test_no_registered_domain():
    r = SCORER.score("com.vn")
    assert r.score == 0 and r.reasons == ["no_registered_domain"]


def test_lexical_features():
    f = lexical_features("login-secure-vietcombank-2024", "top", subdomain="")
    assert f.hyphens == 3 and f.risky_tld and {"login", "secure"} <= set(f.keywords)
    assert f.length == 29 and 0 < f.digit_ratio < 0.2
    assert lexical_features("khuyến-mãi", "vn").keywords == ("khuyenmai",)
    assert "xacthuc" in lexical_features("abc", "vn", subdomain="xacthuc").keywords
    assert not lexical_features("abc", "com.vn").risky_tld


def test_edit_distance_and_entropy():
    assert edit_distance("kitten", "sitting") == 3
    assert edit_distance("momo", "momo") == 0
    assert edit_distance("abcdef", "uvwxyz", limit=2) == 3  # vượt limit thì dừng sớm
    assert entropy("aaaa") == 0 and entropy("abcd") == pytest.approx(2.0)
    assert entropy("") == 0


def test_match_brand_kinds():
    idx = build_index(BRANDS)
    assert match_brand("vietcombank-login", idx).kind == "exact"
    assert match_brand("v1etcombank", idx).kind == "homoglyph"
    m = match_brand("vietcombamk", idx)
    assert (m.kind, m.distance) == ("fuzzy", 1)
    assert match_brand("hoa-qua-tuoi", idx) is None
    assert match_brand("acbconstruction", idx) is None  # acb chỉ khớp nguyên token
    assert match_brand("acb-login", idx).brand_id == "acb"
    assert match_brand("vietcombank", idx, skip={"vietcombank"}) is None
