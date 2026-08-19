"""Inline keyboards for the KNM exam flow.

Answer buttons carry the option's full Dutch text, one option per row: Telegram
wraps a long single-button label across lines, so the option list lives on the
buttons and never has to be repeated in the message body.
"""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from services.knm_service import KnmGroup, KnmOption
from utils.fa_text import fa_digits, progress_bar

# Circled letters keep the option key readable without the noise of "A)".
_CIRCLED = {"A": "Ⓐ", "B": "Ⓑ", "C": "Ⓒ", "D": "Ⓓ"}


def option_marker(key: str) -> str:
    return _CIRCLED.get(key, key)


def _group_label(group: KnmGroup) -> str:
    span = f"دسته {fa_digits(group.index + 1)}"
    if group.is_finished:
        return f"✅ {span} · {fa_digits(group.correct)}/{fa_digits(group.total)} درست"
    bar = progress_bar(group.answered, group.total)
    return f"{span} {bar} {fa_digits(group.answered)}/{fa_digits(group.total)}"


def groups_keyboard(groups: list[KnmGroup]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=_group_label(group), callback_data=f"knm:grp:{group.index}"
                )
            ]
            for group in groups
        ]
    )


def answer_keyboard(options: list[KnmOption]) -> InlineKeyboardMarkup:
    """One full-width button per option, carrying its own text."""
    rows = [
        [
            InlineKeyboardButton(
                text=f"{option_marker(option.key)}  {option.text_nl}",
                callback_data=f"knm:ans:{option.key}",
            )
        ]
        for option in options
    ]
    rows.append([InlineKeyboardButton(text="⏹ پایان", callback_data="knm:stop")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def after_answer_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="سؤال بعدی ◀️", callback_data="knm:next")],
            [
                InlineKeyboardButton(text="📋 دسته‌ها", callback_data="knm:home"),
                InlineKeyboardButton(text="⏹ پایان", callback_data="knm:stop"),
            ],
        ]
    )


def group_finished_keyboard(group_index: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 تکرار این دسته",
                    callback_data=f"knm:reset:{group_index}",
                )
            ],
            [InlineKeyboardButton(text="📋 دسته‌ها", callback_data="knm:home")],
        ]
    )


def reset_confirm_keyboard(group_index: int) -> InlineKeyboardMarkup:
    """Resetting throws away answers, so it gets its own confirmation step."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ بله، از اول",
                    callback_data=f"knm:reset:go:{group_index}",
                ),
                InlineKeyboardButton(text="↩️ بازگشت", callback_data="knm:home"),
            ]
        ]
    )


def back_to_groups_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 دسته‌ها", callback_data="knm:home")]
        ]
    )
