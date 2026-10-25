import pytest

from serving.app.defang import defang_domain, defang_url, display_domain


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
