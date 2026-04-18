"""Short, human-shareable codes."""
from __future__ import annotations

import secrets


def generate_invite_code() -> str:
    """Return a fresh `GRUPPE-XXXXXX` code.

    6 digits gives ~1M combinations. Uniqueness is enforced at the DB level
    via `groups.invite_code UNIQUE`; services retry on conflict.
    """
    n = secrets.randbelow(1_000_000)
    return f"GRUPPE-{n:06d}"
