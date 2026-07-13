"""Quiz handlers with an FSM-driven multiple-choice flow.

Started with /quiz. The user picks the correct Persian translation of a Dutch
word from four options. Score is tracked in FSM state for the session.
"""

from __future__ import annotations

import logging

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

from database.connection import get_db_session
from database.models import User
from keyboards.main_menu import get_main_menu_keyboard
from services import quiz_service as qs
from services.xp import award_xp

logger = logging.getLogger(__name__)

router = Router(name="quiz")

_LETTERS = ["A", "B", "C", "D"]


class QuizStates(StatesGroup):
    answering = State()


def _question_keyboard(num_options: int) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=_LETTERS[i], callback_data=f"quiz:ans:{i}")]
        for i in range(num_options)
    ]
    rows.append([InlineKeyboardButton(text="⏹ پایان", callback_data="quiz:stop")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _format_question(q, index: int, total: int) -> str:
    opts = "\n".join(f"{_LETTERS[i]}) {opt}" for i, opt in enumerate(q.options))
    return (
        f"❓ <b>سوال {index + 1} از {total}</b>\n\n"
        f"معنی این کلمه چیه؟\n👉 <b>{q.prompt}</b>\n\n{opts}"
    )


async def _send_current_question(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    questions = data["questions"]
    idx = data["index"]
    q = questions[idx]
    await message.answer(
        _format_question(q, idx, len(questions)),
        reply_markup=_question_keyboard(len(q.options)),
    )


@router.message(Command("quiz"))
async def cmd_quiz(message: Message, state: FSMContext, user: User | None) -> None:
    """Start a new quiz session at the user's level."""
    level = (user.current_cefr_level if user else None) or "A0"
    questions = await qs.generate_quiz(cefr_level=level)
    if not questions:
        await message.answer(
            "هنوز واژه‌ی کافی برای کوییز نداریم. 📭",
            reply_markup=get_main_menu_keyboard(),
        )
        return

    await state.set_state(QuizStates.answering)
    await state.set_data({"questions": questions, "index": 0, "score": 0})
    await message.answer(
        f"🧠 <b>کوییز واژگان</b> ({len(questions)} سوال)\nبزن بریم! 🚀"
    )
    await _send_current_question(message, state)


@router.callback_query(QuizStates.answering, F.data == "quiz:stop")
async def quiz_stop(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.answer(
        "کوییز متوقف شد. هر وقت خواستی /quiz رو بزن. 🙂",
        reply_markup=get_main_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(QuizStates.answering, F.data.startswith("quiz:ans:"))
async def quiz_answer(
    callback: CallbackQuery, state: FSMContext, user: User | None
) -> None:
    """Grade the answer, show feedback and advance or finish."""
    data = await state.get_data()
    questions = data["questions"]
    idx = data["index"]
    q = questions[idx]
    chosen = int(callback.data.split(":")[2])

    is_correct = chosen == q.correct_index
    score = data["score"] + (1 if is_correct else 0)

    correct_text = q.options[q.correct_index]
    if is_correct:
        feedback = f"✅ <b>درسته!</b> «{q.prompt}» یعنی «{correct_text}»."
    else:
        feedback = (
            f"❌ <b>اشتباه بود.</b>\n"
            f"«{q.prompt}» یعنی «{correct_text}»."
        )
    if q.example_dutch:
        feedback += f"\n\n<i>{q.example_dutch}</i>"
        if q.example_persian:
            feedback += f"\n{q.example_persian}"

    await callback.message.edit_text(feedback)
    await callback.answer("درست! ✅" if is_correct else "اشتباه ❌")

    next_idx = idx + 1
    if next_idx < len(questions):
        await state.update_data(index=next_idx, score=score)
        await _send_current_question(callback.message, state)
    else:
        await _finish_quiz(callback.message, state, user, score, len(questions))


async def _finish_quiz(
    message: Message, state: FSMContext, user: User | None, score: int, total: int
) -> None:
    """Show the final score and award XP."""
    await state.clear()
    earned = score * qs.XP_PER_CORRECT

    if user is not None and earned > 0:
        async with get_db_session() as session:
            db_user = await session.get(User, user.id)
            if db_user is not None:
                await award_xp(
                    session,
                    user=db_user,
                    event_type="quiz_correct",
                    amount=earned,
                    description=f"quiz {score}/{total}",
                )

    if score == total:
        verdict = "عالی بود! 🏆 Perfect!"
    elif score >= total / 2:
        verdict = "خوب بود! 👏 ادامه بده."
    else:
        verdict = "اشکالی نداره، با تمرین بهتر می‌شه. 💪"

    await message.answer(
        f"🏁 <b>نتیجه‌ی کوییز</b>\n"
        f"امتیاز: <b>{score} از {total}</b>\n"
        f"+{earned} XP ⭐\n\n{verdict}",
        reply_markup=get_main_menu_keyboard(),
    )
