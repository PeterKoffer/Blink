"""Resolve an AuthContext from a bearer JWT issued by Supabase Auth.

This is the one place that speaks JWT. Everything else downstream just
receives an AuthContext.

Flow:
    Authorization: Bearer <jwt>
      -> verify signature + iss + aud + exp via PyJWT
      -> extract auth.users.id (claim `sub`)
      -> look up public.users by auth_user_id
      -> build AuthContext (including parent_account_id if user_type == parent)

If any step fails, raise AuthError. Callers surface a 401.
"""
from __future__ import annotations

from uuid import UUID

import asyncpg
import jwt

from blink.auth.context import AuthContext
from blink.config import get_settings
from blink.errors import AuthError
from blink.types import ParentAccountId, UserId, UserType


def _extract_bearer(authorization_header: str | None) -> str:
    if not authorization_header:
        raise AuthError("Missing Authorization header")
    parts = authorization_header.strip().split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AuthError("Malformed Authorization header; expected 'Bearer <token>'")
    return parts[1]


def _decode_jwt(token: str) -> dict:
    s = get_settings()
    try:
        return jwt.decode(
            token,
            s.supabase_jwt_secret,
            algorithms=["HS256"],
            audience=s.supabase_jwt_audience,
            issuer=s.supabase_jwt_issuer,
            options={"require": ["exp", "sub"]},
        )
    except jwt.ExpiredSignatureError as e:
        raise AuthError("Token expired") from e
    except jwt.InvalidTokenError as e:
        raise AuthError(f"Invalid token: {e}") from e


async def resolve_from_header(
    conn: asyncpg.Connection,
    authorization_header: str | None,
    x_dev_user_id: str | None = None,
) -> AuthContext:
    """Verify JWT + load the local user row. Raises AuthError on any failure.

    In dev env with BLINK_DEV_BYPASS_AUTH=true, a valid `X-Dev-User-Id`
    header short-circuits JWT verification. Any other env rejects the
    bypass header silently and falls through to JWT.
    """
    from blink.auth.dev_bypass import resolve_dev
    dev_ctx = await resolve_dev(conn, x_dev_user_id)
    if dev_ctx is not None:
        return dev_ctx

    token = _extract_bearer(authorization_header)
    claims = _decode_jwt(token)

    sub = claims.get("sub")
    if not sub:
        raise AuthError("Token is missing 'sub' claim")

    try:
        auth_user_id = UUID(sub)
    except (ValueError, TypeError) as e:
        raise AuthError("Token 'sub' is not a UUID") from e

    row = await conn.fetchrow(
        """
        SELECT u.id AS user_id,
               u.type::text AS user_type,
               u.status::text AS user_status,
               pa.id AS parent_account_id
        FROM users u
        LEFT JOIN parent_accounts pa ON pa.user_id = u.id
        WHERE u.auth_user_id = $1
        """,
        auth_user_id,
    )
    if row is None:
        raise AuthError("No Blink user linked to this authenticated identity")
    if row["user_status"] != "active":
        raise AuthError(f"User is not active (status={row['user_status']})")

    user_type = UserType(row["user_type"])

    if user_type == UserType.PARENT and row["parent_account_id"] is None:
        # Data inconsistency — parent user without parent_accounts row.
        # Treat as auth failure; investigation is a server problem, not a client one.
        raise AuthError("Parent user is missing parent_accounts row")

    parent_id: ParentAccountId | None = None
    if row["parent_account_id"] is not None:
        parent_id = ParentAccountId(row["parent_account_id"])

    return AuthContext(
        user_id=UserId(row["user_id"]),
        user_type=user_type,
        parent_account_id=parent_id,
    )
