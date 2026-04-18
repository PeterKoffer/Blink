"""/parent/groups/{group_id}/billing, activate, upgrade."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from blink.api.deps import AuthDep, ConnDep
from blink.api.schemas import (
    ActivateGroupBody,
    BillingStateResponse,
    BillingSummaryResponse,
    UpgradeGroupBody,
)
from blink.services import billing_service
from blink.types import GroupId

router = APIRouter(prefix="/parent/groups", tags=["billing"])


@router.get("/{group_id}/billing", response_model=BillingSummaryResponse)
async def get_billing(
    group_id: UUID,
    ctx: AuthDep,
    conn: ConnDep,
) -> BillingSummaryResponse:
    summary = await billing_service.get_billing_summary(
        conn, ctx, group_id=GroupId(group_id),
    )
    return BillingSummaryResponse(
        status=summary.status,
        current_tier=summary.current_tier,
        current_cap=summary.current_cap,
        next_tier=summary.next_tier,
        next_tier_cap=summary.next_tier_cap,
        active_member_count=summary.active_member_count,
        pending_member_count=summary.pending_member_count,
        total_member_count=summary.total_member_count,
        group_full_on_current_tier=summary.group_full_on_current_tier,
        at_hard_cap=summary.at_hard_cap,
        activated_at=summary.activated_at,
        current_period_start=summary.current_period_start,
        current_period_end=summary.current_period_end,
    )


def _to_state_response(
    group_id: UUID, row
) -> BillingStateResponse:
    return BillingStateResponse(
        group_id=group_id,
        status=row.status,
        current_tier=row.current_tier,
        activated_at=row.activated_at,
        current_period_start=row.current_period_start,
        current_period_end=row.current_period_end,
    )


@router.post("/{group_id}/activate", response_model=BillingStateResponse, status_code=200)
async def activate(
    group_id: UUID,
    body: ActivateGroupBody,
    ctx: AuthDep,
    conn: ConnDep,
) -> BillingStateResponse:
    row = await billing_service.activate_group(
        conn, ctx, group_id=GroupId(group_id), tier=body.tier,
    )
    return _to_state_response(group_id, row)


@router.post("/{group_id}/upgrade", response_model=BillingStateResponse, status_code=200)
async def upgrade(
    group_id: UUID,
    body: UpgradeGroupBody,
    ctx: AuthDep,
    conn: ConnDep,
) -> BillingStateResponse:
    row = await billing_service.upgrade_group_tier(
        conn, ctx, group_id=GroupId(group_id), new_tier=body.tier,
    )
    return _to_state_response(group_id, row)
