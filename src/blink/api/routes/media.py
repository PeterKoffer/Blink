"""/media routes.

Three endpoints:
    POST /media/upload-url   — create pending row + signed PUT URL
    POST /media/confirm      — verify object exists, flip upload_status=ready
    GET  /media/{id}/url     — issue short-lived signed GET URL
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from blink.api.deps import AuthDep, ConnDep, R2Dep
from blink.api.schemas import (
    ConfirmMediaBody,
    CreateMediaUploadUrlBody,
    MediaConfirmResponse,
    MediaReadUrlResponse,
    MediaUploadUrlResponse,
)
from blink.rate_limit.deps import rate_limit
from blink.services import media_service
from blink.types import (
    MEDIA_MAX_SIZE_BYTES,
    MEDIA_PUT_URL_TTL_SECONDS,
    GroupId,
    MediaId,
)

router = APIRouter(prefix="/media", tags=["media"])


@router.post(
    "/upload-url",
    response_model=MediaUploadUrlResponse,
    status_code=200,
    dependencies=[rate_limit("media:upload_url")],
)
async def create_upload_url(
    body: CreateMediaUploadUrlBody,
    ctx: AuthDep,
    conn: ConnDep,
    r2: R2Dep,
) -> MediaUploadUrlResponse:
    row, url = await media_service.create_upload_url(
        conn, r2, ctx,
        group_id=GroupId(body.group_id) if body.group_id else None,
        chat_id=body.chat_id,
        mime=body.mime,
        size=body.size,
        width=body.width,
        height=body.height,
    )
    return MediaUploadUrlResponse(
        media_id=row.id,
        upload_url=url,
        method="PUT",
        headers={"Content-Type": body.mime},
        max_size=MEDIA_MAX_SIZE_BYTES,
        expires_in_seconds=MEDIA_PUT_URL_TTL_SECONDS,
    )


@router.post(
    "/confirm",
    response_model=MediaConfirmResponse,
    status_code=200,
    dependencies=[rate_limit("media:confirm")],
)
async def confirm_media(
    body: ConfirmMediaBody,
    ctx: AuthDep,
    conn: ConnDep,
    r2: R2Dep,
) -> MediaConfirmResponse:
    row = await media_service.confirm_media(
        conn, r2, ctx, media_id=MediaId(body.media_id),
    )
    return MediaConfirmResponse(
        media_id=row.id,
        upload_status=row.upload_status.value,
        access_status=row.access_status.value,
    )


@router.get("/{media_id}/url", response_model=MediaReadUrlResponse)
async def get_read_url(
    media_id: UUID,
    ctx: AuthDep,
    conn: ConnDep,
    r2: R2Dep,
) -> MediaReadUrlResponse:
    url, ttl = await media_service.get_read_url(
        conn, r2, ctx, media_id=MediaId(media_id),
    )
    return MediaReadUrlResponse(
        media_id=media_id,
        url=url,
        expires_in_seconds=ttl,
    )
