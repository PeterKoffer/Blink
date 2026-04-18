"""/parent routes — approval hub and parent-side listings."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from blink.api.deps import AuthDep, ConnDep
from blink.api.schemas import (
    PendingFriendRequestItem,
    PendingGroupRequestItem,
    PendingRequestsResponse,
    ReviewResult,
)
from blink.authz.require import require_parent
from blink.repos import friends as friends_repo
from blink.repos import group_requests as gr_repo
from blink.repos import groups as groups_repo
from blink.repos import users as users_repo
from blink.services import approval_service, friend_service
from blink.types import FriendRequestId, GroupRequestId, UserId

router = APIRouter(prefix="/parent", tags=["parent"])


# ---------- Pending hub ----------

@router.get("/requests/pending", response_model=PendingRequestsResponse)
async def list_pending(ctx: AuthDep, conn: ConnDep) -> PendingRequestsResponse:
    require_parent(ctx)
    assert ctx.parent_account_id is not None

    friend_rows = await friends_repo.list_pending_for_parent(conn, ctx.parent_account_id)
    group_rows = await gr_repo.list_pending_for_parent(conn, ctx.parent_account_id)

    # Enrich with display names in one bulk lookup.
    user_ids: list[UserId] = []
    group_ids_for_names: set[UUID] = set()
    for fr in friend_rows:
        user_ids.append(fr.requester_child_id)
        user_ids.append(fr.target_child_id)
    for gr in group_rows:
        user_ids.append(gr.actor_child_id)
        if gr.target_child_id is not None:
            user_ids.append(gr.target_child_id)
        if gr.group_id is not None:
            group_ids_for_names.add(gr.group_id)

    users = {u.id: u for u in await users_repo.get_many(conn, list(set(user_ids)))}

    group_names: dict[UUID, str] = {}
    for gid in group_ids_for_names:
        g = await groups_repo.get_group(conn, gid)  # type: ignore[arg-type]
        if g is not None:
            group_names[g.id] = g.name

    friend_items = [
        PendingFriendRequestItem(
            request_id=fr.id,
            requester_child_id=fr.requester_child_id,
            requester_display_name=(users[fr.requester_child_id].display_name if fr.requester_child_id in users else None),
            target_child_id=fr.target_child_id,
            target_display_name=(users[fr.target_child_id].display_name if fr.target_child_id in users else None),
            method=fr.method,
            created_at=fr.created_at,
        )
        for fr in friend_rows
    ]

    group_items = [
        PendingGroupRequestItem(
            request_id=gr.id,
            type=gr.type,
            actor_child_id=gr.actor_child_id,
            actor_display_name=(users[gr.actor_child_id].display_name if gr.actor_child_id in users else None),
            group_id=gr.group_id,
            group_name=group_names.get(gr.group_id) if gr.group_id else None,
            target_child_id=gr.target_child_id,
            target_display_name=(
                users[gr.target_child_id].display_name
                if gr.target_child_id and gr.target_child_id in users else None
            ),
            requested_name=gr.requested_name,
            created_at=gr.created_at,
        )
        for gr in group_rows
    ]

    return PendingRequestsResponse(friend_requests=friend_items, group_requests=group_items)


# ---------- Friend review ----------

@router.post("/requests/friend/{request_id}/approve", response_model=ReviewResult)
async def approve_friend(
    request_id: UUID,
    ctx: AuthDep,
    conn: ConnDep,
) -> ReviewResult:
    updated, _friendship = await friend_service.approve_friend_request(
        conn, ctx, request_id=FriendRequestId(request_id),
    )
    assert updated.reviewed_at is not None
    return ReviewResult(
        request_id=updated.id,
        status=updated.status,
        reviewed_at=updated.reviewed_at,
    )


@router.post("/requests/friend/{request_id}/decline", response_model=ReviewResult)
async def decline_friend(
    request_id: UUID,
    ctx: AuthDep,
    conn: ConnDep,
) -> ReviewResult:
    updated = await friend_service.decline_friend_request(
        conn, ctx, request_id=FriendRequestId(request_id),
    )
    assert updated.reviewed_at is not None
    return ReviewResult(
        request_id=updated.id,
        status=updated.status,
        reviewed_at=updated.reviewed_at,
    )


# ---------- Group review ----------

@router.post("/requests/group/{request_id}/approve", response_model=ReviewResult)
async def approve_group(
    request_id: UUID,
    ctx: AuthDep,
    conn: ConnDep,
) -> ReviewResult:
    """Dispatch by request type so the client has one endpoint per review surface.

    Type is looked up inside the service — routes don't branch on business state.
    """
    gid = GroupRequestId(request_id)
    # Load the request to know which service method to call.
    req = await gr_repo.get(conn, gid)
    if req is None:
        from blink.errors import NotFoundError
        raise NotFoundError("Group request not found")

    from blink.types import GroupRequestType
    if req.type == GroupRequestType.CREATE_GROUP:
        updated = await approval_service.approve_group_create(conn, ctx, request_id=gid)
    elif req.type == GroupRequestType.JOIN_GROUP:
        updated = await approval_service.approve_group_join(conn, ctx, request_id=gid)
    else:  # INVITE_TO_GROUP
        updated = await approval_service.approve_group_invite(conn, ctx, request_id=gid)

    assert updated.reviewed_at is not None
    return ReviewResult(
        request_id=updated.id,
        status=updated.status,
        reviewed_at=updated.reviewed_at,
    )


@router.post("/requests/group/{request_id}/decline", response_model=ReviewResult)
async def decline_group(
    request_id: UUID,
    ctx: AuthDep,
    conn: ConnDep,
) -> ReviewResult:
    gid = GroupRequestId(request_id)
    req = await gr_repo.get(conn, gid)
    if req is None:
        from blink.errors import NotFoundError
        raise NotFoundError("Group request not found")

    from blink.types import GroupRequestType
    if req.type == GroupRequestType.CREATE_GROUP:
        updated = await approval_service.decline_group_create(conn, ctx, request_id=gid)
    elif req.type == GroupRequestType.JOIN_GROUP:
        updated = await approval_service.decline_group_join(conn, ctx, request_id=gid)
    else:
        updated = await approval_service.decline_group_invite(conn, ctx, request_id=gid)

    assert updated.reviewed_at is not None
    return ReviewResult(
        request_id=updated.id,
        status=updated.status,
        reviewed_at=updated.reviewed_at,
    )
