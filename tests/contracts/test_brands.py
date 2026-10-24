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
        for d in b["official_domains"]:
            assert d not in owners, f"{d}: {owners[d]} và {b['brand_id']}"
            owners[d] = b["brand_id"]


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
