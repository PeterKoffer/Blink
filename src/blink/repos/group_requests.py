"""group_requests data access — one table, three request types."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import asyncpg

from blink.types import (
    GroupId,
    GroupRequestId,
    GroupRequestStatus,
    GroupRequestType,
    ParentAccountId,
    UserId,
)


@dataclass(frozen=True, slots=True)
class GroupRequestRow:
    id: GroupRequestId
    type: GroupRequestType
    actor_child_id: UserId
    group_id: GroupId | None
    target_child_id: UserId | None
    requested_name: str | None
    status: GroupRequestStatus
    created_at: datetime
    reviewed_at: datetime | None
    reviewed_by_parent_account_id: ParentAccountId | None


_COLS = """
    id, type::text AS type, actor_child_id, group_id, target_child_id,
    requested_name, status::text AS status, created_at, reviewed_at,
    reviewed_by_parent_account_id
"""


def _row(r: asyncpg.Record) -> GroupRequestRow:
    return GroupRequestRow(
        id=GroupRequestId(r["id"]),
        type=GroupRequestType(r["type"]),
        actor_child_id=UserId(r["actor_child_id"]),
        group_id=GroupId(r["group_id"]) if r["group_id"] else None,
        target_child_id=UserId(r["target_child_id"]) if r["target_child_id"] else None,
        requested_name=r["requested_name"],
        status=GroupRequestStatus(r["status"]),
        created_at=r["created_at"],
        reviewed_at=r["reviewed_at"],
        reviewed_by_parent_account_id=(
            ParentAccountId(r["reviewed_by_parent_account_id"])
            if r["reviewed_by_parent_account_id"] else None
        ),
    )


async def get(conn: asyncpg.Connection, request_id: GroupRequestId) -> GroupRequestRow | None:
    r = await conn.fetchrow(f"SELECT {_COLS} FROM group_requests WHERE id = $1", request_id)
    return _row(r) if r else None


async def insert_create_group(
    conn: asyncpg.Connection,
    *,
    actor: UserId,
    group_id: GroupId,
    requested_name: str,
) -> GroupRequestRow:
    r = await conn.fetchrow(
        f"""
        INSERT INTO group_requests (type, actor_child_id, group_id, requested_name)
        VALUES ('create_group', $1, $2, $3)
        RETURNING {_COLS}
        """,
        actor, group_id, requested_name,
    )
    return _row(r)


async def insert_join_group(
    conn: asyncpg.Connection,
    *,
    actor: UserId,
    group_id: GroupId,
) -> GroupRequestRow:
    r = await conn.fetchrow(
        f"""
        INSERT INTO group_requests (type, actor_child_id, group_id)
        VALUES ('join_group', $1, $2)
        RETURNING {_COLS}
        """,
        actor, group_id,
    )
    return _row(r)


async def insert_invite_to_group(
    conn: asyncpg.Connection,
    *,
    actor: UserId,
    group_id: GroupId,
    target: UserId,
) -> GroupRequestRow:
    r = await conn.fetchrow(
        f"""
        INSERT INTO group_requests (type, actor_child_id, group_id, target_child_id)
        VALUES ('invite_to_group', $1, $2, $3)
        RETURNING {_COLS}
        """,
        actor, group_id, target,
    )
    return _row(r)


async def mark_reviewed(
    conn: asyncpg.Connection,
    *,
    request_id: GroupRequestId,
    new_status: GroupRequestStatus,
    reviewed_by: ParentAccountId,
) -> GroupRequestRow | None:
    r = await conn.fetchrow(
        f"""
        UPDATE group_requests
           SET status = $2::group_request_status,
               reviewed_at = now(),
               reviewed_by_parent_account_id = $3
         WHERE id = $1 AND status = 'pending_parent'
        RETURNING {_COLS}
        """,
        request_id, new_status.value, reviewed_by,
    )
    return _row(r) if r else None


async def list_pending_for_parent(
    conn: asyncpg.Connection,
    parent_account_id: ParentAccountId,
) -> list[GroupRequestRow]:
    """A parent reviews:
    - create_group / join_group requests made by their linked child (actor)
    - invite_to_group requests whose target is their linked child
    """
    rows = await conn.fetch(
        f"""
        SELECT {_COLS} FROM group_requests gr
        WHERE gr.status = 'pending_parent'
          AND (
            (gr.type IN ('create_group', 'join_group')
              AND EXISTS (
                SELECT 1 FROM child_parent_links cpl
                 WHERE cpl.child_user_id = gr.actor_child_id
                   AND cpl.parent_account_id = $1
                   AND cpl.status = 'active'
              ))
            OR
            (gr.type = 'invite_to_group'
              AND EXISTS (
                SELECT 1 FROM child_parent_links cpl
                 WHERE cpl.child_user_id = gr.target_child_id
                   AND cpl.parent_account_id = $1
                   AND cpl.status = 'active'
              ))
          )
        ORDER BY gr.created_at DESC
        """,
        parent_account_id,
    )
    return [_row(r) for r in rows]
