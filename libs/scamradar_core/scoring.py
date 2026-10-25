"""Hàm điểm 0-100 kèm lý do. Heuristic cộng dồn có trần, không phải xác suất.

Kết quả khớp `alerts.v1`: `domain` (eTLD+1, punycode), `brand_id`, `score` (int 0-100), `reasons[]`.

Domain chính chủ: nếu eTLD+1 nằm trong `official_domains` của bất kỳ thương hiệu nào thì điểm 0,
lý do `official_domain`; không bao giờ bị gắn cờ, kể cả subdomain như `login.vietcombank.com.vn`.

`other_domains` (domain nhiều khả năng là của thương hiệu nhưng chưa xác minh) được MIỄN HẲN như
chính chủ: điểm 0, lý do `other_domain_unverified`. Miễn hẳn chứ không giảm điểm, vì báo nhầm chính
site thật tệ hơn bỏ sót một domain nghi vấn; lý do khác biệt để người duyệt xác minh dần và chuyển
sang `official_domains`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

from .brands import Brand, load_brands
from .domain import parse
from .features import lexical_features
from .matching import build_index, match_brand

NON_BRAND_CAP = 60  # không khớp thương hiệu nào thì tối đa 60, để mạo danh thương hiệu xếp trên
_MATCH_POINTS = {"sub5": 45, "sub4": 35, "tok": 30}


@dataclass
class ScoreResult:
    domain: str  # eTLD+1, ASCII punycode
    score: int
    reasons: list[str] = field(default_factory=list)
    brand_id: str | None = None

    def as_alert_fields(self) -> dict:
        """Các trường chấm điểm của alerts.v1 (người gọi thêm alert_ts, alert_type, ...)."""
        return {
            "domain": self.domain,
            "brand_id": self.brand_id,
            "score": self.score,
            "reasons": list(self.reasons),
        }


class Scorer:
    def __init__(self, brands: list[Brand]):
        self.index = build_index(brands)
        self.official = {d: b.brand_id for b in brands for d in b.official_domains}
        self.unverified = {d: b.brand_id for b in brands for d in b.other_domains}

    def score(self, raw: str) -> ScoreResult:
        p = parse(raw)
        if not p.registered:
            return ScoreResult(p.host, 0, ["no_registered_domain"])
        if p.registered in self.official:
            return ScoreResult(p.registered, 0, ["official_domain"], self.official[p.registered])
        if p.registered in self.unverified:
            reasons = ["other_domain_unverified"]
            return ScoreResult(p.registered, 0, reasons, self.unverified[p.registered])

        pts, reasons = 0, []

        def add(n: int, why: str) -> None:
            nonlocal pts
            pts += n
            reasons.append(why)

        f = lexical_features(p.label, p.suffix, p.is_idn, p.subdomain)
        m = match_brand(p.label, self.index)
        brand_id = None
        if m:
            brand_id = m.brand_id
            if m.kind == "exact":
                add(_MATCH_POINTS[m.mode], f"brand_in_name:{m.brand_id}")
            elif m.kind == "homoglyph":
                add(50, f"brand_homoglyph:{m.brand_id}")
            else:
                add(45 if m.distance == 1 else 35, f"brand_typo:{m.brand_id}:d{m.distance}")
        elif p.subdomain:
            ms = match_brand(p.subdomain, self.index)
            if ms and ms.kind != "fuzzy":
                brand_id = ms.brand_id
                add(40, f"brand_in_subdomain:{ms.brand_id}")

        if f.keywords:
            extra = min(12 + 5 * (len(f.keywords) - 1), 25) + (5 if brand_id else 0)
            add(extra, "keyword:" + "+".join(f.keywords[:3]))
        if f.is_idn:
            add(10, "idn")
        elif f.has_confusables and not (m and m.kind == "homoglyph"):
            add(5, "mixed_digits_letters")
        if f.risky_tld:
            add(10, f"risky_tld:{p.suffix.rsplit('.', 1)[-1]}")
        if f.hyphens >= 3:
            add(10, f"hyphens:{f.hyphens}")
        elif f.hyphens == 2:
            add(5, "hyphens:2")
        if f.length > 40:
            add(10, f"long_label:{f.length}")
        elif f.length > 25:
            add(5, f"long_label:{f.length}")
        if f.length >= 14 and f.entropy > 4.0:
            add(5, f"high_entropy:{f.entropy:.2f}")
        if f.digit_ratio > 0.3:
            add(5, "many_digits")

        if brand_id is None:
            pts = min(pts, NON_BRAND_CAP)
        return ScoreResult(p.registered, max(0, min(100, pts)), reasons, brand_id)


@lru_cache(maxsize=1)
def _default_scorer() -> Scorer:
    return Scorer(load_brands())


def score_domain(raw: str, brands: list[Brand] | None = None) -> ScoreResult:
    """Chấm một domain/FQDN/URL. Không truyền `brands` thì dùng danh mục mặc định (đã cache)."""
    return (Scorer(brands) if brands is not None else _default_scorer()).score(raw)
