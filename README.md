# ScamRadar VN

**Real-time Detection of Phishing Websites Impersonating Vietnamese Brands**

Nhóm 19, môn IT4043E (Big Data Storage and Processing).

## Kiến trúc

Hệ thống theo kiến trúc Lambda, phát hiện website lừa đảo mạo danh thương hiệu Việt từ Certificate Transparency:

- **Ingestion:** CertStream đẩy chứng chỉ mới vào Kafka.
- **Speed layer:** Spark Structured Streaming chấm điểm domain gần thời gian thực và phát cảnh báo.
- **Batch layer:** Spark batch xây dựng bảng Iceberg (bronze/silver/gold) trên MinIO, tính đặc trưng, đồ thị và mô hình để hiệu chỉnh điểm.
- **Serving:** MongoDB và Redis phục vụ tra cứu, giao diện Streamlit hiển thị cảnh báo.

Toàn bộ chạy trên cụm Kubernetes (kind).
