"""A small fixed-window limiter for the routes worth protecting.

In-process and intentionally simple. Behind more than one worker, point
``_HITS`` at Redis -- the dependency signature does not change.
"""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import HTTPException, Request, status

_HITS: dict[str, list[float]] = defaultdict(list)


class RateLimiter:
    """``Depends(RateLimiter(times=10, seconds=60, scope="login"))``."""

    def __init__(self, times: int, seconds: int, scope: str = "default") -> None:
        self.times = times
        self.seconds = seconds
        self.scope = scope

    async def __call__(self, request: Request) -> None:
        client = request.client.host if request.client else "unknown"
        self.check(f"{self.scope}:{client}")

    def check(self, key: str) -> None:
        now = time.monotonic()
        hits = [stamp for stamp in _HITS[key] if stamp > now - self.seconds]
        if len(hits) >= self.times:
            retry_after = max(1, int(self.seconds - (now - hits[0])))
            _HITS[key] = hits
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Try again in {retry_after}s.",
                headers={"Retry-After": str(retry_after)},
            )
        hits.append(now)
        _HITS[key] = hits


def reset_rate_limits() -> None:
    """Used by the test suite; never called at runtime."""
    _HITS.clear()
