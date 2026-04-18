"""Group billing state service — activation, upgrade, status.

No external payment provider in v1. The service manages our own state
machine; Stripe/Paddle wiring is future work.

Authz: any parent linked to at least one active member of the group can
manage billing. Same rule as `require_group_access` — a parent who
oversees a child in the group can take billing actions for the group.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import asyncpg

from blink.audit import Events, write_audit
from blink.auth.context import AuthContext
from blink.authz.require import require_group_access, require_parent
from blink.errors import NotFoundError, StateConflictError, ValidationError
from blink.pricing import cap_for, is_higher_tier, next_tier
from blink.repos import billing as billing_repo
from blink.repos import groups as groups_repo
from blink.types import (
    BillingStatus,
    GroupId,
    GroupPlanTier,
    HARD_MAX_GROUP_MEMBERS,
)


# Default billing period: 30 days. In a real integration, the provider
# dictates the period; here we set a placeholder so reports/UIs have
# reasonable timestamps to display.
_DEFAULT_PERIOD_DAYS = 30


@dataclass(frozen=True, slots=True)
class BillingSummary:
    """Read-only view for the parent-facing /billing endpoint."""
    status: BillingStatus
    current_tier: GroupPlanTier
    current_cap: int
    next_tier: GroupPlanTier | None
    next_tier_cap: int | None
    active_member_count: int
    pending_member_count: int
    total_member_count: int
    group_full_on_current_tier: bool
    at_hard_cap: bool
    activated_at: datetime | None
    current_period_start: datetime | None
    current_period_end: datetime | None


async def get_billing_summary(
    conn: asyncpg.Connection,
    ctx: AuthContext,
    *,
    group_id: GroupId,
) -> BillingSummary:
    require_parent(ctx)
    await require_group_access(conn, ctx, group_id=group_id)

    state = await billing_repo.ensure_row(conn, group_id)
    active, pending = await groups_repo.count_members(conn, group_id)
    total = active + pending
    cap = cap_for(state.current_tier)
    nt = next_tier(state.current_tier)

    return BillingSummary(
        status=state.status,
        current_tier=state.current_tier,
        current_cap=cap,
        next_tier=nt,
        next_tier_cap=cap_for(nt) if nt else None,
        active_member_count=active,
        pending_member_count=pending,
        total_member_count=total,
        group_full_on_current_tier=total >= cap,
        at_hard_cap=total >= HARD_MAX_GROUP_MEMBERS,
        activated_at=state.activated_at,
        current_period_start=state.current_period_start,
        current_period_end=state.current_period_end,
    )


async def activate_group(
    conn: asyncpg.Connection,
    ctx: AuthContext,
    *,
    group_id: GroupId,
    tier: GroupPlanTier,
) -> billing_repo.GroupBillingStateRow:
    require_parent(ctx)
    assert ctx.parent_account_id is not None
    await require_group_access(conn, ctx, group_id=group_id)

    async with conn.transaction():
        state = await billing_repo.ensure_row(conn, group_id)
        group = await groups_repo.get_group(conn, group_id)
        if group is None:
            raise NotFoundError("Group not found")

        # If we're re-activating at a LOWER tier than current, that's a
        # downgrade — not supported in v1.
        if state.status == BillingStatus.ACTIVE and not (
            tier == state.current_tier or is_higher_tier(tier, state.current_tier)
        ):
            raise StateConflictError(
                "Downgrade is not supported in v1; use upgrade to go up."
            )

        # Tier must be big enough to hold the current members.
        active, pending = await groups_repo.count_members(conn, group_id)
        total = active + pending
        if total > cap_for(tier):
            raise StateConflictError(
                f"Group has {total} members — cannot activate at tier '{tier.value}' "
                f"(cap={cap_for(tier)}). Choose a higher tier."
            )

        now = datetime.now(tz=timezone.utc)
        end = now + timedelta(days=_DEFAULT_PERIOD_DAYS)

        updated = await billing_repo.set_active_at_tier(
            conn,
            group_id=group_id,
            tier=tier,
            activated_by=ctx.parent_account_id,
            period_start=now,
            period_end=end,
        )
        # Mirror the cap tier onto groups for hot-path enforcement.
        await groups_repo.set_member_cap_tier(
            conn, group_id=group_id, tier=tier,
        )

        await write_audit(
            conn,
            event_type=Events.BILLING_ACTIVATED,
            actor_parent_account_id=ctx.parent_account_id,
            target_type="group",
            target_id=group_id,
            payload={"tier": tier.value},
        )
        return updated


async def upgrade_group_tier(
    conn: asyncpg.Connection,
    ctx: AuthContext,
    *,
    group_id: GroupId,
    new_tier: GroupPlanTier,
) -> billing_repo.GroupBillingStateRow:
    require_parent(ctx)
    assert ctx.parent_account_id is not None
    await require_group_access(conn, ctx, group_id=group_id)

    async with conn.transaction():
        state = await billing_repo.ensure_row(conn, group_id)
        if state.status != BillingStatus.ACTIVE:
            raise StateConflictError(
                f"Cannot upgrade — billing is {state.status.value}. Activate first."
            )
        if not is_higher_tier(new_tier, state.current_tier):
            raise ValidationError(
                f"New tier '{new_tier.value}' must be higher than current "
                f"'{state.current_tier.value}'. Downgrade is not supported in v1."
            )

        updated = await billing_repo.set_tier(
            conn, group_id=group_id, new_tier=new_tier,
        )
        await groups_repo.set_member_cap_tier(
            conn, group_id=group_id, tier=new_tier,
        )

        await write_audit(
            conn,
            event_type=Events.BILLING_UPGRADED,
            actor_parent_account_id=ctx.parent_account_id,
            target_type="group",
            target_id=group_id,
            payload={
                "from_tier": state.current_tier.value,
                "to_tier": new_tier.value,
            },
        )
        return updated
