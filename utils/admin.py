"""Admin-status check, plus a request-scoped flag for cross-cutting UI use.

``is_admin`` is the single source of truth (reads ``ADMIN_USER_ID``) and is
what any handler doing a hard access check should call directly. The
``ContextVar`` below exists only so widely-reused, parameterless helpers like
``keyboards.main_menu.get_main_menu_keyboard`` can know the current update's
admin status without threading it through every call site — ``UserMiddleware``
sets it once per update and resets it when the handler returns.
"""

from __future__ import annotations

from contextvars import ContextVar

from bot.config import get_settings

_current_is_admin: ContextVar[bool] = ContextVar("current_is_admin", default=False)


def is_admin(telegram_id: int) -> bool:
    """True if this Telegram user id is configured as a bot admin."""
    return telegram_id in get_settings().bot.admin_ids


def set_current_is_admin(value: bool):
    """Set the current update's admin flag; returns a token for ``reset``."""
    return _current_is_admin.set(value)


def reset_current_is_admin(token) -> None:
    _current_is_admin.reset(token)


def current_is_admin() -> bool:
    """Admin status of the user handling the update currently in flight."""
    return _current_is_admin.get()
