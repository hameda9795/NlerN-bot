"""Inline keyboards for the KNM exam flow."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from services.knm_service import KnmGroup


def _group_label(group: KnmGroup) -> str:
    """One row per group, carrying its own progress so the menu needs no legend."""
    span = f"دسته {group.index + 1} · {group.first_number}–{group.last_number}"
    if group.is_finished:
        return f"✅ {span} — تمام ({group.correct}/{group.total} درست)"
    if group.is_untouched:
        return f"{span} — شروع نشده"
    return f"▶️ {span} — {group.answered}/{group.total}"


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


def answer_keyboard(option_keys: list[str]) -> InlineKeyboardMarkup:
    """One button per option — however many the question has — then an exit."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=key, callback_data=f"knm:ans:{key}")
                for key in option_keys
            ],
            [InlineKeyboardButton(text="⏹ پایان", callback_data="knm:stop")],
        ]
    )


def after_answer_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="▶️ سؤال بعدی", callback_data="knm:next")],
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
