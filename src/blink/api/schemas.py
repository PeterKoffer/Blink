"""Pydantic request/response models for the API surface.

Rules:
- Never return DB rows directly from handlers; map through one of these.
- Field names are camelCase at the wire, snake_case in Python. Pydantic's
  `alias_generator=to_camel` + `populate_by_name=True` handles both.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from blink.types import (
    AvatarType,
    BillingStatus,
    EphemeralMode,
    FriendRequestStatus,
    FriendshipStatus,
    GroupMemberRole,
    GroupMembershipStatus,
    GroupPlanTier,
    GroupRequestStatus,
    GroupRequestType,
    GroupStatus,
    MessageStatus,
    MessageType,
    OnboardingStatus,
    ParentInviteStatus,
    UserStatus,
    UserType,
)


class _Base(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


# ==============================
# Friends
# ==============================

class CreateFriendRequestBody(_Base):
    target_child_id: UUID


class FriendRequestView(_Base):
    id: UUID
    requester_child_id: UUID
    target_child_id: UUID
    status: FriendRequestStatus
    method: str | None
    created_at: datetime
    reviewed_at: datetime | None = None
    reviewed_by_parent_account_id: UUID | None = None


class FriendshipView(_Base):
    id: UUID
    child_user_id_a: UUID
    child_user_id_b: UUID
    status: FriendshipStatus
    approved_at: datetime
    created_at: datetime


class FriendListItem(_Base):
    """One row in GET /friends — the peer's basic profile + friendship anchor."""
    friendship_id: UUID
    child_user_id: UUID
    display_name: str | None
    avatar_initial: str | None
    approved_at: datetime


# ==============================
# Groups
# ==============================

class CreateGroupBody(_Base):
    name: str = Field(..., min_length=1, max_length=40)
    initial_member_ids: list[UUID] = Field(default_factory=list)


class JoinGroupBody(_Base):
    invite_code: str = Field(..., pattern=r"^GRUPPE-\d{4,6}$")


class InviteToGroupBody(_Base):
    target_child_id: UUID


class GroupMemberView(_Base):
    child_user_id: UUID
    display_name: str | None
    avatar_initial: str | None
    role: GroupMemberRole
    status: GroupMembershipStatus


class GroupView(_Base):
    id: UUID
    name: str
    status: GroupStatus
    created_by_child_id: UUID
    invite_code: str
    active_member_count: int
    pending_member_count: int
    created_at: datetime
    approved_at: datetime | None = None

    # Enriched in list/detail views — null when no active messages exist.
    last_message_at: datetime | None = None
    last_message_preview: str | None = None


class GroupDetailView(GroupView):
    members: list[GroupMemberView]


class GroupListResponse(_Base):
    groups: list[GroupView]


class CreateGroupResponse(_Base):
    group: GroupDetailView
    pending_approval: bool
    request_id: UUID | None = None


class JoinOrInviteResponse(_Base):
    group_id: UUID
    target_child_id: UUID
    membership_status: GroupMembershipStatus
    pending_approval: bool
    request_id: UUID | None = None


# ==============================
# Parent approvals hub
# ==============================

class PendingFriendRequestItem(_Base):
    kind: Literal["friend"] = "friend"
    request_id: UUID
    requester_child_id: UUID
    requester_display_name: str | None
    target_child_id: UUID
    target_display_name: str | None
    method: str | None
    created_at: datetime


class PendingGroupRequestItem(_Base):
    kind: Literal["group"] = "group"
    request_id: UUID
    type: GroupRequestType
    actor_child_id: UUID
    actor_display_name: str | None
    group_id: UUID | None
    group_name: str | None
    target_child_id: UUID | None
    target_display_name: str | None
    requested_name: str | None
    created_at: datetime


class PendingRequestsResponse(_Base):
    friend_requests: list[PendingFriendRequestItem]
    group_requests: list[PendingGroupRequestItem]


class ReviewResult(_Base):
    request_id: UUID
    status: GroupRequestStatus | FriendRequestStatus
    reviewed_at: datetime


# ==============================
# Messages
# ==============================

class CreateMessageBody(_Base):
    group_id: UUID | None = None
    chat_id: UUID | None = None
    type: MessageType
    text: str | None = None
    media_id: UUID | None = None
    client_message_id: str = Field(..., min_length=1, max_length=100)
    ephemeral_mode: EphemeralMode
    ttl_seconds: int = Field(..., ge=1, le=604800)


class MessageView(_Base):
    id: UUID
    sender_id: UUID
    sender_display_name: str | None = None
    sender_avatar_initial: str | None = None
    group_id: UUID | None = None
    chat_id: UUID | None = None
    type: MessageType
    text: str | None = None
    media_id: UUID | None = None
    client_message_id: str
    ephemeral_mode: EphemeralMode
    ttl_seconds: int
    created_at: datetime
    expires_at: datetime
    status: MessageStatus


class MessageListResponse(_Base):
    messages: list[MessageView]


# ==============================
# Media
# ==============================

class CreateMediaUploadUrlBody(_Base):
    group_id: UUID | None = None
    chat_id: UUID | None = None
    mime: str = Field(..., min_length=1, max_length=50)
    size: int = Field(..., ge=1, le=1_048_576)
    width: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)


class MediaUploadUrlResponse(_Base):
    media_id: UUID
    upload_url: str
    method: str = "PUT"
    headers: dict[str, str]
    max_size: int
    expires_in_seconds: int


class ConfirmMediaBody(_Base):
    media_id: UUID


class MediaConfirmResponse(_Base):
    ok: bool = True
    media_id: UUID
    upload_status: str
    access_status: str


class MediaReadUrlResponse(_Base):
    media_id: UUID
    url: str
    expires_in_seconds: int


# ==============================
# Billing
# ==============================

class BillingSummaryResponse(_Base):
    status: BillingStatus
    current_tier: GroupPlanTier
    current_cap: int
    next_tier: GroupPlanTier | None = None
    next_tier_cap: int | None = None
    active_member_count: int
    pending_member_count: int
    total_member_count: int
    group_full_on_current_tier: bool
    at_hard_cap: bool
    activated_at: datetime | None = None
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None


class ActivateGroupBody(_Base):
    tier: GroupPlanTier


class UpgradeGroupBody(_Base):
    tier: GroupPlanTier


class BillingStateResponse(_Base):
    group_id: UUID
    status: BillingStatus
    current_tier: GroupPlanTier
    activated_at: datetime | None = None
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None


# ==============================
# Onboarding
# ==============================

class CreateChildProfileBody(_Base):
    display_name: str = Field(..., min_length=1, max_length=24)
    avatar_type: AvatarType
    avatar_value: str = Field(..., min_length=1, max_length=20)
    avatar_color: str = Field(..., pattern=r"^#[0-9a-fA-F]{6}$")


class ChildProfileResponse(_Base):
    user_id: UUID
    display_name: str
    avatar_type: AvatarType
    avatar_value: str
    avatar_color: str
    blink_code: str
    onboarding_status: OnboardingStatus


class StartParentInviteBody(_Base):
    child_user_id: UUID
    contact: str = Field(..., min_length=3, max_length=200)


class ParentInviteResponse(_Base):
    invite_id: UUID
    child_user_id: UUID
    status: ParentInviteStatus
    expires_at: datetime
    # invite_token and otp are NEVER returned in production. In dev-bypass
    # they're included so the single-device prototype can test the full
    # flow without a real email/SMS. Gate on BLINK_DEV_BYPASS_AUTH.
    invite_token: str | None = None
    otp: str | None = None


class InvitePreviewResponse(_Base):
    child_display_name: str | None
    child_avatar_type: AvatarType | None = None
    child_avatar_value: str | None = None
    child_avatar_color: str | None = None
    contact_masked: str
    status: ParentInviteStatus
    expires_at: datetime


class VerifyParentBody(_Base):
    invite_token: str
    otp: str = Field(..., min_length=4, max_length=10)


class ApproveChildBody(_Base):
    invite_token: str
    consent_accepted: bool
    consent_version: str


class DeclineChildBody(_Base):
    invite_token: str


# ==============================
# /me
# ==============================

class MeLinkedChild(_Base):
    user_id: UUID
    display_name: str | None
    avatar_type: AvatarType | None = None
    avatar_value: str | None = None
    avatar_color: str | None = None
    onboarding_status: OnboardingStatus | None = None
    status: UserStatus


class MeResponse(_Base):
    user_id: UUID
    user_type: UserType
    status: UserStatus
    display_name: str | None
    avatar_type: AvatarType | None = None
    avatar_value: str | None = None
    avatar_color: str | None = None
    blink_code: str | None = None
    onboarding_status: OnboardingStatus | None = None

    # Parent-only fields
    parent_account_id: UUID | None = None
    parent_verified: bool | None = None
    linked_children: list[MeLinkedChild] | None = None
