import pytest

from labeling.safebrowsing import (
    ENV_KEY,
    MAX_ENTRIES_PER_REQUEST,
    SafeBrowsingClient,
    SafeBrowsingError,
)


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, url, body):
        self.calls.append((url, body))
        return self.responses.pop(0)


def make(transport, **kw):
    return SafeBrowsingClient("k", transport=transport, sleep=lambda s: None, **kw)


def test_missing_key_raises(monkeypatch):
    monkeypatch.delenv(ENV_KEY, raising=False)
    with pytest.raises(SafeBrowsingError, match=ENV_KEY):
        SafeBrowsingClient()


def test_key_from_env(monkeypatch):
    monkeypatch.setenv(ENV_KEY, "abc")
    t = FakeTransport([(200, {})])
    SafeBrowsingClient(transport=t, sleep=lambda s: None).check(["a.example"])
    assert t.calls[0][0].endswith("key=abc")


def test_flags_matches_and_keeps_order():
    t = FakeTransport(
        [
            (
                200,
                {
                    "matches": [
                        {"threatType": "SOCIAL_ENGINEERING", "threat": {"url": "bad.example"}}
                    ]
                },
            )
        ]
    )
    out = make(t).check(["ok.example", "BAD.example", "ok.example"])
    assert [(v.domain, v.flagged, v.threats) for v in out] == [
        ("ok.example", False, ()),
        ("bad.example", True, ("SOCIAL_ENGINEERING",)),
    ]


def test_batches_over_limit():
    n = MAX_ENTRIES_PER_REQUEST + 1
    t = FakeTransport([(200, {}), (200, {})])
    out = make(t).check(f"d{i}.example" for i in range(n))
    assert len(out) == n and len(t.calls) == 2
    assert len(t.calls[0][1]["threatInfo"]["threatEntries"]) == MAX_ENTRIES_PER_REQUEST


def test_retries_on_429_with_backoff():
    sleeps = []
    t = FakeTransport([(429, {}), (200, {})])
    c = SafeBrowsingClient("k", transport=t, sleep=sleeps.append, min_interval=0)
    c.check(["a.example"])
    assert len(t.calls) == 2 and 1 in sleeps


def test_error_does_not_leak_key():
    t = FakeTransport([(403, {})])
    c = SafeBrowsingClient("secret-key-123", transport=t, sleep=lambda s: None)
    with pytest.raises(SafeBrowsingError) as e:
        c.check(["a.example"])
    assert "secret-key-123" not in str(e.value) and "403" in str(e.value)


def test_rate_limit_spaces_calls():
    now = [0.0]
    sleeps = []
    t = FakeTransport([(200, {}), (200, {})])
    c = SafeBrowsingClient(
        "k", transport=t, min_interval=2.0, sleep=sleeps.append, clock=lambda: now[0]
    )
    c.check(["a.example"])
    c._last_call = 0.0
    now[0] = 0.5
    c.check(["b.example"])
    assert sleeps == [1.5]
