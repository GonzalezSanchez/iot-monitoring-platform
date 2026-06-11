"""Unit tests for silver_wap.py — WAP validation and batch splitting.

Tests run with PySpark in local mode (no Databricks or Azure connection needed).
SparkSession is shared across the module via a module-scoped fixture.

Only validate_batch() is tested here — it contains all the business logic.
merge_good_records() and write_quarantine() require a live Delta catalog
and are covered by integration tests run after terraform apply.
"""

import pytest
from pyspark.sql import DataFrame, Row, SparkSession
from pyspark.sql.types import DoubleType, StringType, StructField, StructType, TimestampType

from jobs.silver_wap import VALID_SENSOR_TYPES, validate_batch

# Schema mirrors what bronze_autoloader.py writes to the Bronze Delta table
BRONZE_SCHEMA = StructType(
    [
        StructField("event_id", StringType(), True),
        StructField("room_id", StringType(), True),
        StructField("sensor_type", StringType(), True),
        StructField("value", DoubleType(), True),
        StructField("timestamp", StringType(), True),
        StructField("_source_file", StringType(), True),
        StructField("_ingestion_time", TimestampType(), True),
    ]
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def spark() -> SparkSession:
    return (
        SparkSession.builder.master("local[1]")
        .appName("test_silver_wap")
        .config("spark.sql.shuffle.partitions", "1")
        .getOrCreate()
    )


def _make_df(spark: SparkSession, rows: list[dict]) -> DataFrame:
    return spark.createDataFrame([Row(**r) for r in rows], schema=BRONZE_SCHEMA)


VALID_ROW = {
    "event_id": "550e8400-e29b-41d4-a716-446655440000",
    "room_id": "room_001",
    "sensor_type": "temperature",
    "value": 21.5,
    "timestamp": "2024-01-01T00:00:00+00:00",
    "_source_file": "abfss://bronze@acct.dfs.core.windows.net/year=2024/...",
    "_ingestion_time": None,
}

# ---------------------------------------------------------------------------
# Good records pass through
# ---------------------------------------------------------------------------


class TestValidBatchPassesThrough:
    def test_single_valid_row_goes_to_good(self, spark: SparkSession) -> None:
        df = _make_df(spark, [VALID_ROW])
        good, quarantine = validate_batch(df)
        assert good.count() == 1
        assert quarantine.count() == 0

    def test_all_sensor_types_are_accepted(self, spark: SparkSession) -> None:
        rows = [{**VALID_ROW, "sensor_type": t} for t in VALID_SENSOR_TYPES]
        df = _make_df(spark, rows)
        good, quarantine = validate_batch(df)
        assert good.count() == len(VALID_SENSOR_TYPES)
        assert quarantine.count() == 0

    def test_good_row_has_ts_column(self, spark: SparkSession) -> None:
        df = _make_df(spark, [VALID_ROW])
        good, _ = validate_batch(df)
        assert "ts" in good.columns

    def test_good_row_value_is_cast_to_double(self, spark: SparkSession) -> None:
        df = _make_df(spark, [{**VALID_ROW, "value": 21.0}])
        good, _ = validate_batch(df)
        assert dict(good.dtypes)["value"] == "double"


# ---------------------------------------------------------------------------
# Invalid records go to quarantine
# ---------------------------------------------------------------------------


class TestInvalidRowsGoToQuarantine:
    def test_null_event_id_is_quarantined(self, spark: SparkSession) -> None:
        row = {**VALID_ROW, "event_id": None}
        df = _make_df(spark, [row])
        good, quarantine = validate_batch(df)
        assert good.count() == 0
        assert quarantine.count() == 1

    def test_null_room_id_is_quarantined(self, spark: SparkSession) -> None:
        row = {**VALID_ROW, "room_id": None}
        df = _make_df(spark, [row])
        good, quarantine = validate_batch(df)
        assert good.count() == 0
        assert quarantine.count() == 1

    def test_empty_room_id_is_quarantined(self, spark: SparkSession) -> None:
        row = {**VALID_ROW, "room_id": ""}
        df = _make_df(spark, [row])
        good, quarantine = validate_batch(df)
        assert good.count() == 0
        assert quarantine.count() == 1

    def test_unknown_sensor_type_is_quarantined(self, spark: SparkSession) -> None:
        row = {**VALID_ROW, "sensor_type": "radiation"}
        df = _make_df(spark, [row])
        good, quarantine = validate_batch(df)
        assert good.count() == 0
        assert quarantine.count() == 1

    def test_null_value_is_quarantined(self, spark: SparkSession) -> None:
        row = {**VALID_ROW, "value": None}
        df = _make_df(spark, [row])
        good, quarantine = validate_batch(df)
        assert good.count() == 0
        assert quarantine.count() == 1

    def test_unparseable_timestamp_is_quarantined(self, spark: SparkSession) -> None:
        row = {**VALID_ROW, "timestamp": "not-a-timestamp"}
        df = _make_df(spark, [row])
        good, quarantine = validate_batch(df)
        assert good.count() == 0
        assert quarantine.count() == 1


# ---------------------------------------------------------------------------
# Mixed batch splits correctly
# ---------------------------------------------------------------------------


class TestMixedBatchSplit:
    def test_mixed_batch_splits_good_and_bad(self, spark: SparkSession) -> None:
        rows = [
            {**VALID_ROW, "room_id": "room_001"},
            {**VALID_ROW, "room_id": "room_002", "sensor_type": "co2", "value": 800.0},
            {**VALID_ROW, "room_id": ""},  # bad
            {**VALID_ROW, "sensor_type": "unknown"},  # bad
        ]
        df = _make_df(spark, rows)
        good, quarantine = validate_batch(df)
        assert good.count() == 2
        assert quarantine.count() == 2

    def test_pipeline_continues_when_all_quarantined(self, spark: SparkSession) -> None:
        rows = [
            {**VALID_ROW, "room_id": ""},
            {**VALID_ROW, "sensor_type": "unknown"},
        ]
        df = _make_df(spark, rows)
        good, quarantine = validate_batch(df)
        assert good.count() == 0
        assert quarantine.count() == 2

    def test_quarantine_preserves_all_original_fields(self, spark: SparkSession) -> None:
        row = {**VALID_ROW, "sensor_type": "radiation"}
        df = _make_df(spark, [row])
        _, quarantine = validate_batch(df)
        result = quarantine.collect()[0]
        assert result["event_id"] == VALID_ROW["event_id"]
        assert result["sensor_type"] == "radiation"

    def test_good_records_have_correct_columns(self, spark: SparkSession) -> None:
        df = _make_df(spark, [VALID_ROW])
        good, _ = validate_batch(df)
        expected = {
            "event_id",
            "room_id",
            "sensor_type",
            "value",
            "ts",
            "_source_file",
            "_ingestion_time",
        }
        assert set(good.columns) == expected
