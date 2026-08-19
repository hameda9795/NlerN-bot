"""Standalone membership website — Telegram-compliant iDEAL checkout.

This is a *standalone website* (not a Telegram bot/Mini App), so it may accept
iDEAL. Flow: the bot links the user here with a signed token; they pay €4.99 via
Mollie iDEAL (a "first payment" that sets up a SEPA mandate); Mollie's webhook
confirms the payment, a monthly subscription is created, and the user's access
is activated in the shared database that the bot reads.

Run locally:  uvicorn webapp.main:app --reload --port 8100
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone

from pathlib import Path

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from bot.config import get_settings
from database.connection import get_db_session
from database.models import User
from services import mollie_client as mollie
from services import subscription_service as subs
from utils.tokens import verify_subscription_token

logger = logging.getLogger(__name__)

app = FastAPI(title="NLern Abonnement")
# Self-hosted Vazirmatn (SIL OFL) so the Persian text renders in a proper
# Persian typeface everywhere, cached by the browser like any other asset —
# no external font CDN dependency (Google Fonts et al. can be slow/blocked
# for some users).
app.mount(
    "/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static"
)
_settings = get_settings()
_PRICE = _settings.subscription.price_eur
# One paid month of access, plus a few days' grace so a slightly delayed
# recurring charge never causes a coverage gap (the webhook re-extends monthly).
_ACCESS_DAYS = 34
_KVK = "99202301"
_TERMINAL_PAYMENT_STATUSES = {"paid", "failed", "expired", "canceled"}
_payment_flow_lock = asyncio.Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _verified_user_id(token: str) -> int | None:
    """Verify a short-lived membership-site bearer token."""
    if not token:
        return None
    return verify_subscription_token(
        token,
        max_age_seconds=_settings.subscription.token_max_age_seconds,
    )


def _next_month(d: date) -> date:
    """Same day next month (day clamped to 28 to stay valid)."""
    year, month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return date(year, month, min(d.day, 28))


def _page(title: str, body: str) -> HTMLResponse:
    html = f"""<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
 @font-face{{
   font-family:"Vazirmatn";font-style:normal;font-weight:400;font-display:swap;
   src:url("/static/fonts/Vazirmatn-Regular.woff2") format("woff2");
 }}
 @font-face{{
   font-family:"Vazirmatn";font-style:normal;font-weight:500;font-display:swap;
   src:url("/static/fonts/Vazirmatn-Medium.woff2") format("woff2");
 }}
 @font-face{{
   font-family:"Vazirmatn";font-style:normal;font-weight:700;font-display:swap;
   src:url("/static/fonts/Vazirmatn-Bold.woff2") format("woff2");
 }}
 :root{{
   --bg-1:#0b0f1f; --bg-2:#161b36; --accent-1:#7c6cff; --accent-2:#38d9c9;
   --ink:#161a2e; --muted:#7a8199; --card:#ffffff; --line:#e8e9f3;
   --ok:#0f9d63; --ok-bg:#e6f7ef; --warn:#b8860b; --warn-bg:#fbf3d9;
   --bad:#c23a4a; --bad-bg:#fbe9ec; --neutral:#5b6178; --neutral-bg:#eef0f7;
 }}
 *{{box-sizing:border-box}}
 body{{
   font-family:"Vazirmatn","Segoe UI",Tahoma,sans-serif;margin:0;color:var(--ink);
   min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;
   gap:18px;padding:20px 14px;
   background:
     radial-gradient(1100px 480px at 15% -10%, rgba(124,108,255,.35), transparent 60%),
     radial-gradient(900px 420px at 100% 0%, rgba(56,217,201,.22), transparent 55%),
     linear-gradient(180deg, var(--bg-1), var(--bg-2));
   background-attachment:fixed;
 }}
 .card{{
   background:var(--card);width:100%;max-width:420px;padding:28px 22px;border-radius:22px;
   box-shadow:0 24px 60px rgba(6,8,25,.45), 0 2px 8px rgba(6,8,25,.15);
   text-align:center;border:1px solid rgba(255,255,255,.06);
 }}
 h1{{font-size:1.32rem;margin:0 0 10px;letter-spacing:-.01em}}
 p{{line-height:1.85;color:#495066;margin:0 0 12px;font-size:.97rem}}
 .price{{
   font-size:2.4rem;font-weight:800;margin:16px 0 2px;letter-spacing:-.02em;
   background:linear-gradient(90deg,var(--accent-1),var(--accent-2));
   -webkit-background-clip:text;background-clip:text;color:transparent;
 }}
 .muted{{color:var(--muted);font-size:.88rem}}
 input{{
   width:100%;padding:13px 14px;border:1.5px solid var(--line);border-radius:12px;
   font-size:1rem;margin:9px 0;box-sizing:border-box;text-align:left;direction:ltr;
   background:#fbfbfe;transition:border-color .15s,box-shadow .15s;
 }}
 input:focus{{outline:none;border-color:var(--accent-1);box-shadow:0 0 0 4px rgba(124,108,255,.15)}}
 .btn{{
   width:100%;padding:15px;border:0;border-radius:14px;color:#fff;font-size:1.02rem;
   font-weight:700;cursor:pointer;margin-top:6px;
   background:linear-gradient(90deg,var(--accent-1),#6a5cf0);
   box-shadow:0 10px 24px rgba(124,108,255,.35);transition:transform .12s,box-shadow .12s;
 }}
 .btn:hover{{transform:translateY(-1px);box-shadow:0 14px 30px rgba(124,108,255,.42)}}
 .btn:active{{transform:translateY(0)}}
 .btn-secondary{{
   background:var(--neutral-bg);color:var(--neutral);box-shadow:none;font-weight:600;
 }}
 .btn-secondary:hover{{box-shadow:none;filter:brightness(.97)}}
 .ideal{{margin-top:16px;color:var(--muted);font-size:.82rem}}
 .badge{{
   display:inline-flex;align-items:center;gap:6px;padding:6px 14px;border-radius:999px;
   font-size:.86rem;font-weight:700;margin:6px 0 14px;
 }}
 .badge-ok{{background:var(--ok-bg);color:var(--ok)}}
 .badge-warn{{background:var(--warn-bg);color:var(--warn)}}
 .badge-bad{{background:var(--bad-bg);color:var(--bad)}}
 .badge-neutral{{background:var(--neutral-bg);color:var(--neutral)}}
 .history{{margin-top:18px;text-align:right}}
 .history-title{{font-size:.82rem;color:var(--muted);font-weight:700;margin-bottom:8px}}
 .history-row{{
   display:flex;align-items:center;justify-content:space-between;gap:10px;
   padding:11px 4px;border-top:1px solid var(--line);font-size:.88rem;
 }}
 .history-row:first-of-type{{border-top:none}}
 .history-date{{color:var(--muted);flex:1;text-align:right}}
 .history-amount{{font-weight:700;white-space:nowrap}}
 .footer{{
   color:rgba(235,236,245,.55);font-size:.78rem;line-height:1.9;text-align:center;
   max-width:420px;width:100%;padding:0 10px;
 }}
 .footer b{{color:rgba(235,236,245,.8);font-weight:500}}
 @media (min-width:640px){{
   .card{{max-width:460px;padding:36px 32px;border-radius:26px}}
   h1{{font-size:1.5rem}}
   .price{{font-size:2.7rem}}
 }}
</style></head><body><div class="card">{body}</div>
<div class="footer">
 © {_now().year} <b>techsolutionsutrecht</b> — تمام حقوق مادی و معنوی این وب‌سایت متعلق به این شرکت است.<br>
 KVK: {_KVK}
</div>
</body></html>"""
    return HTMLResponse(html)


def _badge(text: str, kind: str) -> str:
    return f'<span class="badge badge-{kind}">{text}</span>'


@app.get("/health")
async def health() -> PlainTextResponse:
    return PlainTextResponse("ok")


@app.get("/abonnement", response_class=HTMLResponse)
async def page(token: str = "") -> HTMLResponse:
    """Show the plan + payment form for the user identified by the token."""
    user_id = _verified_user_id(token)
    if user_id is None:
        return _page(
            "لینک نامعتبر",
            "<h1>🔗 لینک نامعتبر یا منقضی</h1>"
            "<p>لطفاً دوباره از داخل ربات روی «💳 اشتراک» بزن تا لینک تازه بگیری.</p>",
        )
    body = (
        "<h1>🇳🇱 اشتراک NLern</h1>"
        "<p>دسترسی کامل به همه‌ی بخش‌های ربات یادگیری هلندی.</p>"
        f'<div class="price">€{_PRICE:.2f}</div><div class="muted">ماهانه — قابل لغو</div>'
        f'<form method="post" action="/abonnement/pay">'
        f'<input type="hidden" name="token" value="{token}">'
        '<input type="email" name="email" placeholder="ایمیل (برای رسید)" required>'
        '<button type="submit" class="btn">پرداخت با iDEAL</button></form>'
        '<div class="ideal">پرداخت امن از طریق Mollie · iDEAL</div>'
    )
    return _page("اشتراک NLern", body)


@app.post("/abonnement/pay")
async def pay(token: str = Form(...), email: str = Form(...)):
    """Create the Mollie customer + first iDEAL payment, then redirect to Mollie."""
    user_id = _verified_user_id(token)
    if user_id is None:
        return _page("لینک نامعتبر", "<h1>🔗 لینک نامعتبر</h1><p>از ربات لینک تازه بگیر.</p>")
    if not _settings.subscription.mollie_enabled:
        return _page("به‌زودی", "<h1>⏳ پرداخت هنوز فعال نیست</h1><p>کمی بعد دوباره امتحان کن.</p>")

    async with get_db_session() as session:
        user = await session.scalar(select(User).where(User.id == user_id))
    if user is None:
        return _page("خطا", "<h1>کاربر پیدا نشد</h1><p>دوباره از ربات /start بزن.</p>")

    # The deployed web container runs one worker. Serializing its short payment
    # state transitions closes double-click and webhook interleaving races.
    async with _payment_flow_lock:
        return await _create_or_reuse_checkout(user_id=user_id, email=email, user=user)


async def _create_or_reuse_checkout(
    *, user_id: int, email: str, user: User
) -> HTMLResponse | RedirectResponse:
    """Reuse an unfinished checkout or create exactly one new first payment."""

    sub = await subs.get_or_create(user_id=user_id)
    if sub.mollie_subscription_id and sub.status == subs.STATUS_PAST_DUE:
        return _page(
            "پرداخت در حال پیگیری",
            "<h1>⏳ پرداخت قبلی در حال پیگیری است</h1>"
            "<p>Mollie پرداخت ناموفق را خودکار دوباره امتحان می‌کند. "
            "برای جلوگیری از برداشت دوباره، پرداخت جدیدی ساخته نشد. "
            "اگر می‌خواهی روش پرداخت را از نو تنظیم کنی، از بخش مدیریت "
            "اشتراک داخل ربات گزینه «لغو و شروع دوباره» را بزن.</p>",
        )
    if (
        sub.mollie_subscription_id
        and sub.status not in (subs.STATUS_CANCELED, subs.STATUS_EXPIRED)
    ):
        return _page(
            "اشتراک موجود",
            "<h1>✅ اشتراک قبلاً ساخته شده</h1>"
            "<p>برای جلوگیری از برداشت دوباره، پرداخت جدیدی ایجاد نشد. "
            "وضعیت اشتراکت را از بخش مدیریت اشتراک داخل ربات ببین.</p>",
        )

    pending_payment = await subs.get_pending_first_payment(user_id=user_id)
    if pending_payment is not None:
        existing_payment = await mollie.get_payment(
            pending_payment.mollie_payment_id
        )
        existing_status = str(existing_payment.get("status") or "open")
        if existing_status not in _TERMINAL_PAYMENT_STATUSES:
            checkout = (
                existing_payment.get("_links", {})
                .get("checkout", {})
                .get("href")
            )
            if checkout:
                return RedirectResponse(checkout, status_code=303)
            return _page(
                "پرداخت در انتظار",
                "<h1>⏳ یک پرداخت در حال بررسی است</h1>"
                "<p>چند دقیقه بعد دوباره وضعیت اشتراک را داخل ربات بررسی کن.</p>",
            )
        await subs.record_payment(
            user_id=user_id,
            mollie_payment_id=pending_payment.mollie_payment_id,
            amount_eur=float(
                existing_payment.get("amount", {}).get("value", _PRICE)
            ),
            status=existing_status,
            sequence_type="first",
            paid_at=None,
        )
        if existing_status == "paid":
            return _page(
                "پرداخت تأیید شد",
                "<h1>✅ پرداخت قبلی تأیید شده</h1>"
                "<p>اشتراکت در حال فعال‌شدن است؛ پرداخت جدیدی ایجاد نشد.</p>",
            )

    customer_id = sub.mollie_customer_id
    if not customer_id:
        customer = await mollie.create_customer(
            name=user.first_name or f"user_{user_id}", email=email
        )
        customer_id = customer["id"]
        await subs.set_mollie_customer(user_id=user_id, customer_id=customer_id)

    base = _settings.subscription.site_base_url.rstrip("/")
    payment = await mollie.create_first_payment(
        customer_id=customer_id,
        amount_eur=_PRICE,
        description="NLern — اشتراک ماهانه",
        redirect_url=f"{base}/abonnement/klaar",
        webhook_url=f"{base}/webhook/mollie",
        metadata={"user_id": user_id},
    )
    checkout = payment.get("_links", {}).get("checkout", {}).get("href")
    if not checkout:
        return _page("خطا", "<h1>خطا در ایجاد پرداخت</h1><p>کمی بعد دوباره امتحان کن.</p>")
    await subs.record_payment(
        user_id=user_id,
        mollie_payment_id=str(payment["id"]),
        amount_eur=_PRICE,
        status=str(payment.get("status") or "open"),
        sequence_type="first",
        paid_at=None,
    )
    return RedirectResponse(checkout, status_code=303)


@app.get("/abonnement/klaar", response_class=HTMLResponse)
async def done() -> HTMLResponse:
    return _page(
        "ممنون",
        "<h1>✅ ممنون!</h1>"
        "<p>پرداختت در حال بررسیه. به‌محض تأیید، اشتراکت داخل ربات فعال می‌شه "
        "و پیام می‌گیری. می‌تونی این صفحه رو ببندی و به تلگرام برگردی. 🌷</p>",
    )


@app.post("/webhook/mollie")
async def webhook(id: str = Form(...)) -> PlainTextResponse:
    """Mollie calls this with a payment id; we fetch the real status from Mollie."""
    async with _payment_flow_lock:
        payment = await mollie.get_payment(id)  # raises -> 500 -> Mollie retries
        status = str(payment.get("status") or "")
        seq = payment.get("sequenceType")
        if status in _TERMINAL_PAYMENT_STATUSES and await subs.payment_has_status(
            mollie_payment_id=id, status=status
        ):
            return PlainTextResponse("ok")

        meta = payment.get("metadata") or {}
        raw_uid = meta.get("user_id")
        user_id: int | None = None
        if raw_uid is not None:
            try:
                user_id = int(raw_uid)
            except (TypeError, ValueError):
                logger.warning("Mollie webhook %s has invalid user_id metadata", id)

        mollie_subscription_id = payment.get("subscriptionId")
        if user_id is None and mollie_subscription_id:
            local_sub = await subs.get_subscription_by_mollie_id(
                mollie_subscription_id=str(mollie_subscription_id)
            )
            if local_sub is not None:
                user_id = local_sub.user_id

        if user_id is None:
            logger.warning(
                "Mollie webhook %s cannot be associated with a local user", id
            )
            return PlainTextResponse("ok")

        base = _settings.subscription.site_base_url.rstrip("/")
        if status == "paid":
            if seq == "first":
                current_sub = await subs.get_subscription(user_id=user_id)
                has_current_recurring = bool(
                    current_sub
                    and current_sub.mollie_subscription_id
                    and current_sub.status
                    not in (subs.STATUS_CANCELED, subs.STATUS_EXPIRED)
                )
                if not has_current_recurring:
                    customer_id = payment.get("customerId")
                    if not customer_id:
                        raise mollie.MollieError(
                            "Paid first payment has no Mollie customer id."
                        )
                    sub_obj = await mollie.create_subscription(
                        customer_id=customer_id,
                        amount_eur=_PRICE,
                        description="NLern — اشتراک ماهانه",
                        webhook_url=f"{base}/webhook/mollie",
                        start_date=_next_month(date.today()).isoformat(),
                    )
                    new_subscription_id = sub_obj.get("id")
                    if not new_subscription_id:
                        raise mollie.MollieError(
                            "Mollie create-subscription response has no id."
                        )
                    await subs.activate_until(
                        user_id=user_id,
                        period_end=_now() + timedelta(days=_ACCESS_DAYS),
                        mollie_customer_id=customer_id,
                        mollie_mandate_id=payment.get("mandateId"),
                        mollie_subscription_id=str(new_subscription_id),
                    )
                    logger.info(
                        "First payment paid; subscription started for user %s",
                        user_id,
                    )
                else:
                    logger.info(
                        "Ignored duplicate first-payment subscription creation for user %s",
                        user_id,
                    )
            elif seq == "recurring":
                await subs.activate_until(
                    user_id=user_id,
                    period_end=_now() + timedelta(days=_ACCESS_DAYS),
                )
                logger.info("Recurring payment paid; extended user %s", user_id)
        elif status in ("failed", "expired", "canceled") and seq == "recurring":
            await subs.mark_past_due(user_id=user_id)
            logger.info(
                "Recurring payment %s for user %s; marked past_due",
                status,
                user_id,
            )

        if status in _TERMINAL_PAYMENT_STATUSES:
            paid_at_raw = payment.get("paidAt")
            await subs.record_payment(
                user_id=user_id,
                mollie_payment_id=id,
                amount_eur=float(
                    payment.get("amount", {}).get("value", _PRICE)
                ),
                status=status,
                sequence_type=seq,
                paid_at=(
                    datetime.fromisoformat(paid_at_raw) if paid_at_raw else None
                ),
            )

    return PlainTextResponse("ok")


@app.get("/account", response_class=HTMLResponse)
async def account_page(token: str = "") -> HTMLResponse:
    """Show subscription status, a cancel button, and recent payment history."""
    user_id = _verified_user_id(token)
    if user_id is None:
        return _page(
            "لینک نامعتبر",
            "<h1>🔗 لینک نامعتبر یا منقضی</h1>"
            "<p>لطفاً دوباره از داخل ربات روی «💳 اشتراک» بزن تا لینک تازه بگیری.</p>",
        )

    sub = await subs.get_subscription(user_id=user_id)
    payments = await subs.list_payments(user_id=user_id)

    if sub is None:
        status_html = _badge("هنوز اشتراکی نداری", "neutral")
    else:
        is_trial = sub.trial_used_at is not None and sub.mollie_subscription_id is None
        until = sub.current_period_end.strftime("%Y-%m-%d") if sub.current_period_end else "—"
        if is_trial and subs.is_active(sub):
            status_html = _badge(f"🎁 روز رایگان — تا {until}", "warn")
        elif subs.is_active(sub) and sub.status == subs.STATUS_CANCELED:
            status_html = _badge(f"لغو شده — دسترسی تا {until}", "warn")
        elif subs.is_active(sub):
            status_html = _badge(f"فعال — تا {until}", "ok")
        elif sub.status == subs.STATUS_PAST_DUE:
            status_html = _badge("پرداخت ناموفق", "bad")
        else:
            status_html = _badge(sub.status, "neutral")

    action_html = ""
    if (
        sub is not None
        and sub.mollie_subscription_id
        and sub.status == subs.STATUS_PAST_DUE
    ):
        action_html = (
            '<p class="muted">Mollie پرداخت را تا چند بار خودکار دوباره امتحان می‌کند. '
            "می‌توانی منتظر بمانی؛ یا اشتراک قبلی را لغو و روش پرداخت را از نو تنظیم کنی.</p>"
            '<form method="post" action="/account/restart">'
            f'<input type="hidden" name="token" value="{token}">'
            '<button type="submit" class="btn">لغو و شروع دوباره</button></form>'
        )
    elif (
        sub is not None
        and sub.mollie_subscription_id
        and sub.status not in (subs.STATUS_CANCELED, subs.STATUS_EXPIRED)
    ):
        action_html = (
            f'<form method="post" action="/account/cancel">'
            f'<input type="hidden" name="token" value="{token}">'
            '<button type="submit" class="btn btn-secondary">لغو اشتراک</button></form>'
        )

    if payments:
        rows = "".join(
            '<div class="history-row">'
            f'<span class="history-date">{p.created_at.strftime("%Y-%m-%d")}</span>'
            f'<span class="history-amount">€{p.amount_eur:.2f}</span>'
            f"{_badge(p.status, 'ok' if p.status == 'paid' else 'bad')}"
            "</div>"
            for p in payments
        )
        history_html = f'<div class="history"><div class="history-title">تاریخچه‌ی پرداخت</div>{rows}</div>'
    else:
        history_html = '<p class="muted">هنوز پرداختی ثبت نشده.</p>'

    body = (
        "<h1>⚙️ مدیریت اشتراک</h1>"
        f"{status_html}{action_html}{history_html}"
    )
    return _page("مدیریت اشتراک NLern", body)


@app.post("/account/restart")
async def account_restart(token: str = Form(...)):
    """Cancel a past-due remote subscription before enabling a fresh checkout."""
    user_id = _verified_user_id(token)
    if user_id is None:
        return _page(
            "لینک نامعتبر",
            "<h1>🔗 لینک نامعتبر</h1><p>از ربات لینک تازه بگیر.</p>",
        )

    async with _payment_flow_lock:
        sub = await subs.get_subscription(user_id=user_id)
        if sub is None or sub.status != subs.STATUS_PAST_DUE:
            return _page(
                "امکان شروع دوباره نیست",
                "<h1>ℹ️ اشتراک در وضعیت پرداخت ناموفق نیست</h1>"
                "<p>وضعیت اشتراکت را دوباره از داخل ربات باز کن.</p>",
            )
        if not sub.mollie_customer_id or not sub.mollie_subscription_id:
            logger.error("Past-due user %s has incomplete Mollie identifiers", user_id)
            return _page(
                "خطا",
                "<h1>⚠️ شروع دوباره ممکن نشد</h1>"
                "<p>لطفاً با مدیریت تماس بگیر؛ پرداخت جدیدی ایجاد نشده است.</p>",
            )

        try:
            remote_sub = await mollie.get_subscription(
                customer_id=sub.mollie_customer_id,
                subscription_id=sub.mollie_subscription_id,
            )
            if remote_sub.get("status") != "canceled":
                await mollie.cancel_subscription(
                    customer_id=sub.mollie_customer_id,
                    subscription_id=sub.mollie_subscription_id,
                )
        except mollie.MollieError as exc:
            if exc.status_code == 404:
                logger.info(
                    "Past-due Mollie subscription already absent for user %s",
                    user_id,
                )
            else:
                logger.exception(
                    "Could not confirm cancellation before restarting user %s",
                    user_id,
                )
                return _page(
                    "لغو ناموفق",
                    "<h1>⚠️ لغو اشتراک قبلی تأیید نشد</h1>"
                    "<p>برای جلوگیری از برداشت دوباره، پرداخت جدیدی ساخته نشد. "
                    "کمی بعد دوباره امتحان کن یا با مدیریت تماس بگیر.</p>",
                )

        await subs.prepare_subscription_restart(user_id=user_id)

    return RedirectResponse(f"/abonnement?token={token}", status_code=303)


@app.post("/account/cancel")
async def account_cancel(token: str = Form(...)):
    """Cancel the Mollie subscription (if any) and mark it canceled locally."""
    user_id = _verified_user_id(token)
    if user_id is None:
        return _page("لینک نامعتبر", "<h1>🔗 لینک نامعتبر</h1><p>از ربات لینک تازه بگیر.</p>")

    sub = await subs.get_subscription(user_id=user_id)
    if sub is not None and sub.mollie_customer_id and sub.mollie_subscription_id:
        try:
            remote_sub = await mollie.get_subscription(
                customer_id=sub.mollie_customer_id,
                subscription_id=sub.mollie_subscription_id,
            )
            if remote_sub.get("status") != "canceled":
                await mollie.cancel_subscription(
                    customer_id=sub.mollie_customer_id,
                    subscription_id=sub.mollie_subscription_id,
                )
        except mollie.MollieError as exc:
            if exc.status_code == 404:
                logger.info("Mollie subscription already absent for user %s", user_id)
            else:
                logger.exception("Mollie cancel failed for user %s", user_id)
                return _page(
                    "لغو ناموفق",
                    "<h1>⚠️ لغو اشتراک تأیید نشد</h1>"
                    "<p>وضعیت اشتراک محلی تغییر نکرد. کمی بعد دوباره امتحان کن "
                    "یا با مدیریت تماس بگیر.</p>",
                )

    await subs.cancel(user_id=user_id)
    return _page(
        "اشتراک لغو شد",
        "<h1>✅ اشتراکت لغو شد</h1>"
        "<p>تمدید خودکار متوقف شد. تا پایان دوره‌ی پرداخت‌شده همچنان دسترسی داری.</p>",
    )
