"""Parent policy resolution — backend source of truth.

Every gated action (create group, join group, invite, send image) must call
`resolve_parent_policy(conn, child_user_id)` and respect the result.

Design rules:
- If no row exists for a child yet, return sane defaults (not "deny all" —
  the product assumes "Balanceret" safety level by default).
- Defaults mirror the values in migrations/004_parent_policies.sql so a
  freshly created row and a missing row behave identically.
- Policy is per-child; a child's linked parents share one policy row.
- Callers MUST NOT rely on the DB row existing. Always go through this helper.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import asyncpg

from blink.errors import PolicyBlockedError
from blink.types import ParentAccountId, UserId, HARD_MAX_GROUP_MEMBERS


# Defaults match migrations/004_parent_policies.sql DEFAULTs exactly.
# If you change either, change both.
DEFAULT_MAY_CREATE_GROUPS = True
DEFAULT_REQUIRE_GROUP_APPROVAL = True
DEFAULT_MAY_JOIN_GROUPS = True
DEFAULT_REQUIRE_GROUP_INVITE_APPROVAL = True
DEFAULT_MAX_GROUP_MEMBERS = 20
DEFAULT_MAY_SEND_IMAGES = True


@dataclass(frozen=True, slots=True)
class ParentPolicy:
    child_user_id: UserId

    may_create_groups: bool
    require_group_approval: bool
    may_join_groups: bool
    require_group_invite_approval: bool
    max_group_members: int
    may_send_images: bool

    # Metadata — may be None when returning synthetic defaults.
    updated_at: datetime | None = None
    is_default: bool = field(default=False)

    # --- Convenience guards. These raise PolicyBlockedError with the exact
    # policy key so the API layer can surface a structured error. ---

    def ensure_can_create_groups(self) -> None:
        if not self.may_create_groups:
            raise PolicyBlockedError("may_create_groups")

    def ensure_can_join_groups(self) -> None:
        if not self.may_join_groups:
            raise PolicyBlockedError("may_join_groups")

    def ensure_can_send_images(self) -> None:
        if not self.may_send_images:
            raise PolicyBlockedError("may_send_images")

    def ensure_group_size_ok(self, proposed_member_count: int) -> None:
        """The caller knows the resulting active-member count; we verify it."""
        if proposed_member_count > self.max_group_members:
            raise PolicyBlockedError(
                "max_group_members",
                message=(
                    f"Group would exceed parent-set max ({self.max_group_members})"
                ),
            )
        if proposed_member_count > HARD_MAX_GROUP_MEMBERS:
            raise PolicyBlockedError(
                "max_group_members",
                message=f"Exceeds hard cap of {HARD_MAX_GROUP_MEMBERS} members",
            )


def default_policy(child_user_id: UserId) -> ParentPolicy:
    return ParentPolicy(
        child_user_id=child_user_id,
        may_create_groups=DEFAULT_MAY_CREATE_GROUPS,
        require_group_approval=DEFAULT_REQUIRE_GROUP_APPROVAL,
        may_join_groups=DEFAULT_MAY_JOIN_GROUPS,
        require_group_invite_approval=DEFAULT_REQUIRE_GROUP_INVITE_APPROVAL,
        max_group_members=DEFAULT_MAX_GROUP_MEMBERS,
        may_send_images=DEFAULT_MAY_SEND_IMAGES,
        updated_at=None,
        is_default=True,
    )


async def resolve_parent_policy(
    conn: asyncpg.Connection,
    child_user_id: UserId,
) -> ParentPolicy:
    """Return the current policy for a child, or synthetic defaults if no row."""
    row = await conn.fetchrow(
        """
        SELECT may_create_groups,
               require_group_approval,
               may_join_groups,
               require_group_invite_approval,
               max_group_members,
               may_send_images,
               updated_at
        FROM parent_policies
        WHERE child_user_id = $1
        """,
        child_user_id,
    )
    if row is None:
        return default_policy(child_user_id)

    return ParentPolicy(
        child_user_id=child_user_id,
        may_create_groups=row["may_create_groups"],
        require_group_approval=row["require_group_approval"],
        may_join_groups=row["may_join_groups"],
        require_group_invite_approval=row["require_group_invite_approval"],
        max_group_members=row["max_group_members"],
        may_send_images=row["may_send_images"],
        updated_at=row["updated_at"],
        is_default=False,
    )


async def upsert_parent_policy(
    conn: asyncpg.Connection,
    *,
    child_user_id: UserId,
    updated_by: ParentAccountId | None,
    may_create_groups: bool | None = None,
    require_group_approval: bool | None = None,
    may_join_groups: bool | None = None,
    require_group_invite_approval: bool | None = None,
    max_group_members: int | None = None,
    may_send_images: bool | None = None,
) -> ParentPolicy:
    """Upsert — create row with defaults, then overlay any provided values.

    Only the given fields are changed; missing arguments leave existing
    values alone. On first write, missing arguments take their DEFAULTs.
    """
    # Start from current state (or synthetic defaults) so we never accidentally
    # reset a field the caller didn't touch.
    current = await resolve_parent_policy(conn, child_user_id)

    new = {
        "may_create_groups":              may_create_groups              if may_create_groups              is not None else current.may_create_groups,
        "require_group_approval":         require_group_approval         if require_group_approval         is not None else current.require_group_approval,
        "may_join_groups":                may_join_groups                if may_join_groups                is not None else current.may_join_groups,
        "require_group_invite_approval":  require_group_invite_approval  if require_group_invite_approval  is not None else current.require_group_invite_approval,
        "max_group_members":              max_group_members              if max_group_members              is not None else current.max_group_members,
        "may_send_images":                may_send_images                if may_send_images                is not None else current.may_send_images,
    }

    if not (2 <= new["max_group_members"] <= HARD_MAX_GROUP_MEMBERS):
        raise ValueError(
            f"max_group_members must be between 2 and {HARD_MAX_GROUP_MEMBERS}"
        )

    await conn.execute(
        """
        INSERT INTO parent_policies (
            child_user_id,
            may_create_groups,
            require_group_approval,
            may_join_groups,
            require_group_invite_approval,
            max_group_members,
            may_send_images,
            updated_by_parent_account_id
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        ON CONFLICT (child_user_id) DO UPDATE SET
            may_create_groups             = EXCLUDED.may_create_groups,
            require_group_approval        = EXCLUDED.require_group_approval,
            may_join_groups               = EXCLUDED.may_join_groups,
            require_group_invite_approval = EXCLUDED.require_group_invite_approval,
            max_group_members             = EXCLUDED.max_group_members,
            may_send_images               = EXCLUDED.may_send_images,
            updated_by_parent_account_id  = EXCLUDED.updated_by_parent_account_id
        """,
        child_user_id,
        new["may_create_groups"],
        new["require_group_approval"],
        new["may_join_groups"],
        new["require_group_invite_approval"],
        new["max_group_members"],
        new["may_send_images"],
        updated_by,
    )

    return await resolve_parent_policy(conn, child_user_id)
