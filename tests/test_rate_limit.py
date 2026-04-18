"""Rate limiter unit tests — no DB needed."""
from __future__ import annotations

import pytest

from blink.rate_limit.limiter import FixedWindowLimiter


def test_limiter_allows_up_to_max_then_rejects():
    lim = FixedWindowLimiter(max_requests=3, window_seconds=60)
    results = [lim.check_and_consume("u1")[0] for _ in range(3)]
    assert all(results)

    ok, retry = lim.check_and_consume("u1")
    assert ok is False
    assert retry > 0


def test_limiter_keys_are_isolated():
    lim = FixedWindowLimiter(max_requests=1, window_seconds=60)
    assert lim.check_and_consume("alice")[0] is True
    # Bob gets his own bucket.
    assert lim.check_and_consume("bob")[0] is True
    # Alice is now blocked.
    assert lim.check_and_consume("alice")[0] is False


def test_limiter_rejects_invalid_config():
    with pytest.raises(ValueError):
        FixedWindowLimiter(max_requests=0, window_seconds=60)
    with pytest.raises(ValueError):
        FixedWindowLimiter(max_requests=1, window_seconds=0)


def test_limiter_window_resets_on_time_advance(monkeypatch):
    lim = FixedWindowLimiter(max_requests=2, window_seconds=60)

    current = {"t": 1000}
    monkeypatch.setattr(lim, "_now", lambda: current["t"])

    assert lim.check_and_consume("u")[0] is True
    assert lim.check_and_consume("u")[0] is True
    ok, retry = lim.check_and_consume("u")
    assert ok is False
    assert retry >= 1

    # Advance past the window boundary.
    current["t"] = 1000 + 60
    assert lim.check_and_consume("u")[0] is True


def test_retry_after_shrinks_as_time_advances(monkeypatch):
    lim = FixedWindowLimiter(max_requests=1, window_seconds=60)
    current = {"t": 1000}
    monkeypatch.setattr(lim, "_now", lambda: current["t"])

    lim.check_and_consume("u")  # consume the one slot in window [960, 1020)
    _, retry_a = lim.check_and_consume("u")
    assert retry_a > 0

    current["t"] = 1010
    _, retry_b = lim.check_and_consume("u")
    assert retry_b < retry_a
