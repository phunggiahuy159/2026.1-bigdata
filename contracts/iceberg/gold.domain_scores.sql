-- Chủ ghi: P5 (jobs/batch_ml). Đọc: P5. Hạt: (registered_domain, score_date, model_version).
CREATE TABLE IF NOT EXISTS gold.domain_scores (
  score_date        DATE      NOT NULL,
  registered_domain STRING    NOT NULL,
  score             INT       NOT NULL COMMENT '0..100',
  reasons           ARRAY<STRING> NOT NULL,
  model_version     STRING    NOT NULL,
  scored_ts         TIMESTAMP NOT NULL COMMENT 'UTC'
)
USING iceberg
PARTITIONED BY (score_date)
TBLPROPERTIES (
  'format-version' = '2',
  'write.parquet.compression-codec' = 'zstd'
);
