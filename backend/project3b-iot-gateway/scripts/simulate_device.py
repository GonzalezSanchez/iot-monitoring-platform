"""Device simulator — N devices sending sensor readings through the gateway.

Each simulated device registers itself (fresh IDs per run — API keys are shown
exactly once, so a rerun cannot re-auth old devices), exchanges its key for a
JWT, and posts readings at a configurable rate. Tokens are refreshed before
expiry and on 401. 429s (rate limit) are counted, never treated as errors —
proving the limiter is part of the point.

Runs against the gateway from inside the Docker network (production is
internal-only) or against a local compose stack:

    python scripts/simulate_device.py --gateway http://localhost:8002 \
        --devices 5 --rate 12 --duration 60
"""

import argparse
import asyncio
import json
import random
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class DeviceStats:
    sent: int = 0
    accepted: int = 0
    rate_limited: int = 0
    errors: dict = field(default_factory=dict)


class SimulatedDevice:
    def __init__(self, gateway: str, device_id: str, device_type: str, location: str):
        self.gateway = gateway
        self.device_id = device_id
        self.device_type = device_type
        self.location = location
        self.api_key = ""
        self.token = ""
        self.token_expires_at = 0.0
        self.temperature = random.uniform(18.0, 24.0)
        self.stats = DeviceStats()

    def _post(self, path: str, body: dict, token: str | None = None) -> tuple[int, dict]:
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(
            self.gateway + path, method="POST", data=json.dumps(body).encode(), headers=headers
        )
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    async def post(self, path: str, body: dict, token: str | None = None) -> tuple[int, dict]:
        return await asyncio.to_thread(self._post, path, body, token)

    async def register_and_auth(self) -> None:
        status, resp = await self.post(
            "/devices/register",
            {
                "device_id": self.device_id,
                "device_type": self.device_type,
                "metadata": {"location": self.location},
            },
        )
        if status != 201:
            raise RuntimeError(f"{self.device_id}: register failed ({status}: {resp})")
        self.api_key = resp["api_key"]
        await self.refresh_token()

    async def refresh_token(self) -> None:
        status, resp = await self.post(
            f"/devices/{self.device_id}/auth", {"api_key": self.api_key}
        )
        if status != 200:
            raise RuntimeError(f"{self.device_id}: auth failed ({status}: {resp})")
        self.token = resp["access_token"]
        # refresh 60s before the server-side expiry
        self.token_expires_at = time.monotonic() + resp["expires_in"] - 60

    def _reading(self) -> dict:
        # small random walk keeps the dashboard lively without absurd values
        self.temperature = min(30.0, max(15.0, self.temperature + random.uniform(-0.3, 0.3)))
        return {"temperature": round(self.temperature, 2), "humidity": random.randint(35, 65)}

    async def send_one(self) -> None:
        if time.monotonic() >= self.token_expires_at:
            await self.refresh_token()
        status, _ = await self.post(
            "/messages",
            {
                "device_id": self.device_id,
                "payload": self._reading(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            token=self.token,
        )
        self.stats.sent += 1
        if status == 202:
            self.stats.accepted += 1
        elif status == 429:
            self.stats.rate_limited += 1
        elif status == 401:  # token raced its expiry — refresh and count as retryable
            await self.refresh_token()
            self.stats.errors[401] = self.stats.errors.get(401, 0) + 1
        else:
            self.stats.errors[status] = self.stats.errors.get(status, 0) + 1

    async def run(self, rate_per_minute: int, duration: float) -> None:
        interval = 60.0 / rate_per_minute
        deadline = time.monotonic() + duration
        while time.monotonic() < deadline:
            started = time.monotonic()
            await self.send_one()
            await asyncio.sleep(max(0.0, interval - (time.monotonic() - started)))


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--gateway", default="http://localhost:8002", help="gateway base URL")
    parser.add_argument("--devices", type=int, default=5, help="number of simulated devices")
    parser.add_argument("--rate", type=int, default=12, help="messages per minute per device")
    parser.add_argument("--duration", type=float, default=60.0, help="seconds to run")
    parser.add_argument("--device-type", default="temperature_sensor")
    parser.add_argument(
        "--rooms", type=int, default=3, help="devices are spread over this many rooms"
    )
    args = parser.parse_args()

    run_id = time.strftime("%H%M%S")
    devices = [
        SimulatedDevice(
            args.gateway,
            device_id=f"sim-{run_id}-{i:03d}",
            device_type=args.device_type,
            location=f"room-sim-{i % args.rooms}",
        )
        for i in range(args.devices)
    ]

    print(f"registering {len(devices)} devices (run {run_id}) against {args.gateway} …")
    await asyncio.gather(*(d.register_and_auth() for d in devices))
    print(f"sending at {args.rate} msg/min per device for {args.duration:.0f}s …")
    await asyncio.gather(*(d.run(args.rate, args.duration) for d in devices))

    print(f"\n{'device':<16} {'sent':>5} {'202':>5} {'429':>5}  errors")
    totals = DeviceStats()
    for d in devices:
        s = d.stats
        print(f"{d.device_id:<16} {s.sent:>5} {s.accepted:>5} {s.rate_limited:>5}  {s.errors or ''}")
        totals.sent += s.sent
        totals.accepted += s.accepted
        totals.rate_limited += s.rate_limited
    print(f"{'TOTAL':<16} {totals.sent:>5} {totals.accepted:>5} {totals.rate_limited:>5}")


if __name__ == "__main__":
    asyncio.run(main())
