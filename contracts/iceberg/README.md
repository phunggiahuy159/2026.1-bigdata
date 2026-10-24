# Hợp đồng Iceberg

DDL Spark SQL cho các bảng lakehouse của nhóm. Mỗi bảng một file `<namespace>.<bảng>.sql`.
Thứ tự tạo: `00_namespaces.sql`, rồi các bảng bất kỳ (không có khoá ngoại).

## Quy ước

- Catalog Iceberg là catalog mặc định của phiên Spark (`spark.sql.defaultCatalog`), nên DDL chỉ ghi `namespace.bảng`.
- **Bắt buộc** đặt `spark.sql.session.timeZone=UTC` cho mọi job đọc/ghi các bảng này (image/conf Spark chung của P1). `TIMESTAMP` theo múi giờ của phiên, nên `days(...)` và các cột `DATE` (`feature_date`, `day`, `score_date`, `history_date`, `run_date`) sẽ lệch ngày nếu khác UTC.
- Domain (`fqdn`, `registered_domain`, `subdomain`, `tld`) lưu dạng ASCII punycode (`xn--...`), viết thường, đúng đầu ra của `scamradar_core`, để join với `silver.enrichment`, `gold.domain_scores` và `_id` MongoDB không lệch. Unicode chỉ dùng khi hiển thị.
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
- Bảng partition theo ngày, hạt không vượt khỏi ngày (`silver.domain_features`, `gold.campaigns`, `gold.brand_daily`, `gold.vn_daily`, `gold.domain_scores`): job nhận khoảng ngày và ghi bằng `overwritePartitions()`.
- Bảng **chỉ partition theo bucket**, không có cột ngày trong partition (`gold.domain_history`, `silver.enrichment`, `silver.labels`): chỉ ghi bằng `MERGE INTO` theo khoá hạt trong bảng trên. Không dùng `overwritePartitions()` vì nó ghi đè cả bucket, xoá dữ liệu của các ngày khác.
- `silver.cert_domains` (partition `days(cert_ts)` + bucket): ghi bằng `MERGE INTO` theo `(cert_key, fqdn)`, và job đọc bronze **lùi 1 ngày** so với khoảng chạy (chạy ngày `[s, e]` thì đọc `[s-1, e]`).
  Lý do: `cert_ts = min(seen_ts)` của các bản đã gộp. Precert đến ngày D và cert cuối đến ngày D+1: nếu chỉ đọc D+1 sẽ ra một dòng `cert_ts` thuộc D+1 trùng với dòng đã có ở D. Đọc lùi 1 ngày thì cả hai bản cùng vào phép gộp, `cert_ts` vẫn thuộc D và `MERGE` cập nhật đúng dòng cũ (`has_final_cert`, `cert_sha256s`, `last_seen_ts`). Cert cuối đến muộn hơn 1 ngày sau precert không được gộp ở bảng này; đo tỷ lệ này trên dữ liệu thật và tăng cửa sổ lùi nếu đáng kể.
- Không `append` thuần ở bảng nào của P4.

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
job silver gộp precert/cert theo `cert_key = issuer_cn|upper(serial_number)`. Quy tắc khi thiếu serial: `cert_key = 'sha256:' || sha256`, tức bản ghi đó không gộp được với precert/cert tương ứng và được tính là một chứng chỉ riêng.
`issuer_cn` của precert đôi khi khác cert cuối (intermediate riêng cho precert); cần kiểm trên dữ liệu thật trước khi coi `cert_key` là chắc chắn, nếu lệch nhiều thì đổi khoá gộp (ví dụ chỉ `serial_number` + `not_before`) và cập nhật file này.

## Giả định cần P2 xác nhận

Bảng `silver.enrichment` do P2 ghi; cột trong file là đề xuất của P4 theo nhu cầu đọc của `batch_graph`, P2 chỉnh nếu cần.
Đã chốt (P2): `asn`, `asn_org`, `country` tính cho cả IPv4 (`a_records`) và IPv6 (`aaaa_records`); mỗi cột là mảng một phần tử cho mỗi IP của `concat(a_records, aaaa_records)`, cùng thứ tự, phần tử NULL nếu IP không tra được.
