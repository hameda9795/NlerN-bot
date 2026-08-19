"""Read-only aggregate queries and admin actions for the in-bot admin dashboard.

Kept separate from ``subscription_service`` (which is the source of truth for
the access gate) — this module composes it plus a few dashboard-only queries.
The user base is small enough today that list views load everything in one
query and let the handler paginate client-side (same pattern already used by
``handlers/vocab_b2.py``'s word-browsing queues), rather than building real
DB-side pagination.
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from database.connection import get_db_session
from database.models import Payment, Subscription, User
from services import mollie_client as mollie
from services import subscription_service as subs

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def get_user_by_id(user_id: int) -> User | None:
    async with get_db_session() as session:
        return await session.get(User, user_id)


async def count_users() -> int:
    async with get_db_session() as session:
        return int(await session.scalar(select(func.count()).select_from(User)) or 0)


async def count_by_subscription_status() -> dict[str, int]:
    """Bucket every subscription row by status, plus a "trialing" split of
    active rows that are on the free trial (no Mollie subscription yet), and
    a "none" bucket for users who never started a subscription at all.
    """
    counts = {
        "active": 0,
        "trialing": 0,
        "past_due": 0,
        "canceled": 0,
        "pending": 0,
        "expired": 0,
        "none": 0,
    }
    async with get_db_session() as session:
        total_users = await session.scalar(select(func.count()).select_from(User))
        all_subs = list(await session.scalars(select(Subscription)))
    for sub in all_subs:
        if (
            sub.status == subs.STATUS_ACTIVE
            and sub.trial_used_at is not None
            and sub.mollie_subscription_id is None
        ):
            counts["trialing"] += 1
        elif sub.status in counts:
            counts[sub.status] += 1
    counts["none"] = max(0, int(total_users or 0) - len(all_subs))
    return counts


async def revenue_this_month() -> float:
    now = _now()
    start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    async with get_db_session() as session:
        total = await session.scalar(
            select(func.coalesce(func.sum(Payment.amount_eur), 0.0)).where(
                Payment.status == "paid", Payment.paid_at >= start
            )
        )
    return float(total or 0.0)


async def search_users(query: str, limit: int = 10) -> list[User]:
    """Numeric queries match the Telegram id exactly; otherwise ILIKE on username."""
    q = query.strip().lstrip("@")
    async with get_db_session() as session:
        stmt = select(User)
        if q.isdigit():
            stmt = stmt.where(User.telegram_id == int(q))
        else:
            stmt = stmt.where(User.username.ilike(f"%{q}%"))
        stmt = stmt.order_by(User.last_active_at.desc()).limit(limit)
        return list(await session.scalars(stmt))


async def list_users(limit: int = 500) -> list[User]:
    async with get_db_session() as session:
        stmt = select(User).order_by(User.last_active_at.desc()).limit(limit)
        return list(await session.scalars(stmt))


async def list_past_due_subscriptions() -> list[Subscription]:
    async with get_db_session() as session:
        stmt = (
            select(Subscription)
            .where(Subscription.status == subs.STATUS_PAST_DUE)
            .options(selectinload(Subscription.user))
            .order_by(Subscription.updated_at.desc())
        )
        return list(await session.scalars(stmt))


async def list_recent_payments(limit: int = 30) -> list[Payment]:
    async with get_db_session() as session:
        stmt = (
            select(Payment)
            .options(selectinload(Payment.user))
            .order_by(Payment.created_at.desc())
            .limit(limit)
        )
        return list(await session.scalars(stmt))


async def export_payments_csv() -> bytes:
    """All payments as a CSV (bytes, UTF-8 with a BOM so Excel opens it cleanly)."""
    async with get_db_session() as session:
        stmt = (
            select(Payment)
            .options(selectinload(Payment.user))
            .order_by(Payment.created_at.desc())
        )
        payments = list(await session.scalars(stmt))

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["date", "telegram_id", "username", "amount_eur", "status", "sequence_type"])
    for p in payments:
        writer.writerow([
            p.created_at.strftime("%Y-%m-%d %H:%M"),
            p.user.telegram_id if p.user else "",
            p.user.username if p.user else "",
            f"{p.amount_eur:.2f}",
            p.status,
            p.sequence_type or "",
        ])
    return buf.getvalue().encode("utf-8-sig")


async def extend_access(*, user_id: int, days: int) -> Subscription:
    """Extend (or grant) access by ``days``, stacking on top of remaining time.

    Used for both admin "extend" and "free comp grant" actions — deliberately
    does not touch Mollie fields or ``trial_used_at``, so it never interferes
    with a real paid subscription or burns the user's trial eligibility.
    """
    current = await subs.get_subscription(user_id=user_id)
    base = current.current_period_end if current and subs.is_active(current) else None
    base = base or _now()
    return await subs.activate_until(user_id=user_id, period_end=base + timedelta(days=days))


async def cancel_subscription(*, user_id: int) -> None:
    """Cancel a user's subscription: stop Mollie auto-renewal, keep access
    until the current paid period ends (same semantics as the website's
    own cancel flow in ``webapp/main.py``).
    """
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
                logger.exception("Admin Mollie cancel failed for user %s", user_id)
                raise
    await subs.cancel(user_id=user_id)
