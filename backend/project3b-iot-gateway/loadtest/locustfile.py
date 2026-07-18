"""Locust load tests — the three scenarios from docs/project3b-iot-gateway.md.

Rate limiting is only credible if you can prove it (docs/project3-prd.md §7 3b-3):

1. normal    — steady devices under the limit → everything 202
2. ratelimit — one device hammering far over the limit → 429 past the threshold
3. isolation — 1 aggressive device + 9 steady ones → only the aggressor sees 429

Each Locust user is one device: it registers itself on start (fresh ID per run),
authenticates, and posts readings. A 429 on an aggressive device is a PASS (the
limiter works); a 429 on a steady device is a FAIL (cross-device impact).

Run (gateway reachable on --host, e.g. the local compose stack):

    locust -f loadtest/locustfile.py --host http://localhost:8002 \
        --headless -u 10 -r 10 -t 90s --tags normal
    locust -f loadtest/locustfile.py --host http://localhost:8002 \
        --headless -u 10 -r 10 -t 90s --tags isolation

For a `ratelimit`-only run, select the class explicitly instead of --tags:
at -u 1, Locust's tag filter can end up spawning zero matching tasks even
though only one class carries the tag (observed during the 2026-07-17
acceptance run — register/auth fired but no /messages requests were sent).

    locust -f loadtest/locustfile.py AggressiveDevice --host http://localhost:8002 \
        --headless -u 1 -r 1 -t 90s
"""

import random
import time
from datetime import datetime, timezone

from locust import HttpUser, between, constant, tag, task

RUN_ID = time.strftime("%H%M%S")
_COUNTER = iter(range(10_000))


class _Device(HttpUser):
    """Shared device behaviour: self-register, auth, send readings."""

    abstract = True
    device_type = "temperature_sensor"  # rate limit: 60/min (config/rate_limits.yml)
    expect_rate_limit = False

    def on_start(self):
        self.device_id = f"loc-{RUN_ID}-{next(_COUNTER):04d}"
        resp = self.client.post(
            "/devices/register",
            json={
                "device_id": self.device_id,
                "device_type": self.device_type,
                "metadata": {"location": f"room-loadtest-{RUN_ID}"},
            },
        )
        resp.raise_for_status()
        auth = self.client.post(
            f"/devices/{self.device_id}/auth", json={"api_key": resp.json()["api_key"]}
        )
        auth.raise_for_status()
        self.token = auth.json()["access_token"]

    def send_reading(self):
        with self.client.post(
            "/messages",
            json={
                "device_id": self.device_id,
                "payload": {"temperature": round(random.uniform(18, 26), 2)},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            headers={"Authorization": f"Bearer {self.token}"},
            catch_response=True,
            name=f"/messages [{type(self).__name__}]",
        ) as resp:
            if resp.status_code == 202:
                resp.success()
            elif resp.status_code == 429 and self.expect_rate_limit:
                resp.success()  # the limiter doing its job IS the pass criterion
            elif resp.status_code == 429:
                resp.failure("rate-limited although under the limit (cross-device impact!)")
            else:
                resp.failure(f"unexpected {resp.status_code}")


@tag("normal", "isolation")
class SteadyDevice(_Device):
    """1 request/second — under the 60/min limit, must never see a 429."""

    weight = 9
    wait_time = constant(1)

    @task
    def reading(self):
        self.send_reading()


@tag("ratelimit", "isolation")
class AggressiveDevice(_Device):
    """~200 requests/minute — must hit 429 once past the 60/min threshold."""

    weight = 1
    expect_rate_limit = True
    wait_time = between(0.2, 0.4)

    @task
    def reading(self):
        self.send_reading()
