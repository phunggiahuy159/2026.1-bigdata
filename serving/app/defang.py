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


_TOKEN = re.compile(
    r"(?P<url>[A-Za-z][A-Za-z0-9+.-]*://\S+)"
    r"|(?P<ip>(?<![\w.])\d{1,3}(?:\.\d{1,3}){3}(?![\w.]))"
    r"|(?P<domain>(?<![\w.@-])(?:[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?\.)+[A-Za-z][A-Za-z0-9-]*)"
)


def defang_text(text: str) -> str:
    """Vô hiệu hoá mọi URL, địa chỉ IPv4 và chuỗi dạng domain trong một đoạn văn bản."""

    def replace(match: re.Match) -> str:
        if match.group("url"):
            return defang_url(match.group("url"))
        return defang_domain(match.group(0))

    return _TOKEN.sub(replace, text)


def defang_value(value):
    """Áp `defang_text` cho mọi chuỗi trong dict/list lồng nhau (kể cả IPv6 và tên miền)."""
    if isinstance(value, str):
        return defang_text(value)
    if isinstance(value, dict):
        return {key: defang_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [defang_value(item) for item in value]
    return value
