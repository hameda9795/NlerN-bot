"""Keyboards for the FSRS review flow."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def show_answer_keyboard(card_id: int) -> InlineKeyboardMarkup:
    """Keyboard shown on the question side (reveal the answer)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👁 نمایش پاسخ", callback_data=f"review:show:{card_id}"
                )
            ],
            [
                InlineKeyboardButton(text="⏸️ بعداً", callback_data="review:skip"),
                InlineKeyboardButton(text="🏠 منو", callback_data="review:menu"),
            ],
        ]
    )


def rating_keyboard(card_id: int) -> InlineKeyboardMarkup:
    """Keyboard shown on the answer side (rate recall: 1=Again..4=Easy)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔴 دوباره", callback_data=f"review:rate:{card_id}:1"
                ),
                InlineKeyboardButton(
                    text="🟠 سخت", callback_data=f"review:rate:{card_id}:2"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🟢 خوب", callback_data=f"review:rate:{card_id}:3"
                ),
                InlineKeyboardButton(
                    text="🔵 آسان", callback_data=f"review:rate:{card_id}:4"
                ),
            ],
            [
                InlineKeyboardButton(text="⏸️ بعداً", callback_data="review:skip"),
                InlineKeyboardButton(text="🏠 منو", callback_data="review:menu"),
            ],
        ]
    )
