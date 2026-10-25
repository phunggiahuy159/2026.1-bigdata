import re

from serving.app.data import SampleRepository
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
