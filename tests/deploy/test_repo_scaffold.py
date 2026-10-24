"""Kiểm tra khung repo: .env.example chỉ có giá trị giả, CI/pre-commit đủ bước bắt buộc."""

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
