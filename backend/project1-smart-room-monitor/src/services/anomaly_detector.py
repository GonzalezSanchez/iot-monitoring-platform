"""
Anomaly Detector
Detects anomalies in sensor readings
"""
import logging
from typing import Tuple
from src.models.sensor_event import SensorEvent

# Configure logger
logger = logging.getLogger(__name__)


class AnomalyDetector:
    """Detects anomalies in sensor data"""

    # Status severity levels for proper escalation
    # Higher number = more severe
    STATUS_SEVERITY = {"normal": 0, "warning": 1, "alert": 2}

    # Units for better messaging
    SENSOR_UNITS = {"temperature": "°C", "humidity": "%", "occupancy": "people"}

    # Threshold configurations
    # Note: Check critical thresholds first for proper alert priority
    THRESHOLDS = {
        "temperature": {
            "critical_min": 10.0,
            "min": 18.0,
            "max": 26.0,
            "critical_max": 30.0,
        },
        "humidity": {
            "critical_min": 20.0,
            "min": 30.0,
            "max": 70.0,
            "critical_max": 80.0,
        },
        "occupancy": {"min": 0, "max": 20, "critical_max": 30},
    }

    def check_anomaly(self, event: SensorEvent) -> Tuple[str, str]:
        """
        Check if event contains anomaly
        Returns: (status, message with detailed threshold info)
        """
        sensor_type = event.sensor_type
        value = event.value

        # Only numeric sensors support threshold-based anomaly detection
        # Motion sensors (bool) and other non-numeric types are skipped
        if not isinstance(value, (int, float)):
            logger.debug(
                f"Skipping threshold check for non-numeric sensor: {sensor_type}"
            )
            return "normal", ""

        if sensor_type not in self.THRESHOLDS:
            return "normal", ""

        thresholds = self.THRESHOLDS[sensor_type]
        unit = self.SENSOR_UNITS.get(sensor_type, "")

        # Check critical thresholds first (highest priority)
        if "critical_max" in thresholds and value >= thresholds["critical_max"]:
            return "alert", (
                f"{sensor_type} critically high "
                f'({value}{unit} ≥ {thresholds["critical_max"]}{unit})'
            )

        if "critical_min" in thresholds and value <= thresholds["critical_min"]:
            return "alert", (
                f"{sensor_type} critically low "
                f'({value}{unit} ≤ {thresholds["critical_min"]}{unit})'
            )

        # Check warning thresholds
        if "max" in thresholds and value > thresholds["max"]:
            return "warning", (
                f"{sensor_type} above threshold "
                f'({value}{unit} > {thresholds["max"]}{unit})'
            )

        if "min" in thresholds and value < thresholds["min"]:
            return "warning", (
                f"{sensor_type} below threshold "
                f'({value}{unit} < {thresholds["min"]}{unit})'
            )

        return "normal", ""

    def apply_anomaly_detection(self, event: SensorEvent) -> SensorEvent:
        """
        Apply anomaly detection and update event status
        Only escalates status, never downgrades (normal < warning < alert)
        """
        detected_status, message = self.check_anomaly(event)

        # Only upgrade status if detected status is more severe
        # Prevents downgrading from alert → warning or warning → normal
        current_severity = self.STATUS_SEVERITY.get(event.status, 0)
        detected_severity = self.STATUS_SEVERITY.get(detected_status, 0)

        if detected_severity > current_severity:
            event.status = detected_status
            logger.info(
                f"Status escalated to '{detected_status}' for {event.sensor_type}"
            )

        # Log anomalies for monitoring and debugging
        if message:
            logger.warning(f"Anomaly detected: {message}")

        return event
