# batch_silver

`bronze.ct_certs` -> `silver.cert_domains` (DDL: `contracts/iceberg/silver.cert_domains.sql`). Hạt: một dòng cho mỗi (chứng chỉ, FQDN).

Các bước (`transforms.py`, mỗi bước nhận và trả DataFrame): lọc theo khoảng ngày UTC trên `seen_ts`
-> `cert_key` (`issuer_cn|SERIAL`, thiếu serial thì `sha256:<sha256>`) -> tách từng tên trong `all_domains`
(viết thường, bỏ dấu chấm cuối, bỏ `*.`) -> punycode -> loại IP/tên không hợp lệ -> tách eTLD+1 bằng `scamradar_core` (PSL gồm cả phần PRIVATE:
`x.github.io` là domain gốc riêng, khớp speed layer)
-> gộp precert/cert và khử trùng theo `(cert_key, fqdn)`.

## Ghi chạy lại được

- Đọc bronze lùi 1 ngày (`LOOKBACK_DAYS`) so với khoảng chạy, để precert ngày D và cert cuối ngày D+1 gộp ngay trong một lần chạy.
- `compute_updates` đọc dòng đã có trong silver **theo khoá** của dòng mới (không lọc theo ngày) và `merge_cert_domains`
  hợp nhất: cờ OR, hợp tập sha, `cert_ts` nhỏ nhất, `last_seen_ts` lớn nhất. Phép này lặp lại không đổi kết quả.
- Ghi bằng `MERGE INTO ... ON t.cert_key = s.cert_key AND t.fqdn = s.fqdn` (đúng khoá hạt của contract), thay cả dòng
  vì dòng ghi đã là kết quả hợp nhất. Kết quả không phụ thuộc lịch chạy: chạy từng ngày, chạy lại một ngày hay chạy cả khoảng
  đều cho cùng bảng (có test hồi quy mô phỏng `run_iceberg` qua nhiều ngày).
- Cert cuối đến muộn bao lâu sau precert cũng gộp vào dòng precert đã ghi, miễn precert đã vào silver. Nếu precert chưa từng vào silver
  thì dòng chỉ có `has_final_cert`, và sẽ được hợp nhất khi precert tới.
- Chi phí: đọc dòng cũ theo khoá là semi-join với bảng silver (không cắt được theo ngày). Chấp nhận ở quy mô hiện tại; đo khi có dữ liệu thật.

## Chạy local trên file mẫu

```bash
uv sync --all-packages              # cần Java 17
PYTHONPATH=.:libs uv run python -m jobs.batch_silver.job --start 2026-10-20 --end 2026-10-22 \
    --source-json tests/fixtures/bronze_ct_certs.jsonl --sink-path /tmp/silver_cert_domains
uv run pytest tests/batch_silver    # PSL kèm trong scamradar_core, không cần tải gì
```

Fixture `tests/fixtures/bronze_ct_certs.jsonl` sinh bằng `tests/batch_silver/make_fixture.py`; mọi tên miền là giả.

## Chưa làm / TODO

- Đường ghi Iceberg (`run_iceberg`, `MERGE INTO`) chưa chạy được vì cụm chưa cài; test chỉ phủ phần biến đổi DataFrame.
- Phiên bản PySpark (`pyproject.toml` của module) phải khớp image Spark của P1 khi image được ghim.
