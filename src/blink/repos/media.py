"""media data access — raw SQL, typed dataclasses.

State flips use conditional UPDATE (WHERE status='X') so callers get a row
back only when the transition was legal. Zero rows returned = state conflict.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import asyncpg

from blink.types import (
    GroupId,
    MediaAccessStatus,
    MediaId,
    MediaUploadStatus,
    MediaUsageStatus,
    UserId,
)


@dataclass(frozen=True, slots=True)
class MediaRow:
    id: MediaId
    uploader_id: UserId
    group_id: GroupId | None
    chat_id: UUID | None
    r2_key: str
    mime: str
    size_bytes: int
    width: int | None
    height: int | None
    created_at: datetime
    expires_at: datetime
    upload_status: MediaUploadStatus
    access_status: MediaAccessStatus
    usage_status: MediaUsageStatus


_COLS = """
    id, uploader_id, group_id, chat_id, r2_key, mime, size_bytes,
    width, height, created_at, expires_at,
    upload_status::text  AS upload_status,
    access_status::text  AS access_status,
    usage_status::text   AS usage_status
"""


def _row(r: asyncpg.Record) -> MediaRow:
    return MediaRow(
        id=MediaId(r["id"]),
        uploader_id=UserId(r["uploader_id"]),
        group_id=GroupId(r["group_id"]) if r["group_id"] else None,
        chat_id=r["chat_id"],
        r2_key=r["r2_key"],
        mime=r["mime"],
        size_bytes=r["size_bytes"],
        width=r["width"],
        height=r["height"],
        created_at=r["created_at"],
        expires_at=r["expires_at"],
        upload_status=MediaUploadStatus(r["upload_status"]),
        access_status=MediaAccessStatus(r["access_status"]),
        usage_status=MediaUsageStatus(r["usage_status"]),
    )


# ---------- create ----------

async def insert_pending(
    conn: asyncpg.Connection,
    *,
    uploader_id: UserId,
    group_id: GroupId | None,
    chat_id: UUID | None,
    r2_key: str,
    mime: str,
    size_bytes: int,
    width: int | None,
    height: int | None,
    retention_seconds: int,
) -> MediaRow:
    r = await conn.fetchrow(
        f"""
        INSERT INTO media (
            uploader_id, group_id, chat_id, r2_key, mime, size_bytes,
            width, height, expires_at
        )
        VALUES (
            $1, $2, $3, $4, $5, $6,
            $7, $8, now() + make_interval(secs => $9)
        )
        RETURNING {_COLS}
        """,
        uploader_id, group_id, chat_id, r2_key, mime, size_bytes,
        width, height, retention_seconds,
    )
    return _row(r)


# ---------- lookups ----------

async def get(conn: asyncpg.Connection, media_id: MediaId) -> MediaRow | None:
    r = await conn.fetchrow(f"SELECT {_COLS} FROM media WHERE id = $1", media_id)
    return _row(r) if r else None


# ---------- state transitions ----------

async def mark_ready(
    conn: asyncpg.Connection,
    media_id: MediaId,
) -> MediaRow | None:
    """pending -> ready. Returns None if not in pending state."""
    r = await conn.fetchrow(
        f"""
        UPDATE media SET upload_status = 'ready'
         WHERE id = $1 AND upload_status = 'pending'
        RETURNING {_COLS}
        """,
        media_id,
    )
    return _row(r) if r else None


async def claim_attachment(
    conn: asyncpg.Connection,
    *,
    media_id: MediaId,
    expected_uploader_id: UserId,
    expected_group_id: GroupId | None,
    expected_chat_id: UUID | None,
) -> MediaRow | None:
    """Atomically flip usage_status from 'unused' to 'attached', ONLY if all
    gating conditions hold. Returns the updated row, or None if any guard
    failed (state wrong, ownership mismatch, context mismatch).

    Used by message_service when sending an image. Prevents the race where
    two concurrent message creates both try to claim the same media row.
    """
    r = await conn.fetchrow(
        f"""
        UPDATE media
           SET usage_status = 'attached'
         WHERE id = $1
           AND usage_status = 'unused'
           AND upload_status = 'ready'
           AND access_status = 'active'
           AND uploader_id = $2
           AND group_id IS NOT DISTINCT FROM $3
           AND chat_id  IS NOT DISTINCT FROM $4
           AND expires_at > now()
        RETURNING {_COLS}
        """,
        media_id, expected_uploader_id, expected_group_id, expected_chat_id,
    )
    return _row(r) if r else None


async def cascade_expire(
    conn: asyncpg.Connection,
    media_ids: list[MediaId],
) -> int:
    """Flip access_status='expired' on the given media rows.

    Only flips rows currently in 'active'. Returns count of rows flipped.
    Called by the expiration engine's cascade step when messages expire.
    """
    if not media_ids:
        return 0
    result = await conn.execute(
        """
        UPDATE media
           SET access_status = 'expired'
         WHERE access_status = 'active'
           AND id = ANY($1::uuid[])
        """,
        media_ids,
    )
    return int(result.split()[-1]) if result else 0


# ---------- cleanup ----------

async def find_cleanup_candidates(
    conn: asyncpg.Connection,
    *,
    expired_older_than_seconds: int,
    pending_older_than_seconds: int,
    limit: int = 500,
) -> list[MediaId]:
    """Return media ids that are candidates for `mark_deleted`.

    Two categories:
    - access_status='expired' for longer than `expired_older_than_seconds`
    - upload_status='pending' for longer than `pending_older_than_seconds`
      (stuck uploads that never confirmed)
    """
    rows = await conn.fetch(
        """
        SELECT id FROM media
        WHERE (access_status = 'expired'
               AND created_at < now() - make_interval(secs => $1))
           OR (upload_status = 'pending'
               AND created_at < now() - make_interval(secs => $2))
        LIMIT $3
        """,
        expired_older_than_seconds, pending_older_than_seconds, limit,
    )
    return [MediaId(r["id"]) for r in rows]


async def mark_deleted(
    conn: asyncpg.Connection,
    media_ids: list[MediaId],
) -> int:
    """Flip access_status='deleted' for the given ids.

    Does NOT physically remove anything from R2; that's handled by the
    bucket's lifecycle rule (see project_blink_media.md).
    """
    if not media_ids:
        return 0
    r = await conn.execute(
        """
        UPDATE media SET access_status = 'deleted'
         WHERE id = ANY($1::uuid[])
           AND access_status <> 'deleted'
        """,
        media_ids,
    )
    return int(r.split()[-1]) if r else 0
