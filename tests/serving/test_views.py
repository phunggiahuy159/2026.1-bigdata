import re

from serving.app.data import SampleRepository, effective
from serving.app.views import domain_detail, domain_options, feed_rows, vn_rows

REPO = SampleRepository()
RAW_DOMAINS = {d["_id"] for d in REPO.domains()}


def flatten(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            yield from flatten(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from flatten(v)
    else:
        yield str(obj)


def test_feed_filters_by_score_and_brand():
    rows = feed_rows(REPO.alerts(), min_score=80)
    assert rows and all(r["Điểm"] >= 80 for r in rows)
    rows = feed_rows(REPO.alerts(), brand="bidv")
    assert rows and all(r["Thương hiệu"] == "bidv" for r in rows)


def test_nothing_shown_contains_raw_domain_or_scheme():
    outputs = [
        feed_rows(REPO.alerts()),
        vn_rows(REPO.domains()),
        list(domain_options(REPO.domains())),
        [domain_detail(d) for d in REPO.domains()],
    ]
    for text in flatten(outputs):
        for domain in RAW_DOMAINS:
            assert domain not in text
        assert not re.search(r"https?://", text)


def test_domain_options_sorted_by_effective_score_and_map_back():
    options = domain_options(REPO.domains())
    assert set(options.values()) == RAW_DOMAINS
    assert all(label.startswith("hxxps://") for label in options)
    assert options[next(iter(options))] == "bank-demo-xacthuc.vn"


def test_vn_page_lists_only_vn_domains():
    rows = vn_rows(REPO.domains())
    assert rows and all(r["Domain"].endswith("[.]vn") for r in rows)
    assert [r["Điểm"] for r in rows] == sorted((r["Điểm"] for r in rows), reverse=True)


def test_detail_without_batch_marks_unscored():
    doc = next(d for d in REPO.domains() if d["_id"] == "xn--demo-bidv-9xa.net")
    detail = domain_detail(doc)
    assert detail["source"] == "speed" and detail["batch_score"] is None
    assert detail["enrichment"]["ips"] == []


BATCH_ONLY = next(d for d in REPO.domains() if d["_id"] == "batch-only-demo.vn")
EMPTY = {"_id": "empty.example"}


def test_batch_only_document_does_not_crash_any_view():
    assert "speed" not in BATCH_ONLY
    detail = domain_detail(BATCH_ONLY)
    assert detail["source"] == "batch" and detail["score"] == 70
    assert detail["speed_score"] is None and detail["first_seen"] == ""
    assert any(r["Nguồn điểm"] == "batch" for r in vn_rows([BATCH_ONLY]))
    assert len(domain_options([BATCH_ONLY])) == 1


def test_document_with_only_id_is_handled():
    assert effective(EMPTY) == (0, [], "none")
    detail = domain_detail(EMPTY)
    assert detail["source"] == "none" and detail["batch_score"] is None
    assert detail["enrichment"]["ips"] == []
    assert len(domain_options([EMPTY])) == 1


def test_speed_only_document_has_no_batch_score():
    doc = {"_id": "speed-only.example", "speed": {"score": 40, "reasons": ["x"], "updated_ts": 1}}
    detail = domain_detail(doc)
    assert detail["source"] == "speed" and detail["batch_score"] is None
    assert detail["first_seen"] == ""
