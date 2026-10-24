# Onboarding

## Môi trường Python

Repo dùng [uv](https://docs.astral.sh/uv/) với Python 3.11 và một workspace.

```bash
uv sync                 # tạo .venv từ uv.lock
uv run pytest           # chạy test
uv run ruff check .     # lint
pre-commit install      # bật gitleaks, chặn file lớn, nbstripout, ruff
```

## Thêm dependency cho module của mình

`pyproject.toml` gốc chỉ giữ công cụ dev. Mỗi module có `pyproject.toml` riêng
trong thư mục của mình (`libs/<tên>`, `ingestion`, `enrichment`, `jobs/<tên>`,
`labeling`, `serving`) và tự được nhận làm member của workspace.

```toml
[project]
name = "stream-detect"
version = "0.1.0"
requires-python = ">=3.11,<3.12"
dependencies = ["redis>=5", "scamradar-core"]

[tool.uv.sources]
scamradar-core = { workspace = true }
```

Sau đó chạy `uv lock` và commit `uv.lock`. Khi `uv.lock` xung đột lúc merge, chạy lại
`uv lock` trên nhánh đã rebase thay vì sửa tay. Phiên bản PySpark, Iceberg, GraphFrames
theo image Spark chung của P1, không tự đổi.

## Biến môi trường

Sao chép `.env.example` thành `.env` (đã gitignore) và điền giá trị thật. Không commit `.env`.
