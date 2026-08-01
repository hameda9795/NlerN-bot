"""Admin broadcast: segment targeting and the rate-limited send loop.

Kept separate from ``admin_service`` because it needs a live ``Bot`` instance
to actually send messages (see ``run_broadcast``), not just DB reads.
"""

from __future__ import annotations

from database.connection import get_db_session
from database.models import Subscription, User
from services import subscription_service as subs
from sqlalchemy import select

SEGMENTS: dict[str, str] = {
    "all": "همه‌ی کاربران",
    "never_subscribed": "هرگز مشترک نشده",
    "lapsed": "trial/اشتراک منقضی‌شده",
    "active": "مشترک فعال الان",
}


async def resolve_segment_user_ids(segment: str) -> list[int]:
    """Return the target `User.id` list for a segment.

    Raises ``ValueError`` for an unrecognized segment key.
    """
    if segment not in SEGMENTS:
        raise ValueError(f"Unknown segment: {segment}")

    async with get_db_session() as session:
        all_user_ids = list(await session.scalars(select(User.id)))
        if segment == "all":
            return all_user_ids
        all_subs = list(await session.scalars(select(Subscription)))

    subscribed_ids = {sub.user_id for sub in all_subs}
    if segment == "never_subscribed":
        return [uid for uid in all_user_ids if uid not in subscribed_ids]

    active_ids = {sub.user_id for sub in all_subs if subs.is_active(sub)}
    if segment == "active":
        return [uid for uid in all_user_ids if uid in active_ids]

    # segment == "lapsed": has a subscription row, but it's not currently active
    return [uid for uid in all_user_ids if uid in subscribed_ids and uid not in active_ids]
