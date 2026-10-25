import pytest

from jobs.batch_silver.normalize import split


@pytest.mark.parametrize(
    "fqdn,expected",
    [
        ("example.com", ("example.com", None, "com")),
        ("a.b.example.com", ("example.com", "a.b", "com")),
        ("shop.example.com.vn", ("example.com.vn", "shop", "com.vn")),
        ("example.unknowntld", ("example.unknowntld", None, "unknowntld")),  # luật mặc định "*"
        ("x.foo.ck", ("x.foo.ck", None, "foo.ck")),  # *.ck
        ("www.ck", ("www.ck", None, "ck")),  # !www.ck
        ("x.github.io", ("x.github.io", None, "github.io")),  # PRIVATE: tenant là domain gốc riêng
        ("a.x.github.io", ("x.github.io", "a", "github.io")),
        ("xn--bnh-fixture-k7a.vn", ("xn--bnh-fixture-k7a.vn", None, "vn")),
        ("com.vn", None),  # chính là public suffix
        ("com", None),
    ],
)
def test_split_matches_scamradar_core_psl(fqdn, expected):
    assert split(fqdn) == expected


def test_to_ascii_punycode(norm):
    assert norm.to_ascii("bánh-fixture.vn") == "xn--bnh-fixture-k7a.vn"
    assert norm.to_ascii("example.com") == "example.com"
