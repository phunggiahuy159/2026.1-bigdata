-- Chủ ghi: P4 (jobs/batch_graph). Đọc: P5. Hạt: (run_date, campaign_id).
-- Domain trong bảng là domain thật dạng chuỗi; mọi nơi hiển thị phải vô hiệu hoá (hxxps://abc[.]com).
CREATE TABLE IF NOT EXISTS gold.campaigns (
  run_date          DATE      NOT NULL COMMENT 'ngày chạy job (UTC)',
  campaign_id       STRING    NOT NULL COMMENT 'ổn định giữa các lần chạy: hash của domain nhỏ nhất trong thành phần',
  domain_count      INT       NOT NULL,
  domains           ARRAY<STRING> NOT NULL COMMENT 'registered_domain thuộc chiến dịch',
  brands            ARRAY<STRING> COMMENT 'brand_id bị mạo danh',
  shared_ips        ARRAY<STRING>,
  shared_nameservers ARRAY<STRING>,
  asns              ARRAY<INT>,
  hub_node          STRING    COMMENT 'hạ tầng trung tâm theo PageRank',
  hub_rank          DOUBLE,
  first_seen_ts     TIMESTAMP COMMENT 'UTC',
  last_seen_ts      TIMESTAMP
)
USING iceberg
PARTITIONED BY (run_date)
TBLPROPERTIES (
  'format-version' = '2',
  'write.parquet.compression-codec' = 'zstd'
);
