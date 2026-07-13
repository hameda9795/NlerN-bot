"""Common command handlers: /start, /help, /cancel."""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from keyboards.main_menu import get_main_menu_keyboard

logger = logging.getLogger(__name__)

router = Router(name="common")

WELCOME_TEXT = (
    "<b>سلام! به NlerN خوش اومدی 🌷</b>\n"
    "<b>Welkom bij de Nederlandse les!</b>\n\n"
    "NlerN یه ربات آموزش زبان هلندیه، مخصوص فارسی‌زبان‌ها، که قدم‌به‌قدم از سطح صفر "
    "(A0) تا B2 همراهته. 🇳🇱\n\n"
    "این چیزیه که همین الان توی NlerN داری:\n"
    "📂 <b>واژگان</b> — نزدیک به ۱۰۰۰ واژه‌ی پرکاربرد B2 به‌علاوه‌ی بیش از ۵۶۰۰ فعل "
    "(باقاعده، بی‌قاعده و جداشدنی) با معنی، مثال و تلفظ.\n"
    "📝 <b>امتحان</b> — بیش از ۶۰۰۰ سوال چهارگزینه‌ای دست‌ساز، در سطح‌های A2، B1 و B2.\n"
    "🗣 <b>تمرین جمله</b> — یه جمله‌ی واقعی هلندی می‌گیری، بلند می‌خونیش، و صدات رو "
    "تحلیل می‌کنیم تا واقعاً بفهمی تلفظت چقدر درسته.\n"
    "⭐ <b>کلمات سخت من</b> — هر کلمه یا فعلی که موقع مرور سختت بود رو با یه ضربه ذخیره "
    "کن؛ بعداً از همین‌جا فقط همونا رو مرور می‌کنی (اول هلندیش نشون داده می‌شه، با یه ضربه‌ی "
    "دیگه معنی فارسیش رو می‌بینی).\n\n"
    "این دیتا حاصل نزدیک به یک سال جمع‌آوری و بازبینیه و همین الان هم یکی از کامل‌ترین "
    "منابع فارسی↔هلندیه که پیدا می‌کنی — ولی با این حجم داده، طبیعیه که گاهی به یه اشتباه "
    "کوچیک هم بربخوری؛ اگه دیدی بگو تا اصلاح بشه. 🙏\n"
    "و با حمایت شما مشترک‌ها، این مجموعه هر روز کامل‌تر می‌شه و بخش‌های تازه هم بهش "
    "اضافه خواهد شد.\n\n"
    "از منوی پایین شروع کن. برای راهنمای کامل‌تر /help رو بزن.\n\n"
    "<i>Veel succes! موفق باشی!</i> 🚀"
)

HELP_TEXT = (
    "<b>راهنمای NlerN 📖</b>\n\n"
    "NlerN یه ربات آموزش زبان هلندیه برای فارسی‌زبان‌ها، از صفر (A0) تا B2، با تمرکز "
    "روی واژگان، دستور زبان و تلفظ درست.\n\n"
    "<b>دستورات:</b>\n"
    "/start — شروع و نمایش منوی اصلی\n"
    "/vajegan — بخش واژگان و فعل‌ها\n"
    "/zin — تمرین جمله و تلفظ\n"
    "/help — همین راهنما\n"
    "/cancel — لغو عملیات فعلی و بازگشت به منو\n\n"
    "<b>بخش‌های منوی اصلی:</b>\n"
    "📂 <b>واژگان</b> — نزدیک به ۱۰۰۰ واژه‌ی پرکاربرد B2 و بیش از ۵۶۰۰ فعل (باقاعده، "
    "بی‌قاعده، جداشدنی)، دسته‌بندی‌شده و با مثال.\n"
    "📝 <b>امتحان</b> — بیش از ۶۰۰۰ سوال دست‌ساز؛ سه سطح داره: <b>A2</b> (پایه‌ی محکم)، "
    "<b>B1</b> (مکالمه‌ی روزمره) و <b>B2</b> (سطح پیشرفته و ظریف‌کاری‌های زبان).\n"
    "🗣 <b>تمرین جمله</b> — یه جمله‌ی واقعی هلندی بهت نشون داده می‌شه، صداتو ضبط می‌کنی "
    "و بلافاصله بهت می‌گیم کجاهاش رو درست و کجاهاش رو نادرست تلفظ کردی.\n"
    "⭐ <b>کلمات سخت من</b> — کلماتی که موقع مرور ستاره‌شون می‌زنی اینجا جمع می‌شن تا هر "
    "وقت خواستی، فقط همونایی که واقعاً براشون وقت لازم داری رو مرور کنی.\n\n"
    "<b>درباره‌ی دیتا:</b> این مجموعه حاصل نزدیک به یک سال جمع‌آوری و تایید دستیه و "
    "همین الان هم یکی از کامل‌ترین منابع فارسی↔هلندیه، اما به‌مرور زمان و با حمایت شما "
    "مشترک‌ها کامل‌تر هم می‌شه و بخش‌های جدیدی هم بهش اضافه می‌شه. با این حجم از داده، "
    "احتمال یه خطای کوچیک اینجا و اونجا هم وجود داره — اگه دیدی، خوشحال می‌شیم بهمون بگی.\n\n"
    "<b>نکته‌های یادگیری بهتر:</b>\n"
    "• هر روز کمی تمرین کن تا استریک (streak) ات حفظ بشه 🔥\n"
    "• به article کلمه‌ها (<b>de</b>/<b>het</b>) خوب دقت کن — خیلی مهمه!\n"
    "• جمله‌ها رو بلند تکرار کن تا تلفظت طبیعی‌تر بشه.\n\n"
    "<i>Tot ziens! به امید دیدار!</i>"
)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    """Greet the user and show the main menu."""
    await state.clear()
    await message.answer(WELCOME_TEXT, reply_markup=get_main_menu_keyboard())


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Show the help text with available commands and tips."""
    await message.answer(HELP_TEXT, reply_markup=get_main_menu_keyboard())


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    """Clear any active FSM state and return to the main menu."""
    current_state = await state.get_state()
    if current_state is None:
        await message.answer(
            "چیزی برای لغو کردن نبود. 🙂", reply_markup=get_main_menu_keyboard()
        )
        return
    await state.clear()
    await message.answer(
        "عملیات لغو شد. برگشتی به منوی اصلی. ✅",
        reply_markup=get_main_menu_keyboard(),
    )
