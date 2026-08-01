"""Shared filter for handlers that capture free-form text during a multi-step
FSM flow (contact-admin relay, AI chat, voice recording, admin search, ...).

Those handlers must not swallow a main-menu button press or a slash command
as if it were flow input — see ``handlers/contact_admin.py`` for the escape
handler this filter is meant to be paired with.
"""

from __future__ import annotations

from aiogram.types import Message

from keyboards.main_menu import MENU_BUTTON_TEXTS


def is_menu_navigation(message: Message) -> bool:
    text = message.text
    if not text:
        return False
    return text in MENU_BUTTON_TEXTS or text.startswith("/")
