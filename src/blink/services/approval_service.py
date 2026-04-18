"""Parent approvals hub business logic.

Reviewing an already-reviewed request raises StateConflictError — reviews
must land on pending rows. Authz rule: only a parent linked to the relevant
child can review.
"""
from __future__ import annotations

import asyncpg

from blink.audit import Events, write_audit
from blink.auth.context import AuthContext
from blink.authz.require import require_parent, require_parent_can_review_child
from blink.errors import (
    HardCapExceededError,
    NotFoundError,
    StateConflictError,
    UpgradeRequiredError,
)
from blink.obs.metrics import count_approval
from blink.pricing import cap_for, required_tier_for
from blink.repos import group_requests as gr_repo
from blink.repos import groups as groups_repo
from blink.types import (
    GroupId,
    GroupMembershipStatus,
    GroupRequestId,
    GroupRequestStatus,
    GroupRequestType,
    HARD_MAX_GROUP_MEMBERS,
)


async def _guard_cap_at_approval(
    conn: asyncpg.Connection,
    group_id: GroupId,
) -> None:
    """Defensive cap check at approve time.

    If the cap was tightened between pending creation and this approval
    (e.g. policy change), raise so the parent can upgrade first.
    """
    group = await groups_repo.get_group(conn, group_id)
    if group is None:
        raise NotFoundError("Group not found")
    active, pending = await groups_repo.count_members(conn, group_id)
    total = active + pending
    if total > HARD_MAX_GROUP_MEMBERS:
        raise HardCapExceededError(limit=HARD_MAX_GROUP_MEMBERS)
    current_cap = cap_for(group.member_cap_tier)
    if total > current_cap:
        required = required_tier_for(total)
        assert required is not None
        raise UpgradeRequiredError(
            current_tier=group.member_cap_tier.value,
            required_tier=required.value,
            current_member_count=total,
            current_cap=current_cap,
        )


# ----------------------------------------------------------------
# Group create
# ----------------------------------------------------------------

async def approve_group_create(
    conn: asyncpg.Connection,
    ctx: AuthContext,
    *,
    request_id: GroupRequestId,
) -> gr_repo.GroupRequestRow:
    require_parent(ctx)
    assert ctx.parent_account_id is not None

    async with conn.transaction():
        req = await gr_repo.get(conn, request_id)
        if req is None:
            raise NotFoundError("Group request not found")
        if req.type != GroupRequestType.CREATE_GROUP:
            raise StateConflictError("Wrong request type for this endpoint")
        if req.status != GroupRequestStatus.PENDING_PARENT:
            raise StateConflictError(f"Already reviewed (status={req.status.value})")
        if req.group_id is None:
            raise StateConflictError("create_group request missing group_id")

        await require_parent_can_review_child(
            conn, ctx, child_user_id=req.actor_child_id
        )

        # Cap check — rare but possible if policy tightened between
        # create_group and this approval.
        await _guard_cap_at_approval(conn, req.group_id)

        # Activate the group itself, then flip all pending memberships.
        await groups_repo.activate_group(conn, req.group_id)
        await groups_repo.bulk_activate_pending(conn, req.group_id)

        updated = await gr_repo.mark_reviewed(
            conn,
            request_id=request_id,
            new_status=GroupRequestStatus.APPROVED,
            reviewed_by=ctx.parent_account_id,
        )
        if updated is None:
            raise StateConflictError("Request state changed during review")

        await write_audit(
            conn,
            event_type=Events.GROUP_CREATE_APPROVED,
            actor_parent_account_id=ctx.parent_account_id,
            target_type="group",
            target_id=req.group_id,
            payload={"request_id": str(request_id)},
        )
        count_approval("group_create", "approve")
        return updated


async def decline_group_create(
    conn: asyncpg.Connection,
    ctx: AuthContext,
    *,
    request_id: GroupRequestId,
) -> gr_repo.GroupRequestRow:
    require_parent(ctx)
    assert ctx.parent_account_id is not None

    async with conn.transaction():
        req = await gr_repo.get(conn, request_id)
        if req is None:
            raise NotFoundError("Group request not found")
        if req.type != GroupRequestType.CREATE_GROUP:
            raise StateConflictError("Wrong request type for this endpoint")
        if req.status != GroupRequestStatus.PENDING_PARENT:
            raise StateConflictError(f"Already reviewed (status={req.status.value})")
        if req.group_id is None:
            raise StateConflictError("create_group request missing group_id")

        await require_parent_can_review_child(
            conn, ctx, child_user_id=req.actor_child_id
        )

        # Decline all pending memberships, then soft-delete the group.
        await groups_repo.bulk_decline_pending(conn, req.group_id)
        await groups_repo.soft_delete_group(conn, req.group_id)

        updated = await gr_repo.mark_reviewed(
            conn,
            request_id=request_id,
            new_status=GroupRequestStatus.DECLINED,
            reviewed_by=ctx.parent_account_id,
        )
        if updated is None:
            raise StateConflictError("Request state changed during review")

        await write_audit(
            conn,
            event_type=Events.GROUP_CREATE_DECLINED,
            actor_parent_account_id=ctx.parent_account_id,
            target_type="group",
            target_id=req.group_id,
            payload={"request_id": str(request_id)},
        )
        count_approval("group_create", "decline")
        return updated


# ----------------------------------------------------------------
# Group join
# ----------------------------------------------------------------

async def approve_group_join(
    conn: asyncpg.Connection,
    ctx: AuthContext,
    *,
    request_id: GroupRequestId,
) -> gr_repo.GroupRequestRow:
    require_parent(ctx)
    assert ctx.parent_account_id is not None

    async with conn.transaction():
        req = await gr_repo.get(conn, request_id)
        if req is None:
            raise NotFoundError("Group request not found")
        if req.type != GroupRequestType.JOIN_GROUP:
            raise StateConflictError("Wrong request type for this endpoint")
        if req.status != GroupRequestStatus.PENDING_PARENT:
            raise StateConflictError(f"Already reviewed (status={req.status.value})")
        if req.group_id is None:
            raise StateConflictError("join_group request missing group_id")

        await require_parent_can_review_child(
            conn, ctx, child_user_id=req.actor_child_id
        )

        await _guard_cap_at_approval(conn, req.group_id)

        await groups_repo.set_membership_status(
            conn,
            group_id=req.group_id,
            child_user_id=req.actor_child_id,
            new_status=GroupMembershipStatus.ACTIVE,
            expect_current=GroupMembershipStatus.PENDING,
        )

        updated = await gr_repo.mark_reviewed(
            conn,
            request_id=request_id,
            new_status=GroupRequestStatus.APPROVED,
            reviewed_by=ctx.parent_account_id,
        )
        if updated is None:
            raise StateConflictError("Request state changed during review")

        await write_audit(
            conn,
            event_type=Events.GROUP_JOIN_APPROVED,
            actor_parent_account_id=ctx.parent_account_id,
            target_type="group_request",
            target_id=request_id,
            payload={
                "group_id": str(req.group_id),
                "actor_child_id": str(req.actor_child_id),
            },
        )
        count_approval("group_join", "approve")
        return updated


async def decline_group_join(
    conn: asyncpg.Connection,
    ctx: AuthContext,
    *,
    request_id: GroupRequestId,
) -> gr_repo.GroupRequestRow:
    require_parent(ctx)
    assert ctx.parent_account_id is not None

    async with conn.transaction():
        req = await gr_repo.get(conn, request_id)
        if req is None:
            raise NotFoundError("Group request not found")
        if req.type != GroupRequestType.JOIN_GROUP:
            raise StateConflictError("Wrong request type for this endpoint")
        if req.status != GroupRequestStatus.PENDING_PARENT:
            raise StateConflictError(f"Already reviewed (status={req.status.value})")
        if req.group_id is None:
            raise StateConflictError("join_group request missing group_id")

        await require_parent_can_review_child(
            conn, ctx, child_user_id=req.actor_child_id
        )

        await groups_repo.set_membership_status(
            conn,
            group_id=req.group_id,
            child_user_id=req.actor_child_id,
            new_status=GroupMembershipStatus.DECLINED,
            expect_current=GroupMembershipStatus.PENDING,
        )

        updated = await gr_repo.mark_reviewed(
            conn,
            request_id=request_id,
            new_status=GroupRequestStatus.DECLINED,
            reviewed_by=ctx.parent_account_id,
        )
        if updated is None:
            raise StateConflictError("Request state changed during review")

        await write_audit(
            conn,
            event_type=Events.GROUP_JOIN_DECLINED,
            actor_parent_account_id=ctx.parent_account_id,
            target_type="group_request",
            target_id=request_id,
        )
        count_approval("group_join", "decline")
        return updated


# ----------------------------------------------------------------
# Group invite
# ----------------------------------------------------------------

async def approve_group_invite(
    conn: asyncpg.Connection,
    ctx: AuthContext,
    *,
    request_id: GroupRequestId,
) -> gr_repo.GroupRequestRow:
    require_parent(ctx)
    assert ctx.parent_account_id is not None

    async with conn.transaction():
        req = await gr_repo.get(conn, request_id)
        if req is None:
            raise NotFoundError("Group request not found")
        if req.type != GroupRequestType.INVITE_TO_GROUP:
            raise StateConflictError("Wrong request type for this endpoint")
        if req.status != GroupRequestStatus.PENDING_PARENT:
            raise StateConflictError(f"Already reviewed (status={req.status.value})")
        if req.group_id is None or req.target_child_id is None:
            raise StateConflictError("invite_to_group request missing group_id/target")

        # The target child's parent is the reviewer here.
        await require_parent_can_review_child(
            conn, ctx, child_user_id=req.target_child_id
        )

        await _guard_cap_at_approval(conn, req.group_id)

        await groups_repo.set_membership_status(
            conn,
            group_id=req.group_id,
            child_user_id=req.target_child_id,
            new_status=GroupMembershipStatus.ACTIVE,
            expect_current=GroupMembershipStatus.PENDING,
        )

        updated = await gr_repo.mark_reviewed(
            conn,
            request_id=request_id,
            new_status=GroupRequestStatus.APPROVED,
            reviewed_by=ctx.parent_account_id,
        )
        if updated is None:
            raise StateConflictError("Request state changed during review")

        await write_audit(
            conn,
            event_type=Events.GROUP_INVITE_APPROVED,
            actor_parent_account_id=ctx.parent_account_id,
            target_type="group_request",
            target_id=request_id,
            payload={
                "group_id": str(req.group_id),
                "target_child_id": str(req.target_child_id),
            },
        )
        count_approval("group_invite", "approve")
        return updated


async def decline_group_invite(
    conn: asyncpg.Connection,
    ctx: AuthContext,
    *,
    request_id: GroupRequestId,
) -> gr_repo.GroupRequestRow:
    require_parent(ctx)
    assert ctx.parent_account_id is not None

    async with conn.transaction():
        req = await gr_repo.get(conn, request_id)
        if req is None:
            raise NotFoundError("Group request not found")
        if req.type != GroupRequestType.INVITE_TO_GROUP:
            raise StateConflictError("Wrong request type for this endpoint")
        if req.status != GroupRequestStatus.PENDING_PARENT:
            raise StateConflictError(f"Already reviewed (status={req.status.value})")
        if req.group_id is None or req.target_child_id is None:
            raise StateConflictError("invite_to_group request missing group_id/target")

        await require_parent_can_review_child(
            conn, ctx, child_user_id=req.target_child_id
        )

        await groups_repo.set_membership_status(
            conn,
            group_id=req.group_id,
            child_user_id=req.target_child_id,
            new_status=GroupMembershipStatus.DECLINED,
            expect_current=GroupMembershipStatus.PENDING,
        )

        updated = await gr_repo.mark_reviewed(
            conn,
            request_id=request_id,
            new_status=GroupRequestStatus.DECLINED,
            reviewed_by=ctx.parent_account_id,
        )
        if updated is None:
            raise StateConflictError("Request state changed during review")

        await write_audit(
            conn,
            event_type=Events.GROUP_INVITE_DECLINED,
            actor_parent_account_id=ctx.parent_account_id,
            target_type="group_request",
            target_id=request_id,
        )
        count_approval("group_invite", "decline")
        return updated
