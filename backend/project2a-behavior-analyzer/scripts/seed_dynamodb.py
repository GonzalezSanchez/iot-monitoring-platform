#!/usr/bin/env python3
"""
seed_dynamodb.py — populate prod-SensorEvents with 30 days of realistic data.

Writes events in the format expected by the project 2a extract Lambda:
  event_id  : UUID string
  device_id : string
  room_id   : string
  ts        : ISO-8601 UTC string  ("2026-01-09T14:30:00Z")
  payload   : JSON string { temperature, humidity, motion, occupancy }

Run from the project root:
  python backend/project2a-behavior-analyzer/scripts/seed_dynamodb.py

Options:
  --days     Number of days of history to generate (default: 30)
  --interval Minutes between readings per room    (default: 30)
  --table    DynamoDB table name                  (default: prod-SensorEvents)
  --region   AWS region                           (default: eu-central-1)
  --dry-run  Print stats without writing to AWS
"""

import argparse
import json
import math
import random
import uuid
from datetime import UTC, datetime, timedelta

import boto3

# ─────────────────────────────────────────────────────────────────────────────
# Room profiles
# Each room has a distinct personality that the analyzer should detect.
# ─────────────────────────────────────────────────────────────────────────────

ROOMS: dict[str, dict] = {
    "conference-a1": {
        "device_id": "dev-conf-a1",
        # Occupied Mon–Fri 8–18
        "occupied_weekdays": {0, 1, 2, 3, 4},
        "occupied_hours": set(range(8, 18)),
        "temp_mean": 21.0,
        "temp_std": 1.2,
        "humidity_mean": 50.0,
        "humidity_std": 4.0,
        "occupancy_during_hours": 0.85,  # probability of being occupied during work hours
        "occupancy_outside_hours": 0.02,
    },
    "conference-b2": {
        "device_id": "dev-conf-b2",
        # Occupied Mon–Fri 9–17
        "occupied_weekdays": {0, 1, 2, 3, 4},
        "occupied_hours": set(range(9, 17)),
        "temp_mean": 22.0,
        "temp_std": 1.0,
        "humidity_mean": 48.0,
        "humidity_std": 3.5,
        "occupancy_during_hours": 0.80,
        "occupancy_outside_hours": 0.02,
    },
    "meeting-room-c3": {
        "device_id": "dev-meet-c3",
        # Sporadic usage — short blocks during the day
        "occupied_weekdays": {0, 1, 2, 3, 4},
        "occupied_hours": set(range(9, 19)),
        "temp_mean": 20.5,
        "temp_std": 1.5,
        "humidity_mean": 52.0,
        "humidity_std": 5.0,
        "occupancy_during_hours": 0.40,  # sporadic — only used part of the time
        "occupancy_outside_hours": 0.01,
    },
    "lab-d4": {
        "device_id": "dev-lab-d4",
        # Extended hours Mon–Sat 7–22
        "occupied_weekdays": {0, 1, 2, 3, 4, 5},
        "occupied_hours": set(range(7, 22)),
        "temp_mean": 19.0,
        "temp_std": 2.0,
        "humidity_mean": 55.0,
        "humidity_std": 6.0,
        "occupancy_during_hours": 0.70,
        "occupancy_outside_hours": 0.05,  # researchers sometimes work late
    },
    "server-room-e5": {
        "device_id": "dev-srv-e5",
        # 24/7 — servers always running, AC keeps it cool
        "occupied_weekdays": {0, 1, 2, 3, 4, 5, 6},
        "occupied_hours": set(range(0, 24)),
        "temp_mean": 18.0,
        "temp_std": 2.5,  # AC fluctuations
        "humidity_mean": 40.0,
        "humidity_std": 3.0,
        "occupancy_during_hours": 0.95,  # servers = always motion
        "occupancy_outside_hours": 0.95,
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# Generation helpers
# ─────────────────────────────────────────────────────────────────────────────


def _is_occupied(room: dict, dt: datetime) -> bool:
    weekday = dt.weekday()
    hour = dt.hour
    in_schedule = weekday in room["occupied_weekdays"] and hour in room["occupied_hours"]
    prob = room["occupancy_during_hours"] if in_schedule else room["occupancy_outside_hours"]
    return random.random() < prob


def _temperature(room: dict, dt: datetime, spike: bool = False) -> float:
    base = random.gauss(room["temp_mean"], room["temp_std"])
    if spike:
        # Push it > 3 stddev above mean so the analyzer flags it
        direction = random.choice([1, -1])
        base = room["temp_mean"] + direction * room["temp_std"] * random.uniform(3.5, 5.0)
    # Slight circadian variation: warmer during work hours
    hour_factor = math.sin((dt.hour - 6) * math.pi / 12) * 0.8
    return round(base + hour_factor, 1)


def _humidity(room: dict) -> float:
    return round(random.gauss(room["humidity_mean"], room["humidity_std"]), 1)


def _make_event(room_id: str, room: dict, dt: datetime, spike: bool = False) -> dict:
    occupied = _is_occupied(room, dt)
    return {
        "event_id": str(uuid.uuid4()),
        "device_id": room["device_id"],
        "room_id": room_id,
        "timestamp": dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "payload": json.dumps(
            {
                "temperature": _temperature(room, dt, spike=spike),
                "humidity": _humidity(room),
                "motion": occupied,
                "occupancy": occupied,
            }
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Spike injection
# ─────────────────────────────────────────────────────────────────────────────


def _inject_spikes(
    events_by_room: dict[str, list[dict]],
    rooms: dict[str, dict],
    spikes_per_room: int = 4,
) -> None:
    """Replace a handful of readings with temperature spikes."""
    for room_id, events in events_by_room.items():
        indices = random.sample(range(len(events)), min(spikes_per_room, len(events)))
        for i in indices:
            ev = events[i]
            ts = datetime.strptime(ev["timestamp"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
            payload = json.loads(ev["payload"])
            payload["temperature"] = _temperature(rooms[room_id], ts, spike=True)
            ev["payload"] = json.dumps(payload)


def _inject_unusual_activity(
    events_by_room: dict[str, list[dict]],
    rooms: dict[str, dict],
    events_per_room: int = 3,
) -> None:
    """Force motion=True on readings that fall outside the normal occupancy window."""
    for room_id, events in events_by_room.items():
        room = rooms[room_id]
        outside = [
            i
            for i, ev in enumerate(events)
            if not (
                datetime.strptime(ev["timestamp"], "%Y-%m-%dT%H:%M:%SZ").weekday()
                in room["occupied_weekdays"]
                and datetime.strptime(ev["timestamp"], "%Y-%m-%dT%H:%M:%SZ").hour
                in room["occupied_hours"]
            )
        ]
        if not outside:
            continue
        for i in random.sample(outside, min(events_per_room, len(outside))):
            payload = json.loads(events[i]["payload"])
            payload["motion"] = True
            payload["occupancy"] = True
            events[i]["payload"] = json.dumps(payload)


# ─────────────────────────────────────────────────────────────────────────────
# DynamoDB writer
# ─────────────────────────────────────────────────────────────────────────────


def _write_to_dynamodb(events: list[dict], table_name: str, region: str) -> None:
    dynamodb = boto3.resource("dynamodb", region_name=region)
    table = dynamodb.Table(table_name)

    total = len(events)
    written = 0

    with table.batch_writer() as batch:
        for ev in events:
            batch.put_item(Item=ev)
            written += 1
            if written % 500 == 0:
                print(f"  {written}/{total} written...")

    print(f"  {written}/{total} written.")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────


def generate(days: int, interval_minutes: int) -> dict[str, list[dict]]:
    now = datetime.now(tz=UTC).replace(minute=0, second=0, microsecond=0)
    start = now - timedelta(days=days)

    events_by_room: dict[str, list[dict]] = {room_id: [] for room_id in ROOMS}

    dt = start
    while dt <= now:
        for room_id, room in ROOMS.items():
            events_by_room[room_id].append(_make_event(room_id, room, dt))
        dt += timedelta(minutes=interval_minutes)

    return events_by_room


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed prod-SensorEvents with historical data")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--interval", type=int, default=30, help="Minutes between readings")
    parser.add_argument("--table", default="prod-SensorEvents")
    parser.add_argument("--region", default="eu-central-1")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print(
        f"Generating {args.days} days of data "
        f"({args.interval}min intervals) for {len(ROOMS)} rooms..."
    )

    events_by_room = generate(args.days, args.interval)

    _inject_spikes(events_by_room, ROOMS, spikes_per_room=4)
    _inject_unusual_activity(events_by_room, ROOMS, events_per_room=3)

    all_events = [ev for evs in events_by_room.values() for ev in evs]
    total = len(all_events)

    print("\nSummary:")
    for room_id, evs in events_by_room.items():
        print(f"  {room_id}: {len(evs)} events")
    print(f"  Total: {total} events")
    print(f"  Date range: {all_events[0]['timestamp']} → {all_events[-1]['timestamp']}")

    if args.dry_run:
        print("\nDry run — nothing written to DynamoDB.")
        return

    print(f"\nWriting to DynamoDB table '{args.table}' in {args.region}...")
    _write_to_dynamodb(all_events, args.table, args.region)
    print("Done.")


if __name__ == "__main__":
    main()
