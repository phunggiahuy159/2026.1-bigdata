-- Chủ ghi: P4. Đọc: P5. Hạt: (day, issuer_o). Chỉ domain thuộc .vn.
CREATE TABLE IF NOT EXISTS gold.vn_daily (
  day               DATE      NOT NULL COMMENT 'UTC',
  issuer_o          STRING    NOT NULL COMMENT 'CA phát hành',
  cert_count        BIGINT    NOT NULL,
  domain_count      BIGINT    NOT NULL,
  ca_share          DOUBLE    NOT NULL COMMENT 'cert_count / tổng cert .vn trong ngày, 0..1'
)
USING iceberg
PARTITIONED BY (days(day))
TBLPROPERTIES (
  'format-version' = '2',
  'write.parquet.compression-codec' = 'zstd'
);
