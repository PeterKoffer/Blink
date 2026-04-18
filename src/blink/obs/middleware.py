"""HTTP request observability — one log line + one metric bump per request.

Path normalization keeps the `path` label's cardinality bounded so metrics
don't explode from UUIDs in URLs.
"""
from __future__ import annotations

import logging
import re
import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from blink.obs.metrics import get_metrics


_log = logging.getLogger("blink.request")

_UUID_RE = re.compile(
    r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)


def normalize_path(path: str) -> str:
    """Replace UUID path segments with `/{id}` for label cardinality."""
    return _UUID_RE.sub("/{id}", path)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Emit one structured log + one http-request counter bump per request."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        start = time.monotonic()
        status = 500
        error = None
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        except Exception as e:
            error = type(e).__name__
            raise
        finally:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            path = normalize_path(request.url.path)
            _log.info(
                "http_request",
                extra={
                    "blink_method": request.method,
                    "blink_path": path,
                    "blink_status": status,
                    "blink_latency_ms": elapsed_ms,
                    **({"blink_error": error} if error else {}),
                },
            )
            m = get_metrics()
            m.inc(
                "blink_http_requests_total",
                {
                    "method": request.method,
                    "path": path,
                    "status": str(status),
                },
            )
            m.inc("blink_http_latency_ms_sum", {"path": path}, value=elapsed_ms)
