"""Central authorization helpers — deny by default.

Every `require_*` function raises on failure. Callers never check return
values for truthiness; they let exceptions propagate to the API layer.

Design rules:
- These are the ONLY place membership/ownership checks live. Do not inline
  equivalents in handlers.
- A missing row is an AuthzError, not a NotFoundError, when the resource
  existence itself is sensitive (i.e. don't leak "this group exists, you
  just can't see it"). Use NotFoundError only for user-visible lookups
  where existence is not sensitive.
- Helpers operate on IDs + an AuthContext; they take a DB connection so
  they can be composed inside a transaction.
"""
from __future__ import annotations

import asyncpg

from blink.auth.context import AuthContext
from blink.errors import AuthError, AuthzError
from blink.types import (
    GroupId,
    GroupMembershipStatus,
    LinkStatus,
    ParentAccountId,
    UserId,
    UserStatus,
    UserType,
)


# ---------------------------------------------------------------
# Identity-level guards
# ---------------------------------------------------------------

def require_authenticated(ctx: AuthContext | None) -> AuthContext:
    """Reject anonymous callers."""
    if ctx is None:
        raise AuthError("Authentication required")
    return ctx


def require_child(ctx: AuthContext) -> AuthContext:
    """Caller must be a child."""
    if ctx.user_type != UserType.CHILD:
        raise AuthzError("Child identity required")
    return ctx


def require_parent(ctx: AuthContext) -> AuthContext:
    """Caller must be a parent with a parent_accounts row."""
    if ctx.user_type != UserType.PARENT or ctx.parent_account_id is None:
        raise AuthzError("Parent identity required")
    return ctx


# ---------------------------------------------------------------
# Parent ↔ child linkage
# ---------------------------------------------------------------

async def require_child_linked_to_parent(
    conn: asyncpg.Connection,
    *,
    child_user_id: UserId,
    parent_account_id: ParentAccountId,
) -> None:
    """The child must be linked to this parent via an ACTIVE child_parent_links row."""
    row = await conn.fetchrow(
        """
        SELECT 1
        FROM child_parent_links
        WHERE child_user_id = $1
          AND parent_account_id = $2
          AND status = $3
        """,
        child_user_id,
        parent_account_id,
        LinkStatus.ACTIVE.value,
    )
    if row is None:
        raise AuthzError("Parent is not linked to this child")


async def require_parent_can_review_child(
    conn: asyncpg.Connection,
    ctx: AuthContext,
    *,
    child_user_id: UserId,
) -> None:
    """Caller must be a parent linked to the given child.

    Used before approve/decline of friend and group requests that target or
    involve the child.
    """
    require_parent(ctx)
    assert ctx.parent_account_id is not None  # guaranteed by require_parent
    await require_child_linked_to_parent(
        conn,
        child_user_id=child_user_id,
        parent_account_id=ctx.parent_account_id,
    )


# ---------------------------------------------------------------
# Group scope
# ---------------------------------------------------------------

async def require_group_member(
    conn: asyncpg.Connection,
    *,
    group_id: GroupId,
    child_user_id: UserId,
) -> None:
    """Child must have an ACTIVE membership in the group."""
    row = await conn.fetchrow(
        """
        SELECT 1
        FROM group_memberships
        WHERE group_id = $1
          AND child_user_id = $2
          AND status = $3
        """,
        group_id,
        child_user_id,
        GroupMembershipStatus.ACTIVE.value,
    )
    if row is None:
        raise AuthzError("Not a member of this group")


async def require_group_access(
    conn: asyncpg.Connection,
    ctx: AuthContext,
    *,
    group_id: GroupId,
) -> None:
    """Caller can access the group.

    Rules:
    - A child can access a group they are an ACTIVE member of.
    - A parent can access a group if at least one of their linked children
      has an ACTIVE membership in it.

    This is the primary gate for reading group state (messages, info, members).
    """
    if ctx.user_type == UserType.CHILD:
        await require_group_member(
            conn,
            group_id=group_id,
            child_user_id=ctx.user_id,
        )
        return

    if ctx.user_type == UserType.PARENT and ctx.parent_account_id is not None:
        row = await conn.fetchrow(
            """
            SELECT 1
            FROM group_memberships gm
            JOIN child_parent_links cpl
              ON cpl.child_user_id = gm.child_user_id
             AND cpl.status = $3
            WHERE gm.group_id = $1
              AND gm.status = $2
              AND cpl.parent_account_id = $4
            LIMIT 1
            """,
            group_id,
            GroupMembershipStatus.ACTIVE.value,
            LinkStatus.ACTIVE.value,
            ctx.parent_account_id,
        )
        if row is None:
            raise AuthzError("No linked child is a member of this group")
        return

    raise AuthzError("Unknown identity type for group access")


# ---------------------------------------------------------------
# Friendship scope (used from Sprint 2+)
# ---------------------------------------------------------------

async def require_friendship(
    conn: asyncpg.Connection,
    *,
    child_a: UserId,
    child_b: UserId,
) -> None:
    """There must be an ACTIVE friendship between two children."""
    if child_a == child_b:
        raise AuthzError("Self is not a friendship")
    # Canonicalize ordering to match the table's storage convention.
    lo, hi = (child_a, child_b) if child_a < child_b else (child_b, child_a)
    row = await conn.fetchrow(
        """
        SELECT 1
        FROM friendships
        WHERE child_user_id_a = $1
          AND child_user_id_b = $2
          AND status = 'active'
        """,
        lo,
        hi,
    )
    if row is None:
        raise AuthzError("No active friendship between these children")


# ---------------------------------------------------------------
# User status
# ---------------------------------------------------------------

async def require_active_user(
    conn: asyncpg.Connection,
    user_id: UserId,
) -> None:
    """User row must exist with status='active'."""
    row = await conn.fetchrow(
        "SELECT status::text AS status FROM users WHERE id = $1",
        user_id,
    )
    if row is None or row["status"] != UserStatus.ACTIVE.value:
        raise AuthzError("User is not active")
