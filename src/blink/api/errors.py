"""Map BlinkError subclasses to HTTP responses.

One handler, one mapping table. No ad-hoc try/except in routes.
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from blink.errors import (
    AuthError,
    AuthzError,
    BlinkError,
    HardCapExceededError,
    NotFoundError,
    PolicyBlockedError,
    RateLimitedError,
    StateConflictError,
    UnsupportedError,
    UpgradeRequiredError,
    ValidationError,
)


_STATUS: dict[type[BlinkError], int] = {
    AuthError: 401,
    AuthzError: 403,
    PolicyBlockedError: 403,
    NotFoundError: 404,
    StateConflictError: 409,
    UpgradeRequiredError: 409,
    HardCapExceededError: 409,
    ValidationError: 422,
    UnsupportedError: 422,
    RateLimitedError: 429,
}


def _status_for(exc: BlinkError) -> int:
    for cls in type(exc).__mro__:
        if cls in _STATUS:
            return _STATUS[cls]
    return 500


async def _handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, BlinkError)
    body: dict[str, object] = {
        "error": {
            "code": exc.code,
            "message": str(exc),
        }
    }
    if isinstance(exc, PolicyBlockedError):
        body["error"]["policyKey"] = exc.policy_key  # type: ignore[index]
    if isinstance(exc, UnsupportedError):
        body["error"]["feature"] = exc.feature  # type: ignore[index]
    if isinstance(exc, UpgradeRequiredError):
        body["error"]["currentTier"] = exc.current_tier  # type: ignore[index]
        body["error"]["requiredTier"] = exc.required_tier  # type: ignore[index]
        body["error"]["currentMemberCount"] = exc.current_member_count  # type: ignore[index]
        body["error"]["currentCap"] = exc.current_cap  # type: ignore[index]
    if isinstance(exc, HardCapExceededError):
        body["error"]["limit"] = exc.limit  # type: ignore[index]
    headers: dict[str, str] = {}
    if isinstance(exc, RateLimitedError):
        body["error"]["bucket"] = exc.bucket  # type: ignore[index]
        body["error"]["limit"] = exc.limit  # type: ignore[index]
        body["error"]["windowSeconds"] = exc.window_seconds  # type: ignore[index]
        body["error"]["retryAfterSeconds"] = exc.retry_after_seconds  # type: ignore[index]
        headers["Retry-After"] = str(exc.retry_after_seconds)
    return JSONResponse(
        status_code=_status_for(exc),
        content=body,
        headers=headers or None,
    )


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(BlinkError, _handler)
