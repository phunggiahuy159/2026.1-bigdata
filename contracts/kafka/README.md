# contracts/kafka

JSON Schema cho các topic Kafka do P2 ghi.

| Topic | Key | Partition | Giữ | Nén | Schema |
| --- | --- | --- | --- | --- | --- |
| `ct.raw` | sha256 (hex thường) | 6 | 48 giờ | zstd | `ct.raw.schema.json` |
| `ct.dlq` | sha256 nếu có | theo mặc định | 7 ngày | zstd | `ct.dlq.schema.json` |

Quy ước: thời gian là UTC mili giây (các trường giây của CertStream được nhân 1000 khi parse). `ct.raw` là bản làm phẳng của định dạng lite
(`wss://api.certstream.dev/lite`) cộng `seen_ts`, `collector_id`. Thêm trường tuỳ chọn là tương thích ngược; đổi không tương thích thì đổi tên topic có phiên bản.
