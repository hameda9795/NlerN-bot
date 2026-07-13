"""Main menu reply keyboard (Persian)."""

from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from utils.admin import current_is_admin

# Button labels — also matched by handlers, so keep these as the source of truth.
# Buttons shown in the main menu:
BTN_VAJEGAN = "📂 واژگان"
BTN_QUIZ = "📝 امتحان"
BTN_SENTENCE = "🗣 تمرین جمله"
BTN_SAVED_WORDS = "⭐ کلمات سخت من"
BTN_AI_CHAT = "🤖 چت با AI"
BTN_SUBSCRIBE = "💳 اشتراک"
BTN_ADMIN = "🛠 داشبورد ادمین"
BTN_CONTACT_ADMIN = "📩 تماس با مدیریت"

# Labels for features no longer shown in the menu (their handlers are not wired
# up in the dispatcher). Kept as constants so any remaining import resolves.
BTN_PRONUNCIATION = "🎤 تمرین تلفظ"
BTN_SETTINGS = "⚙️ تنظیمات"
BTN_LESSONS = "📚 درس‌های امروز"
BTN_REVIEW = "🔄 مرور واژگان"
BTN_VOCAB_B2 = "📖 لغات پرکاربرد B2"
BTN_PROGRESS = "📊 پیشرفت من"


def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Return the persistent main menu keyboard.

    The AI-chat and admin-dashboard rows are admin-only — they read the
    current update's admin flag (set per-request by ``UserMiddleware``) so
    every call site here shows the right menu without having to pass
    anything in.
    """
    rows = [
        [KeyboardButton(text=BTN_VAJEGAN), KeyboardButton(text=BTN_QUIZ)],
        [
            KeyboardButton(text=BTN_SENTENCE),
            KeyboardButton(text=BTN_SAVED_WORDS),
        ],
    ]
    if current_is_admin():
        rows.append([KeyboardButton(text=BTN_AI_CHAT)])
        rows.append([KeyboardButton(text=BTN_ADMIN)])
    rows.append([KeyboardButton(text=BTN_SUBSCRIBE), KeyboardButton(text=BTN_CONTACT_ADMIN)])
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="یک گزینه را انتخاب کن…",
    )
