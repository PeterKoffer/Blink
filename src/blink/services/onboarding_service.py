"""Onboarding service — child profile + adult verification + approval.

Flow (matches project_blink_adult_verification.md):

    1. create_child_profile      (unauthenticated)
       → child row: status=pending_activation, onboarding_status=profile_pending
    2. start_parent_invite       (with childUserId)
       → parent_invites row pending; OTP delivered via adapter
       → child onboarding_status=parent_invited
    3. verify_parent_invite      (token + OTP)
       → parent_invites status='verified'
       → child onboarding_status=parent_verified
    4. approve_child             (token + consentAccepted)
       → parent_account created-or-linked, verified=true
       → consent_record written
       → child_parent_links row active
       → child status='active', onboarding_status='active'
       → parent_invites status='approved'
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import asyncpg

from blink.audit import Events, write_audit
from blink.errors import (
    AuthzError,
    NotFoundError,
    StateConflictError,
    ValidationError,
)
from blink.onboarding.adapters import OtpDeliveryAdapter
from blink.onboarding.codes import (
    generate_blink_code,
    generate_invite_token,
    generate_otp,
    hash_otp,
    verify_otp,
)
from blink.repos import consent as consent_repo
from blink.repos import parent_invites as pi_repo
from blink.repos import users as users_repo
from blink.types import (
    CONSENT_TEXT,
    CONSENT_VERSION,
    INVITE_EXPIRES_MINUTES,
    OTP_MAX_ATTEMPTS,
    AvatarType,
    LinkStatus,
    OnboardingStatus,
    ParentAccountId,
    ParentInviteStatus,
    UserId,
    UserType,
)


MAX_DISPLAY_NAME = 24
_BLINK_CODE_RETRIES = 5


# ---------- child profile ----------

async def create_child_profile(
    conn: asyncpg.Connection,
    *,
    display_name: str,
    avatar_type: AvatarType,
    avatar_value: str,
    avatar_color: str,
) -> users_repo.UserRow:
    """Unauthenticated entry point. Creates a pending child user.

    Validation:
    - display_name 1..24 chars, stripped
    - avatar_value 1..20 chars
    - avatar_color #RRGGBB
    """
    dn = (display_name or "").strip()
    if not dn or len(dn) > MAX_DISPLAY_NAME:
        raise ValidationError(
            f"displayName must be 1..{MAX_DISPLAY_NAME} chars (non-blank)"
        )
    if not avatar_value or len(avatar_value) > 20:
        raise ValidationError("avatarValue must be 1..20 chars")
    if not (avatar_color.startswith("#") and len(avatar_color) == 7):
        raise ValidationError("avatarColor must be #RRGGBB hex")

    async with conn.transaction():
        last_err: Exception | None = None
        for _ in range(_BLINK_CODE_RETRIES):
            code = generate_blink_code()
            try:
                row = await users_repo.insert_child_profile(
                    conn,
                    display_name=dn,
                    avatar_type=avatar_type,
                    avatar_value=avatar_value,
                    avatar_color=avatar_color,
                    blink_code=code,
                )
                await write_audit(
                    conn,
                    event_type=Events.ONBOARDING_PROFILE_CREATED,
                    actor_user_id=row.id,
                    target_type="user",
                    target_id=row.id,
                    payload={"display_name": dn},
                )
                return row
            except asyncpg.UniqueViolationError as e:
                last_err = e
                continue
        raise RuntimeError("Could not allocate unique blink_code") from last_err


# ---------- parent invite ----------

async def start_parent_invite(
    conn: asyncpg.Connection,
    otp_adapter: OtpDeliveryAdapter,
    *,
    child_user_id: UserId,
    contact: str,
) -> tuple[pi_repo.ParentInviteRow, str]:
    """Create or replace the pending invite for a child and deliver an OTP.

    Returns `(invite_row, otp_plaintext)`. The plaintext OTP is returned so
    dev-mode callers can surface it for local testing. It MUST only be
    exposed to the client when `BLINK_DEV_BYPASS_AUTH=true`.
    """
    contact = contact.strip()
    if not (3 <= len(contact) <= 200):
        raise ValidationError("contact must be 3..200 chars")

    async with conn.transaction():
        child = await users_repo.get_by_id(conn, child_user_id)
        if child is None:
            raise NotFoundError("Child user not found")
        if child.type != UserType.CHILD:
            raise StateConflictError("Target user is not a child")
        if child.onboarding_status not in (
            OnboardingStatus.PROFILE_PENDING,
            OnboardingStatus.PARENT_INVITED,
            OnboardingStatus.DECLINED,
        ):
            raise StateConflictError(
                f"Child is not eligible for invite (status={child.onboarding_status})"
            )

        # Supersede any existing pending invite for this child: decline it.
        existing = await pi_repo.get_pending_for_child(conn, child_user_id)
        if existing is not None:
            await pi_repo.mark_declined(conn, existing.id)

        otp = generate_otp()
        token = generate_invite_token()
        expires = datetime.now(tz=timezone.utc) + timedelta(
            minutes=INVITE_EXPIRES_MINUTES
        )

        invite = await pi_repo.insert_pending(
            conn,
            child_user_id=child_user_id,
            contact=contact,
            invite_token=token,
            otp_code_hash=hash_otp(otp),
            expires_at=expires,
        )

        await users_repo.set_onboarding_status(
            conn,
            user_id=child_user_id,
            new_status=OnboardingStatus.PARENT_INVITED,
        )

        await write_audit(
            conn,
            event_type=Events.ONBOARDING_PARENT_INVITED,
            actor_user_id=child_user_id,
            target_type="parent_invite",
            target_id=invite.id,
            payload={"contact": contact},
        )

    # Deliver OTP *outside* the DB transaction so a delivery-layer failure
    # doesn't roll back the invite row. The parent can request a resend.
    await otp_adapter.send_otp(
        contact=contact,
        otp=otp,
        invite_token=token,
        child_display_name=child.display_name,
    )
    return invite, otp


# ---------- verify ----------

async def verify_parent_invite(
    conn: asyncpg.Connection,
    *,
    invite_token: str,
    otp: str,
) -> pi_repo.ParentInviteRow:
    async with conn.transaction():
        invite = await pi_repo.get_by_token(conn, invite_token)
        if invite is None:
            raise NotFoundError("Invite not found")
        now = datetime.now(tz=invite.expires_at.tzinfo)
        if invite.expires_at <= now:
            raise StateConflictError("Invite has expired")
        if invite.status != ParentInviteStatus.PENDING:
            raise StateConflictError(
                f"Invite is not pending (status={invite.status.value})"
            )
        if invite.otp_attempts >= OTP_MAX_ATTEMPTS:
            raise StateConflictError("Too many OTP attempts; request a new invite")

        if not verify_otp(otp, invite.otp_code_hash):
            attempts = await pi_repo.increment_otp_attempts(conn, invite.id)
            await write_audit(
                conn,
                event_type=Events.ONBOARDING_OTP_FAILED,
                target_type="parent_invite",
                target_id=invite.id,
                payload={"attempts": attempts},
            )
            raise ValidationError("Incorrect OTP")

        verified = await pi_repo.mark_verified(conn, invite.id)
        await users_repo.set_onboarding_status(
            conn,
            user_id=invite.child_user_id,
            new_status=OnboardingStatus.PARENT_VERIFIED,
        )
        await write_audit(
            conn,
            event_type=Events.ONBOARDING_PARENT_VERIFIED,
            target_type="parent_invite",
            target_id=invite.id,
        )
        return verified


# ---------- approve ----------

async def approve_child(
    conn: asyncpg.Connection,
    *,
    invite_token: str,
    consent_accepted: bool,
    consent_version: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> tuple[users_repo.UserRow, ParentAccountId]:
    """Approve the child — final step of onboarding.

    Creates a parent_user + parent_account if the contact is new, else links
    to the existing account. Writes consent. Activates the child.
    """
    if not consent_accepted:
        raise ValidationError("Consent must be accepted to approve a child")
    if consent_version not in CONSENT_TEXT:
        raise ValidationError(f"Unknown consent version: {consent_version}")

    async with conn.transaction():
        invite = await pi_repo.get_by_token(conn, invite_token)
        if invite is None:
            raise NotFoundError("Invite not found")
        if invite.status != ParentInviteStatus.VERIFIED:
            raise StateConflictError(
                f"Invite must be verified first (status={invite.status.value})"
            )

        # Find or create parent_user + parent_account for this contact.
        existing_account = await conn.fetchrow(
            """
            SELECT pa.id AS parent_account_id, pa.user_id AS parent_user_id
            FROM parent_accounts pa
            WHERE pa.contact_email_or_phone = $1
            """,
            invite.contact_email_or_phone,
        )
        if existing_account is not None:
            parent_account_id = ParentAccountId(existing_account["parent_account_id"])
            # Ensure the account is marked verified (OTP just succeeded).
            await conn.execute(
                "UPDATE parent_accounts SET verified = true WHERE id = $1",
                parent_account_id,
            )
        else:
            # Create a minimal parent user + account.
            user_row = await conn.fetchrow(
                """
                INSERT INTO users (type, status, display_name,
                                   onboarding_status)
                VALUES ('parent', 'active', $1, 'active')
                RETURNING id
                """,
                # Display name: use contact as a placeholder; production UI
                # would collect the parent's real name before this step.
                invite.contact_email_or_phone,
            )
            parent_user_id = user_row["id"]
            pa_row = await conn.fetchrow(
                """
                INSERT INTO parent_accounts (
                    user_id, display_name, contact_email_or_phone, verified
                )
                VALUES ($1, $2, $3, true)
                RETURNING id
                """,
                parent_user_id,
                invite.contact_email_or_phone,
                invite.contact_email_or_phone,
            )
            parent_account_id = ParentAccountId(pa_row["id"])

        # Consent must come BEFORE link activation so we never have an active
        # link without a matching consent row.
        await consent_repo.record_consent(
            conn,
            parent_account_id=parent_account_id,
            child_user_id=invite.child_user_id,
            consent_type="parent_self_declaration",
            consent_version=consent_version,
            consent_text=CONSENT_TEXT[consent_version],
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await write_audit(
            conn,
            event_type=Events.ONBOARDING_CONSENT_LOGGED,
            actor_parent_account_id=parent_account_id,
            target_type="user",
            target_id=invite.child_user_id,
            payload={"consent_version": consent_version},
        )

        # Link parent ↔ child as active.
        await conn.execute(
            """
            INSERT INTO child_parent_links
                (child_user_id, parent_account_id, status, activated_at)
            VALUES ($1, $2, $3::link_status, now())
            ON CONFLICT (child_user_id, parent_account_id) DO UPDATE SET
                status = EXCLUDED.status,
                activated_at = COALESCE(
                    child_parent_links.activated_at, EXCLUDED.activated_at
                )
            """,
            invite.child_user_id, parent_account_id, LinkStatus.ACTIVE.value,
        )

        # Activate child.
        activated = await users_repo.activate_child(
            conn, user_id=invite.child_user_id
        )

        # Close the invite.
        await pi_repo.mark_approved(conn, invite.id)

        await write_audit(
            conn,
            event_type=Events.ONBOARDING_PARENT_APPROVED,
            actor_parent_account_id=parent_account_id,
            target_type="user",
            target_id=invite.child_user_id,
        )

        return activated, parent_account_id


# ---------- decline ----------

async def decline_child(
    conn: asyncpg.Connection,
    *,
    invite_token: str,
) -> users_repo.UserRow:
    async with conn.transaction():
        invite = await pi_repo.get_by_token(conn, invite_token)
        if invite is None:
            raise NotFoundError("Invite not found")
        if invite.status not in (ParentInviteStatus.PENDING, ParentInviteStatus.VERIFIED):
            raise StateConflictError(
                f"Invite cannot be declined (status={invite.status.value})"
            )

        await pi_repo.mark_declined(conn, invite.id)
        updated = await users_repo.set_onboarding_status(
            conn,
            user_id=invite.child_user_id,
            new_status=OnboardingStatus.DECLINED,
        )

        await write_audit(
            conn,
            event_type=Events.ONBOARDING_PARENT_DECLINED,
            target_type="parent_invite",
            target_id=invite.id,
        )
        return updated
