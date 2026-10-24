"""Client Google Safe Browsing Lookup API (v4 threatMatches:find).

Key đọc từ biến môi trường ``SAFE_BROWSING_API_KEY``, không nằm trong code.
Chỉ trả về nhãn đã rút gọn (domain, bị đánh dấu hay không, loại mối đe doạ);
phản hồi thô của API không được lưu lại hay commit.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field

ENDPOINT = "https://safebrowsing.googleapis.com/v4/threatMatches:find"
ENV_KEY = "SAFE_BROWSING_API_KEY"
MAX_ENTRIES_PER_REQUEST = 500  # giới hạn của API
THREAT_TYPES = ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE", "POTENTIALLY_HARMFUL_APPLICATION"]

# transport(url, body) -> (status, parsed_json)
Transport = Callable[[str, dict], tuple[int, dict]]


class SafeBrowsingError(RuntimeError):
    pass


@dataclass(frozen=True)
class Verdict:
    domain: str
    flagged: bool
    threats: tuple[str, ...] = field(default_factory=tuple)


def _urllib_transport(url: str, body: dict) -> tuple[int, dict]:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, {}


def _chunks(items: list[str], n: int) -> Iterator[list[str]]:
    for i in range(0, len(items), n):
        yield items[i : i + n]


class SafeBrowsingClient:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        client_id: str = "scamradar-labeling",
        min_interval: float = 1.0,
        max_retries: int = 3,
        transport: Transport = _urllib_transport,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._key = api_key or os.environ.get(ENV_KEY)
        if not self._key:
            raise SafeBrowsingError(f"thiếu API key: đặt biến môi trường {ENV_KEY}")
        self._client_id = client_id
        self._min_interval = min_interval
        self._max_retries = max_retries
        self._transport = transport
        self._sleep = sleep
        self._clock = clock
        self._last_call: float | None = None

    def _throttle(self) -> None:
        if self._last_call is not None:
            wait = self._min_interval - (self._clock() - self._last_call)
            if wait > 0:
                self._sleep(wait)
        self._last_call = self._clock()

    def _post(self, body: dict) -> dict:
        url = f"{ENDPOINT}?key={self._key}"
        for attempt in range(self._max_retries + 1):
            self._throttle()
            status, data = self._transport(url, body)
            if status == 200:
                return data
            if status in (429, 500, 502, 503, 504) and attempt < self._max_retries:
                self._sleep(2**attempt)
                continue
            # không đưa URL (chứa key) vào thông báo lỗi
            raise SafeBrowsingError(f"Safe Browsing trả về HTTP {status}")
        raise SafeBrowsingError("unreachable")

    def check(self, domains: Iterable[str]) -> list[Verdict]:
        """Kiểm tra danh sách domain gốc; trả về một Verdict cho mỗi domain, giữ thứ tự."""
        ordered = list(dict.fromkeys(d.strip().lower() for d in domains if d.strip()))
        threats: dict[str, set[str]] = {}
        for batch in _chunks(ordered, MAX_ENTRIES_PER_REQUEST):
            body = {
                "client": {"clientId": self._client_id, "clientVersion": "1.0"},
                "threatInfo": {
                    "threatTypes": THREAT_TYPES,
                    "platformTypes": ["ANY_PLATFORM"],
                    "threatEntryTypes": ["URL"],
                    "threatEntries": [{"url": d} for d in batch],
                },
            }
            for m in self._post(body).get("matches", []):
                threats.setdefault(m["threat"]["url"].lower(), set()).add(m["threatType"])
        return [Verdict(d, d in threats, tuple(sorted(threats.get(d, ())))) for d in ordered]
