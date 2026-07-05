"""Rate limiter unit tests (docs/project3-prd.md §5.3)."""

from gateway.rate_limiter import RateLimiter


def test_blocks_at_limit_and_isolates_devices():
    limiter = RateLimiter(default_per_minute=3, per_type={})
    for _ in range(3):
        assert limiter.allow("dev-a", "temperature_sensor")
    assert not limiter.allow("dev-a", "temperature_sensor")  # 4th blocked
    assert limiter.allow("dev-b", "temperature_sensor")  # other device unaffected


def test_per_type_limit_overrides_default():
    limiter = RateLimiter(default_per_minute=1, per_type={"motion_sensor": 2})
    assert limiter.limit_for("motion_sensor") == 2
    assert limiter.limit_for("unknown_type") == 1


def test_window_expiry_frees_slots():
    limiter = RateLimiter(default_per_minute=1, per_type={}, window_seconds=0.05)
    assert limiter.allow("dev-a", "t")
    assert not limiter.allow("dev-a", "t")
    import time

    time.sleep(0.06)
    assert limiter.allow("dev-a", "t")


def test_remaining_counts_down():
    limiter = RateLimiter(default_per_minute=2, per_type={})
    assert limiter.remaining("dev-a", "t") == 2
    limiter.allow("dev-a", "t")
    assert limiter.remaining("dev-a", "t") == 1
