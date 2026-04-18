"""Minimal in-process metrics registry.

Uses Prometheus text format so we can point any scraper at /metrics without
a client library dependency. Labels are cardinality-bounded — route paths
are normalized (UUIDs → `{id}`) by middleware before reaching here.

For horizontal scale, replace the global registry with a Redis/StatsD sink.
The public API (`inc`, `render_prometheus`) stays the same.
"""
from __future__ import annotations

from threading import Lock
from typing import Iterable


class Metrics:
    def __init__(self) -> None:
        self._counters: dict[tuple[str, tuple[tuple[str, str], ...]], int] = {}
        self._counter_defs: dict[str, str] = {}
        self._lock = Lock()

    def register_counter(self, name: str, help_text: str) -> None:
        self._counter_defs[name] = help_text

    def inc(
        self,
        name: str,
        labels: dict[str, str] | None = None,
        value: int = 1,
    ) -> None:
        labels_tuple = tuple(sorted((labels or {}).items()))
        with self._lock:
            key = (name, labels_tuple)
            self._counters[key] = self._counters.get(key, 0) + value

    def snapshot(self) -> dict[tuple[str, tuple[tuple[str, str], ...]], int]:
        with self._lock:
            return dict(self._counters)

    def render_prometheus(self) -> str:
        lines: list[str] = []
        # Emit HELP/TYPE for registered counters, even if count=0.
        for name, help_text in sorted(self._counter_defs.items()):
            lines.append(f"# HELP {name} {help_text}")
            lines.append(f"# TYPE {name} counter")
        snap = self.snapshot()
        for (name, labels), value in sorted(snap.items()):
            if labels:
                label_str = ",".join(f'{k}="{v}"' for k, v in labels)
                lines.append(f"{name}{{{label_str}}} {value}")
            else:
                lines.append(f"{name} {value}")
        return "\n".join(lines) + "\n"


_default = Metrics()


def get_metrics() -> Metrics:
    return _default


def register_default_counters() -> None:
    """Register the counters emitted across the codebase."""
    m = _default
    m.register_counter("blink_http_requests_total", "HTTP requests by method/path/status")
    m.register_counter("blink_http_latency_ms_sum", "Sum of HTTP latency in ms")
    m.register_counter("blink_messages_created_total", "Text and image messages created")
    m.register_counter("blink_messages_expired_total", "Messages flipped to expired by the engine")
    m.register_counter("blink_media_upload_url_total", "Media upload-url calls")
    m.register_counter("blink_media_confirm_total", "Media confirm calls by outcome")
    m.register_counter("blink_media_get_url_total", "Media read-url calls")
    m.register_counter("blink_media_cascade_expired_total", "Media rows expired via message cascade")
    m.register_counter("blink_approvals_total", "Parent approve/decline actions by kind/action")
    m.register_counter("blink_upgrade_required_total", "UpgradeRequiredError raised")
    m.register_counter("blink_hard_cap_exceeded_total", "HardCapExceededError raised")
    m.register_counter("blink_rate_limited_total", "Requests denied by rate limiter, by bucket")


register_default_counters()


# Convenience helpers — tight names so service code stays readable.

def count_message_created(message_type: str) -> None:
    _default.inc("blink_messages_created_total", {"type": message_type})


def count_messages_expired(n: int) -> None:
    _default.inc("blink_messages_expired_total", value=n)


def count_media_cascade(n: int) -> None:
    _default.inc("blink_media_cascade_expired_total", value=n)


def count_media_event(event: str, outcome: str = "ok") -> None:
    """event: upload_url | confirm | get_url"""
    if event == "upload_url":
        _default.inc("blink_media_upload_url_total", {"outcome": outcome})
    elif event == "confirm":
        _default.inc("blink_media_confirm_total", {"outcome": outcome})
    elif event == "get_url":
        _default.inc("blink_media_get_url_total", {"outcome": outcome})


def count_approval(kind: str, action: str) -> None:
    """kind: friend | group_create | group_join | group_invite; action: approve | decline"""
    _default.inc("blink_approvals_total", {"kind": kind, "action": action})


def count_upgrade_required() -> None:
    _default.inc("blink_upgrade_required_total")


def count_hard_cap_exceeded() -> None:
    _default.inc("blink_hard_cap_exceeded_total")


def count_rate_limited(bucket: str) -> None:
    _default.inc("blink_rate_limited_total", {"bucket": bucket})


def iter_counters() -> Iterable[tuple[tuple[str, tuple[tuple[str, str], ...]], int]]:
    """For tests."""
    return _default.snapshot().items()
