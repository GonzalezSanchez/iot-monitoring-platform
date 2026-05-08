#!/usr/bin/env python3
"""
jobs/extract.py — PySpark extract job for project 2b.

Reads sensor events from DynamoDB (prod-SensorEvents),
archives them as Parquet on S3,
and loads new events into raw_sensor_data (PostgreSQL via JDBC).

Idempotent: existing event_ids are skipped before writing.

Usage:
    spark-submit --master local[*] jobs/extract.py
"""

import json
import logging
import os
import sys
from datetime import UTC, datetime

import boto3
from dotenv import load_dotenv
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.types import (
    BooleanType,
    DoubleType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

load_dotenv()

log = logging.getLogger(__name__)

RAW_SCHEMA = StructType(
    [
        StructField("event_id", StringType(), False),
        StructField("device_id", StringType(), False),
        StructField("room_id", StringType(), False),
        StructField("ts", TimestampType(), False),
        StructField("temperature", DoubleType(), True),
        StructField("humidity", DoubleType(), True),
        StructField("motion", BooleanType(), True),
        StructField("occupancy", BooleanType(), True),
        StructField("raw_payload", StringType(), False),
    ]
)


def scan_dynamodb(table_name: str, region: str) -> list[dict]:
    """Scan all items from DynamoDB table, handling pagination."""
    dynamodb = boto3.resource("dynamodb", region_name=region)
    table = dynamodb.Table(table_name)

    items: list[dict] = []
    response = table.scan()
    items.extend(response["Items"])

    while "LastEvaluatedKey" in response:
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        items.extend(response["Items"])

    return items


def to_dataframe(spark: SparkSession, items: list[dict]) -> DataFrame:
    """Convert DynamoDB items to Spark DataFrame matching raw_sensor_data schema."""
    rows = []
    for item in items:
        payload = json.loads(item["payload"])
        ts = datetime.strptime(item["timestamp"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)

        temp = payload.get("temperature")
        hum = payload.get("humidity")

        rows.append(
            (
                item["event_id"],
                item["device_id"],
                item["room_id"],
                ts,
                float(temp) if temp is not None else None,
                float(hum) if hum is not None else None,
                bool(payload.get("motion")),
                bool(payload.get("occupancy")),
                item["payload"],
            )
        )

    return spark.createDataFrame(rows, schema=RAW_SCHEMA)


def filter_new_events(df: DataFrame, existing_ids: set[str]) -> DataFrame:
    """Remove already-loaded events to ensure idempotent writes."""
    if not existing_ids:
        return df
    return df.filter(~df.event_id.isin(existing_ids))


def get_existing_event_ids(spark: SparkSession, jdbc_url: str, properties: dict) -> set[str]:
    """Read event_ids already present in raw_sensor_data."""
    existing = spark.read.jdbc(
        jdbc_url,
        "(SELECT event_id FROM raw_sensor_data) t",
        properties=properties,
    )
    return {row.event_id for row in existing.collect()}


def write_parquet(df: DataFrame, s3_path: str) -> None:
    """Write DataFrame as Parquet to S3, partitioned by year and month."""
    from pyspark.sql.functions import month, year

    df.withColumn("year", year("ts")).withColumn("month", month("ts")).write.partitionBy(
        "year", "month"
    ).mode("append").parquet(s3_path)


def write_jdbc(df: DataFrame, jdbc_url: str, table: str, properties: dict) -> None:
    """Append DataFrame to PostgreSQL table via JDBC."""
    df.write.jdbc(jdbc_url, table, mode="append", properties=properties)


def build_spark(master: str) -> SparkSession:
    return (
        SparkSession.builder.appName("project2b-extract")
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

    table_name = os.getenv("DYNAMODB_TABLE", "prod-SensorEvents")
    region = os.getenv("AWS_DEFAULT_REGION", "eu-central-1")
    s3_path = os.getenv("S3_PARQUET_PATH")
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

    log.info("Scanning DynamoDB table '%s' in %s...", table_name, region)
    items = scan_dynamodb(table_name, region)
    log.info("Found %d items in DynamoDB", len(items))

    if not items:
        log.info("Nothing to load.")
        spark.stop()
        return

    df = to_dataframe(spark, items)

    existing_ids = get_existing_event_ids(spark, jdbc_url, jdbc_props)
    if existing_ids:
        log.info("Skipping %d already-loaded events", len(existing_ids))
    df = filter_new_events(df, existing_ids)

    new_count = df.count()
    if new_count == 0:
        log.info("No new events to load.")
        spark.stop()
        return

    if s3_path:
        log.info("Writing %d events to S3: %s", new_count, s3_path)
        write_parquet(df, s3_path)

    log.info("Writing %d events to raw_sensor_data...", new_count)
    write_jdbc(df, jdbc_url, "raw_sensor_data", jdbc_props)
    log.info("Extract complete.")

    spark.stop()


if __name__ == "__main__":
    main()
