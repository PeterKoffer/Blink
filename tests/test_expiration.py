"""Expiration engine."""
from __future__ import annotations

import pytest

from blink.repos import messages as messages_repo
from blink.services import expiration_service, message_service
from blink.types import EphemeralMode, MessageStatus, MessageType


pytestmark = pytest.mark.asyncio


async def _insert_raw_expired_msg(conn, sender_id, group_id, *, seconds_ago: int) -> str:
    """Backdate a message so expires_at is already in the past."""
    import uuid
    client_id = f"backdated-{uuid.uuid4().hex[:8]}"
    row = await conn.fetchrow(
        """
        INSERT INTO messages (
            sender_id, group_id, type, text_content,
            client_message_id, ephemeral_mode, ttl_seconds,
            created_at, expires_at, status
        )
        VALUES (
            $1, $2, 'text', $3,
            $4, 'timer', 10,
            now() - ($5 || ' seconds')::interval,
            now() - (($5 - 10) || ' seconds')::interval,
            'active'
        )
        RETURNING id
        """,
        sender_id, group_id, "udløbet besked", client_id, seconds_ago,
    )
    return row["id"]


async def test_past_expires_at_is_flipped_to_expired(
    conn, make_child, make_active_group,
):
    alice = await make_child("Alice")
    gid = await make_active_group(alice)

    mid = await _insert_raw_expired_msg(
        conn, alice.user_id, gid, seconds_ago=30,
    )

    count = await expiration_service.expire_due_messages(conn)
    assert count >= 1

    row = await conn.fetchrow(
        "SELECT status::text AS status FROM messages WHERE id = $1", mid,
    )
    assert row["status"] == "expired"


async def test_future_messages_remain_active(
    conn, make_child, make_active_group,
):
    alice = await make_child("Alice")
    gid = await make_active_group(alice)

    fresh = await message_service.create_text_message(
        conn, alice.ctx,
        group_id=gid, chat_id=None,
        type=MessageType.TEXT,
        text="jeg lever",
        client_message_id="cm-live",
        ephemeral_mode=EphemeralMode.TIMER,
        ttl_seconds=3600,  # 1 hour — well into the future
    )

    await expiration_service.expire_due_messages(conn)

    row = await conn.fetchrow(
        "SELECT status::text AS status FROM messages WHERE id = $1", fresh.id,
    )
    assert row["status"] == "active"


async def test_expiration_is_idempotent(
    conn, make_child, make_active_group,
):
    """Running the job twice does nothing the second time (nothing new due)."""
    alice = await make_child("Alice")
    gid = await make_active_group(alice)

    await _insert_raw_expired_msg(conn, alice.user_id, gid, seconds_ago=30)

    first = await expiration_service.expire_due_messages(conn)
    second = await expiration_service.expire_due_messages(conn)
    assert first >= 1
    assert second == 0


async def test_list_does_not_return_expired_even_before_job_runs(
    conn, make_child, make_active_group,
):
    """Defense-in-depth: list query filters by expires_at > now() itself,
    so even if the job is delayed, logically-expired messages don't leak.
    """
    alice = await make_child("Alice")
    gid = await make_active_group(alice)

    _stale_id = await _insert_raw_expired_msg(
        conn, alice.user_id, gid, seconds_ago=30,
    )
    # Note: status is still 'active' in DB — we have NOT run the job.

    msgs = await messages_repo.list_active_in_group(
        conn, group_id=gid, limit=50,
    )
    assert all(m.expires_at > m.created_at for m in msgs)
    # The stale row is filtered out by expires_at > now()
    assert all(m.id != _stale_id for m in msgs)
    assert all(m.status == MessageStatus.ACTIVE for m in msgs)
