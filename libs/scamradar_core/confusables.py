"""Ký tự dễ nhầm: bỏ dấu tiếng Việt, đồng hình Cyrillic/Greek, số giả chữ, chữ ghép.

Bảng tự soạn, nhỏ (xem data/NOTICE.md), dùng để đưa nhãn tên miền về "khung" (skeleton) rồi
so khớp với tên thương hiệu.
"""

from __future__ import annotations

import unicodedata

_HOMOGLYPHS = {
    # Cyrillic giống Latin
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x", "у": "y",
    "і": "i", "ј": "j", "ѕ": "s", "һ": "h", "ԁ": "d", "ԛ": "q", "ԝ": "w",
    # Greek giống Latin
    "α": "a", "ο": "o", "ν": "v", "ρ": "p", "τ": "t", "ι": "i", "κ": "k",
    # chữ Latin không phân rã được bằng NFKD
    "đ": "d", "ı": "i", "ɡ": "g", "ø": "o", "ł": "l",
}  # fmt: skip
_DIGITS = {"0": "o", "3": "e", "4": "a", "5": "s", "7": "t", "8": "b", "9": "g"}
_MULTI = (("rn", "m"), ("vv", "w"), ("cl", "d"))


def strip_marks(s: str) -> str:
    """Chữ thường, đồng hình về Latin, bỏ dấu (việt -> viet, đ -> d)."""
    s = "".join(_HOMOGLYPHS.get(c, c) for c in s.lower())
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return "".join(_HOMOGLYPHS.get(c, c) for c in s)


def skeletons(label: str) -> list[str]:
    """Các dạng khung khả dĩ của một nhãn. Phần tử đầu chỉ bỏ dấu/đồng hình; các phần tử sau
    thêm số giả chữ (1 có thể là l hoặc i) và chữ ghép (rn -> m)."""
    base = strip_marks(label)
    out = [base]
    mapped = "".join(_DIGITS.get(c, c) for c in base)
    for one in ("l", "i"):
        v = mapped.replace("1", one)
        for a, b in _MULTI:
            v = v.replace(a, b)
        if v not in out:
            out.append(v)
    return out


def has_confusables(label: str) -> bool:
    """Nhãn có ký tự ngoài ASCII, hoặc số lẫn trong chữ (kiểu m0mo)."""
    if any(ord(c) > 127 for c in label):
        return True
    return any(c.isdigit() for c in label) and any(c.isalpha() for c in label)
