"""Billing state — activation, upgrade, summary."""
from __future__ import annotations

import pytest

from blink.errors import AuthzError, StateConflictError, ValidationError
from blink.repos import billing as billing_repo
from blink.repos import groups as groups_repo
from blink.services import billing_service
from blink.types import (
    BillingStatus,
    GroupPlanTier,
)


pytestmark = pytest.mark.asyncio


async def _link_parent_to_group(conn, mom, child, gid):
    """Ensure `mom` is linked to `child` and `child` is a member of `gid`.

    Needed so require_group_access() passes for mom against gid.
    """
    # Link parent to child.
    await conn.execute(
        """
        INSERT INTO child_parent_links
            (child_user_id, parent_account_id, status, activated_at)
        VALUES ($1, $2, 'active', now())
        ON CONFLICT (child_user_id, parent_account_id) DO NOTHING
        """,
        child.user_id, mom.parent_account_id,
    )


# ----------------------------- summary -----------------------------

async def test_parent_can_get_billing_summary(
    conn, make_child, make_parent, make_active_group,
):
    alice = await make_child("Alice")
    mom = await make_parent("Mom")
    await _link_parent_to_group(conn, mom, alice, None)  # pre-link

    gid = await make_active_group(alice, tier=GroupPlanTier.LILLE)

    summary = await billing_service.get_billing_summary(
        conn, mom.ctx, group_id=gid,
    )
    assert summary.status == BillingStatus.INACTIVE  # default after trigger
    assert summary.current_tier == GroupPlanTier.LILLE
    assert summary.current_cap == 10
    assert summary.next_tier == GroupPlanTier.NORMAL
    assert summary.next_tier_cap == 30
    assert summary.active_member_count == 1  # just the creator
    assert summary.pending_member_count == 0
    assert not summary.group_full_on_current_tier
    assert not summary.at_hard_cap


# ----------------------------- activate -----------------------------

async def test_parent_activates_group_at_normal_tier(
    conn, make_child, make_parent, make_active_group,
):
    alice = await make_child("Alice")
    mom = await make_parent("Mom")
    await _link_parent_to_group(conn, mom, alice, None)
    gid = await make_active_group(alice, tier=GroupPlanTier.LILLE)

    row = await billing_service.activate_group(
        conn, mom.ctx, group_id=gid, tier=GroupPlanTier.NORMAL,
    )
    assert row.status == BillingStatus.ACTIVE
    assert row.current_tier == GroupPlanTier.NORMAL
    assert row.activated_at is not None
    assert row.activated_by_parent_account_id == mom.parent_account_id

    # Cap tier on groups mirrors the change.
    group = await groups_repo.get_group(conn, gid)
    assert group is not None
    assert group.member_cap_tier == GroupPlanTier.NORMAL


async def test_unlinked_parent_cannot_activate(
    conn, make_child, make_parent, make_active_group,
):
    alice = await make_child("Alice")
    stranger = await make_parent("Stranger")
    gid = await make_active_group(alice, tier=GroupPlanTier.LILLE)
    # No link from stranger to alice → no group access.

    with pytest.raises(AuthzError):
        await billing_service.activate_group(
            conn, stranger.ctx, group_id=gid, tier=GroupPlanTier.NORMAL,
        )


async def test_activation_at_too_small_tier_fails(
    conn, make_child, make_parent, make_active_group, make_many_children,
):
    """A group with 15 members cannot be activated at 'lille' (cap 10)."""
    creator = await make_child("Creator")
    mom = await make_parent("Mom")
    await _link_parent_to_group(conn, mom, creator, None)
    # Start at 'stor' so we can pack in more members first.
    gid = await make_active_group(creator, tier=GroupPlanTier.STOR)

    fillers = await make_many_children(14, prefix="M")
    for f in fillers:
        await conn.execute(
            """
            INSERT INTO group_memberships
                (group_id, child_user_id, role, status, activated_at)
            VALUES ($1, $2, 'member', 'active', now())
            """,
            gid, f.user_id,
        )

    # Now try to activate at 'lille' — too small.
    with pytest.raises(StateConflictError):
        await billing_service.activate_group(
            conn, mom.ctx, group_id=gid, tier=GroupPlanTier.LILLE,
        )


# ----------------------------- upgrade -----------------------------

async def test_parent_upgrades_lille_to_normal(
    conn, make_child, make_parent, make_active_group,
):
    alice = await make_child("Alice")
    mom = await make_parent("Mom")
    await _link_parent_to_group(conn, mom, alice, None)
    gid = await make_active_group(alice, tier=GroupPlanTier.LILLE)

    await billing_service.activate_group(
        conn, mom.ctx, group_id=gid, tier=GroupPlanTier.LILLE,
    )
    row = await billing_service.upgrade_group_tier(
        conn, mom.ctx, group_id=gid, new_tier=GroupPlanTier.NORMAL,
    )
    assert row.current_tier == GroupPlanTier.NORMAL

    group = await groups_repo.get_group(conn, gid)
    assert group is not None
    assert group.member_cap_tier == GroupPlanTier.NORMAL


async def test_upgrade_normal_to_stor(
    conn, make_child, make_parent, make_active_group,
):
    alice = await make_child("Alice")
    mom = await make_parent("Mom")
    await _link_parent_to_group(conn, mom, alice, None)
    gid = await make_active_group(alice, tier=GroupPlanTier.NORMAL)

    await billing_service.activate_group(
        conn, mom.ctx, group_id=gid, tier=GroupPlanTier.NORMAL,
    )
    row = await billing_service.upgrade_group_tier(
        conn, mom.ctx, group_id=gid, new_tier=GroupPlanTier.STOR,
    )
    assert row.current_tier == GroupPlanTier.STOR


async def test_upgrade_to_same_or_lower_tier_rejected(
    conn, make_child, make_parent, make_active_group,
):
    alice = await make_child("Alice")
    mom = await make_parent("Mom")
    await _link_parent_to_group(conn, mom, alice, None)
    gid = await make_active_group(alice, tier=GroupPlanTier.NORMAL)

    await billing_service.activate_group(
        conn, mom.ctx, group_id=gid, tier=GroupPlanTier.NORMAL,
    )
    # Same tier.
    with pytest.raises(ValidationError):
        await billing_service.upgrade_group_tier(
            conn, mom.ctx, group_id=gid, new_tier=GroupPlanTier.NORMAL,
        )
    # Lower tier (downgrade, v1 unsupported).
    with pytest.raises(ValidationError):
        await billing_service.upgrade_group_tier(
            conn, mom.ctx, group_id=gid, new_tier=GroupPlanTier.LILLE,
        )


async def test_upgrade_requires_activation_first(
    conn, make_child, make_parent, make_active_group,
):
    alice = await make_child("Alice")
    mom = await make_parent("Mom")
    await _link_parent_to_group(conn, mom, alice, None)
    gid = await make_active_group(alice, tier=GroupPlanTier.LILLE)

    # No activation call → billing_state.status is still 'inactive'.
    with pytest.raises(StateConflictError):
        await billing_service.upgrade_group_tier(
            conn, mom.ctx, group_id=gid, new_tier=GroupPlanTier.NORMAL,
        )


# ----------------------------- trigger-created row -----------------------------

async def test_trigger_creates_billing_row_on_group_insert(
    conn, make_child, make_active_group,
):
    alice = await make_child("Alice")
    gid = await make_active_group(alice, tier=GroupPlanTier.LILLE)

    row = await billing_repo.get_by_group_id(conn, gid)
    assert row is not None
    assert row.status == BillingStatus.INACTIVE
    assert row.current_tier == GroupPlanTier.LILLE
