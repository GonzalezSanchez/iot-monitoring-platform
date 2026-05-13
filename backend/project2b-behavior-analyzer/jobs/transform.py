"""
jobs/transform.py — PySpark transform job for project 2b.

Reads raw Parquet from S3 (landing zone),
filters invalid sensor values (null, out of range),
renames columns to processed schema,
and writes cleaned Parquet to S3 processed layer.

Idempotent: dynamic partition overwrite — re-running overwrites
only the affected monthly partitions.

Usage:
    spark-submit --master local[*] jobs/transform.py
"""

import logging
import os
import sys

from dotenv import load_dotenv
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import col, month, year

load_dotenv()

log = logging.getLogger(__name__)

TEMP_MIN = -10.0
TEMP_MAX = 60.0
HUM_MIN = 0.0
HUM_MAX = 100.0


def validate_and_clean(df: DataFrame) -> DataFrame:
    """Filter rows with invalid sensor values and rename columns to processed schema."""
    return (
        df.filter(col("temperature").isNotNull() & col("temperature").between(TEMP_MIN, TEMP_MAX))
        .filter(col("humidity").isNotNull() & col("humidity").between(HUM_MIN, HUM_MAX))
        .withColumnRenamed("temperature", "temperature_c")
        .withColumnRenamed("humidity", "humidity_pct")
        .select(
            "event_id",
            "device_id",
            "room_id",
            "ts",
            "temperature_c",
            "humidity_pct",
            "motion",
            "occupancy",
        )
    )


def filter_unprocessed(df: DataFrame, processed_ids: set[str]) -> DataFrame:
    """Remove events already present in a processed dataset."""
    if not processed_ids:
        return df
    return df.filter(~df.event_id.isin(processed_ids))


def read_raw(spark: SparkSession, s3_path: str) -> DataFrame:  # pragma: no cover
    """Read raw Parquet from S3 landing zone."""
    return spark.read.parquet(s3_path)


def write_processed(df: DataFrame, s3_path: str) -> None:  # pragma: no cover
    """Write cleaned Parquet to S3 processed layer, partitioned by year/month.

    Dynamic partition overwrite ensures re-running only replaces
    the monthly partitions being written, not the entire prefix.
    """
    df.withColumn("year", year("ts")).withColumn("month", month("ts")).write.partitionBy(
        "year", "month"
    ).mode("overwrite").parquet(s3_path)


def build_spark(master: str) -> SparkSession:  # pragma: no cover
    return (
        SparkSession.builder.appName("project2b-transform")
        .master(master)
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.sources.partitionOverwriteMode", "dynamic")
        .getOrCreate()
    )


def main() -> None:  # pragma: no cover
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(levelname)s %(message)s",
    )

    s3_raw = os.getenv("S3_PARQUET_PATH")
    s3_processed = os.getenv("S3_PROCESSED_PATH")

    missing = [
        name
        for name, val in [("S3_PARQUET_PATH", s3_raw), ("S3_PROCESSED_PATH", s3_processed)]
        if not val
    ]
    if missing:
        log.error("Missing required env vars: %s", ", ".join(missing))
        sys.exit(1)

    assert s3_raw is not None
    assert s3_processed is not None

    master = os.getenv("SPARK_MASTER")
    if not master:
        log.error("Missing required env var: SPARK_MASTER")
        sys.exit(1)

    spark = build_spark(master)
    spark.sparkContext.setLogLevel("WARN")

    log.info("Reading raw Parquet from %s...", s3_raw)
    raw_df = read_raw(spark, s3_raw)
    raw_count = raw_df.count()
    log.info("Found %d raw rows", raw_count)

    if raw_count == 0:
        log.info("Nothing to transform.")
        spark.stop()
        return

    df = validate_and_clean(raw_df)
    new_count = df.count()

    if new_count == 0:
        log.info("No valid events after cleaning.")
        spark.stop()
        return

    log.info("Writing %d cleaned events to %s...", new_count, s3_processed)
    write_processed(df, s3_processed)
    log.info("Transform complete.")

    spark.stop()


if __name__ == "__main__":
    main()
