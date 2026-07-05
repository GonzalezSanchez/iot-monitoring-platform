"""Per-device sliding-window rate limiter (docs/project3-prd.md §5.3).

In-memory on purpose: the gateway runs as a single container. A shared store
(the DynamoDB TTL pattern) is the 3a variant's approach and a documented
non-goal here.
"""

import time
from collections import defaultdict, deque
from typing import Deque, Dict


class RateLimiter:
    def __init__(self, default_per_minute: int, per_type: Dict[str, int], window_seconds: float = 60.0):
        self._default = default_per_minute
        self._per_type = per_type
        self._window = window_seconds
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)

    def limit_for(self, device_type: str) -> int:
        return self._per_type.get(device_type, self._default)

    def allow(self, device_id: str, device_type: str) -> bool:
        """Record one hit; False when the device exceeded its window limit."""
        now = time.monotonic()
        hits = self._hits[device_id]
        cutoff = now - self._window
        while hits and hits[0] <= cutoff:
            hits.popleft()
        if len(hits) >= self.limit_for(device_type):
            return False
        hits.append(now)
        return True

    def remaining(self, device_id: str, device_type: str) -> int:
        now = time.monotonic()
        hits = self._hits[device_id]
        cutoff = now - self._window
        while hits and hits[0] <= cutoff:
            hits.popleft()
        return max(0, self.limit_for(device_type) - len(hits))
