"""Chuẩn hoá tên miền: punycode và tách domain gốc (eTLD+1) theo Public Suffix List.

TODO: thay toàn bộ file này bằng `scamradar_core` của P3 (PR #14) khi thư viện được merge.
Giữ nguyên chữ ký `ToAsciiFn` / `SplitFn` để transform không phải đổi. Quy tắc giữ cùng thư viện
của P3 để khoá domain hai lớp (batch và speed) khớp nhau: tính cả phần PRIVATE của PSL (`x.github.io` là domain gốc
riêng), luật Unicode của PSL đổi sang punycode, domain gốc là eTLD+1,
ASCII punycode, viết thường (xem contracts/iceberg/README.md).
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

# (domain gốc eTLD+1, subdomain hoặc None, public suffix); None nếu tên là suffix/không hợp lệ
SplitResult = tuple[str, str | None, str] | None
SplitFn = Callable[[str], SplitResult]
ToAsciiFn = Callable[[str], str | None]

DEFAULT_PSL_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "reference" / "public_suffix_list.dat"
)
_PRIVATE_MARK = "===BEGIN PRIVATE DOMAINS==="


def _rule_to_ascii(rule: str) -> str:
    """Luật PSL Unicode (ví dụ `公司.cn`) sang punycode, vì tên miền đã được đổi sang ASCII."""
    labels = []
    for label in rule.split("."):
        if label != "*" and not label.isascii():
            label = label.encode("idna").decode("ascii")
        labels.append(label)
    return ".".join(labels)


def load_psl_rules(path: str | os.PathLike[str], include_private: bool = True) -> frozenset[str]:
    """Đọc file PSL. Mặc định gồm cả phần PRIVATE, giống scamradar_core: mỗi tenant của dịch vụ
    lưu trữ (github.io, web.app, ...) là một domain gốc riêng."""
    rules: set[str] = set()
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if _PRIVATE_MARK in line and not include_private:
            break
        line = line.strip()
        if line and not line.startswith("//"):
            rules.add(_rule_to_ascii(line.split()[0].lower()))
    return frozenset(rules)


def make_split(rules: frozenset[str]) -> SplitFn:
    """Thuật toán PSL: ưu tiên luật ngoại lệ (`!`), rồi luật dài nhất (kể cả `*.`); mặc định `*`."""

    def split(fqdn: str) -> SplitResult:
        labels = fqdn.split(".")
        n = len(labels)
        suffix_len = 1
        for i in range(n):
            suffix = ".".join(labels[i:])
            if "!" + suffix in rules:
                suffix_len = n - i - 1
                break
            if suffix in rules or (i + 1 < n and "*." + ".".join(labels[i + 1 :]) in rules):
                suffix_len = n - i
                break
        if suffix_len >= n:
            return None
        registered = ".".join(labels[-(suffix_len + 1) :])
        sub = ".".join(labels[: -(suffix_len + 1)]) or None
        return registered, sub, ".".join(labels[-suffix_len:])

    return split


def to_ascii(name: str) -> str | None:
    """Tên IDN (Unicode) -> ASCII punycode; None nếu không mã hoá được."""
    try:
        return name.encode("idna").decode("ascii")
    except UnicodeError:
        return None


@dataclass(frozen=True)
class Normalizer:
    to_ascii: ToAsciiFn
    split: SplitFn


def default_normalizer(psl_path: str | os.PathLike[str] | None = None) -> Normalizer:
    """Normalizer dùng PSL từ `psl_path`, PSL_PATH / SCAMRADAR_PSL hoặc data/reference/."""
    env = os.environ.get("PSL_PATH") or os.environ.get("SCAMRADAR_PSL")
    path = Path(psl_path or env or DEFAULT_PSL_PATH)
    if not path.exists():
        raise FileNotFoundError(
            f"không thấy Public Suffix List ở {path}; "
            "chạy data/reference/download.sh hoặc đặt PSL_PATH"
        )
    return Normalizer(to_ascii=to_ascii, split=make_split(load_psl_rules(path)))
