#!/usr/bin/env python3
"""
scripts/manage_partitions.py

Creates monthly range partitions for raw_sensor_data for the next N months.
Idempotent (CREATE TABLE IF NOT EXISTS). Safe to run multiple times.

Usage:
    python scripts/manage_partitions.py --months-ahead 3
    python scripts/manage_partitions.py --months-ahead 3 --dry-run
"""

import argparse
import logging
import os
import sys

import psycopg2
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)


def partition_bounds(year: int, month: int) -> tuple[str, str]:
    """Return (from_date, to_date) for a monthly partition."""
    from_date = f"{year}-{month:02d}-01"
    to_year, to_month = (year + 1, 1) if month == 12 else (year, month + 1)
    to_date = f"{to_year}-{to_month:02d}-01"
    return from_date, to_date


def partition_sql(year: int, month: int) -> str:
    from_date, to_date = partition_bounds(year, month)
    name = f"raw_sensor_data_{year}_{month:02d}"
    return (
        f"CREATE TABLE IF NOT EXISTS {name}\n"
        f"    PARTITION OF raw_sensor_data\n"
        f"    FOR VALUES FROM ('{from_date}') TO ('{to_date}');"
    )


def months_ahead(start_year: int, start_month: int, n: int):
    """Yield (year, month) tuples for n months starting from start_year/month."""
    year, month = start_year, start_month
    for _ in range(n):
        yield year, month
        month += 1
        if month > 12:
            month, year = 1, year + 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Create monthly partitions for raw_sensor_data")
    parser.add_argument("--months-ahead", type=int, default=3, help="Number of months to create")
    parser.add_argument("--dry-run", action="store_true", help="Print SQL without executing")
    args = parser.parse_args()

    from datetime import datetime

    now = datetime.now()

    if args.dry_run:
        for year, month in months_ahead(now.year, now.month, args.months_ahead):
            print(partition_sql(year, month))
        return

    missing = [v for v in ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD") if not os.getenv(v)]
    if missing:
        log.error("Missing required env vars: %s", ", ".join(missing))
        sys.exit(1)

    conn = psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
    )

    try:
        with conn:
            with conn.cursor() as cur:
                for year, month in months_ahead(now.year, now.month, args.months_ahead):
                    sql = partition_sql(year, month)
                    cur.execute(sql)
                    log.info("Partition ready: raw_sensor_data_%d_%02d", year, month)
    finally:
        conn.close()

    log.info("Done — %d partition(s) ensured", args.months_ahead)


if __name__ == "__main__":
    main()
