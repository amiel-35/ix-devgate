import time

import pytest

from app.modules.auth.rate_limit import RateLimitExceeded, RateLimiter


def test_allows_under_limit():
    limiter = RateLimiter(max_requests=3, window_seconds=60)
    limiter.check("user@example.com")
    limiter.check("user@example.com")
    limiter.check("user@example.com")


def test_blocks_over_limit():
    limiter = RateLimiter(max_requests=2, window_seconds=60)
    limiter.check("user@example.com")
    limiter.check("user@example.com")
    with pytest.raises(RateLimitExceeded):
        limiter.check("user@example.com")


def test_window_expires():
    limiter = RateLimiter(max_requests=1, window_seconds=1)
    limiter.check("user@example.com")
    time.sleep(1.1)
    limiter.check("user@example.com")  # must not raise


def test_keys_are_isolated():
    limiter = RateLimiter(max_requests=1, window_seconds=60)
    limiter.check("a@b.com")
    limiter.check("c@d.com")  # different key, must not raise
