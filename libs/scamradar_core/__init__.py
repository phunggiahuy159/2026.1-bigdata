"""scamradar_core: chuẩn hoá domain và chấm điểm mạo danh thương hiệu (dùng chung stream, batch)."""

from .domain import DomainParts, parse, refang, registered_domain, to_ascii, to_unicode

__all__ = ["DomainParts", "parse", "refang", "registered_domain", "to_ascii", "to_unicode"]
