"""Subscription handler: /subscribe command and the «💳 اشتراک» button.

Shows the user's current subscription status and a button that opens the
standalone membership site to pay with iDEAL. The same ``build_paywall`` helper
is reused by the access-gate middleware so the paywall looks consistent.
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.config import get_settings
from database.models import User
from keyboards.main_menu import BTN_SUBSCRIBE
from keyboards.subscription_keyboard import subscribe_keyboard, subscription_keyboard
from services import subscription_service as subs

logger = logging.getLogger(__name__)

router = Router(name="subscription")

_settings = get_settings()
_PRICE = _settings.subscription.price_eur


def _checkout_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return subscribe_keyboard(subs.build_checkout_url(user_id))


async def build_paywall(user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    """Return the (text, keyboard) shown when a non-subscriber hits a feature."""
    trial_available = await subs.is_trial_available(user_id=user_id)
    if trial_available:
        text = (
            "🔒 <b>این بخش نیاز به اشتراک داره</b>\n\n"
            "می‌تونی ۱ روز کاملاً <b>رایگان</b> و بدون نیاز به پرداخت همه‌ی بخش‌ها رو امتحان کنی:\n"
            "📂 واژگان · 📝 امتحان · 🗣 تمرین جمله · ⭐ کلمات سخت من\n\n"
            f"بعد از یک روز، اگه خوشت اومد، با اشتراک ماهانه (<b>€{_PRICE:.2f}</b>) و "
            "پرداخت <b>iDEAL</b> ادامه بده. 🌷"
        )
    else:
        text = (
            "🔒 <b>این بخش نیاز به اشتراک داره</b>\n\n"
            f"با اشتراک ماهانه (<b>€{_PRICE:.2f}</b>) به همه‌ی بخش‌های ربات دسترسی داری:\n"
            "📂 واژگان · 📝 امتحان · 🗣 تمرین جمله · ⭐ کلمات سخت من\n\n"
            "روی دکمه‌ی زیر بزن و با <b>iDEAL</b> پرداخت کن. بعد از پرداخت، "
            "اشتراکت خودکار فعال می‌شه. 🌷"
        )
    keyboard = subscription_keyboard(subs.build_checkout_url(user_id), show_trial=trial_available)
    return text, keyboard


def _format_date(dt) -> str:
    return dt.strftime("%Y-%m-%d") if dt else "—"


async def show_subscription(message: Message, user: User | None) -> None:
    """Show subscription status and the appropriate action button."""
    if user is None:
        await message.answer("یه لحظه دوباره /start رو بزن. 🙏")
        return

    sub = await subs.get_subscription(user_id=user.id)
    account_url = subs.build_account_url(user.id) if sub is not None else None
    is_trial = sub is not None and sub.trial_used_at is not None and sub.mollie_subscription_id is None

    if subs.is_active(sub):
        until = _format_date(sub.current_period_end)
        if is_trial:
            text = (
                f"🎁 <b>روز رایگانت فعاله!</b>\n"
                f"تا <b>{until}</b> به همه‌ی بخش‌ها دسترسی داری.\n\n"
                f"اگه خوشت اومد، با اشتراک ماهانه (<b>€{_PRICE:.2f}</b>) ادامه بده."
            )
        elif sub.status == subs.STATUS_CANCELED:
            text = (
                "ℹ️ اشتراکت <b>لغو</b> شده، ولی تا "
                f"<b>{until}</b> دسترسی داری. بعد از اون تمدید خودکار نمی‌شه.\n\n"
                "اگه بخوای دوباره فعالش کنی، از دکمه‌ی زیر اقدام کن."
            )
        else:
            text = (
                "✅ <b>اشتراکت فعاله!</b>\n"
                f"تا تاریخ <b>{until}</b> به همه‌ی بخش‌ها دسترسی داری.\n"
                f"تمدید خودکار ماهانه: <b>€{_PRICE:.2f}</b>"
            )
        keyboard = subscription_keyboard(subs.build_checkout_url(user.id), account_url=account_url)
        await message.answer(text, reply_markup=keyboard)
        return

    text, keyboard = await build_paywall(user.id)
    if account_url is not None:
        keyboard.inline_keyboard.append(
            [InlineKeyboardButton(text="⚙️ مدیریت اشتراک", url=account_url)]
        )
    await message.answer(text, reply_markup=keyboard)


@router.message(Command("subscribe"))
@router.message(F.text == BTN_SUBSCRIBE)
async def cmd_subscribe(message: Message, user: User | None) -> None:
    await show_subscription(message, user)


@router.callback_query(F.data == "sub:trial")
async def cb_start_trial(callback: CallbackQuery, user: User | None) -> None:
    if user is None:
        await callback.answer("یه لحظه دوباره /start رو بزن. 🙏", show_alert=True)
        return

    sub = await subs.start_trial(user_id=user.id)
    if sub is None:
        await callback.answer("قبلاً از تست رایگان استفاده کردی. 🙏", show_alert=True)
        return

    until = _format_date(sub.current_period_end)
    await callback.answer("🎉 یک روز دسترسی رایگان فعال شد!", show_alert=True)
    if callback.message is not None:
        await callback.message.answer(
            f"🎉 <b>یک روز دسترسی رایگان فعال شد!</b>\n"
            f"تا <b>{until}</b> به همه‌ی بخش‌ها دسترسی داری. خوش بگذره! 🌷"
        )
