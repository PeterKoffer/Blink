"""Expiration engine — media cascade."""
from __future__ import annotations

import pytest

from blink.repos import media as media_repo
from blink.services import expiration_service, media_service, message_service
from blink.types import (
    EphemeralMode,
    MediaAccessStatus,
    MessageType,
)


pytestmark = pytest.mark.asyncio


async def _prepare_ready_media(conn, r2, child, gid):
    row, _url = await media_service.create_upload_url(
        conn, r2, child.ctx,
        group_id=gid, chat_id=None,
        mime="image/jpeg", size=500_000, width=1600, height=1200,
    )
    r2.simulate_upload(row.r2_key, mime="image/jpeg", size=500_000)
    await media_service.confirm_media(conn, r2, child.ctx, media_id=row.id)
    return row


async def test_image_message_expiration_cascades_to_media(
    conn, r2, make_child, make_active_group,
):
    alice = await make_child("Alice")
    gid = await make_active_group(alice)
    media = await _prepare_ready_media(conn, r2, alice, gid)

    msg = await message_service.create_message(
        conn, alice.ctx,
        group_id=gid, chat_id=None,
        type=MessageType.IMAGE, text=None, media_id=media.id,
        client_message_id="img-exp",
        ephemeral_mode=EphemeralMode.TIMER, ttl_seconds=60,
    )

    # Backdate expires_at so the engine will expire it.
    await conn.execute(
        "UPDATE messages SET expires_at = now() - interval '1 second' WHERE id = $1",
        msg.id,
    )

    msg_count, media_count = await expiration_service.expire_due_messages(conn)
    assert msg_count >= 1
    assert media_count >= 1

    # Media should now be access_status='expired'.
    fresh = await media_repo.get(conn, media.id)
    assert fresh is not None
    assert fresh.access_status == MediaAccessStatus.EXPIRED


async def test_cascade_is_idempotent(
    conn, r2, make_child, make_active_group,
):
    alice = await make_child("Alice")
    gid = await make_active_group(alice)
    media = await _prepare_ready_media(conn, r2, alice, gid)

    msg = await message_service.create_message(
        conn, alice.ctx,
        group_id=gid, chat_id=None,
        type=MessageType.IMAGE, text=None, media_id=media.id,
        client_message_id="img-idempotent",
        ephemeral_mode=EphemeralMode.TIMER, ttl_seconds=60,
    )
    await conn.execute(
        "UPDATE messages SET expires_at = now() - interval '1 second' WHERE id = $1",
        msg.id,
    )

    first = await expiration_service.expire_due_messages(conn)
    second = await expiration_service.expire_due_messages(conn)
    assert first[0] >= 1  # at least one message flipped in first run
    assert second == (0, 0)  # nothing left to expire
