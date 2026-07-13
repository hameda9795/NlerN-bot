"""Lightweight XP awarding shared across features.

A minimal stand-in until the full gamification service (Phase 4). It updates
``User.xp_points`` and records a ``GamificationEvent`` within the caller's
session, so it participates in the same transaction.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from database.models import GamificationEvent, User


async def award_xp(
    session: AsyncSession,
    *,
    user: User,
    event_type: str,
    amount: int,
    description: str | None = None,
) -> int:
    """Add ``amount`` XP to the user and log the event. Returns the new total."""
    user.xp_points = (user.xp_points or 0) + amount
    session.add(
        GamificationEvent(
            user_id=user.id,
            event_type=event_type,
            xp_earned=amount,
            description=description,
        )
    )
    return user.xp_points


def level_for_xp(xp: int) -> int:
    """Level formula: floor(sqrt(xp / 100)), capped at 50."""
    import math

    return min(int(math.sqrt(max(xp, 0) / 100)), 50)
