"""Nạp danh mục thương hiệu từ data/reference/brands.yaml."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Brand:
    brand_id: str
    name: str
    category: str
    official_domains: frozenset[str]  # đã xác minh hoặc chưa: không bao giờ bị gắn cờ
    other_domains: frozenset[str]  # chưa xác minh; vẫn coi là chính chủ (xem scoring.py)
    keywords: tuple[str, ...]  # tên/từ khoá thương hiệu, chữ thường không dấu
    aliases: tuple[str, ...]  # viết tắt, chỉ khớp nguyên token
    optional: bool = False


def default_brands_path() -> Path:
    if os.environ.get("SCAMRADAR_BRANDS"):
        return Path(os.environ["SCAMRADAR_BRANDS"])
    for parent in Path(__file__).resolve().parents:
        cand = parent / "data" / "reference" / "brands.yaml"
        if cand.is_file():
            return cand
    raise FileNotFoundError("không thấy data/reference/brands.yaml; đặt SCAMRADAR_BRANDS")


def load_brands(path: str | Path | None = None, include_optional: bool = False) -> list[Brand]:
    """Thương hiệu `optional: true` (quốc tế) bị bỏ qua trừ khi `include_optional=True`."""
    data = yaml.safe_load(Path(path or default_brands_path()).read_text(encoding="utf-8"))
    out = []
    for b in data["brands"]:
        if b.get("optional", False) and not include_optional:
            continue
        out.append(
            Brand(
                brand_id=b["brand_id"],
                name=b["name"],
                category=b["category"],
                official_domains=frozenset(d.lower() for d in b["official_domains"]),
                other_domains=frozenset(d.lower() for d in b.get("other_domains", [])),
                keywords=tuple(dict.fromkeys(k.lower() for k in b["keywords"])),
                aliases=tuple(dict.fromkeys(a.lower() for a in b["aliases"])),
                optional=bool(b.get("optional", False)),
            )
        )
    return out
