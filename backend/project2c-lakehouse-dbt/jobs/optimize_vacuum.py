"""OPTIMIZE + VACUUM job: maintenance tasks for Silver Delta tables.

Pipeline position: runs after silver_wap.py as a separate task in the Databricks Job.

    OPTIMIZE: merges small Delta files into larger ones — solves the small files problem
              that builds up after frequent incremental writes (MERGE INTO).
    VACUUM:   removes old file versions no longer reachable via Delta log.
              168h retention = 7 days of time travel preserved.
              Does NOT delete current data — only stale historical file versions.

Runs on both silver tables:
    {catalog}.silver.sensor_events
    {catalog}.silver.sensor_events_quarantine

Environment variables:
    DATABRICKS_CATALOG      -- defaults to "p2c_dev"
    DATABRICKS_JOB_RUN_ID   -- injected automatically by Databricks Jobs at runtime
"""

import logging
import os
import time

from dotenv import load_dotenv
from pyspark.sql import SparkSession

load_dotenv()

_run_id = os.environ.get("DATABRICKS_JOB_RUN_ID", "local")
logging.basicConfig(
    level=logging.INFO,
    format=f"%(asctime)s [%(levelname)s] run_id={_run_id} %(name)s: %(message)s",
)
log = logging.getLogger(__name__)

VACUUM_RETENTION_HOURS = 168  # 7 days — minimum for safe time travel


def optimize(spark: SparkSession, table: str) -> None:
    log.info("OPTIMIZE start | table=%s", table)
    t0 = time.monotonic()
    spark.sql(f"OPTIMIZE {table}")
    log.info("OPTIMIZE done | table=%s | elapsed=%.1fs", table, time.monotonic() - t0)


def vacuum(spark: SparkSession, table: str, retention_hours: int = VACUUM_RETENTION_HOURS) -> None:
    log.info("VACUUM start | table=%s | retain=%dh", table, retention_hours)
    t0 = time.monotonic()
    spark.sql(f"VACUUM {table} RETAIN {retention_hours} HOURS")
    log.info("VACUUM done | table=%s | elapsed=%.1fs", table, time.monotonic() - t0)


def run(spark: SparkSession, catalog: str) -> None:
    tables = [
        f"{catalog}.silver.sensor_events",
        f"{catalog}.silver.sensor_events_quarantine",
    ]

    log.info("Maintenance start | catalog=%s | tables=%s", catalog, tables)

    for table in tables:
        optimize(spark, table)
        vacuum(spark, table)

    log.info("Maintenance done | catalog=%s", catalog)


def main() -> None:
    catalog = os.environ.get("DATABRICKS_CATALOG", "p2c_dev")
    spark = SparkSession.builder.getOrCreate()
    run(spark, catalog)


if __name__ == "__main__":
    main()
