"""Postgres access via asyncpg.

A single pool per process. Connections are acquired per request/handler.
No ORM — raw SQL, typed results via Pydantic where relevant.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

import asyncpg

from blink.config import get_settings


_pool: asyncpg.Pool | None = None


async def init_pool() -> asyncpg.Pool:
    """Create the shared pool. Call once at app startup."""
    global _pool
    if _pool is not None:
        return _pool
    settings = get_settings()
    _pool = await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=1,
        max_size=10,
        command_timeout=10,
    )
    return _pool


async def close_pool() -> None:
    """Close the pool at app shutdown."""
    global _pool
    if _pool is None:
        return
    await _pool.close()
    _pool = None


def get_pool() -> asyncpg.Pool:
    """Return the initialized pool. Raises if init_pool() was not awaited first."""
    if _pool is None:
        raise RuntimeError("DB pool not initialized — call init_pool() at app startup.")
    return _pool


@asynccontextmanager
async def acquire() -> AsyncIterator[asyncpg.Connection]:
    """Acquire a pooled connection. Use in `async with`."""
    pool = get_pool()
    async with pool.acquire() as conn:
        yield conn
