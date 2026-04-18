"""Groups + group_memberships data access."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import asyncpg

from blink.types import (
    GroupId,
    GroupMemberRole,
    GroupMembershipId,
    GroupMembershipStatus,
    GroupPlanTier,
    GroupStatus,
    UserId,
)


@dataclass(frozen=True, slots=True)
class GroupRow:
    id: GroupId
    name: str
    created_by_child_id: UserId
    status: GroupStatus
    member_cap_tier: GroupPlanTier       # hot-path cap reference
    invite_code: str
    created_at: datetime
    approved_at: datetime | None


@dataclass(frozen=True, slots=True)
class MembershipRow:
    id: GroupMembershipId
    group_id: GroupId
    child_user_id: UserId
    role: GroupMemberRole
    status: GroupMembershipStatus
    created_at: datetime
    activated_at: datetime | None


def _row_to_group(r: asyncpg.Record) -> GroupRow:
    return GroupRow(
        id=GroupId(r["id"]),
        name=r["name"],
        created_by_child_id=UserId(r["created_by_child_id"]),
        status=GroupStatus(r["status"]),
        member_cap_tier=GroupPlanTier(r["member_cap_tier"]),
        invite_code=r["invite_code"],
        created_at=r["created_at"],
        approved_at=r["approved_at"],
    )


def _row_to_membership(r: asyncpg.Record) -> MembershipRow:
    return MembershipRow(
        id=GroupMembershipId(r["id"]),
        group_id=GroupId(r["group_id"]),
        child_user_id=UserId(r["child_user_id"]),
        role=GroupMemberRole(r["role"]),
        status=GroupMembershipStatus(r["status"]),
        created_at=r["created_at"],
        activated_at=r["activated_at"],
    )


_GROUP_COLS = """
    id, name, created_by_child_id, status::text AS status,
    member_cap_tier::text AS member_cap_tier,
    invite_code, created_at, approved_at
"""

_MEMBERSHIP_COLS = """
    id, group_id, child_user_id, role::text AS role,
    status::text AS status, created_at, activated_at
"""


# --- groups ---

async def insert_group(
    conn: asyncpg.Connection,
    *,
    name: str,
    created_by: UserId,
    status: GroupStatus,
    invite_code: str,
) -> GroupRow:
    approved_at_clause = "now()" if status == GroupStatus.ACTIVE else "NULL"
    r = await conn.fetchrow(
        f"""
        INSERT INTO groups (name, created_by_child_id, status, invite_code, approved_at)
        VALUES ($1, $2, $3::group_status, $4, {approved_at_clause})
        RETURNING {_GROUP_COLS}
        """,
        name, created_by, status.value, invite_code,
    )
    return _row_to_group(r)


async def get_group(conn: asyncpg.Connection, group_id: GroupId) -> GroupRow | None:
    r = await conn.fetchrow(f"SELECT {_GROUP_COLS} FROM groups WHERE id = $1", group_id)
    return _row_to_group(r) if r else None


async def get_group_by_invite_code(conn: asyncpg.Connection, code: str) -> GroupRow | None:
    r = await conn.fetchrow(
        f"SELECT {_GROUP_COLS} FROM groups WHERE invite_code = $1",
        code,
    )
    return _row_to_group(r) if r else None


async def activate_group(conn: asyncpg.Connection, group_id: GroupId) -> GroupRow:
    r = await conn.fetchrow(
        f"""
        UPDATE groups
           SET status = 'active', approved_at = now()
         WHERE id = $1 AND status = 'pending_parent'
        RETURNING {_GROUP_COLS}
        """,
        group_id,
    )
    if r is None:
        raise RuntimeError("activate_group hit zero rows (wrong state?)")
    return _row_to_group(r)


async def soft_delete_group(conn: asyncpg.Connection, group_id: GroupId) -> None:
    await conn.execute("UPDATE groups SET status = 'deleted' WHERE id = $1", group_id)


async def set_member_cap_tier(
    conn: asyncpg.Connection,
    *,
    group_id: GroupId,
    tier: "GroupPlanTier",
) -> GroupRow:
    """Update the cap tier on a group. Called by the billing service inside
    the same transaction as a billing_state update."""
    r = await conn.fetchrow(
        f"""
        UPDATE groups
           SET member_cap_tier = $2::group_plan_tier
         WHERE id = $1
        RETURNING {_GROUP_COLS}
        """,
        group_id, tier.value,
    )
    if r is None:
        raise RuntimeError("set_member_cap_tier hit zero rows")
    return _row_to_group(r)


# --- group_memberships ---

async def insert_membership(
    conn: asyncpg.Connection,
    *,
    group_id: GroupId,
    child_user_id: UserId,
    role: GroupMemberRole,
    status: GroupMembershipStatus,
) -> MembershipRow:
    activated_clause = "now()" if status == GroupMembershipStatus.ACTIVE else "NULL"
    r = await conn.fetchrow(
        f"""
        INSERT INTO group_memberships (group_id, child_user_id, role, status, activated_at)
        VALUES ($1, $2, $3::group_member_role, $4::group_membership_status, {activated_clause})
        RETURNING {_MEMBERSHIP_COLS}
        """,
        group_id, child_user_id, role.value, status.value,
    )
    return _row_to_membership(r)


async def get_membership(
    conn: asyncpg.Connection,
    group_id: GroupId,
    child_user_id: UserId,
) -> MembershipRow | None:
    r = await conn.fetchrow(
        f"""
        SELECT {_MEMBERSHIP_COLS}
        FROM group_memberships
        WHERE group_id = $1 AND child_user_id = $2
        """,
        group_id, child_user_id,
    )
    return _row_to_membership(r) if r else None


async def list_memberships_for_group(
    conn: asyncpg.Connection,
    group_id: GroupId,
    *,
    include_terminal: bool = False,
) -> list[MembershipRow]:
    if include_terminal:
        rows = await conn.fetch(
            f"SELECT {_MEMBERSHIP_COLS} FROM group_memberships WHERE group_id = $1 ORDER BY created_at",
            group_id,
        )
    else:
        rows = await conn.fetch(
            f"""
            SELECT {_MEMBERSHIP_COLS} FROM group_memberships
            WHERE group_id = $1 AND status IN ('active', 'pending')
            ORDER BY created_at
            """,
            group_id,
        )
    return [_row_to_membership(r) for r in rows]


async def count_members(conn: asyncpg.Connection, group_id: GroupId) -> tuple[int, int]:
    """Return (active_count, pending_count) for membership-cap decisions."""
    r = await conn.fetchrow(
        """
        SELECT
            COUNT(*) FILTER (WHERE status = 'active')  AS active,
            COUNT(*) FILTER (WHERE status = 'pending') AS pending
        FROM group_memberships
        WHERE group_id = $1
        """,
        group_id,
    )
    return int(r["active"] or 0), int(r["pending"] or 0)


async def set_membership_status(
    conn: asyncpg.Connection,
    *,
    group_id: GroupId,
    child_user_id: UserId,
    new_status: GroupMembershipStatus,
    expect_current: GroupMembershipStatus | None = None,
) -> MembershipRow:
    activated_clause = ", activated_at = now()" if new_status == GroupMembershipStatus.ACTIVE else ""
    if expect_current is None:
        r = await conn.fetchrow(
            f"""
            UPDATE group_memberships
               SET status = $3::group_membership_status{activated_clause}
             WHERE group_id = $1 AND child_user_id = $2
            RETURNING {_MEMBERSHIP_COLS}
            """,
            group_id, child_user_id, new_status.value,
        )
    else:
        r = await conn.fetchrow(
            f"""
            UPDATE group_memberships
               SET status = $3::group_membership_status{activated_clause}
             WHERE group_id = $1 AND child_user_id = $2
               AND status = $4::group_membership_status
            RETURNING {_MEMBERSHIP_COLS}
            """,
            group_id, child_user_id, new_status.value, expect_current.value,
        )
    if r is None:
        raise RuntimeError("set_membership_status hit zero rows")
    return _row_to_membership(r)


async def bulk_activate_pending(conn: asyncpg.Connection, group_id: GroupId) -> int:
    """When a pending_parent group is approved, flip all PENDING memberships to ACTIVE."""
    r = await conn.execute(
        """
        UPDATE group_memberships
           SET status = 'active', activated_at = now()
         WHERE group_id = $1 AND status = 'pending'
        """,
        group_id,
    )
    # asyncpg returns "UPDATE N"
    return int(r.split()[-1]) if r else 0


async def bulk_decline_pending(conn: asyncpg.Connection, group_id: GroupId) -> int:
    r = await conn.execute(
        """
        UPDATE group_memberships
           SET status = 'declined'
         WHERE group_id = $1 AND status = 'pending'
        """,
        group_id,
    )
    return int(r.split()[-1]) if r else 0


async def list_groups_for_child(
    conn: asyncpg.Connection,
    child_user_id: UserId,
) -> list[tuple[GroupRow, GroupMembershipStatus]]:
    """Groups where this child has a non-removed membership."""
    rows = await conn.fetch(
        f"""
        SELECT {', '.join('g.' + c.strip() for c in _GROUP_COLS.strip().split(','))},
               gm.status::text AS my_status
        FROM group_memberships gm
        JOIN groups g ON g.id = gm.group_id
        WHERE gm.child_user_id = $1
          AND gm.status IN ('active', 'pending')
          AND g.status <> 'deleted'
        ORDER BY g.created_at DESC
        """,
        child_user_id,
    )
    out: list[tuple[GroupRow, GroupMembershipStatus]] = []
    for r in rows:
        out.append((
            _row_to_group(r),
            GroupMembershipStatus(r["my_status"]),
        ))
    return out
