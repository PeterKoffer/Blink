"""FastAPI application factory.

Run with:
    uvicorn blink.api.app:app --reload
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from blink.api.errors import install_error_handlers
from blink.api.routes import billing as billing_routes
from blink.api.routes import friends as friends_routes
from blink.api.routes import groups as groups_routes
from blink.api.routes import me as me_routes
from blink.api.routes import media as media_routes
from blink.api.routes import messages as messages_routes
from blink.api.routes import onboarding as onboarding_routes
from blink.api.routes import parent as parent_routes
from blink.config import get_settings
from blink.db import close_pool, init_pool
from blink.obs.logging import setup_logging
from blink.obs.metrics import get_metrics
from blink.obs.middleware import RequestLoggingMiddleware


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    setup_logging(get_settings().blink_log_level)
    await init_pool()
    try:
        yield
    finally:
        await close_pool()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Blink v1",
        version="0.1.0",
        lifespan=lifespan,
    )
    install_error_handlers(app)

    # --- CORS — only if origins configured. Required for the single-file
    # prototype at localhost:8765 to call this backend during integration.
    if settings.cors_origins:
        origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
            allow_headers=["*"],
            expose_headers=["Retry-After"],
        )

    # Observability middleware runs outermost so it captures all request state.
    app.add_middleware(RequestLoggingMiddleware)

    app.include_router(billing_routes.router)
    app.include_router(friends_routes.router)
    app.include_router(groups_routes.router)
    app.include_router(me_routes.router)
    app.include_router(media_routes.router)
    app.include_router(messages_routes.router)
    app.include_router(onboarding_routes.router)
    app.include_router(parent_routes.router)

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> dict[str, str]:
        """Liveness — process is up. Does not touch the DB."""
        return {"status": "ok"}

    @app.get("/readyz", include_in_schema=False)
    async def readyz() -> PlainTextResponse:
        """Readiness — can serve traffic. Confirms the DB pool is healthy."""
        from blink.db import get_pool
        try:
            pool = get_pool()
            async with pool.acquire() as c:
                await c.fetchval("SELECT 1")
        except Exception as e:
            return PlainTextResponse(
                f"not_ready: {type(e).__name__}",
                status_code=503,
            )
        return PlainTextResponse("ready\n")

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> PlainTextResponse:
        """Prometheus text format. Scrape on a regular schedule."""
        body = get_metrics().render_prometheus()
        return PlainTextResponse(body, media_type="text/plain; version=0.0.4")

    return app


app = create_app()
