"""
jobs/spatial.py — GeoPandas spatial analysis job for project 2b.

Reads anomalies and room locations from PostgreSQL, performs spatial
aggregation per building, and writes results to the spatial_insights table.

Spatial analysis (GeoPandas):
  - Joins anomalies with rooms on room_id to obtain building coordinates
  - Creates a GeoDataFrame with Point geometries (WGS84 / EPSG:4326)
  - Aggregates anomaly counts per building: total, high, medium, dominant type
  - Writes one row per building to spatial_insights for Power BI map visual

Note: this job is specific to project 2b. Project 2a exposes results via a
REST API and uses Power BI with the rooms table directly for map visualisation.
GeoPandas is used here because project 2b is a Data Engineering stack —
spatial analysis is a natural extension of the PySpark + Python pipeline.

Usage:
    python jobs/spatial.py
"""

import logging
import os
import sys
import uuid
from datetime import datetime

import geopandas as gpd
import pandas as pd
import psycopg2
import psycopg2.extensions
from dotenv import load_dotenv
from shapely.geometry import Point

from jobs.metrics import init_meter, shutdown

load_dotenv()

log = logging.getLogger(__name__)


def read_anomalies(conn: psycopg2.extensions.connection) -> pd.DataFrame:  # pragma: no cover
    """Read all anomalies from PostgreSQL."""
    sql = "SELECT job_id, entity_id AS room_id, anomaly_type, severity, detected_at FROM anomalies"
    return pd.read_sql(sql, conn)


def read_rooms(conn: psycopg2.extensions.connection) -> pd.DataFrame:  # pragma: no cover
    """Read room locations from PostgreSQL."""
    sql = "SELECT room_id, building_id, building_name, lat, lon FROM rooms"
    return pd.read_sql(sql, conn)


def write_insights(
    conn: psycopg2.extensions.connection, rows: list[dict]
) -> None:  # pragma: no cover
    """Insert spatial insight rows into PostgreSQL."""
    sql = """
        INSERT INTO spatial_insights
            (job_id, building_id, building_name, lat, lon,
             anomaly_count, high_count, medium_count, dominant_type,
             period_start, period_end)
        VALUES
            (%(job_id)s, %(building_id)s, %(building_name)s, %(lat)s, %(lon)s,
             %(anomaly_count)s, %(high_count)s, %(medium_count)s, %(dominant_type)s,
             %(period_start)s, %(period_end)s)
    """
    with conn.cursor() as cur:
        for row in rows:
            cur.execute(sql, row)
    conn.commit()


def build_geodataframe(anomalies: pd.DataFrame, rooms: pd.DataFrame) -> gpd.GeoDataFrame:
    """Join anomalies with rooms and create a GeoDataFrame with Point geometries."""
    merged = anomalies.merge(rooms, on="room_id", how="inner")
    geometry = [Point(lon, lat) for lon, lat in zip(merged["lon"], merged["lat"])]
    return gpd.GeoDataFrame(merged, geometry=geometry, crs="EPSG:4326")


def aggregate_by_building(gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    """Aggregate anomaly counts and dominant type per building."""
    agg = (
        gdf.groupby(["building_id", "building_name", "lat", "lon"])
        .agg(
            anomaly_count=("anomaly_type", "count"),
            high_count=("severity", lambda s: (s == "high").sum()),
            medium_count=("severity", lambda s: (s == "medium").sum()),
            dominant_type=("anomaly_type", lambda s: s.value_counts().idxmax()),
        )
        .reset_index()
    )
    return agg


def build_insight_rows(
    agg: pd.DataFrame,
    job_id: str,
    period_start: datetime,
    period_end: datetime,
) -> list[dict]:
    """Convert aggregated DataFrame to a list of dicts for PostgreSQL insert."""
    rows = []
    for _, row in agg.iterrows():
        rows.append(
            {
                "job_id": job_id,
                "building_id": row["building_id"],
                "building_name": row["building_name"],
                "lat": row["lat"],
                "lon": row["lon"],
                "anomaly_count": int(row["anomaly_count"]),
                "high_count": int(row["high_count"]),
                "medium_count": int(row["medium_count"]),
                "dominant_type": row["dominant_type"],
                "period_start": period_start,
                "period_end": period_end,
            }
        )
    return rows


def get_connection() -> psycopg2.extensions.connection:  # pragma: no cover
    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
    )


def main() -> None:  # pragma: no cover
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(levelname)s %(message)s",
    )

    missing = [v for v in ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD") if not os.getenv(v)]
    if missing:
        log.error("Missing required env vars: %s", ", ".join(missing))
        sys.exit(1)

    conn = get_connection()
    try:
        log.info("Reading anomalies and rooms from PostgreSQL...")
        anomalies = read_anomalies(conn)
        rooms = read_rooms(conn)

        if anomalies.empty:
            log.info("No anomalies found — nothing to analyse.")
            return

        log.info("Found %d anomalies across %d rooms", len(anomalies), rooms["room_id"].nunique())

        gdf = build_geodataframe(anomalies, rooms)
        agg = aggregate_by_building(gdf)

        period_start = anomalies["detected_at"].min()
        period_end = anomalies["detected_at"].max()
        job_id = str(uuid.uuid4())

        rows = build_insight_rows(agg, job_id, period_start, period_end)
        log.info("Writing %d spatial insight rows (one per building)...", len(rows))
        write_insights(conn, rows)
        log.info("Spatial analysis complete. job_id=%s", job_id)

        meter = init_meter("p2b.spatial")
        meter.create_counter("p2b.spatial.buildings_processed").add(len(rows))
        shutdown()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
