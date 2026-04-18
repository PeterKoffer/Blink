"""consent_records data access."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import asyncpg

from blink.types import ConsentRecordId, ParentAccountId, UserId


@dataclass(frozen=True, slots=True)
class ConsentRecordRow:
    id: ConsentRecordId
    parent_account_id: ParentAccountId
    child_user_id: UserId
    consent_type: str
    consent_version: str
    consent_text: str
    accepted_at: datetime
    ip_address: str | None
    user_agent: str | None
    created_at: datetime


_COLS = """
    id, parent_account_id, child_user_id,
    consent_type, consent_version, consent_text,
    accepted_at, ip_address, user_agent, created_at
"""


def _row(r: asyncpg.Record) -> ConsentRecordRow:
    return ConsentRecordRow(
        id=ConsentRecordId(r["id"]),
        parent_account_id=ParentAccountId(r["parent_account_id"]),
        child_user_id=UserId(r["child_user_id"]),
        consent_type=r["consent_type"],
        consent_version=r["consent_version"],
        consent_text=r["consent_text"],
        accepted_at=r["accepted_at"],
        ip_address=r["ip_address"],
        user_agent=r["user_agent"],
        created_at=r["created_at"],
    )


async def record_consent(
    conn: asyncpg.Connection,
    *,
    parent_account_id: ParentAccountId,
    child_user_id: UserId,
    consent_type: str,
    consent_version: str,
    consent_text: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> ConsentRecordRow:
    """Insert a consent row. Idempotent on (parent, child, type, version) —
    if the same combination already exists, returns the existing row.
    """
    r = await conn.fetchrow(
        f"""
        INSERT INTO consent_records (
            parent_account_id, child_user_id,
            consent_type, consent_version, consent_text,
            ip_address, user_agent
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (parent_account_id, child_user_id, consent_type, consent_version)
        DO NOTHING
        RETURNING {_COLS}
        """,
        parent_account_id, child_user_id,
        consent_type, consent_version, consent_text,
        ip_address, user_agent,
    )
    if r is not None:
        return _row(r)
    # Conflict — return the existing row.
    existing = await conn.fetchrow(
        f"""
        SELECT {_COLS} FROM consent_records
        WHERE parent_account_id = $1
          AND child_user_id = $2
          AND consent_type = $3
          AND consent_version = $4
        """,
        parent_account_id, child_user_id, consent_type, consent_version,
    )
    assert existing is not None, "conflict fired but row not found"
    return _row(existing)


async def list_for_child(
    conn: asyncpg.Connection,
    child_user_id: UserId,
) -> list[ConsentRecordRow]:
    rows = await conn.fetch(
        f"""
        SELECT {_COLS} FROM consent_records
         WHERE child_user_id = $1
         ORDER BY created_at DESC
        """,
        child_user_id,
    )
    return [_row(r) for r in rows]
