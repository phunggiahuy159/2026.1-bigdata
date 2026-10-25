"""scamradar_core: chuẩn hoá domain và chấm điểm mạo danh thương hiệu (dùng chung stream, batch)."""

from .brands import Brand, load_brands
from .domain import DomainParts, parse, refang, registered_domain, to_ascii, to_unicode
from .features import edit_distance, entropy, lexical_features
from .matching import match_brand
from .scoring import Scorer, ScoreResult, score_domain

__all__ = [
    "Brand",
    "DomainParts",
    "ScoreResult",
    "Scorer",
    "edit_distance",
    "entropy",
    "lexical_features",
    "load_brands",
    "match_brand",
    "parse",
    "refang",
    "registered_domain",
    "score_domain",
    "to_ascii",
    "to_unicode",
]
