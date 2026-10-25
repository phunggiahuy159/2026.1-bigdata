import pytest

from serving.app.defang import (
    defang_domain,
    defang_text,
    defang_url,
    defang_value,
    display_domain,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("abc.com", "abc[.]com"),
        ("a.b.com.vn", "a[.]b[.]com[.]vn"),
        ("xn--demo-bidv-9xa.net", "xn--demo-bidv-9xa[.]net"),
        ("abc[.]com", "abc[.]com"),
    ],
)
def test_defang_domain(raw, expected):
    assert defang_domain(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://abc.com", "hxxps://abc[.]com"),
        ("http://abc.com/path.html?q=1", "hxxp://abc[.]com/path[.]html?q=1"),
        ("HTTPS://ABC.com", "hxxps://ABC[.]com"),
        ("abc.com", "hxxps://abc[.]com"),
        ("hxxps://abc[.]com", "hxxps://abc[.]com"),
    ],
)
def test_defang_url(raw, expected):
    assert defang_url(raw) == expected


def test_display_domain_matches_convention():
    assert display_domain("abc.com") == "hxxps://abc[.]com"


def test_defanged_output_never_contains_clickable_scheme():
    out = display_domain("login.example.vn")
    assert "http://" not in out and "https://" not in out and ".vn" not in out


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("ns1.evil.example", "ns1[.]evil[.]example"),
        ("192.0.2.10", "192[.]0[.]2[.]10"),
        ("2001:db8::1", "2001:db8::1"),
        ("visit https://bad.example/x now", "visit hxxps://bad[.]example/x now"),
        ("Example.com Hosting LLC", "Example[.]com Hosting LLC"),
        ("typosquat", "typosquat"),
        ("DEMO-HOSTING", "DEMO-HOSTING"),
        ("score 1.5 ok", "score 1.5 ok"),
        ("hxxps://abc[.]com", "hxxps://abc[.]com"),
        ("abc[.]com", "abc[.]com"),
    ],
)
def test_defang_text(raw, expected):
    assert defang_text(raw) == expected


def test_defang_text_is_idempotent():
    once = defang_text("a.b.example 192.0.2.1 http://c.example")
    assert defang_text(once) == once


def test_defang_value_walks_nested_structures():
    value = {"ns": ["ns1.bad.example"], "n": 5, "x": {"u": "http://bad.example"}, "none": None}
    assert defang_value(value) == {
        "ns": ["ns1[.]bad[.]example"],
        "n": 5,
        "x": {"u": "hxxp://bad[.]example"},
        "none": None,
    }
