import os
from pathlib import Path

import pytest

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "bronze_ct_certs.jsonl"


@pytest.fixture(scope="session")
def spark():
    from pyspark.sql import SparkSession

    # worker Python của Spark cần import được `jobs` và `scamradar_core` (pytest chỉ thêm cho driver)
    root = Path(__file__).resolve().parents[2]
    paths = [str(root), str(root / "libs"), os.environ.get("PYTHONPATH", "")]
    os.environ["PYTHONPATH"] = os.pathsep.join(p for p in paths if p)

    session = (
        SparkSession.builder.master("local[2]")
        .appName("test_batch_silver")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", "4")
        .config("spark.default.parallelism", "2")
        .config("spark.ui.enabled", "false")
        .config("spark.driver.bindAddress", "127.0.0.1")
        .config("spark.driver.host", "127.0.0.1")
        .getOrCreate()
    )
    yield session
    session.stop()


@pytest.fixture(scope="session")
def norm():
    from jobs.batch_silver.normalize import default_normalizer

    return default_normalizer()


@pytest.fixture(scope="session")
def bronze(spark):
    from jobs.batch_silver.job import read_bronze_json

    return read_bronze_json(spark, str(FIXTURE)).cache()
