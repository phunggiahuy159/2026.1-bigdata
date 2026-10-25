"""Vô hiệu hoá domain và URL trước khi hiển thị: không bao giờ render link bấm được."""

from __future__ import annotations

import re

_SCHEME = re.compile(r"^(?P<scheme>[A-Za-z][A-Za-z0-9+.-]*)://")


def defang_domain(domain: str) -> str:
    """`abc.com` thành `abc[.]com`. Chạy lại trên chuỗi đã vô hiệu hoá thì giữ nguyên."""
    return domain.replace("[.]", ".").replace(".", "[.]")


def defang_url(url: str) -> str:
    """`https://abc.com/x` thành `hxxps://abc[.]com/x`."""
    match = _SCHEME.match(url)
    scheme = "https" if match is None else match.group("scheme").lower()
    rest = url[match.end() :] if match else url
    scheme = re.sub(r"^http", "hxxp", scheme)
    return f"{scheme}://{defang_domain(rest)}"


def display_domain(domain: str) -> str:
    """Dạng hiển thị chuẩn của một domain trong ứng dụng: `hxxps://abc[.]com`."""
    return defang_url(f"https://{domain}")
