#!/usr/bin/env bash
# Bootstrap Lakekeeper và tạo warehouse `bigd` trỏ bucket `warehouse` trên MinIO. Chạy lại được:
# đã bootstrap hoặc đã có warehouse thì bỏ qua.
#  - Khoá MinIO lấy từ .env (không `source`), ghi vào file tạm quyền 0600 rồi gửi bằng
#    `curl --data @file`, không nằm trong argv. Hiện dùng tài khoản gốc của MinIO; chuyển sang
#    tài khoản riêng theo bucket ở tuần bảo mật.
#  - sts tắt; remote signing để mặc định (bật) của Lakekeeper. Kiểm đọc/ghi bảng từ Spark ở tuần 2.
set -euo pipefail

ENV_FILE="${ENV_FILE:-.env}"
NAMESPACE="${NAMESPACE:-iceberg}"
SERVICE="${SERVICE:-iceberg-catalog-lakekeeper}"
LOCAL_PORT="${LOCAL_PORT:-18181}"
WAREHOUSE="${WAREHOUSE:-bigd}"
BUCKET="${BUCKET:-warehouse}"
MINIO_ENDPOINT="${MINIO_ENDPOINT:-http://minio.minio.svc:9000}"
BASE="http://127.0.0.1:${LOCAL_PORT}"

env_value() {
  local line value
  line="$(grep -E "^$1=" "$ENV_FILE" | tail -n 1 || true)"
  value="${line#*=}"
  printf '%s' "${value%$'\r'}"
}

[[ -f "$ENV_FILE" ]] || { echo "thiếu $ENV_FILE" >&2; exit 1; }
ACCESS_KEY="$(env_value MINIO_ROOT_USER)"
SECRET_KEY="$(env_value MINIO_ROOT_PASSWORD)"
[[ -n "$ACCESS_KEY" && -n "$SECRET_KEY" ]] || { echo "thiếu MINIO_ROOT_USER/PASSWORD trong $ENV_FILE" >&2; exit 1; }

tmp="$(mktemp)"
trap 'rm -f "$tmp"; [[ -n "${pf_pid:-}" ]] && kill "$pf_pid" 2>/dev/null || true' EXIT
chmod 600 "$tmp"

kubectl port-forward -n "$NAMESPACE" "svc/$SERVICE" "${LOCAL_PORT}:8181" >/dev/null 2>&1 &
pf_pid=$!
for _ in $(seq 1 30); do
  curl -sf "$BASE/health" >/dev/null 2>&1 && break
  sleep 1
done
curl -sf "$BASE/health" >/dev/null || { echo "catalog chưa trả lời /health" >&2; exit 1; }

if curl -sf "$BASE/management/v1/info" | grep -q '"bootstrapped":true'; then
  echo "bỏ qua: Lakekeeper đã bootstrap"
else
  curl -sf -X POST "$BASE/management/v1/bootstrap" -H 'Content-Type: application/json' \
    -d '{"accept-terms-of-use": true}'
  echo "đã bootstrap Lakekeeper"
fi

if curl -sf "$BASE/management/v1/warehouse" | grep -q "\"name\":\"$WAREHOUSE\""; then
  echo "bỏ qua: warehouse $WAREHOUSE đã tồn tại"
else
  WAREHOUSE="$WAREHOUSE" BUCKET="$BUCKET" MINIO_ENDPOINT="$MINIO_ENDPOINT" \
    ACCESS_KEY="$ACCESS_KEY" SECRET_KEY="$SECRET_KEY" python3 - > "$tmp" <<'PY'
import json
import os

print(json.dumps({
    "warehouse-name": os.environ["WAREHOUSE"],
    "storage-profile": {
        "type": "s3",
        "bucket": os.environ["BUCKET"],
        "key-prefix": "iceberg",
        "endpoint": os.environ["MINIO_ENDPOINT"],
        "region": "us-east-1",
        "path-style-access": True,
        "flavor": "s3-compat",
        "sts-enabled": False,
    },
    "storage-credential": {
        "type": "s3",
        "credential-type": "access-key",
        "access-key-id": os.environ["ACCESS_KEY"],
        "secret-access-key": os.environ["SECRET_KEY"],
    },
}))
PY
  curl -sf -X POST "$BASE/management/v1/warehouse" -H 'Content-Type: application/json' \
    --data @"$tmp"
  : > "$tmp"
  echo
  echo "đã tạo warehouse $WAREHOUSE"
fi

curl -sf "$BASE/management/v1/warehouse"
echo
