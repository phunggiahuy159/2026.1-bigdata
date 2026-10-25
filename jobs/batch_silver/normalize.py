"""Chuẩn hoá tên miền: punycode và tách domain gốc (eTLD+1) theo Public Suffix List.

TODO: thay toàn bộ file này bằng `scamradar_core` của P3 khi thư viện được merge. Giữ nguyên chữ ký
`ToAsciiFn` / `SplitFn` để transform không phải đổi. Quy tắc giữ cùng contract: domain gốc là
eTLD+1,
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


def load_psl_rules(path: str | os.PathLike[str], include_private: bool = False) -> frozenset[str]:
    """Đọc file PSL (data/reference/download.sh tải về). Mặc định chỉ lấy phần ICANN.

    TODO(P3): phần PRIVATE (github.io, blogspot.com, ...) có tính là suffix hay không do
    scamradar_core quyết định.
    """
    rules: set[str] = set()
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if _PRIVATE_MARK in line and not include_private:
            break
        line = line.strip()
        if line and not line.startswith("//"):
            rules.add(line.split()[0].lower())
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
    """Normalizer dùng PSL từ `psl_path`, biến môi trường PSL_PATH hoặc data/reference/."""
    path = Path(psl_path or os.environ.get("PSL_PATH") or DEFAULT_PSL_PATH)
    if not path.exists():
        raise FileNotFoundError(
            f"không thấy Public Suffix List ở {path}; "
            "chạy data/reference/download.sh hoặc đặt PSL_PATH"
        )
    return Normalizer(to_ascii=to_ascii, split=make_split(load_psl_rules(path)))
