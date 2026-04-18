"""Dev-only auth escape hatch.

When BOTH:
  - BLINK_ENV=dev
  - BLINK_DEV_BYPASS_AUTH=true
and a request arrives with header `X-Dev-User-Id: <uuid>`, we resolve that
as a fully authenticated session for the given local user id.

This exists so the single-file prototype frontend (kidschat_demo.py) can
talk to the backend without a real OIDC login. Rejected outside dev env
regardless of header presence.

Production/staging MUST set BLINK_DEV_BYPASS_AUTH=false (default).
"""
from __future__ import annotations

from uuid import UUID

import asyncpg

from blink.auth.context import AuthContext
from blink.config import get_settings
from blink.errors import AuthError
from blink.types import ParentAccountId, UserId, UserType


async def resolve_dev(
    conn: asyncpg.Connection,
    x_dev_user_id: str | None,
) -> AuthContext | None:
    """Return AuthContext if dev bypass applies; else None."""
    s = get_settings()
    if s.blink_env != "dev":
        return None
    if not s.blink_dev_bypass_auth:
        return None
    if not x_dev_user_id:
        return None

    try:
        uid = UUID(x_dev_user_id)
    except (ValueError, TypeError) as e:
        raise AuthError("Invalid X-Dev-User-Id header") from e

    row = await conn.fetchrow(
        """
        SELECT u.id, u.type::text AS type, u.status::text AS status,
               pa.id AS parent_account_id
        FROM users u
        LEFT JOIN parent_accounts pa ON pa.user_id = u.id
        WHERE u.id = $1
        """,
        uid,
    )
    if row is None:
        raise AuthError("Dev user id not found")
    if row["status"] != "active":
        raise AuthError(f"Dev user is not active (status={row['status']})")

    user_type = UserType(row["type"])
    parent_id: ParentAccountId | None = None
    if row["parent_account_id"] is not None:
        parent_id = ParentAccountId(row["parent_account_id"])
    return AuthContext(
        user_id=UserId(row["id"]),
        user_type=user_type,
        parent_account_id=parent_id,
    )
