-- Chủ ghi: P2 (enrichment/). Đọc: P4 (batch_graph), P5. Cột là đề xuất của P4, P2 chỉnh.
-- Hạt: (registered_domain, lookup_ts). Job đọc lấy bản mới nhất mỗi domain.
CREATE TABLE IF NOT EXISTS silver.enrichment (
  registered_domain STRING    NOT NULL,
  lookup_ts         TIMESTAMP NOT NULL COMMENT 'UTC',
  a_records         ARRAY<STRING> COMMENT 'IPv4',
  aaaa_records      ARRAY<STRING> COMMENT 'IPv6',
  ns_records        ARRAY<STRING> COMMENT 'nameserver, viết thường',
  asn               ARRAY<INT>    COMMENT 'ASN của các IP, cùng thứ tự a_records',
  asn_org           ARRAY<STRING>,
  country           ARRAY<STRING> COMMENT 'mã quốc gia ISO-2 của các IP',
  dns_status        STRING    COMMENT 'ok, nxdomain, timeout, ...'
)
USING iceberg
PARTITIONED BY (bucket(32, registered_domain))
TBLPROPERTIES (
  'format-version' = '2',
  'write.parquet.compression-codec' = 'zstd'
);
