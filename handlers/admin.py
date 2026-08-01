"""In-bot admin dashboard: users, subscriptions, payments.

Entered via /admin or the "🛠 داشبورد ادمین" menu button (both hidden from
regular users — see ``utils/admin.py`` and ``keyboards/main_menu.py``). Every
entry point re-checks ``is_admin`` directly, mirroring ``handlers/ai_chat.py``,
so this whole router is unreachable for non-admins even via a direct command.

List views (users / past-due / payments) load everything into an FSM-backed
queue + index cursor and page through it — the same pattern
``handlers/vocab_b2.py`` uses for browsing word lists — since the user base is
small enough that real DB-side pagination isn't needed yet.
"""

from __future__ import annotations

from datetime import datetime

from aiogram import Bot, F, Router
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

from database.models import User
from keyboards.admin_keyboard import (
    broadcast_preview_keyboard,
    broadcast_segment_keyboard,
    confirm_keyboard,
    list_row_keyboard,
    overview_keyboard,
    payments_list_keyboard,
    user_profile_keyboard,
    users_menu_keyboard,
)
from keyboards.main_menu import BTN_ADMIN
from services import admin_service
from services import broadcast_service as bc
from services import subscription_service as subs
from utils.admin import is_admin

router = Router(name="admin")


class AdminStates(StatesGroup):
    searching = State()
    broadcast_composing = State()


def _fmt(dt: datetime | None) -> str:
    return dt.strftime("%Y-%m-%d") if dt else "—"


def _user_label(user: User) -> str:
    return f"@{user.username}" if user.username else str(user.telegram_id)


def _user_label_dict(item: dict) -> str:
    return f"@{item['username']}" if item.get("username") else str(item.get("telegram_id", "—"))


async def _denied(message: Message) -> None:
    await message.answer("🔒 این بخش فقط برای مدیر ربات در دسترسه.")


async def _overview_text() -> str:
    total = await admin_service.count_users()
    counts = await admin_service.count_by_subscription_status()
    revenue = await admin_service.revenue_this_month()
    return (
        "🛠 <b>داشبورد ادمین</b>\n\n"
        f"👥 کل کاربران: <b>{total}</b>\n\n"
        f"✅ فعال: {counts['active']}\n"
        f"🎁 تست رایگان: {counts['trialing']}\n"
        f"⚠️ پرداخت ناموفق: {counts['past_due']}\n"
        f"⛔️ لغوشده: {counts['canceled']}\n"
        f"⏳ در انتظار: {counts['pending']}\n"
        f"🚫 بدون اشتراک: {counts['none']}\n\n"
        f"💶 <b>درآمد این ماه: €{revenue:.2f}</b>"
    )


def _describe_subscription(sub) -> str:
    if sub is None:
        return "🚫 بدون اشتراک"
    until = _fmt(sub.current_period_end)
    is_trial = sub.trial_used_at is not None and sub.mollie_subscription_id is None
    if subs.is_active(sub):
        if is_trial:
            return f"🎁 تست رایگان — تا {until}"
        if sub.status == subs.STATUS_CANCELED:
            return f"ℹ️ لغوشده — دسترسی تا {until}"
        return f"✅ فعال — تا {until}"
    if sub.status == subs.STATUS_PAST_DUE:
        return "⚠️ پرداخت ناموفق"
    return f"وضعیت: {sub.status}"


def _can_cancel(sub) -> bool:
    return bool(
        sub is not None
        and sub.mollie_subscription_id
        and sub.status not in (subs.STATUS_CANCELED, subs.STATUS_EXPIRED)
    )


async def _show_profile(message: Message, user_id: int, *, edit: bool) -> None:
    user = await admin_service.get_user_by_id(user_id)
    if user is None:
        text, keyboard = "کاربر پیدا نشد.", overview_keyboard()
    else:
        sub = await subs.get_subscription(user_id=user_id)
        payments = await subs.list_payments(user_id=user_id, limit=3)
        history = (
            "\n".join(f"• {_fmt(p.created_at)} — €{p.amount_eur:.2f} — {p.status}" for p in payments)
            if payments
            else "پرداختی ثبت نشده."
        )
        text = (
            f"👤 <b>{_user_label(user)}</b>\n"
            f"آیدی: <code>{user.telegram_id}</code>\n"
            f"عضویت: {_fmt(user.created_at)} — آخرین فعالیت: {_fmt(user.last_active_at)}\n"
            f"سطح: {user.current_cefr_level}\n\n"
            f"{_describe_subscription(sub)}\n\n"
            f"<b>آخرین پرداخت‌ها:</b>\n{history}"
        )
        keyboard = user_profile_keyboard(user_id, can_cancel=_can_cancel(sub))
    if edit:
        await message.edit_text(text, reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=keyboard)


async def _render_list(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    kind, queue, index = data["kind"], data["queue"], data["index"]
    total = len(queue)
    item = queue[index]
    label = _user_label_dict(item)
    if kind == "users":
        text = f"👤 {label}\nآخرین فعالیت: {_fmt(item['last_active'])}\n\n({index + 1}/{total})"
        keyboard = list_row_keyboard(kind, index, total, user_id=item["id"], back="admin:users")
    elif kind == "pastdue":
        text = f"⚠️ {label}\nتا: {_fmt(item['until'])}\n\n({index + 1}/{total})"
        keyboard = list_row_keyboard(kind, index, total, user_id=item["id"], back="admin:home")
    else:  # pay
        text = (
            f"💳 {label}\n{_fmt(item['date'])} — €{item['amount']:.2f} — {item['status']}"
            f"\n\n({index + 1}/{total})"
        )
        keyboard = payments_list_keyboard(index, total)
    await message.edit_text(text, reply_markup=keyboard)


# --- entry point -------------------------------------------------------------

@router.message(Command("admin"))
@router.message(F.text == BTN_ADMIN)
async def cmd_admin(message: Message, state: FSMContext, user: User | None) -> None:
    if user is None or not is_admin(user.telegram_id):
        await _denied(message)
        return
    await state.clear()
    await message.answer(await _overview_text(), reply_markup=overview_keyboard())


@router.callback_query(F.data == "admin:home")
async def admin_home(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(await _overview_text(), reply_markup=overview_keyboard())
    await callback.answer()


# --- users -------------------------------------------------------------------

@router.callback_query(F.data == "admin:users")
async def admin_users_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(
        "👥 <b>کاربران</b>\nچطور می‌خوای پیدا کنی؟", reply_markup=users_menu_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "admin:users:find")
async def admin_users_find_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminStates.searching)
    await callback.message.edit_text("🔍 یوزرنیم یا آیدی عددی تلگرام کاربر رو بفرست:")
    await callback.answer()


@router.message(AdminStates.searching)
async def admin_users_find_result(message: Message, state: FSMContext, user: User | None) -> None:
    if user is None or not is_admin(user.telegram_id):
        await _denied(message)
        return
    await state.clear()
    results = await admin_service.search_users(message.text or "")
    if not results:
        await message.answer("چیزی پیدا نشد. 🤷", reply_markup=users_menu_keyboard())
        return
    if len(results) == 1:
        await _show_profile(message, results[0].id, edit=False)
        return
    rows = [
        [InlineKeyboardButton(text=_user_label(u), callback_data=f"admin:u:{u.id}")]
        for u in results
    ]
    rows.append([InlineKeyboardButton(text="↩️ بازگشت", callback_data="admin:users")])
    await message.answer("نتایج جست‌وجو:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@router.callback_query(F.data == "admin:users:all")
async def admin_users_all(callback: CallbackQuery, state: FSMContext) -> None:
    users = await admin_service.list_users()
    if not users:
        await callback.message.edit_text("کاربری وجود نداره.", reply_markup=users_menu_keyboard())
        await callback.answer()
        return
    queue = [
        {
            "id": u.id,
            "telegram_id": u.telegram_id,
            "username": u.username,
            "last_active": u.last_active_at,
        }
        for u in users
    ]
    await state.set_data({"kind": "users", "queue": queue, "index": 0})
    await _render_list(callback.message, state)
    await callback.answer()


@router.callback_query(F.data.startswith("admin:u:"))
async def admin_view_user(callback: CallbackQuery) -> None:
    user_id = int(callback.data.split(":")[2])
    await _show_profile(callback.message, user_id, edit=True)
    await callback.answer()


# --- past-due ------------------------------------------------------------

@router.callback_query(F.data == "admin:pastdue")
async def admin_pastdue(callback: CallbackQuery, state: FSMContext) -> None:
    past_due = await admin_service.list_past_due_subscriptions()
    if not past_due:
        await callback.message.edit_text("چیزی برای پیگیری نیست. 🎉", reply_markup=overview_keyboard())
        await callback.answer()
        return
    queue = [
        {
            "id": s.user_id,
            "telegram_id": s.user.telegram_id if s.user else None,
            "username": s.user.username if s.user else None,
            "until": s.current_period_end,
        }
        for s in past_due
    ]
    await state.set_data({"kind": "pastdue", "queue": queue, "index": 0})
    await _render_list(callback.message, state)
    await callback.answer()


# --- payments ------------------------------------------------------------

@router.callback_query(F.data == "admin:pay")
async def admin_payments(callback: CallbackQuery, state: FSMContext) -> None:
    payments = await admin_service.list_recent_payments()
    if not payments:
        await callback.message.edit_text("پرداختی ثبت نشده.", reply_markup=overview_keyboard())
        await callback.answer()
        return
    queue = [
        {
            "id": p.user_id,
            "telegram_id": p.user.telegram_id if p.user else None,
            "username": p.user.username if p.user else None,
            "date": p.created_at,
            "amount": p.amount_eur,
            "status": p.status,
        }
        for p in payments
    ]
    await state.set_data({"kind": "pay", "queue": queue, "index": 0})
    await _render_list(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "admin:pay:csv")
async def admin_payments_csv(callback: CallbackQuery) -> None:
    csv_bytes = await admin_service.export_payments_csv()
    await callback.message.answer_document(
        BufferedInputFile(csv_bytes, filename="payments.csv"),
        caption="📄 خروجی کامل پرداخت‌ها",
    )
    await callback.answer()


# --- broadcast ---------------------------------------------------------------

@router.callback_query(F.data == "admin:bc")
async def admin_broadcast_menu(callback: CallbackQuery, state: FSMContext, user: User | None) -> None:
    if user is None or not is_admin(user.telegram_id):
        await callback.answer()
        return
    await state.clear()
    segments = [
        (key, label, len(await bc.resolve_segment_user_ids(key)))
        for key, label in bc.SEGMENTS.items()
    ]
    await callback.message.edit_text(
        "📢 <b>پیام همگانی</b>\nگروه هدف رو انتخاب کن:",
        reply_markup=broadcast_segment_keyboard(segments),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:bc:seg:"))
async def admin_broadcast_segment_chosen(
    callback: CallbackQuery, state: FSMContext, user: User | None
) -> None:
    if user is None or not is_admin(user.telegram_id):
        await callback.answer()
        return
    segment = callback.data.split(":")[3]
    target_count = len(await bc.resolve_segment_user_ids(segment))
    await state.set_state(AdminStates.broadcast_composing)
    await state.update_data(segment=segment, target_count=target_count)
    await callback.message.edit_text(
        f"✍️ متن پیام رو بفرست (گیرنده‌ها: {target_count} نفر).\n"
        "فرمت بولد/ایتالیک تلگرام حفظ می‌شه."
    )
    await callback.answer()


@router.message(AdminStates.broadcast_composing)
async def admin_broadcast_text_received(
    message: Message, state: FSMContext, user: User | None
) -> None:
    if user is None or not is_admin(user.telegram_id):
        await _denied(message)
        return
    html_text = message.html_text or ""
    await state.update_data(message_html=html_text)
    data = await state.get_data()
    await message.answer(
        f"👀 <b>پیش‌نمایش</b> (برای {data['target_count']} نفر):\n\n{html_text}\n\n"
        "می‌تونی متن جدیدی بفرستی تا جایگزین بشه، یا یکی از گزینه‌های زیر رو انتخاب کن.",
        reply_markup=broadcast_preview_keyboard(),
    )


@router.callback_query(F.data == "admin:bc:test")
async def admin_broadcast_test_send(
    callback: CallbackQuery, state: FSMContext, user: User | None, bot: Bot
) -> None:
    if user is None or not is_admin(user.telegram_id):
        await callback.answer()
        return
    data = await state.get_data()
    html_text = data.get("message_html", "")
    await bot.send_message(user.telegram_id, html_text, parse_mode="HTML")
    await callback.answer("✅ برای خودت فرستاده شد.", show_alert=True)


# --- pagination (shared by users / past-due / payments lists) ------------

@router.callback_query(F.data.startswith("admin:users:pg:"))
@router.callback_query(F.data.startswith("admin:pastdue:pg:"))
@router.callback_query(F.data.startswith("admin:pay:pg:"))
async def admin_list_page(callback: CallbackQuery, state: FSMContext) -> None:
    delta = int(callback.data.rsplit(":", 1)[1])
    data = await state.get_data()
    queue = data.get("queue")
    if not queue:
        await callback.answer()
        return
    new_index = data["index"] + delta
    if 0 <= new_index < len(queue):
        await state.update_data(index=new_index)
        await _render_list(callback.message, state)
    await callback.answer()


# --- mutating actions (extend / grant / cancel), confirm-gated -----------

@router.callback_query(F.data.startswith("admin:ext:"))
async def admin_extend_confirm(callback: CallbackQuery) -> None:
    _, _, user_id_s, days_s = callback.data.split(":")
    user_id, days = int(user_id_s), int(days_s)
    await callback.message.edit_text(
        f"مطمئنی می‌خوای <b>{days} روز</b> به دسترسی این کاربر اضافه کنی؟",
        reply_markup=confirm_keyboard(f"admin:go:ext:{user_id}:{days}", user_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:go:ext:"))
async def admin_extend_go(callback: CallbackQuery) -> None:
    _, _, _, user_id_s, days_s = callback.data.split(":")
    user_id, days = int(user_id_s), int(days_s)
    await admin_service.extend_access(user_id=user_id, days=days)
    await callback.answer("✅ انجام شد")
    await _show_profile(callback.message, user_id, edit=True)


@router.callback_query(F.data.startswith("admin:cxl:"))
async def admin_cancel_confirm(callback: CallbackQuery) -> None:
    user_id = int(callback.data.split(":")[2])
    await callback.message.edit_text(
        "مطمئنی می‌خوای اشتراک این کاربر رو لغو کنی؟\n"
        "(تمدید خودکار متوقف می‌شه، ولی دسترسی تا پایان دوره‌ی پرداخت‌شده باقی می‌مونه)",
        reply_markup=confirm_keyboard(f"admin:go:cxl:{user_id}", user_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:go:cxl:"))
async def admin_cancel_go(callback: CallbackQuery) -> None:
    user_id = int(callback.data.split(":")[3])
    await admin_service.cancel_subscription(user_id=user_id)
    await callback.answer("✅ لغو شد")
    await _show_profile(callback.message, user_id, edit=True)
