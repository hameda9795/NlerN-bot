"""Inline keyboards for the in-bot admin dashboard (see ``handlers/admin.py``)."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def overview_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 کاربران", callback_data="admin:users")],
        [InlineKeyboardButton(text="⚠️ نیاز به پیگیری", callback_data="admin:pastdue")],
        [InlineKeyboardButton(text="💳 پرداخت‌ها", callback_data="admin:pay")],
        [InlineKeyboardButton(text="📢 پیام همگانی", callback_data="admin:bc")],
    ])


def users_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 جستجو", callback_data="admin:users:find")],
        [InlineKeyboardButton(text="📋 همه‌ی کاربران", callback_data="admin:users:all")],
        [InlineKeyboardButton(text="↩️ بازگشت", callback_data="admin:home")],
    ])


def _pagination_row(kind: str, index: int, total: int) -> list[InlineKeyboardButton]:
    row = []
    if index > 0:
        row.append(InlineKeyboardButton(text="⬅️ قبلی", callback_data=f"admin:{kind}:pg:-1"))
    if index < total - 1:
        row.append(InlineKeyboardButton(text="بعدی ➡️", callback_data=f"admin:{kind}:pg:1"))
    return row


def list_row_keyboard(
    kind: str, index: int, total: int, *, user_id: int | None, back: str
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if user_id is not None:
        rows.append([InlineKeyboardButton(text="👤 پروفایل", callback_data=f"admin:u:{user_id}")])
    nav = _pagination_row(kind, index, total)
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="↩️ بازگشت", callback_data=back)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def payments_list_keyboard(index: int, total: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    nav = _pagination_row("pay", index, total)
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="📄 دریافت CSV کامل", callback_data="admin:pay:csv")])
    rows.append([InlineKeyboardButton(text="↩️ بازگشت", callback_data="admin:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def user_profile_keyboard(user_id: int, *, can_cancel: bool) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="⏳ +۷ روز", callback_data=f"admin:ext:{user_id}:7"),
            InlineKeyboardButton(text="⏳ +۳۰ روز", callback_data=f"admin:ext:{user_id}:30"),
        ],
        [InlineKeyboardButton(text="🎁 فعال‌سازی رایگان (۳۰ روز)", callback_data=f"admin:ext:{user_id}:30")],
    ]
    if can_cancel:
        rows.append([InlineKeyboardButton(text="❌ لغو اشتراک", callback_data=f"admin:cxl:{user_id}")])
    rows.append([InlineKeyboardButton(text="↩️ بازگشت", callback_data="admin:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_keyboard(yes_callback: str, cancel_user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ مطمئنم", callback_data=yes_callback),
            InlineKeyboardButton(text="↩️ انصراف", callback_data=f"admin:u:{cancel_user_id}"),
        ],
    ])


def broadcast_segment_keyboard(segments: list[tuple[str, str, int]]) -> InlineKeyboardMarkup:
    """``segments`` is a list of (segment_key, label, recipient_count)."""
    rows = [
        [
            InlineKeyboardButton(
                text=f"{label} ({count} نفر)",
                callback_data=f"admin:bc:seg:{key}",
            )
        ]
        for key, label, count in segments
    ]
    rows.append([InlineKeyboardButton(text="↩️ بازگشت", callback_data="admin:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def broadcast_preview_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧪 ارسال آزمایشی به خودم", callback_data="admin:bc:test")],
        [InlineKeyboardButton(text="🚀 ارسال نهایی", callback_data="admin:bc:go")],
        [InlineKeyboardButton(text="❌ لغو", callback_data="admin:bc:cancel")],
    ])


def broadcast_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ مطمئنم، بفرست", callback_data="admin:bc:go:confirm"),
            InlineKeyboardButton(text="↩️ انصراف", callback_data="admin:bc:cancel"),
        ],
    ])
