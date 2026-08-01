"""Sentence-check practice: say a Dutch sentence, we verify the words (Deepgram).

Entered via /zin. The bot shows a Dutch sentence from the database, the user
records a voice message, and Deepgram Nova-3 transcribes it. The transcript is
aligned word-by-word against the target to confirm the user said it correctly.
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.filters import Command, invert_f
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from keyboards.main_menu import BTN_SENTENCE, get_main_menu_keyboard
from services import deepgram_service as dg
from services import jomelat_service as js
from utils.navigation import is_menu_navigation

logger = logging.getLogger(__name__)

router = Router(name="sentence_check")


class SentenceStates(StatesGroup):
    recording = State()


def _after_result_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔁 دوباره", callback_data="zin:again"),
                InlineKeyboardButton(text="➡️ جمله بعدی", callback_data="zin:next"),
            ],
            [InlineKeyboardButton(text="🏠 منو", callback_data="zin:menu")],
        ]
    )


async def _present_sentence(message: Message, state: FSMContext) -> None:
    """Pick a random sentence from the library, store it, and ask to record."""
    sentence = await js.get_random_sentence()
    if sentence is None:
        await message.answer("جمله‌ای توی دیتابیس پیدا نشد. 🙏")
        return
    await state.update_data(target=sentence.dutch)
    await state.set_state(SentenceStates.recording)
    hint = f"\n<i>{sentence.persian}</i>" if sentence.persian else ""
    await message.answer(
        "🗣️ این جمله رو بلند و واضح بخون، بعد <b>🎤 ضبط کن</b> و بفرست:\n\n"
        f"<b>{sentence.dutch}</b>{hint}"
    )


@router.message(Command("zin"))
@router.message(F.text == BTN_SENTENCE)
async def cmd_zin(message: Message, state: FSMContext) -> None:
    if not dg.is_enabled():
        await message.answer(
            "🎤 این تمرین به کلید Deepgram نیاز داره که هنوز تنظیم نشده.\n"
            "وقتی DEEPGRAM_API_KEY رو توی فایل .env گذاشتی، فعال می‌شه.",
            reply_markup=get_main_menu_keyboard(),
        )
        return
    if not js.is_enabled():
        await message.answer(
            "🎤 این تمرین به کتابخانه‌ی جملات (VOCAB_DATABASE_URL) نیاز داره "
            "که هنوز تنظیم نشده.",
            reply_markup=get_main_menu_keyboard(),
        )
        return
    await message.answer("🎤 <b>تمرین جمله</b> — جمله رو ببین، بخون و صداتو بفرست.")
    await _present_sentence(message, state)


@router.message(SentenceStates.recording, F.voice)
async def handle_voice(message: Message, state: FSMContext) -> None:
    """Transcribe the user's recording and check it against the target."""
    data = await state.get_data()
    target = data.get("target", "")

    file = await message.bot.get_file(message.voice.file_id)
    buffer = await message.bot.download_file(file.file_path)
    audio_bytes = buffer.read()

    try:
        result = await dg.transcribe(audio_bytes, content_type="audio/ogg")
    except dg.DeepgramError:
        await message.answer("نتونستم صدا رو تشخیص بدم. یه بار دیگه امتحان کن. 🙏")
        return

    feedback = dg.build_feedback(target, result)
    await message.answer(feedback, reply_markup=_after_result_keyboard())


@router.message(SentenceStates.recording, is_menu_navigation)
async def sentence_menu_escape(message: Message, state: FSMContext) -> None:
    """Let a main-menu button or command break out of recording mode.

    ``expecting_voice`` below excludes menu navigation from its own filter
    so it can't also match this same update — see the equivalent escape
    handler in ``handlers/contact_admin.py`` for the full explanation of
    why ``SkipHandler`` is needed here.
    """
    await state.clear()
    raise SkipHandler


@router.message(SentenceStates.recording, invert_f(is_menu_navigation))
async def expecting_voice(message: Message) -> None:
    await message.answer("لطفاً یک پیام صوتی 🎤 ضبط کن و بفرست (نه متن).")


@router.callback_query(F.data == "zin:again")
async def again(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    target = data.get("target")
    if target:
        await callback.message.answer(
            "🗣️ دوباره این جمله رو بخون و ضبط کن:\n\n" f"<b>{target}</b>"
        )
        await state.set_state(SentenceStates.recording)


@router.callback_query(F.data == "zin:next")
async def next_sentence(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await _present_sentence(callback.message, state)


@router.callback_query(F.data == "zin:menu")
async def menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.answer(
        "برگشتی به منوی اصلی. 🏠", reply_markup=get_main_menu_keyboard()
    )
    await callback.answer()
