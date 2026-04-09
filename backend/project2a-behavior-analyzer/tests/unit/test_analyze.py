"""
Unit tests for lambdas/analyze/handler.py

Tests pure detection functions — no DB connection needed.
DB-touching functions are tested with a mocked psycopg2 connection.
"""

import json
from unittest.mock import MagicMock, patch

from analyze.handler import (
    _insert_anomalies,
    _insert_patterns,
    _load_rows,
    detect_occupancy_schedule,
    detect_temperature_spikes,
    detect_temperature_trend,
    detect_unusual_activity,
    handler,
)

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _row(
    room_id: str = "room-a",
    ts: str = "2026-01-05T09:00:00Z",  # Monday
    temperature: float | None = 21.0,
    humidity: float | None = 55.0,
    motion: bool = False,
    occupancy: bool = False,
    device_id: str = "dev-1",
) -> dict:
    return {
        "room_id": room_id,
        "device_id": device_id,
        "ts": ts,
        "temperature": temperature,
        "humidity": humidity,
        "motion": motion,
        "occupancy": occupancy,
    }


# ──────────────────────────────────────────────────────────────────────────────
# detect_occupancy_schedule
# ──────────────────────────────────────────────────────────────────────────────


class TestDetectOccupancySchedule:
    def test_returns_empty_for_no_rows(self) -> None:
        assert detect_occupancy_schedule([]) == []

    def test_returns_empty_when_no_motion_or_occupancy(self) -> None:
        rows = [_row(motion=False, occupancy=False) for _ in range(5)]
        assert detect_occupancy_schedule(rows) == []

    def test_detects_pattern_for_room_with_repeated_occupancy(self) -> None:
        # 3 readings on Monday at 9:00 → hour 9 should appear
        rows = [
            _row(ts="2026-01-05T09:00:00Z", motion=True),  # Mon
            _row(ts="2026-01-05T09:15:00Z", motion=True),  # Mon
            _row(ts="2026-01-05T09:30:00Z", motion=True),  # Mon
        ]
        patterns = detect_occupancy_schedule(rows)
        assert len(patterns) == 1
        assert patterns[0]["pattern_type"] == "occupancy_schedule"
        assert patterns[0]["entity_id"] == "room-a"
        schedule = json.loads(patterns[0]["data"])["schedule"]
        assert "0" in schedule  # weekday 0 = Monday
        assert 9 in schedule["0"]

    def test_ignores_hours_with_only_one_reading(self) -> None:
        # Only 1 reading at hour 14 — threshold is 2
        rows = [_row(ts="2026-01-05T14:00:00Z", motion=True)]
        assert detect_occupancy_schedule(rows) == []

    def test_separate_patterns_per_room(self) -> None:
        rows = [
            _row(room_id="room-a", ts="2026-01-05T09:00:00Z", motion=True),
            _row(room_id="room-a", ts="2026-01-05T09:15:00Z", motion=True),
            _row(room_id="room-b", ts="2026-01-05T10:00:00Z", motion=True),
            _row(room_id="room-b", ts="2026-01-05T10:15:00Z", motion=True),
        ]
        patterns = detect_occupancy_schedule(rows)
        rooms = {p["entity_id"] for p in patterns}
        assert rooms == {"room-a", "room-b"}


# ──────────────────────────────────────────────────────────────────────────────
# detect_temperature_trend
# ──────────────────────────────────────────────────────────────────────────────


class TestDetectTemperatureTrend:
    def test_returns_empty_for_no_rows(self) -> None:
        assert detect_temperature_trend([]) == []

    def test_returns_empty_when_too_few_readings(self) -> None:
        rows = [_row(ts=f"2026-01-0{i+1}T09:00:00Z", temperature=20.0) for i in range(3)]
        assert detect_temperature_trend(rows) == []

    def test_rising_trend(self) -> None:
        rows = [
            _row(ts="2026-01-01T09:00:00Z", temperature=18.0),
            _row(ts="2026-01-02T09:00:00Z", temperature=19.0),
            _row(ts="2026-01-03T09:00:00Z", temperature=23.0),
            _row(ts="2026-01-04T09:00:00Z", temperature=25.0),
        ]
        patterns = detect_temperature_trend(rows)
        assert len(patterns) == 1
        data = json.loads(patterns[0]["data"])
        assert data["trend"] == "rising"

    def test_falling_trend(self) -> None:
        rows = [
            _row(ts="2026-01-01T09:00:00Z", temperature=25.0),
            _row(ts="2026-01-02T09:00:00Z", temperature=24.0),
            _row(ts="2026-01-03T09:00:00Z", temperature=20.0),
            _row(ts="2026-01-04T09:00:00Z", temperature=19.0),
        ]
        patterns = detect_temperature_trend(rows)
        data = json.loads(patterns[0]["data"])
        assert data["trend"] == "falling"

    def test_stable_trend(self) -> None:
        rows = [_row(ts=f"2026-01-0{i+1}T09:00:00Z", temperature=21.0) for i in range(4)]
        patterns = detect_temperature_trend(rows)
        data = json.loads(patterns[0]["data"])
        assert data["trend"] == "stable"

    def test_skips_rows_without_temperature(self) -> None:
        rows = [_row(ts=f"2026-01-0{i+1}T09:00:00Z", temperature=None) for i in range(4)]
        assert detect_temperature_trend(rows) == []


# ──────────────────────────────────────────────────────────────────────────────
# detect_temperature_spikes
# ──────────────────────────────────────────────────────────────────────────────


class TestDetectTemperatureSpikes:
    def test_returns_empty_for_no_rows(self) -> None:
        assert detect_temperature_spikes([]) == []

    def test_returns_empty_when_too_few_readings(self) -> None:
        rows = [_row(temperature=21.0) for _ in range(3)]
        assert detect_temperature_spikes(rows) == []

    def test_detects_spike(self) -> None:
        # 10 normal readings + 1 extreme spike; z = 10/sqrt(11) ≈ 3.02 ≥ threshold
        normal = [_row(ts=f"2026-01-{i+1:02d}T09:00:00Z", temperature=20.0) for i in range(10)]
        spike = [_row(ts="2026-01-11T09:00:00Z", temperature=60.0)]
        anomalies = detect_temperature_spikes(normal + spike)
        assert len(anomalies) == 1
        assert anomalies[0]["anomaly_type"] == "temperature_spike"
        assert anomalies[0]["entity_id"] == "room-a"

    def test_no_spike_for_normal_variation(self) -> None:
        rows = [
            _row(ts=f"2026-01-{i+1:02d}T09:00:00Z", temperature=20.0 + i * 0.1) for i in range(10)
        ]
        assert detect_temperature_spikes(rows) == []

    def test_high_severity_for_extreme_spike(self) -> None:
        # 29 normal readings + 1 spike; z = 29/sqrt(30) ≈ 5.29 ≥ 5 → "high"
        normal = [_row(ts=f"2026-01-{i+1:02d}T09:00:00Z", temperature=20.0) for i in range(29)]
        extreme = [_row(ts="2026-01-30T09:00:00Z", temperature=100.0)]
        anomalies = detect_temperature_spikes(normal + extreme)
        assert anomalies[0]["severity"] == "high"


# ──────────────────────────────────────────────────────────────────────────────
# detect_unusual_activity
# ──────────────────────────────────────────────────────────────────────────────


class TestDetectUnusualActivity:
    def _schedule_pattern(
        self, room_id: str = "room-a", weekday: int = 0, hours: list[int] = [9, 10]
    ) -> dict:
        return {
            "entity_type": "room",
            "entity_id": room_id,
            "pattern_type": "occupancy_schedule",
            "data": json.dumps({"schedule": {str(weekday): hours}}),
        }

    def test_returns_empty_with_no_patterns(self) -> None:
        rows = [_row(motion=True)]
        assert detect_unusual_activity(rows, []) == []

    def test_returns_empty_for_motion_within_schedule(self) -> None:
        # Monday (weekday=0) at 09:00 — within schedule
        rows = [_row(ts="2026-01-05T09:00:00Z", motion=True)]
        patterns = [self._schedule_pattern(weekday=0, hours=[9, 10])]
        assert detect_unusual_activity(rows, patterns) == []

    def test_detects_motion_outside_schedule(self) -> None:
        # Monday at 03:00 — not in schedule
        rows = [_row(ts="2026-01-05T03:00:00Z", motion=True)]
        patterns = [self._schedule_pattern(weekday=0, hours=[9, 10])]
        anomalies = detect_unusual_activity(rows, patterns)
        assert len(anomalies) == 1
        assert anomalies[0]["anomaly_type"] == "unusual_activity"
        assert anomalies[0]["severity"] == "low"

    def test_ignores_rows_without_motion(self) -> None:
        rows = [_row(ts="2026-01-05T03:00:00Z", motion=False)]
        patterns = [self._schedule_pattern(weekday=0, hours=[9, 10])]
        assert detect_unusual_activity(rows, patterns) == []

    def test_ignores_room_without_known_schedule(self) -> None:
        rows = [_row(room_id="room-unknown", ts="2026-01-05T03:00:00Z", motion=True)]
        patterns = [self._schedule_pattern(room_id="room-a")]
        assert detect_unusual_activity(rows, patterns) == []


# ──────────────────────────────────────────────────────────────────────────────
# _load_rows
# ──────────────────────────────────────────────────────────────────────────────


class TestLoadRows:
    def test_returns_list_of_dicts(self) -> None:
        cur = MagicMock()
        cur.description = [("room_id",), ("ts",), ("temperature",)]
        cur.fetchall.return_value = [("room-a", "2026-01-01T09:00:00Z", 21.0)]
        conn = MagicMock()
        conn.cursor.return_value.__enter__ = lambda s: cur
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = _load_rows(conn, "2026-01-01", "2026-01-07")

        assert result == [{"room_id": "room-a", "ts": "2026-01-01T09:00:00Z", "temperature": 21.0}]

    def test_returns_empty_list_when_no_rows(self) -> None:
        cur = MagicMock()
        cur.description = [("room_id",)]
        cur.fetchall.return_value = []
        conn = MagicMock()
        conn.cursor.return_value.__enter__ = lambda s: cur
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        assert _load_rows(conn, "2026-01-01", "2026-01-07") == []


# ──────────────────────────────────────────────────────────────────────────────
# _insert_patterns / _insert_anomalies
# ──────────────────────────────────────────────────────────────────────────────


class TestInsertPatterns:
    def _conn(self) -> MagicMock:
        cur = MagicMock()
        conn = MagicMock()
        conn.cursor.return_value.__enter__ = lambda s: cur
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        return conn

    def test_returns_zero_for_empty_list(self) -> None:
        assert _insert_patterns(self._conn(), "job-1", "2026-01-01", "2026-01-07", []) == 0

    def test_returns_count_of_inserted_patterns(self) -> None:
        patterns = [
            {
                "entity_type": "room",
                "entity_id": "room-a",
                "pattern_type": "occupancy_schedule",
                "data": "{}",
            }
        ]
        assert _insert_patterns(self._conn(), "job-1", "2026-01-01", "2026-01-07", patterns) == 1

    def test_commits_after_insert(self) -> None:
        conn = self._conn()
        _insert_patterns(
            conn,
            "job-1",
            "2026-01-01",
            "2026-01-07",
            [{"entity_type": "room", "entity_id": "r", "pattern_type": "t", "data": "{}"}],
        )
        conn.commit.assert_called_once()


class TestInsertAnomalies:
    def _conn(self) -> MagicMock:
        cur = MagicMock()
        conn = MagicMock()
        conn.cursor.return_value.__enter__ = lambda s: cur
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        return conn

    def test_returns_zero_for_empty_list(self) -> None:
        assert _insert_anomalies(self._conn(), "job-1", []) == 0

    def test_returns_count_of_inserted_anomalies(self) -> None:
        anomalies = [
            {
                "entity_type": "room",
                "entity_id": "room-a",
                "anomaly_type": "temperature_spike",
                "detected_at": "2026-01-01T09:00:00+00:00",
                "severity": "medium",
                "data": "{}",
            }
        ]
        assert _insert_anomalies(self._conn(), "job-1", anomalies) == 1

    def test_commits_after_insert(self) -> None:
        conn = self._conn()
        anomalies = [
            {
                "entity_type": "room",
                "entity_id": "r",
                "anomaly_type": "t",
                "detected_at": "2026-01-01T09:00:00+00:00",
                "severity": "low",
                "data": "{}",
            }
        ]
        _insert_anomalies(conn, "job-1", anomalies)
        conn.commit.assert_called_once()


# ──────────────────────────────────────────────────────────────────────────────
# handler
# ──────────────────────────────────────────────────────────────────────────────


class TestAnalyzeHandler:
    def _event(self) -> dict:
        return {"job_id": "job-1", "start_date": "2026-01-01", "end_date": "2026-01-07"}

    def _conn(self) -> MagicMock:
        cur = MagicMock()
        cur.description = []
        cur.fetchall.return_value = []
        conn = MagicMock()
        conn.cursor.return_value.__enter__ = lambda s: cur
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        return conn

    def test_returns_job_fields(self) -> None:
        with (
            patch("analyze.handler.get_connection", return_value=self._conn()),
            patch("analyze.handler._load_rows", return_value=[]),
            patch("analyze.handler._insert_patterns", return_value=0),
            patch("analyze.handler._insert_anomalies", return_value=0),
        ):
            result = handler(self._event(), None)

        assert result["job_id"] == "job-1"
        assert result["patterns_count"] == 0
        assert result["anomalies_count"] == 0

    def test_closes_connection_on_success(self) -> None:
        conn = self._conn()
        with (
            patch("analyze.handler.get_connection", return_value=conn),
            patch("analyze.handler._load_rows", return_value=[]),
            patch("analyze.handler._insert_patterns", return_value=0),
            patch("analyze.handler._insert_anomalies", return_value=0),
        ):
            handler(self._event(), None)

        conn.close.assert_called_once()

    def test_closes_connection_on_error(self) -> None:
        conn = self._conn()
        with (
            patch("analyze.handler.get_connection", return_value=conn),
            patch("analyze.handler._load_rows", side_effect=RuntimeError("db error")),
        ):
            try:
                handler(self._event(), None)
            except RuntimeError:
                pass

        conn.close.assert_called_once()
