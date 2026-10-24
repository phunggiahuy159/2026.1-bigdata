# contracts/kafka

JSON Schema cho các topic Kafka: `ct.raw`, `ct.dlq` do P2 ghi, `alerts.v1` do P3 ghi.

| Topic | Key | Partition | Giữ | Nén | Schema |
| --- | --- | --- | --- | --- | --- |
| `ct.raw` | sha256 (hex thường) | 6 | 48 giờ | zstd | `ct.raw.schema.json` |
| `ct.dlq` | sha256 nếu có | theo mặc định | 7 ngày | zstd | `ct.dlq.schema.json` |
| `alerts.v1` | domain gốc (eTLD+1, ASCII punycode) | 3 | 7 ngày | zstd | `alerts.v1.schema.json` |

Quy ước: thời gian là UTC mili giây (các trường giây của CertStream được nhân 1000 khi parse). `ct.raw` là bản làm phẳng của định dạng lite
(`wss://api.certstream.dev/lite`) cộng `seen_ts`, `collector_id`. Thêm trường tuỳ chọn là tương thích ngược; đổi không tương thích thì đổi tên topic có phiên bản.

## `alerts.v1`

P3 ghi (`jobs/stream_detect`), P2 (enrichment) và P5 đọc. Key là domain gốc nên mọi cảnh báo của một domain vào cùng partition và giữ đúng thứ tự.
Chỉ phát khi domain mới hoặc điểm tăng (`alert_type` = `new_domain` / `score_increase`). Giao nhận at-least-once: người đọc khử trùng theo `(domain, alert_ts)`.
Tên trường khớp `contracts/mongodb/alerts.schema.json` (`domain`, `brand_id`, `score`, `reasons`, `fqdn`, `alert_ts`); các trường chỉ có ở Kafka
(`alert_type`, `prev_score`, `sha256`, `first_seen_ts`, `cert_count`, `rule_version`) không được lưu vào collection `alerts`.
Volume thấp (chỉ cảnh báo, không phải mọi chứng chỉ) nên 3 partition là đủ; 7 ngày đủ cho enrichment và P5 chạy bù sau sự cố.
