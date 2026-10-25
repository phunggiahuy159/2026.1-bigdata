import pytest

from jobs.batch_silver.normalize import load_psl_rules, to_ascii


@pytest.mark.parametrize(
    "fqdn,expected",
    [
        ("example.com", ("example.com", None, "com")),
        ("a.b.example.com", ("example.com", "a.b", "com")),
        ("shop.example.com.vn", ("example.com.vn", "shop", "com.vn")),
        ("example.unknowntld", ("example.unknowntld", None, "unknowntld")),  # luật mặc định "*"
        ("x.foo.ck", ("x.foo.ck", None, "foo.ck")),  # *.ck
        ("www.ck", ("www.ck", None, "ck")),  # !www.ck
        ("com.vn", None),  # chính là public suffix
        ("com", None),
    ],
)
def test_split_psl(norm, fqdn, expected):
    assert norm.split(fqdn) == expected


def test_to_ascii_punycode():
    assert to_ascii("bánh-fixture.vn") == "xn--bnh-fixture-k7a.vn"
    assert to_ascii("example.com") == "example.com"
    assert to_ascii("a" * 70 + ".com") is None  # nhãn quá dài, không mã hoá được


def test_load_psl_rules_icann_only(tmp_path):
    f = tmp_path / "psl.dat"
    f.write_text(
        "// c\ncom\n*.ck\n!www.ck\n// ===BEGIN PRIVATE DOMAINS===\ngithub.io\n", encoding="utf-8"
    )
    assert load_psl_rules(f) == {"com", "*.ck", "!www.ck"}
    assert "github.io" in load_psl_rules(f, include_private=True)
