"""Unit tests for sensor data generation script."""

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.generate_sensor_data import (
    ROOMS,
    SENSOR_TYPES,
    VALUE_RANGES,
    generate_event,
    main,
    make_blob_path,
    write_to_adls,
    write_to_dir,
)

FIXED_TS = datetime(2024, 3, 15, 9, 5, 30, tzinfo=UTC)


class TestGenerateEvent:
    def test_returns_required_fields(self) -> None:
        event = generate_event()
        assert set(event.keys()) == {"event_id", "room_id", "sensor_type", "value", "timestamp"}

    def test_sensor_type_is_valid(self) -> None:
        for _ in range(50):
            assert generate_event()["sensor_type"] in SENSOR_TYPES

    def test_room_id_is_valid(self) -> None:
        for _ in range(50):
            assert generate_event()["room_id"] in ROOMS

    def test_value_within_range(self) -> None:
        for _ in range(100):
            event = generate_event()
            sensor_type = str(event["sensor_type"])
            lo, hi = VALUE_RANGES[sensor_type]
            assert lo <= float(str(event["value"])) <= hi

    def test_event_id_is_uuid_string(self) -> None:
        event_id = str(generate_event()["event_id"])
        assert len(event_id) == 36
        assert event_id.count("-") == 4

    def test_timestamp_is_iso_string(self) -> None:
        ts = str(generate_event()["timestamp"])
        assert "T" in ts
        assert "+" in ts or ts.endswith("Z")


class TestMakeBlobPath:
    def test_path_format(self) -> None:
        path = make_blob_path(FIXED_TS)
        assert path == "year=2024/month=03/day=15/sensors_20240315T090530.json"

    def test_path_contains_all_partition_levels(self) -> None:
        path = make_blob_path(FIXED_TS)
        assert path.startswith("year=")
        assert "/month=" in path
        assert "/day=" in path

    def test_path_ends_with_json(self) -> None:
        assert make_blob_path(FIXED_TS).endswith(".json")

    def test_single_digit_month_zero_padded(self) -> None:
        ts = datetime(2024, 1, 5, tzinfo=UTC)
        path = make_blob_path(ts)
        assert "month=01" in path
        assert "day=05" in path

    def test_path_matches_expected_pattern(self) -> None:
        path = make_blob_path(FIXED_TS)
        pattern = r"year=\d{4}/month=\d{2}/day=\d{2}/sensors_\d{8}T\d{6}\.json"
        assert re.match(pattern, path)


class TestWriteToDir:
    def test_creates_partitioned_file(self, tmp_path: Path) -> None:
        events: list[dict[str, object]] = [
            {
                "event_id": "abc",
                "room_id": "room_001",
                "sensor_type": "temperature",
                "value": 21.0,
                "timestamp": "2024-01-01T00:00:00+00:00",
            },
        ]
        write_to_dir(events, tmp_path)
        json_files = list(tmp_path.rglob("*.json"))
        assert len(json_files) == 1
        # File must be inside a Hive-partitioned subdirectory
        assert "year=" in str(json_files[0])

    def test_file_contains_correct_event_count(self, tmp_path: Path) -> None:
        events: list[dict[str, object]] = [generate_event() for _ in range(7)]
        write_to_dir(events, tmp_path)
        files = list(tmp_path.rglob("*.json"))
        lines = files[0].read_text().strip().splitlines()
        assert len(lines) == 7

    def test_each_line_is_valid_json(self, tmp_path: Path) -> None:
        events: list[dict[str, object]] = [generate_event() for _ in range(3)]
        write_to_dir(events, tmp_path)
        files = list(tmp_path.rglob("*.json"))
        for line in files[0].read_text().strip().splitlines():
            parsed = json.loads(line)
            assert "event_id" in parsed


class TestWriteToAdls:
    def test_uploads_payload_and_returns_abfss_path(self) -> None:
        events: list[dict[str, object]] = [generate_event() for _ in range(5)]

        mock_blob_client = MagicMock()
        mock_service_client = MagicMock()
        mock_service_client.get_blob_client.return_value = mock_blob_client

        with (
            patch("azure.identity.DefaultAzureCredential"),
            patch(
                "azure.storage.blob.BlobServiceClient",
                return_value=mock_service_client,
            ),
        ):
            path = write_to_adls(events, "mystorageaccount", "bronze")

        assert path.startswith("abfss://bronze@mystorageaccount.dfs.core.windows.net/")
        assert path.endswith(".json")
        mock_blob_client.upload_blob.assert_called_once()
        _, call_kwargs = mock_blob_client.upload_blob.call_args
        assert call_kwargs.get("overwrite") is True

    def test_payload_is_newline_delimited_json(self) -> None:
        events: list[dict[str, object]] = [generate_event() for _ in range(3)]
        captured: list[str] = []

        mock_blob_client = MagicMock()
        mock_blob_client.upload_blob.side_effect = lambda payload, **_: captured.append(payload)
        mock_service_client = MagicMock()
        mock_service_client.get_blob_client.return_value = mock_blob_client

        with (
            patch("azure.identity.DefaultAzureCredential"),
            patch("azure.storage.blob.BlobServiceClient", return_value=mock_service_client),
        ):
            write_to_adls(events, "mystorageaccount", "bronze")

        lines = captured[0].splitlines()
        assert len(lines) == 3
        for line in lines:
            json.loads(line)  # must not raise


class TestMain:
    def test_main_stdout(self) -> None:
        main(count=3, output_dir=None, use_adls=False)

    def test_main_writes_to_dir(self, tmp_path: Path) -> None:
        main(count=5, output_dir=str(tmp_path), use_adls=False)
        files = list(tmp_path.rglob("*.json"))
        assert len(files) == 1

    def test_main_adls_calls_write_to_adls(self) -> None:
        with (
            patch.dict("os.environ", {"AZURE_STORAGE_ACCOUNT_NAME": "myaccount"}),
            patch("scripts.generate_sensor_data.write_to_adls") as mock_write,
        ):
            main(count=10, output_dir=None, use_adls=True)
            mock_write.assert_called_once()
            _, kwargs = mock_write.call_args
            assert len(mock_write.call_args[0][0]) == 10  # events list
