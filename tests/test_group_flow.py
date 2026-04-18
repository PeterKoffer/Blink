"""Group create / join / invite flow."""
from __future__ import annotations

import pytest

from blink.errors import PolicyBlockedError, StateConflictError
from blink.policies.parent import upsert_parent_policy
from blink.services import group_service
from blink.types import GroupMembershipStatus, GroupStatus


pytestmark = pytest.mark.asyncio


# ---------------- create ----------------

async def test_create_group_pending_when_approval_required(
    conn, make_child, make_parent, link_parent_child, make_friendship,
):
    alice = await make_child("Alice")
    bob = await make_child("Bob")
    mom = await make_parent("Mom")
    await link_parent_child(mom, alice)
    await make_friendship(alice, bob)

    # Default policy: require_group_approval = true.
    group, memberships, request = await group_service.create_group(
        conn, alice.ctx, name="Parken", initial_member_ids=[bob.user_id],
    )
    assert group.status == GroupStatus.PENDING_PARENT
    assert request is not None
    assert all(m.status == GroupMembershipStatus.PENDING for m in memberships)


async def test_create_group_active_when_approval_not_required(
    conn, make_child, make_parent, link_parent_child, make_friendship,
):
    alice = await make_child("Alice")
    bob = await make_child("Bob")
    mom = await make_parent("Mom")
    await link_parent_child(mom, alice)
    await make_friendship(alice, bob)

    await upsert_parent_policy(
        conn,
        child_user_id=alice.user_id,
        updated_by=mom.parent_account_id,
        require_group_approval=False,
    )

    group, memberships, request = await group_service.create_group(
        conn, alice.ctx, name="Parken", initial_member_ids=[bob.user_id],
    )
    assert group.status == GroupStatus.ACTIVE
    assert request is None
    assert all(m.status == GroupMembershipStatus.ACTIVE for m in memberships)


async def test_create_group_rejects_non_friends(
    conn, make_child, make_parent, link_parent_child,
):
    alice = await make_child("Alice")
    stranger = await make_child("Stranger")
    mom = await make_parent("Mom")
    await link_parent_child(mom, alice)

    with pytest.raises(StateConflictError):
        await group_service.create_group(
            conn, alice.ctx,
            name="Stranger danger",
            initial_member_ids=[stranger.user_id],
        )


async def test_create_group_blocked_by_max_members_policy(
    conn, make_child, make_parent, link_parent_child, make_friendship,
):
    alice = await make_child("Alice")
    b = await make_child("B")
    c = await make_child("C")
    mom = await make_parent("Mom")
    await link_parent_child(mom, alice)
    await make_friendship(alice, b)
    await make_friendship(alice, c)

    await upsert_parent_policy(
        conn,
        child_user_id=alice.user_id,
        updated_by=mom.parent_account_id,
        max_group_members=2,  # creator + 1 other = 2 is fine; creator + 2 others = 3 is not
    )

    with pytest.raises(PolicyBlockedError):
        await group_service.create_group(
            conn, alice.ctx, name="Too big",
            initial_member_ids=[b.user_id, c.user_id],
        )


async def test_create_group_blocked_when_policy_disallows(
    conn, make_child, make_parent, link_parent_child,
):
    alice = await make_child("Alice")
    mom = await make_parent("Mom")
    await link_parent_child(mom, alice)

    await upsert_parent_policy(
        conn,
        child_user_id=alice.user_id,
        updated_by=mom.parent_account_id,
        may_create_groups=False,
    )

    with pytest.raises(PolicyBlockedError):
        await group_service.create_group(
            conn, alice.ctx, name="Nope", initial_member_ids=[],
        )


# ---------------- join ----------------

async def test_join_request_created_when_approval_required(
    conn, make_child, make_parent, link_parent_child, make_friendship,
):
    alice = await make_child("Alice")
    bob = await make_child("Bob")       # group creator
    carol = await make_child("Carol")   # will join
    mom_bob = await make_parent("MomBob")
    mom_carol = await make_parent("MomCarol")
    await link_parent_child(mom_bob, bob)
    await link_parent_child(mom_carol, carol)
    await make_friendship(bob, alice)

    await upsert_parent_policy(
        conn, child_user_id=bob.user_id,
        updated_by=mom_bob.parent_account_id, require_group_approval=False,
    )
    group, _m, _r = await group_service.create_group(
        conn, bob.ctx, name="Parken", initial_member_ids=[alice.user_id],
    )

    # Carol joins via invite code — Carol's parent policy controls approval.
    g2, membership, request = await group_service.join_group(
        conn, carol.ctx, invite_code=group.invite_code,
    )
    assert g2.id == group.id
    assert membership.status == GroupMembershipStatus.PENDING
    assert request is not None


async def test_cannot_join_same_group_twice(
    conn, make_child, make_parent, link_parent_child, make_friendship,
):
    alice = await make_child("Alice")
    bob = await make_child("Bob")
    mom_alice = await make_parent("MomA")
    mom_bob = await make_parent("MomB")
    await link_parent_child(mom_alice, alice)
    await link_parent_child(mom_bob, bob)
    await make_friendship(alice, bob)

    await upsert_parent_policy(
        conn, child_user_id=alice.user_id,
        updated_by=mom_alice.parent_account_id, require_group_approval=False,
    )
    group, _m, _r = await group_service.create_group(
        conn, alice.ctx, name="Parken", initial_member_ids=[],
    )

    await group_service.join_group(conn, bob.ctx, invite_code=group.invite_code)
    with pytest.raises(StateConflictError):
        await group_service.join_group(
            conn, bob.ctx, invite_code=group.invite_code,
        )


# ---------------- invite ----------------

async def test_invite_requires_inviter_to_be_member(
    conn, make_child, make_parent, link_parent_child, make_friendship,
):
    from blink.errors import AuthzError

    alice = await make_child("Alice")
    bob = await make_child("Bob")
    carol = await make_child("Carol")
    mom_alice = await make_parent("MomA")
    await link_parent_child(mom_alice, alice)
    await make_friendship(alice, bob)
    await make_friendship(alice, carol)

    await upsert_parent_policy(
        conn, child_user_id=alice.user_id,
        updated_by=mom_alice.parent_account_id, require_group_approval=False,
    )
    group, _m, _r = await group_service.create_group(
        conn, alice.ctx, name="Parken", initial_member_ids=[],
    )

    # Bob is not a member; cannot invite Carol.
    with pytest.raises(AuthzError):
        await group_service.invite_to_group(
            conn, bob.ctx, group_id=group.id, target_child_id=carol.user_id,
        )


async def test_invite_requires_friendship_with_target(
    conn, make_child, make_parent, link_parent_child,
):
    alice = await make_child("Alice")
    stranger = await make_child("Stranger")
    mom_alice = await make_parent("MomA")
    await link_parent_child(mom_alice, alice)

    await upsert_parent_policy(
        conn, child_user_id=alice.user_id,
        updated_by=mom_alice.parent_account_id, require_group_approval=False,
    )
    group, _m, _r = await group_service.create_group(
        conn, alice.ctx, name="Parken", initial_member_ids=[],
    )

    with pytest.raises(StateConflictError):
        await group_service.invite_to_group(
            conn, alice.ctx, group_id=group.id, target_child_id=stranger.user_id,
        )
