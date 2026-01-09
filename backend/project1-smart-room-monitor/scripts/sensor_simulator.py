#!/usr/bin/env python3
"""
Sensor Simulator
Simulates IoT sensors sending data to the Smart Room Monitor API
"""
import random
import time
from datetime import datetime
from typing import Optional
import requests


class SensorSimulator:
    """Simulates IoT sensor devices"""

    def __init__(
        self,
        api_url: str = "http://localhost:8080",
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        self.api_url = api_url
        self.rooms = ["room-001", "room-002", "room-003"]
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.failed_events = 0
        self.successful_events = 0

    def generate_temperature_reading(self) -> float:
        """Generate realistic temperature reading"""
        # Normal distribution around 22°C
        return round(random.gauss(22.0, 2.0), 1)

    def generate_humidity_reading(self) -> float:
        """Generate realistic humidity reading"""
        return round(random.uniform(40.0, 65.0), 1)

    def generate_occupancy_reading(self) -> int:
        """Generate realistic occupancy count"""
        hour = datetime.now().hour

        # Simulate office hours pattern
        if 9 <= hour <= 17:
            return random.randint(0, 15)
        elif 18 <= hour <= 21:
            return random.randint(0, 5)
        else:
            return 0

    def generate_motion_reading(self, occupancy: int) -> bool:
        """Generate motion based on occupancy"""
        return occupancy > 0

    def check_api_health(self) -> bool:
        """Check if API is reachable"""
        try:
            response = requests.get(f"{self.api_url}/health", timeout=5)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def send_event(self, event_data: dict) -> Optional[dict]:
        """
        Send event to API with retry logic and exponential backoff

        Returns:
            Response dict if successful, None if failed after retries
        """
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    f"{self.api_url}/events",
                    json=event_data,
                    headers={"Content-Type": "application/json"},
                    timeout=10,
                )
                response.raise_for_status()
                self.successful_events += 1
                return response.json()

            except requests.exceptions.HTTPError as e:
                # Log HTTP errors with detail
                status_code = e.response.status_code if e.response else "N/A"
                try:
                    error_body = e.response.json() if e.response else {}
                except ValueError:
                    error_body = e.response.text if e.response else ""

                print(
                    f"⚠️  HTTP {status_code} error "
                    f"(attempt {attempt + 1}/{self.max_retries}): {error_body}"
                )

                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2**attempt)
                    time.sleep(delay)
                else:
                    self.failed_events += 1

            except requests.exceptions.RequestException as e:
                print(
                    f"⚠️  Connection error "
                    f"(attempt {attempt + 1}/{self.max_retries}): {e}"
                )

                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2**attempt)
                    time.sleep(delay)
                else:
                    self.failed_events += 1

        return None

    def simulate_room_cycle(self, room_id: str):
        """Simulate one cycle of sensor readings for a room"""
        timestamp = datetime.now().isoformat()

        # Generate readings
        temperature = self.generate_temperature_reading()
        humidity = self.generate_humidity_reading()
        occupancy = self.generate_occupancy_reading()
        motion = self.generate_motion_reading(occupancy)

        # Send temperature event
        self.send_event(
            {
                "room_id": room_id,
                "sensor_type": "temperature",
                "value": temperature,
                "timestamp": timestamp,
            }
        )

        # Send humidity event
        self.send_event(
            {
                "room_id": room_id,
                "sensor_type": "humidity",
                "value": humidity,
                "timestamp": timestamp,
            }
        )

        # Send occupancy event
        self.send_event(
            {
                "room_id": room_id,
                "sensor_type": "occupancy",
                "value": occupancy,
                "timestamp": timestamp,
            }
        )

        # Send motion event
        self.send_event(
            {
                "room_id": room_id,
                "sensor_type": "motion",
                "value": 1 if motion else 0,
                "timestamp": timestamp,
            }
        )

        print(
            f"[{room_id}] T:{temperature}°C H:{humidity}% "
            f"O:{occupancy} M:{motion}"
        )

    def run(self, duration_seconds: int = 300, interval_seconds: int = 10):
        """
        Run simulator for specified duration

        Args:
            duration_seconds: How long to run (default: 5 minutes)
            interval_seconds: Delay between cycles (default: 10 seconds)
        """
        print(f"Starting sensor simulator for {len(self.rooms)} rooms")
        print(f"API URL: {self.api_url}")
        print(f"Duration: {duration_seconds}s, Interval: {interval_seconds}s")
        print("-" * 60)

        # Check API health before starting
        print("Checking API health...")
        if not self.check_api_health():
            print(
                "⚠️  Warning: API health check failed. "
                "Events may not be delivered."
            )
            print("Continuing anyway...")
        else:
            print("✅ API is reachable\n")

        end_time = time.time() + duration_seconds
        cycle_count = 0

        while time.time() < end_time:
            cycle_count += 1
            print(f"\n--- Cycle {cycle_count} ---")

            # Simulate all rooms
            for room_id in self.rooms:
                self.simulate_room_cycle(room_id)

            # Wait before next cycle
            time.sleep(interval_seconds)

        # Print statistics
        total_events = self.successful_events + self.failed_events
        success_rate = (
            (self.successful_events / total_events * 100)
            if total_events > 0
            else 0
        )

        print(f"\n{'=' * 60}")
        print("Simulation complete!")
        print(f"Total cycles: {cycle_count}")
        print(f"Successful events: {self.successful_events}")
        print(f"Failed events: {self.failed_events}")
        print(f"Success rate: {success_rate:.1f}%")
        print("=" * 60)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Simulate IoT sensors sending data to Smart Room Monitor API"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run for 60 seconds with 5 second intervals
  python sensor_simulator.py --duration 60 --interval 5

  # Use LocalStack API Gateway (adjust URL as needed)
  python sensor_simulator.py --api-url \
    http://localhost:4566/restapis/xxx/dev/_user_request_

  # Run with custom retry settings
  python sensor_simulator.py --max-retries 5 --retry-delay 2
        """,
    )
    parser.add_argument(
        "--api-url",
        default="http://localhost:8080",
        help="API URL (default: http://localhost:8080)",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=300,
        help="Duration in seconds (default: 300)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=10,
        help="Interval between readings in seconds (default: 10)",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Max retry attempts per request (default: 3)",
    )
    parser.add_argument(
        "--retry-delay",
        type=float,
        default=1.0,
        help="Initial retry delay in seconds (default: 1.0)",
    )

    args = parser.parse_args()

    simulator = SensorSimulator(
        api_url=args.api_url,
        max_retries=args.max_retries,
        retry_delay=args.retry_delay,
    )
    simulator.run(
        duration_seconds=args.duration, interval_seconds=args.interval
    )
