"""Silver WAP job: Bronze Delta table → Silver using Write-Audit-Publish pattern.

Pipeline position:
    {catalog}.bronze.sensor_events
        ↓  schema enforcement + WAP validation
    {catalog}.silver.sensor_events            (good records — MERGE INTO on event_id)
    {catalog}.silver.sensor_events_quarantine (bad records — MERGE INTO on _quarantine_key,
                                                never deleted)

WAP = Write → Audit → Publish:
    Write:   read batch from Bronze
    Audit:   validate each row (null checks, sensor_type whitelist, value non-null)
    Publish: good → Silver via MERGE INTO (idempotent), bad → quarantine via MERGE INTO (idempotent)

Both MERGEs are insert-only (whenNotMatchedInsertAll), keyed on event_id for good records.
Quarantine records often lack a usable event_id (that's frequently *why* they're bad), so
they're keyed on a hash of their content instead — see add_quarantine_key(). Either way,
re-running the job on the same Bronze batch never produces duplicates.

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


def ensure_tables(spark: SparkSession, catalog: str) -> None:  # pragma: no cover
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
            event_id         STRING,
            room_id          STRING,
            sensor_type      STRING,
            value            DOUBLE,
            ts               TIMESTAMP,
            _source_file     STRING,
            _ingestion_time  TIMESTAMP,
            _quarantine_key  STRING
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


def add_quarantine_key(df: DataFrame) -> DataFrame:
    """Add a deterministic dedup key for quarantine records.

    Bad records often lack a usable event_id (missing/null event_id is itself
    one of the quarantine reasons), so event_id alone can't key the MERGE the
    way it does for good records. Falls back to a hash of the row's own
    content — the same bad row read again on a re-run hashes to the same key,
    so the MERGE below stays insert-only without duplicating it.

    Pure PySpark — no Delta or Azure connection needed, fully unit-testable.
    """
    row_hash = F.sha2(
        F.concat_ws(
            "||",
            F.coalesce(F.col("room_id"), F.lit("")),
            F.coalesce(F.col("sensor_type"), F.lit("")),
            F.coalesce(F.col("value").cast("string"), F.lit("")),
            F.coalesce(F.col("timestamp"), F.lit("")),
            F.coalesce(F.col("_source_file"), F.lit("")),
        ),
        256,
    )
    return df.withColumn("_quarantine_key", F.coalesce(F.col("event_id"), row_hash))


def merge_good_records(spark: SparkSession, df: DataFrame, catalog: str) -> int:  # pragma: no cover
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


def write_quarantine(spark: SparkSession, df: DataFrame, catalog: str) -> int:  # pragma: no cover
    """Merge bad records into quarantine — idempotent on _quarantine_key, never overwrite/delete."""
    from delta.tables import DeltaTable

    target = f"{catalog}.silver.sensor_events_quarantine"
    count = int(df.count())
    if count == 0:
        log.info("No quarantine records | target=%s", target)
        return 0

    keyed = add_quarantine_key(df)
    (
        DeltaTable.forName(spark, target)
        .alias("t")
        .merge(keyed.alias("s"), "t._quarantine_key = s._quarantine_key")
        .whenNotMatchedInsertAll()
        .execute()
    )
    log.info("Merged %d quarantine records | target=%s", count, target)
    return count


def run(spark: SparkSession, catalog: str) -> None:  # pragma: no cover
    bronze_table = f"{catalog}.bronze.sensor_events"
    log.info("Silver WAP start | source=%s | catalog=%s", bronze_table, catalog)

    ensure_tables(spark, catalog)

    bronze_df = spark.read.table(bronze_table)
    good_df, quarantine_df = validate_batch(bronze_df)

    good_count = merge_good_records(spark, good_df, catalog)
    bad_count = write_quarantine(spark, quarantine_df, catalog)

    total = good_count + bad_count
    pct_good = round(good_count / total * 100, 1) if total > 0 else 0.0
    log.info(
        "Silver WAP done | good=%d | quarantine=%d | total=%d | quality=%.1f%%",
        good_count,
        bad_count,
        total,
        pct_good,
    )


def main() -> None:  # pragma: no cover
    catalog = os.environ.get("DATABRICKS_CATALOG", "p2c_dev")
    spark = SparkSession.builder.getOrCreate()
    run(spark, catalog)


if __name__ == "__main__":
    main()
