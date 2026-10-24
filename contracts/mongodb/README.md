# Hợp đồng MongoDB

Cơ sở dữ liệu `scamradar`, ba collection. Schema là JSON Schema (`*.schema.json`), index ở `indexes.json`.
Đây là **đề xuất** của P5, chờ P3 (ghi `domains.speed`, `alerts`) và P4 (nguồn `campaigns`) xác nhận.

| Collection | `_id` | Ghi | Đọc |
| --- | --- | --- | --- |
| `domains` | domain gốc (eTLD+1) | P3 (`speed`, `brand_id`), P5 (`batch`) | P5 (Streamlit) |
| `alerts` | `{domain}\|{alert_ts}` | P3 | P5 |
| `campaigns` | `campaign_id` | P5 | P5 |

## Quy tắc hợp nhất speed + batch (`domains`)

1. **Mỗi bên chỉ ghi vùng của mình.** P3 chỉ `$set` `speed.*` và `brand_id`; P5 chỉ `$set` `batch.*`.
   Không ai dùng `replaceOne` trên cả document, nên hai bên không ghi đè lẫn nhau. Dùng `upsert: true`
   vì document có thể do bên nào đến trước tạo ra.
2. **Điểm hiệu lực** (`effective_score`) tính khi đọc, không lưu:
   `batch.score` nếu có `batch`, ngược lại `speed.score`. Điểm batch ghi đè khi có, vì có enrichment và ngữ cảnh đồ thị.
3. **Lý do** đi theo điểm được chọn: `batch.reasons` nếu dùng điểm batch, ngược lại `speed.reasons`.
4. **Ngoại lệ - speed mới hơn batch.** Nếu `speed.updated_ts` lớn hơn `batch.updated_ts` thì domain có chứng chỉ mới
   sau lần chấm batch cuối; ứng dụng dùng `max(batch.score, speed.score)` và gắn cờ "cập nhật sau batch".
   (P3/P5 cần xác nhận quy tắc này; nếu không muốn, bỏ mục 4.)
5. **Ghi lại chạy lại được.** Job batch chấm lại cùng `scored_date` thì ghi cùng giá trị (idempotent). Điểm
   `batch` của ngày cũ hơn không ghi đè `batch` của ngày mới hơn (so `batch.scored_date`).
6. Thời gian là UTC mili giây (số nguyên); `score` 0-100; `reasons[]` là danh sách mã lý do.

## Ghi chú

- `alerts` có TTL 30 ngày trên `created_at` (chỉ là bản xem nhanh; bản đầy đủ nằm ở Kafka/Iceberg).
- Thay đổi tương thích ngược (thêm trường tuỳ chọn) chỉ cần báo; đổi không tương thích phải tăng phiên bản
  (collection mới `domains_v2`).
- Domain lừa đảo trong ví dụ và tài liệu luôn viết dạng vô hiệu hoá (`hxxps://abc[.]com`).
