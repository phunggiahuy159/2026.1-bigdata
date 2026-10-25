"""Chuẩn hoá tên miền cho batch_silver: dùng chung `scamradar_core` với speed layer.

Cùng thư viện nên khoá domain hai lớp khớp nhau (kể cả PSL PRIVATE: `x.github.io` là domain gốc
riêng, punycode ASCII, viết thường). File này chỉ điều chỉnh đầu ra cho đúng DDL: `subdomain` giữ
dạng ASCII.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from scamradar_core import parse, to_ascii

# (domain gốc eTLD+1, subdomain hoặc None, public suffix); None nếu tên là suffix/không hợp lệ
SplitResult = tuple[str, str | None, str] | None
SplitFn = Callable[[str], SplitResult]
ToAsciiFn = Callable[[str], str | None]


def split(fqdn: str) -> SplitResult:
    """Tách một tên ASCII đã làm sạch thành (domain gốc, subdomain, suffix)."""
    parts = parse(fqdn)
    if not parts.registered:
        return None
    sub = parts.host[: -len(parts.registered)].rstrip(".")
    return parts.registered, sub or None, parts.suffix


@dataclass(frozen=True)
class Normalizer:
    to_ascii: ToAsciiFn
    split: SplitFn


def default_normalizer() -> Normalizer:
    """Normalizer dùng PSL kèm theo scamradar_core (đổi file bằng biến môi trường SCAMRADAR_PSL)."""
    return Normalizer(to_ascii=to_ascii, split=split)
