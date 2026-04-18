"""R2 adapter — the only module that knows about the storage SDK.

Contract (ref project_blink_media.md):
- Bucket is private.
- Signed PUT URL TTL: 5 minutes (give client time to actually upload).
- Signed GET URL TTL: 60 seconds (tight so leaked URLs decay fast).
- No shared / deterministic URL caching.
- App server never streams bytes.

Two implementations are provided:
    InMemoryR2Adapter   — used in tests. No network; records "uploaded" keys.
    Boto3R2Adapter      — production. Lazy-imports boto3 so tests don't need it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ObjectMetadata:
    content_type: str | None
    content_length: int | None


class R2Adapter(Protocol):
    """Every method is async. Network-less operations still return async
    for a uniform call site.
    """

    async def generate_put_url(
        self, *, key: str, mime: str, size: int, ttl_seconds: int
    ) -> str: ...

    async def generate_get_url(self, *, key: str, ttl_seconds: int) -> str: ...

    async def object_exists(self, key: str) -> bool: ...

    async def object_metadata(self, key: str) -> ObjectMetadata | None: ...


# ---------------------------------------------------------------
# In-memory stub for tests
# ---------------------------------------------------------------

class InMemoryR2Adapter:
    """Test double. Stores what 'clients' have 'uploaded' via simulate_upload()."""

    def __init__(self) -> None:
        self._objects: dict[str, ObjectMetadata] = {}

    async def generate_put_url(
        self, *, key: str, mime: str, size: int, ttl_seconds: int
    ) -> str:
        return f"https://fake.r2.test/put/{key}?sig=fake&mime={mime}&size={size}&ttl={ttl_seconds}"

    async def generate_get_url(self, *, key: str, ttl_seconds: int) -> str:
        return f"https://fake.r2.test/get/{key}?sig=fake&ttl={ttl_seconds}"

    async def object_exists(self, key: str) -> bool:
        return key in self._objects

    async def object_metadata(self, key: str) -> ObjectMetadata | None:
        return self._objects.get(key)

    # Test helper
    def simulate_upload(self, key: str, *, mime: str, size: int) -> None:
        self._objects[key] = ObjectMetadata(content_type=mime, content_length=size)


# ---------------------------------------------------------------
# Production boto3 adapter — lazy-loaded
# ---------------------------------------------------------------

class Boto3R2Adapter:
    """Production R2 adapter. Boto3 is imported on first instantiation only,
    so tests and environments without boto3 installed remain importable.
    """

    def __init__(
        self,
        *,
        bucket: str,
        endpoint_url: str,
        access_key_id: str,
        secret_access_key: str,
    ) -> None:
        try:
            import boto3  # type: ignore[import-not-found]
            from botocore.config import Config  # type: ignore[import-not-found]
        except ImportError as e:
            raise RuntimeError(
                "boto3 is required for Boto3R2Adapter — install it via "
                "`pip install boto3` in production envs"
            ) from e

        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name="auto",
            config=Config(signature_version="s3v4"),
        )

    async def generate_put_url(
        self, *, key: str, mime: str, size: int, ttl_seconds: int
    ) -> str:
        # generate_presigned_url is a pure cryptographic operation — no network.
        return self._client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self._bucket,
                "Key": key,
                "ContentType": mime,
                "ContentLength": size,
            },
            ExpiresIn=ttl_seconds,
        )

    async def generate_get_url(self, *, key: str, ttl_seconds: int) -> str:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=ttl_seconds,
        )

    async def object_exists(self, key: str) -> bool:
        import asyncio
        try:
            await asyncio.to_thread(
                self._client.head_object, Bucket=self._bucket, Key=key
            )
            return True
        except Exception:  # noqa: BLE001 — boto exceptions are varied; any failure = not found
            return False

    async def object_metadata(self, key: str) -> ObjectMetadata | None:
        import asyncio
        try:
            r = await asyncio.to_thread(
                self._client.head_object, Bucket=self._bucket, Key=key
            )
            return ObjectMetadata(
                content_type=r.get("ContentType"),
                content_length=r.get("ContentLength"),
            )
        except Exception:  # noqa: BLE001
            return None
