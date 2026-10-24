-- Chủ ghi: P4. Đọc: P5. Hạt: (day, brand_id).
CREATE TABLE IF NOT EXISTS gold.brand_daily (
  day               DATE      NOT NULL COMMENT 'UTC',
  brand_id          STRING    NOT NULL COMMENT 'brand_id trong data/reference/brands.yaml',
  cert_count        BIGINT    NOT NULL,
  domain_count      BIGINT    NOT NULL COMMENT 'số domain gốc khác nhau',
  new_domain_count  BIGINT    NOT NULL COMMENT 'domain lần đầu thấy trong ngày',
  top_tlds          MAP<STRING, BIGINT> COMMENT 'số domain theo TLD',
  top_issuers       MAP<STRING, BIGINT> COMMENT 'số cert theo CA'
)
USING iceberg
PARTITIONED BY (days(day))
TBLPROPERTIES (
  'format-version' = '2',
  'write.parquet.compression-codec' = 'zstd'
);
