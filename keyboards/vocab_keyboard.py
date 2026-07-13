"""Inline keyboards for the B2 vocabulary browsing and saved-words flows."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def browse_keyboard(*, position: int, total: int, saved: bool) -> InlineKeyboardMarkup:
    """Keyboard under each browsed word.

    ``position``/``total`` drive the progress label; ``saved`` toggles the
    save button between 'save' and 'already saved'.
    """
    save_btn = (
        InlineKeyboardButton(text="✅ ذخیره شد", callback_data="vocab:noop")
        if saved
        else InlineKeyboardButton(text="💾 سخت بود، ذخیره کن", callback_data="vocab:save")
    )
    last = position >= total
    next_btn = InlineKeyboardButton(
        text="🏁 پایان" if last else "➡️ بعدی",
        callback_data="vocab:next",
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [save_btn],
            [next_btn],
            [InlineKeyboardButton(text="🏠 منو", callback_data="vocab:menu")],
        ]
    )


def browse_finished_keyboard() -> InlineKeyboardMarkup:
    """Keyboard shown after the 10-word batch is finished."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔁 ۱۰ تای دیگه", callback_data="vocab:more")],
            [InlineKeyboardButton(text="⭐ کلمات سخت من", callback_data="vocab:saved")],
            [InlineKeyboardButton(text="🏠 منو", callback_data="vocab:menu")],
        ]
    )


def saved_review_keyboard(*, saved_word_id: int, revealed: bool) -> InlineKeyboardMarkup:
    """Keyboard for reviewing one saved word.

    Before reveal: show the 'reveal meaning' button. After reveal: allow
    deleting (learned) or moving to the next saved word.
    """
    if not revealed:
        rows = [
            [
                InlineKeyboardButton(
                    text="👁 نمایش معنی",
                    callback_data=f"saved:show:{saved_word_id}",
                )
            ]
        ]
    else:
        rows = [
            [
                InlineKeyboardButton(
                    text="✅ یاد گرفتم (حذف)",
                    callback_data=f"saved:del:{saved_word_id}",
                )
            ],
            [InlineKeyboardButton(text="➡️ بعدی", callback_data="saved:next")],
        ]
    rows.append([InlineKeyboardButton(text="🏠 منو", callback_data="saved:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
