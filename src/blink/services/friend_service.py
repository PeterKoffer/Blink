"""Friend flow business logic.

State machine:
    create_request:  (none) -> pending_parent
    approve:         pending_parent -> approved  + create friendship
    decline:         pending_parent -> declined
"""
from __future__ import annotations

import asyncpg

from blink.audit import Events, write_audit
from blink.auth.context import AuthContext
from blink.authz.require import (
    require_active_user,
    require_child,
    require_parent,
    require_parent_can_review_child,
)
from blink.errors import NotFoundError, StateConflictError
from blink.obs.metrics import count_approval
from blink.repos import friends as friends_repo
from blink.types import (
    FriendRequestId,
    FriendRequestStatus,
    UserId,
)


async def create_friend_request(
    conn: asyncpg.Connection,
    ctx: AuthContext,
    *,
    target_child_id: UserId,
    method: str | None = None,
) -> friends_repo.FriendRequestRow:
    """Idempotent: if a pending request already exists, return it."""
    require_child(ctx)

    if ctx.user_id == target_child_id:
        raise StateConflictError("Cannot friend yourself")

    async with conn.transaction():
        await require_active_user(conn, target_child_id)

        existing_friendship = await friends_repo.get_active_friendship(
            conn, ctx.user_id, target_child_id
        )
        if existing_friendship is not None:
            raise StateConflictError("Already friends")

        existing_pending = await friends_repo.get_pending_between(
            conn, ctx.user_id, target_child_id
        )
        if existing_pending is not None:
            return existing_pending

        req = await friends_repo.insert_request(
            conn,
            requester=ctx.user_id,
            target=target_child_id,
            method=method,
        )
        await write_audit(
            conn,
            event_type=Events.FRIEND_REQUEST_CREATED,
            actor_user_id=ctx.user_id,
            target_type="friend_request",
            target_id=req.id,
            payload={"target_child_id": str(target_child_id)},
        )
        return req


async def approve_friend_request(
    conn: asyncpg.Connection,
    ctx: AuthContext,
    *,
    request_id: FriendRequestId,
) -> tuple[friends_repo.FriendRequestRow, friends_repo.FriendshipRow]:
    require_parent(ctx)
    assert ctx.parent_account_id is not None

    async with conn.transaction():
        req = await friends_repo.get_request(conn, request_id)
        if req is None:
            raise NotFoundError("Friend request not found")
        if req.status != FriendRequestStatus.PENDING_PARENT:
            raise StateConflictError(f"Request already reviewed (status={req.status.value})")

        # The requesting child must be linked to this parent.
        await require_parent_can_review_child(
            conn, ctx, child_user_id=req.requester_child_id
        )

        updated = await friends_repo.mark_reviewed(
            conn,
            request_id=request_id,
            new_status=FriendRequestStatus.APPROVED,
            reviewed_by=ctx.parent_account_id,
        )

        # Idempotency on the friendship side: don't error if it already exists.
        existing = await friends_repo.get_active_friendship(
            conn, req.requester_child_id, req.target_child_id
        )
        if existing is not None:
            friendship = existing
        else:
            friendship = await friends_repo.insert_friendship(
                conn,
                child_a=req.requester_child_id,
                child_b=req.target_child_id,
            )
            await write_audit(
                conn,
                event_type=Events.FRIENDSHIP_ACTIVATED,
                actor_parent_account_id=ctx.parent_account_id,
                target_type="friendship",
                target_id=friendship.id,
                payload={
                    "child_user_id_a": str(friendship.child_user_id_a),
                    "child_user_id_b": str(friendship.child_user_id_b),
                },
            )

        await write_audit(
            conn,
            event_type=Events.FRIEND_REQUEST_APPROVED,
            actor_parent_account_id=ctx.parent_account_id,
            target_type="friend_request",
            target_id=request_id,
        )
        count_approval("friend", "approve")
        return updated, friendship


async def decline_friend_request(
    conn: asyncpg.Connection,
    ctx: AuthContext,
    *,
    request_id: FriendRequestId,
) -> friends_repo.FriendRequestRow:
    require_parent(ctx)
    assert ctx.parent_account_id is not None

    async with conn.transaction():
        req = await friends_repo.get_request(conn, request_id)
        if req is None:
            raise NotFoundError("Friend request not found")
        if req.status != FriendRequestStatus.PENDING_PARENT:
            raise StateConflictError(f"Request already reviewed (status={req.status.value})")

        await require_parent_can_review_child(
            conn, ctx, child_user_id=req.requester_child_id
        )

        updated = await friends_repo.mark_reviewed(
            conn,
            request_id=request_id,
            new_status=FriendRequestStatus.DECLINED,
            reviewed_by=ctx.parent_account_id,
        )
        await write_audit(
            conn,
            event_type=Events.FRIEND_REQUEST_DECLINED,
            actor_parent_account_id=ctx.parent_account_id,
            target_type="friend_request",
            target_id=request_id,
        )
        count_approval("friend", "decline")
        return updated


async def list_friends(
    conn: asyncpg.Connection,
    ctx: AuthContext,
) -> list[dict]:
    require_child(ctx)
    return await friends_repo.list_active_friends_of(conn, ctx.user_id)
