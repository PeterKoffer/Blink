"""Friend requests + friendships data access."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import asyncpg

from blink.types import (
    FriendRequestId,
    FriendRequestStatus,
    FriendshipId,
    FriendshipStatus,
    ParentAccountId,
    UserId,
)


@dataclass(frozen=True, slots=True)
class FriendRequestRow:
    id: FriendRequestId
    requester_child_id: UserId
    target_child_id: UserId
    status: FriendRequestStatus
    method: str | None
    created_at: datetime
    reviewed_at: datetime | None
    reviewed_by_parent_account_id: ParentAccountId | None


@dataclass(frozen=True, slots=True)
class FriendshipRow:
    id: FriendshipId
    child_user_id_a: UserId
    child_user_id_b: UserId
    status: FriendshipStatus
    approved_at: datetime
    created_at: datetime


def _row_to_request(r: asyncpg.Record) -> FriendRequestRow:
    return FriendRequestRow(
        id=FriendRequestId(r["id"]),
        requester_child_id=UserId(r["requester_child_id"]),
        target_child_id=UserId(r["target_child_id"]),
        status=FriendRequestStatus(r["status"]),
        method=r["method"],
        created_at=r["created_at"],
        reviewed_at=r["reviewed_at"],
        reviewed_by_parent_account_id=(
            ParentAccountId(r["reviewed_by_parent_account_id"])
            if r["reviewed_by_parent_account_id"] else None
        ),
    )


def _row_to_friendship(r: asyncpg.Record) -> FriendshipRow:
    return FriendshipRow(
        id=FriendshipId(r["id"]),
        child_user_id_a=UserId(r["child_user_id_a"]),
        child_user_id_b=UserId(r["child_user_id_b"]),
        status=FriendshipStatus(r["status"]),
        approved_at=r["approved_at"],
        created_at=r["created_at"],
    )


# --- friend_requests ---

async def get_request(conn: asyncpg.Connection, request_id: FriendRequestId) -> FriendRequestRow | None:
    r = await conn.fetchrow(
        """
        SELECT id, requester_child_id, target_child_id, status::text AS status,
               method, created_at, reviewed_at, reviewed_by_parent_account_id
        FROM friend_requests
        WHERE id = $1
        """,
        request_id,
    )
    return _row_to_request(r) if r else None


async def get_pending_between(
    conn: asyncpg.Connection,
    requester: UserId,
    target: UserId,
) -> FriendRequestRow | None:
    r = await conn.fetchrow(
        """
        SELECT id, requester_child_id, target_child_id, status::text AS status,
               method, created_at, reviewed_at, reviewed_by_parent_account_id
        FROM friend_requests
        WHERE requester_child_id = $1 AND target_child_id = $2
          AND status = 'pending_parent'
        """,
        requester, target,
    )
    return _row_to_request(r) if r else None


async def insert_request(
    conn: asyncpg.Connection,
    *,
    requester: UserId,
    target: UserId,
    method: str | None,
) -> FriendRequestRow:
    r = await conn.fetchrow(
        """
        INSERT INTO friend_requests (requester_child_id, target_child_id, method)
        VALUES ($1, $2, $3)
        RETURNING id, requester_child_id, target_child_id, status::text AS status,
                  method, created_at, reviewed_at, reviewed_by_parent_account_id
        """,
        requester, target, method,
    )
    return _row_to_request(r)


async def mark_reviewed(
    conn: asyncpg.Connection,
    *,
    request_id: FriendRequestId,
    new_status: FriendRequestStatus,
    reviewed_by: ParentAccountId,
) -> FriendRequestRow:
    r = await conn.fetchrow(
        """
        UPDATE friend_requests
           SET status = $2::friend_request_status,
               reviewed_at = now(),
               reviewed_by_parent_account_id = $3
         WHERE id = $1
           AND status = 'pending_parent'
        RETURNING id, requester_child_id, target_child_id, status::text AS status,
                  method, created_at, reviewed_at, reviewed_by_parent_account_id
        """,
        request_id, new_status.value, reviewed_by,
    )
    if r is None:
        # either not found, or already reviewed — caller must distinguish via prior load
        raise RuntimeError("friend_request update hit zero rows")
    return _row_to_request(r)


async def list_pending_for_parent(
    conn: asyncpg.Connection,
    parent_account_id: ParentAccountId,
) -> list[FriendRequestRow]:
    rows = await conn.fetch(
        """
        SELECT fr.id, fr.requester_child_id, fr.target_child_id, fr.status::text AS status,
               fr.method, fr.created_at, fr.reviewed_at, fr.reviewed_by_parent_account_id
        FROM friend_requests fr
        JOIN child_parent_links cpl
          ON cpl.child_user_id = fr.requester_child_id
         AND cpl.status = 'active'
        WHERE fr.status = 'pending_parent'
          AND cpl.parent_account_id = $1
        ORDER BY fr.created_at DESC
        """,
        parent_account_id,
    )
    return [_row_to_request(r) for r in rows]


# --- friendships ---

async def get_active_friendship(
    conn: asyncpg.Connection,
    child_a: UserId,
    child_b: UserId,
) -> FriendshipRow | None:
    lo, hi = (child_a, child_b) if child_a < child_b else (child_b, child_a)
    r = await conn.fetchrow(
        """
        SELECT id, child_user_id_a, child_user_id_b, status::text AS status, approved_at, created_at
        FROM friendships
        WHERE child_user_id_a = $1 AND child_user_id_b = $2 AND status = 'active'
        """,
        lo, hi,
    )
    return _row_to_friendship(r) if r else None


async def insert_friendship(
    conn: asyncpg.Connection,
    *,
    child_a: UserId,
    child_b: UserId,
) -> FriendshipRow:
    lo, hi = (child_a, child_b) if child_a < child_b else (child_b, child_a)
    r = await conn.fetchrow(
        """
        INSERT INTO friendships (child_user_id_a, child_user_id_b, approved_at)
        VALUES ($1, $2, now())
        RETURNING id, child_user_id_a, child_user_id_b, status::text AS status, approved_at, created_at
        """,
        lo, hi,
    )
    return _row_to_friendship(r)


async def list_active_friends_of(
    conn: asyncpg.Connection,
    child_user_id: UserId,
) -> list[dict]:
    """Return peer rows with friendship anchor. Used by GET /friends."""
    rows = await conn.fetch(
        """
        SELECT f.id AS friendship_id,
               CASE WHEN f.child_user_id_a = $1 THEN f.child_user_id_b ELSE f.child_user_id_a END AS peer_id,
               u.display_name, u.avatar_initial,
               f.approved_at
        FROM friendships f
        JOIN users u ON u.id = CASE WHEN f.child_user_id_a = $1 THEN f.child_user_id_b ELSE f.child_user_id_a END
        WHERE f.status = 'active'
          AND (f.child_user_id_a = $1 OR f.child_user_id_b = $1)
          AND u.status = 'active'
        ORDER BY f.approved_at DESC
        """,
        child_user_id,
    )
    return [dict(r) for r in rows]
