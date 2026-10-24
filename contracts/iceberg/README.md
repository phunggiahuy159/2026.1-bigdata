# Hợp đồng Iceberg

DDL Spark SQL cho các bảng lakehouse của nhóm. Mỗi bảng một file `<namespace>.<bảng>.sql`.
Thứ tự tạo: `00_namespaces.sql`, rồi các bảng bất kỳ (không có khoá ngoại).

## Quy ước

- Catalog Iceberg là catalog mặc định của phiên Spark (`spark.sql.defaultCatalog`), nên DDL chỉ ghi `namespace.bảng`.
- Thời gian là UTC, độ chính xác mili giây (`TIMESTAMP` của Spark/Iceberg là micro giây, ghi giá trị đã cắt về mili giây).
- Khoá domain là domain gốc (eTLD+1) viết thường, cột `registered_domain`.
- Điểm là `score` 0–100 kèm `reasons ARRAY<STRING>`.
- Bảng dùng `format-version = 2`, Parquet nén zstd.
- Partition ẩn của Iceberg (`days(ts)`, `bucket(32, registered_domain)`), nên truy vấn lọc theo `ts` hoặc `registered_domain` tự được pruning, không cần cột partition riêng.

## Bảng

| Bảng | Ghi | Đọc | Partition | Hạt (một dòng là) |
| --- | --- | --- | --- | --- |
| `bronze.ct_certs` | P2 | P4 | `days(seen_ts)` | một bản ghi CertStream, chỉ append |
| `silver.cert_domains` | P4 | P4, P5 | `days(cert_ts)`, `bucket(32, registered_domain)` | (chứng chỉ đã gộp precert/cert, FQDN) |
| `silver.domain_features` | P4 | P5 | `feature_date` (DATE, identity) | (domain gốc, ngày) |
| `silver.enrichment` | P2 | P4, P5 | `bucket(32, registered_domain)` | (domain gốc, lần tra cứu) |
| `silver.labels` | P5 | P5 | `bucket(32, registered_domain)` | (domain gốc, nguồn nhãn) |
| `gold.domain_history` | P4 | P4 | `bucket(32, registered_domain)` | (domain gốc, ngày) |
| `gold.domain_scores` | P5 | P5 | `days(score_date)` | (domain gốc, ngày, phiên bản mô hình) |
| `gold.campaigns` | P4 | P5 | `run_date` | (ngày chạy, chiến dịch) |
| `gold.brand_daily` | P4 | P5 | `days(day)` | (ngày, thương hiệu) |
| `gold.vn_daily` | P4 | P5 | `days(day)` | (ngày, CA phát hành) |

## Cách ghi chạy lại được

- `bronze.ct_certs`: chỉ append (P2, exactly-once qua checkpoint).
- `silver.*` và `gold.*` của P4: job nhận khoảng ngày, ghi bằng `overwritePartitions()` hoặc `MERGE INTO` theo khoá hạt ở bảng trên; không `append` thuần.

## Quan hệ với Kafka

`bronze.ct_certs` khớp `contracts/kafka/ct.raw.schema.json`. Phép đổi do job bronze (P2) thực hiện:

| `ct.raw` | `bronze.ct_certs` |
| --- | --- |
| `seen_ts`, `not_before`, `not_after`, `ct_seen`, `submission_ts` (số nguyên, UTC mili giây) | cột `TIMESTAMP` cùng tên (UTC, mili giây) |
| `sha256` | `sha256` |
| `subject.CN` | `subject_cn` |
| `issuer.CN`, `issuer.O` | `issuer_cn`, `issuer_o` |
| `source.name`, `source.url` | `source_name`, `log_url` |
| các trường còn lại | cùng tên |
| `message_type`, `extensions`, `subject`/`issuer` khác CN/O | không lưu |

Cột `kafka_partition`, `kafka_offset` do job bronze gắn thêm. `serial_number` có thể NULL ở `ct.raw`;
job silver gộp precert/cert theo `(issuer_cn, serial_number)` và bỏ qua bản ghi thiếu serial khỏi phép gộp (dùng `sha256` làm khoá thay thế).

## Giả định cần P2 xác nhận

Bảng `silver.enrichment` do P2 ghi; cột trong file là đề xuất của P4 theo nhu cầu đọc của `batch_graph`, P2 chỉnh nếu cần.
