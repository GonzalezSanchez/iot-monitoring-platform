import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from jobs.extract import RAW_SCHEMA, main, scan_dynamodb, to_dataframe


@pytest.fixture(scope="module")
def spark():
    from pyspark.sql import SparkSession

    return (
        SparkSession.builder.appName("test-extract")
        .master("local[1]")
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )


SAMPLE_ITEMS = [
    {
        "event_id": "evt-001",
        "device_id": "dev-conf-a1",
        "room_id": "conference-a1",
        "timestamp": "2026-01-15T10:00:00Z",
        "payload": json.dumps(
            {"temperature": 21.5, "humidity": 50.0, "motion": True, "occupancy": True}
        ),
    },
    {
        "event_id": "evt-002",
        "device_id": "dev-lab-d4",
        "room_id": "lab-d4",
        "timestamp": "2026-01-15T11:00:00Z",
        "payload": json.dumps(
            {"temperature": 19.0, "humidity": 55.0, "motion": False, "occupancy": False}
        ),
    },
]


class TestToDataframe:
    def test_row_count(self, spark):
        df = to_dataframe(spark, SAMPLE_ITEMS)
        assert df.count() == 2

    def test_schema_matches(self, spark):
        df = to_dataframe(spark, SAMPLE_ITEMS)
        assert df.schema == RAW_SCHEMA

    def test_values_mapped_correctly(self, spark):
        df = to_dataframe(spark, SAMPLE_ITEMS)
        row = df.filter(df.event_id == "evt-001").collect()[0]
        assert row.device_id == "dev-conf-a1"
        assert row.room_id == "conference-a1"
        assert row.temperature == 21.5
        assert row.humidity == 50.0
        assert row.motion is True
        assert row.occupancy is True

    def test_timestamp_parsed(self, spark):
        df = to_dataframe(spark, SAMPLE_ITEMS)
        row = df.filter(df.event_id == "evt-001").collect()[0]
        assert row.ts.year == 2026
        assert row.ts.month == 1
        assert row.ts.day == 15

    def test_raw_payload_preserved(self, spark):
        df = to_dataframe(spark, SAMPLE_ITEMS)
        row = df.filter(df.event_id == "evt-001").collect()[0]
        payload = json.loads(row.raw_payload)
        assert payload["temperature"] == 21.5

    def test_empty_input_returns_empty_dataframe(self, spark):
        df = to_dataframe(spark, [])
        assert df.count() == 0

    def test_null_sensor_values_allowed(self, spark):
        items = [
            {
                "event_id": "evt-003",
                "device_id": "dev-test",
                "room_id": "test-room",
                "timestamp": "2026-01-15T12:00:00Z",
                "payload": json.dumps(
                    {"temperature": None, "humidity": None, "motion": False, "occupancy": False}
                ),
            }
        ]
        df = to_dataframe(spark, items)
        row = df.collect()[0]
        assert row.temperature is None
        assert row.humidity is None


class TestMain:
    ENV = {
        "S3_PARQUET_PATH": "s3://bucket/raw",
        "DYNAMODB_TABLE": "prod-SensorEvents",
        "AWS_REGION": "eu-central-1",
        "SPARK_MASTER": "local[*]",
    }

    def test_exits_if_s3_path_missing(self):
        env = {k: v for k, v in self.ENV.items() if k != "S3_PARQUET_PATH"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit):
                main()

    def test_exits_if_required_var_missing(self):
        env = {k: v for k, v in self.ENV.items() if k != "DYNAMODB_TABLE"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit):
                main()

    @patch("jobs.extract.write_parquet")
    @patch("jobs.extract.to_dataframe")
    @patch("jobs.extract.scan_dynamodb", return_value=[])
    @patch("jobs.extract.build_spark")
    def test_skips_write_if_no_items(self, _spark, _scan, _to_df, mock_write):
        with patch.dict(os.environ, self.ENV):
            main()
        mock_write.assert_not_called()

    @patch("jobs.extract.write_parquet")
    @patch("jobs.extract.to_dataframe")
    @patch("jobs.extract.scan_dynamodb", return_value=[{"event_id": "evt-1"}])
    @patch("jobs.extract.build_spark")
    def test_runs_full_pipeline(self, _spark, _scan, mock_to_df, mock_write):
        mock_df = MagicMock()
        mock_df.count.return_value = 1
        mock_to_df.return_value = mock_df
        with patch.dict(os.environ, self.ENV):
            main()
        mock_write.assert_called_once()


class TestScanDynamodb:
    def test_returns_items_from_single_page(self):
        mock_table = MagicMock()
        mock_table.scan.return_value = {"Items": SAMPLE_ITEMS}

        with patch("jobs.extract.boto3.resource") as mock_resource:
            mock_resource.return_value.Table.return_value = mock_table
            result = scan_dynamodb("prod-SensorEvents", "eu-central-1")

        assert result == SAMPLE_ITEMS

    def test_handles_pagination(self):
        page1 = {"Items": [SAMPLE_ITEMS[0]], "LastEvaluatedKey": {"event_id": "evt-001"}}
        page2 = {"Items": [SAMPLE_ITEMS[1]]}

        mock_table = MagicMock()
        mock_table.scan.side_effect = [page1, page2]

        with patch("jobs.extract.boto3.resource") as mock_resource:
            mock_resource.return_value.Table.return_value = mock_table
            result = scan_dynamodb("prod-SensorEvents", "eu-central-1")

        assert len(result) == 2
        assert mock_table.scan.call_count == 2

    def test_returns_empty_list_when_table_empty(self):
        mock_table = MagicMock()
        mock_table.scan.return_value = {"Items": []}

        with patch("jobs.extract.boto3.resource") as mock_resource:
            mock_resource.return_value.Table.return_value = mock_table
            result = scan_dynamodb("prod-SensorEvents", "eu-central-1")

        assert result == []
