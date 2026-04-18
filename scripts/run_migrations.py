#!/usr/bin/env python3
"""Apply pending SQL migrations in order.

Tracks applied migrations in a `schema_migrations` bookkeeping table. Each
migration file is applied inside a single transaction (migrations themselves
typically begin/commit, but the runner also wraps for safety).

Usage:
    python scripts/run_migrations.py          # apply all pending
    python scripts/run_migrations.py --dry    # list pending without applying
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import sys
from pathlib import Path

import asyncpg

# Make `blink` importable when run directly.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from blink.config import get_settings  # noqa: E402


MIGRATIONS_DIR = ROOT / "migrations"


BOOKKEEPING_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     text PRIMARY KEY,
    checksum    text NOT NULL,
    applied_at  timestamptz NOT NULL DEFAULT now()
);
"""


def load_migrations() -> list[tuple[str, Path]]:
    """Return sorted list of (version, path) for every migration file."""
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    out = []
    for f in files:
        # Version is filename without extension; e.g. "001_core_identity"
        out.append((f.stem, f))
    return out


def checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


async def applied_versions(conn: asyncpg.Connection) -> dict[str, str]:
    rows = await conn.fetch("SELECT version, checksum FROM schema_migrations")
    return {r["version"]: r["checksum"] for r in rows}


async def apply_one(conn: asyncpg.Connection, version: str, path: Path) -> None:
    sql = path.read_text()
    print(f"  applying {version} ...", flush=True)
    # Each migration file is expected to control its own transaction (BEGIN/COMMIT),
    # but we still run in a transaction here so the bookkeeping insert is atomic.
    # asyncpg's execute() handles multi-statement scripts fine.
    async with conn.transaction():
        await conn.execute(sql)
        await conn.execute(
            "INSERT INTO schema_migrations (version, checksum) VALUES ($1, $2)",
            version,
            checksum(path),
        )


async def main(dry: bool) -> int:
    settings = get_settings()
    conn = await asyncpg.connect(settings.database_url)
    try:
        await conn.execute(BOOKKEEPING_SQL)
        applied = await applied_versions(conn)
        all_migrations = load_migrations()

        pending = [(v, p) for v, p in all_migrations if v not in applied]

        # Drift check: applied migrations should still match their file checksum.
        for v, p in all_migrations:
            if v in applied and applied[v] != checksum(p):
                print(
                    f"ERROR: migration {v} has been modified since it was applied.",
                    file=sys.stderr,
                )
                print(
                    "Migrations are immutable once applied. Write a new migration instead.",
                    file=sys.stderr,
                )
                return 2

        if not pending:
            print("No pending migrations.")
            return 0

        print(f"Pending migrations ({len(pending)}):")
        for v, _ in pending:
            print(f"  - {v}")

        if dry:
            return 0

        for v, p in pending:
            await apply_one(conn, v, p)

        print(f"Applied {len(pending)} migration(s).")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry", action="store_true", help="list pending without applying")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.dry)))
