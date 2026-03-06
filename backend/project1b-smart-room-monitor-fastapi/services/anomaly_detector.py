"""
Anomaly Detector
Detects anomalies in sensor readings
"""
from typing import Dict, Tuple

from models.sensor_event import SensorEvent


class AnomalyDetector:
    """Detects anomalies in sensor data"""

    STATUS_SEVERITY: Dict[str, int] = {"normal": 0, "warning": 1, "alert": 2}
    SENSOR_UNITS: Dict[str, str] = {
        "temperature": "°C",
        "humidity": "%",
        "occupancy": "people",
    }
    THRESHOLDS: Dict[str, Dict[str, float]] = {
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
        "occupancy": {"min": 0.0, "max": 20.0, "critical_max": 30.0},
    }

    def check_anomaly(self, event: SensorEvent) -> Tuple[str, str]:
        """
        Check if event contains anomaly.
        Returns: (status, message) where status is 'normal', 'warning', or 'alert'
        and message describes the anomaly (empty string if normal).
        """
        sensor_type: str = event.sensor_type
        value: float = event.value

        if sensor_type not in self.THRESHOLDS:
            return "normal", ""

        thresholds: Dict[str, float] = self.THRESHOLDS[sensor_type]
        unit: str = self.SENSOR_UNITS.get(sensor_type, "")

        # Check critical thresholds first (highest priority)
        if "critical_max" in thresholds and value >= thresholds["critical_max"]:
            return "alert", (
                f"{sensor_type} critically high "
                f"({value}{unit} >= {thresholds['critical_max']}{unit})"
            )

        if "critical_min" in thresholds and value <= thresholds["critical_min"]:
            return "alert", (
                f"{sensor_type} critically low "
                f"({value}{unit} <= {thresholds['critical_min']}{unit})"
            )

        # Check warning thresholds
        if "max" in thresholds and value > thresholds["max"]:
            return "warning", (
                f"{sensor_type} above threshold "
                f"({value}{unit} > {thresholds['max']}{unit})"
            )

        if "min" in thresholds and value < thresholds["min"]:
            return "warning", (
                f"{sensor_type} below threshold "
                f"({value}{unit} < {thresholds['min']}{unit})"
            )

        return "normal", ""

    def apply_anomaly_detection(self, event: SensorEvent) -> SensorEvent:
        """
        Apply anomaly detection and update event status.
        Only escalates status, never downgrades (normal < warning < alert).
        """
        detected_status, _ = self.check_anomaly(event)

        current_severity = self.STATUS_SEVERITY.get(event.status, 0)
        detected_severity = self.STATUS_SEVERITY.get(detected_status, 0)

        if detected_severity > current_severity:
            event.status = detected_status

        return event
