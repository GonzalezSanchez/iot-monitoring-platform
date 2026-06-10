"""Sensor data generator — writes simulated IoT sensor events as JSON to ADLS Gen2 Bronze.

Usage:
    # Print to stdout (dev/test, no dependencies needed):
    python scripts/generate_sensor_data.py --count 100

    # Write to local directory (mirrors production path structure, no Azure needed):
    python scripts/generate_sensor_data.py --count 100 --output-dir /tmp/bronze

    # Write to ADLS Gen2 Bronze container:
    #   Local: requires 'az login' beforehand (DefaultAzureCredential picks it up)
    #   Databricks Job: uses Access Connector Managed Identity automatically
    python scripts/generate_sensor_data.py --count 1000 --adls

Environment variables (see .env.example):
    AZURE_STORAGE_ACCOUNT_NAME     -- storage account created by Terraform
    AZURE_STORAGE_CONTAINER_BRONZE -- defaults to "bronze"
"""

import argparse
import json
import os
import random
import uuid
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

SENSOR_TYPES = ["temperature", "co2", "occupancy", "humidity"]
ROOMS = [f"room_{i:03d}" for i in range(1, 11)]

VALUE_RANGES: dict[str, tuple[float, float]] = {
    "temperature": (18.0, 26.0),
    "co2": (400.0, 1200.0),
    "occupancy": (0.0, 20.0),
    "humidity": (30.0, 70.0),
}


def generate_event() -> dict[str, object]:
    sensor_type = random.choice(SENSOR_TYPES)
    lo, hi = VALUE_RANGES[sensor_type]
    return {
        "event_id": str(uuid.uuid4()),
        "room_id": random.choice(ROOMS),
        "sensor_type": sensor_type,
        "value": round(random.uniform(lo, hi), 2),
        "timestamp": datetime.now(UTC).isoformat(),
    }


def make_blob_path(batch_ts: datetime) -> str:
    """Return the Hive-partitioned ADLS blob path for a batch.

    Format: year=YYYY/month=MM/day=DD/sensors_YYYYMMDDTHHmmss.json
    This structure lets Auto Loader do efficient incremental reads per day-partition.
    """
    return (
        f"year={batch_ts.year:04d}/"
        f"month={batch_ts.month:02d}/"
        f"day={batch_ts.day:02d}/"
        f"sensors_{batch_ts.strftime('%Y%m%dT%H%M%S')}.json"
    )


def write_to_adls(
    events: list[dict[str, object]],
    account_name: str,
    container: str,
) -> str:
    """Upload a batch of events as newline-delimited JSON to ADLS Gen2.

    Authentication via DefaultAzureCredential:
    - Local dev: picks up 'az login' credentials automatically
    - Databricks Job: picks up Access Connector Managed Identity automatically
    No storage keys or tokens needed in either case.
    """
    from azure.identity import DefaultAzureCredential
    from azure.storage.blob import BlobServiceClient

    batch_ts = datetime.now(UTC)
    blob_path = make_blob_path(batch_ts)
    payload = "\n".join(json.dumps(e) for e in events)

    account_url = f"https://{account_name}.blob.core.windows.net"
    client = BlobServiceClient(account_url=account_url, credential=DefaultAzureCredential())
    blob_client = client.get_blob_client(container=container, blob=blob_path)
    blob_client.upload_blob(payload, overwrite=True)

    abfss_path = f"abfss://{container}@{account_name}.dfs.core.windows.net/{blob_path}"
    print(f"Wrote {len(events)} events to {abfss_path}")
    return abfss_path


def write_to_dir(events: list[dict[str, object]], output_dir: Path) -> None:
    """Write a batch as newline-delimited JSON using the same partitioned structure as ADLS."""
    batch_ts = datetime.now(UTC)
    blob_path = make_blob_path(batch_ts)
    output_path = output_dir / Path(blob_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        for event in events:
            f.write(json.dumps(event) + "\n")
    print(f"Wrote {len(events)} events to {output_path}")


def main(count: int, output_dir: str | None, use_adls: bool = False) -> None:
    events = [generate_event() for _ in range(count)]

    if use_adls:
        account_name = os.environ["AZURE_STORAGE_ACCOUNT_NAME"]
        container = os.environ.get("AZURE_STORAGE_CONTAINER_BRONZE", "bronze")
        write_to_adls(events, account_name, container)
    elif output_dir:
        write_to_dir(events, Path(output_dir))
    else:
        for event in events:
            print(json.dumps(event))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate simulated IoT sensor events")
    parser.add_argument("--count", type=int, default=100, help="Number of events to generate")
    parser.add_argument("--output-dir", type=str, default=None, help="Write to local directory")
    parser.add_argument(
        "--adls",
        action="store_true",
        help="Write to ADLS Gen2 (requires az login or Managed Identity)",
    )
    args = parser.parse_args()
    main(args.count, args.output_dir, args.adls)
