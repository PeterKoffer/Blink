"""Group lifecycle business logic.

Pending state policy:
- If parent policy.require_group_approval = True:
    group.status = pending_parent
    memberships created as status = pending
    a group_requests row (type=create_group) is written
- If False:
    group.status = active
    memberships created as status = active
    no group_requests row

Pending memberships count toward the max_group_members cap along with active ones.
"""
from __future__ import annotations

import asyncpg

from blink.audit import Events, write_audit
from blink.auth.context import AuthContext
from blink.authz.require import require_child, require_group_member
from blink.errors import (
    HardCapExceededError,
    NotFoundError,
    StateConflictError,
    UpgradeRequiredError,
)
from blink.ids import generate_invite_code
from blink.obs.metrics import count_hard_cap_exceeded, count_upgrade_required
from blink.policies.parent import resolve_parent_policy
from blink.pricing import cap_for, required_tier_for
from blink.repos import friends as friends_repo
from blink.repos import group_requests as gr_repo
from blink.repos import groups as groups_repo
from blink.repos import users as users_repo
from blink.types import (
    GroupId,
    GroupMemberRole,
    GroupMembershipStatus,
    GroupPlanTier,
    GroupStatus,
    HARD_MAX_GROUP_MEMBERS,
    UserId,
)


def _enforce_tier_and_hard_cap(
    *,
    current_tier: GroupPlanTier,
    proposed_total: int,
) -> None:
    """Central cap enforcement. Called by every flow that grows a group.

    Raises HardCapExceededError if proposed_total > 50.
    Raises UpgradeRequiredError if proposed_total > current tier's cap.
    """
    if proposed_total > HARD_MAX_GROUP_MEMBERS:
        count_hard_cap_exceeded()
        raise HardCapExceededError(limit=HARD_MAX_GROUP_MEMBERS)

    current_cap = cap_for(current_tier)
    if proposed_total > current_cap:
        required = required_tier_for(proposed_total)
        assert required is not None  # guarded by the hard-cap branch above
        count_upgrade_required()
        raise UpgradeRequiredError(
            current_tier=current_tier.value,
            required_tier=required.value,
            current_member_count=proposed_total - 1,  # before the new member
            current_cap=current_cap,
        )


_INVITE_CODE_RETRIES = 5


async def _insert_group_with_unique_code(
    conn: asyncpg.Connection,
    *,
    name: str,
    created_by: UserId,
    status: GroupStatus,
) -> groups_repo.GroupRow:
    """Retry on the rare invite_code collision (UNIQUE constraint)."""
    last_err: Exception | None = None
    for _ in range(_INVITE_CODE_RETRIES):
        code = generate_invite_code()
        try:
            return await groups_repo.insert_group(
                conn, name=name, created_by=created_by, status=status, invite_code=code,
            )
        except asyncpg.UniqueViolationError as e:
            last_err = e
            continue
    raise RuntimeError("Could not allocate unique invite_code") from last_err


async def create_group(
    conn: asyncpg.Connection,
    ctx: AuthContext,
    *,
    name: str,
    initial_member_ids: list[UserId],
) -> tuple[groups_repo.GroupRow, list[groups_repo.MembershipRow], gr_repo.GroupRequestRow | None]:
    require_child(ctx)

    # De-dup, excluding creator.
    unique_members: list[UserId] = []
    seen: set[UserId] = set()
    for m in initial_member_ids:
        if m == ctx.user_id:
            continue
        if m in seen:
            continue
        seen.add(m)
        unique_members.append(m)

    async with conn.transaction():
        policy = await resolve_parent_policy(conn, ctx.user_id)
        policy.ensure_can_create_groups()

        # Every initial member must be an active friend of the creator.
        for m in unique_members:
            friendship = await friends_repo.get_active_friendship(conn, ctx.user_id, m)
            if friendship is None:
                raise StateConflictError(
                    f"Cannot add non-friend {m} to a new group"
                )

        # Verify the listed member ids are existing, active children.
        users = await users_repo.get_many(conn, unique_members)
        if len(users) != len(unique_members):
            raise NotFoundError("One or more initial members do not exist")

        proposed_count = 1 + len(unique_members)  # creator + others
        # New groups start at the 'lille' tier (default on groups.member_cap_tier).
        # Parent must activate/upgrade billing separately to grow past 10.
        _enforce_tier_and_hard_cap(
            current_tier=GroupPlanTier.LILLE,
            proposed_total=proposed_count,
        )
        policy.ensure_group_size_ok(proposed_count)

        needs_approval = policy.require_group_approval
        group_status = GroupStatus.PENDING_PARENT if needs_approval else GroupStatus.ACTIVE
        member_status = (
            GroupMembershipStatus.PENDING if needs_approval else GroupMembershipStatus.ACTIVE
        )

        group = await _insert_group_with_unique_code(
            conn, name=name, created_by=ctx.user_id, status=group_status,
        )

        # Creator first, as CREATOR.
        memberships: list[groups_repo.MembershipRow] = [
            await groups_repo.insert_membership(
                conn,
                group_id=group.id,
                child_user_id=ctx.user_id,
                role=GroupMemberRole.CREATOR,
                status=member_status,
            )
        ]
        for m in unique_members:
            memberships.append(
                await groups_repo.insert_membership(
                    conn,
                    group_id=group.id,
                    child_user_id=m,
                    role=GroupMemberRole.MEMBER,
                    status=member_status,
                )
            )

        request: gr_repo.GroupRequestRow | None = None
        if needs_approval:
            request = await gr_repo.insert_create_group(
                conn, actor=ctx.user_id, group_id=group.id, requested_name=name,
            )
            await write_audit(
                conn,
                event_type=Events.GROUP_CREATE_REQUESTED,
                actor_user_id=ctx.user_id,
                target_type="group_request",
                target_id=request.id,
                payload={"group_id": str(group.id), "member_count": proposed_count},
            )
        else:
            await write_audit(
                conn,
                event_type=Events.GROUP_CREATED,
                actor_user_id=ctx.user_id,
                target_type="group",
                target_id=group.id,
                payload={"member_count": proposed_count},
            )

        return group, memberships, request


async def join_group(
    conn: asyncpg.Connection,
    ctx: AuthContext,
    *,
    invite_code: str,
) -> tuple[groups_repo.GroupRow, groups_repo.MembershipRow, gr_repo.GroupRequestRow | None]:
    require_child(ctx)

    async with conn.transaction():
        policy = await resolve_parent_policy(conn, ctx.user_id)
        policy.ensure_can_join_groups()

        group = await groups_repo.get_group_by_invite_code(conn, invite_code)
        if group is None:
            raise NotFoundError("Group not found")
        if group.status != GroupStatus.ACTIVE:
            raise StateConflictError("Group is not joinable")

        existing = await groups_repo.get_membership(conn, group.id, ctx.user_id)
        if existing and existing.status in (GroupMembershipStatus.ACTIVE, GroupMembershipStatus.PENDING):
            raise StateConflictError(
                f"Already {existing.status.value} in this group"
            )

        active, pending = await groups_repo.count_members(conn, group.id)
        proposed_total = active + pending + 1
        _enforce_tier_and_hard_cap(
            current_tier=group.member_cap_tier,
            proposed_total=proposed_total,
        )
        policy.ensure_group_size_ok(proposed_total)

        needs_approval = policy.require_group_invite_approval
        member_status = (
            GroupMembershipStatus.PENDING if needs_approval else GroupMembershipStatus.ACTIVE
        )

        membership = await groups_repo.insert_membership(
            conn,
            group_id=group.id,
            child_user_id=ctx.user_id,
            role=GroupMemberRole.MEMBER,
            status=member_status,
        )

        request: gr_repo.GroupRequestRow | None = None
        if needs_approval:
            request = await gr_repo.insert_join_group(
                conn, actor=ctx.user_id, group_id=group.id,
            )
            await write_audit(
                conn,
                event_type=Events.GROUP_JOIN_REQUESTED,
                actor_user_id=ctx.user_id,
                target_type="group_request",
                target_id=request.id,
                payload={"group_id": str(group.id)},
            )
        else:
            await write_audit(
                conn,
                event_type=Events.GROUP_MEMBERSHIP_ACTIVATED,
                actor_user_id=ctx.user_id,
                target_type="group_membership",
                target_id=membership.id,
                payload={"group_id": str(group.id), "via": "join"},
            )

        return group, membership, request


async def invite_to_group(
    conn: asyncpg.Connection,
    ctx: AuthContext,
    *,
    group_id: GroupId,
    target_child_id: UserId,
) -> tuple[groups_repo.MembershipRow, gr_repo.GroupRequestRow | None]:
    require_child(ctx)

    if ctx.user_id == target_child_id:
        raise StateConflictError("Cannot invite yourself")

    async with conn.transaction():
        # Inviter must be an active member.
        await require_group_member(conn, group_id=group_id, child_user_id=ctx.user_id)

        group = await groups_repo.get_group(conn, group_id)
        if group is None or group.status != GroupStatus.ACTIVE:
            raise StateConflictError("Group is not active")

        # Target must be an active friend of the inviter.
        friendship = await friends_repo.get_active_friendship(
            conn, ctx.user_id, target_child_id
        )
        if friendship is None:
            raise StateConflictError("Target is not an active friend")

        target_user = await users_repo.get_by_id(conn, target_child_id)
        if target_user is None:
            raise NotFoundError("Target user not found")

        existing = await groups_repo.get_membership(conn, group_id, target_child_id)
        if existing and existing.status in (GroupMembershipStatus.ACTIVE, GroupMembershipStatus.PENDING):
            raise StateConflictError(
                f"Target is already {existing.status.value} in this group"
            )

        # Target's parent policy governs approval. Cap is a group-level rule.
        target_policy = await resolve_parent_policy(conn, target_child_id)
        active, pending = await groups_repo.count_members(conn, group_id)
        proposed_total = active + pending + 1
        _enforce_tier_and_hard_cap(
            current_tier=group.member_cap_tier,
            proposed_total=proposed_total,
        )
        target_policy.ensure_group_size_ok(proposed_total)

        needs_approval = target_policy.require_group_invite_approval
        member_status = (
            GroupMembershipStatus.PENDING if needs_approval else GroupMembershipStatus.ACTIVE
        )

        membership = await groups_repo.insert_membership(
            conn,
            group_id=group_id,
            child_user_id=target_child_id,
            role=GroupMemberRole.MEMBER,
            status=member_status,
        )

        request: gr_repo.GroupRequestRow | None = None
        if needs_approval:
            request = await gr_repo.insert_invite_to_group(
                conn, actor=ctx.user_id, group_id=group_id, target=target_child_id,
            )
            await write_audit(
                conn,
                event_type=Events.GROUP_INVITE_REQUESTED,
                actor_user_id=ctx.user_id,
                target_type="group_request",
                target_id=request.id,
                payload={
                    "group_id": str(group_id),
                    "target_child_id": str(target_child_id),
                },
            )
        else:
            await write_audit(
                conn,
                event_type=Events.GROUP_MEMBERSHIP_ACTIVATED,
                actor_user_id=ctx.user_id,
                target_type="group_membership",
                target_id=membership.id,
                payload={
                    "group_id": str(group_id),
                    "target_child_id": str(target_child_id),
                    "via": "invite",
                },
            )

        return membership, request


async def list_groups_for_child(
    conn: asyncpg.Connection,
    ctx: AuthContext,
) -> list[tuple[groups_repo.GroupRow, GroupMembershipStatus]]:
    require_child(ctx)
    return await groups_repo.list_groups_for_child(conn, ctx.user_id)
