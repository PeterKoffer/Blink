"""User lookups + child-profile writes."""
from __future__ import annotations

from dataclasses import dataclass

import asyncpg

from blink.types import (
    AvatarType,
    OnboardingStatus,
    UserId,
    UserStatus,
    UserType,
)


@dataclass(frozen=True, slots=True)
class UserRow:
    id: UserId
    type: UserType
    status: UserStatus
    display_name: str | None
    avatar_initial: str | None
    avatar_type: AvatarType | None = None
    avatar_value: str | None = None
    avatar_color: str | None = None
    blink_code: str | None = None
    onboarding_status: OnboardingStatus | None = None


_USER_COLS = """
    id, type::text AS type, status::text AS status,
    display_name, avatar_initial,
    avatar_type::text AS avatar_type,
    avatar_value, avatar_color, blink_code,
    onboarding_status::text AS onboarding_status
"""


def _row_to_user(r: asyncpg.Record) -> UserRow:
    return UserRow(
        id=UserId(r["id"]),
        type=UserType(r["type"]),
        status=UserStatus(r["status"]),
        display_name=r["display_name"],
        avatar_initial=r["avatar_initial"],
        avatar_type=AvatarType(r["avatar_type"]) if r["avatar_type"] else None,
        avatar_value=r["avatar_value"],
        avatar_color=r["avatar_color"],
        blink_code=r["blink_code"],
        onboarding_status=(
            OnboardingStatus(r["onboarding_status"])
            if r["onboarding_status"] else None
        ),
    )


async def get_by_id(conn: asyncpg.Connection, user_id: UserId) -> UserRow | None:
    row = await conn.fetchrow(
        f"SELECT {_USER_COLS} FROM users WHERE id = $1",
        user_id,
    )
    return _row_to_user(row) if row else None


async def get_by_blink_code(conn: asyncpg.Connection, code: str) -> UserRow | None:
    row = await conn.fetchrow(
        f"SELECT {_USER_COLS} FROM users WHERE blink_code = $1",
        code,
    )
    return _row_to_user(row) if row else None


async def get_many(
    conn: asyncpg.Connection,
    user_ids: list[UserId],
) -> list[UserRow]:
    if not user_ids:
        return []
    rows = await conn.fetch(
        f"SELECT {_USER_COLS} FROM users WHERE id = ANY($1::uuid[])",
        user_ids,
    )
    return [_row_to_user(r) for r in rows]


async def insert_child_profile(
    conn: asyncpg.Connection,
    *,
    display_name: str,
    avatar_type: AvatarType,
    avatar_value: str,
    avatar_color: str,
    blink_code: str,
) -> UserRow:
    """Create a child user in profile_pending state.

    The row is NOT yet usable — status='pending_activation' until a parent
    approves via the onboarding flow. authz layer blocks this user.
    """
    r = await conn.fetchrow(
        f"""
        INSERT INTO users (
            type, status, display_name, avatar_initial,
            avatar_type, avatar_value, avatar_color, blink_code,
            onboarding_status
        )
        VALUES (
            'child', 'pending_activation', $1, $2,
            $3::avatar_type, $4, $5, $6,
            'profile_pending'::onboarding_status
        )
        RETURNING {_USER_COLS}
        """,
        display_name,
        (display_name[0] if display_name else "?").upper()[:1],
        avatar_type.value,
        avatar_value,
        avatar_color,
        blink_code,
    )
    return _row_to_user(r)


async def set_onboarding_status(
    conn: asyncpg.Connection,
    *,
    user_id: UserId,
    new_status: OnboardingStatus,
) -> UserRow:
    r = await conn.fetchrow(
        f"""
        UPDATE users SET onboarding_status = $2::onboarding_status
         WHERE id = $1
        RETURNING {_USER_COLS}
        """,
        user_id, new_status.value,
    )
    if r is None:
        raise RuntimeError("set_onboarding_status hit zero rows")
    return _row_to_user(r)


async def activate_child(
    conn: asyncpg.Connection,
    *,
    user_id: UserId,
) -> UserRow:
    """Flip child from pending_activation → active after parent approval."""
    r = await conn.fetchrow(
        f"""
        UPDATE users
           SET status = 'active'::user_status,
               onboarding_status = 'active'::onboarding_status
         WHERE id = $1 AND type = 'child'
        RETURNING {_USER_COLS}
        """,
        user_id,
    )
    if r is None:
        raise RuntimeError("activate_child hit zero rows")
    return _row_to_user(r)
