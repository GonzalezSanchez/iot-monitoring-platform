"""Unit tests for silver_wap.py — WAP validation, batch splitting, quarantine keying.

Tests run with PySpark in local mode (no Databricks or Azure connection needed).
SparkSession is shared across the module via a module-scoped fixture.

validate_batch() and add_quarantine_key() are the pure, testable business logic.
merge_good_records() and write_quarantine() themselves call DeltaTable.forName()
with a catalog-qualified name (catalog.schema.table) — Databricks Runtime resolves
that fine, but the open-source delta-spark package's forName() can't parse a
3-part identifier at all (confirmed: it raises ParseException even for the
default catalog, while spark.read.table() accepts the same name). So those two
functions can't be exercised locally; TestMergeIdempotency below proves the
underlying MERGE statements are idempotent against a locally-addressable table
instead of calling those two functions directly.
"""

from collections.abc import Generator

import pytest
from pyspark.sql import DataFrame, Row, SparkSession
from pyspark.sql.types import DoubleType, StringType, StructField, StructType, TimestampType

from jobs.silver_wap import (
    VALID_SENSOR_TYPES,
    add_quarantine_key,
    build_checkpoint_path,
    validate_batch,
)

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
def spark() -> Generator[SparkSession, None, None]:
    import shutil
    import tempfile

    from delta import configure_spark_with_delta_pip

    # Delta extensions are configured here (not in a second, separate fixture) because
    # they must be present on the JVM's classpath at SparkSession creation time — once
    # a session exists, a later .getOrCreate() silently reuses it without adding jars.
    warehouse_dir = tempfile.mkdtemp(prefix="p2c_test_warehouse_")
    builder = (
        SparkSession.builder.master("local[1]")
        .appName("test_silver_wap")
        .config("spark.sql.shuffle.partitions", "1")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog"
        )
        .config("spark.sql.warehouse.dir", warehouse_dir)
    )
    spark = configure_spark_with_delta_pip(builder).getOrCreate()
    yield spark
    spark.stop()
    shutil.rmtree(warehouse_dir, ignore_errors=True)


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


# ---------------------------------------------------------------------------
# Quarantine dedup key — makes re-running the job on the same batch idempotent
# ---------------------------------------------------------------------------


class TestQuarantineKey:
    def test_uses_event_id_when_present(self, spark: SparkSession) -> None:
        row = {**VALID_ROW, "sensor_type": "radiation"}
        df = _make_df(spark, [row])
        keyed = add_quarantine_key(df)
        assert keyed.collect()[0]["_quarantine_key"] == VALID_ROW["event_id"]

    def test_falls_back_to_content_hash_when_event_id_missing(self, spark: SparkSession) -> None:
        row = {**VALID_ROW, "event_id": None}
        df = _make_df(spark, [row])
        keyed = add_quarantine_key(df)
        key = keyed.collect()[0]["_quarantine_key"]
        assert key is not None
        assert key != VALID_ROW["event_id"]

    def test_same_bad_row_reread_twice_gets_the_same_key(self, spark: SparkSession) -> None:
        row = {**VALID_ROW, "event_id": None, "room_id": ""}
        df = _make_df(spark, [row, row])  # same bad row read on two separate runs
        keyed = add_quarantine_key(df)
        keys = [r["_quarantine_key"] for r in keyed.collect()]
        assert keys[0] == keys[1]

    def test_different_bad_rows_get_different_keys(self, spark: SparkSession) -> None:
        rows = [
            {**VALID_ROW, "event_id": None, "room_id": "room_001"},
            {**VALID_ROW, "event_id": None, "room_id": "room_002"},
        ]
        df = _make_df(spark, rows)
        keyed = add_quarantine_key(df)
        keys = {r["_quarantine_key"] for r in keyed.collect()}
        assert len(keys) == 2


# ---------------------------------------------------------------------------
# Streaming checkpoint path — tracks incremental progress across runs
# ---------------------------------------------------------------------------


class TestBuildCheckpointPath:
    def test_builds_abfss_path_under_checkpoints_root(self) -> None:
        path = build_checkpoint_path("stp2cdeviotags", "bronze")
        assert path == "abfss://bronze@stp2cdeviotags.dfs.core.windows.net/_checkpoints/silver_wap"

    def test_differs_from_bronze_autoloaders_own_checkpoint(self) -> None:
        # Two separate streams must not share a checkpoint, or Spark mixes up their progress.
        from jobs.bronze_autoloader import build_checkpoint_path as bronze_checkpoint_path

        silver_path = build_checkpoint_path("stp2cdeviotags", "bronze")
        bronze_path = bronze_checkpoint_path("stp2cdeviotags", "bronze")
        assert silver_path != bronze_path


# ---------------------------------------------------------------------------
# MERGE idempotency — replaying the same batch must never duplicate rows
# ---------------------------------------------------------------------------


class TestMergeIdempotency:
    """Proves the Silver MERGE pattern is idempotent against a real Delta table.

    merge_good_records()/write_quarantine() can't be called directly here (see the
    module docstring), so this test performs the identical MERGE statements they
    use — same whenNotMatchedInsertAll(), same keys (event_id / _quarantine_key) —
    against a local, 2-part-named Delta table built with the real add_quarantine_key().
    Uses the module's shared `spark` fixture: Delta's catalog classes must be on the
    JVM classpath from the very first SparkSession.getOrCreate() call in this process,
    so a second, separately-configured session here would just reuse the first one
    without picking up the Delta jars.
    """

    def _merge_good(self, spark: SparkSession, good_df: DataFrame) -> None:
        from delta.tables import DeltaTable

        (
            DeltaTable.forName(spark, "silver.sensor_events")
            .alias("t")
            .merge(good_df.alias("s"), "t.event_id = s.event_id")
            .whenNotMatchedInsertAll()
            .execute()
        )

    def _merge_quarantine(self, spark: SparkSession, quarantine_df: DataFrame) -> None:
        from delta.tables import DeltaTable

        keyed = add_quarantine_key(quarantine_df)
        (
            DeltaTable.forName(spark, "silver.sensor_events_quarantine")
            .alias("t")
            .merge(keyed.alias("s"), "t._quarantine_key = s._quarantine_key")
            .whenNotMatchedInsertAll()
            .execute()
        )

    def test_replaying_the_same_batch_twice_adds_no_new_rows(self, spark: SparkSession) -> None:
        spark.sql("CREATE SCHEMA IF NOT EXISTS silver")
        spark.sql("""
            CREATE TABLE IF NOT EXISTS silver.sensor_events (
                event_id STRING, room_id STRING, sensor_type STRING,
                value DOUBLE, ts TIMESTAMP, _source_file STRING, _ingestion_time TIMESTAMP
            ) USING DELTA
        """)
        spark.sql("""
            CREATE TABLE IF NOT EXISTS silver.sensor_events_quarantine (
                event_id STRING, room_id STRING, sensor_type STRING, value DOUBLE,
                ts TIMESTAMP, _source_file STRING, _ingestion_time TIMESTAMP,
                _quarantine_key STRING
            ) USING DELTA
        """)

        batch = [
            VALID_ROW,
            {**VALID_ROW, "event_id": None, "room_id": ""},  # lands in quarantine
        ]
        df = _make_df(spark, batch)
        good_df, quarantine_df = validate_batch(df)

        self._merge_good(spark, good_df)
        self._merge_quarantine(spark, quarantine_df)

        # Re-read the exact same Bronze rows a second time, as a re-run of the job would.
        df_replay = _make_df(spark, batch)
        good_replay, quarantine_replay = validate_batch(df_replay)
        self._merge_good(spark, good_replay)
        self._merge_quarantine(spark, quarantine_replay)

        assert spark.table("silver.sensor_events").count() == 1
        assert spark.table("silver.sensor_events_quarantine").count() == 1
