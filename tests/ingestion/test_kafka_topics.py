"""Đối chiếu ingestion/kafka/topics.yaml với contracts/kafka/README.md và deploy/kafka."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
HOUR_MS = 3600 * 1000
TOPICS = {
    d["metadata"]["name"]: d
    for d in yaml.safe_load_all((ROOT / "ingestion/kafka/topics.yaml").read_text(encoding="utf-8"))
}
CLUSTER = [
    d
    for d in yaml.safe_load_all((ROOT / "deploy/kafka/kafka-cluster.yaml").read_text("utf-8"))
    if d["kind"] == "Kafka"
][0]


def contract_rows():
    rows = {}
    for line in (ROOT / "contracts/kafka/README.md").read_text(encoding="utf-8").splitlines():
        if line.startswith("| `"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            rows[cells[0].strip("`")] = cells
    return rows


def retention_hours(text):
    n, unit = text.split()
    return int(n) * {"giờ": 1, "ngày": 24}[unit]


def test_topics_match_contract_set():
    assert set(TOPICS) == set(contract_rows())


def test_partitions_retention_and_compression_follow_contract():
    default_partitions = CLUSTER["spec"]["kafka"]["config"]["num.partitions"]
    for name, row in contract_rows().items():
        spec = TOPICS[name]["spec"]
        partitions = default_partitions if row[2] == "theo mặc định" else int(row[2])
        assert spec["partitions"] == partitions, name
        assert spec["config"]["retention.ms"] == retention_hours(row[3]) * HOUR_MS, name
        assert spec["config"]["compression.type"] == row[4] == "zstd", name


def test_cluster_reference_matches_deploy():
    cluster = CLUSTER["metadata"]["name"]
    for name, doc in TOPICS.items():
        assert doc["apiVersion"] == CLUSTER["apiVersion"], name
        assert doc["kind"] == "KafkaTopic"
        assert doc["metadata"]["labels"]["strimzi.io/cluster"] == cluster, name
        assert doc["metadata"]["namespace"] == "kafka", name
        assert (
            doc["spec"]["replicas"]
            == CLUSTER["spec"]["kafka"]["config"]["default.replication.factor"]
        )
