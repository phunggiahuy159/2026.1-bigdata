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
        ("x.github.io", ("x.github.io", None, "github.io")),  # PRIVATE: tenant là domain gốc riêng
        ("a.x.github.io", ("x.github.io", "a", "github.io")),
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


def test_load_psl_rules_includes_private_like_scamradar_core(tmp_path):
    f = tmp_path / "psl.dat"
    f.write_text(
        "// c\ncom\n*.ck\n!www.ck\n// ===BEGIN PRIVATE DOMAINS===\ngithub.io\n", encoding="utf-8"
    )
    assert load_psl_rules(f) == {"com", "*.ck", "!www.ck", "github.io"}
    assert "github.io" not in load_psl_rules(f, include_private=False)


def test_unicode_psl_rules_become_punycode(
    tmp_path,
):
    f = tmp_path / "psl.dat"
    f.write_text("com\n公司.cn\n*.рф\n", encoding="utf-8")
    rules = load_psl_rules(f)
    assert "xn--55qx5d.cn" in rules and "*.xn--p1ai" in rules
    assert not any(not r.isascii() for r in rules)
