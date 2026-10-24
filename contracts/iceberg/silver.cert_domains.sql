-- Chủ ghi: P4 (jobs/batch_silver). Đọc: P4, P5.
-- Hạt: (cert_key, fqdn). Precert và cert cuối cùng của cùng một chứng chỉ gộp thành một dòng
-- theo cert_key = (issuer, serial_number). Ghi lại bằng overwritePartitions().
CREATE TABLE IF NOT EXISTS silver.cert_domains (
  cert_key          STRING    NOT NULL COMMENT 'khoá gộp precert/cert: issuer_cn|serial_number',
  fqdn              STRING    NOT NULL COMMENT 'tên đầy đủ, viết thường, bỏ "*." đầu, IDNA',
  registered_domain STRING    NOT NULL COMMENT 'domain gốc eTLD+1, từ scamradar_core',
  subdomain         STRING    COMMENT 'phần trước domain gốc, NULL nếu không có',
  tld               STRING    COMMENT 'public suffix, ví dụ com, com.vn',
  is_wildcard       BOOLEAN   NOT NULL COMMENT 'tên gốc bắt đầu bằng "*."',
  has_precert       BOOLEAN   NOT NULL,
  has_final_cert    BOOLEAN   NOT NULL,
  cert_sha256s      ARRAY<STRING> NOT NULL COMMENT 'các sha256 đã gộp',
  issuer_o          STRING,
  not_before        TIMESTAMP,
  not_after         TIMESTAMP,
  san_count         INT       NOT NULL COMMENT 'số tên trong chứng chỉ',
  cert_ts           TIMESTAMP NOT NULL COMMENT 'UTC, min(seen_ts) của các bản ghi đã gộp; cột partition ngày',
  last_seen_ts      TIMESTAMP NOT NULL
)
USING iceberg
PARTITIONED BY (days(cert_ts), bucket(32, registered_domain))
TBLPROPERTIES (
  'format-version' = '2',
  'write.parquet.compression-codec' = 'zstd',
  'write.distribution-mode' = 'hash'
);
