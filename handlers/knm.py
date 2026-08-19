"""KNM inburgering exam: pick a group, answer, see the Persian explanation.

Mirrors ``handlers/exam.py``'s shape (question rendered into the message, one
inline button per option, feedback appended under the question) but reads the
standalone ``knm`` table instead of the shared question bank, and resumes each
group where the user left off — see ``services/knm_service.py``.

Explanations are shown in Persian; the English set the dataset carries is kept
in the database but not rendered here.
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from database.models import User
from keyboards.knm_keyboard import (
    after_answer_keyboard,
    answer_keyboard,
    back_to_groups_keyboard,
    group_finished_keyboard,
    groups_keyboard,
    reset_confirm_keyboard,
)
from keyboards.main_menu import BTN_KNM, get_main_menu_keyboard
from services import knm_service as knm

logger = logging.getLogger(__name__)

router = Router(name="knm")

_HOME_TITLE = "🇳🇱 <b>آزمون KNM</b>"


class KnmStates(StatesGroup):
    answering = State()


def _format_question(view: knm.KnmQuestionView) -> str:
    options = "\n".join(f"{option.key}) {option.text_nl}" for option in view.options)
    return (
        f"{_HOME_TITLE} — دسته {view.group + 1} · "
        f"سؤال {view.index_in_group} از {view.group_total}\n\n"
        f"🇳🇱 <b>{view.question_text_nl}</b>\n\n{options}"
    )


async def _show_groups(message: Message, state: FSMContext, *, user_id: int, edit: bool) -> None:
    await state.clear()
    groups = await knm.list_groups(user_id=user_id)
    if not groups:
        text = (
            f"{_HOME_TITLE}\n\nهنوز سؤالی وارد نشده. به‌زودی در دسترس قرار می‌گیرد."
        )
        keyboard = None
    else:
        total = sum(group.total for group in groups)
        answered = sum(group.answered for group in groups)
        text = (
            f"{_HOME_TITLE}\n\n{total} سؤال در {len(groups)} دسته — "
            f"تا حالا {answered} سؤال جواب داده‌ای.\n\nیک دسته را انتخاب کن:"
        )
        keyboard = groups_keyboard(groups)
    if edit:
        await message.edit_text(text, reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=keyboard)


async def _serve_question(
    message: Message, state: FSMContext, *, user_id: int, group: int, edit: bool
) -> None:
    """Show the group's next unanswered question, or its finished summary."""
    view = await knm.next_question(user_id=user_id, group=group)
    if view is None:
        summary = await knm.get_group(user_id=user_id, group=group)
        if summary is None:
            await state.clear()
            await message.edit_text(
                f"{_HOME_TITLE}\n\nاین دسته پیدا نشد.",
                reply_markup=back_to_groups_keyboard(),
            )
            return
        await state.clear()
        percent = round(summary.correct * 100 / summary.total) if summary.total else 0
        await message.edit_text(
            f"🎉 <b>دسته {group + 1} تمام شد!</b>\n\n"
            f"{summary.correct} از {summary.total} درست ({percent}٪)",
            reply_markup=group_finished_keyboard(group),
        )
        return

    await state.set_state(KnmStates.answering)
    await state.set_data({
        "group": group,
        "knm_id": view.id,
        "text": _format_question(view),
        "options": {option.key: option.text_nl for option in view.options},
    })
    keyboard = answer_keyboard([option.key for option in view.options])
    if edit:
        await message.edit_text(_format_question(view), reply_markup=keyboard)
    else:
        await message.answer(_format_question(view), reply_markup=keyboard)


@router.message(Command("knm"))
@router.message(F.text == BTN_KNM)
async def cmd_knm(message: Message, state: FSMContext, user: User | None) -> None:
    if user is None:
        return
    await _show_groups(message, state, user_id=user.id, edit=False)


@router.callback_query(F.data == "knm:home")
async def knm_home(callback: CallbackQuery, state: FSMContext, user: User | None) -> None:
    await callback.answer()
    if user is None:
        return
    await _show_groups(callback.message, state, user_id=user.id, edit=True)


@router.callback_query(F.data.startswith("knm:grp:"))
async def knm_group(callback: CallbackQuery, state: FSMContext, user: User | None) -> None:
    if user is None:
        await callback.answer()
        return
    group = int(callback.data.split(":")[2])
    await callback.answer()
    await _serve_question(
        callback.message, state, user_id=user.id, group=group, edit=True
    )


@router.callback_query(KnmStates.answering, F.data == "knm:next")
async def knm_next(callback: CallbackQuery, state: FSMContext, user: User | None) -> None:
    data = await state.get_data()
    await callback.answer()
    if user is None:
        await state.clear()
        return
    await _serve_question(
        callback.message, state, user_id=user.id, group=data["group"], edit=True
    )


@router.callback_query(KnmStates.answering, F.data.startswith("knm:ans:"))
async def knm_answer(callback: CallbackQuery, state: FSMContext, user: User | None) -> None:
    """Grade the tapped option and append the Persian feedback under it."""
    data = await state.get_data()
    if user is None or "knm_id" not in data:
        await callback.answer()
        return
    chosen = callback.data.split(":")[2]

    result = await knm.record_answer(
        user_id=user.id, knm_id=data["knm_id"], selected_option_key=chosen
    )
    if result is None:
        await callback.answer("سؤال پیدا نشد", show_alert=True)
        return

    if result.is_correct:
        head = "✅ <b>درست!</b>"
    else:
        head = (
            "❌ <b>اشتباه بود.</b>\nپاسخ درست: "
            f"<b>{result.correct_option_key}) {result.correct_option_text}</b>"
        )
    parts = [head]
    if result.feedback_fa:
        parts.append(result.feedback_fa)
    if result.explanation_fa:
        parts.append(f"💡 {result.explanation_fa}")
    if result.key_terms_fa:
        parts.append(f"📖 {result.key_terms_fa}")

    await callback.message.edit_text(
        f"{data['text']}\n\n➖➖➖➖➖\n\n" + "\n\n".join(parts),
        reply_markup=after_answer_keyboard(),
    )
    await callback.answer("✅" if result.is_correct else "❌")


@router.callback_query(F.data.startswith("knm:reset:go:"))
async def knm_reset_go(callback: CallbackQuery, state: FSMContext, user: User | None) -> None:
    if user is None:
        await callback.answer()
        return
    group = int(callback.data.split(":")[3])
    await knm.reset_group(user_id=user.id, group=group)
    await callback.answer("پیشرفت این دسته پاک شد")
    await _serve_question(
        callback.message, state, user_id=user.id, group=group, edit=True
    )


@router.callback_query(F.data.startswith("knm:reset:"))
async def knm_reset_confirm(callback: CallbackQuery) -> None:
    group = int(callback.data.split(":")[2])
    await callback.message.edit_text(
        f"🔄 <b>تکرار دسته {group + 1}</b>\n\n"
        "همه‌ی جواب‌های این دسته پاک می‌شود و از سؤال ۱ شروع می‌کنی. مطمئنی؟",
        reply_markup=reset_confirm_keyboard(group),
    )
    await callback.answer()


@router.callback_query(F.data == "knm:stop")
async def knm_stop(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.answer(
        "آزمون KNM متوقف شد. هر وقت خواستی دوباره «🇳🇱 آزمون KNM» را بزن. 🙂",
        reply_markup=get_main_menu_keyboard(),
    )
    await callback.answer()
