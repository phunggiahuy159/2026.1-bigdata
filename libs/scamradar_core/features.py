"""Đặc trưng từ vựng của một nhãn tên miền."""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

from .confusables import has_confusables, strip_marks

SUSPICIOUS_KEYWORDS = (
    "login", "signin", "dangnhap", "xacthuc", "xacminh", "verify", "secure", "account",
    "taikhoan", "update", "capnhat", "otp", "khuyenmai", "trungthuong", "nhanqua", "hoantien",
    "uudai", "quatang", "tindung", "support", "hotro", "thanhtoan", "payment", "wallet",
    "mokhoa", "khoatk", "phatnguoi", "congan",
)  # fmt: skip
RISKY_TLDS = frozenset(
    "top xyz icu click vip live cc cfd sbs buzz cyou online site club link info work support "
    "rest monster fun today shop store bond tk ml ga cf gq".split()
)


def edit_distance(a: str, b: str, limit: int = 99) -> int:
    """Levenshtein; trả limit + 1 ngay khi chắc chắn vượt limit."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        if min(cur) > limit:
            return limit + 1
        prev = cur
    return prev[-1]


def entropy(s: str) -> float:
    """Entropy Shannon (bit/ký tự)."""
    if not s:
        return 0.0
    n = len(s)
    return -sum(c / n * math.log2(c / n) for c in Counter(s).values())


@dataclass(frozen=True)
class LexicalFeatures:
    length: int
    hyphens: int
    digit_ratio: float
    entropy: float
    risky_tld: bool
    keywords: tuple[str, ...]
    has_confusables: bool
    is_idn: bool


def lexical_features(
    label: str, suffix: str, is_idn: bool = False, subdomain: str = ""
) -> LexicalFeatures:
    """Đặc trưng của nhãn đăng ký; từ khoá nghi vấn tìm cả ở subdomain (login.abc.xyz)."""
    low = label.lower()
    # bỏ dấu để "khuyến-mãi" khớp từ khoá "khuyenmai"
    flat = strip_marks(f"{subdomain}.{low}").replace("-", "").replace(".", "")
    return LexicalFeatures(
        length=len(low),
        hyphens=low.count("-"),
        digit_ratio=sum(c.isdigit() for c in low) / len(low) if low else 0.0,
        entropy=entropy(low.replace("-", "")),
        risky_tld=suffix.rsplit(".", 1)[-1] in RISKY_TLDS,
        keywords=tuple(k for k in SUSPICIOUS_KEYWORDS if k in flat),
        has_confusables=has_confusables(low),
        is_idn=is_idn,
    )
