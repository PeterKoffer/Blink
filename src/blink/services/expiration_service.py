"""Timer-based expiration with media cascade.

On run:
    1. Flip all active messages past TTL to status='expired'.
    2. For messages that referenced a media row, also flip the associated
       media.access_status from 'active' to 'expired'. Physical R2 deletion
       is handled by the bucket's lifecycle rule, not here.

Safe to run on any schedule, idempotent.
"""
from __future__ import annotations

import asyncpg

from blink.audit import Events, write_audit
from blink.obs.metrics import count_media_cascade, count_messages_expired
from blink.repos import media as media_repo
from blink.repos import messages as messages_repo


async def expire_due_messages(conn: asyncpg.Connection) -> tuple[int, int]:
    """Run one expiration pass.

    Returns (messages_flipped, media_flipped).
    """
    async with conn.transaction():
        msg_count, media_ids = await messages_repo.mark_expired_due(conn)

        media_count = 0
        if media_ids:
            from blink.types import MediaId
            media_count = await media_repo.cascade_expire(
                conn, [MediaId(mid) for mid in media_ids],
            )

        if msg_count > 0:
            await write_audit(
                conn,
                event_type=Events.MESSAGES_EXPIRED,
                target_type="messages",
                payload={"count": msg_count},
            )
            count_messages_expired(msg_count)
        if media_count > 0:
            await write_audit(
                conn,
                event_type=Events.MEDIA_CASCADE_EXPIRED,
                target_type="media",
                payload={"count": media_count},
            )
            count_media_cascade(media_count)
        return msg_count, media_count
