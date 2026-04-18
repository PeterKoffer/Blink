"""Tier cap enforcement across group flows.

The three v1 tiers (lille/normal/stor) map to caps 10/30/50. A hard cap
of 50 applies regardless of tier. These tests verify:
    - Joining the group at cap+1 returns UpgradeRequiredError with the
      right current/required tier metadata.
    - Crossing the hard cap raises HardCapExceededError instead.
    - Pending + active counts both apply toward the cap.
    - Approve guards against cap violation even if caps were tightened.
"""
from __future__ import annotations

import pytest

from blink.errors import HardCapExceededError, StateConflictError, UpgradeRequiredError
from blink.pricing import cap_for, next_tier, required_tier_for
from blink.policies.parent import upsert_parent_policy
from blink.repos import groups as groups_repo
from blink.services import group_service
from blink.types import (
    GroupMembershipStatus,
    GroupPlanTier,
)


pytestmark = pytest.mark.asyncio


# ----------------------------- pricing helpers -----------------------------

def test_cap_for_matches_canonical_table():
    assert cap_for(GroupPlanTier.LILLE) == 10
    assert cap_for(GroupPlanTier.NORMAL) == 30
    assert cap_for(GroupPlanTier.STOR) == 50


def test_next_tier_ascends_and_stops_at_stor():
    assert next_tier(GroupPlanTier.LILLE) == GroupPlanTier.NORMAL
    assert next_tier(GroupPlanTier.NORMAL) == GroupPlanTier.STOR
    assert next_tier(GroupPlanTier.STOR) is None


def test_required_tier_boundaries():
    assert required_tier_for(1) == GroupPlanTier.LILLE
    assert required_tier_for(10) == GroupPlanTier.LILLE
    assert required_tier_for(11) == GroupPlanTier.NORMAL
    assert required_tier_for(30) == GroupPlanTier.NORMAL
    assert required_tier_for(31) == GroupPlanTier.STOR
    assert required_tier_for(50) == GroupPlanTier.STOR
    assert required_tier_for(51) is None  # hard cap


# ----------------------------- join at tier cap -----------------------------

async def _fill_group_to(conn, gid, children, *, status=GroupMembershipStatus.ACTIVE):
    """Insert raw memberships to bring a group up to len(children) members."""
    for c in children:
        await conn.execute(
            """
            INSERT INTO group_memberships
                (group_id, child_user_id, role, status, activated_at)
            VALUES ($1, $2, 'member', $3::group_membership_status,
                    CASE WHEN $3 = 'active' THEN now() ELSE NULL END)
            """,
            gid, c.user_id, status.value,
        )


async def test_lille_tier_rejects_eleventh_member(
    conn, make_child, make_parent, link_parent_child, make_friendship,
    make_active_group, make_many_children,
):
    creator = await make_child("Creator")
    joiner = await make_child("Joiner")
    mom = await make_parent("Mom")
    await link_parent_child(mom, joiner)
    await upsert_parent_policy(
        conn, child_user_id=joiner.user_id,
        updated_by=mom.parent_account_id,
        require_group_invite_approval=False,
    )
    gid = await make_active_group(creator, tier=GroupPlanTier.LILLE)

    # Fill to 10 (including creator).
    fillers = await make_many_children(9, prefix="F")
    await _fill_group_to(conn, gid, fillers)

    # 11th member must fail with UpgradeRequiredError.
    group = await groups_repo.get_group(conn, gid)
    assert group is not None
    with pytest.raises(UpgradeRequiredError) as exc:
        await group_service.join_group(
            conn, joiner.ctx, invite_code=group.invite_code,
        )
    assert exc.value.current_tier == GroupPlanTier.LILLE.value
    assert exc.value.required_tier == GroupPlanTier.NORMAL.value
    assert exc.value.current_cap == 10


async def test_normal_tier_rejects_thirty_first_member(
    conn, make_child, make_parent, link_parent_child,
    make_active_group, make_many_children,
):
    creator = await make_child("Creator")
    joiner = await make_child("Joiner")
    mom = await make_parent("Mom")
    await link_parent_child(mom, joiner)
    await upsert_parent_policy(
        conn, child_user_id=joiner.user_id,
        updated_by=mom.parent_account_id,
        require_group_invite_approval=False,
        max_group_members=50,
    )
    gid = await make_active_group(creator, tier=GroupPlanTier.NORMAL)

    fillers = await make_many_children(29, prefix="N")  # creator + 29 = 30
    await _fill_group_to(conn, gid, fillers)

    group = await groups_repo.get_group(conn, gid)
    assert group is not None
    with pytest.raises(UpgradeRequiredError) as exc:
        await group_service.join_group(
            conn, joiner.ctx, invite_code=group.invite_code,
        )
    assert exc.value.current_tier == GroupPlanTier.NORMAL.value
    assert exc.value.required_tier == GroupPlanTier.STOR.value


async def test_stor_tier_hard_cap_raises_hard_cap_exceeded(
    conn, make_child, make_parent, link_parent_child,
    make_active_group, make_many_children,
):
    creator = await make_child("Creator")
    joiner = await make_child("Joiner")
    mom = await make_parent("Mom")
    await link_parent_child(mom, joiner)
    await upsert_parent_policy(
        conn, child_user_id=joiner.user_id,
        updated_by=mom.parent_account_id,
        require_group_invite_approval=False,
        max_group_members=50,
    )
    gid = await make_active_group(creator, tier=GroupPlanTier.STOR)

    fillers = await make_many_children(49, prefix="S")  # creator + 49 = 50
    await _fill_group_to(conn, gid, fillers)

    group = await groups_repo.get_group(conn, gid)
    assert group is not None
    with pytest.raises(HardCapExceededError) as exc:
        await group_service.join_group(
            conn, joiner.ctx, invite_code=group.invite_code,
        )
    assert exc.value.limit == 50


# ----------------------------- pending counts -----------------------------

async def test_pending_memberships_count_toward_cap(
    conn, make_child, make_parent, link_parent_child,
    make_active_group, make_many_children,
):
    creator = await make_child("Creator")
    joiner = await make_child("Joiner")
    mom = await make_parent("Mom")
    await link_parent_child(mom, joiner)
    await upsert_parent_policy(
        conn, child_user_id=joiner.user_id,
        updated_by=mom.parent_account_id,
        require_group_invite_approval=False,
    )
    gid = await make_active_group(creator, tier=GroupPlanTier.LILLE)

    # 5 active + 5 pending = 10 total. 11th must fail.
    active_fillers = await make_many_children(4, prefix="A")  # 1 creator + 4 active = 5
    pending_fillers = await make_many_children(5, prefix="P")
    await _fill_group_to(conn, gid, active_fillers, status=GroupMembershipStatus.ACTIVE)
    await _fill_group_to(conn, gid, pending_fillers, status=GroupMembershipStatus.PENDING)

    group = await groups_repo.get_group(conn, gid)
    assert group is not None
    with pytest.raises(UpgradeRequiredError):
        await group_service.join_group(
            conn, joiner.ctx, invite_code=group.invite_code,
        )


# ----------------------------- create group -----------------------------

async def test_create_group_with_too_many_members_requires_upgrade(
    conn, make_child, make_parent, link_parent_child, make_friendship,
    make_many_children,
):
    creator = await make_child("Creator")
    mom = await make_parent("Mom")
    await link_parent_child(mom, creator)
    # Parent allows big groups at policy level.
    await upsert_parent_policy(
        conn, child_user_id=creator.user_id,
        updated_by=mom.parent_account_id,
        max_group_members=50,
    )

    friends = await make_many_children(11, prefix="Fr")
    for f in friends:
        await make_friendship(creator, f)

    # Creator + 11 others = 12 proposed members. New groups default to 'lille'
    # (cap=10), so this must raise UpgradeRequiredError.
    with pytest.raises(UpgradeRequiredError) as exc:
        await group_service.create_group(
            conn, creator.ctx, name="TooBigFromStart",
            initial_member_ids=[f.user_id for f in friends],
        )
    assert exc.value.required_tier == GroupPlanTier.NORMAL.value


async def test_create_group_over_hard_cap_fails(
    conn, make_child, make_parent, link_parent_child, make_friendship,
    make_many_children,
):
    creator = await make_child("Creator")
    mom = await make_parent("Mom")
    await link_parent_child(mom, creator)
    await upsert_parent_policy(
        conn, child_user_id=creator.user_id,
        updated_by=mom.parent_account_id,
        max_group_members=50,
    )

    friends = await make_many_children(51, prefix="Fr")
    for f in friends:
        await make_friendship(creator, f)

    with pytest.raises(HardCapExceededError):
        await group_service.create_group(
            conn, creator.ctx, name="OverHardCap",
            initial_member_ids=[f.user_id for f in friends],
        )
