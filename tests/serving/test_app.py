from pathlib import Path

from streamlit.testing.v1 import AppTest

from serving.app.data import SampleRepository

APP = str(Path(__file__).resolve().parents[2] / "serving" / "app" / "main.py")


def _script(name):
    from serving.app import pages

    getattr(pages, name)()


def run_page(name):
    return AppTest.from_function(_script, args=(name,), default_timeout=30).run()


ELEMENTS = ("title", "header", "subheader", "markdown", "caption", "text", "metric", "json")


def shown_text(at):
    """Mọi văn bản người dùng thấy: tiêu đề, markdown, bảng, JSON, metric, ô chọn."""
    out = []
    for kind in ELEMENTS:
        for element in at.get(kind):
            out.append(str(element.value))
            out.append(str(getattr(element, "label", "")))
    for table in at.dataframe:
        out.append(table.value.to_string())
    for box in at.selectbox:
        out.extend(box.options)
    return out


def test_entry_point_renders_feed_without_error():
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    assert at.title[0].value == "Feed cảnh báo"


def test_feed_page_counts_alerts_and_filters():
    at = run_page("feed_page")
    assert not at.exception
    assert int(at.metric[0].value) > 0
    at.slider[0].set_value(100).run()
    assert at.metric[0].value == "0"


def test_domain_page_shows_only_defanged_domain():
    at = run_page("domain_page")
    assert not at.exception
    assert at.subheader[0].value.startswith("hxxps://")
    assert all(o.startswith("hxxps://") for o in at.selectbox[0].options)


def test_vn_page_renders():
    at = run_page("vn_page")
    assert not at.exception
    assert int(at.metric[0].value) > 0


def raw_values():
    """Domain, nameserver và IP thô trong dữ liệu mẫu: không được xuất hiện trên trang nào."""
    values = set()
    for doc in SampleRepository().domains():
        values.add(doc["_id"])
        enrichment = (doc.get("batch") or {}).get("enrichment") or {}
        values |= set(enrichment.get("a_records", []) + enrichment.get("ns_records", []))
    for alert in SampleRepository().alerts():
        values |= {alert["domain"], alert["fqdn"]}
    return values


def assert_clean(texts, where):
    for text in texts:
        assert "http://" not in text and "https://" not in text, (where, text)
        for value in raw_values():
            assert value not in text, (where, value)


def test_no_page_shows_a_clickable_link_or_raw_value():
    for name in ("feed_page", "domain_page", "vn_page"):
        assert_clean(shown_text(run_page(name)), name)


def test_every_domain_detail_is_clean():
    at = run_page("domain_page")
    labels = list(at.selectbox[0].options)
    assert len(labels) >= 10
    for label in labels:
        at = at.selectbox[0].select(label).run()
        assert not at.exception, label
        assert_clean(shown_text(at), label)
    assert at.json, "trang chi tiết phải có khối enrichment để quét"


def _empty_script(name):
    from serving.app import pages

    class Empty:
        def alerts(self):
            return []

        def domains(self):
            return []

    original = pages.repository
    pages.repository = lambda: Empty()
    try:
        getattr(pages, name)()
    finally:
        pages.repository = original


def test_pages_survive_empty_data():
    for name in ("feed_page", "domain_page", "vn_page"):
        at = AppTest.from_function(_empty_script, args=(name,), default_timeout=30).run()
        assert not at.exception, name


def test_domain_page_handles_batch_only_document():
    at = run_page("domain_page")
    box = at.selectbox[0]
    label = next(o for o in box.options if "batch-only-demo" in o.replace("[.]", "."))
    at = box.select(label).run()
    assert not at.exception
    assert at.metric[1].value == "chưa có"
