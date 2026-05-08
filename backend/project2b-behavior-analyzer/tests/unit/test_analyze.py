import json
import os
import sys
from datetime import UTC, datetime

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from jobs.analyze import (
    SLOPE_THRESHOLD,
    build_trend_pattern_rows,
    compute_hourly_occupancy,
    compute_temperature_trends,
    detect_temperature_anomalies,
)


@pytest.fixture(scope="module")
def spark():
    from pyspark.sql import SparkSession

    return (
        SparkSession.builder.appName("test-analyze")
        .master("local[1]")
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _ts(day: int, hour: int) -> datetime:
    """Return a fixed Monday (2026-01-19) + offset for varied days/hours."""
    return datetime(2026, 1, 19 + day, hour, 0, 0, tzinfo=UTC)


def _make_df(spark, rows: list[dict]):
    """Build a processed_sensor_data DataFrame from dicts."""
    from pyspark.sql.types import (
        BooleanType,
        DoubleType,
        StringType,
        StructField,
        StructType,
        TimestampType,
    )

    schema = StructType(
        [
            StructField("event_id", StringType(), False),
            StructField("device_id", StringType(), False),
            StructField("room_id", StringType(), False),
            StructField("ts", TimestampType(), False),
            StructField("temperature_c", DoubleType(), True),
            StructField("humidity_pct", DoubleType(), True),
            StructField("motion", BooleanType(), True),
            StructField("occupancy", BooleanType(), True),
        ]
    )
    data = [
        (
            r.get("event_id", f"evt-{i:03d}"),
            r.get("device_id", "dev-001"),
            r.get("room_id", "room-a"),
            r["ts"],
            r.get("temperature_c", 20.0),
            r.get("humidity_pct", 50.0),
            r.get("motion", False),
            r.get("occupancy", False),
        )
        for i, r in enumerate(rows)
    ]
    return spark.createDataFrame(data, schema=schema)


# ──────────────────────────────────────────────────────────────────────────────
# compute_hourly_occupancy
# ──────────────────────────────────────────────────────────────────────────────


class TestComputeHourlyOccupancy:
    def test_occupied_hour_rate_is_1(self, spark):
        df = _make_df(
            spark,
            [
                {"ts": _ts(0, 9), "occupancy": True},
                {"ts": _ts(0, 9), "occupancy": True, "event_id": "evt-002"},
            ],
        )
        result = compute_hourly_occupancy(df)
        row = result.filter(result.hour == 9).collect()[0]
        assert row.occupancy_rate == 1.0

    def test_unoccupied_hour_rate_is_0(self, spark):
        df = _make_df(spark, [{"ts": _ts(0, 2), "occupancy": False}])
        result = compute_hourly_occupancy(df)
        row = result.filter(result.hour == 2).collect()[0]
        assert row.occupancy_rate == 0.0

    def test_partial_occupancy(self, spark):
        df = _make_df(
            spark,
            [
                {"ts": _ts(0, 10), "occupancy": True},
                {"ts": _ts(0, 10), "occupancy": True, "event_id": "evt-002"},
                {"ts": _ts(0, 10), "occupancy": False, "event_id": "evt-003"},
                {"ts": _ts(0, 10), "occupancy": False, "event_id": "evt-004"},
            ],
        )
        result = compute_hourly_occupancy(df)
        row = result.filter(result.hour == 10).collect()[0]
        assert row.occupancy_rate == pytest.approx(0.5)

    def test_groups_by_room(self, spark):
        df = _make_df(
            spark,
            [
                {"room_id": "room-a", "ts": _ts(0, 9), "occupancy": True},
                {"room_id": "room-b", "ts": _ts(0, 9), "occupancy": False, "event_id": "evt-002"},
            ],
        )
        result = compute_hourly_occupancy(df)
        room_a_rate = result.filter(result.room_id == "room-a").collect()[0].occupancy_rate
        room_b_rate = result.filter(result.room_id == "room-b").collect()[0].occupancy_rate
        assert room_a_rate == 1.0
        assert room_b_rate == 0.0


# ──────────────────────────────────────────────────────────────────────────────
# compute_temperature_trends + build_trend_pattern_rows
# ──────────────────────────────────────────────────────────────────────────────


class TestComputeTemperatureTrends:
    def test_rising_slope_is_positive(self, spark):
        df = _make_df(
            spark,
            [{"ts": _ts(i, 0), "temperature_c": float(20 + 2 * i)} for i in range(5)],
        )
        result = compute_temperature_trends(df)
        row = result.collect()[0]
        assert row.slope > 0

    def test_falling_slope_is_negative(self, spark):
        df = _make_df(
            spark,
            [{"ts": _ts(i, 0), "temperature_c": float(20 - 2 * i)} for i in range(5)],
        )
        result = compute_temperature_trends(df)
        row = result.collect()[0]
        assert row.slope < 0


class TestBuildTrendPatternRows:
    def _rising_trend_df(self, spark):
        # 2°C/day >> SLOPE_THRESHOLD (1°C/day) → clearly 'rising'
        df = _make_df(
            spark,
            [{"ts": _ts(i, 0), "temperature_c": float(20 + 2 * i)} for i in range(5)],
        )
        return compute_temperature_trends(df)

    def _falling_trend_df(self, spark):
        # -2°C/day << -SLOPE_THRESHOLD → clearly 'falling'
        df = _make_df(
            spark,
            [{"ts": _ts(i, 0), "temperature_c": float(20 - 2 * i)} for i in range(5)],
        )
        return compute_temperature_trends(df)

    def _stable_trend_df(self, spark):
        # temperatures change by 0.0001°C/day — below SLOPE_THRESHOLD
        tiny_slope_per_second = SLOPE_THRESHOLD / 100
        df = _make_df(
            spark,
            [
                {"ts": _ts(0, i), "temperature_c": 20.0 + i * tiny_slope_per_second * 3600}
                for i in range(5)
            ],
        )
        return compute_temperature_trends(df)

    def test_rising_direction(self, spark):
        pattern_df = build_trend_pattern_rows(self._rising_trend_df(spark), "job-test")
        data = json.loads(pattern_df.collect()[0].data)
        assert data["direction"] == "rising"

    def test_falling_direction(self, spark):
        pattern_df = build_trend_pattern_rows(self._falling_trend_df(spark), "job-test")
        data = json.loads(pattern_df.collect()[0].data)
        assert data["direction"] == "falling"

    def test_stable_direction(self, spark):
        pattern_df = build_trend_pattern_rows(self._stable_trend_df(spark), "job-test")
        data = json.loads(pattern_df.collect()[0].data)
        assert data["direction"] == "stable"

    def test_pattern_type(self, spark):
        pattern_df = build_trend_pattern_rows(self._rising_trend_df(spark), "job-test")
        assert pattern_df.collect()[0].pattern_type == "temperature_trend"


# ──────────────────────────────────────────────────────────────────────────────
# detect_temperature_anomalies
#
# Mathematical property used in test data design:
# With m identical "normal" values and 1 outlier (any different value),
# z(outlier) = sqrt(m) exactly (population stddev).
# So: m=4 → z=2 (below threshold), m=9 → z=3 (medium), m=25 → z=5 (high).
# ──────────────────────────────────────────────────────────────────────────────


class TestDetectTemperatureAnomalies:
    def _make_room_df(self, spark, room_id: str, temperatures: list[float]):
        rows = [
            {
                "event_id": f"evt-{room_id}-{i:03d}",
                "room_id": room_id,
                "ts": _ts(i % 5, i % 24),
                "temperature_c": t,
            }
            for i, t in enumerate(temperatures)
        ]
        return _make_df(spark, rows)

    def test_no_anomaly_below_min_count(self, spark):
        df = self._make_room_df(spark, "room-a", [20.0, 21.0, 22.0])  # 3 readings < 4
        result = detect_temperature_anomalies(df, "job-test")
        assert result.count() == 0

    def test_no_anomaly_z_below_threshold(self, spark):
        # m=4 normal values + 1 outlier → z(outlier) = sqrt(4) = 2.0 < Z_MEDIUM
        temps = [20.0] * 4 + [100.0]
        df = self._make_room_df(spark, "room-a", temps)
        result = detect_temperature_anomalies(df, "job-test")
        assert result.count() == 0

    def test_medium_anomaly_z_equals_3(self, spark):
        # m=9 normal values + 1 outlier → z(outlier) = sqrt(9) = 3.0 >= Z_MEDIUM
        temps = [20.0] * 9 + [100.0]
        df = self._make_room_df(spark, "room-a", temps)
        result = detect_temperature_anomalies(df, "job-test")
        assert result.count() == 1
        assert result.collect()[0].severity == "medium"

    def test_high_anomaly_z_equals_5(self, spark):
        # m=25 normal values + 1 outlier → z(outlier) = sqrt(25) = 5.0 >= Z_HIGH
        temps = [20.0] * 25 + [100.0]
        df = self._make_room_df(spark, "room-a", temps)
        result = detect_temperature_anomalies(df, "job-test")
        assert result.count() == 1
        assert result.collect()[0].severity == "high"

    def test_anomaly_entity_id_is_room_id(self, spark):
        temps = [20.0] * 9 + [100.0]
        df = self._make_room_df(spark, "conf-b", temps)
        result = detect_temperature_anomalies(df, "job-test")
        assert result.collect()[0].entity_id == "conf-b"

    def test_anomaly_type_is_temperature(self, spark):
        temps = [20.0] * 9 + [100.0]
        df = self._make_room_df(spark, "room-a", temps)
        result = detect_temperature_anomalies(df, "job-test")
        assert result.collect()[0].anomaly_type == "temperature"

    def test_isolated_to_anomalous_room(self, spark):
        # room-x has anomaly (z=3), room-y has no anomaly (z=2)

        anomalous_df = self._make_room_df(spark, "room-x", [20.0] * 9 + [100.0])
        normal_df = self._make_room_df(spark, "room-y", [20.0] * 4 + [100.0])
        combined = anomalous_df.union(normal_df)

        result = detect_temperature_anomalies(combined, "job-test")
        entity_ids = {row.entity_id for row in result.collect()}
        assert "room-x" in entity_ids
        assert "room-y" not in entity_ids

    def test_data_json_contains_z_score(self, spark):
        temps = [20.0] * 9 + [100.0]
        df = self._make_room_df(spark, "room-a", temps)
        result = detect_temperature_anomalies(df, "job-test")
        data = json.loads(result.collect()[0].data)
        assert "z_score" in data
        assert abs(data["z_score"] - 3.0) < 0.01
