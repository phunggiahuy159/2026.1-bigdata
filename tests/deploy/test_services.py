"""Kiểm tra deploy/: phiên bản ghim, requests/limits, tổng tài nguyên, volume, không secret thật."""

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "deploy"
CATALOG = yaml.safe_load((DEPLOY / "services.yaml").read_text())
SERVICES = CATALOG["services"]
WEEK1 = [s for s in SERVICES if s["week"] == 1]
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def _load_all(path: Path) -> list:
    return [d for d in yaml.safe_load_all(path.read_text()) if d]


def _walk(node, path=()):
    yield path, node
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _walk(value, (*path, key))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _walk(value, (*path, index))


def _total(services, section, field):
    return sum(s[section][field] for s in services)


@pytest.mark.parametrize("service", SERVICES, ids=lambda s: s["name"])
def test_versions_are_pinned(service):
    if service["chart"]:
        assert SEMVER.match(service["chart"]["version"]), service["name"]
    assert service["images"], service["name"]
    for image in service["images"]:
        name, _, tag = image.rpartition(":")
        assert name and tag, f"{image}: thiếu tag"
        assert tag not in {"latest", "stable", "main"}, image
    assert service["images_checked"] is True, f"{service['name']}: chưa kiểm image kéo được"


@pytest.mark.parametrize("service", SERVICES, ids=lambda s: s["name"])
def test_requests_do_not_exceed_limits(service):
    for field in ("cpu", "memory"):
        assert 0 < service["requests"][field] <= service["limits"][field], service["name"]


def test_week1_services_have_files_with_resources_everywhere():
    for service in WEEK1:
        path = ROOT / (service.get("values") or service["manifest"])
        assert path.is_file(), path
        found = 0
        for doc in _load_all(path):
            for _, node in _walk(doc):
                if not isinstance(node, dict):
                    continue
                for key in ("resources", "initResources"):
                    if key in node:
                        found += 1
                        for section in ("requests", "limits"):
                            for field in ("cpu", "memory"):
                                assert node[key][section][field], (path, key)
        assert found, f"{path}: không đặt resources"


def test_platform_requests_fit_the_machine():
    machine = CATALOG["machine"]
    available = machine["memory_mib"] - machine["reserved_mib"]
    assert _total(SERVICES, "requests", "memory") <= 0.7 * available
    assert _total(WEEK1, "requests", "memory") <= 0.25 * available
    assert _total(SERVICES, "requests", "cpu") <= machine["threads"] * 1000 * 0.5
    assert _total(SERVICES, "limits", "memory") <= machine["memory_mib"]


def test_makefile_versions_match_services():
    makefile = (ROOT / "Makefile").read_text()
    pins = dict(re.findall(r"^(\w+_VERSION) := (\S+)$", makefile, re.MULTILINE))
    by_name = {s["name"]: s["chart"]["version"] for s in SERVICES if s["chart"]}
    assert pins == {
        "STRIMZI_VERSION": by_name["strimzi-operator"],
        "MINIO_VERSION": by_name["minio"],
        "LAKEKEEPER_VERSION": by_name["iceberg-catalog"],
    }


def test_image_tags_in_values_match_services():
    images = {s["name"]: s["images"] for s in SERVICES}
    minio = yaml.safe_load((DEPLOY / "minio/values.yaml").read_text())
    for key in ("image", "mcImage"):
        assert f"{minio[key]['repository']}:{minio[key]['tag']}" in images["minio"]
    catalog = yaml.safe_load((DEPLOY / "iceberg-catalog/values.yaml").read_text())
    assert (
        f"quay.io/lakekeeper/catalog:{catalog['catalog']['image']['tag']}"
        in images["iceberg-catalog"]
    )
    assert (
        f"docker.io/postgres:{catalog['postgresql']['image']['tag']}" in images["iceberg-catalog"]
    )
    strimzi = yaml.safe_load((DEPLOY / "kafka/strimzi-operator-values.yaml").read_text())
    assert f"quay.io/strimzi/operator:{strimzi['defaultImageTag']}" in images["strimzi-operator"]


def test_volume_sizes_match_declared_disk():
    docs = _load_all(DEPLOY / "storage/bigd-data.yaml")
    volumes = {
        d["metadata"]["labels"]["bigd.volume"]: d for d in docs if d["kind"] == "PersistentVolume"
    }
    disk = {s["name"]: s["disk_gib"] for s in SERVICES}
    sizes = {
        n: int(v["spec"]["capacity"]["storage"].removesuffix("Gi")) for n, v in volumes.items()
    }
    assert sizes == {
        "kafka": disk["kafka"],
        "minio": disk["minio"],
        "catalog-postgres": disk["iceberg-catalog"],
    }


def test_kafka_image_matches_cluster_version():
    kafka = next(d for d in _load_all(DEPLOY / "kafka/kafka-cluster.yaml") if d["kind"] == "Kafka")
    version = kafka["spec"]["kafka"]["version"]
    images = next(s for s in SERVICES if s["name"] == "kafka")["images"]
    assert any(image.endswith(f"-kafka-{version}") for image in images)
