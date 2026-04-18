"""Test fixtures.

Tests run against a real Postgres — set TEST_DATABASE_URL to a throwaway DB
that has had all migrations applied.

Strategy:
- Each test wraps its work in an outer transaction that is rolled back at
  the end. asyncpg turns nested service-level transactions into savepoints
  automatically, so services work normally inside this wrapper.
- `factories` lets tests create the exact users/relations they need without
  running full onboarding flows.
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from typing import AsyncIterator

import asyncpg
import pytest
import pytest_asyncio

from blink.auth.context import AuthContext
from blink.types import (
    LinkStatus,
    ParentAccountId,
    UserId,
    UserStatus,
    UserType,
)


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")


def _require_db() -> str:
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL not set — skipping DB-backed tests")
    return TEST_DATABASE_URL


@pytest_asyncio.fixture
async def conn() -> AsyncIterator[asyncpg.Connection]:
    dsn = _require_db()
    connection = await asyncpg.connect(dsn)
    tx = connection.transaction()
    await tx.start()
    try:
        yield connection
    finally:
        await tx.rollback()
        await connection.close()


# --- Factories -----------------------------------------------------------

@dataclass
class ChildFixture:
    user_id: UserId
    display_name: str
    ctx: AuthContext


@dataclass
class ParentFixture:
    user_id: UserId
    parent_account_id: ParentAccountId
    ctx: AuthContext


@pytest_asyncio.fixture
async def make_child(conn: asyncpg.Connection):
    counter = {"n": 0}

    async def _make(name: str | None = None) -> ChildFixture:
        counter["n"] += 1
        display = name or f"Kid{counter['n']}"
        row = await conn.fetchrow(
            """
            INSERT INTO users (type, status, display_name, avatar_initial)
            VALUES ('child', 'active', $1, $2)
            RETURNING id
            """,
            display, display[0].upper(),
        )
        uid = UserId(row["id"])
        return ChildFixture(
            user_id=uid,
            display_name=display,
            ctx=AuthContext(user_id=uid, user_type=UserType.CHILD),
        )

    return _make


@pytest_asyncio.fixture
async def make_parent(conn: asyncpg.Connection):
    counter = {"n": 0}

    async def _make(name: str | None = None) -> ParentFixture:
        counter["n"] += 1
        display = name or f"Forælder{counter['n']}"
        user_row = await conn.fetchrow(
            """
            INSERT INTO users (type, status, display_name)
            VALUES ('parent', 'active', $1)
            RETURNING id
            """,
            display,
        )
        uid = UserId(user_row["id"])
        parent_row = await conn.fetchrow(
            """
            INSERT INTO parent_accounts (user_id, display_name, contact_email_or_phone, verified)
            VALUES ($1, $2, $3, true)
            RETURNING id
            """,
            uid, display, f"{display.lower()}+{uuid.uuid4().hex[:6]}@example.test",
        )
        pid = ParentAccountId(parent_row["id"])
        return ParentFixture(
            user_id=uid,
            parent_account_id=pid,
            ctx=AuthContext(
                user_id=uid,
                user_type=UserType.PARENT,
                parent_account_id=pid,
            ),
        )

    return _make


@pytest_asyncio.fixture
async def link_parent_child(conn: asyncpg.Connection):
    async def _link(parent: ParentFixture, child: ChildFixture) -> None:
        await conn.execute(
            """
            INSERT INTO child_parent_links
                (child_user_id, parent_account_id, status, activated_at)
            VALUES ($1, $2, $3, now())
            """,
            child.user_id, parent.parent_account_id, LinkStatus.ACTIVE.value,
        )

    return _link


@pytest_asyncio.fixture
async def make_friendship(conn: asyncpg.Connection):
    async def _make(a: ChildFixture, b: ChildFixture) -> None:
        lo, hi = (a.user_id, b.user_id) if a.user_id < b.user_id else (b.user_id, a.user_id)
        await conn.execute(
            """
            INSERT INTO friendships (child_user_id_a, child_user_id_b, approved_at)
            VALUES ($1, $2, now())
            """,
            lo, hi,
        )

    return _make


@pytest.fixture
def r2():
    """Fresh InMemoryR2Adapter per test."""
    from blink.r2.adapter import InMemoryR2Adapter
    return InMemoryR2Adapter()


@pytest_asyncio.fixture
async def make_active_group(conn: asyncpg.Connection):
    """Create an ACTIVE group with the given child as creator+member.

    Bypasses the service layer so tests can set up state directly.
    Optional tier parameter overrides groups.member_cap_tier so tier
    enforcement tests can exercise each cap.
    """
    from blink.ids import generate_invite_code
    from blink.types import GroupId, GroupMemberRole, GroupPlanTier

    counter = {"n": 0}

    async def _make(
        creator: ChildFixture,
        name: str | None = None,
        other_members: list[ChildFixture] | None = None,
        tier: GroupPlanTier = GroupPlanTier.LILLE,
    ):
        counter["n"] += 1
        gname = name or f"TestGroup{counter['n']}"
        code = generate_invite_code()
        row = await conn.fetchrow(
            """
            INSERT INTO groups
                (name, created_by_child_id, status, invite_code, approved_at, member_cap_tier)
            VALUES ($1, $2, 'active', $3, now(), $4::group_plan_tier)
            RETURNING id
            """,
            gname, creator.user_id, code, tier.value,
        )
        gid = GroupId(row["id"])
        # Keep billing_state in sync with the tier used in the test.
        if tier != GroupPlanTier.LILLE:
            await conn.execute(
                """
                UPDATE group_billing_state
                   SET current_tier = $2::group_plan_tier
                 WHERE group_id = $1
                """,
                gid, tier.value,
            )
        await conn.execute(
            """
            INSERT INTO group_memberships
                (group_id, child_user_id, role, status, activated_at)
            VALUES ($1, $2, $3::group_member_role, 'active', now())
            """,
            gid, creator.user_id, GroupMemberRole.CREATOR.value,
        )
        for m in (other_members or []):
            await conn.execute(
                """
                INSERT INTO group_memberships
                    (group_id, child_user_id, role, status, activated_at)
                VALUES ($1, $2, 'member', 'active', now())
                """,
                gid, m.user_id,
            )
        return gid

    return _make


@pytest_asyncio.fixture
async def make_many_children(conn: asyncpg.Connection, make_child):
    """Helper to create N children cheaply in one call."""
    async def _make(n: int, prefix: str = "K"):
        return [await make_child(f"{prefix}{i}") for i in range(n)]
    return _make
