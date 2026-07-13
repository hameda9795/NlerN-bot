"""Pronunciation practice handler (TTS + Whisper).

Entered via /pronounce. The user picks a difficult Dutch sound (or types any
word), hears the target audio, records a voice message, and gets a similarity
score with Persian feedback.
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from keyboards.main_menu import BTN_PRONUNCIATION, get_main_menu_keyboard
from services import pronunciation_service as ps

logger = logging.getLogger(__name__)

router = Router(name="pronunciation")


class PronounceStates(StatesGroup):
    choosing = State()
    recording = State()


def _sounds_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=str(data["title"]), callback_data=f"pron:sound:{key}"
            )
        ]
        for key, data in ps.DIFFICULT_SOUNDS.items()
    ]
    rows.append([InlineKeyboardButton(text="🏠 منو", callback_data="pron:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _after_result_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔁 تمرین دوباره", callback_data="pron:again"),
                InlineKeyboardButton(text="➡️ کلمه بعدی", callback_data="pron:next"),
            ],
            [InlineKeyboardButton(text="🏠 منو", callback_data="pron:menu")],
        ]
    )


@router.message(Command("pronounce"))
@router.message(F.text == BTN_PRONUNCIATION)
async def cmd_pronounce(message: Message, state: FSMContext) -> None:
    if ps.get_openai_client() is None:
        await message.answer(
            "🎤 تمرین تلفظ به کلید OpenAI نیاز داره که هنوز تنظیم نشده.\n"
            "وقتی کلید رو توی فایل .env گذاشتی، این بخش فعال می‌شه.",
            reply_markup=get_main_menu_keyboard(),
        )
        return
    await state.set_state(PronounceStates.choosing)
    await message.answer(
        "🎤 <b>تمرین تلفظ</b>\n\n"
        "یکی از صداهای سخت هلندی رو انتخاب کن، یا هر کلمه‌ی هلندی‌ای که می‌خوای رو تایپ کن:",
        reply_markup=_sounds_keyboard(),
    )


async def _present_target(message: Message, state: FSMContext, target: str) -> None:
    """Send the target audio and ask the user to record."""
    await state.update_data(target=target)
    await state.set_state(PronounceStates.recording)
    try:
        audio, _cost = await ps.generate_target_audio(target)
    except ps.PronunciationError:
        await message.answer("نتونستم صدا رو بسازم. بعداً دوباره امتحان کن. 🙏")
        return
    await message.answer_audio(
        BufferedInputFile(audio, filename=f"{target}.mp3"),
        caption=f"🎧 به تلفظ <b>{target}</b> گوش بده، بعد خودت <b>🎤 ضبط کن</b> و بفرست.",
    )


@router.callback_query(PronounceStates.choosing, F.data.startswith("pron:sound:"))
async def choose_sound(callback: CallbackQuery, state: FSMContext) -> None:
    key = callback.data.split(":")[2]
    sound = ps.DIFFICULT_SOUNDS.get(key)
    await callback.answer()
    if not sound:
        return
    target = str(sound["words"][0])
    await callback.message.answer(
        f"🔊 <b>{sound['title']}</b>\n{sound['hint']}\n\n"
        f"کلمه‌ی تمرین: <b>{target}</b>"
    )
    await _present_target(callback.message, state, target)


@router.message(PronounceStates.choosing, F.text)
async def choose_typed_word(message: Message, state: FSMContext) -> None:
    target = message.text.strip()
    await _present_target(message, state, target)


@router.message(PronounceStates.recording, F.voice)
async def handle_voice(message: Message, state: FSMContext) -> None:
    """Transcribe the user's recording and score it against the target."""
    data = await state.get_data()
    target = data.get("target", "")

    file = await message.bot.get_file(message.voice.file_id)
    buffer = await message.bot.download_file(file.file_path)
    audio_bytes = buffer.read()

    try:
        heard, _cost = await ps.transcribe_user_audio(audio_bytes)
    except ps.PronunciationError:
        await message.answer("نتونستم صدا رو تشخیص بدم. یه بار دیگه امتحان کن. 🙏")
        return

    result = ps.compare_pronunciation(target, heard)
    await message.answer(
        f"🎯 <b>نتیجه‌ی تلفظ «{target}»</b>\n"
        f"دقت: <b>{result['accuracy_score']}٪</b>\n"
        f"چیزی که شنیدم: «{result['heard'] or '—'}»\n\n"
        f"{result['feedback_message']}",
        reply_markup=_after_result_keyboard(),
    )


@router.message(PronounceStates.recording)
async def expecting_voice(message: Message) -> None:
    await message.answer("لطفاً یک پیام صوتی 🎤 ضبط کن و بفرست (نه متن).")


@router.callback_query(F.data == "pron:again")
async def practice_again(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    target = data.get("target")
    await callback.answer()
    if target:
        await _present_target(callback.message, state, target)


@router.callback_query(F.data == "pron:next")
async def practice_next(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(PronounceStates.choosing)
    await callback.message.answer(
        "صدا یا کلمه‌ی بعدی رو انتخاب کن:", reply_markup=_sounds_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "pron:menu")
async def pron_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.answer(
        "برگشتی به منوی اصلی. 🏠", reply_markup=get_main_menu_keyboard()
    )
    await callback.answer()
