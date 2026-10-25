"""ScamRadar VN: ứng dụng Streamlit (khung chạy trên dữ liệu mẫu).

Chạy: `uv run streamlit run serving/app/main.py`
"""

import sys
from pathlib import Path

# Streamlit chỉ thêm thư mục của script vào sys.path; thêm gốc repo để import `serving.app`.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st  # noqa: E402

from serving.app.pages import domain_page, feed_page, vn_page  # noqa: E402


def main() -> None:
    st.set_page_config(page_title="ScamRadar VN", layout="wide")
    pages = [
        st.Page(feed_page, title="Feed cảnh báo", url_path="feed", default=True),
        st.Page(domain_page, title="Chi tiết domain", url_path="domain"),
        st.Page(vn_page, title="Domain .vn", url_path="vn"),
    ]
    st.navigation(pages).run()


main()
