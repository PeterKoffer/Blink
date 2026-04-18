"""Message create + list.

Validation order (matches project_blink_messages.md):
    1. auth (is child)
    2. scope (exactly one of group_id/chat_id; chat_id unsupported in v1)
    3. membership (require_group_member)
    4. type (text or image)
    5. ephemeral_mode (only 'timer' in v1)
    6. ttl (1..604800)
    7. payload shape (text / media_id) per type
    8. image-only: atomic media attach (uploader + context + usage_status)
    9. idempotency via clientMessageId (INSERT ON CONFLICT DO NOTHING)
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

import asyncpg

from blink.audit import Events, write_audit
from blink.auth.context import AuthContext
from blink.authz.require import require_child, require_group_access, require_group_member
from blink.errors import NotFoundError, StateConflictError, UnsupportedError, ValidationError
from blink.obs.metrics import count_message_created
from blink.repos import media as media_repo
from blink.repos import messages as messages_repo
from blink.types import (
    EphemeralMode,
    GroupId,
    MediaId,
    MessageType,
    TEXT_MAX_LEN,
    TTL_MAX_SECONDS,
    TTL_MIN_SECONDS,
)


async def create_message(
    conn: asyncpg.Connection,
    ctx: AuthContext,
    *,
    group_id: GroupId | None,
    chat_id: UUID | None,
    type: MessageType,
    text: str | None,
    media_id: MediaId | None,
    client_message_id: str,
    ephemeral_mode: EphemeralMode,
    ttl_seconds: int,
) -> messages_repo.MessageRow:
    """Unified text + image message create.

    Text path: Sprint 3 semantics, unchanged.
    Image path: Sprint 4. Additional rules (per project_blink_messages.md):
      - mediaId required, text must be null (no captions in v1)
      - media must be ready + active + unused + owned + same scope
      - media.usage_status flips 'unused' -> 'attached' atomically; if the
        flip fails (race or state wrong), the message create rolls back.
    """
    require_child(ctx)

    # Scope.
    if (group_id is None) == (chat_id is None):
        raise ValidationError("Exactly one of groupId or chatId must be set")
    if chat_id is not None:
        raise UnsupportedError(
            "direct_chats",
            message="Direct chats are not modeled in v1 — use groupId",
        )
    assert group_id is not None

    # Ephemeral mode — v1 policy.
    if ephemeral_mode != EphemeralMode.TIMER:
        raise UnsupportedError(
            f"ephemeral_mode:{ephemeral_mode.value}",
            message="Only ephemeralMode=timer is supported in v1",
        )

    # TTL range.
    if not (TTL_MIN_SECONDS <= ttl_seconds <= TTL_MAX_SECONDS):
        raise ValidationError(
            f"ttlSeconds must be between {TTL_MIN_SECONDS} and {TTL_MAX_SECONDS}"
        )

    # clientMessageId shape.
    if not client_message_id or len(client_message_id) > 100:
        raise ValidationError("clientMessageId must be 1..100 chars")

    # --- per-type validation ---
    trimmed_text: str | None = None
    if type == MessageType.TEXT:
        if media_id is not None:
            raise ValidationError("Text messages must not carry mediaId")
        if text is None:
            raise ValidationError("Text messages require 'text'")
        trimmed_text = text.strip()
        if not trimmed_text:
            raise ValidationError("Text cannot be empty or whitespace-only")
        if len(trimmed_text) > TEXT_MAX_LEN:
            raise ValidationError(f"Text exceeds max length ({TEXT_MAX_LEN})")
    elif type == MessageType.IMAGE:
        if media_id is None:
            raise ValidationError("Image messages require 'mediaId'")
        if text is not None:
            raise UnsupportedError(
                "image_caption",
                message="Captions on image messages are not supported in v1",
            )
    else:  # defensive — enum narrowing
        raise UnsupportedError(f"message_type:{type}")

    async with conn.transaction():
        # Membership.
        await require_group_member(
            conn, group_id=group_id, child_user_id=ctx.user_id,
        )

        if type == MessageType.IMAGE:
            assert media_id is not None
            msg, is_fresh = await _insert_image_message_attach_media(
                conn,
                ctx=ctx,
                group_id=group_id,
                media_id=media_id,
                client_message_id=client_message_id,
                ephemeral_mode=ephemeral_mode,
                ttl_seconds=ttl_seconds,
            )
        else:
            assert trimmed_text is not None
            msg, is_fresh = await messages_repo.insert_text_message_atomic(
                conn,
                sender_id=ctx.user_id,
                group_id=group_id,
                chat_id=None,
                text=trimmed_text,
                client_message_id=client_message_id,
                ephemeral_mode=ephemeral_mode,
                ttl_seconds=ttl_seconds,
            )

        if is_fresh:
            await write_audit(
                conn,
                event_type=Events.MESSAGE_CREATED,
                actor_user_id=ctx.user_id,
                target_type="message",
                target_id=msg.id,
                payload={
                    "group_id": str(group_id),
                    "ttl_seconds": ttl_seconds,
                    "type": type.value,
                    "media_id": str(media_id) if media_id else None,
                },
            )
            count_message_created(type.value)
        return msg


async def _insert_image_message_attach_media(
    conn: asyncpg.Connection,
    *,
    ctx: AuthContext,
    group_id: GroupId,
    media_id: MediaId,
    client_message_id: str,
    ephemeral_mode: EphemeralMode,
    ttl_seconds: int,
) -> tuple[messages_repo.MessageRow, bool]:
    """Image-message create + media attachment, atomic.

    Order:
    1. Check for idempotent replay first — if (sender, clientMessageId)
       already exists, return the old row (media was attached on first send).
    2. Atomic `claim_attachment` on the media row: flips usage_status
       unused→attached only if all gates pass (uploader, context, states).
    3. Insert the message with media_id.

    If step 2 fails (media gone / wrong state / already attached), we raise.
    If step 3 fails on idempotency conflict (race between step 1 and here),
    we refetch and return the existing row — but in that case step 2 may
    have already flipped usage_status. That only happens if the same client
    sends the same clientMessageId twice in rapid succession referring to
    the same media, which is exactly the idempotent replay case; the media
    was genuinely attached by this caller, state is consistent.
    """
    # Pre-check replay — don't attach media if we're just going to return
    # the existing row.
    existing = await messages_repo.get_by_idempotency_key(
        conn, sender_id=ctx.user_id, client_message_id=client_message_id,
    )
    if existing is not None:
        return existing, False

    # Load media for friendlier error messages.
    media_row = await media_repo.get(conn, media_id)
    if media_row is None:
        raise NotFoundError("Media not found")
    # Friendlier errors before the atomic claim.
    if media_row.uploader_id != ctx.user_id:
        raise StateConflictError("Media belongs to a different uploader")
    if media_row.group_id != group_id:
        raise StateConflictError("Media belongs to a different group/chat")

    # Atomic claim — the real gate.
    claimed = await media_repo.claim_attachment(
        conn,
        media_id=media_id,
        expected_uploader_id=ctx.user_id,
        expected_group_id=group_id,
        expected_chat_id=None,
    )
    if claimed is None:
        # State check failed (most likely: already attached / expired / not ready).
        raise StateConflictError(
            "Media cannot be attached — it may already be used, expired, or not ready"
        )

    # Insert the image message row.
    r = await conn.fetchrow(
        """
        INSERT INTO messages (
            sender_id, group_id, chat_id, type, media_id,
            client_message_id, ephemeral_mode, ttl_seconds, expires_at
        )
        VALUES (
            $1, $2, NULL, 'image', $3,
            $4, $5::ephemeral_mode, $6, now() + make_interval(secs => $6)
        )
        ON CONFLICT (sender_id, client_message_id) DO NOTHING
        RETURNING id
        """,
        ctx.user_id, group_id, media_id,
        client_message_id, ephemeral_mode.value, ttl_seconds,
    )
    if r is None:
        # Extremely narrow race: idempotency collision after our pre-check.
        # Refetch and return existing. The media attach above is a slight
        # leak in that case; acceptable for v1.
        existing = await messages_repo.get_by_idempotency_key(
            conn, sender_id=ctx.user_id, client_message_id=client_message_id,
        )
        assert existing is not None
        return existing, False

    await write_audit(
        conn,
        event_type=Events.MEDIA_ATTACHED,
        actor_user_id=ctx.user_id,
        target_type="media",
        target_id=media_id,
        payload={"message_id": str(r["id"]), "group_id": str(group_id)},
    )

    # Reload fully hydrated row with sender JOIN.
    fresh = await conn.fetchrow(
        f"""
        SELECT m.id, m.sender_id, m.group_id, m.chat_id,
               m.type::text AS type, m.text_content, m.media_id,
               m.client_message_id,
               m.ephemeral_mode::text AS ephemeral_mode,
               m.ttl_seconds, m.created_at, m.expires_at,
               m.status::text AS status,
               u.display_name AS sender_display_name,
               u.avatar_initial AS sender_avatar_initial
        FROM messages m
        JOIN users u ON u.id = m.sender_id
        WHERE m.id = $1
        """,
        r["id"],
    )
    assert fresh is not None
    from blink.repos.messages import _row as _msg_row  # internal helper
    return _msg_row(fresh, with_sender=True), True


# Backward-compatible alias so Sprint 3 tests using create_text_message still pass.
async def create_text_message(
    conn: asyncpg.Connection,
    ctx: AuthContext,
    *,
    group_id: GroupId | None,
    chat_id: UUID | None,
    type: MessageType,
    text: str | None,
    client_message_id: str,
    ephemeral_mode: EphemeralMode,
    ttl_seconds: int,
) -> messages_repo.MessageRow:
    return await create_message(
        conn, ctx,
        group_id=group_id, chat_id=chat_id,
        type=type, text=text, media_id=None,
        client_message_id=client_message_id,
        ephemeral_mode=ephemeral_mode,
        ttl_seconds=ttl_seconds,
    )


async def list_group_messages(
    conn: asyncpg.Connection,
    ctx: AuthContext,
    *,
    group_id: GroupId,
    limit: int = 50,
    before: datetime | None = None,
) -> list[messages_repo.MessageRow]:
    # Access check — require_group_access allows both child-members and
    # linked parents to read. Children get their own group; parents get
    # read-only visibility into their linked children's groups.
    await require_group_access(conn, ctx, group_id=group_id)

    if limit < 1 or limit > 200:
        raise ValidationError("limit must be between 1 and 200")

    return await messages_repo.list_active_in_group(
        conn, group_id=group_id, limit=limit, before=before,
    )
