-- Chủ ghi: P4. Đọc: P4. Hạt: (registered_domain, history_date).
-- Cùng bucket(32, registered_domain) với silver.cert_domains để join không shuffle (bucketed join).
CREATE TABLE IF NOT EXISTS gold.domain_history (
  registered_domain STRING    NOT NULL,
  history_date      DATE      NOT NULL,
  cert_count        INT       NOT NULL COMMENT 'số chứng chỉ trong ngày',
  fqdn_count        INT       NOT NULL,
  first_seen_ts     TIMESTAMP NOT NULL COMMENT 'lần đầu thấy domain tính đến ngày này',
  last_seen_ts      TIMESTAMP NOT NULL,
  total_cert_count  BIGINT    NOT NULL COMMENT 'cộng dồn đến hết ngày'
)
USING iceberg
PARTITIONED BY (bucket(32, registered_domain))
TBLPROPERTIES (
  'format-version' = '2',
  'write.parquet.compression-codec' = 'zstd',
  'write.distribution-mode' = 'hash'
);
