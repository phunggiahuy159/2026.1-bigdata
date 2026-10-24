"""Kiểm tra khung repo: .env.example chỉ có giá trị giả, CI/pre-commit đủ bước bắt buộc."""

import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def _env_pairs(path: Path) -> dict[str, str]:
    pairs = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            key, _, value = line.partition("=")
            pairs[key] = value
    return pairs


def test_env_example_has_only_placeholder_values():
    # iceberg / iceberg_catalog là tên user và database, không phải secret
    pairs = _env_pairs(ROOT / ".env.example")
    assert pairs, ".env.example rỗng"
    for key, value in pairs.items():
        assert value.startswith("changeme-") or value in {"iceberg", "iceberg_catalog"}, key


def test_env_example_is_not_ignored_but_env_is():
    ignore = (ROOT / ".gitignore").read_text().splitlines()
    assert ".env" in ignore
    assert "!.env.example" in ignore


def test_pyproject_pins_python_311_and_dev_tools():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert "3.11" in data["project"]["requires-python"]
    dev = " ".join(data["dependency-groups"]["dev"])
    assert "pytest" in dev and "ruff" in dev
    assert (ROOT / "uv.lock").exists()


def test_pre_commit_has_required_hooks():
    config = yaml.safe_load((ROOT / ".pre-commit-config.yaml").read_text())
    hooks = {h["id"]: h for repo in config["repos"] for h in repo["hooks"]}
    for required in ("gitleaks", "check-added-large-files", "nbstripout", "ruff"):
        assert required in hooks
    assert "--maxkb=1024" in hooks["check-added-large-files"]["args"]


def test_ci_runs_ruff_pytest_gitleaks():
    ci = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
    steps = " ".join(
        str(s.get("run", s.get("uses", ""))) for job in ci["jobs"].values() for s in job["steps"]
    )
    assert "ruff check" in steps
    assert "pytest" in steps
    assert "gitleaks" in steps
    assert ci["permissions"] == {"contents": "read"}


def test_workspace_members_are_explicit_and_have_pyproject():
    members = tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]["uv"]["workspace"][
        "members"
    ]
    for member in members:
        assert not set(member) & set("*?["), f"{member}: không dùng glob trong members"
        assert (ROOT / member / "pyproject.toml").is_file(), f"{member} thiếu pyproject.toml"


def test_new_directory_without_pyproject_does_not_break_uv(tmp_path):
    for name in ("pyproject.toml", "uv.lock", "README.md"):
        shutil.copy(ROOT / name, tmp_path / name)
    for module in ("labeling", "jobs/batch_ml", "libs/scamradar_core"):
        (tmp_path / module).mkdir(parents=True)
    result = subprocess.run(
        ["uv", "lock", "--check"], cwd=tmp_path, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


def test_pytest_pythonpath_lets_tests_import_module_packages(tmp_path):
    options = tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]["pytest"]["ini_options"]
    paths = " ".join(options["pythonpath"])
    (tmp_path / "pytest.ini").write_text(f"[pytest]\npythonpath = {paths}\n")
    for package in ("ingestion", "jobs/stream_detect", "libs/scamradar_core"):
        (tmp_path / package).mkdir(parents=True)
        (tmp_path / package / "__init__.py").touch()
    (tmp_path / "jobs/__init__.py").touch()
    (tmp_path / "test_imports.py").write_text(
        "def test_imports():\n"
        "    import ingestion\n"
        "    import jobs.stream_detect\n"
        "    import scamradar_core\n"
    )
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout


def test_pre_commit_ruff_rev_matches_uv_lock():
    lock = tomllib.loads((ROOT / "uv.lock").read_text())
    locked = next(p["version"] for p in lock["package"] if p["name"] == "ruff")
    config = yaml.safe_load((ROOT / ".pre-commit-config.yaml").read_text())
    rev = next(r["rev"] for r in config["repos"] if "ruff-pre-commit" in r["repo"])
    assert rev == f"v{locked}"
