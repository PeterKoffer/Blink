"""Append-only audit event logging.

Services call `write_audit` on every meaningful state transition. The event
row is written inside the calling transaction, so it commits/rolls back with
the state change itself (no orphan audits).
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg

from blink.types import ParentAccountId, UserId


async def write_audit(
    conn: asyncpg.Connection,
    *,
    event_type: str,
    actor_user_id: UserId | None = None,
    actor_parent_account_id: ParentAccountId | None = None,
    target_type: str | None = None,
    target_id: UUID | str | None = None,
    payload: dict[str, Any] | None = None,
) -> int:
    """Insert an audit_events row. Returns the row id."""
    row = await conn.fetchrow(
        """
        INSERT INTO audit_events (
            event_type,
            actor_user_id,
            actor_parent_account_id,
            target_type,
            target_id,
            payload
        ) VALUES ($1, $2, $3, $4, $5, $6::jsonb)
        RETURNING id
        """,
        event_type,
        actor_user_id,
        actor_parent_account_id,
        target_type,
        str(target_id) if target_id is not None else None,
        _to_jsonb(payload or {}),
    )
    return row["id"]


def _to_jsonb(payload: dict[str, Any]) -> str:
    import json
    return json.dumps(payload, default=_json_default)


def _json_default(obj: Any) -> Any:
    if isinstance(obj, UUID):
        return str(obj)
    # datetimes/enums handled via str() for audit purposes
    return str(obj)


# Canonical event type names. Keep here so routes/services never use raw strings.
class Events:
    FRIEND_REQUEST_CREATED = "friend_request.created"
    FRIEND_REQUEST_APPROVED = "friend_request.approved"
    FRIEND_REQUEST_DECLINED = "friend_request.declined"
    FRIENDSHIP_ACTIVATED = "friendship.activated"

    GROUP_CREATED = "group.created"
    GROUP_CREATE_REQUESTED = "group.create_requested"
    GROUP_CREATE_APPROVED = "group.create_approved"
    GROUP_CREATE_DECLINED = "group.create_declined"

    GROUP_JOIN_REQUESTED = "group.join_requested"
    GROUP_JOIN_APPROVED = "group.join_approved"
    GROUP_JOIN_DECLINED = "group.join_declined"

    GROUP_INVITE_REQUESTED = "group.invite_requested"
    GROUP_INVITE_APPROVED = "group.invite_approved"
    GROUP_INVITE_DECLINED = "group.invite_declined"

    GROUP_MEMBERSHIP_ACTIVATED = "group.membership_activated"

    MESSAGE_CREATED = "message.created"
    MESSAGES_EXPIRED = "message.batch_expired"

    MEDIA_UPLOAD_REQUESTED = "media.upload_requested"
    MEDIA_UPLOAD_CONFIRMED = "media.upload_confirmed"
    MEDIA_READ_URL_ISSUED = "media.read_url_issued"
    MEDIA_ATTACHED = "media.attached"
    MEDIA_CASCADE_EXPIRED = "media.cascade_expired"
    MEDIA_MARKED_DELETED = "media.marked_deleted"

    BILLING_ACTIVATED = "billing.activated"
    BILLING_UPGRADED = "billing.upgraded"
    BILLING_DOWNGRADED = "billing.downgraded"  # reserved; not used in v1
    BILLING_CANCELED = "billing.canceled"
    BILLING_TIER_MISMATCH = "billing.tier_mismatch"

    ONBOARDING_PROFILE_CREATED = "onboarding.profile_created"
    ONBOARDING_PARENT_INVITED = "onboarding.parent_invited"
    ONBOARDING_PARENT_VERIFIED = "onboarding.parent_verified"
    ONBOARDING_PARENT_APPROVED = "onboarding.parent_approved"
    ONBOARDING_PARENT_DECLINED = "onboarding.parent_declined"
    ONBOARDING_CONSENT_LOGGED = "onboarding.consent_logged"
    ONBOARDING_OTP_FAILED = "onboarding.otp_failed"
