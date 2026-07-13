"""Subscription state — the source of truth for feature-access gating.

Read helpers (``has_active_subscription``, ``get_subscription``) are used by the
bot's access gate. Write helpers (``activate_until``, ``mark_past_due``,
``cancel``) are called by the payment webhook (and are handy for manual testing).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from bot.config import get_settings
from database.connection import get_db_session
from database.models import Payment, Subscription
from utils.tokens import make_subscription_token

logger = logging.getLogger(__name__)

# Subscription status values.
STATUS_PENDING = "pending"
STATUS_ACTIVE = "active"
STATUS_PAST_DUE = "past_due"
STATUS_CANCELED = "canceled"
STATUS_EXPIRED = "expired"

TRIAL_HOURS = 24


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    """Treat naive datetimes (possible from the driver) as UTC."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def is_active(sub: Subscription | None) -> bool:
    """Return True if the subscription grants access right now.

    Access lasts until ``current_period_end``. A *canceled* subscription keeps
    access until the paid period ends (only auto-renewal stops); ``pending``,
    ``past_due`` and ``expired`` grant no access.
    """
    if sub is None or sub.status not in (STATUS_ACTIVE, STATUS_CANCELED):
        return False
    end = _aware(sub.current_period_end)
    return end is not None and end > _now()


async def get_subscription(*, user_id: int) -> Subscription | None:
    """Return the user's subscription row, or None if they never started one."""
    async with get_db_session() as session:
        return await session.scalar(
            select(Subscription).where(Subscription.user_id == user_id)
        )


async def has_active_subscription(*, user_id: int) -> bool:
    """Return True if the user currently has access (active and not expired)."""
    return is_active(await get_subscription(user_id=user_id))


async def get_or_create(*, user_id: int) -> Subscription:
    """Return the user's subscription row, creating a 'pending' one if absent."""
    async with get_db_session() as session:
        sub = await session.scalar(
            select(Subscription).where(Subscription.user_id == user_id)
        )
        if sub is None:
            sub = Subscription(user_id=user_id, status=STATUS_PENDING)
            session.add(sub)
            await session.flush()
            await session.refresh(sub)
        return sub


async def activate_until(
    *,
    user_id: int,
    period_end: datetime,
    mollie_customer_id: str | None = None,
    mollie_mandate_id: str | None = None,
    mollie_subscription_id: str | None = None,
) -> Subscription:
    """Activate (or extend) a subscription until ``period_end``.

    Called after a successful (first or recurring) Mollie payment. Only
    overwrites Mollie identifiers when a new value is supplied.
    """
    async with get_db_session() as session:
        sub = await session.scalar(
            select(Subscription).where(Subscription.user_id == user_id)
        )
        if sub is None:
            sub = Subscription(user_id=user_id)
            session.add(sub)
        sub.status = STATUS_ACTIVE
        sub.current_period_end = period_end
        sub.canceled_at = None
        if mollie_customer_id is not None:
            sub.mollie_customer_id = mollie_customer_id
        if mollie_mandate_id is not None:
            sub.mollie_mandate_id = mollie_mandate_id
        if mollie_subscription_id is not None:
            sub.mollie_subscription_id = mollie_subscription_id
        await session.flush()
        await session.refresh(sub)
        logger.info("Subscription active for user %s until %s", user_id, period_end)
        return sub


async def is_trial_available(*, user_id: int) -> bool:
    """True if this user has never subscribed or trialed before.

    The trial is a first-timer perk: anyone with a subscription row that has
    ever gone beyond ``pending`` (activated, paid, canceled...) or already has
    ``trial_used_at`` set is ineligible.
    """
    sub = await get_subscription(user_id=user_id)
    if sub is None:
        return True
    return sub.status == STATUS_PENDING and sub.trial_used_at is None


async def start_trial(*, user_id: int) -> Subscription | None:
    """Grant a one-time, no-payment trial. Returns None if already used."""
    async with get_db_session() as session:
        sub = await session.scalar(
            select(Subscription).where(Subscription.user_id == user_id)
        )
        if sub is None:
            sub = Subscription(user_id=user_id)
            session.add(sub)
        elif not (sub.status == STATUS_PENDING and sub.trial_used_at is None):
            return None
        now = _now()
        sub.status = STATUS_ACTIVE
        sub.current_period_end = now + timedelta(hours=TRIAL_HOURS)
        sub.trial_used_at = now
        await session.flush()
        await session.refresh(sub)
        logger.info("Trial started for user %s until %s", user_id, sub.current_period_end)
        return sub


async def record_payment(
    *,
    user_id: int,
    mollie_payment_id: str,
    amount_eur: float,
    status: str,
    sequence_type: str | None,
    paid_at: datetime | None,
) -> None:
    """Log a Mollie payment for the account page's history list (idempotent)."""
    async with get_db_session() as session:
        existing = await session.scalar(
            select(Payment).where(Payment.mollie_payment_id == mollie_payment_id)
        )
        if existing is not None:
            existing.status = status
            existing.paid_at = paid_at
            return
        session.add(
            Payment(
                user_id=user_id,
                mollie_payment_id=mollie_payment_id,
                amount_eur=amount_eur,
                status=status,
                sequence_type=sequence_type,
                paid_at=paid_at,
            )
        )


async def list_payments(*, user_id: int, limit: int = 20) -> list[Payment]:
    """Return this user's most recent payments, newest first."""
    async with get_db_session() as session:
        result = await session.scalars(
            select(Payment)
            .where(Payment.user_id == user_id)
            .order_by(Payment.created_at.desc())
            .limit(limit)
        )
        return list(result)


def build_account_url(user_id: int) -> str:
    """Return the membership-site account-management URL for this user."""
    base = get_settings().subscription.site_base_url.rstrip("/")
    token = make_subscription_token(user_id)
    return f"{base}/account?token={token}"


async def set_mollie_customer(*, user_id: int, customer_id: str) -> None:
    """Persist the Mollie customer id (created during the first checkout)."""
    async with get_db_session() as session:
        sub = await session.scalar(
            select(Subscription).where(Subscription.user_id == user_id)
        )
        if sub is None:
            sub = Subscription(user_id=user_id, status=STATUS_PENDING)
            session.add(sub)
        sub.mollie_customer_id = customer_id


async def mark_past_due(*, user_id: int) -> None:
    """Mark a subscription as past_due (a recurring charge failed)."""
    async with get_db_session() as session:
        sub = await session.scalar(
            select(Subscription).where(Subscription.user_id == user_id)
        )
        if sub is not None:
            sub.status = STATUS_PAST_DUE


def build_checkout_url(user_id: int) -> str:
    """Return the membership-site URL carrying this user's signed token."""
    base = get_settings().subscription.site_base_url.rstrip("/")
    token = make_subscription_token(user_id)
    return f"{base}/abonnement?token={token}"


async def cancel(*, user_id: int) -> None:
    """Cancel a subscription. Access remains until ``current_period_end``."""
    async with get_db_session() as session:
        sub = await session.scalar(
            select(Subscription).where(Subscription.user_id == user_id)
        )
        if sub is not None:
            sub.status = STATUS_CANCELED
            sub.canceled_at = _now()
