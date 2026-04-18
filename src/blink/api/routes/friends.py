"""/friends routes — child-facing."""
from __future__ import annotations

from fastapi import APIRouter

from blink.api.deps import AuthDep, ConnDep
from blink.api.schemas import (
    CreateFriendRequestBody,
    FriendListItem,
    FriendRequestView,
)
from blink.rate_limit.deps import rate_limit
from blink.services import friend_service
from blink.types import UserId

router = APIRouter(prefix="/friends", tags=["friends"])


@router.post(
    "/requests",
    response_model=FriendRequestView,
    status_code=200,
    dependencies=[rate_limit("friends:create_request")],
)
async def create_friend_request(
    body: CreateFriendRequestBody,
    ctx: AuthDep,
    conn: ConnDep,
) -> FriendRequestView:
    req = await friend_service.create_friend_request(
        conn, ctx, target_child_id=UserId(body.target_child_id),
    )
    return FriendRequestView.model_validate(req)


@router.get("", response_model=list[FriendListItem])
async def list_friends(ctx: AuthDep, conn: ConnDep) -> list[FriendListItem]:
    rows = await friend_service.list_friends(conn, ctx)
    return [
        FriendListItem(
            friendship_id=r["friendship_id"],
            child_user_id=r["peer_id"],
            display_name=r["display_name"],
            avatar_initial=r["avatar_initial"],
            approved_at=r["approved_at"],
        )
        for r in rows
    ]
