"""Nạp và gộp dữ liệu hiển thị theo schema trong contracts/mongodb.

Hiện đọc dữ liệu mẫu (`sample_data/`) vì cụm chưa có MongoDB; `Repository` là chỗ thay bằng
truy vấn MongoDB sau này mà không đổi các trang.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

SAMPLE_DIR = Path(__file__).resolve().parent / "sample_data"
Doc = dict


class Repository(Protocol):
    def alerts(self) -> list[Doc]: ...

    def domains(self) -> list[Doc]: ...


@dataclass(frozen=True)
class SampleRepository:
    directory: Path = SAMPLE_DIR

    def _load(self, name: str) -> list[Doc]:
        return json.loads((self.directory / f"{name}.json").read_text(encoding="utf-8"))

    def alerts(self) -> list[Doc]:
        """Cảnh báo mới nhất trước."""
        return sorted(self._load("alerts"), key=lambda a: a["alert_ts"], reverse=True)

    def domains(self) -> list[Doc]:
        return self._load("domains")


def effective(domain_doc: Doc) -> tuple[int, list[str], str]:
    """Điểm hiệu lực theo quy tắc hợp nhất: batch ghi đè speed khi có.

    Trả về (score, reasons, nguồn) với nguồn là `batch`, `speed` hoặc `none`. Contract chỉ bắt
    buộc `_id`, nên document có thể chỉ có `batch` (domain chưa từng có cảnh báo speed), chỉ có
    `speed`, hoặc chưa có cả hai (nguồn `none`, điểm 0).
    """
    batch = domain_doc.get("batch")
    if batch:
        return batch["score"], batch["reasons"], "batch"
    speed = domain_doc.get("speed")
    if speed:
        return speed["score"], speed["reasons"], "speed"
    return 0, [], "none"


def is_vn(domain: str) -> bool:
    return domain == "vn" or domain.endswith(".vn")


def fmt_ts(ms: int) -> str:
    """UTC mili giây sang chuỗi `YYYY-MM-DD HH:MM` (UTC)."""
    return datetime.fromtimestamp(ms / 1000, UTC).strftime("%Y-%m-%d %H:%M")
