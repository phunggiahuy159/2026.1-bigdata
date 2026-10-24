-- Chủ ghi: P5 (labeling/). Đọc: P5. Hạt: (registered_domain, label_source).
CREATE TABLE IF NOT EXISTS silver.labels (
  registered_domain STRING    NOT NULL,
  label             STRING    NOT NULL COMMENT 'phishing | benign',
  label_source      STRING    NOT NULL COMMENT 'safe_browsing | manual | tranco | official',
  labeled_ts        TIMESTAMP NOT NULL COMMENT 'UTC',
  confidence        DOUBLE    COMMENT '0..1'
)
USING iceberg
PARTITIONED BY (bucket(32, registered_domain))
TBLPROPERTIES (
  'format-version' = '2',
  'write.parquet.compression-codec' = 'zstd'
);
