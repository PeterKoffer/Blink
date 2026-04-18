"""GET /me — the authenticated user's own state.

Used by the client to render "who am I right now" consistently across both
child and parent modes. For parents, this also lists linked children.
"""
from __future__ import annotations

from fastapi import APIRouter

from blink.api.deps import AuthDep, ConnDep
from blink.api.schemas import MeLinkedChild, MeResponse
from blink.errors import NotFoundError
from blink.repos import users as users_repo
from blink.types import LinkStatus, UserType

router = APIRouter(tags=["me"])


@router.get("/me", response_model=MeResponse)
async def get_me(ctx: AuthDep, conn: ConnDep) -> MeResponse:
    me = await users_repo.get_by_id(conn, ctx.user_id)
    if me is None:
        raise NotFoundError("User not found")

    resp = MeResponse(
        user_id=me.id,
        user_type=me.type,
        status=me.status,
        display_name=me.display_name,
        avatar_type=me.avatar_type,
        avatar_value=me.avatar_value,
        avatar_color=me.avatar_color,
        blink_code=me.blink_code,
        onboarding_status=me.onboarding_status,
    )

    if me.type == UserType.PARENT and ctx.parent_account_id is not None:
        # Fetch linked children.
        rows = await conn.fetch(
            """
            SELECT u.id, u.display_name,
                   u.avatar_type::text AS avatar_type,
                   u.avatar_value, u.avatar_color,
                   u.onboarding_status::text AS onboarding_status,
                   u.status::text AS status
            FROM child_parent_links cpl
            JOIN users u ON u.id = cpl.child_user_id
            WHERE cpl.parent_account_id = $1
              AND cpl.status = $2
            ORDER BY u.display_name
            """,
            ctx.parent_account_id, LinkStatus.ACTIVE.value,
        )
        from blink.types import (
            AvatarType,
            OnboardingStatus,
            UserStatus,
        )
        children = []
        for r in rows:
            children.append(MeLinkedChild(
                user_id=r["id"],
                display_name=r["display_name"],
                avatar_type=AvatarType(r["avatar_type"]) if r["avatar_type"] else None,
                avatar_value=r["avatar_value"],
                avatar_color=r["avatar_color"],
                onboarding_status=(
                    OnboardingStatus(r["onboarding_status"])
                    if r["onboarding_status"] else None
                ),
                status=UserStatus(r["status"]),
            ))

        # Parent account details (verified flag)
        pa_row = await conn.fetchrow(
            "SELECT verified FROM parent_accounts WHERE id = $1",
            ctx.parent_account_id,
        )
        resp = resp.model_copy(update={
            "parent_account_id": ctx.parent_account_id,
            "parent_verified": bool(pa_row["verified"]) if pa_row else False,
            "linked_children": children,
        })

    return resp
