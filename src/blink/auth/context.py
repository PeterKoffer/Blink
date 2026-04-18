"""AuthContext — the resolved identity for a request.

Small, immutable, framework-agnostic. Handlers receive this via dependency
injection (Sprint 2+ when FastAPI endpoints land); authz helpers consume it.
"""
from __future__ import annotations

from dataclasses import dataclass

from blink.types import ParentAccountId, UserId, UserType


@dataclass(frozen=True, slots=True)
class AuthContext:
    """Who is making this request.

    Invariants:
    - user_id is always set (anonymous access is not supported anywhere in v1).
    - user_type reflects the row in `users.type`.
    - parent_account_id is set iff user_type == PARENT (and the account row exists).
    """

    user_id: UserId
    user_type: UserType
    parent_account_id: ParentAccountId | None = None

    @property
    def is_child(self) -> bool:
        return self.user_type == UserType.CHILD

    @property
    def is_parent(self) -> bool:
        return self.user_type == UserType.PARENT
