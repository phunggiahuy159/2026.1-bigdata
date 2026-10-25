from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[2] / "serving" / "app" / "main.py")


def _script(name):
    from serving.app import pages

    getattr(pages, name)()


def run_page(name):
    return AppTest.from_function(_script, args=(name,), default_timeout=30).run()


def shown_text(at):
    return (
        [m.value for m in at.markdown] + [c.value for c in at.caption] + [t.value for t in at.text]
    )


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


def test_no_page_shows_a_clickable_link():
    for name in ("feed_page", "domain_page", "vn_page"):
        shown = shown_text(run_page(name))
        assert not any("http://" in s or "https://" in s for s in shown), name


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
