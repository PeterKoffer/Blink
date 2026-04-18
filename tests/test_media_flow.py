"""Media upload-url, confirm, read-url flows."""
from __future__ import annotations

import pytest

from blink.errors import (
    AuthzError,
    NotFoundError,
    PolicyBlockedError,
    StateConflictError,
    UnsupportedError,
    ValidationError,
)
from blink.policies.parent import upsert_parent_policy
from blink.repos import media as media_repo
from blink.services import media_service
from blink.types import (
    MEDIA_MAX_SIZE_BYTES,
    MediaAccessStatus,
    MediaId,
    MediaUploadStatus,
)


pytestmark = pytest.mark.asyncio


# ============== upload-url ==============

async def test_member_can_get_upload_url(
    conn, r2, make_child, make_active_group,
):
    alice = await make_child("Alice")
    gid = await make_active_group(alice)

    row, url = await media_service.create_upload_url(
        conn, r2, alice.ctx,
        group_id=gid, chat_id=None,
        mime="image/jpeg", size=500_000, width=1600, height=1200,
    )
    assert row.uploader_id == alice.user_id
    assert row.group_id == gid
    assert row.upload_status == MediaUploadStatus.PENDING
    assert row.access_status == MediaAccessStatus.ACTIVE
    assert "fake.r2.test/put" in url


async def test_non_member_cannot_get_upload_url(
    conn, r2, make_child, make_active_group,
):
    alice = await make_child("Alice")
    outsider = await make_child("Outsider")
    gid = await make_active_group(alice)

    with pytest.raises(AuthzError):
        await media_service.create_upload_url(
            conn, r2, outsider.ctx,
            group_id=gid, chat_id=None,
            mime="image/jpeg", size=500_000, width=1600, height=1200,
        )


async def test_may_send_images_false_blocks_upload(
    conn, r2, make_child, make_parent, link_parent_child, make_active_group,
):
    alice = await make_child("Alice")
    mom = await make_parent("Mom")
    await link_parent_child(mom, alice)
    await upsert_parent_policy(
        conn, child_user_id=alice.user_id,
        updated_by=mom.parent_account_id, may_send_images=False,
    )
    gid = await make_active_group(alice)

    with pytest.raises(PolicyBlockedError) as exc:
        await media_service.create_upload_url(
            conn, r2, alice.ctx,
            group_id=gid, chat_id=None,
            mime="image/jpeg", size=500_000, width=1600, height=1200,
        )
    assert exc.value.policy_key == "may_send_images"


async def test_oversized_file_rejected(
    conn, r2, make_child, make_active_group,
):
    alice = await make_child("Alice")
    gid = await make_active_group(alice)

    with pytest.raises(ValidationError):
        await media_service.create_upload_url(
            conn, r2, alice.ctx,
            group_id=gid, chat_id=None,
            mime="image/jpeg",
            size=MEDIA_MAX_SIZE_BYTES + 1,
            width=1600, height=1200,
        )


async def test_unsupported_mime_rejected(
    conn, r2, make_child, make_active_group,
):
    alice = await make_child("Alice")
    gid = await make_active_group(alice)

    with pytest.raises(UnsupportedError) as exc:
        await media_service.create_upload_url(
            conn, r2, alice.ctx,
            group_id=gid, chat_id=None,
            mime="image/gif", size=100_000, width=500, height=500,
        )
    assert "mime" in exc.value.feature


# ============== confirm ==============

async def _create_pending(conn, r2, child, gid):
    return await media_service.create_upload_url(
        conn, r2, child.ctx,
        group_id=gid, chat_id=None,
        mime="image/jpeg", size=500_000, width=1600, height=1200,
    )


async def test_uploader_can_confirm_after_upload(
    conn, r2, make_child, make_active_group,
):
    alice = await make_child("Alice")
    gid = await make_active_group(alice)
    row, _url = await _create_pending(conn, r2, alice, gid)

    # Simulate client uploading bytes to R2.
    r2.simulate_upload(row.r2_key, mime="image/jpeg", size=500_000)

    updated = await media_service.confirm_media(
        conn, r2, alice.ctx, media_id=row.id,
    )
    assert updated.upload_status == MediaUploadStatus.READY


async def test_confirm_fails_if_object_missing_in_r2(
    conn, r2, make_child, make_active_group,
):
    alice = await make_child("Alice")
    gid = await make_active_group(alice)
    row, _url = await _create_pending(conn, r2, alice, gid)

    # No simulate_upload — object does not exist in R2.
    from blink.errors import BlinkError
    with pytest.raises(BlinkError) as exc:
        await media_service.confirm_media(
            conn, r2, alice.ctx, media_id=row.id,
        )
    assert exc.value.code == "storage_missing"


async def test_different_user_cannot_confirm(
    conn, r2, make_child, make_active_group, make_friendship,
):
    alice = await make_child("Alice")
    bob = await make_child("Bob")
    await make_friendship(alice, bob)
    gid = await make_active_group(alice, other_members=[bob])
    row, _ = await _create_pending(conn, r2, alice, gid)
    r2.simulate_upload(row.r2_key, mime="image/jpeg", size=500_000)

    with pytest.raises(StateConflictError):
        await media_service.confirm_media(
            conn, r2, bob.ctx, media_id=row.id,
        )


async def test_confirm_fails_when_not_pending(
    conn, r2, make_child, make_active_group,
):
    alice = await make_child("Alice")
    gid = await make_active_group(alice)
    row, _ = await _create_pending(conn, r2, alice, gid)
    r2.simulate_upload(row.r2_key, mime="image/jpeg", size=500_000)
    await media_service.confirm_media(conn, r2, alice.ctx, media_id=row.id)

    # Second confirm on already-ready media.
    with pytest.raises(StateConflictError):
        await media_service.confirm_media(conn, r2, alice.ctx, media_id=row.id)


# ============== read-url ==============

async def test_active_member_gets_read_url_for_ready_media(
    conn, r2, make_child, make_active_group,
):
    alice = await make_child("Alice")
    gid = await make_active_group(alice)
    row, _ = await _create_pending(conn, r2, alice, gid)
    r2.simulate_upload(row.r2_key, mime="image/jpeg", size=500_000)
    await media_service.confirm_media(conn, r2, alice.ctx, media_id=row.id)

    url, ttl = await media_service.get_read_url(
        conn, r2, alice.ctx, media_id=row.id,
    )
    assert "fake.r2.test/get" in url
    assert ttl == 60


async def test_non_member_cannot_get_read_url(
    conn, r2, make_child, make_active_group,
):
    alice = await make_child("Alice")
    outsider = await make_child("Outsider")
    gid = await make_active_group(alice)
    row, _ = await _create_pending(conn, r2, alice, gid)
    r2.simulate_upload(row.r2_key, mime="image/jpeg", size=500_000)
    await media_service.confirm_media(conn, r2, alice.ctx, media_id=row.id)

    with pytest.raises(AuthzError):
        await media_service.get_read_url(
            conn, r2, outsider.ctx, media_id=row.id,
        )


async def test_expired_media_does_not_issue_url(
    conn, r2, make_child, make_active_group,
):
    alice = await make_child("Alice")
    gid = await make_active_group(alice)
    row, _ = await _create_pending(conn, r2, alice, gid)
    r2.simulate_upload(row.r2_key, mime="image/jpeg", size=500_000)
    await media_service.confirm_media(conn, r2, alice.ctx, media_id=row.id)

    # Manually flip access_status to expired.
    await conn.execute(
        "UPDATE media SET access_status = 'expired' WHERE id = $1", row.id,
    )

    from blink.errors import BlinkError
    with pytest.raises(BlinkError) as exc:
        await media_service.get_read_url(
            conn, r2, alice.ctx, media_id=row.id,
        )
    assert exc.value.code == "gone"


async def test_pending_media_does_not_issue_url(
    conn, r2, make_child, make_active_group,
):
    alice = await make_child("Alice")
    gid = await make_active_group(alice)
    row, _ = await _create_pending(conn, r2, alice, gid)
    # Not confirmed — still pending.

    with pytest.raises(StateConflictError):
        await media_service.get_read_url(
            conn, r2, alice.ctx, media_id=row.id,
        )


async def test_missing_media_returns_not_found(
    conn, r2, make_child,
):
    import uuid
    alice = await make_child("Alice")
    with pytest.raises(NotFoundError):
        await media_service.get_read_url(
            conn, r2, alice.ctx, media_id=MediaId(uuid.uuid4()),
        )
