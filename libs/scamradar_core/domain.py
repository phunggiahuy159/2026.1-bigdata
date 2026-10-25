"""Chuẩn hoá tên miền: chữ thường, bỏ wildcard và dấu chấm cuối, punycode <-> Unicode, eTLD+1."""

from __future__ import annotations

from dataclasses import dataclass

from .psl import default_psl


def refang(s: str) -> str:
    """hxxps://abc[.]com -> https://abc.com (fixture và tài liệu lưu dạng vô hiệu hoá)."""
    return s.replace("[.]", ".").replace("(.)", ".").replace("hxxp", "http")


def clean_host(raw: str) -> str:
    """Lấy phần host: bỏ scheme, userinfo, cổng, đường dẫn, wildcard đầu và dấu chấm thừa."""
    h = refang(raw).strip().lower()
    if "://" in h:
        h = h.split("://", 1)[1]
    h = h.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    h = h.rsplit("@", 1)[-1].split(":", 1)[0]
    while h.startswith("*."):
        h = h[2:]
    return h.strip(".")


def to_ascii(host: str) -> str:
    """Nhãn Unicode -> punycode; nhãn không mã hoá được (quá dài, ký tự cấm) giữ nguyên."""
    out = []
    for lab in host.split("."):
        if lab and not lab.isascii():
            try:
                lab = lab.encode("idna").decode("ascii")
            except UnicodeError:
                pass
        out.append(lab)
    return ".".join(out)


def to_unicode(host: str) -> str:
    """Nhãn punycode (xn--) -> Unicode; nhãn lỗi giữ nguyên."""
    out = []
    for lab in host.split("."):
        if lab.startswith("xn--"):
            try:
                lab = lab.encode("ascii").decode("idna")
            except UnicodeError:
                pass
        out.append(lab)
    return ".".join(out)


@dataclass(frozen=True)
class DomainParts:
    host: str  # host đã chuẩn hoá, ASCII (punycode)
    registered: str  # eTLD+1, ASCII; rỗng nếu host chính là public suffix hoặc rỗng
    suffix: str  # public suffix, ASCII
    label: str  # nhãn ngay trước suffix, dạng Unicode (để so khớp với thương hiệu)
    subdomain: str  # phần trước eTLD+1, dạng Unicode; rỗng nếu không có
    is_idn: bool  # có nhãn punycode (xn--)


def parse(raw: str) -> DomainParts:
    host = to_ascii(clean_host(raw))
    if not host:
        return DomainParts("", "", "", "", "", False)
    prefix, suffix = default_psl().split(host)
    if not prefix:
        return DomainParts(host, "", suffix, "", "", False)
    plabels = prefix.split(".")
    uni = to_unicode(prefix).split(".")
    return DomainParts(
        host=host,
        registered=f"{plabels[-1]}.{suffix}",
        suffix=suffix,
        label=uni[-1],
        subdomain=".".join(uni[:-1]),
        is_idn=any(lab.startswith("xn--") for lab in host.split(".")),
    )


def registered_domain(raw: str) -> str:
    """eTLD+1 dạng ASCII punycode, chữ thường; rỗng nếu không xác định được."""
    return parse(raw).registered
