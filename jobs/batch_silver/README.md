# batch_silver

`bronze.ct_certs` -> `silver.cert_domains` (DDL: `contracts/iceberg/silver.cert_domains.sql`). Hạt: một dòng cho mỗi (chứng chỉ, FQDN).

Các bước (`transforms.py`, mỗi bước nhận và trả DataFrame): lọc theo khoảng ngày UTC trên `seen_ts`
-> `cert_key` (`issuer_cn|SERIAL`, thiếu serial thì `sha256:<sha256>`) -> tách từng tên trong `all_domains`
(viết thường, bỏ dấu chấm cuối, bỏ `*.`) -> punycode -> loại IP/tên không hợp lệ -> tách eTLD+1 theo PSL
-> gộp precert/cert và khử trùng theo `(cert_key, fqdn)`.

## Ghi chạy lại được

- Đọc bronze lùi 1 ngày (`LOOKBACK_DAYS`) so với khoảng chạy, để precert ngày D và cert cuối ngày D+1 vẫn gộp.
- `merge_cert_domains` hợp nhất dòng mới với dòng đã có (cờ OR, hợp tập sha, `cert_ts` nhỏ nhất); phép này lặp lại không đổi kết quả.
- Ghi bằng `MERGE INTO` theo `(cert_key, fqdn)`, không ghi đè partition. Cert đến muộn hơn 1 ngày sau precert không được gộp.

## Chạy local trên file mẫu

```bash
data/reference/download.sh          # tải Public Suffix List về data/reference/ (không commit)
uv sync --all-packages              # cần Java 17
uv run python -m jobs.batch_silver.job --start 2026-10-20 --end 2026-10-22 \
    --source-json tests/fixtures/bronze_ct_certs.jsonl --sink-path /tmp/silver_cert_domains
uv run pytest tests/batch_silver    # test dùng luật PSL nhỏ trong conftest, không cần tải gì
```

Fixture `tests/fixtures/bronze_ct_certs.jsonl` sinh bằng `tests/batch_silver/make_fixture.py`; mọi tên miền là giả.

## Chưa làm / TODO

- `normalize.py` là bản tạm; thay bằng `libs/scamradar_core` của P3 khi thư viện được merge.
- Đường ghi Iceberg (`run_iceberg`, `MERGE INTO`) chưa chạy được vì cụm chưa cài; test chỉ phủ phần biến đổi DataFrame.
- Phiên bản PySpark (`pyproject.toml` của module) phải khớp image Spark của P1 khi image được ghim.
