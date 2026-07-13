"""Standalone membership website — Telegram-compliant iDEAL checkout.

This is a *standalone website* (not a Telegram bot/Mini App), so it may accept
iDEAL. Flow: the bot links the user here with a signed token; they pay €4.99 via
Mollie iDEAL (a "first payment" that sets up a SEPA mandate); Mollie's webhook
confirms the payment, a monthly subscription is created, and the user's access
is activated in the shared database that the bot reads.

Run locally:  uvicorn webapp.main:app --reload --port 8100
"""

from __future__ import annotations

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
from webapp.api_questions import router as questions_router

logger = logging.getLogger(__name__)

app = FastAPI(title="NLern Abonnement")
app.include_router(questions_router)
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


def _now() -> datetime:
    return datetime.now(timezone.utc)


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
    user_id = verify_subscription_token(token) if token else None
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
    user_id = verify_subscription_token(token)
    if user_id is None:
        return _page("لینک نامعتبر", "<h1>🔗 لینک نامعتبر</h1><p>از ربات لینک تازه بگیر.</p>")
    if not _settings.subscription.mollie_enabled:
        return _page("به‌زودی", "<h1>⏳ پرداخت هنوز فعال نیست</h1><p>کمی بعد دوباره امتحان کن.</p>")

    async with get_db_session() as session:
        user = await session.scalar(select(User).where(User.id == user_id))
    if user is None:
        return _page("خطا", "<h1>کاربر پیدا نشد</h1><p>دوباره از ربات /start بزن.</p>")

    sub = await subs.get_or_create(user_id=user_id)
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
    payment = await mollie.get_payment(id)  # raises -> 500 -> Mollie retries
    meta = payment.get("metadata") or {}
    raw_uid = meta.get("user_id")
    if raw_uid is None:
        logger.warning("Mollie webhook %s has no user_id metadata", id)
        return PlainTextResponse("ok")
    user_id = int(raw_uid)
    status = payment.get("status")
    seq = payment.get("sequenceType")
    base = _settings.subscription.site_base_url.rstrip("/")

    if status == "paid":
        if seq == "first":
            customer_id = payment.get("customerId")
            sub_obj = await mollie.create_subscription(
                customer_id=customer_id,
                amount_eur=_PRICE,
                description="NLern — اشتراک ماهانه",
                webhook_url=f"{base}/webhook/mollie",
                start_date=_next_month(date.today()).isoformat(),
            )
            await subs.activate_until(
                user_id=user_id,
                period_end=_now() + timedelta(days=_ACCESS_DAYS),
                mollie_customer_id=customer_id,
                mollie_mandate_id=payment.get("mandateId"),
                mollie_subscription_id=sub_obj.get("id"),
            )
            logger.info("First payment paid; subscription started for user %s", user_id)
        elif seq == "recurring":
            await subs.activate_until(
                user_id=user_id, period_end=_now() + timedelta(days=_ACCESS_DAYS)
            )
            logger.info("Recurring payment paid; extended user %s", user_id)
    elif status in ("failed", "expired", "canceled") and seq == "recurring":
        await subs.mark_past_due(user_id=user_id)
        logger.info("Recurring payment %s for user %s; marked past_due", status, user_id)

    if status in ("paid", "failed", "expired", "canceled"):
        paid_at_raw = payment.get("paidAt")
        await subs.record_payment(
            user_id=user_id,
            mollie_payment_id=id,
            amount_eur=float(payment.get("amount", {}).get("value", _PRICE)),
            status=status,
            sequence_type=seq,
            paid_at=datetime.fromisoformat(paid_at_raw) if paid_at_raw else None,
        )

    return PlainTextResponse("ok")


@app.get("/account", response_class=HTMLResponse)
async def account_page(token: str = "") -> HTMLResponse:
    """Show subscription status, a cancel button, and recent payment history."""
    user_id = verify_subscription_token(token) if token else None
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

    cancel_html = ""
    if (
        sub is not None
        and sub.mollie_subscription_id
        and sub.status not in (subs.STATUS_CANCELED, subs.STATUS_EXPIRED)
    ):
        cancel_html = (
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
        f"{status_html}{cancel_html}{history_html}"
    )
    return _page("مدیریت اشتراک NLern", body)


@app.post("/account/cancel")
async def account_cancel(token: str = Form(...)):
    """Cancel the Mollie subscription (if any) and mark it canceled locally."""
    user_id = verify_subscription_token(token)
    if user_id is None:
        return _page("لینک نامعتبر", "<h1>🔗 لینک نامعتبر</h1><p>از ربات لینک تازه بگیر.</p>")

    sub = await subs.get_subscription(user_id=user_id)
    if sub is not None and sub.mollie_customer_id and sub.mollie_subscription_id:
        try:
            await mollie.cancel_subscription(
                customer_id=sub.mollie_customer_id,
                subscription_id=sub.mollie_subscription_id,
            )
        except mollie.MollieError:
            logger.warning("Mollie cancel failed for user %s (already gone?)", user_id, exc_info=True)

    await subs.cancel(user_id=user_id)
    return _page(
        "اشتراک لغو شد",
        "<h1>✅ اشتراکت لغو شد</h1>"
        "<p>تمدید خودکار متوقف شد. تا پایان دوره‌ی پرداخت‌شده همچنان دسترسی داری.</p>",
    )
