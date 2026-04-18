"""Friend flow — create, approve, decline, idempotency, wrong-parent."""
from __future__ import annotations

import pytest

from blink.errors import AuthzError, StateConflictError
from blink.repos import friends as friends_repo
from blink.services import friend_service
from blink.types import FriendRequestStatus


pytestmark = pytest.mark.asyncio


async def test_child_creates_friend_request(conn, make_child):
    alice = await make_child("Alice")
    bob = await make_child("Bob")

    req = await friend_service.create_friend_request(
        conn, alice.ctx, target_child_id=bob.user_id,
    )
    assert req.requester_child_id == alice.user_id
    assert req.target_child_id == bob.user_id
    assert req.status == FriendRequestStatus.PENDING_PARENT


async def test_duplicate_pending_request_is_idempotent(conn, make_child):
    alice = await make_child("Alice")
    bob = await make_child("Bob")

    first = await friend_service.create_friend_request(
        conn, alice.ctx, target_child_id=bob.user_id,
    )
    second = await friend_service.create_friend_request(
        conn, alice.ctx, target_child_id=bob.user_id,
    )
    assert first.id == second.id  # same row, not a duplicate


async def test_linked_parent_approves_creates_friendship(
    conn, make_child, make_parent, link_parent_child,
):
    alice = await make_child("Alice")
    bob = await make_child("Bob")
    mom = await make_parent("Mom")
    await link_parent_child(mom, alice)

    req = await friend_service.create_friend_request(
        conn, alice.ctx, target_child_id=bob.user_id,
    )
    updated, friendship = await friend_service.approve_friend_request(
        conn, mom.ctx, request_id=req.id,
    )
    assert updated.status == FriendRequestStatus.APPROVED
    assert updated.reviewed_by_parent_account_id == mom.parent_account_id

    active = await friends_repo.get_active_friendship(conn, alice.user_id, bob.user_id)
    assert active is not None
    assert active.id == friendship.id


async def test_decline_does_not_create_friendship(
    conn, make_child, make_parent, link_parent_child,
):
    alice = await make_child("Alice")
    bob = await make_child("Bob")
    mom = await make_parent("Mom")
    await link_parent_child(mom, alice)

    req = await friend_service.create_friend_request(
        conn, alice.ctx, target_child_id=bob.user_id,
    )
    updated = await friend_service.decline_friend_request(
        conn, mom.ctx, request_id=req.id,
    )
    assert updated.status == FriendRequestStatus.DECLINED

    active = await friends_repo.get_active_friendship(conn, alice.user_id, bob.user_id)
    assert active is None


async def test_wrong_parent_cannot_approve(
    conn, make_child, make_parent, link_parent_child,
):
    alice = await make_child("Alice")
    bob = await make_child("Bob")
    alice_mom = await make_parent("AliceMom")
    stranger = await make_parent("Stranger")
    await link_parent_child(alice_mom, alice)
    # `stranger` is NOT linked to Alice.

    req = await friend_service.create_friend_request(
        conn, alice.ctx, target_child_id=bob.user_id,
    )
    with pytest.raises(AuthzError):
        await friend_service.approve_friend_request(
            conn, stranger.ctx, request_id=req.id,
        )


async def test_cannot_friend_yourself(conn, make_child):
    alice = await make_child("Alice")
    with pytest.raises(StateConflictError):
        await friend_service.create_friend_request(
            conn, alice.ctx, target_child_id=alice.user_id,
        )
