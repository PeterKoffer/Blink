"""Blink-code + OTP + invite-token generation and hashing.

- blink_code: `BLINK-XXXXXX` using an unambiguous alphabet (no 0/O/1/I/L)
  → ~887M combinations. Uniqueness enforced at DB level; services retry.
- OTP: 6 decimal digits. Stored as SHA-256 hash; attempts bounded in DB.
- invite_token: 32 url-safe bytes (256 bits of entropy). Used as the
  magic-link identifier a parent receives alongside the OTP.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets


# Alphabet excludes 0/O/1/I/L to reduce hand-copy errors.
_BLINK_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
_BLINK_CODE_LEN = 6


def generate_blink_code() -> str:
    """Return a fresh `BLINK-XXXXXX` code. Collisions are caught by DB UNIQUE."""
    suffix = "".join(secrets.choice(_BLINK_ALPHABET) for _ in range(_BLINK_CODE_LEN))
    return f"BLINK-{suffix}"


def generate_otp() -> str:
    """6 decimal digits. Returned to the adapter, stored as hash."""
    n = secrets.randbelow(1_000_000)
    return f"{n:06d}"


def hash_otp(otp: str) -> str:
    """SHA-256 of the OTP. No per-record salt — OTPs live ≤60 minutes and
    are single-use, and the attempts counter already blocks brute force.
    Keeps DB dumps from exposing live OTPs to casual readers.
    """
    return hashlib.sha256(otp.encode("utf-8")).hexdigest()


def verify_otp(otp: str, expected_hash: str) -> bool:
    """Constant-time comparison."""
    return hmac.compare_digest(hash_otp(otp), expected_hash)


def generate_invite_token() -> str:
    """32 url-safe bytes = 43-char token."""
    return secrets.token_urlsafe(32)
