"""In-process fixed-window rate limiter.

Sufficient for single-node dev/staging. For production with multiple
workers, swap the `_windows` dict for Redis (same public interface).
"""
from __future__ import annotations

import time
from threading import Lock


class FixedWindowLimiter:
    """Simple fixed-window counter. Not the fairest algorithm; the simplest
    one that's obviously correct.
    """

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        if max_requests < 1 or window_seconds < 1:
            raise ValueError("max_requests and window_seconds must be >= 1")
        self.max = max_requests
        self.window = window_seconds
        self._windows: dict[str, tuple[int, int]] = {}
        self._lock = Lock()

    def _now(self) -> int:
        """Extracted so tests can monkeypatch."""
        return int(time.time())

    def check_and_consume(self, key: str) -> tuple[bool, int]:
        """Returns (allowed, retry_after_seconds).

        - allowed=True consumes one from the current window.
        - allowed=False does not; retry_after is seconds until the next window.
        """
        now = self._now()
        window_start = now - (now % self.window)

        with self._lock:
            existing = self._windows.get(key)
            if existing is None or existing[0] != window_start:
                self._windows[key] = (window_start, 1)
                return True, 0
            _, count = existing
            if count >= self.max:
                retry = window_start + self.window - now
                return False, max(retry, 1)
            self._windows[key] = (window_start, count + 1)
            return True, 0
