"""Middleware that auto-registers users and tracks activity.

On every incoming event it ensures a ``User`` row exists for the Telegram
user, updates ``last_active_at``, and injects the user object into the
handler data as ``data["user"]``.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User as TgUser
from sqlalchemy import select

from database.connection import get_db_session
from database.models import User
from utils.admin import is_admin, reset_current_is_admin, set_current_is_admin

logger = logging.getLogger(__name__)


class UserMiddleware(BaseMiddleware):
    """Register new users and refresh activity for existing ones."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user: TgUser | None = data.get("event_from_user")

        if tg_user is not None and not tg_user.is_bot:
            try:
                data["user"] = await self._get_or_create_user(tg_user)
            except Exception as exc:  # noqa: BLE001 - never break the update flow
                logger.error("UserMiddleware failed for %s: %s", tg_user.id, exc)
                data["user"] = None

        admin_token = set_current_is_admin(
            tg_user is not None and is_admin(tg_user.id)
        )
        try:
            return await handler(event, data)
        finally:
            reset_current_is_admin(admin_token)

    @staticmethod
    async def _get_or_create_user(tg_user: TgUser) -> User:
        """Fetch the user by telegram_id, creating it if missing."""
        now = datetime.now(timezone.utc)
        async with get_db_session() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == tg_user.id)
            )
            user = result.scalar_one_or_none()

            if user is None:
                user = User(
                    telegram_id=tg_user.id,
                    username=tg_user.username,
                    first_name=tg_user.first_name,
                    last_name=tg_user.last_name,
                    language_code=tg_user.language_code,
                    current_cefr_level="A0",
                    subscription_tier="free",
                    created_at=now,
                    last_active_at=now,
                )
                session.add(user)
                logger.info("Registered new user telegram_id=%s", tg_user.id)
            else:
                user.last_active_at = now
                # Keep profile fields fresh in case the user renamed themselves.
                user.username = tg_user.username
                user.first_name = tg_user.first_name
                user.last_name = tg_user.last_name

            await session.flush()
            await session.refresh(user)
            return user
