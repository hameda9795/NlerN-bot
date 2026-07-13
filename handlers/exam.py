"""Exam flow: امتحان → level (A2/B1/B2) → section → MCQ questions from the bank.

Serves curated, hand-authored questions from the static bank (no AI, no
generation). The user picks a level and a section; the bot then serves an
unseen 4-option question for that (level, section), grades the answer via the
question bank, and shows the Persian explanation + feedback.

Sections with no curated content yet, or where the user has already seen
every question, show the same "nothing new right now" message.
"""

from __future__ import annotations

import logging
import time

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
from keyboards.main_menu import BTN_QUIZ, get_main_menu_keyboard
from services.exam_taxonomy import (
    LEVELS,
    SECTION_LABELS_FA,
    SECTION_ORDER,
    is_supported,
)
from services.question_selection_service import QuestionSelectionService
from services.question_service import NO_UNSEEN_QUESTION_AVAILABLE, record_answer

logger = logging.getLogger(__name__)

router = Router(name="exam")
_OPTION_KEYS = ("A", "B", "C", "D")


class ExamStates(StatesGroup):
    answering = State()


# --- keyboards -------------------------------------------------------------

def _level_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=lvl, callback_data=f"exam:lvl:{lvl}") for lvl in LEVELS],
    ])


def _section_keyboard(level: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for sec in SECTION_ORDER:
        label = SECTION_LABELS_FA[sec]
        row.append(InlineKeyboardButton(text=label, callback_data=f"exam:sec:{level}:{sec}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="↩️ تغییر سطح", callback_data="exam:start")])
    return rows_markup(rows)


def rows_markup(rows: list[list[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _answer_keyboard(option_keys: list[str]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for key in option_keys:
        row.append(InlineKeyboardButton(text=key, callback_data=f"exam:ans:{key}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="⏹ پایان", callback_data="exam:stop")])
    return rows_markup(rows)


def _after_answer_keyboard(level: str, section: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➡️ سوال بعدی", callback_data="exam:next")],
        [
            InlineKeyboardButton(text="📚 بخش دیگر", callback_data=f"exam:lvl:{level}"),
            InlineKeyboardButton(text="⏹ پایان", callback_data="exam:stop"),
        ],
    ])


def _no_question_keyboard(level: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📚 بخش دیگر", callback_data=f"exam:lvl:{level}"),
            InlineKeyboardButton(text="⏹ پایان", callback_data="exam:stop"),
        ],
    ])


def _format_question(
    *,
    question_text_nl: str,
    question_text_fa: str | None,
    options: list[tuple[str, str]],
    level: str,
    section: str,
) -> str:
    label = SECTION_LABELS_FA.get(section, section)
    opts = "\n".join(f"{key}) {text}" for key, text in options)
    head = f"📝 <b>امتحان — {level} · {label}</b>\n\n"
    body = ""
    if question_text_fa:
        body += f"{question_text_fa}\n\n"
    body += f"🇳🇱 <b>{question_text_nl}</b>\n\n{opts}"
    return head + body


_selection = QuestionSelectionService()


async def _serve_question(
    message: Message, state: FSMContext, *, user_id: int, level: str, section: str
) -> None:
    """Fetch the next unseen question from the bank, then show it."""
    label = SECTION_LABELS_FA.get(section, section)
    placeholder = await message.answer(f"⏳ در حال آماده‌سازی سوالِ «{level} · {label}»…")
    view = await _selection.get_next_question_for_section(
        user_id=user_id, level=level, section=section
    )

    if view == NO_UNSEEN_QUESTION_AVAILABLE:
        await state.clear()
        await placeholder.edit_text(
            "به‌زودی سوالات این بخش در دسترس قرار می‌گیرد.\n"
            "لطفاً بخش‌های دیگر را امتحان کنید.",
            reply_markup=_no_question_keyboard(level),
        )
        return

    await state.set_state(ExamStates.answering)
    await state.set_data({
        "level": level,
        "section": section,
        "question_id": view.id,
        "question_text_nl": view.question_text_nl,
        "question_text_fa": view.question_text_fa,
        "options": [[o.key, o.text_nl] for o in view.options],
        "ts": time.time(),
    })
    await placeholder.edit_text(
        _format_question(
            question_text_nl=view.question_text_nl,
            question_text_fa=view.question_text_fa,
            options=[(o.key, o.text_nl) for o in view.options],
            level=level,
            section=section,
        ),
        reply_markup=_answer_keyboard([o.key for o in view.options]),
    )


# --- handlers --------------------------------------------------------------

@router.message(Command("exam"))
@router.message(F.text == BTN_QUIZ)
async def cmd_exam(message: Message, state: FSMContext) -> None:
    """Entry point: choose a level."""
    await state.clear()
    await message.answer(
        "📝 <b>امتحان</b>\nاول سطح را انتخاب کن:",
        reply_markup=_level_keyboard(),
    )


@router.callback_query(F.data == "exam:start")
async def exam_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(
        "📝 <b>امتحان</b>\nاول سطح را انتخاب کن:",
        reply_markup=_level_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("exam:lvl:"))
async def exam_level(callback: CallbackQuery, state: FSMContext) -> None:
    level = callback.data.split(":")[2]
    if level not in LEVELS:
        await callback.answer("سطح نامعتبر", show_alert=True)
        return
    await callback.message.edit_text(
        f"📝 <b>امتحان — {level}</b>\nحالا بخش را انتخاب کن:",
        reply_markup=_section_keyboard(level),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("exam:sec:"))
async def exam_section(callback: CallbackQuery, state: FSMContext, user: User | None) -> None:
    _, _, level, section = callback.data.split(":", 3)
    if not is_supported(level, section) or user is None:
        await callback.answer("نامعتبر", show_alert=True)
        return
    await callback.answer()
    await _serve_question(
        callback.message, state, user_id=user.id, level=level, section=section
    )


@router.callback_query(ExamStates.answering, F.data == "exam:stop")
async def exam_stop(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.answer(
        "امتحان متوقف شد. هر وقت خواستی دوباره «📝 امتحان» را بزن. 🙂",
        reply_markup=get_main_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(ExamStates.answering, F.data == "exam:next")
async def exam_next(callback: CallbackQuery, state: FSMContext, user: User | None) -> None:
    data = await state.get_data()
    await callback.answer()
    if user is None:
        await state.clear()
        return
    await _serve_question(
        callback.message, state,
        user_id=user.id, level=data["level"], section=data["section"],
    )


@router.callback_query(ExamStates.answering, F.data.startswith("exam:ans:"))
async def exam_answer(callback: CallbackQuery, state: FSMContext, user: User | None) -> None:
    """Grade the chosen option via the question bank and show feedback."""
    data = await state.get_data()
    if user is None or "question_id" not in data:
        await callback.answer()
        return
    chosen = callback.data.split(":")[2]
    spent = max(0, int(time.time() - data.get("ts", time.time())))
    options = {k: v for k, v in data["options"]}

    result = await record_answer(
        user_id=user.id,
        question_id=data["question_id"],
        selected_option_key=chosen,
        time_spent_seconds=spent,
    )
    if result is None:
        await callback.answer("سوال پیدا نشد", show_alert=True)
        return

    if result.is_correct:
        head = "✅ <b>درست!</b>"
    else:
        correct_text = options.get(result.correct_option_key, "")
        head = (f"❌ <b>اشتباه بود.</b>\nپاسخ درست: "
                f"<b>{result.correct_option_key}) {correct_text}</b>")
    parts = [head]
    if result.feedback_fa:
        parts.append(result.feedback_fa)
    if result.explanation_fa:
        parts.append(f"💡 {result.explanation_fa}")
    feedback_block = "\n\n".join(parts)

    question_block = _format_question(
        question_text_nl=data.get("question_text_nl", ""),
        question_text_fa=data.get("question_text_fa"),
        options=data["options"],
        level=data["level"],
        section=data["section"],
    )

    await callback.message.edit_text(
        f"{question_block}\n\n➖➖➖➖➖\n\n{feedback_block}",
        reply_markup=_after_answer_keyboard(data["level"], data["section"]),
    )
    await callback.answer("✅" if result.is_correct else "❌")
