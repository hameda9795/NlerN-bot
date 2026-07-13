"""B2 'common words' browsing + saved 'hard words' review.

Two flows, both reached from the main menu:

* "📖 لغات پرکاربرد B2" — show 10 random words from the remote vocabulary
  library one by one; the user can save the hard ones to practise later.
* "⭐ کلمات سخت من" — review the words the user saved, reveal the meaning,
  and remove them once learned.

Words are *read* from the remote PostgreSQL library (``services.vocab_service``);
saved words are stored in the bot's own database (``services.saved_word_service``).
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.config import get_settings
from database.models import User
from keyboards.main_menu import (
    BTN_SAVED_WORDS,
    BTN_VOCAB_B2,
    get_main_menu_keyboard,
)
from keyboards.vocab_keyboard import (
    browse_finished_keyboard,
    browse_keyboard,
    saved_review_keyboard,
)
from services import saved_word_service as saved_svc
from services import vocab_service as vocab
from services.vocab_service import VocabWord

logger = logging.getLogger(__name__)

router = Router(name="vocab_b2")

_settings = get_settings()
BATCH_SIZE = 10

_DISABLED_MSG = (
    "📖 کتابخانه‌ی واژگان فعلاً در دسترس نیست.\n"
    "<i>(VOCAB_DATABASE_URL تنظیم نشده.)</i>"
)
_REMOTE_ERROR_MSG = (
    "⚠️ ارتباط با سرور کلمات برقرار نشد. چند لحظه‌ی دیگر دوباره امتحان کن."
)
_EXPIRED_MSG = "این نشست تموم شده 🙂 دوباره از منو «📖 لغات پرکاربرد B2» رو بزن."


class VocabStates(StatesGroup):
    browsing = State()


class SavedStates(StatesGroup):
    reviewing = State()


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------
def _format_word(
    *, nederlands: str, persian: str | None, pronunciation: str | None,
    category: str | None, reveal: bool = True,
) -> str:
    head = f"🔤 <b>{nederlands}</b>"
    if pronunciation:
        head += f"  🗣 <i>{pronunciation}</i>"
    text = head
    if reveal and persian:
        text += f"\n➡️ <b>{persian}</b>"
    if category:
        text += f"\n\n🗂 <i>{category}</i>"
    return text


def _word_dict(w: VocabWord) -> dict:
    return {
        "id": w.id,
        "nederlands": w.nederlands,
        "persian": w.persian,
        "pronunciation": w.pronunciation,
        "category": w.category,
    }


# ---------------------------------------------------------------------------
# Flow 1: browse B2 words
# ---------------------------------------------------------------------------
async def _start_browse(message: Message, state: FSMContext) -> None:
    if not _settings.database.vocab_enabled:
        await message.answer(_DISABLED_MSG, reply_markup=get_main_menu_keyboard())
        return
    try:
        words = await vocab.get_random_words(limit=BATCH_SIZE)
    except Exception as exc:  # noqa: BLE001 - show a friendly message, never crash
        logger.error("Failed to load vocabulary words: %s", exc)
        await message.answer(_REMOTE_ERROR_MSG, reply_markup=get_main_menu_keyboard())
        return

    if not words:
        await message.answer(
            "کلمه‌ای پیدا نشد.", reply_markup=get_main_menu_keyboard()
        )
        return

    await state.set_state(VocabStates.browsing)
    await state.set_data(
        {"queue": [_word_dict(w) for w in words], "index": 0, "saved": []}
    )
    await message.answer(
        f"📖 <b>لغات پرکاربرد B2</b> — {len(words)} کلمه‌ی تصادفی\n"
        "<i>هر کدوم سخت بود، ذخیره کن تا بعداً تمرین کنی.</i>"
    )
    await _send_browse_card(message, state, new=True)


async def _send_browse_card(
    message: Message, state: FSMContext, *, new: bool
) -> None:
    """Render the current word. ``new`` sends a fresh message; else edits."""
    data = await state.get_data()
    queue: list[dict] = data["queue"]
    index: int = data["index"]
    saved: list[int] = data["saved"]
    word = queue[index]

    text = (
        f"<b>کلمه‌ی {index + 1} از {len(queue)}</b>\n\n"
        + _format_word(
            nederlands=word["nederlands"],
            persian=word["persian"],
            pronunciation=word["pronunciation"],
            category=word["category"],
        )
    )
    keyboard = browse_keyboard(
        position=index + 1, total=len(queue), saved=word["id"] in saved
    )
    if new:
        await message.answer(text, reply_markup=keyboard)
    else:
        await message.edit_text(text, reply_markup=keyboard)


@router.message(Command("vocab"))
@router.message(F.text == BTN_VOCAB_B2)
async def cmd_vocab(message: Message, state: FSMContext) -> None:
    await _start_browse(message, state)


@router.callback_query(F.data == "vocab:save")
async def vocab_save(
    callback: CallbackQuery, state: FSMContext, user: User | None
) -> None:
    data = await state.get_data()
    if not data.get("queue") or user is None:
        await callback.answer(_EXPIRED_MSG, show_alert=True)
        return
    queue: list[dict] = data["queue"]
    word = queue[data["index"]]

    added = await saved_svc.save_word(
        user_id=user.id,
        word=VocabWord(
            id=word["id"],
            nederlands=word["nederlands"],
            persian=word["persian"],
            pronunciation=word["pronunciation"],
            category=word["category"],
        ),
    )
    saved: list[int] = data["saved"]
    if word["id"] not in saved:
        saved.append(word["id"])
        await state.update_data(saved=saved)
    await callback.answer("ذخیره شد ⭐" if added else "قبلاً ذخیره شده بود ✅")
    await _send_browse_card(callback.message, state, new=False)


@router.callback_query(F.data == "vocab:noop")
async def vocab_noop(callback: CallbackQuery) -> None:
    await callback.answer("این کلمه ذخیره شده ✅")


@router.callback_query(F.data == "vocab:next")
async def vocab_next(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    if not data.get("queue"):
        await callback.answer(_EXPIRED_MSG, show_alert=True)
        return
    queue: list[dict] = data["queue"]
    index = data["index"] + 1
    await callback.answer()

    if index < len(queue):
        await state.update_data(index=index)
        await _send_browse_card(callback.message, state, new=False)
    else:
        saved_count = len(data["saved"])
        await callback.message.edit_text(
            f"🎉 <b>تموم شد!</b> {len(queue)} کلمه رو دیدی.\n"
            f"⭐ {saved_count} کلمه برای تمرین ذخیره کردی.\n\n"
            "<i>Goed gedaan!</i>",
            reply_markup=browse_finished_keyboard(),
        )


@router.callback_query(F.data == "vocab:more")
async def vocab_more(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await _start_browse(callback.message, state)


@router.callback_query(F.data == "vocab:menu")
async def vocab_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.answer(
        "برگشتی به منوی اصلی. 🏠", reply_markup=get_main_menu_keyboard()
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Flow 2: review saved 'hard' words
# ---------------------------------------------------------------------------
async def _start_saved_review(
    message: Message, state: FSMContext, user: User | None
) -> None:
    if user is None:
        await message.answer("یه لحظه دوباره /start رو بزن. 🙏")
        return
    words = await saved_svc.list_saved_words(user_id=user.id)
    if not words:
        await message.answer(
            "هنوز هیچ کلمه‌ای ذخیره نکردی. ⭐\n"
            "از «📂 واژگان» کلمه‌های سختت رو ذخیره کن تا اینجا بیان.",
            reply_markup=get_main_menu_keyboard(),
        )
        return

    queue = [
        {
            "id": w.id,
            "nederlands": w.nederlands,
            "persian": w.persian,
            "pronunciation": w.pronunciation,
            "category": w.category,
        }
        for w in words
    ]
    await state.set_state(SavedStates.reviewing)
    await state.set_data({"queue": queue, "index": 0})
    await message.answer(
        f"⭐ <b>کلمات سخت من</b> — {len(queue)} کلمه\n"
        "<i>معنی رو حدس بزن، بعد نمایش بده.</i>"
    )
    await _send_saved_card(message, state, new=True)


async def _send_saved_card(
    message: Message, state: FSMContext, *, new: bool, reveal: bool = False
) -> None:
    data = await state.get_data()
    queue: list[dict] = data["queue"]
    index: int = data["index"]
    word = queue[index]
    text = (
        f"<b>{index + 1} از {len(queue)}</b>\n\n"
        + _format_word(
            nederlands=word["nederlands"],
            persian=word["persian"],
            pronunciation=word["pronunciation"],
            category=word["category"],
            reveal=reveal,
        )
    )
    keyboard = saved_review_keyboard(saved_word_id=word["id"], revealed=reveal)
    if new:
        await message.answer(text, reply_markup=keyboard)
    else:
        await message.edit_text(text, reply_markup=keyboard)


async def _advance_saved(callback: CallbackQuery, state: FSMContext) -> None:
    """Show the next saved word, or finish if the queue is exhausted."""
    data = await state.get_data()
    queue: list[dict] = data["queue"]
    index = data["index"]
    if index < len(queue):
        await _send_saved_card(callback.message, state, new=False)
    else:
        await state.clear()
        await callback.message.edit_text(
            "🎉 <b>مرور کلمات سخت تموم شد!</b>\n<i>Tot de volgende keer!</i>"
        )
        await callback.message.answer(
            "برگشتی به منوی اصلی. 🏠", reply_markup=get_main_menu_keyboard()
        )


@router.message(Command("saved"))
@router.message(F.text == BTN_SAVED_WORDS)
async def cmd_saved(message: Message, state: FSMContext, user: User | None) -> None:
    await _start_saved_review(message, state, user)


@router.callback_query(SavedStates.reviewing, F.data.startswith("saved:show:"))
async def saved_show(callback: CallbackQuery, state: FSMContext) -> None:
    await _send_saved_card(callback.message, state, new=False, reveal=True)
    await callback.answer()


@router.callback_query(SavedStates.reviewing, F.data.startswith("saved:del:"))
async def saved_delete(
    callback: CallbackQuery, state: FSMContext, user: User | None
) -> None:
    saved_word_id = int(callback.data.rsplit(":", 1)[1])
    if user is not None:
        await saved_svc.delete_saved_word(
            user_id=user.id, saved_word_id=saved_word_id
        )
    data = await state.get_data()
    queue: list[dict] = data["queue"]
    # Drop the current word; index now points at the following one.
    queue = [w for w in queue if w["id"] != saved_word_id]
    await state.update_data(queue=queue)
    await callback.answer("آفرین! حذف شد ✅")
    if not queue:
        await state.clear()
        await callback.message.edit_text(
            "🎉 <b>همه‌ی کلمات سخت رو یاد گرفتی!</b> عالیه."
        )
        await callback.message.answer(
            "برگشتی به منوی اصلی. 🏠", reply_markup=get_main_menu_keyboard()
        )
        return
    await _advance_saved(callback, state)


@router.callback_query(SavedStates.reviewing, F.data == "saved:next")
async def saved_next(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await state.update_data(index=data["index"] + 1)
    await callback.answer()
    await _advance_saved(callback, state)


@router.callback_query(F.data == "saved:menu")
async def saved_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.answer(
        "برگشتی به منوی اصلی. 🏠", reply_markup=get_main_menu_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "vocab:saved")
async def vocab_to_saved(
    callback: CallbackQuery, state: FSMContext, user: User | None
) -> None:
    await callback.answer()
    await _start_saved_review(callback.message, state, user)
