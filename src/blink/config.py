"""Environment-backed settings.

Loaded once at process start; injected via dependency system in FastAPI later.
"""
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


Env = Literal["dev", "staging", "prod"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Runtime
    blink_env: Env = "dev"
    blink_log_level: str = "info"

    # Postgres
    database_url: str = Field(..., description="Postgres connection string")

    # Supabase Auth
    supabase_jwt_secret: str = Field(..., description="HS256 JWT secret from Supabase")
    supabase_jwt_audience: str = "authenticated"
    supabase_jwt_issuer: str = Field(..., description="Expected iss claim on JWTs")

    # R2 (Sprint 4)
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = "blink-media"
    r2_endpoint: str = ""

    # Sprint 6 — frontend integration + observability
    # Comma-separated list of origins allowed to call the API with credentials.
    # Only applied if non-empty. Example: "http://localhost:8765"
    cors_origins: str = ""
    # Dev-only escape hatch: when env=dev AND this is true, accept
    # `X-Dev-User-Id: <uuid>` instead of a real Supabase JWT. Lets the
    # prototype frontend talk to the backend without a full OIDC flow.
    # Rejected in all other envs regardless of header presence.
    blink_dev_bypass_auth: bool = False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings singleton. Exceptions surface the first time this is called."""
    return Settings()  # type: ignore[call-arg]
