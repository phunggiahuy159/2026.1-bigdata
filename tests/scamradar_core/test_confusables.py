"""Bảng ký tự dễ nhầm."""

import pytest
from scamradar_core.confusables import has_confusables, skeletons, strip_marks


@pytest.mark.parametrize(
    "label,expected",
    [
        ("việt", "viet"),
        ("ngânhàng", "nganhang"),
        ("đại", "dai"),
        ("momо", "momo"),  # chữ о Cyrillic
        ("раураl", "paypal"),  # Cyrillic р, а, у
    ],
)
def test_strip_marks(label, expected):
    assert strip_marks(label) == expected


def test_skeletons_digits_and_ligatures():
    assert "momo" in skeletons("m0m0")
    assert "vietcombank" in skeletons("vietc0mbank")
    assert "mobifone" in skeletons("rnobifone")  # rn -> m
    assert any(s == "vib" for s in skeletons("v1b"))
    assert any(s == "lazada" for s in skeletons("1azada"))


def test_first_skeleton_keeps_digits():
    assert skeletons("tiki2024")[0] == "tiki2024"


def test_has_confusables():
    assert has_confusables("m0mo")
    assert has_confusables("việt")
    assert not has_confusables("momo")
    assert not has_confusables("123456")
