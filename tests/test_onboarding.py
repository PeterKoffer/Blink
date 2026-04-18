"""Onboarding service + approval flow end-to-end."""
from __future__ import annotations

import pytest

from blink.errors import (
    NotFoundError,
    StateConflictError,
    ValidationError,
)
from blink.onboarding.adapters import NullOtpAdapter
from blink.onboarding.codes import generate_otp, hash_otp
from blink.repos import consent as consent_repo
from blink.repos import parent_invites as pi_repo
from blink.repos import users as users_repo
from blink.services import onboarding_service
from blink.types import (
    CONSENT_VERSION,
    AvatarType,
    OnboardingStatus,
    ParentInviteStatus,
    UserStatus,
)


pytestmark = pytest.mark.asyncio


async def _make_child(conn):
    return await onboarding_service.create_child_profile(
        conn,
        display_name="Sofie",
        avatar_type=AvatarType.EMOJI,
        avatar_value="🦊",
        avatar_color="#FF7A59",
    )


# ------------------------- child profile -------------------------

async def test_child_profile_is_created_in_pending_state(conn):
    row = await _make_child(conn)
    assert row.display_name == "Sofie"
    assert row.avatar_type == AvatarType.EMOJI
    assert row.avatar_color == "#FF7A59"
    assert row.onboarding_status == OnboardingStatus.PROFILE_PENDING
    assert row.status == UserStatus.PENDING_ACTIVATION
    assert row.blink_code is not None
    assert row.blink_code.startswith("BLINK-")


async def test_child_profile_rejects_blank_display_name(conn):
    with pytest.raises(ValidationError):
        await onboarding_service.create_child_profile(
            conn,
            display_name="   ",
            avatar_type=AvatarType.EMOJI,
            avatar_value="🦊",
            avatar_color="#FF7A59",
        )


async def test_child_profile_rejects_bad_color(conn):
    with pytest.raises(ValidationError):
        await onboarding_service.create_child_profile(
            conn,
            display_name="Sofie",
            avatar_type=AvatarType.EMOJI,
            avatar_value="🦊",
            avatar_color="red",  # not hex
        )


async def test_blink_code_is_unique_across_children(conn):
    a = await _make_child(conn)
    b = await onboarding_service.create_child_profile(
        conn,
        display_name="Noah",
        avatar_type=AvatarType.ICON,
        avatar_value="star",
        avatar_color="#4A8BF0",
    )
    assert a.blink_code != b.blink_code


# ------------------------- parent invite -------------------------

async def test_parent_invite_creates_pending_row(conn):
    child = await _make_child(conn)
    adapter = NullOtpAdapter()
    invite = await onboarding_service.start_parent_invite(
        conn, adapter,
        child_user_id=child.id,
        contact="mor@example.dk",
    )
    assert invite.status == ParentInviteStatus.PENDING
    assert invite.child_user_id == child.id
    assert invite.contact_email_or_phone == "mor@example.dk"

    # Child onboarding status advanced.
    fresh = await users_repo.get_by_id(conn, child.id)
    assert fresh is not None
    assert fresh.onboarding_status == OnboardingStatus.PARENT_INVITED


async def test_second_invite_supersedes_first(conn):
    child = await _make_child(conn)
    adapter = NullOtpAdapter()
    first = await onboarding_service.start_parent_invite(
        conn, adapter,
        child_user_id=child.id,
        contact="mor@example.dk",
    )
    second = await onboarding_service.start_parent_invite(
        conn, adapter,
        child_user_id=child.id,
        contact="mor2@example.dk",
    )
    assert first.id != second.id

    # The first row should have flipped to declined.
    stale = await pi_repo.get(conn, first.id)
    assert stale is not None
    assert stale.status == ParentInviteStatus.DECLINED


# ------------------------- verify -------------------------

async def test_verify_with_correct_otp_succeeds(conn):
    child = await _make_child(conn)
    # Create an invite with a known OTP by talking to the repo directly.
    from datetime import datetime, timedelta, timezone
    otp = "123456"
    invite = await pi_repo.insert_pending(
        conn,
        child_user_id=child.id,
        contact="mor@example.dk",
        invite_token="t" * 40,
        otp_code_hash=hash_otp(otp),
        expires_at=datetime.now(tz=timezone.utc) + timedelta(minutes=30),
    )
    # Must also bump child status, mirroring start_parent_invite()
    await users_repo.set_onboarding_status(
        conn, user_id=child.id, new_status=OnboardingStatus.PARENT_INVITED,
    )

    verified = await onboarding_service.verify_parent_invite(
        conn, invite_token=invite.invite_token, otp=otp,
    )
    assert verified.status == ParentInviteStatus.VERIFIED
    assert verified.verified_at is not None

    fresh_child = await users_repo.get_by_id(conn, child.id)
    assert fresh_child is not None
    assert fresh_child.onboarding_status == OnboardingStatus.PARENT_VERIFIED


async def test_verify_with_wrong_otp_fails(conn):
    child = await _make_child(conn)
    from datetime import datetime, timedelta, timezone
    invite = await pi_repo.insert_pending(
        conn,
        child_user_id=child.id,
        contact="mor@example.dk",
        invite_token="w" * 40,
        otp_code_hash=hash_otp("123456"),
        expires_at=datetime.now(tz=timezone.utc) + timedelta(minutes=30),
    )

    with pytest.raises(ValidationError):
        await onboarding_service.verify_parent_invite(
            conn, invite_token=invite.invite_token, otp="999999",
        )
    # Attempts counter went up.
    fresh = await pi_repo.get(conn, invite.id)
    assert fresh is not None
    assert fresh.otp_attempts == 1
    assert fresh.status == ParentInviteStatus.PENDING


async def test_verify_fails_after_expiration(conn):
    child = await _make_child(conn)
    from datetime import datetime, timedelta, timezone
    # Backdated expiry.
    past = datetime.now(tz=timezone.utc) - timedelta(seconds=1)
    # DB constraint requires expires_at > created_at, so set created_at
    # further back by directly inserting.
    await conn.execute(
        """
        INSERT INTO parent_invites (
            child_user_id, contact_email_or_phone, invite_token,
            otp_code_hash, expires_at, created_at
        )
        VALUES ($1, $2, $3, $4, $5, $5 - interval '1 minute')
        """,
        child.id, "mor@example.dk", "x" * 40, hash_otp("123456"), past,
    )
    invite = await pi_repo.get_by_token(conn, "x" * 40)
    assert invite is not None

    with pytest.raises(StateConflictError):
        await onboarding_service.verify_parent_invite(
            conn, invite_token=invite.invite_token, otp="123456",
        )


# ------------------------- approve -------------------------

async def _prepare_verified_invite(conn):
    """Shortcut: make a child and an invite that's already verified."""
    child = await _make_child(conn)
    from datetime import datetime, timedelta, timezone
    otp = "424242"
    invite = await pi_repo.insert_pending(
        conn,
        child_user_id=child.id,
        contact="mor@example.dk",
        invite_token="v" * 40,
        otp_code_hash=hash_otp(otp),
        expires_at=datetime.now(tz=timezone.utc) + timedelta(minutes=30),
    )
    await users_repo.set_onboarding_status(
        conn, user_id=child.id, new_status=OnboardingStatus.PARENT_INVITED,
    )
    await onboarding_service.verify_parent_invite(
        conn, invite_token=invite.invite_token, otp=otp,
    )
    return child, invite


async def test_approve_without_consent_is_rejected(conn):
    _child, invite = await _prepare_verified_invite(conn)
    with pytest.raises(ValidationError):
        await onboarding_service.approve_child(
            conn,
            invite_token=invite.invite_token,
            consent_accepted=False,
            consent_version=CONSENT_VERSION,
        )


async def test_approve_with_unknown_consent_version_is_rejected(conn):
    _child, invite = await _prepare_verified_invite(conn)
    with pytest.raises(ValidationError):
        await onboarding_service.approve_child(
            conn,
            invite_token=invite.invite_token,
            consent_accepted=True,
            consent_version="9999.9",
        )


async def test_approve_activates_child_and_logs_consent(conn):
    child, invite = await _prepare_verified_invite(conn)

    activated, parent_account_id = await onboarding_service.approve_child(
        conn,
        invite_token=invite.invite_token,
        consent_accepted=True,
        consent_version=CONSENT_VERSION,
        ip_address="127.0.0.1",
        user_agent="pytest",
    )

    # Child flipped to active.
    assert activated.status == UserStatus.ACTIVE
    assert activated.onboarding_status == OnboardingStatus.ACTIVE

    # Consent row written.
    consents = await consent_repo.list_for_child(conn, child.id)
    assert len(consents) == 1
    c = consents[0]
    assert c.parent_account_id == parent_account_id
    assert c.consent_type == "parent_self_declaration"
    assert c.consent_version == CONSENT_VERSION
    assert c.ip_address == "127.0.0.1"

    # child_parent_links row is active.
    link_row = await conn.fetchrow(
        """
        SELECT status::text AS status, activated_at
        FROM child_parent_links
        WHERE child_user_id = $1 AND parent_account_id = $2
        """,
        child.id, parent_account_id,
    )
    assert link_row is not None
    assert link_row["status"] == "active"
    assert link_row["activated_at"] is not None

    # Invite itself is closed.
    fresh_invite = await pi_repo.get_by_token(conn, invite.invite_token)
    assert fresh_invite is not None
    assert fresh_invite.status == ParentInviteStatus.APPROVED


async def test_approve_before_verify_is_rejected(conn):
    """Pending (not yet verified) invite cannot jump straight to approval."""
    child = await _make_child(conn)
    from datetime import datetime, timedelta, timezone
    invite = await pi_repo.insert_pending(
        conn,
        child_user_id=child.id,
        contact="mor@example.dk",
        invite_token="p" * 40,
        otp_code_hash=hash_otp("123456"),
        expires_at=datetime.now(tz=timezone.utc) + timedelta(minutes=30),
    )

    with pytest.raises(StateConflictError):
        await onboarding_service.approve_child(
            conn,
            invite_token=invite.invite_token,
            consent_accepted=True,
            consent_version=CONSENT_VERSION,
        )


# ------------------------- decline -------------------------

async def test_decline_moves_child_to_declined(conn):
    child = await _make_child(conn)
    adapter = NullOtpAdapter()
    invite = await onboarding_service.start_parent_invite(
        conn, adapter, child_user_id=child.id, contact="mor@example.dk",
    )

    declined_child = await onboarding_service.decline_child(
        conn, invite_token=invite.invite_token,
    )
    assert declined_child.onboarding_status == OnboardingStatus.DECLINED

    fresh_invite = await pi_repo.get_by_token(conn, invite.invite_token)
    assert fresh_invite is not None
    assert fresh_invite.status == ParentInviteStatus.DECLINED


# ------------------------- not-found -------------------------

async def test_verify_unknown_token_returns_not_found(conn):
    with pytest.raises(NotFoundError):
        await onboarding_service.verify_parent_invite(
            conn, invite_token="does-not-exist-token-" + "x" * 30, otp="000000",
        )
