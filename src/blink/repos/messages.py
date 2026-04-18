"""messages data access.

Rules:
- Queries always filter by `status='active' AND expires_at > now()` when
  returning user-facing data. This double-layer guards against the
  expiration job running late — a logically-expired message is never
  returned as active, even if the row hasn't been flipped yet.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import asyncpg

from blink.types import (
    EphemeralMode,
    GroupId,
    MessageId,
    MessageStatus,
    MessageType,
    UserId,
)


@dataclass(frozen=True, slots=True)
class MessageRow:
    id: MessageId
    sender_id: UserId
    group_id: GroupId | None
    chat_id: UUID | None
    type: MessageType
    text_content: str | None
    media_id: UUID | None
    client_message_id: str
    ephemeral_mode: EphemeralMode
    ttl_seconds: int
    created_at: datetime
    expires_at: datetime
    status: MessageStatus

    # Enriched — nullable if the JOIN didn't include them.
    sender_display_name: str | None = None
    sender_avatar_initial: str | None = None


_COLS = """
    m.id, m.sender_id, m.group_id, m.chat_id,
    m.type::text AS type,
    m.text_content, m.media_id, m.client_message_id,
    m.ephemeral_mode::text AS ephemeral_mode,
    m.ttl_seconds, m.created_at, m.expires_at,
    m.status::text AS status
"""

_COLS_WITH_SENDER = _COLS + """,
    u.display_name AS sender_display_name,
    u.avatar_initial AS sender_avatar_initial
"""


def _row(r: asyncpg.Record, *, with_sender: bool = False) -> MessageRow:
    return MessageRow(
        id=MessageId(r["id"]),
        sender_id=UserId(r["sender_id"]),
        group_id=GroupId(r["group_id"]) if r["group_id"] else None,
        chat_id=r["chat_id"],
        type=MessageType(r["type"]),
        text_content=r["text_content"],
        media_id=r["media_id"],
        client_message_id=r["client_message_id"],
        ephemeral_mode=EphemeralMode(r["ephemeral_mode"]),
        ttl_seconds=r["ttl_seconds"],
        created_at=r["created_at"],
        expires_at=r["expires_at"],
        status=MessageStatus(r["status"]),
        sender_display_name=r["sender_display_name"] if with_sender else None,
        sender_avatar_initial=r["sender_avatar_initial"] if with_sender else None,
    )


# ---------- idempotent create ----------

async def get_by_idempotency_key(
    conn: asyncpg.Connection,
    *,
    sender_id: UserId,
    client_message_id: str,
) -> MessageRow | None:
    r = await conn.fetchrow(
        f"""
        SELECT {_COLS_WITH_SENDER}
        FROM messages m
        JOIN users u ON u.id = m.sender_id
        WHERE m.sender_id = $1 AND m.client_message_id = $2
        """,
        sender_id, client_message_id,
    )
    return _row(r, with_sender=True) if r else None


async def insert_text_message_atomic(
    conn: asyncpg.Connection,
    *,
    sender_id: UserId,
    group_id: GroupId | None,
    chat_id: UUID | None,
    text: str,
    client_message_id: str,
    ephemeral_mode: EphemeralMode,
    ttl_seconds: int,
) -> tuple[MessageRow, bool]:
    """Race-safe idempotent insert.

    Uses ON CONFLICT DO NOTHING on (sender_id, client_message_id).
    Returns (row, is_fresh) where is_fresh=True for first insert,
    False for an idempotent replay.
    """
    r = await conn.fetchrow(
        """
        INSERT INTO messages (
            sender_id, group_id, chat_id, type, text_content,
            client_message_id, ephemeral_mode, ttl_seconds, expires_at
        )
        VALUES (
            $1, $2, $3, 'text', $4,
            $5, $6::ephemeral_mode, $7, now() + make_interval(secs => $7)
        )
        ON CONFLICT (sender_id, client_message_id) DO NOTHING
        RETURNING id
        """,
        sender_id, group_id, chat_id, text,
        client_message_id, ephemeral_mode.value, ttl_seconds,
    )
    if r is not None:
        fresh = await conn.fetchrow(
            f"""
            SELECT {_COLS_WITH_SENDER}
            FROM messages m
            JOIN users u ON u.id = m.sender_id
            WHERE m.id = $1
            """,
            r["id"],
        )
        assert fresh is not None
        return _row(fresh, with_sender=True), True

    existing = await get_by_idempotency_key(
        conn, sender_id=sender_id, client_message_id=client_message_id,
    )
    assert existing is not None, "ON CONFLICT fired but existing row not found"
    return existing, False


# ---------- listing ----------

async def list_active_in_group(
    conn: asyncpg.Connection,
    *,
    group_id: GroupId,
    limit: int,
    before: datetime | None = None,
) -> list[MessageRow]:
    rows = await conn.fetch(
        f"""
        SELECT {_COLS_WITH_SENDER}
        FROM messages m
        JOIN users u ON u.id = m.sender_id
        WHERE m.group_id = $1
          AND m.status = 'active'
          AND m.expires_at > now()
          AND ($2::timestamptz IS NULL OR m.created_at < $2)
        ORDER BY m.created_at DESC
        LIMIT $3
        """,
        group_id, before, limit,
    )
    return [_row(r, with_sender=True) for r in rows]


# ---------- summaries ----------

async def latest_active_per_group(
    conn: asyncpg.Connection,
    group_ids: list[GroupId],
) -> dict[GroupId, tuple[datetime, str | None]]:
    """For each group, return (last_message_at, last_preview) of the newest
    currently-active message. Groups with no active messages are omitted.
    """
    if not group_ids:
        return {}
    rows = await conn.fetch(
        """
        SELECT DISTINCT ON (group_id)
               group_id, created_at, text_content, type::text AS type
        FROM messages
        WHERE group_id = ANY($1::uuid[])
          AND status = 'active'
          AND expires_at > now()
        ORDER BY group_id, created_at DESC
        """,
        group_ids,
    )
    out: dict[GroupId, tuple[datetime, str | None]] = {}
    for r in rows:
        # For image messages the preview text is None — the UI shows a
        # generic "Foto" placeholder itself.
        preview = r["text_content"] if r["type"] == "text" else None
        out[GroupId(r["group_id"])] = (r["created_at"], preview)
    return out


# ---------- expiration ----------

async def mark_expired_due(conn: asyncpg.Connection) -> tuple[int, list[UUID]]:
    """Flip all active messages whose TTL has passed to status='expired'.

    Returns (rows_flipped, media_ids_of_expired_messages). The media_ids list
    only contains non-null values — used by the cascade step to expire
    associated media rows.
    """
    rows = await conn.fetch(
        """
        UPDATE messages
           SET status = 'expired'
         WHERE status = 'active'
           AND expires_at <= now()
        RETURNING id, media_id
        """,
    )
    media_ids = [r["media_id"] for r in rows if r["media_id"] is not None]
    return len(rows), media_ids
