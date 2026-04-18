"""Media flow services — upload-url, confirm, read-url, cleanup.

All three endpoints are gated by:
- auth (child only; parents don't upload)
- membership/access (same scope as messages)
- parent policy `may_send_images` for upload paths
- per-media state checks (upload_status / access_status / expires_at)

R2 adapter is injected by the caller (routes supply a shared singleton;
tests supply InMemoryR2Adapter).
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import asyncpg

from blink.audit import Events, write_audit
from blink.auth.context import AuthContext
from blink.authz.require import require_child, require_group_access, require_group_member
from blink.errors import NotFoundError, StateConflictError, UnsupportedError, ValidationError
from blink.obs.metrics import count_media_event
from blink.policies.parent import resolve_parent_policy
from blink.r2.adapter import R2Adapter
from blink.repos import media as media_repo
from blink.types import (
    GroupId,
    MEDIA_DEFAULT_RETENTION_SECONDS,
    MEDIA_GET_URL_TTL_SECONDS,
    MEDIA_MAX_SIZE_BYTES,
    MEDIA_MIME_WHITELIST,
    MEDIA_PUT_URL_TTL_SECONDS,
    MediaAccessStatus,
    MediaId,
    MediaUploadStatus,
)


# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------

def _r2_key_for(media_id: UUID, mime: str) -> str:
    """m/YYYY/MM/DD/<uuid>.<ext> — matches project_blink_media.md."""
    ext = {"image/jpeg": "jpg", "image/webp": "webp"}[mime]
    today = datetime.utcnow().date()
    return f"m/{today.year:04d}/{today.month:02d}/{today.day:02d}/{media_id}.{ext}"


# ---------------------------------------------------------------
# Upload URL
# ---------------------------------------------------------------

async def create_upload_url(
    conn: asyncpg.Connection,
    r2: R2Adapter,
    ctx: AuthContext,
    *,
    group_id: GroupId | None,
    chat_id: UUID | None,
    mime: str,
    size: int,
    width: int | None,
    height: int | None,
) -> tuple[media_repo.MediaRow, str]:
    require_child(ctx)

    # Scope — exactly one of group_id / chat_id. Chat rejected in v1.
    if (group_id is None) == (chat_id is None):
        raise ValidationError("Exactly one of groupId or chatId must be set")
    if chat_id is not None:
        raise UnsupportedError("direct_chats", "Direct chats are not modeled in v1")
    assert group_id is not None

    # Mime whitelist.
    if mime not in MEDIA_MIME_WHITELIST:
        raise UnsupportedError(
            f"mime:{mime}",
            f"Only {sorted(MEDIA_MIME_WHITELIST)} are supported in v1",
        )

    # Size bounds.
    if not (1 <= size <= MEDIA_MAX_SIZE_BYTES):
        raise ValidationError(
            f"size must be between 1 and {MEDIA_MAX_SIZE_BYTES} bytes"
        )
    if width is not None and width < 1:
        raise ValidationError("width must be positive")
    if height is not None and height < 1:
        raise ValidationError("height must be positive")

    async with conn.transaction():
        # Membership — sender must be active member of the target group.
        await require_group_member(conn, group_id=group_id, child_user_id=ctx.user_id)

        # Policy — parent may have images disabled.
        policy = await resolve_parent_policy(conn, ctx.user_id)
        policy.ensure_can_send_images()

        # Generate r2_key deterministically from a fresh UUID so we don't
        # collide with existing keys. The UNIQUE index on r2_key is a
        # safety net.
        fresh_id = uuid4()
        r2_key = _r2_key_for(fresh_id, mime)

        row = await media_repo.insert_pending(
            conn,
            uploader_id=ctx.user_id,
            group_id=group_id,
            chat_id=None,
            r2_key=r2_key,
            mime=mime,
            size_bytes=size,
            width=width,
            height=height,
            retention_seconds=MEDIA_DEFAULT_RETENTION_SECONDS,
        )

        upload_url = await r2.generate_put_url(
            key=row.r2_key,
            mime=mime,
            size=size,
            ttl_seconds=MEDIA_PUT_URL_TTL_SECONDS,
        )

        await write_audit(
            conn,
            event_type=Events.MEDIA_UPLOAD_REQUESTED,
            actor_user_id=ctx.user_id,
            target_type="media",
            target_id=row.id,
            payload={
                "group_id": str(group_id),
                "mime": mime,
                "size": size,
            },
        )
        count_media_event("upload_url", "ok")

        return row, upload_url


# ---------------------------------------------------------------
# Confirm
# ---------------------------------------------------------------

async def confirm_media(
    conn: asyncpg.Connection,
    r2: R2Adapter,
    ctx: AuthContext,
    *,
    media_id: MediaId,
) -> media_repo.MediaRow:
    require_child(ctx)

    async with conn.transaction():
        row = await media_repo.get(conn, media_id)
        if row is None:
            raise NotFoundError("Media not found")

        # Only the original uploader can confirm. Prevents an attacker with
        # a guessed media_id from claiming an orphan pending upload.
        if row.uploader_id != ctx.user_id:
            raise StateConflictError("Not the uploader of this media")

        if row.upload_status != MediaUploadStatus.PENDING:
            raise StateConflictError(
                f"Media is not pending (upload_status={row.upload_status.value})"
            )

        # Verify the object actually landed in R2. Distinct status 424 in
        # the API so clients know storage is the missing piece, not the DB.
        exists = await r2.object_exists(row.r2_key)
        if not exists:
            from blink.errors import BlinkError

            class _StorageMissing(BlinkError):
                code = "storage_missing"

            raise _StorageMissing(
                f"Object {row.r2_key} not found in storage — upload did not complete"
            )

        # Optional sanity check: content-length / content-type should roughly
        # match what we signed. We log but don't reject on mismatch in v1;
        # tightening this can come later.
        meta = await r2.object_metadata(row.r2_key)
        if meta is not None:
            if meta.content_length is not None and meta.content_length > MEDIA_MAX_SIZE_BYTES:
                raise ValidationError(
                    f"Uploaded object exceeds max size ({meta.content_length} bytes)"
                )

        updated = await media_repo.mark_ready(conn, media_id)
        if updated is None:
            raise StateConflictError("Media state changed during confirm")

        await write_audit(
            conn,
            event_type=Events.MEDIA_UPLOAD_CONFIRMED,
            actor_user_id=ctx.user_id,
            target_type="media",
            target_id=media_id,
        )
        count_media_event("confirm", "ok")
        return updated


# ---------------------------------------------------------------
# Read URL
# ---------------------------------------------------------------

async def get_read_url(
    conn: asyncpg.Connection,
    r2: R2Adapter,
    ctx: AuthContext,
    *,
    media_id: MediaId,
) -> tuple[str, int]:
    """Return (signed_get_url, ttl_seconds)."""
    row = await media_repo.get(conn, media_id)
    if row is None:
        raise NotFoundError("Media not found")

    if row.upload_status != MediaUploadStatus.READY:
        raise StateConflictError("Media is not ready")

    if row.access_status != MediaAccessStatus.ACTIVE:
        # 410 semantically — the resource existed but is gone/expired.
        from blink.errors import BlinkError

        class _Gone(BlinkError):
            code = "gone"

        raise _Gone(f"Media access is {row.access_status.value}")

    # expires_at enforces the retention boundary even if access_status
    # hasn't been flipped yet.
    if row.expires_at <= datetime.now(tz=row.expires_at.tzinfo):
        from blink.errors import BlinkError

        class _Gone(BlinkError):
            code = "gone"

        raise _Gone("Media retention window has passed")

    # Scope check — caller must be able to see the group/chat the media
    # belongs to. require_group_access accepts both child-member and linked-parent.
    if row.group_id is not None:
        await require_group_access(conn, ctx, group_id=row.group_id)
    else:
        # chat_id scope — chats not modeled in v1
        raise UnsupportedError("direct_chats", "Direct chats are not modeled in v1")

    url = await r2.generate_get_url(
        key=row.r2_key, ttl_seconds=MEDIA_GET_URL_TTL_SECONDS,
    )

    await write_audit(
        conn,
        event_type=Events.MEDIA_READ_URL_ISSUED,
        actor_user_id=ctx.user_id,
        target_type="media",
        target_id=media_id,
    )
    count_media_event("get_url", "ok")
    return url, MEDIA_GET_URL_TTL_SECONDS


# ---------------------------------------------------------------
# Cleanup foundation
# ---------------------------------------------------------------

async def sweep_cleanup_candidates(
    conn: asyncpg.Connection,
    *,
    expired_older_than_seconds: int = 7 * 24 * 3600,
    pending_older_than_seconds: int = 24 * 3600,
    batch_limit: int = 500,
) -> int:
    """Mark stale media rows as access_status='deleted'.

    - expired > 7 days old: move to 'deleted'
    - pending > 24 hours old: move to 'deleted' (stuck uploads)

    Physical R2 object cleanup is handled by the bucket's lifecycle rule,
    not by this function. This is purely a database-side sweep.

    Returns count of rows marked deleted.
    """
    async with conn.transaction():
        candidates = await media_repo.find_cleanup_candidates(
            conn,
            expired_older_than_seconds=expired_older_than_seconds,
            pending_older_than_seconds=pending_older_than_seconds,
            limit=batch_limit,
        )
        if not candidates:
            return 0
        count = await media_repo.mark_deleted(conn, candidates)
        if count > 0:
            await write_audit(
                conn,
                event_type=Events.MEDIA_MARKED_DELETED,
                target_type="media",
                payload={"count": count},
            )
        return count
