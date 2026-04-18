"""Authorization guards — the deny-by-default layer must actually deny."""
from __future__ import annotations

import pytest

from blink.authz.require import (
    require_child,
    require_child_linked_to_parent,
    require_group_member,
    require_parent,
    require_parent_can_review_child,
)
from blink.errors import AuthzError


pytestmark = pytest.mark.asyncio


async def test_require_child_rejects_parent(make_parent):
    mom = await make_parent()
    with pytest.raises(AuthzError):
        require_child(mom.ctx)


async def test_require_parent_rejects_child(make_child):
    kid = await make_child()
    with pytest.raises(AuthzError):
        require_parent(kid.ctx)


async def test_unlinked_parent_cannot_review_child(
    conn, make_child, make_parent, link_parent_child,
):
    alice = await make_child("Alice")
    real_mom = await make_parent("RealMom")
    stranger = await make_parent("Stranger")
    await link_parent_child(real_mom, alice)

    with pytest.raises(AuthzError):
        await require_parent_can_review_child(
            conn, stranger.ctx, child_user_id=alice.user_id,
        )


async def test_linked_parent_passes_review_check(
    conn, make_child, make_parent, link_parent_child,
):
    alice = await make_child("Alice")
    mom = await make_parent("Mom")
    await link_parent_child(mom, alice)

    # No exception = pass.
    await require_parent_can_review_child(
        conn, mom.ctx, child_user_id=alice.user_id,
    )


async def test_require_child_linked_to_parent_denies_unrelated(
    conn, make_child, make_parent,
):
    alice = await make_child("Alice")
    stranger = await make_parent("Stranger")
    # No link created.

    with pytest.raises(AuthzError):
        await require_child_linked_to_parent(
            conn,
            child_user_id=alice.user_id,
            parent_account_id=stranger.parent_account_id,
        )


async def test_non_member_fails_group_member_check(
    conn, make_child, make_parent, link_parent_child, make_friendship,
):
    from blink.services import group_service
    from blink.policies.parent import upsert_parent_policy

    alice = await make_child("Alice")
    bob = await make_child("Bob")
    outsider = await make_child("Outsider")
    mom = await make_parent("Mom")
    await link_parent_child(mom, alice)
    await make_friendship(alice, bob)

    await upsert_parent_policy(
        conn, child_user_id=alice.user_id,
        updated_by=mom.parent_account_id, require_group_approval=False,
    )
    group, _m, _r = await group_service.create_group(
        conn, alice.ctx, name="Parken", initial_member_ids=[bob.user_id],
    )

    with pytest.raises(AuthzError):
        await require_group_member(
            conn, group_id=group.id, child_user_id=outsider.user_id,
        )
