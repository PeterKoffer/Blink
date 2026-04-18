"""Structured JSON logging.

One log line per event, JSON object per line — ready for any log shipper.
Fields prefixed with `blink_` on the LogRecord get promoted to top-level
keys in the JSON output (the prefix is stripped).

Example:
    log.info("http_request",
             extra={"blink_method": "POST", "blink_path": "/messages",
                    "blink_status": 200, "blink_latency_ms": 14})

Output:
    {"ts": 1234.5, "level": "INFO", "msg": "http_request",
     "logger": "blink.request", "method": "POST", "path": "/messages",
     "status": 200, "latency_ms": 14}
"""
from __future__ import annotations

import json
import logging
import sys


# Fields always present on every LogRecord that we don't want to promote.
_LOGRECORD_RESERVED = frozenset({
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "taskName", "message",
})

_BLINK_PREFIX = "blink_"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base: dict[str, object] = {
            "ts": round(record.created, 3),
            "level": record.levelname,
            "msg": record.getMessage(),
            "logger": record.name,
        }
        # Promote blink_* extras to top-level, stripping the prefix.
        for key, value in record.__dict__.items():
            if key in _LOGRECORD_RESERVED:
                continue
            if key.startswith(_BLINK_PREFIX):
                base[key[len(_BLINK_PREFIX):]] = value
        if record.exc_info:
            base["exc"] = self.formatException(record.exc_info)
        return json.dumps(base, default=str)


def setup_logging(level: str = "info") -> None:
    """Install the JSON formatter on the root logger.

    Call once at app startup. Safe to call more than once (handlers are
    replaced, not appended).
    """
    root = logging.getLogger()
    root.setLevel(level.upper())
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.handlers = [handler]
    # Quiet down chatty libraries at info level by default.
    logging.getLogger("asyncpg").setLevel("WARNING")
