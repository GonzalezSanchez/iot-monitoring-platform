"""
jobs/extract.py — PySpark extract job for project 2b.

Reads all sensor events from DynamoDB (prod-SensorEvents)
and archives them as Parquet on S3 (raw landing zone),
partitioned by year/month.

Idempotent: dynamic partition overwrite — re-running overwrites
only the affected monthly partitions.

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
from pyspark.sql.functions import month, year
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


def scan_dynamodb(table_name: str, region: str) -> list[dict]:  # pragma: no cover
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


def _parse_ts(ts_str: str) -> datetime:
    """Parse ISO timestamp in either %Y-%m-%dT%H:%M:%SZ or full ISO format."""
    try:
        return datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError:
        return datetime.fromisoformat(ts_str).astimezone(UTC).replace(tzinfo=UTC)


def to_dataframe(spark: SparkSession, items: list[dict]) -> DataFrame:
    """Convert DynamoDB items to Spark DataFrame matching raw schema.

    Handles two event formats:
    - Seed format: JSON payload with all sensors per event (project 2b seed script)
    - Project 1b format: individual sensor readings (sensor_type + value per event)
    """
    rows = []
    for item in items:
        ts = _parse_ts(item["timestamp"])

        if "payload" in item:
            payload = json.loads(item["payload"])
            temp = payload.get("temperature")
            hum = payload.get("humidity")
            rows.append(
                (
                    item["event_id"],
                    item.get("device_id", item["room_id"]),
                    item["room_id"],
                    ts,
                    float(temp) if temp is not None else None,
                    float(hum) if hum is not None else None,
                    bool(payload.get("motion")),
                    bool(payload.get("occupancy")),
                    item["payload"],
                )
            )
        else:
            sensor_type = item.get("sensor_type", "")
            value = float(item["value"]) if "value" in item else None
            rows.append(
                (
                    item["event_id"],
                    item.get("device_id", item["room_id"]),
                    item["room_id"],
                    ts,
                    value if sensor_type == "temperature" else None,
                    value if sensor_type == "humidity" else None,
                    (value > 0) if sensor_type == "motion" and value is not None else False,
                    (value > 0) if sensor_type == "occupancy" and value is not None else False,
                    json.dumps({"sensor_type": sensor_type, "value": str(value)}),
                )
            )

    return spark.createDataFrame(rows, schema=RAW_SCHEMA)


def filter_new_events(df: DataFrame, existing_ids: set[str]) -> DataFrame:
    """Remove events already present in an existing dataset."""
    if not existing_ids:
        return df
    return df.filter(~df.event_id.isin(existing_ids))


def write_parquet(df: DataFrame, s3_path: str) -> None:  # pragma: no cover
    """Write DataFrame as Parquet to S3, partitioned by year and month.

    Dynamic partition overwrite ensures re-running only replaces
    the monthly partitions being written, not the entire prefix.
    """
    df.withColumn("year", year("ts")).withColumn("month", month("ts")).write.partitionBy(
        "year", "month"
    ).mode("overwrite").parquet(s3_path)


def build_spark(master: str) -> SparkSession:  # pragma: no cover
    return (
        SparkSession.builder.appName("project2b-extract")
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

    s3_path = os.getenv("S3_PARQUET_PATH")
    if not s3_path:
        log.error("Missing required env var: S3_PARQUET_PATH")
        sys.exit(1)

    table_name = os.getenv("DYNAMODB_TABLE")
    region = os.getenv("AWS_REGION")
    master = os.getenv("SPARK_MASTER")

    missing = [
        name
        for name, val in [
            ("DYNAMODB_TABLE", table_name),
            ("AWS_REGION", region),
            ("SPARK_MASTER", master),
        ]
        if not val
    ]
    if missing:
        log.error("Missing required env vars: %s", ", ".join(missing))
        sys.exit(1)

    assert table_name is not None
    assert region is not None
    assert master is not None

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
    count = df.count()

    log.info("Writing %d events to S3: %s", count, s3_path)
    write_parquet(df, s3_path)
    log.info("Extract complete.")

    spark.stop()


if __name__ == "__main__":
    main()
