"""KNM inburgering exam: pick a group, answer, see the Persian explanation.

Reads the standalone ``knm`` table (not the shared question bank) and resumes
each group where the user left off — see ``services/knm_service.py``.

This screen is mostly presentation, so the rules it follows are worth stating:

* the options live on the buttons, each carrying its full Dutch text — Telegram
  wraps a long single-button label, so the message body never repeats them;
* the Dutch question sits in a ``<blockquote>``, which separates it from the
  Persian chrome without shouting in bold;
* the explanation goes in an **expandable** blockquote, so the verdict stays
  visible and the detail is one tap away instead of a wall of text;
* every number the user sees is rendered with Persian digits.

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
from aiogram.utils.text_decorations import html_decoration as html

from database.models import User
from keyboards.knm_keyboard import (
    after_answer_keyboard,
    answer_keyboard,
    back_to_groups_keyboard,
    group_finished_keyboard,
    groups_keyboard,
    option_marker,
    reset_confirm_keyboard,
)
from keyboards.main_menu import BTN_KNM, get_main_menu_keyboard
from services import knm_service as knm
from utils.fa_text import fa_digits, progress_bar

logger = logging.getLogger(__name__)

router = Router(name="knm")

_HOME_TITLE = "🇳🇱 <b>آزمون KNM</b>"


class KnmStates(StatesGroup):
    answering = State()


def _header(view: knm.KnmQuestionView) -> str:
    """Title, progress bar and position — the two lines every screen opens with."""
    bar = progress_bar(view.index_in_group - 1, view.group_total)
    # The bar sits on its own line: emoji run left-to-right, and inlining them
    # with Persian text drags the numbers to the wrong end of the line.
    return (
        f"{_HOME_TITLE} · دسته {fa_digits(view.group + 1)}\n"
        f"{bar}\n"
        f"سؤال {fa_digits(view.index_in_group)} از {fa_digits(view.group_total)}"
    )


def _format_question(view: knm.KnmQuestionView) -> str:
    """The question screen. The options are on the buttons, not repeated here."""
    return (
        f"{_header(view)}\n\n"
        f"<blockquote>{html.quote(view.question_text_nl)}</blockquote>\n\n"
        "👇 جواب درست را انتخاب کن"
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
        correct = sum(group.correct for group in groups)
        lines = [
            _HOME_TITLE,
            progress_bar(answered, total),
            "",
            f"{fa_digits(total)} سؤال · {fa_digits(len(groups))} دسته",
        ]
        if answered:
            share = round(correct * 100 / answered)
            lines.append(
                f"جواب داده‌ای: {fa_digits(answered)} — "
                f"{fa_digits(correct)} درست ({fa_digits(share)}٪)"
            )
        else:
            lines.append("هنوز شروع نکرده‌ای — از دسته‌ی ۱ شروع کن.")
        text = "\n".join(lines)
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
            f"🎉 <b>دسته {fa_digits(group + 1)} تمام شد</b>\n"
            f"{progress_bar(summary.correct, summary.total)}\n\n"
            f"{fa_digits(summary.correct)} از {fa_digits(summary.total)} درست"
            f" ({fa_digits(percent)}٪)",
            reply_markup=group_finished_keyboard(group),
        )
        return

    await state.set_state(KnmStates.answering)
    await state.set_data({
        "group": group,
        "knm_id": view.id,
        "header": _header(view),
        "question": view.question_text_nl,
        "options": {option.key: option.text_nl for option in view.options},
    })
    keyboard = answer_keyboard(view.options)
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

    await callback.message.edit_text(
        _format_answer(data, result=result, chosen=chosen),
        reply_markup=after_answer_keyboard(),
    )
    await callback.answer("✅ درست" if result.is_correct else "❌ اشتباه")


def _format_answer(
    data: dict, *, result: knm.KnmAnswerResult, chosen: str
) -> str:
    """The feedback screen: verdict up top, detail folded into an expandable quote."""
    options: dict[str, str] = data.get("options", {})
    correct_line = (
        f"{option_marker(result.correct_option_key)} "
        f"{html.quote(result.correct_option_text)}"
    )
    if result.is_correct:
        verdict = f"✅ <b>درست!</b>  {correct_line}"
    else:
        picked = options.get(chosen, "")
        verdict = (
            f"❌ <b>اشتباه</b>  <s>{option_marker(chosen)} {html.quote(picked)}</s>\n"
            f"✅ پاسخ درست: <b>{correct_line}</b>"
        )

    detail: list[str] = []
    if result.explanation_fa:
        detail.append(html.quote(result.explanation_fa))
    if result.key_terms_fa:
        detail.append(f"📖 <b>واژه‌های کلیدی</b>\n{html.quote(result.key_terms_fa)}")

    blocks = [
        data.get("header", _HOME_TITLE),
        "",
        f"<blockquote>{html.quote(data.get('question', ''))}</blockquote>",
        "",
        verdict,
    ]
    if result.feedback_fa:
        blocks.append(f"\n<blockquote>{html.quote(result.feedback_fa)}</blockquote>")
    if detail:
        # Expandable: the verdict stays on screen, the reasoning is one tap away.
        blocks.append(
            "\n<blockquote expandable>💡 <b>توضیح بیشتر</b>\n"
            + "\n\n".join(detail)
            + "</blockquote>"
        )
    return "\n".join(blocks)


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
