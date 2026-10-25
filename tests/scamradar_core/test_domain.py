"""Chuẩn hoá domain: eTLD+1 theo PSL, punycode/IDN, vô hiệu hoá. Không cần mạng."""

import pytest
from scamradar_core import parse, refang, registered_domain, to_ascii, to_unicode
from scamradar_core.psl import PublicSuffixList


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("www.vietcombank.com.vn", "vietcombank.com.vn"),
        ("a.b.c.example.com", "example.com"),
        ("EXAMPLE.COM.", "example.com"),
        ("*.login.example.top", "example.top"),
        ("https://user:pw@shop.example.vn:8443/path?q=1#x", "example.vn"),
        ("hxxps://shop[.]example[.]vn/login", "example.vn"),
        ("abc.gov.vn", "abc.gov.vn"),
        ("sub.abc.gov.vn", "abc.gov.vn"),
        ("foo.co.uk", "foo.co.uk"),
        ("site.github.io", "site.github.io"),  # PRIVATE: mỗi tenant là một domain gốc
        ("a.b.ck", "a.b.ck"),  # luật wildcard *.ck
        ("www.ck", "www.ck"),  # ngoại lệ !www.ck
    ],
)
def test_registered_domain(raw, expected):
    assert registered_domain(raw) == expected


@pytest.mark.parametrize("raw", ["", ".", "com", "com.vn", "gov.vn", "*.com"])
def test_public_suffix_alone_has_no_registered_domain(raw):
    assert registered_domain(raw) == ""


def test_unknown_tld_falls_back_to_last_label():
    assert registered_domain("a.b.unknowntld") == "b.unknowntld"


def test_parts():
    p = parse("login.secure.mombo-vn.example.com.vn")
    assert (p.registered, p.suffix, p.label) == ("example.com.vn", "com.vn", "example")
    assert p.subdomain == "login.secure.mombo-vn"
    assert not p.is_idn


def test_idn_vietnamese_to_punycode():
    p = parse("https://việt-nam.vn/trang")
    assert p.registered == "xn--vit-nam-zv4c.vn"
    assert p.is_idn
    assert p.label == "việt-nam"
    assert registered_domain("Việt-Nam.VN") == p.registered


def test_punycode_roundtrip():
    uni = "ngânhàng.vn"
    ascii_ = to_ascii(uni)
    assert ascii_ == "xn--ngnhng-ltan.vn"
    assert to_unicode(ascii_) == uni
    assert to_unicode("example.com") == "example.com"


def test_idn_suffix_rule_is_ascii():
    # PSL có luật Unicode ("公司.cn", "中国"); nạp vào phải ở dạng punycode
    psl = PublicSuffixList.from_text("// c\ncn\n公司.cn\n")
    assert psl.split("a.xn--55qx5d.cn") == ("a", "xn--55qx5d.cn")


def test_invalid_labels_do_not_raise():
    registered_domain("a..b.com")  # không ném lỗi
    assert registered_domain("x" * 70 + ".com") == "x" * 70 + ".com"


def test_refang():
    assert refang("hxxps://abc[.]com") == "https://abc.com"
    assert refang("abc(.)com") == "abc.com"
