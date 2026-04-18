"""/groups routes — child-facing."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from blink.api.deps import AuthDep, ConnDep
from blink.api.schemas import (
    CreateGroupBody,
    CreateGroupResponse,
    GroupDetailView,
    GroupListResponse,
    GroupMemberView,
    GroupView,
    InviteToGroupBody,
    JoinGroupBody,
    JoinOrInviteResponse,
)
from blink.authz.require import require_group_access
from blink.errors import NotFoundError
from blink.rate_limit.deps import rate_limit
from blink.repos import groups as groups_repo
from blink.repos import messages as messages_repo
from blink.repos import users as users_repo
from blink.services import group_service
from blink.types import GroupId, GroupMembershipStatus, UserId

router = APIRouter(prefix="/groups", tags=["groups"])


def _to_group_view(g: groups_repo.GroupRow, active: int, pending: int) -> GroupView:
    return GroupView(
        id=g.id,
        name=g.name,
        status=g.status,
        created_by_child_id=g.created_by_child_id,
        invite_code=g.invite_code,
        active_member_count=active,
        pending_member_count=pending,
        created_at=g.created_at,
        approved_at=g.approved_at,
    )


@router.post(
    "",
    response_model=CreateGroupResponse,
    status_code=201,
    dependencies=[rate_limit("groups:create")],
)
async def create_group(
    body: CreateGroupBody,
    ctx: AuthDep,
    conn: ConnDep,
) -> CreateGroupResponse:
    group, memberships, request = await group_service.create_group(
        conn, ctx, name=body.name,
        initial_member_ids=[UserId(i) for i in body.initial_member_ids],
    )

    # Build member view — enrich with display names in one query.
    member_user_ids = [m.child_user_id for m in memberships]
    user_rows = {u.id: u for u in await users_repo.get_many(conn, member_user_ids)}
    member_views = [
        GroupMemberView(
            child_user_id=m.child_user_id,
            display_name=user_rows[m.child_user_id].display_name if m.child_user_id in user_rows else None,
            avatar_initial=user_rows[m.child_user_id].avatar_initial if m.child_user_id in user_rows else None,
            role=m.role,
            status=m.status,
        )
        for m in memberships
    ]
    active = sum(1 for m in memberships if m.status == GroupMembershipStatus.ACTIVE)
    pending = sum(1 for m in memberships if m.status == GroupMembershipStatus.PENDING)

    detail = GroupDetailView(
        **_to_group_view(group, active, pending).model_dump(by_alias=False),
        members=member_views,
    )
    return CreateGroupResponse(
        group=detail,
        pending_approval=request is not None,
        request_id=request.id if request else None,
    )


@router.post(
    "/join",
    response_model=JoinOrInviteResponse,
    status_code=200,
    dependencies=[rate_limit("groups:join")],
)
async def join_group(
    body: JoinGroupBody,
    ctx: AuthDep,
    conn: ConnDep,
) -> JoinOrInviteResponse:
    group, membership, request = await group_service.join_group(
        conn, ctx, invite_code=body.invite_code,
    )
    return JoinOrInviteResponse(
        group_id=group.id,
        target_child_id=membership.child_user_id,
        membership_status=membership.status,
        pending_approval=request is not None,
        request_id=request.id if request else None,
    )


@router.post(
    "/{group_id}/invite",
    response_model=JoinOrInviteResponse,
    status_code=200,
    dependencies=[rate_limit("groups:invite")],
)
async def invite_to_group(
    group_id: UUID,
    body: InviteToGroupBody,
    ctx: AuthDep,
    conn: ConnDep,
) -> JoinOrInviteResponse:
    membership, request = await group_service.invite_to_group(
        conn, ctx,
        group_id=GroupId(group_id),
        target_child_id=UserId(body.target_child_id),
    )
    return JoinOrInviteResponse(
        group_id=GroupId(group_id),
        target_child_id=membership.child_user_id,
        membership_status=membership.status,
        pending_approval=request is not None,
        request_id=request.id if request else None,
    )


@router.get("", response_model=GroupListResponse)
async def list_groups(ctx: AuthDep, conn: ConnDep) -> GroupListResponse:
    rows = await group_service.list_groups_for_child(conn, ctx)
    summaries = await messages_repo.latest_active_per_group(
        conn, [g.id for g, _ in rows],
    )
    views: list[GroupView] = []
    for g, _my_status in rows:
        active, pending = await groups_repo.count_members(conn, g.id)
        view = _to_group_view(g, active, pending)
        if g.id in summaries:
            last_at, last_preview = summaries[g.id]
            view = view.model_copy(update={
                "last_message_at": last_at,
                "last_message_preview": last_preview,
            })
        views.append(view)
    return GroupListResponse(groups=views)


@router.get("/{group_id}", response_model=GroupDetailView)
async def get_group_detail(
    group_id: UUID,
    ctx: AuthDep,
    conn: ConnDep,
) -> GroupDetailView:
    gid = GroupId(group_id)
    await require_group_access(conn, ctx, group_id=gid)

    group = await groups_repo.get_group(conn, gid)
    if group is None:
        raise NotFoundError("Group not found")

    memberships = await groups_repo.list_memberships_for_group(conn, gid)
    member_user_ids = [m.child_user_id for m in memberships]
    user_rows = {u.id: u for u in await users_repo.get_many(conn, member_user_ids)}
    active = sum(1 for m in memberships if m.status == GroupMembershipStatus.ACTIVE)
    pending = sum(1 for m in memberships if m.status == GroupMembershipStatus.PENDING)

    return GroupDetailView(
        **_to_group_view(group, active, pending).model_dump(by_alias=False),
        members=[
            GroupMemberView(
                child_user_id=m.child_user_id,
                display_name=user_rows[m.child_user_id].display_name if m.child_user_id in user_rows else None,
                avatar_initial=user_rows[m.child_user_id].avatar_initial if m.child_user_id in user_rows else None,
                role=m.role,
                status=m.status,
            )
            for m in memberships
        ],
    )
