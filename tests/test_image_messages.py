"""Image message create — ownership, context, no-reuse."""
from __future__ import annotations

import pytest

from blink.errors import StateConflictError, UnsupportedError
from blink.repos import media as media_repo
from blink.services import media_service, message_service
from blink.types import (
    EphemeralMode,
    MediaUsageStatus,
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


async def test_active_member_can_send_image(
    conn, r2, make_child, make_active_group,
):
    alice = await make_child("Alice")
    gid = await make_active_group(alice)
    media = await _prepare_ready_media(conn, r2, alice, gid)

    msg = await message_service.create_message(
        conn, alice.ctx,
        group_id=gid, chat_id=None,
        type=MessageType.IMAGE,
        text=None,
        media_id=media.id,
        client_message_id="img-1",
        ephemeral_mode=EphemeralMode.TIMER,
        ttl_seconds=60,
    )
    assert msg.type == MessageType.IMAGE
    assert msg.media_id == media.id
    assert msg.text_content is None


async def test_sending_image_flips_usage_status_to_attached(
    conn, r2, make_child, make_active_group,
):
    alice = await make_child("Alice")
    gid = await make_active_group(alice)
    media = await _prepare_ready_media(conn, r2, alice, gid)

    await message_service.create_message(
        conn, alice.ctx,
        group_id=gid, chat_id=None,
        type=MessageType.IMAGE, text=None, media_id=media.id,
        client_message_id="img-1",
        ephemeral_mode=EphemeralMode.TIMER, ttl_seconds=60,
    )

    fresh = await media_repo.get(conn, media.id)
    assert fresh is not None
    assert fresh.usage_status == MediaUsageStatus.ATTACHED


async def test_media_cannot_be_reused_in_second_message(
    conn, r2, make_child, make_active_group,
):
    alice = await make_child("Alice")
    gid = await make_active_group(alice)
    media = await _prepare_ready_media(conn, r2, alice, gid)

    await message_service.create_message(
        conn, alice.ctx,
        group_id=gid, chat_id=None,
        type=MessageType.IMAGE, text=None, media_id=media.id,
        client_message_id="img-1",
        ephemeral_mode=EphemeralMode.TIMER, ttl_seconds=60,
    )

    # Second message tries to reference the same media — must fail.
    with pytest.raises(StateConflictError):
        await message_service.create_message(
            conn, alice.ctx,
            group_id=gid, chat_id=None,
            type=MessageType.IMAGE, text=None, media_id=media.id,
            client_message_id="img-2",  # different idempotency key
            ephemeral_mode=EphemeralMode.TIMER, ttl_seconds=60,
        )


async def test_uploader_mismatch_rejected(
    conn, r2, make_child, make_active_group, make_friendship,
):
    alice = await make_child("Alice")
    bob = await make_child("Bob")
    await make_friendship(alice, bob)
    gid = await make_active_group(alice, other_members=[bob])
    # Alice uploads media; Bob tries to attach it to his own message.
    media = await _prepare_ready_media(conn, r2, alice, gid)

    with pytest.raises(StateConflictError):
        await message_service.create_message(
            conn, bob.ctx,
            group_id=gid, chat_id=None,
            type=MessageType.IMAGE, text=None, media_id=media.id,
            client_message_id="img-bob",
            ephemeral_mode=EphemeralMode.TIMER, ttl_seconds=60,
        )


async def test_context_mismatch_rejected(
    conn, r2, make_child, make_active_group, make_friendship,
):
    alice = await make_child("Alice")
    bob = await make_child("Bob")
    await make_friendship(alice, bob)
    gid_a = await make_active_group(alice, other_members=[bob])
    gid_b = await make_active_group(alice, name="OtherGroup", other_members=[bob])

    # Media was created for group A; message tries to attach it in group B.
    media = await _prepare_ready_media(conn, r2, alice, gid_a)

    with pytest.raises(StateConflictError):
        await message_service.create_message(
            conn, alice.ctx,
            group_id=gid_b, chat_id=None,
            type=MessageType.IMAGE, text=None, media_id=media.id,
            client_message_id="img-xgroup",
            ephemeral_mode=EphemeralMode.TIMER, ttl_seconds=60,
        )


async def test_image_with_caption_rejected_in_v1(
    conn, r2, make_child, make_active_group,
):
    alice = await make_child("Alice")
    gid = await make_active_group(alice)
    media = await _prepare_ready_media(conn, r2, alice, gid)

    with pytest.raises(UnsupportedError) as exc:
        await message_service.create_message(
            conn, alice.ctx,
            group_id=gid, chat_id=None,
            type=MessageType.IMAGE,
            text="this is a caption",  # not allowed in v1
            media_id=media.id,
            client_message_id="img-cap",
            ephemeral_mode=EphemeralMode.TIMER, ttl_seconds=60,
        )
    assert "caption" in exc.value.feature
