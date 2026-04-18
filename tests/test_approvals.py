"""Parent approvals hub — create/join/invite approve/decline."""
from __future__ import annotations

import pytest

from blink.errors import AuthzError, StateConflictError
from blink.policies.parent import upsert_parent_policy
from blink.repos import group_requests as gr_repo
from blink.repos import groups as groups_repo
from blink.services import approval_service, group_service
from blink.types import (
    GroupMembershipStatus,
    GroupRequestStatus,
    GroupStatus,
)


pytestmark = pytest.mark.asyncio


async def test_approve_group_create_activates_group_and_memberships(
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
    assert request is not None
    assert group.status == GroupStatus.PENDING_PARENT

    updated = await approval_service.approve_group_create(
        conn, mom.ctx, request_id=request.id,
    )
    assert updated.status == GroupRequestStatus.APPROVED

    # Group is now ACTIVE, memberships flipped to ACTIVE.
    fresh_group = await groups_repo.get_group(conn, group.id)
    assert fresh_group is not None
    assert fresh_group.status == GroupStatus.ACTIVE

    for m in memberships:
        current = await groups_repo.get_membership(conn, group.id, m.child_user_id)
        assert current is not None
        assert current.status == GroupMembershipStatus.ACTIVE


async def test_decline_group_create_deletes_group_and_declines_memberships(
    conn, make_child, make_parent, link_parent_child, make_friendship,
):
    alice = await make_child("Alice")
    bob = await make_child("Bob")
    mom = await make_parent("Mom")
    await link_parent_child(mom, alice)
    await make_friendship(alice, bob)

    group, memberships, request = await group_service.create_group(
        conn, alice.ctx, name="Parken", initial_member_ids=[bob.user_id],
    )
    assert request is not None

    updated = await approval_service.decline_group_create(
        conn, mom.ctx, request_id=request.id,
    )
    assert updated.status == GroupRequestStatus.DECLINED

    fresh = await groups_repo.get_group(conn, group.id)
    assert fresh is not None
    assert fresh.status == GroupStatus.DELETED

    for m in memberships:
        current = await groups_repo.get_membership(conn, group.id, m.child_user_id)
        assert current is not None
        assert current.status == GroupMembershipStatus.DECLINED


async def test_cannot_approve_twice(
    conn, make_child, make_parent, link_parent_child, make_friendship,
):
    alice = await make_child("Alice")
    bob = await make_child("Bob")
    mom = await make_parent("Mom")
    await link_parent_child(mom, alice)
    await make_friendship(alice, bob)

    _group, _m, request = await group_service.create_group(
        conn, alice.ctx, name="Parken", initial_member_ids=[bob.user_id],
    )
    assert request is not None

    await approval_service.approve_group_create(conn, mom.ctx, request_id=request.id)
    with pytest.raises(StateConflictError):
        await approval_service.approve_group_create(conn, mom.ctx, request_id=request.id)


async def test_unlinked_parent_cannot_approve_group_create(
    conn, make_child, make_parent, link_parent_child, make_friendship,
):
    alice = await make_child("Alice")
    bob = await make_child("Bob")
    real_mom = await make_parent("RealMom")
    stranger = await make_parent("Stranger")
    await link_parent_child(real_mom, alice)
    await make_friendship(alice, bob)

    _g, _m, request = await group_service.create_group(
        conn, alice.ctx, name="Parken", initial_member_ids=[bob.user_id],
    )
    assert request is not None

    with pytest.raises(AuthzError):
        await approval_service.approve_group_create(
            conn, stranger.ctx, request_id=request.id,
        )


async def test_approve_group_invite_activates_target_membership(
    conn, make_child, make_parent, link_parent_child, make_friendship,
):
    alice = await make_child("Alice")
    bob = await make_child("Bob")
    carol = await make_child("Carol")
    mom_alice = await make_parent("MomA")
    mom_carol = await make_parent("MomC")
    await link_parent_child(mom_alice, alice)
    await link_parent_child(mom_carol, carol)
    await make_friendship(alice, bob)
    await make_friendship(alice, carol)

    # Alice creates an ACTIVE group (skip approval on her side).
    await upsert_parent_policy(
        conn, child_user_id=alice.user_id,
        updated_by=mom_alice.parent_account_id, require_group_approval=False,
    )
    group, _m, _r = await group_service.create_group(
        conn, alice.ctx, name="Parken", initial_member_ids=[bob.user_id],
    )

    # Alice invites Carol; Carol's parent policy requires approval (default).
    _membership, invite_req = await group_service.invite_to_group(
        conn, alice.ctx, group_id=group.id, target_child_id=carol.user_id,
    )
    assert invite_req is not None

    # Carol's parent approves.
    updated = await approval_service.approve_group_invite(
        conn, mom_carol.ctx, request_id=invite_req.id,
    )
    assert updated.status == GroupRequestStatus.APPROVED

    current = await groups_repo.get_membership(conn, group.id, carol.user_id)
    assert current is not None
    assert current.status == GroupMembershipStatus.ACTIVE


async def test_pending_hub_lists_only_this_parents_requests(
    conn, make_child, make_parent, link_parent_child, make_friendship,
):
    alice = await make_child("Alice")
    bob = await make_child("Bob")
    mom_alice = await make_parent("MomA")
    mom_bob = await make_parent("MomB")
    await link_parent_child(mom_alice, alice)
    await link_parent_child(mom_bob, bob)
    await make_friendship(alice, bob)

    _g, _m, alice_req = await group_service.create_group(
        conn, alice.ctx, name="AliceGroup", initial_member_ids=[],
    )
    _g2, _m2, bob_req = await group_service.create_group(
        conn, bob.ctx, name="BobGroup", initial_member_ids=[],
    )
    assert alice_req is not None and bob_req is not None

    alice_pending = await gr_repo.list_pending_for_parent(
        conn, mom_alice.parent_account_id,
    )
    alice_ids = {r.id for r in alice_pending}
    assert alice_req.id in alice_ids
    assert bob_req.id not in alice_ids
