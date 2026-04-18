"""FastAPI dependencies.

Connection, auth context, and the R2 adapter — injected into every route.
"""
from __future__ import annotations

from typing import Annotated, AsyncIterator

import asyncpg
from fastapi import Depends, Header

from blink.auth.context import AuthContext
from blink.auth.resolver import resolve_from_header
from blink.config import get_settings
from blink.db import acquire
from blink.r2.adapter import R2Adapter


async def get_conn() -> AsyncIterator[asyncpg.Connection]:
    """Per-request pooled connection.

    Routes that modify state start their own transaction with
    `async with conn.transaction():` OR let services do it.
    """
    async with acquire() as conn:
        yield conn


ConnDep = Annotated[asyncpg.Connection, Depends(get_conn)]


async def get_auth(
    conn: ConnDep,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    x_dev_user_id: Annotated[str | None, Header(alias="X-Dev-User-Id")] = None,
) -> AuthContext:
    return await resolve_from_header(conn, authorization, x_dev_user_id)


AuthDep = Annotated[AuthContext, Depends(get_auth)]


# --- R2 adapter singleton --------------------------------------

_r2_adapter: R2Adapter | None = None


def get_r2() -> R2Adapter:
    """Lazy-init the R2 adapter on first request.

    Tests override this dependency via app.dependency_overrides so no real
    boto3 client is constructed.
    """
    global _r2_adapter
    if _r2_adapter is None:
        from blink.r2.adapter import Boto3R2Adapter
        s = get_settings()
        _r2_adapter = Boto3R2Adapter(
            bucket=s.r2_bucket_name,
            endpoint_url=s.r2_endpoint,
            access_key_id=s.r2_access_key_id,
            secret_access_key=s.r2_secret_access_key,
        )
    return _r2_adapter


R2Dep = Annotated[R2Adapter, Depends(get_r2)]


# --- OTP delivery adapter singleton --------------------------

_otp_adapter = None  # lazy init


def get_otp_adapter():
    """Pick an OTP delivery adapter based on env.

    v1: only ConsoleOtpAdapter exists. Production will plug in SES/Twilio
    when ready. The app refuses to start in non-dev env with console mode
    by convention (no code enforcement yet).
    """
    global _otp_adapter
    if _otp_adapter is None:
        from blink.onboarding.adapters import ConsoleOtpAdapter
        _otp_adapter = ConsoleOtpAdapter()
    return _otp_adapter


OtpAdapterDep = Annotated[object, Depends(get_otp_adapter)]
