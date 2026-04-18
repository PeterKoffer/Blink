"""Observability foundation — no DB, no network."""
from __future__ import annotations

import json
import logging

from blink.obs.logging import JsonFormatter
from blink.obs.metrics import Metrics
from blink.obs.middleware import normalize_path


# ---------------- metrics registry ----------------

def test_metrics_register_and_render():
    m = Metrics()
    m.register_counter("test_counter", "A test counter")
    m.inc("test_counter")
    m.inc("test_counter", value=4)
    text = m.render_prometheus()
    assert "# HELP test_counter A test counter" in text
    assert "# TYPE test_counter counter" in text
    assert "test_counter 5" in text


def test_metrics_labels_render_correctly():
    m = Metrics()
    m.register_counter("http_requests_total", "HTTP requests")
    m.inc("http_requests_total", {"method": "GET", "path": "/foo", "status": "200"})
    m.inc("http_requests_total", {"method": "GET", "path": "/foo", "status": "200"})
    m.inc("http_requests_total", {"method": "POST", "path": "/foo", "status": "200"})
    text = m.render_prometheus()
    assert 'http_requests_total{method="GET",path="/foo",status="200"} 2' in text
    assert 'http_requests_total{method="POST",path="/foo",status="200"} 1' in text


def test_metrics_snapshot_is_isolated_from_live_counter():
    m = Metrics()
    m.inc("c", value=1)
    snap = m.snapshot()
    m.inc("c", value=10)
    # snap was taken before the second inc
    assert list(snap.values()) == [1]


# ---------------- path normalization ----------------

def test_normalize_path_replaces_uuids():
    uuid = "11111111-1111-1111-1111-111111111111"
    assert normalize_path(f"/groups/{uuid}") == "/groups/{id}"
    assert normalize_path(f"/groups/{uuid}/messages") == "/groups/{id}/messages"
    assert normalize_path(f"/media/{uuid}/url") == "/media/{id}/url"


def test_normalize_path_preserves_static_paths():
    assert normalize_path("/healthz") == "/healthz"
    assert normalize_path("/metrics") == "/metrics"
    assert normalize_path("/groups") == "/groups"


# ---------------- json log formatter ----------------

def test_json_formatter_emits_single_line_json():
    fmt = JsonFormatter()
    record = logging.LogRecord(
        name="blink.test", level=logging.INFO, pathname="x.py", lineno=1,
        msg="hello", args=(), exc_info=None,
    )
    record.blink_method = "POST"
    record.blink_path = "/groups"
    record.blink_status = 201
    out = fmt.format(record)
    parsed = json.loads(out)
    assert parsed["msg"] == "hello"
    assert parsed["level"] == "INFO"
    assert parsed["method"] == "POST"
    assert parsed["path"] == "/groups"
    assert parsed["status"] == 201
    # Prefix stripped — no field named "blink_method"
    assert "blink_method" not in parsed


def test_json_formatter_ignores_non_blink_extras():
    fmt = JsonFormatter()
    record = logging.LogRecord(
        name="t", level=logging.INFO, pathname="x.py", lineno=1,
        msg="m", args=(), exc_info=None,
    )
    record.some_random_field = "noise"  # not prefixed, should be dropped
    parsed = json.loads(fmt.format(record))
    assert "some_random_field" not in parsed
