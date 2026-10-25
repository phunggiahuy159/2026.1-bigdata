"""Các trang Streamlit. Mỗi trang là một hàm không tham số để `st.navigation` và test gọi được."""

import streamlit as st

from serving.app.data import SampleRepository
from serving.app.views import domain_detail, domain_options, feed_rows, vn_rows

NOTE = "Domain hiển thị dạng vô hiệu hoá (hxxps://abc[.]com); không bấm, không mở."


@st.cache_resource
def repository() -> SampleRepository:
    return SampleRepository()


def feed_page() -> None:
    st.title("Feed cảnh báo")
    st.caption(NOTE + " Dữ liệu mẫu.")
    alerts = repository().alerts()
    brands = sorted({a["brand_id"] for a in alerts if a.get("brand_id")})
    left, right = st.columns(2)
    min_score = left.slider("Điểm tối thiểu", 0, 100, 50)
    brand = right.selectbox("Thương hiệu", ["(tất cả)", *brands])
    rows = feed_rows(alerts, min_score=min_score, brand=None if brand == "(tất cả)" else brand)
    st.metric("Số cảnh báo", len(rows))
    st.dataframe(rows, hide_index=True, width="stretch")


def domain_page() -> None:
    st.title("Chi tiết domain")
    st.caption(NOTE)
    domains = repository().domains()
    options = domain_options(domains)
    choice = st.selectbox("Domain", list(options))
    doc = next(d for d in domains if d["_id"] == options[choice])
    detail = domain_detail(doc)
    st.subheader(detail["domain"])
    cols = st.columns(3)
    cols[0].metric("Điểm hiệu lực", detail["score"], help=f"nguồn: {detail['source']}")
    cols[1].metric("Điểm speed", detail["speed_score"])
    cols[2].metric(
        "Điểm batch", "chưa chấm" if detail["batch_score"] is None else detail["batch_score"]
    )
    st.write(f"Thương hiệu: {detail['brand'] or 'không rõ'}")
    st.write("Lý do: " + ", ".join(detail["reasons"]))
    st.write(f"Thấy lần đầu (UTC): {detail['first_seen'] or 'không rõ'}")
    st.write(f"Chiến dịch: {detail['campaign_id'] or 'không thuộc chiến dịch nào'}")
    st.subheader("Enrichment")
    st.json(detail["enrichment"])


def vn_page() -> None:
    st.title("Domain .vn")
    st.caption(NOTE)
    rows = vn_rows(repository().domains())
    st.metric("Số domain .vn nghi vấn", len(rows))
    st.dataframe(rows, hide_index=True, width="stretch")
