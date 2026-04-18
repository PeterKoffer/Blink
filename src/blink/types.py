"""Domain types, enums, and IDs.

Mirrors the SQL enums defined in migrations/. Keep these in sync: if you add
a value here, add a matching ALTER TYPE migration, and vice versa.
"""
from __future__ import annotations

from enum import Enum
from typing import NewType
from uuid import UUID


# --- Typed IDs ---
# These are UUID aliases — cheap type-level documentation, runtime is still UUID.
UserId = NewType("UserId", UUID)
ParentAccountId = NewType("ParentAccountId", UUID)
GroupId = NewType("GroupId", UUID)
FriendshipId = NewType("FriendshipId", UUID)
FriendRequestId = NewType("FriendRequestId", UUID)
GroupRequestId = NewType("GroupRequestId", UUID)
GroupMembershipId = NewType("GroupMembershipId", UUID)
ChildParentLinkId = NewType("ChildParentLinkId", UUID)
MessageId = NewType("MessageId", UUID)
MediaId = NewType("MediaId", UUID)
ParentInviteId = NewType("ParentInviteId", UUID)
ConsentRecordId = NewType("ConsentRecordId", UUID)


# --- Enums ---

class UserType(str, Enum):
    CHILD = "child"
    PARENT = "parent"
    PENDING = "pending"  # user created but not yet activated as child or parent


class UserStatus(str, Enum):
    PENDING_ACTIVATION = "pending_activation"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DEACTIVATED = "deactivated"


class LinkStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    REVOKED = "revoked"


class FriendshipStatus(str, Enum):
    ACTIVE = "active"
    BLOCKED = "blocked"
    REMOVED = "removed"


class FriendRequestStatus(str, Enum):
    PENDING_PARENT = "pending_parent"
    APPROVED = "approved"
    DECLINED = "declined"
    CANCELED = "canceled"


class GroupStatus(str, Enum):
    PENDING_PARENT = "pending_parent"
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class GroupMembershipStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    DECLINED = "declined"
    REMOVED = "removed"


class GroupMemberRole(str, Enum):
    MEMBER = "member"
    ADMIN = "admin"
    CREATOR = "creator"


class GroupRequestType(str, Enum):
    CREATE_GROUP = "create_group"
    JOIN_GROUP = "join_group"
    INVITE_TO_GROUP = "invite_to_group"


class GroupRequestStatus(str, Enum):
    PENDING_PARENT = "pending_parent"
    APPROVED = "approved"
    DECLINED = "declined"
    CANCELED = "canceled"


# --- Onboarding / adult verification ---

class AvatarType(str, Enum):
    EMOJI = "emoji"
    ICON = "icon"
    SHAPE = "shape"
    INITIAL = "initial"


class OnboardingStatus(str, Enum):
    PROFILE_PENDING = "profile_pending"
    PARENT_INVITED = "parent_invited"
    PARENT_VERIFIED = "parent_verified"
    ACTIVE = "active"
    DECLINED = "declined"


class ParentInviteStatus(str, Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    APPROVED = "approved"
    DECLINED = "declined"
    EXPIRED = "expired"


# Single canonical consent text per version. Changing the text = new version.
CONSENT_VERSION = "1.0"
CONSENT_TEXT: dict[str, str] = {
    "1.0": (
        "Jeg bekræfter at jeg er forælder eller værge til barnet, "
        "eller at jeg har tilladelse fra forælder/værge til at godkende "
        "Blink for dem. Jeg er over 18 år."
    ),
}

# OTP + invite expiration bounds (read from settings at runtime in service).
OTP_MAX_ATTEMPTS = 5
INVITE_EXPIRES_MINUTES = 60


# --- Messaging ---

class MessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"  # DB-only in v1; API rejects until Sprint 4


class EphemeralMode(str, Enum):
    TIMER = "timer"
    AFTER_READ = "after_read"  # DB accepts; API rejects in v1 (fase 2)


class MessageStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    DELETED = "deleted"


# Tight API bounds (DB allows wider as safety net).
TEXT_MAX_LEN = 1000
TTL_MIN_SECONDS = 1
TTL_MAX_SECONDS = 604800  # 7 days


# --- Media ---

class MediaUploadStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"


class MediaAccessStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    DELETED = "deleted"


class MediaUsageStatus(str, Enum):
    UNUSED = "unused"
    ATTACHED = "attached"


# Per project_blink_media.md v1
MEDIA_MIME_WHITELIST: frozenset[str] = frozenset({"image/jpeg", "image/webp"})
MEDIA_MAX_SIZE_BYTES = 1_048_576  # 1 MB
MEDIA_DEFAULT_RETENTION_SECONDS = 7 * 24 * 3600  # 7 days
MEDIA_PUT_URL_TTL_SECONDS = 5 * 60  # 5 min
MEDIA_GET_URL_TTL_SECONDS = 60  # 60 sec


# --- Pricing tier (mirrors project_blink_pricing.md) ---
# Member caps are inclusive upper bounds per tier.

class GroupPlanTier(str, Enum):
    LILLE = "lille"      # 0–10
    NORMAL = "normal"    # 11–30
    STOR = "stor"        # 31–50


class BillingStatus(str, Enum):
    INACTIVE = "inactive"
    ACTIVE = "active"
    GRACE = "grace"
    CANCELED = "canceled"
    UNPAID = "unpaid"


GroupBillingStateId = NewType("GroupBillingStateId", UUID)


TIER_MEMBER_CAPS: dict[GroupPlanTier, int] = {
    GroupPlanTier.LILLE: 10,
    GroupPlanTier.NORMAL: 30,
    GroupPlanTier.STOR: 50,
}

# Hard cap across all tiers in v1. Also the value used as default max_group_members.
HARD_MAX_GROUP_MEMBERS = 50
