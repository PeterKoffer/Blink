"""parent_invites data access."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import asyncpg

from blink.types import (
    ParentInviteId,
    ParentInviteStatus,
    UserId,
)


@dataclass(frozen=True, slots=True)
class ParentInviteRow:
    id: ParentInviteId
    child_user_id: UserId
    contact_email_or_phone: str
    invite_token: str
    otp_code_hash: str
    otp_attempts: int
    status: ParentInviteStatus
    created_at: datetime
    verified_at: datetime | None
    approved_at: datetime | None
    expires_at: datetime


_COLS = """
    id, child_user_id, contact_email_or_phone, invite_token,
    otp_code_hash, otp_attempts,
    status::text AS status,
    created_at, verified_at, approved_at, expires_at
"""


def _row(r: asyncpg.Record) -> ParentInviteRow:
    return ParentInviteRow(
        id=ParentInviteId(r["id"]),
        child_user_id=UserId(r["child_user_id"]),
        contact_email_or_phone=r["contact_email_or_phone"],
        invite_token=r["invite_token"],
        otp_code_hash=r["otp_code_hash"],
        otp_attempts=r["otp_attempts"],
        status=ParentInviteStatus(r["status"]),
        created_at=r["created_at"],
        verified_at=r["verified_at"],
        approved_at=r["approved_at"],
        expires_at=r["expires_at"],
    )


async def get(conn: asyncpg.Connection, invite_id: ParentInviteId) -> ParentInviteRow | None:
    r = await conn.fetchrow(f"SELECT {_COLS} FROM parent_invites WHERE id = $1", invite_id)
    return _row(r) if r else None


async def get_by_token(conn: asyncpg.Connection, token: str) -> ParentInviteRow | None:
    r = await conn.fetchrow(
        f"SELECT {_COLS} FROM parent_invites WHERE invite_token = $1",
        token,
    )
    return _row(r) if r else None


async def get_pending_for_child(
    conn: asyncpg.Connection,
    child_user_id: UserId,
) -> ParentInviteRow | None:
    r = await conn.fetchrow(
        f"""
        SELECT {_COLS} FROM parent_invites
        WHERE child_user_id = $1 AND status = 'pending'
        """,
        child_user_id,
    )
    return _row(r) if r else None


async def insert_pending(
    conn: asyncpg.Connection,
    *,
    child_user_id: UserId,
    contact: str,
    invite_token: str,
    otp_code_hash: str,
    expires_at: datetime,
) -> ParentInviteRow:
    r = await conn.fetchrow(
        f"""
        INSERT INTO parent_invites (
            child_user_id, contact_email_or_phone, invite_token,
            otp_code_hash, expires_at
        )
        VALUES ($1, $2, $3, $4, $5)
        RETURNING {_COLS}
        """,
        child_user_id, contact, invite_token, otp_code_hash, expires_at,
    )
    return _row(r)


async def increment_otp_attempts(
    conn: asyncpg.Connection,
    invite_id: ParentInviteId,
) -> int:
    r = await conn.fetchrow(
        """
        UPDATE parent_invites
           SET otp_attempts = otp_attempts + 1
         WHERE id = $1
        RETURNING otp_attempts
        """,
        invite_id,
    )
    return int(r["otp_attempts"]) if r else 0


async def mark_verified(
    conn: asyncpg.Connection,
    invite_id: ParentInviteId,
) -> ParentInviteRow:
    r = await conn.fetchrow(
        f"""
        UPDATE parent_invites
           SET status = 'verified', verified_at = now()
         WHERE id = $1 AND status = 'pending'
        RETURNING {_COLS}
        """,
        invite_id,
    )
    if r is None:
        raise RuntimeError("mark_verified hit zero rows (wrong state)")
    return _row(r)


async def mark_approved(
    conn: asyncpg.Connection,
    invite_id: ParentInviteId,
) -> ParentInviteRow:
    r = await conn.fetchrow(
        f"""
        UPDATE parent_invites
           SET status = 'approved', approved_at = now()
         WHERE id = $1 AND status = 'verified'
        RETURNING {_COLS}
        """,
        invite_id,
    )
    if r is None:
        raise RuntimeError("mark_approved hit zero rows (wrong state)")
    return _row(r)


async def mark_declined(
    conn: asyncpg.Connection,
    invite_id: ParentInviteId,
) -> ParentInviteRow:
    r = await conn.fetchrow(
        f"""
        UPDATE parent_invites
           SET status = 'declined'
         WHERE id = $1 AND status IN ('pending', 'verified')
        RETURNING {_COLS}
        """,
        invite_id,
    )
    if r is None:
        raise RuntimeError("mark_declined hit zero rows")
    return _row(r)


async def expire_stale(conn: asyncpg.Connection) -> int:
    """Flip status='expired' for pending invites past expires_at.

    Run periodically. Returns count of rows flipped.
    """
    result = await conn.execute(
        """
        UPDATE parent_invites
           SET status = 'expired'
         WHERE status = 'pending' AND expires_at <= now()
        """,
    )
    return int(result.split()[-1]) if result else 0
