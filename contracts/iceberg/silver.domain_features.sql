-- Chủ ghi: P4 (jobs/batch_features). Đọc: P5. Hạt: (registered_domain, feature_date).
CREATE TABLE IF NOT EXISTS silver.domain_features (
  feature_date      DATE      NOT NULL COMMENT 'ngày UTC của đặc trưng',
  registered_domain STRING    NOT NULL,
  cert_cnt_1h       INT       COMMENT 'số cert trong 1 giờ cuối ngày',
  cert_cnt_24h      INT,
  cert_cnt_7d       INT,
  secs_since_prev_cert BIGINT COMMENT 'lag giữa hai lần cấp, NULL nếu lần đầu',
  subdomain_approx_cnt BIGINT COMMENT 'approx_count_distinct subdomain',
  max_san_count     INT,
  brands            ARRAY<STRING> COMMENT 'brand_id (brands.yaml) khớp với domain',
  brand_rank        INT       COMMENT 'rank theo thương hiệu trong ngày, theo cert_cnt_24h',
  tld               STRING,
  issuer_o          STRING    COMMENT 'CA gần nhất trong ngày',
  first_seen_date   DATE      COMMENT 'ngày đầu tiên thấy domain (từ gold.domain_history)'
)
USING iceberg
PARTITIONED BY (feature_date)
TBLPROPERTIES (
  'format-version' = '2',
  'write.parquet.compression-codec' = 'zstd'
);
