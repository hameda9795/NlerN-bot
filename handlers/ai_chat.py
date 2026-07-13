"""AI chat handler — Persian<->Dutch translation assistant.

Entered via /chat or the "🤖 چت با AI" menu button. While in chat mode every
text message is sent to the AI router, which translates it (word or sentence,
either direction) rather than answering its content. Conversation history
(last 10 turns) is kept in the FSM state for context.
"""

from __future__ import annotations

import html
import logging
import re

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from database.models import User
from keyboards.main_menu import BTN_AI_CHAT, get_main_menu_keyboard
from services import ai_router
from utils.admin import is_admin

logger = logging.getLogger(__name__)

router = Router(name="ai_chat")

_TELEGRAM_LIMIT = 4096
_MAX_HISTORY = 10  # turns kept (each turn = user + assistant message)

WELCOME = (
    "🤖 <b>چت با AI</b>\n\n"
    "این بخش یه مترجم فارسی↔هلندیه. هر چی بفرستی رو کوتاه و طبیعی ترجمه می‌کنه "
    "(نه اینکه بهش جواب بده). مثلاً:\n"
    "• یک جمله‌ی فارسی بفرست تا هلندیِ کوتاه و روزمره‌اش رو بگیری.\n"
    "• یک کلمه بفرست (فارسی یا هلندی) تا معنی و چند مثال بگیری.\n"
    "• یک جمله‌ی هلندی بفرست تا معنی فارسیش رو بفهمی.\n\n"
    "برای خروج /cancel یا دکمه‌ی منو رو بزن."
)


class ChatStates(StatesGroup):
    chatting = State()


def _chat_controls() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🧹 پاک‌کردن تاریخچه", callback_data="chat:clear"),
                InlineKeyboardButton(text="🏠 منو", callback_data="chat:menu"),
            ]
        ]
    )


async def _enter_chat(message: Message, state: FSMContext) -> None:
    await state.set_state(ChatStates.chatting)
    await state.update_data(history=[])
    await message.answer(WELCOME, reply_markup=_chat_controls())


@router.message(Command("chat"))
@router.message(F.text == BTN_AI_CHAT)
async def cmd_chat(message: Message, state: FSMContext, user: User | None) -> None:
    if user is None or not is_admin(user.telegram_id):
        await message.answer("🔒 این بخش فقط برای مدیر ربات در دسترسه.")
        return
    await _enter_chat(message, state)


@router.callback_query(F.data == "chat:clear")
async def clear_history(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(history=[])
    await callback.answer("تاریخچه پاک شد 🧹")


@router.callback_query(F.data == "chat:menu")
async def chat_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.answer(
        "از چت خارج شدی. 🏠", reply_markup=get_main_menu_keyboard()
    )
    await callback.answer()


_TAG_RE = re.compile(r"<[^>]+>")


def _plain_text(html_text: str) -> str:
    """Strip Telegram HTML tags before feeding a reply back into the model's
    own conversation history — otherwise it starts mimicking raw <b> tags in
    its next answer instead of following the system prompt's ** convention.
    """
    return html.unescape(_TAG_RE.sub("", html_text))


async def _send_chunked(message: Message, text: str, **kwargs) -> None:
    """Send a possibly long reply within Telegram's 4096-char limit."""
    if len(text) <= _TELEGRAM_LIMIT:
        await message.answer(text, **kwargs)
        return
    for i in range(0, len(text), _TELEGRAM_LIMIT):
        chunk = text[i : i + _TELEGRAM_LIMIT]
        is_last = i + _TELEGRAM_LIMIT >= len(text)
        await message.answer(chunk, **(kwargs if is_last else {}))


@router.message(ChatStates.chatting, F.text)
async def chat_message(
    message: Message, state: FSMContext, user: User | None
) -> None:
    """Route a chat message through the AI router and reply with context."""
    user_id = user.id if user else 0
    data = await state.get_data()
    history: list[dict[str, str]] = data.get("history", [])

    await message.bot.send_chat_action(message.chat.id, "typing")
    response = await ai_router.route_and_respond(
        user_id=user_id, message=message.text, history=history
    )

    # Update rolling history (keep last _MAX_HISTORY turns). Store plain text
    # so the model never sees its own HTML tags and starts echoing them raw.
    history.append({"role": "user", "content": message.text})
    history.append({"role": "assistant", "content": _plain_text(response.text)})
    history = history[-2 * _MAX_HISTORY :]
    await state.update_data(history=history)

    await _send_chunked(message, response.text, reply_markup=_chat_controls())
