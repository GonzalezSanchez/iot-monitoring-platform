#!/usr/bin/env python3
"""
jobs/transform.py — PySpark transform job for project 2b.

Reads raw_sensor_data from PostgreSQL (JDBC),
filters invalid sensor values (null, out of range),
renames columns to processed schema,
and writes new rows to processed_sensor_data (PostgreSQL via JDBC).

Idempotent: event_ids already in processed_sensor_data are skipped.

Usage:
    spark-submit --master local[*] jobs/transform.py
"""

import logging
import os
import sys

from dotenv import load_dotenv
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import col

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
    """Remove events already present in processed_sensor_data."""
    if not processed_ids:
        return df
    return df.filter(~df.event_id.isin(processed_ids))


def get_processed_event_ids(spark: SparkSession, jdbc_url: str, properties: dict) -> set[str]:
    """Read event_ids already present in processed_sensor_data."""
    existing = spark.read.jdbc(
        jdbc_url,
        "(SELECT event_id FROM processed_sensor_data) t",
        properties=properties,
    )
    return {row.event_id for row in existing.collect()}


def read_raw(spark: SparkSession, jdbc_url: str, properties: dict) -> DataFrame:
    """Read all rows from raw_sensor_data."""
    return spark.read.jdbc(jdbc_url, "raw_sensor_data", properties=properties)


def write_processed(df: DataFrame, jdbc_url: str, properties: dict) -> None:
    """Append cleaned rows to processed_sensor_data via JDBC."""
    df.write.jdbc(jdbc_url, "processed_sensor_data", mode="append", properties=properties)


def build_spark(master: str) -> SparkSession:
    return (
        SparkSession.builder.appName("project2b-transform")
        .master(master)
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )


def main() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(levelname)s %(message)s",
    )

    missing = [v for v in ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD") if not os.getenv(v)]
    if missing:
        log.error("Missing required env vars: %s", ", ".join(missing))
        sys.exit(1)

    master = os.getenv("SPARK_MASTER", "local[*]")
    jdbc_url = (
        f"jdbc:postgresql://{os.environ['DB_HOST']}:"
        f"{os.getenv('DB_PORT', '5432')}/{os.environ['DB_NAME']}"
    )
    jdbc_props = {
        "user": os.environ["DB_USER"],
        "password": os.environ["DB_PASSWORD"],
        "driver": "org.postgresql.Driver",
    }

    spark = build_spark(master)
    spark.sparkContext.setLogLevel("WARN")

    log.info("Reading raw_sensor_data...")
    raw_df = read_raw(spark, jdbc_url, jdbc_props)
    raw_count = raw_df.count()
    log.info("Found %d raw rows", raw_count)

    if raw_count == 0:
        log.info("Nothing to transform.")
        spark.stop()
        return

    processed_ids = get_processed_event_ids(spark, jdbc_url, jdbc_props)
    if processed_ids:
        log.info("Skipping %d already-processed events", len(processed_ids))
    df = filter_unprocessed(raw_df, processed_ids)

    df = validate_and_clean(df)
    new_count = df.count()

    if new_count == 0:
        log.info("No new valid events to write.")
        spark.stop()
        return

    log.info("Writing %d events to processed_sensor_data...", new_count)
    write_processed(df, jdbc_url, jdbc_props)
    log.info("Transform complete.")

    spark.stop()


if __name__ == "__main__":
    main()
