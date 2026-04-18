"""group_billing_state data access."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import asyncpg

from blink.types import (
    BillingStatus,
    GroupBillingStateId,
    GroupId,
    GroupPlanTier,
    ParentAccountId,
)


@dataclass(frozen=True, slots=True)
class GroupBillingStateRow:
    id: GroupBillingStateId
    group_id: GroupId
    status: BillingStatus
    current_tier: GroupPlanTier
    activated_by_parent_account_id: ParentAccountId | None
    activated_at: datetime | None
    current_period_start: datetime | None
    current_period_end: datetime | None
    cancel_at_period_end: bool
    created_at: datetime
    updated_at: datetime


_COLS = """
    id, group_id,
    status::text AS status,
    current_tier::text AS current_tier,
    activated_by_parent_account_id, activated_at,
    current_period_start, current_period_end, cancel_at_period_end,
    created_at, updated_at
"""


def _row(r: asyncpg.Record) -> GroupBillingStateRow:
    return GroupBillingStateRow(
        id=GroupBillingStateId(r["id"]),
        group_id=GroupId(r["group_id"]),
        status=BillingStatus(r["status"]),
        current_tier=GroupPlanTier(r["current_tier"]),
        activated_by_parent_account_id=(
            ParentAccountId(r["activated_by_parent_account_id"])
            if r["activated_by_parent_account_id"] else None
        ),
        activated_at=r["activated_at"],
        current_period_start=r["current_period_start"],
        current_period_end=r["current_period_end"],
        cancel_at_period_end=r["cancel_at_period_end"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


async def get_by_group_id(
    conn: asyncpg.Connection,
    group_id: GroupId,
) -> GroupBillingStateRow | None:
    r = await conn.fetchrow(
        f"SELECT {_COLS} FROM group_billing_state WHERE group_id = $1",
        group_id,
    )
    return _row(r) if r else None


async def ensure_row(
    conn: asyncpg.Connection,
    group_id: GroupId,
) -> GroupBillingStateRow:
    """Create the billing row if missing (defensive — the trigger should
    have already done this). Returns the row either way."""
    existing = await get_by_group_id(conn, group_id)
    if existing is not None:
        return existing
    r = await conn.fetchrow(
        f"""
        INSERT INTO group_billing_state (group_id)
        VALUES ($1)
        ON CONFLICT (group_id) DO NOTHING
        RETURNING {_COLS}
        """,
        group_id,
    )
    if r is not None:
        return _row(r)
    # Race: another connection won the insert.
    existing = await get_by_group_id(conn, group_id)
    assert existing is not None
    return existing


async def set_active_at_tier(
    conn: asyncpg.Connection,
    *,
    group_id: GroupId,
    tier: GroupPlanTier,
    activated_by: ParentAccountId,
    period_start: datetime,
    period_end: datetime,
) -> GroupBillingStateRow:
    """Flip an inactive billing row to 'active' at the given tier.

    If the row is already active (activation replay with same or higher tier),
    keep the tier and refresh the period, but don't regress activated_at.
    """
    r = await conn.fetchrow(
        f"""
        UPDATE group_billing_state
           SET status                         = 'active',
               current_tier                   = $2::group_plan_tier,
               activated_by_parent_account_id = COALESCE(
                   activated_by_parent_account_id, $3
               ),
               activated_at                   = COALESCE(activated_at, now()),
               current_period_start           = $4,
               current_period_end             = $5,
               cancel_at_period_end           = false
         WHERE group_id = $1
        RETURNING {_COLS}
        """,
        group_id, tier.value, activated_by, period_start, period_end,
    )
    if r is None:
        raise RuntimeError("set_active_at_tier hit zero rows")
    return _row(r)


async def set_tier(
    conn: asyncpg.Connection,
    *,
    group_id: GroupId,
    new_tier: GroupPlanTier,
) -> GroupBillingStateRow:
    """Update current_tier on an already-active billing row."""
    r = await conn.fetchrow(
        f"""
        UPDATE group_billing_state
           SET current_tier = $2::group_plan_tier
         WHERE group_id = $1
        RETURNING {_COLS}
        """,
        group_id, new_tier.value,
    )
    if r is None:
        raise RuntimeError("set_tier hit zero rows")
    return _row(r)
