-- Chủ ghi: P2 (jobs/stream_bronze). Đọc: P4. Chỉ append.
-- Giả định: theo định dạng lite của CertStream; xem README.md.
CREATE TABLE IF NOT EXISTS bronze.ct_certs (
  cert_sha256   STRING    NOT NULL COMMENT 'sha256 của chứng chỉ, key Kafka ct.raw',
  update_type   STRING    NOT NULL COMMENT 'X509LogEntry (cert) hoặc PrecertLogEntry (precert)',
  all_domains   ARRAY<STRING> NOT NULL COMMENT 'SAN + CN như CertStream báo, chưa chuẩn hoá',
  subject_cn    STRING    COMMENT 'subject.CN',
  issuer_cn     STRING    COMMENT 'issuer.CN',
  issuer_o      STRING    COMMENT 'issuer.O, tên CA',
  serial_number STRING    NOT NULL COMMENT 'số serial, hex viết hoa',
  not_before    TIMESTAMP COMMENT 'UTC',
  not_after     TIMESTAMP COMMENT 'UTC',
  cert_index    BIGINT    COMMENT 'chỉ số trong CT log',
  log_url       STRING    COMMENT 'source.url của CT log',
  seen_ts       TIMESTAMP NOT NULL COMMENT 'UTC, collector nhận được; cột partition',
  collector_id  STRING    NOT NULL,
  kafka_partition INT     COMMENT 'truy vết exactly-once',
  kafka_offset  BIGINT    COMMENT 'truy vết exactly-once'
)
USING iceberg
PARTITIONED BY (days(seen_ts))
TBLPROPERTIES (
  'format-version' = '2',
  'write.format.default' = 'parquet',
  'write.parquet.compression-codec' = 'zstd'
);
