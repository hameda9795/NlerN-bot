"""Inline keyboards for the subscription paywall and status screens."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def subscribe_keyboard(checkout_url: str) -> InlineKeyboardMarkup:
    """A single URL button opening the membership site for iDEAL payment."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 پرداخت با iDEAL", url=checkout_url)]
        ]
    )


def subscription_keyboard(
    checkout_url: str,
    *,
    account_url: str | None = None,
    show_trial: bool = False,
) -> InlineKeyboardMarkup:
    """Build the keyboard shown on the paywall / status screen.

    ``show_trial`` adds the free-trial button on top; ``account_url`` (when the
    user already has a subscription row) adds a "manage subscription" link at
    the bottom, opening the standalone account page.
    """
    rows: list[list[InlineKeyboardButton]] = []
    if show_trial:
        rows.append(
            [InlineKeyboardButton(text="🎁 شروع تست ۱ روزه رایگان", callback_data="sub:trial")]
        )
    rows.append([InlineKeyboardButton(text="💳 پرداخت با iDEAL", url=checkout_url)])
    if account_url is not None:
        rows.append([InlineKeyboardButton(text="⚙️ مدیریت اشتراک", url=account_url)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
