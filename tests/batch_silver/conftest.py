from pathlib import Path

import pytest

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "bronze_ct_certs.jsonl"

# Luật PSL tối thiểu cho fixture: không phụ thuộc file tải về hay mạng.
MINI_PSL = frozenset({"com", "net", "org", "vn", "com.vn", "net.vn", "xyz", "*.ck", "!www.ck"})


@pytest.fixture(scope="session")
def spark():
    from pyspark.sql import SparkSession

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
    from jobs.batch_silver.normalize import Normalizer, make_split, to_ascii

    return Normalizer(to_ascii=to_ascii, split=make_split(MINI_PSL))


@pytest.fixture(scope="session")
def bronze(spark):
    from jobs.batch_silver.job import read_bronze_json

    return read_bronze_json(spark, str(FIXTURE)).cache()
