"""Application-level errors.

These are the deny-by-default exceptions raised from the authz layer and other
foundational helpers. HTTP mapping happens in the API layer (Sprint 2+),
so errors stay framework-agnostic here.
"""
from __future__ import annotations


class BlinkError(Exception):
    """Base for all expected application errors. Not for programmer bugs."""

    code: str = "blink_error"


class AuthError(BlinkError):
    """Authentication failed — missing, invalid, or expired credentials."""

    code = "auth_error"


class AuthzError(BlinkError):
    """Authenticated, but not authorized for this action/resource."""

    code = "authz_error"


class NotFoundError(BlinkError):
    """Resource does not exist or is not visible to the caller."""

    code = "not_found"


class StateConflictError(BlinkError):
    """Operation conflicts with current resource state (e.g. already approved)."""

    code = "state_conflict"


class PolicyBlockedError(BlinkError):
    """Action is blocked by parent policy."""

    code = "policy_blocked"

    def __init__(self, policy_key: str, message: str | None = None) -> None:
        super().__init__(message or f"Blocked by parent policy: {policy_key}")
        self.policy_key = policy_key


class ValidationError(BlinkError):
    """Request is well-formed but semantically invalid (e.g. empty text, bad ttl)."""

    code = "validation_error"


class UnsupportedError(BlinkError):
    """Feature or mode is not supported in the current Blink version.

    Distinct from validation: the value is syntactically legal but we have
    explicitly chosen not to implement it in v1 (e.g. ephemeralMode=after_read,
    message type=image before Sprint 4).
    """

    code = "unsupported"

    def __init__(self, feature: str, message: str | None = None) -> None:
        super().__init__(message or f"Not supported in v1: {feature}")
        self.feature = feature


class UpgradeRequiredError(BlinkError):
    """Group's current tier cannot hold the proposed member count.

    Caller must upgrade to at least `required_tier` before retrying.
    The error carries enough metadata for the parent-facing UI to render
    a precise upgrade CTA.
    """

    code = "upgrade_required"

    def __init__(
        self,
        *,
        current_tier: str,
        required_tier: str,
        current_member_count: int,
        current_cap: int,
        message: str | None = None,
    ) -> None:
        super().__init__(
            message
            or (
                f"Group has {current_member_count} members; current tier "
                f"'{current_tier}' allows up to {current_cap}. Upgrade to "
                f"'{required_tier}'."
            )
        )
        self.current_tier = current_tier
        self.required_tier = required_tier
        self.current_member_count = current_member_count
        self.current_cap = current_cap


class HardCapExceededError(BlinkError):
    """Operation would take the group past the v1 hard cap of 50 members.

    No upgrade path fixes this — it's a product-level limit, not a pricing
    one. Caller must decline or split the group.
    """

    code = "hard_cap_exceeded"

    def __init__(self, limit: int = 50, message: str | None = None) -> None:
        super().__init__(
            message or f"Group cannot exceed {limit} members in v1"
        )
        self.limit = limit


class RateLimitedError(BlinkError):
    """Caller has exceeded the rate limit for a named bucket.

    Carries retry-after metadata so the client can back off intelligently.
    """

    code = "rate_limited"

    def __init__(
        self,
        *,
        bucket: str,
        limit: int,
        window_seconds: int,
        retry_after_seconds: int,
        message: str | None = None,
    ) -> None:
        super().__init__(
            message
            or f"Rate limit hit on '{bucket}': max {limit}/{window_seconds}s"
        )
        self.bucket = bucket
        self.limit = limit
        self.window_seconds = window_seconds
        self.retry_after_seconds = retry_after_seconds
