"""Access gate: every feature requires an active subscription.

Runs after :class:`UserMiddleware` (so ``data["user"]`` is set). A small
whitelist (/start, /help, /cancel, /subscribe, /contact and the «اشتراک»/
«تماس با مدیریت» buttons) always passes so users can reach the paywall or
support. Admins (``ADMIN_USER_ID``) bypass the gate entirely — handy for
testing without paying.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot.config import get_settings
from database.models import User
from handlers.contact_admin import ContactStates
from handlers.subscription import build_paywall
from keyboards.main_menu import BTN_CONTACT_ADMIN, BTN_SUBSCRIBE
from services import subscription_service as subs

logger = logging.getLogger(__name__)

# Commands that must work without an active subscription.
_ALLOWED_COMMANDS = {"start", "help", "cancel", "subscribe", "contact"}
# Callback-data prefixes that must work without a subscription (reserved).
_ALLOWED_CB_PREFIXES = ("sub:", "contact:")


def _command(text: str | None) -> str | None:
    """Return the bare command name from a message text, if any."""
    if not text or not text.startswith("/"):
        return None
    return text[1:].split(maxsplit=1)[0].split("@", 1)[0].lower()


def _is_whitelisted(event: TelegramObject, raw_state: str | None) -> bool:
    """True if this update may pass the gate without a subscription."""
    if raw_state == ContactStates.messaging.state:
        return True  # mid-conversation with support — any message type
    if isinstance(event, Message):
        return (
            _command(event.text) in _ALLOWED_COMMANDS
            or event.text in (BTN_SUBSCRIBE, BTN_CONTACT_ADMIN)
        )
    if isinstance(event, CallbackQuery):
        return bool(event.data) and event.data.startswith(_ALLOWED_CB_PREFIXES)
    return True


class SubscriptionMiddleware(BaseMiddleware):
    """Block feature access for users without an active subscription."""

    def __init__(self) -> None:
        self._admin_ids = set(get_settings().bot.admin_ids)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: User | None = data.get("user")

        # Let it through: no user yet (start can recover), admins, or whitelist.
        if (
            user is None
            or user.telegram_id in self._admin_ids
            or _is_whitelisted(event, data.get("raw_state"))
        ):
            return await handler(event, data)

        if await subs.has_active_subscription(user_id=user.id):
            return await handler(event, data)

        await self._deny(event, user.id)
        return None  # stop: do not call the feature handler

    @staticmethod
    async def _deny(event: TelegramObject, user_id: int) -> None:
        """Show the paywall instead of running the gated handler."""
        text, keyboard = await build_paywall(user_id)
        if isinstance(event, Message):
            await event.answer(text, reply_markup=keyboard)
        elif isinstance(event, CallbackQuery):
            await event.answer("🔒 برای این بخش به اشتراک نیاز داری.", show_alert=True)
            if event.message is not None:
                await event.message.answer(text, reply_markup=keyboard)
