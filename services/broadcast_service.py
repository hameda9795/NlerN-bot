"""Admin broadcast: segment targeting and the rate-limited send loop.

Kept separate from ``admin_service`` because it needs a live ``Bot`` instance
to actually send messages (see ``run_broadcast``), not just DB reads.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter

from database.connection import get_db_session
from database.models import Broadcast, Subscription, User
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


logger = logging.getLogger(__name__)

BROADCAST_DELAY_SECONDS = 0.05
STATUS_UPDATE_INTERVAL_SECONDS = 5.0

_broadcast_running = False


def is_broadcast_running() -> bool:
    return _broadcast_running


async def _safe_edit_status(bot: Bot, chat_id: int, message_id: int, text: str) -> None:
    try:
        await bot.edit_message_text(text, chat_id=chat_id, message_id=message_id)
    except Exception:
        logger.exception("Failed to edit broadcast status message")


async def run_broadcast(
    bot: Bot,
    *,
    admin_user_id: int,
    segment: str,
    message_html: str,
    status_chat_id: int,
    status_message_id: int,
) -> None:
    """Send ``message_html`` to every user in ``segment``, rate-limited.

    Runs as a detached background task (see ``handlers/admin.py``). Never
    raises — every per-recipient error is caught, classified, and counted so
    one bad send can't stop the rest of the broadcast.
    """
    global _broadcast_running
    _broadcast_running = True
    try:
        target_user_ids = await resolve_segment_user_ids(segment)
        async with get_db_session() as session:
            users = list(
                await session.scalars(select(User).where(User.id.in_(target_user_ids)))
            )

        async with get_db_session() as session:
            broadcast = Broadcast(
                admin_user_id=admin_user_id,
                segment=segment,
                message_html=message_html,
                target_count=len(users),
                started_at=datetime.now(timezone.utc),
            )
            session.add(broadcast)
            await session.flush()
            await session.refresh(broadcast)
            broadcast_id = broadcast.id

        sent = blocked = failed = 0
        last_update = time.monotonic()

        for tg_user in users:
            try:
                await bot.send_message(tg_user.telegram_id, message_html, parse_mode="HTML")
                sent += 1
            except TelegramForbiddenError:
                blocked += 1
            except TelegramRetryAfter as exc:
                await asyncio.sleep(exc.retry_after)
                try:
                    await bot.send_message(tg_user.telegram_id, message_html, parse_mode="HTML")
                    sent += 1
                except Exception:
                    failed += 1
                    logger.exception("Broadcast retry failed for user %s", tg_user.telegram_id)
            except Exception:
                failed += 1
                logger.exception("Broadcast send failed for user %s", tg_user.telegram_id)

            await asyncio.sleep(BROADCAST_DELAY_SECONDS)

            now = time.monotonic()
            if now - last_update >= STATUS_UPDATE_INTERVAL_SECONDS:
                last_update = now
                await _safe_edit_status(
                    bot,
                    status_chat_id,
                    status_message_id,
                    f"🚀 در حال ارسال…\nارسال‌شده: {sent + blocked + failed}/{len(users)}",
                )

        await _safe_edit_status(
            bot,
            status_chat_id,
            status_message_id,
            f"✅ ارسال کامل شد!\nموفق: {sent}\nمسدود شده: {blocked}\nخطا: {failed}",
        )

        async with get_db_session() as session:
            row = await session.get(Broadcast, broadcast_id)
            row.sent_count = sent
            row.blocked_count = blocked
            row.failed_count = failed
            row.finished_at = datetime.now(timezone.utc)
    finally:
        _broadcast_running = False
