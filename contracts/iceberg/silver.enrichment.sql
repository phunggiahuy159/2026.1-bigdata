-- Chủ ghi: P2 (enrichment/). Đọc: P4 (batch_graph), P5. Cột là đề xuất của P4, P2 chỉnh.
-- Chỉ partition theo bucket: ghi bằng MERGE INTO theo (registered_domain, lookup_ts), KHÔNG overwritePartitions.
-- asn, asn_org, country tính cho cả IPv4 (A) lẫn IPv6 (AAAA), P2 đã chốt.
-- Hạt: (registered_domain, lookup_ts). Job đọc lấy bản mới nhất mỗi domain.
CREATE TABLE IF NOT EXISTS silver.enrichment (
  registered_domain STRING    NOT NULL COMMENT 'domain gốc eTLD+1, ASCII punycode',
  lookup_ts         TIMESTAMP NOT NULL COMMENT 'UTC',
  a_records         ARRAY<STRING> COMMENT 'IPv4',
  aaaa_records      ARRAY<STRING> COMMENT 'IPv6',
  ns_records        ARRAY<STRING> COMMENT 'nameserver, viết thường',
  asn               ARRAY<INT>    COMMENT 'ASN theo từng IP của concat(a_records, aaaa_records), cùng thứ tự; phần tử NULL nếu IP không tra được',
  asn_org           ARRAY<STRING> COMMENT 'như asn: một phần tử cho mỗi IP của concat(a_records, aaaa_records)',
  country           ARRAY<STRING> COMMENT 'mã quốc gia ISO-2, như asn: một phần tử cho mỗi IP của concat(a_records, aaaa_records)',
  dns_status        STRING    COMMENT 'ok, nxdomain, timeout, ...'
)
USING iceberg
PARTITIONED BY (bucket(32, registered_domain))
TBLPROPERTIES (
  'format-version' = '2',
  'write.parquet.compression-codec' = 'zstd'
);
