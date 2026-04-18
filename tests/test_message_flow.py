"""Text message create + list + idempotency + authz."""
from __future__ import annotations

import pytest

from blink.errors import AuthzError, UnsupportedError, ValidationError
from blink.services import message_service
from blink.types import EphemeralMode, MessageStatus, MessageType


pytestmark = pytest.mark.asyncio


# ---------------- create ----------------

async def test_member_can_create_text_message(
    conn, make_child, make_active_group,
):
    alice = await make_child("Alice")
    gid = await make_active_group(alice)

    msg = await message_service.create_text_message(
        conn, alice.ctx,
        group_id=gid, chat_id=None,
        type=MessageType.TEXT,
        text="Hej!",
        client_message_id="cm-1",
        ephemeral_mode=EphemeralMode.TIMER,
        ttl_seconds=60,
    )
    assert msg.sender_id == alice.user_id
    assert msg.group_id == gid
    assert msg.text_content == "Hej!"
    assert msg.status == MessageStatus.ACTIVE
    assert msg.ttl_seconds == 60


async def test_non_member_cannot_send(
    conn, make_child, make_active_group,
):
    alice = await make_child("Alice")
    outsider = await make_child("Outsider")
    gid = await make_active_group(alice)

    with pytest.raises(AuthzError):
        await message_service.create_text_message(
            conn, outsider.ctx,
            group_id=gid, chat_id=None,
            type=MessageType.TEXT,
            text="Hej!",
            client_message_id="cm-out",
            ephemeral_mode=EphemeralMode.TIMER,
            ttl_seconds=60,
        )


async def test_empty_text_rejected(
    conn, make_child, make_active_group,
):
    alice = await make_child("Alice")
    gid = await make_active_group(alice)

    with pytest.raises(ValidationError):
        await message_service.create_text_message(
            conn, alice.ctx,
            group_id=gid, chat_id=None,
            type=MessageType.TEXT,
            text="   ",
            client_message_id="cm-empty",
            ephemeral_mode=EphemeralMode.TIMER,
            ttl_seconds=60,
        )


async def test_image_type_rejected_in_v1(
    conn, make_child, make_active_group,
):
    alice = await make_child("Alice")
    gid = await make_active_group(alice)

    with pytest.raises(UnsupportedError) as exc:
        await message_service.create_text_message(
            conn, alice.ctx,
            group_id=gid, chat_id=None,
            type=MessageType.IMAGE,
            text=None,
            client_message_id="cm-img",
            ephemeral_mode=EphemeralMode.TIMER,
            ttl_seconds=60,
        )
    assert "message_type" in exc.value.feature


async def test_after_read_rejected_explicitly(
    conn, make_child, make_active_group,
):
    alice = await make_child("Alice")
    gid = await make_active_group(alice)

    with pytest.raises(UnsupportedError) as exc:
        await message_service.create_text_message(
            conn, alice.ctx,
            group_id=gid, chat_id=None,
            type=MessageType.TEXT,
            text="Hej",
            client_message_id="cm-ar",
            ephemeral_mode=EphemeralMode.AFTER_READ,
            ttl_seconds=60,
        )
    assert "ephemeral_mode" in exc.value.feature


async def test_invalid_ttl_rejected(
    conn, make_child, make_active_group,
):
    alice = await make_child("Alice")
    gid = await make_active_group(alice)

    with pytest.raises(ValidationError):
        await message_service.create_text_message(
            conn, alice.ctx,
            group_id=gid, chat_id=None,
            type=MessageType.TEXT,
            text="Hej",
            client_message_id="cm-ttl-low",
            ephemeral_mode=EphemeralMode.TIMER,
            ttl_seconds=0,
        )
    with pytest.raises(ValidationError):
        await message_service.create_text_message(
            conn, alice.ctx,
            group_id=gid, chat_id=None,
            type=MessageType.TEXT,
            text="Hej",
            client_message_id="cm-ttl-high",
            ephemeral_mode=EphemeralMode.TIMER,
            ttl_seconds=700_000,
        )


async def test_chat_id_rejected_in_v1(
    conn, make_child, make_active_group,
):
    import uuid
    alice = await make_child("Alice")
    _ = await make_active_group(alice)  # ensure DB has data

    with pytest.raises(UnsupportedError):
        await message_service.create_text_message(
            conn, alice.ctx,
            group_id=None, chat_id=uuid.uuid4(),
            type=MessageType.TEXT,
            text="Hej",
            client_message_id="cm-chat",
            ephemeral_mode=EphemeralMode.TIMER,
            ttl_seconds=60,
        )


# ---------------- idempotency ----------------

async def test_duplicate_client_message_id_is_idempotent(
    conn, make_child, make_active_group,
):
    alice = await make_child("Alice")
    gid = await make_active_group(alice)

    first = await message_service.create_text_message(
        conn, alice.ctx,
        group_id=gid, chat_id=None,
        type=MessageType.TEXT,
        text="Hej!",
        client_message_id="cm-same",
        ephemeral_mode=EphemeralMode.TIMER,
        ttl_seconds=60,
    )
    second = await message_service.create_text_message(
        conn, alice.ctx,
        group_id=gid, chat_id=None,
        type=MessageType.TEXT,
        text="Different text, same idempotency key",
        client_message_id="cm-same",
        ephemeral_mode=EphemeralMode.TIMER,
        ttl_seconds=60,
    )
    assert first.id == second.id
    # Replay returns the original content, not the new text.
    assert second.text_content == "Hej!"


# ---------------- list ----------------

async def test_list_returns_only_active_messages(
    conn, make_child, make_active_group,
):
    alice = await make_child("Alice")
    gid = await make_active_group(alice)

    m1 = await message_service.create_text_message(
        conn, alice.ctx,
        group_id=gid, chat_id=None,
        type=MessageType.TEXT,
        text="Første",
        client_message_id="cm-a",
        ephemeral_mode=EphemeralMode.TIMER,
        ttl_seconds=60,
    )
    m2 = await message_service.create_text_message(
        conn, alice.ctx,
        group_id=gid, chat_id=None,
        type=MessageType.TEXT,
        text="Anden",
        client_message_id="cm-b",
        ephemeral_mode=EphemeralMode.TIMER,
        ttl_seconds=60,
    )

    msgs = await message_service.list_group_messages(
        conn, alice.ctx, group_id=gid, limit=50,
    )
    ids = {m.id for m in msgs}
    assert m1.id in ids
    assert m2.id in ids
    assert all(m.status == MessageStatus.ACTIVE for m in msgs)


async def test_list_excludes_manually_expired_rows(
    conn, make_child, make_active_group,
):
    alice = await make_child("Alice")
    gid = await make_active_group(alice)

    good = await message_service.create_text_message(
        conn, alice.ctx,
        group_id=gid, chat_id=None,
        type=MessageType.TEXT,
        text="aktiv",
        client_message_id="cm-good",
        ephemeral_mode=EphemeralMode.TIMER,
        ttl_seconds=60,
    )
    gone = await message_service.create_text_message(
        conn, alice.ctx,
        group_id=gid, chat_id=None,
        type=MessageType.TEXT,
        text="udløbet",
        client_message_id="cm-gone",
        ephemeral_mode=EphemeralMode.TIMER,
        ttl_seconds=60,
    )
    # Manually flip one to expired — same effect as the background job.
    await conn.execute(
        "UPDATE messages SET status='expired' WHERE id = $1", gone.id,
    )

    msgs = await message_service.list_group_messages(
        conn, alice.ctx, group_id=gid, limit=50,
    )
    ids = {m.id for m in msgs}
    assert good.id in ids
    assert gone.id not in ids


# ---------------- authz ----------------

async def test_parent_cannot_send_as_child(
    conn, make_child, make_parent, link_parent_child, make_active_group,
):
    alice = await make_child("Alice")
    mom = await make_parent("Mom")
    await link_parent_child(mom, alice)
    gid = await make_active_group(alice)

    # Mom is a linked parent; she can READ Alice's group, but cannot SEND.
    with pytest.raises(AuthzError):
        await message_service.create_text_message(
            conn, mom.ctx,
            group_id=gid, chat_id=None,
            type=MessageType.TEXT,
            text="Hej fra mor",
            client_message_id="cm-mom",
            ephemeral_mode=EphemeralMode.TIMER,
            ttl_seconds=60,
        )


async def test_non_member_child_cannot_list_group_messages(
    conn, make_child, make_active_group,
):
    alice = await make_child("Alice")
    outsider = await make_child("Outsider")
    gid = await make_active_group(alice)

    with pytest.raises(AuthzError):
        await message_service.list_group_messages(
            conn, outsider.ctx, group_id=gid, limit=50,
        )
