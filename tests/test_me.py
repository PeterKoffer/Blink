"""/me endpoint — child and parent variants."""
from __future__ import annotations

import pytest

from blink.api.routes.me import get_me
from blink.auth.context import AuthContext
from blink.errors import NotFoundError
from blink.types import UserType


pytestmark = pytest.mark.asyncio


async def test_me_returns_child_state_for_child(conn, make_child):
    kid = await make_child("Sofie")
    resp = await get_me(kid.ctx, conn)
    assert resp.user_id == kid.user_id
    assert resp.user_type == UserType.CHILD
    assert resp.display_name == "Sofie"
    # No linked-children fields on child response.
    assert resp.parent_account_id is None
    assert resp.linked_children is None


async def test_me_returns_linked_children_for_parent(
    conn, make_child, make_parent, link_parent_child,
):
    kid1 = await make_child("Sofie")
    kid2 = await make_child("Noah")
    mom = await make_parent("Mor")
    await link_parent_child(mom, kid1)
    await link_parent_child(mom, kid2)

    resp = await get_me(mom.ctx, conn)
    assert resp.user_type == UserType.PARENT
    assert resp.parent_account_id == mom.parent_account_id
    assert resp.parent_verified is True
    assert resp.linked_children is not None
    names = sorted([c.display_name for c in resp.linked_children])
    assert names == ["Noah", "Sofie"]


async def test_me_missing_user_returns_not_found(conn):
    import uuid
    from blink.types import UserId
    fake_ctx = AuthContext(
        user_id=UserId(uuid.uuid4()),
        user_type=UserType.CHILD,
    )
    with pytest.raises(NotFoundError):
        await get_me(fake_ctx, conn)
