"""Contact-admin relay: "📩 تماس با مدیریت".

Lets any user (subscribed or not — this is whitelisted in
``SubscriptionMiddleware``) reach the admin directly from the bot. While the
user is in ``ContactStates.messaging``, every message they send (text, photo,
voice, anything) is copied into every configured admin's chat, prefixed with
a small header identifying the sender. When an admin replies (Telegram's
native swipe-to-reply) to one of those copies, the reply is relayed back to
that same user — see ``services/support_service.py`` for how the reply is
matched to the right user.
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from bot.config import get_settings
from database.models import User
from keyboards.main_menu import BTN_CONTACT_ADMIN, get_main_menu_keyboard
from services import support_service
from utils.admin import is_admin

logger = logging.getLogger(__name__)

router = Router(name="contact_admin")


class ContactStates(StatesGroup):
    messaging = State()


def _contact_controls() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏠 پایان و بازگشت به منو", callback_data="contact:stop")]
        ]
    )


def _sender_header(user: User) -> str:
    name = user.first_name or "کاربر"
    if user.last_name:
        name += f" {user.last_name}"
    username_line = f"\nیوزرنیم: @{user.username}" if user.username else ""
    return f"📩 <b>پیام جدید از {name}</b>{username_line}\nآیدی عددی: <code>{user.telegram_id}</code>"


@router.message(Command("contact"))
@router.message(F.text == BTN_CONTACT_ADMIN)
async def cmd_contact(message: Message, state: FSMContext) -> None:
    if not get_settings().bot.admin_ids:
        await message.answer("⚠️ پشتیبانی موقتاً در دسترس نیست.")
        return
    await state.set_state(ContactStates.messaging)
    await message.answer(
        "📩 <b>تماس با مدیریت</b>\n\n"
        "هر چی می‌خوای بگو (متن، عکس، صدا، هرچی) — مستقیم برای مدیریت ارسال می‌شه "
        "و جواب رو همینجا می‌گیری.\n\n"
        "برای خروج /cancel رو بزن.",
        reply_markup=_contact_controls(),
    )


@router.callback_query(F.data == "contact:stop")
async def contact_stop(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if callback.message is not None:
        await callback.message.answer(
            "از بخش تماس با مدیریت خارج شدی. 🏠", reply_markup=get_main_menu_keyboard()
        )
    await callback.answer()


@router.message(ContactStates.messaging)
async def relay_to_admins(message: Message, user: User | None) -> None:
    """Copy the user's message into every admin's chat and track it for replies."""
    if user is None:
        return
    admin_ids = get_settings().bot.admin_ids
    if not admin_ids:
        await message.answer("⚠️ پشتیبانی موقتاً در دسترس نیست.")
        return

    header = _sender_header(user)
    delivered = False
    for admin_id in admin_ids:
        try:
            header_msg = await message.bot.send_message(admin_id, header)
            copied = await message.copy_to(admin_id)
        except TelegramAPIError:
            logger.warning("Failed to relay support message to admin %s", admin_id, exc_info=True)
            continue
        await support_service.record_relay(
            user_id=user.id, admin_chat_id=admin_id, admin_message_id=header_msg.message_id
        )
        await support_service.record_relay(
            user_id=user.id, admin_chat_id=admin_id, admin_message_id=copied.message_id
        )
        delivered = True

    if delivered:
        await message.answer("✅ پیامت برای مدیریت ارسال شد. جواب رو همینجا بهت می‌دم.")
    else:
        await message.answer("⚠️ در ارسال پیام مشکلی پیش اومد، لطفاً بعداً دوباره امتحان کن.")


async def _admin_reply_target(message: Message) -> bool | dict:
    """Filter + data-injector: True only if this is an admin replying to a tracked relay."""
    if message.reply_to_message is None or message.from_user is None:
        return False
    if not is_admin(message.from_user.id):
        return False
    target_user = await support_service.find_user_for_reply(
        admin_chat_id=message.chat.id,
        admin_message_id=message.reply_to_message.message_id,
    )
    if target_user is None:
        return False
    return {"support_target": target_user}


@router.message(F.reply_to_message, _admin_reply_target)
async def relay_admin_reply(message: Message, support_target: User) -> None:
    """Relay an admin's reply-to back to the original user."""
    try:
        await message.bot.send_message(support_target.telegram_id, "👨‍💼 <b>پاسخ مدیریت:</b>")
        await message.copy_to(support_target.telegram_id)
    except TelegramAPIError:
        logger.warning(
            "Failed to relay admin reply to user %s", support_target.telegram_id, exc_info=True
        )
        await message.reply("⚠️ ارسال به کاربر ناموفق بود (شاید ربات رو بلاک کرده).")
        return
    await message.reply("✅ برای کاربر فرستاده شد.")
