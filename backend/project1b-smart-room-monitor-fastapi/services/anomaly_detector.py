"""
Anomaly Detector
Detects anomalies in sensor readings
"""
from typing import Tuple

from models.sensor_event import SensorEvent


class AnomalyDetector:
    """Detects anomalies in sensor data"""

    STATUS_SEVERITY = {"normal": 0, "warning": 1, "alert": 2}
    SENSOR_UNITS = {"temperature": "°C", "humidity": "%", "occupancy": "people"}
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
        # TODO: Implement anomaly detection logic
        raise NotImplementedError("Anomaly detection logic not yet implemented.")
