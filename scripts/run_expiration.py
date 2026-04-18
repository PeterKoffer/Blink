#!/usr/bin/env python3
"""Expire active messages whose TTL has passed.

One-shot — designed to be invoked by cron or a systemd timer on a short
interval (e.g. every 30 seconds). Idempotent; safe to run concurrently,
though one worker is enough.

Usage:
    python scripts/run_expiration.py
    python scripts/run_expiration.py --loop --interval 30   # dev-mode loop
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import asyncpg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from blink.config import get_settings  # noqa: E402
from blink.services.expiration_service import expire_due_messages  # noqa: E402


async def _one_shot() -> int:
    dsn = get_settings().database_url
    conn = await asyncpg.connect(dsn)
    try:
        msg_count, media_count = await expire_due_messages(conn)
    finally:
        await conn.close()
    print(f"expired {msg_count} message(s); cascaded {media_count} media row(s)")
    return msg_count


async def _loop(interval: float) -> None:
    while True:
        try:
            await _one_shot()
        except Exception as e:  # noqa: BLE001 — top-level loop guard
            print(f"expiration run failed: {e}", file=sys.stderr)
        await asyncio.sleep(interval)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop", action="store_true", help="run continuously")
    parser.add_argument("--interval", type=float, default=30.0, help="loop interval in seconds")
    args = parser.parse_args()

    if args.loop:
        asyncio.run(_loop(args.interval))
        return 0
    asyncio.run(_one_shot())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
