-- Chủ ghi: P2 (jobs/stream_bronze). Đọc: P4. Chỉ append.
-- Khớp contracts/kafka/ct.raw.schema.json: các trường mili giây (int) đổi sang TIMESTAMP UTC;
-- subject/issuer/source làm phẳng. extensions không lưu (chưa ai đọc).
CREATE TABLE IF NOT EXISTS bronze.ct_certs (
  sha256        STRING    NOT NULL COMMENT 'ct.raw.sha256, cũng là key Kafka',
  update_type   STRING    NOT NULL COMMENT 'X509LogEntry (cert) hoặc PrecertLogEntry (precert)',
  all_domains   ARRAY<STRING> NOT NULL COMMENT 'CN + SAN, giữ nguyên chữ như nhận được, chưa chuẩn hoá',
  subject_cn    STRING    COMMENT 'ct.raw.subject.CN',
  issuer_cn     STRING    COMMENT 'ct.raw.issuer.CN',
  issuer_o      STRING    COMMENT 'ct.raw.issuer.O, tên CA',
  serial_number STRING    COMMENT 'ct.raw.serial_number; NULL nếu CertStream không gửi',
  fingerprint   STRING    COMMENT 'SHA-1 có dấu hai chấm, như ct.raw.fingerprint',
  signature_algorithm STRING,
  is_ca         BOOLEAN,
  not_before    TIMESTAMP NOT NULL COMMENT 'UTC, từ mili giây của ct.raw.not_before',
  not_after     TIMESTAMP NOT NULL COMMENT 'UTC, từ mili giây của ct.raw.not_after',
  cert_index    BIGINT    NOT NULL COMMENT 'chỉ số mục trong log CT',
  cert_link     STRING    COMMENT 'chỉ để tham chiếu, không fetch',
  source_name   STRING    NOT NULL COMMENT 'ct.raw.source.name',
  log_url       STRING    NOT NULL COMMENT 'ct.raw.source.url',
  ct_seen       TIMESTAMP COMMENT 'UTC, từ ct.raw.ct_seen (mili giây)',
  submission_ts TIMESTAMP COMMENT 'UTC, từ ct.raw.submission_ts (mili giây)',
  seen_ts       TIMESTAMP NOT NULL COMMENT 'UTC, collector nhận được (ct.raw.seen_ts, mili giây); cột partition',
  collector_id  STRING    NOT NULL,
  kafka_partition INT     COMMENT 'truy vết exactly-once, do job bronze gắn',
  kafka_offset  BIGINT    COMMENT 'truy vết exactly-once, do job bronze gắn'
)
USING iceberg
PARTITIONED BY (days(seen_ts))
TBLPROPERTIES (
  'format-version' = '2',
  'write.format.default' = 'parquet',
  'write.parquet.compression-codec' = 'zstd'
);
