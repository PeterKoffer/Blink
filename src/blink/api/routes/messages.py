"""Messages routes.

Two endpoints in Sprint 3:
    POST /messages                      — create text message
    GET  /groups/{group_id}/messages    — list active messages in group

Direct chats are not backend-modeled in v1, so /chats/{id}/messages is
not implemented here — the client uses groupId for now.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Query

from blink.api.deps import AuthDep, ConnDep
from blink.api.schemas import CreateMessageBody, MessageListResponse, MessageView
from blink.rate_limit.deps import rate_limit
from blink.repos import messages as messages_repo
from blink.services import message_service
from blink.types import GroupId, MediaId

router = APIRouter(tags=["messages"])


def _to_view(m: messages_repo.MessageRow) -> MessageView:
    return MessageView(
        id=m.id,
        sender_id=m.sender_id,
        sender_display_name=m.sender_display_name,
        sender_avatar_initial=m.sender_avatar_initial,
        group_id=m.group_id,
        chat_id=m.chat_id,
        type=m.type,
        text=m.text_content,
        media_id=m.media_id,
        client_message_id=m.client_message_id,
        ephemeral_mode=m.ephemeral_mode,
        ttl_seconds=m.ttl_seconds,
        created_at=m.created_at,
        expires_at=m.expires_at,
        status=m.status,
    )


@router.post(
    "/messages",
    response_model=MessageView,
    status_code=200,
    dependencies=[rate_limit("messages:create")],
)
async def create_message(
    body: CreateMessageBody,
    ctx: AuthDep,
    conn: ConnDep,
) -> MessageView:
    """Create a text message. Idempotent on (sender, clientMessageId)."""
    msg = await message_service.create_message(
        conn, ctx,
        group_id=GroupId(body.group_id) if body.group_id else None,
        chat_id=body.chat_id,
        type=body.type,
        text=body.text,
        media_id=MediaId(body.media_id) if body.media_id else None,
        client_message_id=body.client_message_id,
        ephemeral_mode=body.ephemeral_mode,
        ttl_seconds=body.ttl_seconds,
    )
    return _to_view(msg)


@router.get(
    "/groups/{group_id}/messages",
    response_model=MessageListResponse,
)
async def list_group_messages(
    group_id: UUID,
    ctx: AuthDep,
    conn: ConnDep,
    limit: int = Query(50, ge=1, le=200),
    before: datetime | None = Query(None, description="Return messages created before this timestamp"),
) -> MessageListResponse:
    msgs = await message_service.list_group_messages(
        conn, ctx, group_id=GroupId(group_id), limit=limit, before=before,
    )
    return MessageListResponse(messages=[_to_view(m) for m in msgs])
