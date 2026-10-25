"""Kiểm tra deploy/: Kafka khớp hợp đồng, volume trên /bigd-data, resources, không secret thật."""

from pathlib import Path

import pytest
import yaml

DEPLOY = Path(__file__).resolve().parents[2] / "deploy"
LITERAL_SECRET_KEYS = {"password", "rootPassword", "rootUser", "encryptionKey", "token", "apiKey"}


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


def _kafka_docs() -> dict:
    return {d["kind"]: d for d in _load_all(DEPLOY / "kafka/kafka-cluster.yaml")}


def test_kafka_cluster_matches_data_contract():
    docs = _kafka_docs()
    pool, kafka = docs["KafkaNodePool"], docs["Kafka"]
    assert pool["spec"]["replicas"] == 1
    assert set(pool["spec"]["roles"]) == {"controller", "broker"}
    config = kafka["spec"]["kafka"]["config"]
    assert config["num.partitions"] == 6
    assert config["log.retention.hours"] == 48
    assert config["auto.create.topics.enable"] is False


def test_kafka_version_is_pinned_and_operator_tag_matches():
    version = _kafka_docs()["Kafka"]["spec"]["kafka"]["version"]
    assert version.count(".") == 2
    operator = yaml.safe_load((DEPLOY / "kafka/strimzi-operator-values.yaml").read_text())
    assert operator["defaultImageTag"].count(".") == 2


def test_volumes_live_on_bigd_data():
    docs = _load_all(DEPLOY / "storage/bigd-data.yaml")
    volumes = {
        d["metadata"]["labels"]["bigd.volume"]: d for d in docs if d["kind"] == "PersistentVolume"
    }
    assert {"kafka", "minio", "catalog-postgres"} <= set(volumes)
    for name, volume in volumes.items():
        assert volume["spec"]["hostPath"]["path"] == f"/bigd-data/{name}"
        assert volume["spec"]["storageClassName"] == "bigd-data"


def test_kafka_pool_binds_to_its_volume():
    pool = _kafka_docs()["KafkaNodePool"]["spec"]
    assert pool["storage"]["class"] == "bigd-data"
    assert pool["storage"]["selector"] == {"bigd.volume": "kafka"}
    volumes = _load_all(DEPLOY / "storage/bigd-data.yaml")
    kafka_pv = next(
        d for d in volumes if d["metadata"].get("labels", {}).get("bigd.volume") == "kafka"
    )
    assert pool["storage"]["size"] == kafka_pv["spec"]["capacity"]["storage"]


@pytest.mark.parametrize(
    "path",
    [DEPLOY / "kafka/kafka-cluster.yaml", DEPLOY / "kafka/strimzi-operator-values.yaml"],
    ids=lambda p: p.name,
)
def test_every_resources_block_has_requests_and_limits(path):
    found = 0
    for doc in _load_all(path):
        for _, node in _walk(doc):
            if isinstance(node, dict) and "resources" in node:
                found += 1
                for section in ("requests", "limits"):
                    for field in ("cpu", "memory"):
                        assert node["resources"][section][field], (path.name, section, field)
    assert found, f"{path.name}: không đặt resources"


@pytest.mark.parametrize(
    "path",
    sorted(p for p in DEPLOY.rglob("*.yaml") if p.name != "services.yaml"),
    ids=lambda p: str(p.relative_to(DEPLOY)),
)
def test_no_literal_secrets_in_deploy_files(path):
    for doc in _load_all(path):
        assert doc.get("kind") != "Secret", f"{path}: không commit Secret"
        for node_path, node in _walk(doc):
            if node_path and node_path[-1] in LITERAL_SECRET_KEYS and isinstance(node, str):
                pytest.fail(f"{path}: {'.'.join(map(str, node_path))} là giá trị literal")
