"""Lesson browsing & completion handlers.

Triggered by the /lessons command and the "📚 درس‌های امروز" menu button.
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from database.models import User
from keyboards.main_menu import BTN_LESSONS, get_main_menu_keyboard
from services import curriculum_service as cs

logger = logging.getLogger(__name__)

router = Router(name="curriculum")


def _lessons_keyboard(lessons, completed_ids: set[int]) -> InlineKeyboardMarkup:
    """Build an inline keyboard listing lessons with a ✅ for completed ones."""
    rows = []
    for lesson in lessons:
        mark = "✅ " if lesson.id in completed_ids else "▫️ "
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{mark}{lesson.title_persian} ({lesson.title_dutch})",
                    callback_data=f"lesson:open:{lesson.id}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _show_lessons(message: Message, user: User) -> None:
    """Render the lesson list for the user's current level."""
    level = user.current_cefr_level or "A0"
    lessons = await cs.get_available_lessons(user.id, level)
    if not lessons:
        await message.answer(
            f"برای سطح <b>{level}</b> هنوز درسی موجود نیست. 📭",
            reply_markup=get_main_menu_keyboard(),
        )
        return

    completed = await cs.get_completed_lesson_ids(user.id)
    header = (
        f"📚 <b>درس‌های سطح {level}</b>\n"
        f"تکمیل‌شده: {len(completed & {l.id for l in lessons})} از {len(lessons)}\n\n"
        "یک درس را انتخاب کن:"
    )
    await message.answer(header, reply_markup=_lessons_keyboard(lessons, completed))


@router.message(Command("lessons"))
@router.message(F.text == BTN_LESSONS)
async def cmd_lessons(message: Message, user: User | None) -> None:
    """Entry point: show available lessons."""
    if user is None:
        await message.answer("یه لحظه دوباره /start رو بزن. 🙏")
        return
    await _show_lessons(message, user)


def _render_lesson(lesson) -> str:
    """Format a lesson's content into a Persian + Dutch message."""
    content = cs.LessonContent.from_json(lesson.content_json)
    parts = [
        f"📖 <b>{lesson.title_persian}</b>\n<i>{lesson.title_dutch}</i>\n",
    ]
    if content.vocabulary:
        vocab = "، ".join(content.vocabulary)
        parts.append(f"<b>واژگان:</b>\n{vocab}\n")
    if content.grammar_note:
        parts.append(f"<b>نکته‌ی گرامری:</b>\n{content.grammar_note}\n")
    if content.practice:
        practice = "\n".join(f"• {p}" for p in content.practice)
        parts.append(f"<b>تمرین:</b>\n{practice}")
    return "\n".join(parts)


@router.callback_query(F.data.startswith("lesson:open:"))
async def open_lesson(callback: CallbackQuery) -> None:
    """Show a lesson's content with a 'complete' button."""
    lesson_id = int(callback.data.split(":")[2])
    lesson = await cs.get_lesson_detail(lesson_id)
    if lesson is None:
        await callback.answer("درس پیدا نشد.", show_alert=True)
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ تکمیل درس",
                    callback_data=f"lesson:done:{lesson.id}",
                )
            ],
            [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="lesson:list")],
        ]
    )
    await callback.message.edit_text(_render_lesson(lesson), reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "lesson:list")
async def back_to_list(callback: CallbackQuery, user: User | None) -> None:
    """Return to the lesson list."""
    if user is None:
        await callback.answer()
        return
    level = user.current_cefr_level or "A0"
    lessons = await cs.get_available_lessons(user.id, level)
    completed = await cs.get_completed_lesson_ids(user.id)
    await callback.message.edit_text(
        f"📚 <b>درس‌های سطح {level}</b>\n\nیک درس را انتخاب کن:",
        reply_markup=_lessons_keyboard(lessons, completed),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("lesson:done:"))
async def complete_lesson(callback: CallbackQuery, user: User | None) -> None:
    """Mark the lesson complete, award XP and suggest the next one."""
    if user is None:
        await callback.answer()
        return
    lesson_id = int(callback.data.split(":")[2])
    xp = await cs.mark_lesson_completed(user.id, lesson_id, score=100.0)

    if xp == 0:
        await callback.answer("این درس را قبلاً تکمیل کرده بودی. 😉", show_alert=True)
        return

    await callback.message.edit_text(
        f"🎉 <b>آفرین! درس تکمیل شد.</b>\n"
        f"+{xp} XP گرفتی! ⭐\n\n"
        "<i>Goed gedaan! آماده‌ی درس بعدی هستی.</i>"
    )
    # Offer the lesson list again as the natural next step.
    level = user.current_cefr_level or "A0"
    lessons = await cs.get_available_lessons(user.id, level)
    completed = await cs.get_completed_lesson_ids(user.id)
    await callback.message.answer(
        "درس بعدی را انتخاب کن:",
        reply_markup=_lessons_keyboard(lessons, completed),
    )
    await callback.answer("+%d XP" % xp)
