"""Temporary handlers for menu buttons whose features arrive in later phases.

Keeps the bot responsive instead of silently ignoring these buttons.
Remove a handler here once its real feature is implemented.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message

from keyboards.main_menu import (
    BTN_PROGRESS,
    BTN_SETTINGS,
    get_main_menu_keyboard,
)

router = Router(name="placeholders")

_COMING_SOON = {
    BTN_PROGRESS: "📊 پیشرفت من به‌زودی (فاز ۴) اضافه می‌شه.",
    BTN_SETTINGS: "⚙️ تنظیمات به‌زودی اضافه می‌شه.",
}


@router.message(F.text.in_(set(_COMING_SOON)))
async def coming_soon(message: Message) -> None:
    text = _COMING_SOON.get(message.text, "این بخش به‌زودی اضافه می‌شه.")
    await message.answer(
        f"{text}\n\nفعلاً می‌تونی از «📂 واژگان»، «📝 امتحان»، «⭐ کلمات سخت من» یا «🎤 تمرین تلفظ» استفاده کنی.",
        reply_markup=get_main_menu_keyboard(),
    )
