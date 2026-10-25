"""Ánh xạ nhãn tay (CSV, ba giá trị) sang nhãn của silver.labels (phishing | benign)."""

from __future__ import annotations

CSV_LABELS = {"phishing", "suspicious", "clean", "skip"}
_TO_SILVER = {"phishing": "phishing", "clean": "benign"}


def to_silver_label(csv_label: str) -> str | None:
    """Trả về nhãn ghi vào silver.labels, hoặc None nếu dòng không được ghi."""
    label = csv_label.strip().lower()
    if label not in CSV_LABELS:
        raise ValueError(f"nhãn không hợp lệ: {csv_label!r}")
    return _TO_SILVER.get(label)
