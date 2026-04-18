"""Tier model — the ONE place 10/30/50 lives.

All cap enforcement routes through these helpers. No handler or service
should hard-code tier numbers; they must call `cap_for`, `required_tier_for`,
or `can_accept_members`.

Mirrors project_blink_pricing.md:
    lille:  up to 10 members (9 kr/md)
    normal: up to 30 members (15 kr/md)
    stor:   up to 50 members (19 kr/md)
    hard cap: 50 members
"""
from __future__ import annotations

from blink.types import HARD_MAX_GROUP_MEMBERS, TIER_MEMBER_CAPS, GroupPlanTier


# Upgrade path ordered smallest → largest.
_TIER_ORDER: tuple[GroupPlanTier, ...] = (
    GroupPlanTier.LILLE,
    GroupPlanTier.NORMAL,
    GroupPlanTier.STOR,
)


def cap_for(tier: GroupPlanTier) -> int:
    """Member cap allowed by this tier (active + pending, inclusive)."""
    return TIER_MEMBER_CAPS[tier]


def next_tier(tier: GroupPlanTier) -> GroupPlanTier | None:
    """Return the next-higher tier, or None if already at stor."""
    i = _TIER_ORDER.index(tier)
    return _TIER_ORDER[i + 1] if i + 1 < len(_TIER_ORDER) else None


def is_higher_tier(candidate: GroupPlanTier, current: GroupPlanTier) -> bool:
    """Strictly higher in the upgrade path."""
    return _TIER_ORDER.index(candidate) > _TIER_ORDER.index(current)


def required_tier_for(member_count: int) -> GroupPlanTier | None:
    """Smallest tier that can hold `member_count` members.

    Returns None if `member_count` exceeds the v1 hard cap of 50 —
    caller should raise HardCapExceededError.
    """
    if member_count > HARD_MAX_GROUP_MEMBERS:
        return None
    for tier in _TIER_ORDER:
        if member_count <= TIER_MEMBER_CAPS[tier]:
            return tier
    return None


def can_accept_members(tier: GroupPlanTier, proposed_count: int) -> bool:
    """True iff `proposed_count` (active+pending) fits within both the tier
    cap and the hard cap."""
    if proposed_count > HARD_MAX_GROUP_MEMBERS:
        return False
    return proposed_count <= TIER_MEMBER_CAPS[tier]
