#!/usr/bin/env bash
# Tạo K8s Secret từ .env cho MinIO và Iceberg catalog.
#  - Không đọc .env bằng `source`: chỉ lấy các dòng KEY=VALUE, không chạy lệnh nào trong file.
#  - Từ chối chạy nếu biến thiếu, rỗng hoặc còn giá trị mẫu `changeme-*`.
#  - Không ghi đè Secret đã có: đổi mật khẩu hay khoá mã hoá sau khi DB đã khởi tạo làm hỏng
#    catalog. Muốn đổi thì xoá Secret bằng tay, có chủ đích, kèm đổi mật khẩu trong DB.
#  - Giá trị đi qua file tạm quyền 0600 (--from-env-file), không nằm trong argv của kubectl.
set -euo pipefail

ENV_FILE="${ENV_FILE:-.env}"
KUBECTL="${KUBECTL:-kubectl}"

[[ -f "$ENV_FILE" ]] || { echo "thiếu $ENV_FILE (sao chép từ .env.example)" >&2; exit 1; }

env_value() {
  local line value
  line="$(grep -E "^$1=" "$ENV_FILE" | tail -n 1 || true)"
  value="${line#*=}"
  value="${value%$'\r'}"
  if [[ "$value" =~ ^\"(.*)\"$ || "$value" =~ ^\'(.*)\'$ ]]; then
    value="${BASH_REMATCH[1]}"
  fi
  printf '%s' "$value"
}

REQUIRED=(
  MINIO_ROOT_USER MINIO_ROOT_PASSWORD
  POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD POSTGRES_SUPERUSER_PASSWORD
  CATALOG_ENCRYPTION_KEY
)

declare -A V
errors=0
for name in "${REQUIRED[@]}"; do
  V[$name]="$(env_value "$name")"
  if [[ -z "${V[$name]}" ]]; then
    echo "lỗi: $name rỗng hoặc thiếu trong $ENV_FILE" >&2
    errors=1
  elif [[ "${V[$name]}" == changeme-* ]]; then
    echo "lỗi: $name còn giá trị mẫu changeme-*" >&2
    errors=1
  elif [[ "${V[$name]}" == *$'\n'* ]]; then
    echo "lỗi: $name chứa xuống dòng" >&2
    errors=1
  fi
done
[[ $errors -eq 0 ]] || { echo "không tạo Secret nào." >&2; exit 1; }

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

create_secret() {
  local namespace="$1" name="$2"
  shift 2
  local existing
  existing="$("$KUBECTL" get secret "$name" -n "$namespace" -o name --ignore-not-found)"
  if [[ -n "$existing" ]]; then
    echo "bỏ qua: secret $namespace/$name đã tồn tại (xoá bằng tay nếu thật sự muốn đổi)"
    return 0
  fi
  : > "$tmp"
  chmod 600 "$tmp"
  printf '%s\n' "$@" > "$tmp"
  "$KUBECTL" create secret generic "$name" -n "$namespace" --from-env-file="$tmp"
  : > "$tmp"
}

create_secret minio minio-credentials \
  "rootUser=${V[MINIO_ROOT_USER]}" \
  "rootPassword=${V[MINIO_ROOT_PASSWORD]}"
create_secret iceberg catalog-postgres \
  "superuser=postgres" \
  "superuser-password=${V[POSTGRES_SUPERUSER_PASSWORD]}" \
  "database=${V[POSTGRES_DB]}" \
  "user=${V[POSTGRES_USER]}" \
  "password=${V[POSTGRES_PASSWORD]}"
create_secret iceberg catalog-encryption \
  "encryptionKey=${V[CATALOG_ENCRYPTION_KEY]}"
