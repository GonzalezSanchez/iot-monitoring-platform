import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from jobs.extract import to_dataframe
from jobs.transform import (
    TEMP_MAX,
    TEMP_MIN,
    main,
    validate_and_clean,
)


@pytest.fixture(scope="module")
def spark():
    from pyspark.sql import SparkSession

    return (
        SparkSession.builder.appName("test-transform")
        .master("local[1]")
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )


def _make_items(*overrides: dict) -> list[dict]:
    """Build DynamoDB-style items from per-row payload overrides."""
    base = {
        "temperature": 21.5,
        "humidity": 50.0,
        "motion": True,
        "occupancy": True,
    }
    items = []
    for i, override in enumerate(overrides, start=1):
        payload = {**base, **override}
        items.append(
            {
                "event_id": f"evt-{i:03d}",
                "device_id": f"dev-{i:03d}",
                "room_id": "room-a",
                "timestamp": "2026-01-15T10:00:00Z",
                "payload": json.dumps(payload),
            }
        )
    return items


class TestValidateAndClean:
    def test_valid_row_passes(self, spark):
        df = to_dataframe(spark, _make_items({}))
        result = validate_and_clean(df)
        assert result.count() == 1

    def test_invalid_temperature_high_filtered(self, spark):
        df = to_dataframe(spark, _make_items({"temperature": TEMP_MAX + 1}))
        assert validate_and_clean(df).count() == 0

    def test_invalid_temperature_low_filtered(self, spark):
        df = to_dataframe(spark, _make_items({"temperature": TEMP_MIN - 1}))
        assert validate_and_clean(df).count() == 0

    def test_null_temperature_filtered(self, spark):
        df = to_dataframe(spark, _make_items({"temperature": None}))
        assert validate_and_clean(df).count() == 0

    def test_invalid_humidity_high_filtered(self, spark):
        df = to_dataframe(spark, _make_items({"humidity": 101.0}))
        assert validate_and_clean(df).count() == 0

    def test_invalid_humidity_low_filtered(self, spark):
        df = to_dataframe(spark, _make_items({"humidity": -1.0}))
        assert validate_and_clean(df).count() == 0

    def test_null_humidity_filtered(self, spark):
        df = to_dataframe(spark, _make_items({"humidity": None}))
        assert validate_and_clean(df).count() == 0

    def test_columns_renamed(self, spark):
        df = to_dataframe(spark, _make_items({}))
        result = validate_and_clean(df)
        assert "temperature_c" in result.columns
        assert "humidity_pct" in result.columns
        assert "temperature" not in result.columns
        assert "humidity" not in result.columns

    def test_raw_payload_column_dropped(self, spark):
        df = to_dataframe(spark, _make_items({}))
        result = validate_and_clean(df)
        assert "raw_payload" not in result.columns

    def test_temperature_at_boundary_kept(self, spark):
        df = to_dataframe(spark, _make_items({"temperature": TEMP_MAX}))
        assert validate_and_clean(df).count() == 1

    def test_multiple_rows_mixed_validity(self, spark):
        items = _make_items(
            {"temperature": 22.0},
            {"temperature": 999.0},
            {"temperature": None},
            {"humidity": 200.0},
        )
        df = to_dataframe(spark, items)
        assert validate_and_clean(df).count() == 1

    def test_values_preserved_correctly(self, spark):
        df = to_dataframe(spark, _make_items({"temperature": 22.5, "humidity": 60.0}))
        row = validate_and_clean(df).collect()[0]
        assert row.temperature_c == 22.5
        assert row.humidity_pct == 60.0


class TestMain:
    ENV = {
        "S3_PARQUET_PATH": "s3://bucket/raw",
        "S3_PROCESSED_PATH": "s3://bucket/processed",
        "SPARK_MASTER": "local[*]",
    }

    def test_exits_if_env_var_missing(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(SystemExit):
                main()

    @patch("jobs.transform.write_processed")
    @patch("jobs.transform.validate_and_clean")
    @patch("jobs.transform.read_raw")
    @patch("jobs.transform.build_spark")
    def test_skips_write_if_raw_empty(self, _spark, mock_read, _validate, mock_write):
        mock_df = MagicMock()
        mock_df.count.return_value = 0
        mock_read.return_value = mock_df
        with patch.dict(os.environ, self.ENV):
            main()
        mock_write.assert_not_called()

    @patch("jobs.transform.write_processed")
    @patch("jobs.transform.validate_and_clean")
    @patch("jobs.transform.read_raw")
    @patch("jobs.transform.build_spark")
    def test_skips_write_if_all_filtered(self, _spark, mock_read, mock_validate, mock_write):
        mock_raw = MagicMock()
        mock_raw.count.return_value = 3
        mock_read.return_value = mock_raw
        mock_clean = MagicMock()
        mock_clean.count.return_value = 0
        mock_validate.return_value = mock_clean
        with patch.dict(os.environ, self.ENV):
            main()
        mock_write.assert_not_called()

    @patch("jobs.transform.write_processed")
    @patch("jobs.transform.validate_and_clean")
    @patch("jobs.transform.read_raw")
    @patch("jobs.transform.build_spark")
    def test_runs_full_pipeline(self, _spark, mock_read, mock_validate, mock_write):
        mock_raw = MagicMock()
        mock_raw.count.return_value = 5
        mock_read.return_value = mock_raw
        mock_clean = MagicMock()
        mock_clean.count.return_value = 4
        mock_validate.return_value = mock_clean
        with patch.dict(os.environ, self.ENV):
            main()
        mock_write.assert_called_once()
