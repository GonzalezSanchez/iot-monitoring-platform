"""Silver WAP job: Bronze Delta table → Silver using Write-Audit-Publish pattern.

Pipeline position:
    {catalog}.bronze.sensor_events
        ↓  schema enforcement + WAP validation
    {catalog}.silver.sensor_events            (good records — MERGE INTO on event_id)
    {catalog}.silver.sensor_events_quarantine (bad records — append, never deleted)

WAP = Write → Audit → Publish:
    Write:   read batch from Bronze
    Audit:   validate each row (null checks, sensor_type whitelist, value non-null)
    Publish: good → Silver via MERGE INTO (idempotent), bad → quarantine via append

MERGE INTO on event_id makes the job safe to re-run on the same batch without duplicates.

Environment variables:
    DATABRICKS_CATALOG -- defaults to "p2c_dev"
"""

import logging
import os

from dotenv import load_dotenv
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

load_dotenv()

_run_id = os.environ.get("DATABRICKS_JOB_RUN_ID", "local")
logging.basicConfig(
    level=logging.INFO,
    format=f"%(asctime)s [%(levelname)s] run_id={_run_id} %(name)s: %(message)s",
)
log = logging.getLogger(__name__)

VALID_SENSOR_TYPES = frozenset({"temperature", "co2", "occupancy", "humidity"})


def ensure_tables(spark: SparkSession, catalog: str) -> None:
    """Create Silver tables if they don't exist — idempotent DDL.

    CLUSTER BY (room_id, sensor_type): Liquid Clustering for efficient filtered queries.
    Declared at creation so Delta manages file layout automatically.
    """
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {catalog}.silver.sensor_events (
            event_id        STRING    NOT NULL,
            room_id         STRING    NOT NULL,
            sensor_type     STRING    NOT NULL,
            value           DOUBLE    NOT NULL,
            ts              TIMESTAMP NOT NULL,
            _source_file    STRING,
            _ingestion_time TIMESTAMP
        )
        USING DELTA
        CLUSTER BY (room_id, sensor_type)
    """)
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {catalog}.silver.sensor_events_quarantine (
            event_id        STRING,
            room_id         STRING,
            sensor_type     STRING,
            value           DOUBLE,
            ts              TIMESTAMP,
            _source_file    STRING,
            _ingestion_time TIMESTAMP
        )
        USING DELTA
    """)


def validate_batch(df: DataFrame) -> tuple[DataFrame, DataFrame]:
    """Split a Bronze DataFrame into (good, quarantine).

    Also casts timestamp STRING → TIMESTAMP (ts) so Silver schema is clean.
    Pure PySpark — no Delta or Azure connection needed, fully unit-testable.

    Returns:
        good:       rows that pass all WAP rules, cast and ready for Silver
        quarantine: rows that fail one or more rules, kept intact for review
    """
    df = df.withColumn("ts", F.to_timestamp(F.col("timestamp")))

    is_valid = (
        F.col("event_id").isNotNull()
        & F.col("room_id").isNotNull()
        & (F.length(F.col("room_id")) > 0)
        & F.col("sensor_type").isNotNull()
        & F.col("sensor_type").isin(list(VALID_SENSOR_TYPES))
        & F.col("value").isNotNull()
        & F.col("ts").isNotNull()
    )

    good = df.filter(is_valid).select(
        "event_id",
        "room_id",
        "sensor_type",
        F.col("value").cast("double"),
        "ts",
        "_source_file",
        "_ingestion_time",
    )
    quarantine = df.filter(~is_valid)
    return good, quarantine


def merge_good_records(spark: SparkSession, df: DataFrame, catalog: str) -> int:
    """Merge good records into silver.sensor_events — idempotent on event_id."""
    from delta.tables import DeltaTable

    target = f"{catalog}.silver.sensor_events"
    count = int(df.count())
    if count == 0:
        log.info("No good records to merge | target=%s", target)
        return 0

    (
        DeltaTable.forName(spark, target)
        .alias("t")
        .merge(df.alias("s"), "t.event_id = s.event_id")
        .whenNotMatchedInsertAll()
        .execute()
    )
    log.info("Merged %d good records | target=%s", count, target)
    return count


def write_quarantine(df: DataFrame, catalog: str) -> int:
    """Append bad records to quarantine — never overwrite, never delete."""
    target = f"{catalog}.silver.sensor_events_quarantine"
    count = int(df.count())
    if count == 0:
        log.info("No quarantine records | target=%s", target)
        return 0

    df.write.format("delta").mode("append").saveAsTable(target)
    log.info("Appended %d quarantine records | target=%s", count, target)
    return count


def run(spark: SparkSession, catalog: str) -> None:
    bronze_table = f"{catalog}.bronze.sensor_events"
    log.info("Silver WAP start | source=%s | catalog=%s", bronze_table, catalog)

    ensure_tables(spark, catalog)

    bronze_df = spark.read.table(bronze_table)
    good_df, quarantine_df = validate_batch(bronze_df)

    good_count = merge_good_records(spark, good_df, catalog)
    bad_count = write_quarantine(quarantine_df, catalog)

    total = good_count + bad_count
    pct_good = round(good_count / total * 100, 1) if total > 0 else 0.0
    log.info(
        "Silver WAP done | good=%d | quarantine=%d | total=%d | quality=%.1f%%",
        good_count,
        bad_count,
        total,
        pct_good,
    )


def main() -> None:
    catalog = os.environ.get("DATABRICKS_CATALOG", "p2c_dev")
    spark = SparkSession.builder.getOrCreate()
    run(spark, catalog)


if __name__ == "__main__":
    main()
