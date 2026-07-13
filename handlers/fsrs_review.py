"""Daily spaced-repetition review flow (FSRS).

Triggered by /review or the "🔄 مرور واژگان" menu button. The user sees a
Dutch word, reveals the Persian answer, then rates recall (Again/Hard/Good/Easy).
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.config import get_settings
from database.connection import get_db_session
from database.models import User
from keyboards.main_menu import BTN_REVIEW, get_main_menu_keyboard
from keyboards.review_keyboard import rating_keyboard, show_answer_keyboard
from services import fsrs_service as fsrs
from services.xp import award_xp

logger = logging.getLogger(__name__)

router = Router(name="fsrs_review")

_settings = get_settings()
XP_PER_REVIEW = 2


class ReviewStates(StatesGroup):
    reviewing = State()


def _card_term(card: fsrs.DueCard) -> str:
    return f"{card.article} {card.dutch_word}" if card.article else card.dutch_word


async def _send_question(message: Message, state: FSMContext) -> None:
    """Show the current card's question side."""
    data = await state.get_data()
    queue: list[fsrs.DueCard] = data["queue"]
    card = queue[0]
    await message.answer(
        f"🔤 <b>{_card_term(card)}</b>\n\n"
        "<i>معنی را به خاطر بیاور…</i>",
        reply_markup=show_answer_keyboard(card.card_id),
    )


async def _start_review(message: Message, user: User, state: FSMContext) -> None:
    level = user.current_cefr_level or "A0"
    limit = _settings.fsrs.max_daily_reviews
    cards = await fsrs.get_due_cards(user.id, limit=limit)

    if not cards:
        stats = await fsrs.get_card_stats(user.id)
        if stats["total"] == 0:
            # First-time user: seed cards from their level, then re-fetch.
            async with get_db_session() as session:
                created = await fsrs.ensure_cards_for_level(
                    session, user.id, level, limit=limit
                )
            logger.info("Seeded %d cards for user %s", created, user.id)
            cards = await fsrs.get_due_cards(user.id, limit=limit)

    if not cards:
        await message.answer(
            "امروز کارت مروری نداری! 🎉\n"
            "می‌تونی با کوییز (/quiz) یا درس‌ها واژه‌های جدید یاد بگیری.",
            reply_markup=get_main_menu_keyboard(),
        )
        return

    await state.set_state(ReviewStates.reviewing)
    await state.set_data({"queue": cards, "reviewed": 0})
    await message.answer(f"🔄 <b>مرور واژگان</b> — {len(cards)} کارت برای امروز")
    await _send_question(message, state)


@router.message(Command("review"))
@router.message(F.text == BTN_REVIEW)
async def cmd_review(message: Message, state: FSMContext, user: User | None) -> None:
    if user is None:
        await message.answer("یه لحظه دوباره /start رو بزن. 🙏")
        return
    await _start_review(message, user, state)


@router.callback_query(ReviewStates.reviewing, F.data.startswith("review:show:"))
async def show_answer(callback: CallbackQuery, state: FSMContext) -> None:
    """Reveal the answer side with the rating keyboard."""
    data = await state.get_data()
    queue: list[fsrs.DueCard] = data["queue"]
    card = queue[0]
    text = (
        f"🔤 <b>{_card_term(card)}</b>\n"
        f"➡️ <b>{card.persian_translation}</b>\n"
    )
    if card.example_dutch:
        text += f"\n<i>{card.example_dutch}</i>"
        if card.example_persian:
            text += f"\n{card.example_persian}"
    text += "\n\nچقدر خوب یادت بود؟"
    await callback.message.edit_text(text, reply_markup=rating_keyboard(card.card_id))
    await callback.answer()


@router.callback_query(ReviewStates.reviewing, F.data.startswith("review:rate:"))
async def rate_card(
    callback: CallbackQuery, state: FSMContext, user: User | None
) -> None:
    """Persist the rating, advance the queue, show next card or finish."""
    _, _, card_id_str, rating_str = callback.data.split(":")
    card_id, rating = int(card_id_str), int(rating_str)

    await fsrs.review_card(card_id, rating)

    if user is not None:
        async with get_db_session() as session:
            db_user = await session.get(User, user.id)
            if db_user is not None:
                await award_xp(
                    session,
                    user=db_user,
                    event_type="review_card",
                    amount=XP_PER_REVIEW,
                    description=f"card {card_id} rated {rating}",
                )

    data = await state.get_data()
    queue: list[fsrs.DueCard] = data["queue"]
    reviewed = data["reviewed"] + 1
    queue = queue[1:]  # drop the reviewed card

    await callback.answer("ثبت شد ✅")

    if queue:
        await state.update_data(queue=queue, reviewed=reviewed)
        await _send_question(callback.message, state)
    else:
        await _finish_review(callback.message, state, user, reviewed)


@router.callback_query(ReviewStates.reviewing, F.data == "review:skip")
async def skip_card(callback: CallbackQuery, state: FSMContext) -> None:
    """Move the current card to the back of the queue."""
    data = await state.get_data()
    queue: list[fsrs.DueCard] = data["queue"]
    if len(queue) > 1:
        queue = queue[1:] + queue[:1]
        await state.update_data(queue=queue)
        await callback.answer("بعداً می‌بینیمش ⏸️")
        await _send_question(callback.message, state)
    else:
        await callback.answer("این آخرین کارته 🙂")


@router.callback_query(ReviewStates.reviewing, F.data == "review:menu")
async def review_to_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.answer(
        "برگشتی به منوی اصلی. 🏠", reply_markup=get_main_menu_keyboard()
    )
    await callback.answer()


async def _finish_review(
    message: Message, state: FSMContext, user: User | None, reviewed: int
) -> None:
    await state.clear()
    earned = reviewed * XP_PER_REVIEW
    streak_line = ""
    if user is not None and user.daily_streak:
        streak_line = f"\n🔥 استریک: {user.daily_streak} روز"
    await message.answer(
        f"🎉 <b>تبریک! {reviewed} کارت مرور شد.</b>\n"
        f"+{earned} XP ⭐{streak_line}\n\n"
        "<i>Goed bezig! فردا دوباره بیا.</i>",
        reply_markup=get_main_menu_keyboard(),
    )
