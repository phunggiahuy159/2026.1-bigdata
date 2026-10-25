"""Public Suffix List: tách tên miền thành (phần đăng ký, public suffix).

Dùng bản PSL kèm trong `data/` (xem data/NOTICE.md), không cần mạng. Đặt biến môi trường
`SCAMRADAR_PSL` để dùng file khác. Gồm cả phần PRIVATE của PSL (github.io, web.app, ...) vì với
phát hiện lừa đảo, mỗi tenant của dịch vụ lưu trữ là một "domain gốc" riêng.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

_BUNDLED = Path(__file__).resolve().parent / "data" / "public_suffix_list.dat"


def _ascii(rule: str) -> str:
    out = []
    for lab in rule.split("."):
        if lab != "*" and not lab.isascii():
            lab = lab.encode("idna").decode("ascii")
        out.append(lab)
    return ".".join(out)


class PublicSuffixList:
    def __init__(self, rules: list[str]):
        self._rules: set[str] = set()
        self._wild: set[str] = set()  # "*.x.y" lưu dạng "x.y"
        self._exc: set[str] = set()
        for r in rules:
            if r.startswith("!"):
                self._exc.add(r[1:])
            elif r.startswith("*."):
                self._wild.add(r[2:])
            else:
                self._rules.add(r)

    @classmethod
    def from_text(cls, text: str) -> PublicSuffixList:
        rules = []
        for line in text.splitlines():
            line = line.strip()
            if line and not line.startswith("//"):
                rules.append(_ascii(line.split()[0].lower()))
        return cls(rules)

    def suffix_len(self, labels: list[str]) -> int:
        """Số nhãn (tính từ phải) thuộc public suffix, theo thuật toán của publicsuffix.org."""
        n = len(labels)
        best = 1  # luật mặc định "*"
        for k in range(1, n + 1):
            suffix = ".".join(labels[n - k :])
            if suffix in self._exc:
                return k - 1
            if suffix in self._rules:
                best = max(best, k)
            if k >= 2 and ".".join(labels[n - k + 1 :]) in self._wild:
                best = max(best, k)
        return best

    def split(self, host: str) -> tuple[str, str]:
        """(phần trước public suffix, public suffix); phần đầu rỗng nếu host chính là suffix."""
        labels = host.split(".")
        k = self.suffix_len(labels)
        return ".".join(labels[:-k]), ".".join(labels[-k:])


@lru_cache(maxsize=1)
def default_psl() -> PublicSuffixList:
    path = Path(os.environ.get("SCAMRADAR_PSL") or _BUNDLED)
    return PublicSuffixList.from_text(path.read_text(encoding="utf-8"))
