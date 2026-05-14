"""
Unit tests for lambdas/transform/handler.py
"""

from unittest.mock import MagicMock, patch

from transform.handler import RawRow, _delete_invalid, _fetch_unprocessed, _is_valid, handler

# ──────────────────────────────────────────────────────────────────────────────
# _is_valid
# ──────────────────────────────────────────────────────────────────────────────


class TestIsValid:
    def _row(self, **overrides) -> RawRow:
        base = RawRow(
            id=1,
            event_id="e1",
            device_id="dev-1",
            room_id="room-a",
            ts="2026-01-01T09:00:00Z",
            temperature=21.0,
            humidity=55.0,
            motion=True,
            occupancy=True,
        )
        for k, v in overrides.items():
            object.__setattr__(base, k, v)
        return base

    def test_valid_row_passes(self) -> None:
        assert _is_valid(self._row()) is True

    def test_none_temperature_rejected(self) -> None:
        assert _is_valid(self._row(temperature=None)) is False

    def test_none_humidity_rejected(self) -> None:
        assert _is_valid(self._row(humidity=None)) is False

    def test_temperature_too_high_rejected(self) -> None:
        assert _is_valid(self._row(temperature=61.0)) is False

    def test_temperature_too_low_rejected(self) -> None:
        assert _is_valid(self._row(temperature=-21.0)) is False

    def test_temperature_at_boundary_is_valid(self) -> None:
        assert _is_valid(self._row(temperature=60.0)) is True
        assert _is_valid(self._row(temperature=-20.0)) is True

    def test_humidity_out_of_range_rejected(self) -> None:
        assert _is_valid(self._row(humidity=101.0)) is False
        assert _is_valid(self._row(humidity=-1.0)) is False

    def test_missing_device_id_rejected(self) -> None:
        assert _is_valid(self._row(device_id="")) is False

    def test_missing_room_id_rejected(self) -> None:
        assert _is_valid(self._row(room_id="")) is False

    def test_none_ts_rejected(self) -> None:
        assert _is_valid(self._row(ts=None)) is False


# ──────────────────────────────────────────────────────────────────────────────
# _delete_invalid
# ──────────────────────────────────────────────────────────────────────────────


class TestDeleteInvalid:
    def _conn(self) -> MagicMock:
        cur = MagicMock()
        conn = MagicMock()
        conn.cursor.return_value.__enter__ = lambda s: cur
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        conn._cur = cur
        return conn

    def test_does_nothing_for_empty_list(self) -> None:
        conn = self._conn()
        _delete_invalid(conn, [])
        conn.cursor.assert_not_called()

    def test_executes_delete_for_ids(self) -> None:
        conn = self._conn()
        _delete_invalid(conn, [1, 2, 3])
        conn._cur.execute.assert_called_once()
        conn.commit.assert_called_once()


# ──────────────────────────────────────────────────────────────────────────────
# handler
# ──────────────────────────────────────────────────────────────────────────────


class TestTransformHandler:
    def _make_rows(self) -> list[RawRow]:
        return [
            RawRow(1, "e1", "dev-1", "room-a", "2026-01-01T09:00:00Z", 21.0, 55.0, True, True),
            RawRow(
                2, "e2", "dev-2", "room-a", "2026-01-01T10:00:00Z", 99.0, 55.0, True, True
            ),  # bad temp
            RawRow(
                3, "e3", "", "room-a", "2026-01-01T11:00:00Z", 21.0, 55.0, False, False
            ),  # empty device_id
        ]

    def _event(self) -> dict:
        return {
            "job_id": "job-1",
            "start_date": "2026-01-01",
            "end_date": "2026-01-07",
            "extracted_count": 3,
        }

    def test_counts_valid_and_invalid(self) -> None:
        rows = self._make_rows()
        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value.__enter__ = lambda s: cur
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with (
            patch("transform.handler.get_connection", return_value=conn),
            patch("transform.handler._fetch_unprocessed", return_value=rows),
            patch("transform.handler._delete_invalid"),
        ):
            result = handler(self._event(), None)

        assert result["transformed_count"] == 1
        assert result["rejected_count"] == 2

    def test_deletes_invalid_rows(self) -> None:
        rows = self._make_rows()
        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value.__enter__ = lambda s: cur
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with (
            patch("transform.handler.get_connection", return_value=conn),
            patch("transform.handler._fetch_unprocessed", return_value=rows),
            patch("transform.handler._delete_invalid") as mock_delete,
        ):
            handler(self._event(), None)

        # row ids 2 and 3 are invalid
        mock_delete.assert_called_once_with(conn, [2, 3])

    def test_passes_job_fields_through(self) -> None:
        conn = MagicMock()
        conn.cursor.return_value.__enter__ = lambda s: MagicMock()
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with (
            patch("transform.handler.get_connection", return_value=conn),
            patch("transform.handler._fetch_unprocessed", return_value=[]),
            patch("transform.handler._delete_invalid"),
        ):
            result = handler(self._event(), None)

        assert result["job_id"] == "job-1"
        assert result["start_date"] == "2026-01-01"
        assert result["end_date"] == "2026-01-07"

    def test_closes_connection_on_success(self) -> None:
        conn = MagicMock()
        conn.cursor.return_value.__enter__ = lambda s: MagicMock()
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with (
            patch("transform.handler.get_connection", return_value=conn),
            patch("transform.handler._fetch_unprocessed", return_value=[]),
            patch("transform.handler._delete_invalid"),
        ):
            handler(self._event(), None)

        conn.close.assert_called_once()


# ──────────────────────────────────────────────────────────────────────────────
# _fetch_unprocessed
# ──────────────────────────────────────────────────────────────────────────────


class TestFetchUnprocessed:
    def _conn(self, rows: list) -> MagicMock:
        cur = MagicMock()
        cur.fetchall.return_value = rows
        conn = MagicMock()
        conn.cursor.return_value.__enter__ = lambda s: cur
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        return conn

    def test_returns_rawrow_list(self) -> None:
        db_row = (1, "e1", "dev-1", "room-a", "2026-01-01T09:00:00Z", 21.0, 55.0, True, True)
        result = _fetch_unprocessed(self._conn([db_row]), "2026-01-01", "2026-01-07")
        assert len(result) == 1
        assert isinstance(result[0], RawRow)
        assert result[0].event_id == "e1"
        assert result[0].temperature == 21.0

    def test_returns_empty_list_when_no_rows(self) -> None:
        assert _fetch_unprocessed(self._conn([]), "2026-01-01", "2026-01-07") == []
