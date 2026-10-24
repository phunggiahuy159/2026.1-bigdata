"""Kiểm tra data/reference/brands.yaml: định dạng, trùng lặp, quy ước domain."""

import re
from collections import Counter
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
BRANDS = yaml.safe_load((ROOT / "data/reference/brands.yaml").read_text(encoding="utf-8"))["brands"]
CATEGORIES = {
    "bank",
    "finance",
    "ewallet",
    "ecommerce",
    "telecom",
    "gov",
    "logistics",
    "game",
    "insurance",
    "service",
}
# Cùng dạng với brand_id dùng ở key Redis cnt:{brand}:{minute} (không chứa ':').
BRAND_ID = re.compile(r"^[a-z0-9_]+$")
# ASCII punycode, chữ thường, ít nhất hai nhãn.
DOMAIN = re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9-]+$")


def ids():
    return [b["brand_id"] for b in BRANDS]


def test_at_least_80_brands():
    assert len(BRANDS) >= 80


def test_brand_ids_unique_and_well_formed():
    dup = [i for i, n in Counter(ids()).items() if n > 1]
    assert not dup, dup
    bad = [i for i in ids() if not BRAND_ID.match(i)]
    assert not bad, bad


@pytest.mark.parametrize("brand", BRANDS, ids=ids())
def test_brand_fields(brand):
    assert brand["name"].strip()
    assert brand["category"] in CATEGORIES
    assert brand["official_domains"], "thiếu domain chính thức"
    assert brand["keywords"], "thiếu từ khoá"
    assert brand["aliases"], "thiếu biến thể viết tắt"
    assert isinstance(brand["verified"], bool)
    if brand["verified"]:
        assert brand.get("source", "").startswith("https://"), "verified thiếu source https"
    else:
        assert brand.get("note", "").strip(), "chưa verified thì phải có note"
    for kw in [*brand["keywords"], *brand["aliases"]]:
        assert kw == kw.lower().strip() and kw, (brand["brand_id"], kw)
        assert re.match(r"^[a-z0-9]+$", kw), (brand["brand_id"], kw)


def test_official_domains_are_ascii_lowercase():
    for b in BRANDS:
        for d in b["official_domains"]:
            assert DOMAIN.match(d), (b["brand_id"], d)
            assert "[" not in d and "hxxp" not in d


def test_no_domain_shared_between_brands():
    owners = {}
    for b in BRANDS:
        for d in [*b["official_domains"], *b.get("other_domains", [])]:
            assert d not in owners, f"{d}: {owners[d]} và {b['brand_id']}"
            owners[d] = b["brand_id"]


def test_optional_is_bool_and_only_three_international_brands():
    for b in BRANDS:
        assert isinstance(b.get("optional", False), bool), b["brand_id"]
    assert {b["brand_id"] for b in BRANDS if b.get("optional")} == {"paypal", "steam", "facebook"}


def test_no_keyword_shared_between_brands():
    owners = {}
    for b in BRANDS:
        for kw in b["keywords"]:
            assert kw not in owners or owners[kw] == b["brand_id"], (kw, owners[kw], b["brand_id"])
            owners[kw] = b["brand_id"]


def test_other_domains_ascii_lowercase_and_distinct_from_official():
    count = 0
    for b in BRANDS:
        others = b.get("other_domains", [])
        assert len(others) == len(set(others)), b["brand_id"]
        for d in others:
            count += 1
            assert DOMAIN.match(d), (b["brand_id"], d)
            assert d not in b["official_domains"], (b["brand_id"], d)
    assert count > 0


def test_discontinued_brands_kept_with_note():
    by_id = {b["brand_id"]: b for b in BRANDS}
    for bid in ("sendo", "moca", "mic", "timo"):
        assert bid in by_id and "bị mạo danh" in by_id[bid]["note"], bid


def test_most_brands_verified():
    verified = sum(b["verified"] for b in BRANDS)
    assert verified >= len(BRANDS) // 2


def test_each_category_present_and_unverified_notes():
    assert {b["category"] for b in BRANDS} == CATEGORIES
    for b in BRANDS:
        if "note" in b:
            assert b["note"].strip()


def test_downloaded_files_not_tracked():
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "data/reference/*" in ignore and "!data/reference/brands.yaml" in ignore
