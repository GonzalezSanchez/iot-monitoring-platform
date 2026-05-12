#!/usr/bin/env python3
"""
jobs/analyze.py — PySpark analyze job for project 2b.

Reads processed Parquet from S3 (processed layer) and detects:
  - occupancy_schedule : hourly occupancy rate per room via window aggregation
  - temperature_trend  : direction (rising/falling/stable) via regr_slope (linear regression)
  - temperature anomalies: z-score per room (population stddev); min 4 measurements;
                           z >= 3 → medium, z >= 5 → high

Writes results to patterns and anomalies tables in PostgreSQL.

Usage:
    spark-submit --master local[*] jobs/analyze.py
"""

import logging
import os
import sys
import uuid
from datetime import datetime

from dotenv import load_dotenv
from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql.functions import (
    avg,
    col,
    collect_list,
    count,
    dayofweek,
    hour,
    lit,
    regr_slope,
    stddev_pop,
    struct,
    to_json,
    when,
)
from pyspark.sql.functions import (
    max as spark_max,
)
from pyspark.sql.functions import (
    min as spark_min,
)
from pyspark.sql.types import DoubleType

load_dotenv()

log = logging.getLogger(__name__)

MIN_MEASUREMENTS = 4
Z_MEDIUM = 3.0
Z_HIGH = 5.0
# 1 °C per day expressed in °C/second (slope unit from ts cast to unix seconds)
SLOPE_THRESHOLD = 1.0 / 86400


def compute_hourly_occupancy(df: DataFrame) -> DataFrame:
    """Compute average occupancy rate per (room_id, day_of_week, hour)."""
    return (
        df.withColumn("hour", hour("ts"))
        .withColumn("day_of_week", dayofweek("ts"))
        .groupBy("room_id", "day_of_week", "hour")
        .agg(avg(col("occupancy").cast(DoubleType())).alias("occupancy_rate"))
    )


def compute_temperature_trends(df: DataFrame) -> DataFrame:
    """Compute linear temperature trend slope per room using Spark SQL regr_slope.

    regr_slope(y, x) is equivalent to MLlib LinearRegression for simple univariate
    regression and is more efficient for per-group computation in Spark SQL.
    """
    return (
        df.groupBy("room_id")
        .agg(
            regr_slope(col("temperature_c"), col("ts").cast("long")).alias("slope"),
            spark_min("ts").alias("period_start"),
            spark_max("ts").alias("period_end"),
        )
        .filter(col("slope").isNotNull())
    )


def build_occupancy_pattern_rows(
    hourly_df: DataFrame,
    job_id: str,
    period_start: datetime,
    period_end: datetime,
) -> DataFrame:
    """Aggregate hourly occupancy into one pattern row per room."""
    return (
        hourly_df.groupBy("room_id")
        .agg(collect_list(struct("day_of_week", "hour", "occupancy_rate")).alias("schedule"))
        .select(
            lit(job_id).alias("job_id"),
            lit("room").alias("entity_type"),
            col("room_id").alias("entity_id"),
            lit("occupancy_schedule").alias("pattern_type"),
            lit(period_start).cast("timestamp").alias("period_start"),
            lit(period_end).cast("timestamp").alias("period_end"),
            to_json(col("schedule")).alias("data"),
        )
    )


def build_trend_pattern_rows(trend_df: DataFrame, job_id: str) -> DataFrame:
    """Classify each room's temperature slope as rising/falling/stable."""
    return trend_df.select(
        lit(job_id).alias("job_id"),
        lit("room").alias("entity_type"),
        col("room_id").alias("entity_id"),
        lit("temperature_trend").alias("pattern_type"),
        col("period_start"),
        col("period_end"),
        to_json(
            struct(
                col("slope"),
                when(col("slope") > SLOPE_THRESHOLD, lit("rising"))
                .when(col("slope") < -SLOPE_THRESHOLD, lit("falling"))
                .otherwise(lit("stable"))
                .alias("direction"),
            )
        ).alias("data"),
    )


def detect_temperature_anomalies(df: DataFrame, job_id: str) -> DataFrame:
    """Detect temperature anomalies per room using z-score over population stddev.

    Rooms with fewer than MIN_MEASUREMENTS readings or zero stddev are skipped.
    z >= Z_MEDIUM (3) → severity 'medium'
    z >= Z_HIGH  (5) → severity 'high'
    """
    window = Window.partitionBy("room_id")

    return (
        df.withColumn("room_count", count("temperature_c").over(window))
        .withColumn("room_mean", avg("temperature_c").over(window))
        .withColumn("room_stddev", stddev_pop("temperature_c").over(window))
        .filter(col("room_count") >= MIN_MEASUREMENTS)
        .filter(col("room_stddev") > 0)
        .withColumn(
            "z_score",
            (col("temperature_c") - col("room_mean")) / col("room_stddev"),
        )
        .filter(col("z_score") >= Z_MEDIUM)
        .select(
            lit(job_id).alias("job_id"),
            lit("room").alias("entity_type"),
            col("room_id").alias("entity_id"),
            lit("temperature").alias("anomaly_type"),
            col("ts").alias("detected_at"),
            when(col("z_score") >= Z_HIGH, lit("high")).otherwise(lit("medium")).alias("severity"),
            to_json(
                struct(
                    col("event_id"),
                    col("temperature_c"),
                    col("z_score"),
                    col("room_mean"),
                    col("room_stddev"),
                )
            ).alias("data"),
        )
    )


def read_processed(spark: SparkSession, s3_path: str) -> DataFrame:  # pragma: no cover
    """Read processed Parquet from S3."""
    return spark.read.parquet(s3_path)


def write_patterns(df: DataFrame, jdbc_url: str, properties: dict) -> None:  # pragma: no cover
    """Append pattern rows to patterns table via JDBC."""
    df.write.jdbc(jdbc_url, "patterns", mode="append", properties=properties)


def write_anomalies(df: DataFrame, jdbc_url: str, properties: dict) -> None:  # pragma: no cover
    """Append anomaly rows to anomalies table via JDBC."""
    df.write.jdbc(jdbc_url, "anomalies", mode="append", properties=properties)


def build_spark(master: str) -> SparkSession:  # pragma: no cover
    return (
        SparkSession.builder.appName("project2b-analyze")
        .master(master)
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )


def main() -> None:  # pragma: no cover
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(levelname)s %(message)s",
    )

    s3_processed = os.getenv("S3_PROCESSED_PATH")
    missing_s3 = not s3_processed
    missing_db = [v for v in ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD") if not os.getenv(v)]

    if missing_s3:
        log.error("Missing required env var: S3_PROCESSED_PATH")
    if missing_db:
        log.error("Missing required env vars: %s", ", ".join(missing_db))
    if missing_s3 or missing_db:
        sys.exit(1)

    assert s3_processed is not None

    master = os.getenv("SPARK_MASTER", "local[*]")
    jdbc_url = (
        f"jdbc:postgresql://{os.environ['DB_HOST']}:"
        f"{os.getenv('DB_PORT', '5432')}/{os.environ['DB_NAME']}"
    )
    jdbc_props = {
        "user": os.environ["DB_USER"],
        "password": os.environ["DB_PASSWORD"],
        "driver": "org.postgresql.Driver",
        "stringtype": "unspecified",  # allow PostgreSQL to coerce varchar → jsonb
    }

    spark = build_spark(master)
    spark.sparkContext.setLogLevel("WARN")

    log.info("Reading processed Parquet from %s...", s3_processed)
    df = read_processed(spark, s3_processed)
    row_count = df.count()
    log.info("Found %d processed rows", row_count)

    if row_count == 0:
        log.info("Nothing to analyze.")
        spark.stop()
        return

    job_id = str(uuid.uuid4())
    period_start = df.agg(spark_min("ts")).collect()[0][0]
    period_end = df.agg(spark_max("ts")).collect()[0][0]

    # Occupancy schedule
    hourly_df = compute_hourly_occupancy(df)
    occupancy_patterns = build_occupancy_pattern_rows(hourly_df, job_id, period_start, period_end)
    log.info("Writing %d occupancy pattern rows...", occupancy_patterns.count())
    write_patterns(occupancy_patterns, jdbc_url, jdbc_props)

    # Temperature trend
    trend_df = compute_temperature_trends(df)
    trend_patterns = build_trend_pattern_rows(trend_df, job_id)
    log.info("Writing %d temperature trend rows...", trend_patterns.count())
    write_patterns(trend_patterns, jdbc_url, jdbc_props)

    # Anomaly detection
    anomalies_df = detect_temperature_anomalies(df, job_id)
    anomaly_count = anomalies_df.count()
    log.info("Writing %d anomalies...", anomaly_count)
    if anomaly_count > 0:
        write_anomalies(anomalies_df, jdbc_url, jdbc_props)

    log.info("Analyze complete. job_id=%s", job_id)
    spark.stop()


if __name__ == "__main__":
    main()
