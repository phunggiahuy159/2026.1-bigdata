"""So khớp nhãn tên miền với danh mục thương hiệu: nguyên văn, đồng hình, gõ sai."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .brands import Brand
from .confusables import skeletons
from .features import edit_distance

# mode của từ khoá: sub5 = chuỗi con, tên >= 5 ký tự (cho phép gõ sai); sub4 = chuỗi con, tên 4
# ký tự (dễ trùng từ thường nên điểm thấp hơn, không gõ sai); tok = chỉ khớp nguyên token (tên <= 3
# ký tự và mọi viết tắt).
MIN_ALIAS = 3


@dataclass(frozen=True)
class BrandMatch:
    brand_id: str
    kind: str  # exact | homoglyph | fuzzy
    keyword: str
    mode: str  # sub5 | sub4 | tok
    distance: int = 0


def build_index(brands: list[Brand]) -> list[tuple[str, str, str]]:
    """[(từ khoá, brand_id, mode)], từ khoá dài trước."""
    entries = []
    for b in brands:
        for kw in b.keywords:
            n = len(kw)
            entries.append((kw, b.brand_id, "sub5" if n >= 5 else "sub4" if n == 4 else "tok"))
        for al in b.aliases:
            if len(al) >= MIN_ALIAS:
                entries.append((al, b.brand_id, "tok"))
    return sorted(set(entries), key=lambda e: -len(e[0]))


def _tokens(label: str) -> list[str]:
    return [t for t in re.split(r"[-_.]+", label.lower()) if t]


def _windows(flat: str, kw: str, lim: int) -> list[str]:
    """Đầu và cuối của nhãn ghép dài bằng tên đến tên + lim: bắt kiểu `vietcombamklogin`.

    Không lấy cửa sổ ngắn hơn tên: chuỗi cuối `mbank` của `vietcombank` sẽ khớp nhầm `mbbank`.
    """
    out = []
    for n in range(len(kw), len(kw) + lim + 1):
        if 0 < n < len(flat):
            out += [flat[:n], flat[-n:]]
    return out


def match_brand(
    label: str, index: list[tuple[str, str, str]], skip: set[str] | None = None
) -> BrandMatch | None:
    """Khớp tốt nhất: exact < homoglyph < fuzzy (1 rồi 2); cùng loại thì từ khoá dài hơn thắng.

    Fuzzy chỉ áp cho token và đầu/cuối nhãn ghép, không quét mọi cửa sổ, để chạy nhanh trong UDF.
    """
    tokens = _tokens(label)
    flat = "".join(tokens)
    raw_sub = {label.lower(), flat, *tokens}  # chuỗi để tìm chuỗi con
    raw_tok = set(tokens)  # chuỗi để so nguyên token
    flat_sk = {s for s in skeletons(flat) if s != flat}
    tok_sk = {s for t in tokens for s in skeletons(t) if s != t}
    sub_sk = flat_sk | tok_sk
    tok_vars = raw_tok | tok_sk
    best: tuple[tuple[int, int], BrandMatch] | None = None

    def offer(rank: int, kw: str, m: BrandMatch) -> None:
        nonlocal best
        key = (rank, -len(kw))
        if best is None or key < best[0]:
            best = (key, m)

    for kw, bid, mode in index:
        if skip and bid in skip:
            continue
        if kw in raw_tok or (mode != "tok" and any(kw in f for f in raw_sub)):
            offer(0, kw, BrandMatch(bid, "exact", kw, mode))
        elif kw in tok_sk or (mode != "tok" and any(kw in f for f in sub_sk)):
            offer(1, kw, BrandMatch(bid, "homoglyph", kw, mode))
        elif mode == "sub5":
            lim = 1 if len(kw) < 10 else 2  # tên ngắn hơn 10 ký tự chỉ cho sai 1 ký tự
            cands = set(tok_vars)
            for v in {flat, *flat_sk}:
                cands.update(_windows(v, kw, lim))
            n = len(kw)
            pieces = [kw[i * n // (lim + 1) : (i + 1) * n // (lim + 1)] for i in range(lim + 1)]
            # chuồng bồ câu: sai tối đa lim ký tự thì ít nhất một trong lim+1 đoạn còn nguyên
            near = [c for c in cands if any(pc in c for pc in pieces)]
            d = min((edit_distance(c, kw, lim) for c in near), default=lim + 1)
            if 0 < d <= lim:
                offer(1 + d, kw, BrandMatch(bid, "fuzzy", kw, mode, d))
    return best[1] if best else None
