"""Đọc cột bảng Iceberg từ contracts/iceberg/*.sql: job và test dùng chung một nguồn schema."""

from __future__ import annotations

import re
from pathlib import Path

ICEBERG_DIR = Path(__file__).resolve().parents[2] / "contracts" / "iceberg"
_COLUMN = re.compile(r"^\s+(\w+)\s+([A-Z]+(?:<[^>]*>)?)(.*)$")


def table_columns(table: str) -> list[tuple[str, str, bool]]:
    """[(tên cột, kiểu Spark SQL, NOT NULL)] theo thứ tự trong DDL."""
    sql = (ICEBERG_DIR / f"{table}.sql").read_text(encoding="utf-8")
    body = sql[sql.index("(") : sql.index(")\nUSING")]
    cols = []
    for line in body.splitlines():
        m = _COLUMN.match(line)
        if m:
            cols.append((m.group(1), m.group(2), "NOT NULL" in m.group(3)))
    return cols


def ddl_schema(table: str) -> str:
    """Chuỗi schema DDL cho `spark.read.schema(...)`."""
    return ", ".join(f"{name} {typ}" for name, typ, _ in table_columns(table))
