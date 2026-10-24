#!/usr/bin/env bash
# Tải dữ liệu tham chiếu vào data/reference/ (file tải về KHÔNG commit, xem .gitignore).
# Dùng: data/reference/download.sh [thư_mục_đích]
set -euo pipefail

DEST="${1:-$(cd "$(dirname "$0")" && pwd)}"
PSL_URL="${PSL_URL:-https://publicsuffix.org/list/public_suffix_list.dat}"
# Bảng confusables của Unicode (UTS #39). Ghim phiên bản để tái lập.
CONFUSABLES_URL="${CONFUSABLES_URL:-https://www.unicode.org/Public/security/latest/confusables.txt}"

mkdir -p "$DEST"

fetch() {
  local url="$1" out="$2"
  echo "tải $url -> $out"
  curl --fail --silent --show-error --location --retry 3 --output "$out.tmp" "$url"
  mv "$out.tmp" "$out"
}

fetch "$PSL_URL" "$DEST/public_suffix_list.dat"
fetch "$CONFUSABLES_URL" "$DEST/confusables.txt"

{
  echo "downloaded_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "psl_url=$PSL_URL"
  echo "confusables_url=$CONFUSABLES_URL"
  sha256sum "$DEST/public_suffix_list.dat" "$DEST/confusables.txt"
} > "$DEST/VERSIONS.txt"
echo "xong, xem $DEST/VERSIONS.txt"
