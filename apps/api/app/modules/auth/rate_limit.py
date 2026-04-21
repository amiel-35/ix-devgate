"""Rate limiter en mémoire — suffisant pour v1 monolithe single-instance.
À remplacer par Redis si scale-out."""
import time
from collections import defaultdict, deque

from fastapi import HTTPException, status


class RateLimitExceeded(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Trop de tentatives, réessayez dans quelques minutes",
        )


class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = time.monotonic()
        bucket = self._hits[key]
        while bucket and now - bucket[0] > self.window_seconds:
            bucket.popleft()
        if len(bucket) >= self.max_requests:
            raise RateLimitExceeded()
        bucket.append(now)


# Shared instance for /auth/start — 5 attempts per 10 minutes
login_start_limiter = RateLimiter(max_requests=5, window_seconds=600)

# Shared instance for /auth/verify — 10 attempts per 5 minutes
login_verify_limiter = RateLimiter(max_requests=10, window_seconds=300)
