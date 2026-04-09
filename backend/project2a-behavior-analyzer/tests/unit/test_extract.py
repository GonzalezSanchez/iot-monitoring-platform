"""
Unit tests for lambdas/extract/handler.py
"""

import json
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from extract.handler import _map_item, _scan_events, _upsert_batch, handler

# ──────────────────────────────────────────────────────────────────────────────
# _map_item
# ──────────────────────────────────────────────────────────────────────────────


class TestMapItem:
    def _item(self, **overrides) -> dict:
        base = {
            "event_id": "evt-1",
            "device_id": "dev-1",
            "room_id": "room-a",
            "ts": "2026-01-01T09:00:00Z",
            "payload": {"temperature": 21.5, "humidity": 55.0, "motion": True, "occupancy": True},
        }
        base.update(overrides)
        return base

    def test_maps_all_fields(self) -> None:
        row = _map_item(self._item())
        assert row["event_id"] == "evt-1"
        assert row["device_id"] == "dev-1"
        assert row["room_id"] == "room-a"
        assert row["temperature"] == 21.5
        assert row["humidity"] == 55.0
        assert row["motion"] is True
        assert row["occupancy"] is True

    def test_raw_payload_is_json_string(self) -> None:
        row = _map_item(self._item())
        parsed = json.loads(row["raw_payload"])
        assert parsed["temperature"] == 21.5

    def test_payload_as_string(self) -> None:
        item = self._item()
        item["payload"] = json.dumps(item["payload"])
        row = _map_item(item)
        assert row["temperature"] == 21.5

    def test_missing_device_id_defaults_to_unknown(self) -> None:
        item = self._item()
        del item["device_id"]
        assert _map_item(item)["device_id"] == "unknown"

    def test_missing_room_id_defaults_to_unknown(self) -> None:
        item = self._item()
        del item["room_id"]
        assert _map_item(item)["room_id"] == "unknown"

    def test_missing_payload_fields_are_none(self) -> None:
        item = self._item(payload={})
        row = _map_item(item)
        assert row["temperature"] is None
        assert row["humidity"] is None
        assert row["motion"] is None
        assert row["occupancy"] is None


# ──────────────────────────────────────────────────────────────────────────────
# _scan_events
# ──────────────────────────────────────────────────────────────────────────────


class TestScanEvents:
    def _table(self, pages: list[list[dict]]) -> MagicMock:
        """Mock DynamoDB table that returns given pages of items."""
        table = MagicMock()
        responses = []
        for i, page in enumerate(pages):
            last_key = {"pk": str(i)} if i < len(pages) - 1 else None
            responses.append({"Items": page, "LastEvaluatedKey": last_key})
        table.scan.side_effect = responses
        return table

    def test_returns_all_items_single_page(self) -> None:
        items = [{"event_id": "e1"}, {"event_id": "e2"}]
        table = self._table([items])
        result = _scan_events(table, "2026-01-01", "2026-01-07")
        assert len(result) == 2

    def test_paginates_across_multiple_pages(self) -> None:
        page1 = [{"event_id": "e1"}]
        page2 = [{"event_id": "e2"}, {"event_id": "e3"}]
        table = self._table([page1, page2])
        result = _scan_events(table, "2026-01-01", "2026-01-07")
        assert len(result) == 3

    def test_passes_correct_date_range(self) -> None:
        table = self._table([[]])
        _scan_events(table, "2026-01-01", "2026-01-07")
        call_kwargs = table.scan.call_args[1]
        values = call_kwargs["ExpressionAttributeValues"]
        assert values[":s"] == "2026-01-01T00:00:00Z"
        assert values[":e"] == "2026-01-07T23:59:59Z"

    def test_returns_empty_list_when_no_items(self) -> None:
        table = self._table([[]])
        assert _scan_events(table, "2026-01-01", "2026-01-07") == []


# ──────────────────────────────────────────────────────────────────────────────
# _upsert_batch
# ──────────────────────────────────────────────────────────────────────────────


class TestUpsertBatch:
    def _conn(self, rowcount: int = 1) -> MagicMock:
        cur = MagicMock()
        cur.rowcount = rowcount
        conn = MagicMock()
        conn.cursor.return_value.__enter__ = lambda s: cur
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        conn._cur = cur
        return conn

    def _row(self, event_id: str = "e1") -> dict:
        return {
            "event_id": event_id,
            "device_id": "d1",
            "room_id": "r1",
            "ts": "2026-01-01T09:00:00Z",
            "temperature": 21.0,
            "humidity": 50.0,
            "motion": True,
            "occupancy": True,
            "raw_payload": "{}",
        }

    def test_returns_zero_for_empty_list(self) -> None:
        conn = self._conn()
        assert _upsert_batch(conn, []) == 0
        conn.cursor.assert_not_called()

    def test_returns_inserted_count(self) -> None:
        conn = self._conn(rowcount=1)
        rows = [self._row("e1"), self._row("e2")]
        assert _upsert_batch(conn, rows) == 2

    def test_skips_duplicate_rows(self) -> None:
        # rowcount=0 simulates ON CONFLICT DO NOTHING
        conn = self._conn(rowcount=0)
        assert _upsert_batch(conn, [self._row()]) == 0

    def test_commits_after_insert(self) -> None:
        conn = self._conn()
        _upsert_batch(conn, [self._row()])
        conn.commit.assert_called_once()


# ──────────────────────────────────────────────────────────────────────────────
# handler — time window resolution
# ──────────────────────────────────────────────────────────────────────────────


class TestHandlerWindowResolution:
    def _mock_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DYNAMODB_TABLE_EVENTS", "prod-SensorEvents")
        monkeypatch.setenv("AWS_REGION", "eu-central-1")

    def test_uses_explicit_dates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._mock_env(monkeypatch)
        event = {
            "job_id": "job-1",
            "start_date": "2026-01-01",
            "end_date": "2026-01-07",
        }
        with (
            patch("extract.handler.boto3") as mock_boto3,
            patch("extract.handler.get_connection") as mock_conn,
        ):
            mock_table = MagicMock()
            mock_table.scan.return_value = {"Items": [], "LastEvaluatedKey": None}
            mock_boto3.resource.return_value.Table.return_value = mock_table
            mock_conn.return_value.__enter__ = lambda s: MagicMock()
            conn = MagicMock()
            cur = MagicMock()
            cur.rowcount = 0
            conn.cursor.return_value.__enter__ = lambda s: cur
            conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
            mock_conn.return_value = conn

            result = handler(event, None)

        assert result["start_date"] == "2026-01-01"
        assert result["end_date"] == "2026-01-07"

    def test_computes_window_from_days_back(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._mock_env(monkeypatch)
        from datetime import datetime as dt

        fake_today = date(2026, 1, 10)
        event = {"job_id": "job-1", "days_back": 7}

        with (
            patch("extract.handler.boto3") as mock_boto3,
            patch("extract.handler.get_connection") as mock_conn,
            patch("extract.handler.datetime") as mock_dt,
        ):
            mock_dt.now.return_value.date.return_value = fake_today
            mock_dt.fromisoformat = dt.fromisoformat

            mock_table = MagicMock()
            mock_table.scan.return_value = {"Items": [], "LastEvaluatedKey": None}
            mock_boto3.resource.return_value.Table.return_value = mock_table
            conn = MagicMock()
            cur = MagicMock()
            cur.rowcount = 0
            conn.cursor.return_value.__enter__ = lambda s: cur
            conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
            mock_conn.return_value = conn

            result = handler(event, None)

        assert result["end_date"] == "2026-01-09"  # today - 1
        assert result["start_date"] == "2026-01-03"  # today - 7
