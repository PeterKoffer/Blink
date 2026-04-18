"""/onboarding routes — child profile + parent invite + verify + approve.

These endpoints are deliberately light on auth in v1:
- `/child-profile` is unauthenticated. The client has nothing yet.
- `/parent-invite` takes childUserId explicitly (rate-limited).
- `/parent-invite/{token}` preview is public (by-token only — the token IS
  the capability).
- `/parent-verify` + `/parent-approve` + `/parent-decline` are token-bearer.

The invite-token is 32 url-safe bytes of entropy. The OTP is 6 digits with
an attempts cap. Together this is the v1 adult-verification signal.
"""
from __future__ import annotations

from fastapi import APIRouter, Request

from blink.api.deps import ConnDep, OtpAdapterDep
from blink.api.schemas import (
    ApproveChildBody,
    ChildProfileResponse,
    CreateChildProfileBody,
    DeclineChildBody,
    InvitePreviewResponse,
    ParentInviteResponse,
    StartParentInviteBody,
    VerifyParentBody,
)
from blink.config import get_settings
from blink.errors import NotFoundError
from blink.repos import parent_invites as pi_repo
from blink.repos import users as users_repo
from blink.services import onboarding_service
from blink.types import CONSENT_VERSION, UserId

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.post(
    "/child-profile",
    response_model=ChildProfileResponse,
    status_code=201,
)
async def create_child_profile(
    body: CreateChildProfileBody,
    conn: ConnDep,
) -> ChildProfileResponse:
    row = await onboarding_service.create_child_profile(
        conn,
        display_name=body.display_name,
        avatar_type=body.avatar_type,
        avatar_value=body.avatar_value,
        avatar_color=body.avatar_color,
    )
    return ChildProfileResponse(
        user_id=row.id,
        display_name=row.display_name or "",
        avatar_type=row.avatar_type or body.avatar_type,
        avatar_value=row.avatar_value or body.avatar_value,
        avatar_color=row.avatar_color or body.avatar_color,
        blink_code=row.blink_code or "",
        onboarding_status=row.onboarding_status,  # type: ignore[arg-type]
    )


@router.post(
    "/parent-invite",
    response_model=ParentInviteResponse,
    status_code=201,
)
async def start_parent_invite(
    body: StartParentInviteBody,
    conn: ConnDep,
    otp_adapter: OtpAdapterDep,
) -> ParentInviteResponse:
    invite, otp_plaintext = await onboarding_service.start_parent_invite(
        conn, otp_adapter,  # type: ignore[arg-type]
        child_user_id=UserId(body.child_user_id),
        contact=body.contact,
    )
    settings = get_settings()
    # Only expose the raw token + OTP in responses when dev-bypass is active.
    # Outside dev, the parent receives the OTP via email/SMS adapter only.
    dev = settings.blink_dev_bypass_auth
    return ParentInviteResponse(
        invite_id=invite.id,
        child_user_id=invite.child_user_id,
        status=invite.status,
        expires_at=invite.expires_at,
        invite_token=invite.invite_token if dev else None,
        otp=otp_plaintext if dev else None,
    )


def _mask_contact(contact: str) -> str:
    """Show enough to recognise without revealing the full handle."""
    if "@" in contact:
        local, _, domain = contact.partition("@")
        if len(local) <= 2:
            return f"{local[0]}*@{domain}"
        return f"{local[0]}{'*' * (len(local) - 2)}{local[-1]}@{domain}"
    # Phone: keep last 2 digits.
    return ("*" * max(0, len(contact) - 2)) + contact[-2:]


@router.get(
    "/parent-invite/{token}",
    response_model=InvitePreviewResponse,
)
async def preview_parent_invite(
    token: str,
    conn: ConnDep,
) -> InvitePreviewResponse:
    invite = await pi_repo.get_by_token(conn, token)
    if invite is None:
        raise NotFoundError("Invite not found")

    child = await users_repo.get_by_id(conn, invite.child_user_id)
    return InvitePreviewResponse(
        child_display_name=child.display_name if child else None,
        child_avatar_type=child.avatar_type if child else None,
        child_avatar_value=child.avatar_value if child else None,
        child_avatar_color=child.avatar_color if child else None,
        contact_masked=_mask_contact(invite.contact_email_or_phone),
        status=invite.status,
        expires_at=invite.expires_at,
    )


@router.post(
    "/parent-verify",
    response_model=ParentInviteResponse,
    status_code=200,
)
async def verify_parent(
    body: VerifyParentBody,
    conn: ConnDep,
) -> ParentInviteResponse:
    invite = await onboarding_service.verify_parent_invite(
        conn,
        invite_token=body.invite_token,
        otp=body.otp,
    )
    return ParentInviteResponse(
        invite_id=invite.id,
        child_user_id=invite.child_user_id,
        status=invite.status,
        expires_at=invite.expires_at,
    )


@router.post(
    "/parent-approve",
    response_model=ChildProfileResponse,
    status_code=200,
)
async def approve_child(
    body: ApproveChildBody,
    conn: ConnDep,
    request: Request,
) -> ChildProfileResponse:
    # Capture IP + UA for the consent record (best-effort).
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")

    child, _parent_account_id = await onboarding_service.approve_child(
        conn,
        invite_token=body.invite_token,
        consent_accepted=body.consent_accepted,
        consent_version=body.consent_version or CONSENT_VERSION,
        ip_address=ip,
        user_agent=ua,
    )
    return ChildProfileResponse(
        user_id=child.id,
        display_name=child.display_name or "",
        avatar_type=child.avatar_type or None,  # type: ignore[arg-type]
        avatar_value=child.avatar_value or "",
        avatar_color=child.avatar_color or "#000000",
        blink_code=child.blink_code or "",
        onboarding_status=child.onboarding_status,  # type: ignore[arg-type]
    )


@router.post(
    "/parent-decline",
    response_model=ChildProfileResponse,
    status_code=200,
)
async def decline_child(
    body: DeclineChildBody,
    conn: ConnDep,
) -> ChildProfileResponse:
    child = await onboarding_service.decline_child(
        conn, invite_token=body.invite_token,
    )
    return ChildProfileResponse(
        user_id=child.id,
        display_name=child.display_name or "",
        avatar_type=child.avatar_type,  # type: ignore[arg-type]
        avatar_value=child.avatar_value or "",
        avatar_color=child.avatar_color or "#000000",
        blink_code=child.blink_code or "",
        onboarding_status=child.onboarding_status,  # type: ignore[arg-type]
    )
