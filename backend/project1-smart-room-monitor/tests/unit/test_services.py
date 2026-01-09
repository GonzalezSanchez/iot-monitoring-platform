"""
Unit tests for services
"""
import pytest
from datetime import datetime
from src.services.anomaly_detector import AnomalyDetector
from src.models.sensor_event import SensorEvent


class TestAnomalyDetector:
    """Test AnomalyDetector service"""

    def setup_method(self):
        """Setup test fixture"""
        self.detector = AnomalyDetector()
        self.fixed_time = datetime(2026, 1, 9, 12, 0, 0)

    @pytest.mark.parametrize(
        "value,expected_status,expected_phrase",
        [
            # Normal range
            (22.0, "normal", ""),
            (20.0, "normal", ""),
            (24.0, "normal", ""),
            # Edge cases - exact threshold values
            (18.0, "normal", ""),  # Exact min threshold
            (26.0, "normal", ""),  # Exact max threshold
            # Warning range
            (27.0, "warning", "above threshold"),
            (17.5, "warning", "below threshold"),
            (15.0, "warning", "below threshold"),
            # Edge cases for critical
            (
                10.0,
                "alert",
                "critically low",
            ),  # Exact critical_min (triggers alert with <=)
            (30.0, "alert", "critically high"),  # Exact critical_max
            # Critical range
            (31.0, "alert", "critically high"),
            (35.0, "alert", "critically high"),
            (9.9, "alert", "critically low"),
            (8.0, "alert", "critically low"),
            (5.0, "alert", "critically low"),
        ],
    )
    def test_temperature_thresholds(self, value, expected_status, expected_phrase):
        """Test temperature threshold detection with edge cases"""
        event = SensorEvent(
            room_id="room-a",
            sensor_type="temperature",
            value=value,
            timestamp=self.fixed_time,
        )

        status, message = self.detector.check_anomaly(event)

        assert status == expected_status
        if expected_phrase:
            assert expected_phrase in message.lower()
        else:
            assert message == ""

    @pytest.mark.parametrize(
        "value,expected_status,expected_phrase",
        [
            # Normal range
            (50.0, "normal", ""),
            (40.0, "normal", ""),
            (60.0, "normal", ""),
            # Edge cases - exact threshold values
            (30.0, "normal", ""),  # Exact min threshold
            (70.0, "normal", ""),  # Exact max threshold
            # Warning range
            (75.0, "warning", "above threshold"),
            (72.0, "warning", "above threshold"),
            (25.0, "warning", "below threshold"),
            (28.0, "warning", "below threshold"),
            # Edge case for critical
            (80.0, "alert", "critically high"),  # Exact critical_max
            # Critical range
            (85.0, "alert", "critically high"),
            (90.0, "alert", "critically high"),
        ],
    )
    def test_humidity_thresholds(self, value, expected_status, expected_phrase):
        """Test humidity threshold detection with edge cases"""
        event = SensorEvent(
            room_id="room-a",
            sensor_type="humidity",
            value=value,
            timestamp=self.fixed_time,
        )

        status, message = self.detector.check_anomaly(event)

        assert status == expected_status
        if expected_phrase:
            assert expected_phrase in message.lower()
            assert "humidity" in message.lower()
        else:
            assert message == ""

    @pytest.mark.parametrize(
        "value,expected_status,expected_phrase",
        [
            # Normal range
            (0, "normal", ""),
            (5, "normal", ""),
            (10, "normal", ""),
            (15, "normal", ""),
            (20, "normal", ""),  # Exact max threshold
            # Warning range
            (21, "warning", "above threshold"),
            (25, "warning", "above threshold"),
            (29, "warning", "above threshold"),
            # Edge case for critical
            (30, "alert", "critically high"),  # Exact critical_max
            # Critical range
            (35, "alert", "critically high"),
            (40, "alert", "critically high"),
        ],
    )
    def test_occupancy_thresholds(self, value, expected_status, expected_phrase):
        """Test occupancy threshold detection with edge cases and message validation"""
        event = SensorEvent(
            room_id="room-a",
            sensor_type="occupancy",
            value=value,
            timestamp=self.fixed_time,
        )

        status, message = self.detector.check_anomaly(event)

        assert status == expected_status
        if expected_phrase:
            assert expected_phrase in message.lower()
            assert "occupancy" in message.lower()
        else:
            assert message == ""

    def test_apply_anomaly_detection(self):
        """Test applying anomaly detection updates event status"""
        event = SensorEvent(
            room_id="room-a",
            sensor_type="temperature",
            value=28.0,
            timestamp=self.fixed_time,
        )

        updated_event = self.detector.apply_anomaly_detection(event)

        assert updated_event.status == "warning"

    def test_unknown_sensor_type(self):
        """Test unknown sensor type returns normal"""
        event = SensorEvent(
            room_id="room-a",
            sensor_type="motion",  # Motion has no thresholds
            value=1,
            timestamp=self.fixed_time,
        )

        status, message = self.detector.check_anomaly(event)

        assert status == "normal"
        assert message == ""
