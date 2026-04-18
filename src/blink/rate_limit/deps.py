"""Rate-limit FastAPI dependency factory.

Usage in routes:

    from blink.rate_limit.deps import rate_limit

    @router.post("/messages", dependencies=[rate_limit("messages:create")])
    async def create_message(...):
        ...

Buckets are keyed per user, so two users hitting the same endpoint get
independent windows. Use conservative defaults; tune per deployment via
env later.
"""
from __future__ import annotations

from fastapi import Depends

from blink.api.deps import AuthDep
from blink.errors import RateLimitedError
from blink.obs.metrics import count_rate_limited
from blink.rate_limit.limiter import FixedWindowLimiter


# Conservative v1 limits (per user per 60s). Tuned for demo traffic.
_BUCKETS: dict[str, FixedWindowLimiter] = {
    "friends:create_request":   FixedWindowLimiter(20, 60),
    "groups:create":            FixedWindowLimiter(10, 60),
    "groups:join":              FixedWindowLimiter(20, 60),
    "groups:invite":            FixedWindowLimiter(30, 60),
    "messages:create":          FixedWindowLimiter(60, 60),
    "media:upload_url":         FixedWindowLimiter(30, 60),
    "media:confirm":            FixedWindowLimiter(30, 60),
}


def _get_limiter(bucket: str) -> FixedWindowLimiter | None:
    return _BUCKETS.get(bucket)


def rate_limit(bucket: str):
    """Build a Depends that enforces per-user rate limiting for `bucket`."""

    async def _enforce(ctx: AuthDep) -> None:
        limiter = _get_limiter(bucket)
        if limiter is None:
            return
        key = f"{bucket}:{ctx.user_id}"
        ok, retry = limiter.check_and_consume(key)
        if not ok:
            count_rate_limited(bucket)
            raise RateLimitedError(
                bucket=bucket,
                limit=limiter.max,
                window_seconds=limiter.window,
                retry_after_seconds=retry,
            )

    return Depends(_enforce)


def _reset_all_for_tests() -> None:
    """Clear all window state. Only for tests — never called in prod."""
    for lim in _BUCKETS.values():
        with lim._lock:  # type: ignore[attr-defined]
            lim._windows.clear()  # type: ignore[attr-defined]
