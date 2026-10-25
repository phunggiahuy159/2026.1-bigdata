"""Kiểm tra deploy/scripts/create-secrets.sh bằng kubectl giả: không chạm cụm thật."""

import os
import stat
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "deploy/scripts/create-secrets.sh"
NAMES = (
    "MINIO_ROOT_USER",
    "MINIO_ROOT_PASSWORD",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_SUPERUSER_PASSWORD",
    "CATALOG_ENCRYPTION_KEY",
)
# giá trị sinh từ tên biến, không có chuỗi giống khoá thật trong mã nguồn
ENV_VALUES = {name: f"fake-{name.lower().replace('_', '-')}-v1" for name in NAMES}

FAKE_KUBECTL = """#!/usr/bin/env bash
echo "$@" >> "$FAKE_LOG"
if [[ "$1" == "get" ]]; then
  grep -qx "$3" "$FAKE_EXISTING" 2>/dev/null && echo "secret/$3"
  exit 0
fi
for arg in "$@"; do
  if [[ "$arg" == --from-env-file=* ]]; then
    file="${arg#--from-env-file=}"
    stat -c '%a' "$file" >> "$FAKE_MODES"
    cat "$file" >> "$FAKE_CAPTURE"
    echo "$file" >> "$FAKE_FILES"
  fi
done
"""


@pytest.fixture
def sandbox(tmp_path):
    kubectl = tmp_path / "kubectl"
    kubectl.write_text(FAKE_KUBECTL)
    kubectl.chmod(kubectl.stat().st_mode | stat.S_IXUSR)
    (tmp_path / "existing").write_text("")

    def run(values=None, extra_lines="", existing=()):
        merged = {**ENV_VALUES, **(values or {})}
        env_file = tmp_path / ".env"
        body = "".join(f"{k}={v}\n" for k, v in merged.items() if v is not None)
        env_file.write_text(body + extra_lines)
        (tmp_path / "existing").write_text("\n".join(existing))
        for name in ("log", "modes", "capture", "files"):
            (tmp_path / name).write_text("")
        env = {
            **os.environ,
            "ENV_FILE": str(env_file),
            "KUBECTL": str(kubectl),
            "FAKE_LOG": str(tmp_path / "log"),
            "FAKE_MODES": str(tmp_path / "modes"),
            "FAKE_CAPTURE": str(tmp_path / "capture"),
            "FAKE_FILES": str(tmp_path / "files"),
            "FAKE_EXISTING": str(tmp_path / "existing"),
        }
        result = subprocess.run(
            ["bash", str(SCRIPT)], env=env, capture_output=True, text=True, check=False
        )
        read = {n: (tmp_path / n).read_text() for n in ("log", "modes", "capture", "files")}
        return result, read

    return run


def test_creates_three_secrets_with_private_temp_files(sandbox):
    result, read = sandbox()
    assert result.returncode == 0, result.stderr
    creates = [line for line in read["log"].splitlines() if line.startswith("create")]
    assert [line.split()[3] for line in creates] == [
        "minio-credentials",
        "catalog-postgres",
        "catalog-encryption",
    ]
    assert set(read["modes"].split()) == {"600"}
    assert f"rootPassword={ENV_VALUES['MINIO_ROOT_PASSWORD']}" in read["capture"]
    for path in read["files"].split():
        assert not Path(path).exists(), "file tạm phải bị xoá"


def test_passwords_never_appear_in_kubectl_argv(sandbox):
    result, read = sandbox()
    assert result.returncode == 0, result.stderr
    for name in ("MINIO_ROOT_PASSWORD", "POSTGRES_PASSWORD", "POSTGRES_SUPERUSER_PASSWORD"):
        assert ENV_VALUES[name] not in read["log"]
    assert ENV_VALUES["CATALOG_ENCRYPTION_KEY"] not in read["log"]
    assert "--from-literal" not in read["log"]


def test_existing_secret_is_not_overwritten(sandbox):
    result, read = sandbox(existing=["catalog-encryption", "catalog-postgres"])
    assert result.returncode == 0, result.stderr
    created = [line.split()[3] for line in read["log"].splitlines() if line.startswith("create")]
    assert created == ["minio-credentials"]
    assert "bỏ qua" in result.stdout
    assert ENV_VALUES["CATALOG_ENCRYPTION_KEY"] not in read["capture"]


@pytest.mark.parametrize(
    "override",
    [
        {"CATALOG_ENCRYPTION_KEY": "changeme-catalog-encryption-key"},
        {"POSTGRES_PASSWORD": ""},
        {"MINIO_ROOT_PASSWORD": None},
    ],
    ids=["placeholder", "empty", "missing"],
)
def test_refuses_placeholder_empty_or_missing_values(sandbox, override):
    result, read = sandbox(values=override)
    assert result.returncode != 0
    assert read["log"] == "", "không được gọi kubectl khi .env chưa hợp lệ"
    assert "không tạo Secret nào" in result.stderr


def test_env_file_is_not_executed(sandbox, tmp_path):
    marker = tmp_path / "pwned"
    result, _ = sandbox(extra_lines=f"EVIL=$(touch {marker})\n`touch {marker}`\n")
    assert result.returncode == 0, result.stderr
    assert not marker.exists()


def test_quoted_values_are_unquoted(sandbox):
    result, read = sandbox(values={"POSTGRES_PASSWORD": '"quoted pass $x"'})
    assert result.returncode == 0, result.stderr
    assert "password=quoted pass $x\n" in read["capture"]
