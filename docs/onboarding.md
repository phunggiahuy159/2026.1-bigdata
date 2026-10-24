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

`pyproject.toml` gốc chỉ giữ công cụ dev, và `[tool.uv.workspace].members` liệt kê rõ
từng module (không dùng glob). Một thư mục nằm trong `members` mà thiếu `pyproject.toml`
làm hỏng mọi lệnh `uv` của cả nhóm, nên khi thêm module mới, trong **cùng một PR**:

1. Tạo `pyproject.toml` tối thiểu trong thư mục module (`libs/<tên>`, `ingestion`,
   `enrichment`, `jobs/<tên>`, `labeling`, `serving`).
2. Thêm đường dẫn thư mục đó vào `members` của `pyproject.toml` gốc (một dòng).
3. Chạy `uv lock` và commit `uv.lock`.

Thư mục chưa có trong `members` không ảnh hưởng uv.

```toml
[project]
name = "stream-detect"
version = "0.1.0"
requires-python = ">=3.11,<3.12"
dependencies = ["redis>=5", "scamradar-core"]

[tool.uv.sources]
scamradar-core = { workspace = true }
```

Khi `uv.lock` xung đột lúc merge, chạy lại `uv lock` trên nhánh đã rebase thay vì sửa tay.
Phiên bản PySpark, Iceberg, GraphFrames theo image Spark chung của P1, không tự đổi.

## Import trong test

Pytest đặt `pythonpath = [".", "libs"]`, nên test import trực tiếp từ gốc repo:
`import ingestion`, `import jobs.stream_detect`, `import scamradar_core`. Module cần
`__init__.py` (thư mục `jobs/` dùng namespace package). Nguồn nằm ngoài các thư mục
trên thì báo P1 thêm vào `pythonpath`.

## Phiên bản ruff

`rev` của ruff trong `.pre-commit-config.yaml` phải bằng bản trong `uv.lock`
(`v<phiên bản>`); test trong `tests/deploy` kiểm tra điều này. Nâng ruff:
`uv lock --upgrade-package ruff` rồi sửa `rev` theo.

## Biến môi trường

Sao chép `.env.example` thành `.env` (đã gitignore) và điền giá trị thật. Không commit `.env`.
