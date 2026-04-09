"""
Analyze Lambda — project 2a Behavior Pattern Analyzer.

Reads validated rows from raw_sensor_data for the job window, detects
behavioral patterns and anomalies, and writes results to the patterns
and anomalies tables.

Patterns detected:
  - occupancy_schedule : typical occupied hours per room per weekday
  - temperature_trend  : rising/falling/stable mean temperature over the window

Anomalies detected:
  - temperature_spike  : reading > mean + 3*stddev
  - unusual_activity   : motion outside the typical occupancy window

Step Functions input (from Transform output):
{
    "job_id":            "uuid",
    "start_date":        "2026-01-01",
    "end_date":          "2026-01-07",
    "transformed_count": 138,
    "rejected_count":    4
}

Output:
{
    "job_id":          "uuid",
    "start_date":      "2026-01-01",
    "end_date":        "2026-01-07",
    "patterns_count":  12,
    "anomalies_count": 3
}
"""

import json
import logging
import os
import statistics
from collections import defaultdict
from datetime import datetime

from shared.db import get_connection

log = logging.getLogger(__name__)
log.setLevel(os.getenv("LOG_LEVEL", "INFO"))

SPIKE_STDDEV_THRESHOLD = 3.0


# ──────────────────────────────────────────────────────────────────────────────
# Data loading
# ──────────────────────────────────────────────────────────────────────────────


def _load_rows(conn, start_date: str, end_date: str) -> list[dict]:
    sql = """
        SELECT room_id, device_id, ts, temperature, humidity, motion, occupancy
        FROM   raw_sensor_data
        WHERE  ts BETWEEN %s AND %s
        ORDER  BY ts
    """
    with conn.cursor() as cur:
        cur.execute(sql, (f"{start_date}T00:00:00Z", f"{end_date}T23:59:59Z"))
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


# ──────────────────────────────────────────────────────────────────────────────
# Pattern detection
# ──────────────────────────────────────────────────────────────────────────────


def detect_occupancy_schedule(rows: list[dict]) -> list[dict]:
    """
    For each room: find which hours of the day typically have motion/occupancy.
    Returns one pattern record per room.
    """
    # room_id → weekday (0=Mon) → hour → count of occupied readings
    room_hours: dict[str, dict[int, dict[int, int]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(int))
    )

    for row in rows:
        if row.get("motion") or row.get("occupancy"):
            ts = row["ts"]
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            room_hours[row["room_id"]][ts.weekday()][ts.hour] += 1

    patterns = []
    for room_id, weekdays in room_hours.items():
        schedule = {}
        for weekday, hours in weekdays.items():
            # Keep hours that had at least 2 occupied readings
            active_hours = sorted(h for h, count in hours.items() if count >= 2)
            if active_hours:
                schedule[str(weekday)] = active_hours

        if schedule:
            patterns.append(
                {
                    "entity_type": "room",
                    "entity_id": room_id,
                    "pattern_type": "occupancy_schedule",
                    "data": json.dumps({"schedule": schedule}),
                }
            )

    return patterns


def detect_temperature_trend(rows: list[dict]) -> list[dict]:
    """
    For each room: compare mean temperature of first half vs second half of window.
    Labels trend as 'rising', 'falling', or 'stable' (threshold: 1 °C).
    """
    room_temps: dict[str, list[tuple[datetime, float]]] = defaultdict(list)

    for row in rows:
        if row.get("temperature") is not None:
            ts = row["ts"]
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            room_temps[row["room_id"]].append((ts, row["temperature"]))

    patterns = []
    for room_id, readings in room_temps.items():
        if len(readings) < 4:
            continue
        readings.sort(key=lambda x: x[0])
        mid = len(readings) // 2
        mean_first = statistics.mean(t for _, t in readings[:mid])
        mean_second = statistics.mean(t for _, t in readings[mid:])
        delta = mean_second - mean_first

        if delta > 1.0:
            trend = "rising"
        elif delta < -1.0:
            trend = "falling"
        else:
            trend = "stable"

        patterns.append(
            {
                "entity_type": "room",
                "entity_id": room_id,
                "pattern_type": "temperature_trend",
                "data": json.dumps(
                    {
                        "trend": trend,
                        "delta_celsius": round(delta, 2),
                        "mean_start": round(mean_first, 2),
                        "mean_end": round(mean_second, 2),
                    }
                ),
            }
        )

    return patterns


# ──────────────────────────────────────────────────────────────────────────────
# Anomaly detection
# ──────────────────────────────────────────────────────────────────────────────


def detect_temperature_spikes(rows: list[dict]) -> list[dict]:
    """Flag readings that are > mean + 3*stddev for that room."""
    room_temps: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        if row.get("temperature") is not None:
            room_temps[row["room_id"]].append(row["temperature"])

    # Pre-compute mean/stddev per room
    stats: dict[str, tuple[float, float]] = {}
    for room_id, temps in room_temps.items():
        if len(temps) >= 4:
            mean = statistics.mean(temps)
            stdev = statistics.stdev(temps)
            stats[room_id] = (mean, stdev)

    anomalies = []
    for row in rows:
        if row.get("temperature") is None:
            continue
        room = row["room_id"]
        if room not in stats:
            continue
        mean, stdev = stats[room]
        if stdev == 0:
            continue
        z = (row["temperature"] - mean) / stdev
        if abs(z) >= SPIKE_STDDEV_THRESHOLD:
            ts = row["ts"]
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            anomalies.append(
                {
                    "entity_type": "room",
                    "entity_id": room,
                    "anomaly_type": "temperature_spike",
                    "detected_at": ts.isoformat(),
                    "severity": "high" if abs(z) >= 5 else "medium",
                    "data": json.dumps(
                        {
                            "temperature": row["temperature"],
                            "mean": round(mean, 2),
                            "stdev": round(stdev, 2),
                            "z_score": round(z, 2),
                        }
                    ),
                }
            )

    return anomalies


def detect_unusual_activity(rows: list[dict], occupancy_patterns: list[dict]) -> list[dict]:
    """
    Flag motion detected outside the typical occupancy hours for a room.
    Requires occupancy_schedule patterns to already be computed.
    """
    # Build occupancy schedule lookup: room_id → set of (weekday, hour)
    schedule_lookup: dict[str, set[tuple[int, int]]] = {}
    for p in occupancy_patterns:
        if p["pattern_type"] == "occupancy_schedule":
            schedule = json.loads(p["data"]).get("schedule", {})
            occupied: set[tuple[int, int]] = set()
            for weekday_str, hours in schedule.items():
                for h in hours:
                    occupied.add((int(weekday_str), h))
            schedule_lookup[p["entity_id"]] = occupied

    anomalies = []
    for row in rows:
        if not row.get("motion"):
            continue
        room = row["room_id"]
        if room not in schedule_lookup:
            continue
        ts = row["ts"]
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if (ts.weekday(), ts.hour) not in schedule_lookup[room]:
            anomalies.append(
                {
                    "entity_type": "room",
                    "entity_id": room,
                    "anomaly_type": "unusual_activity",
                    "detected_at": ts.isoformat(),
                    "severity": "low",
                    "data": json.dumps(
                        {
                            "weekday": ts.weekday(),
                            "hour": ts.hour,
                            "device_id": row.get("device_id"),
                        }
                    ),
                }
            )

    return anomalies


# ──────────────────────────────────────────────────────────────────────────────
# DB writes
# ──────────────────────────────────────────────────────────────────────────────


def _insert_patterns(
    conn, job_id: str, start_date: str, end_date: str, patterns: list[dict]
) -> int:
    if not patterns:
        return 0
    sql = """
        INSERT INTO patterns
            (job_id, entity_type, entity_id, pattern_type, period_start, period_end, data)
        VALUES
            (%(job_id)s, %(entity_type)s, %(entity_id)s, %(pattern_type)s,
             %(period_start)s, %(period_end)s, %(data)s)
    """
    with conn.cursor() as cur:
        for p in patterns:
            cur.execute(
                sql,
                {
                    **p,
                    "job_id": job_id,
                    "period_start": f"{start_date}T00:00:00Z",
                    "period_end": f"{end_date}T23:59:59Z",
                },
            )
    conn.commit()
    return len(patterns)


def _insert_anomalies(conn, job_id: str, anomalies: list[dict]) -> int:
    if not anomalies:
        return 0
    sql = """
        INSERT INTO anomalies
            (job_id, entity_type, entity_id, anomaly_type, detected_at, severity, data)
        VALUES
            (%(job_id)s, %(entity_type)s, %(entity_id)s, %(anomaly_type)s,
             %(detected_at)s, %(severity)s, %(data)s)
    """
    with conn.cursor() as cur:
        for a in anomalies:
            cur.execute(sql, {**a, "job_id": job_id})
    conn.commit()
    return len(anomalies)


# ──────────────────────────────────────────────────────────────────────────────
# Handler
# ──────────────────────────────────────────────────────────────────────────────


def handler(event: dict, context) -> dict:
    job_id = event["job_id"]
    start_date = event["start_date"]
    end_date = event["end_date"]

    log.info("Analyze job_id=%s  window=%s → %s", job_id, start_date, end_date)

    conn = get_connection()
    try:
        rows = _load_rows(conn, start_date, end_date)
        log.info("Loaded %d rows for analysis", len(rows))

        occupancy_patterns = detect_occupancy_schedule(rows)
        temp_patterns = detect_temperature_trend(rows)
        all_patterns = occupancy_patterns + temp_patterns

        temp_anomalies = detect_temperature_spikes(rows)
        activity_anomalies = detect_unusual_activity(rows, occupancy_patterns)
        all_anomalies = temp_anomalies + activity_anomalies

        patterns_count = _insert_patterns(conn, job_id, start_date, end_date, all_patterns)
        anomalies_count = _insert_anomalies(conn, job_id, all_anomalies)
    finally:
        conn.close()

    log.info("Analyze complete: %d patterns, %d anomalies", patterns_count, anomalies_count)

    return {
        "job_id": job_id,
        "start_date": start_date,
        "end_date": end_date,
        "patterns_count": patterns_count,
        "anomalies_count": anomalies_count,
    }
