"""Regression tests for the security-critical Mollie membership flow."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Payment, Subscription, User
from services import subscription_service as subs
from utils.tokens import make_subscription_token
from webapp import main as web


@pytest.fixture
def subscription_db(monkeypatch, session_factory):
    """Point the web layer and subscription service at the test database."""

    @asynccontextmanager
    async def fake_session() -> AsyncIterator[AsyncSession]:
        session = session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    monkeypatch.setattr(subs, "get_db_session", fake_session)
    monkeypatch.setattr(web, "get_db_session", fake_session)
    return fake_session


async def _seed_user(
    session_factory,
    *,
    status: str = subs.STATUS_PENDING,
    mollie_subscription_id: str | None = None,
) -> int:
    async with session_factory() as session:
        user = User(telegram_id=987654321, first_name="Test")
        session.add(user)
        await session.flush()
        session.add(
            Subscription(
                user_id=user.id,
                status=status,
                current_period_end=(
                    datetime.now(timezone.utc) + timedelta(days=10)
                    if status == subs.STATUS_ACTIVE
                    else None
                ),
                mollie_customer_id="cst_test",
                mollie_subscription_id=mollie_subscription_id,
            )
        )
        await session.commit()
        return user.id


@pytest.mark.asyncio
async def test_recurring_webhook_resolves_user_from_subscription_id(
    monkeypatch, session_factory, subscription_db
):
    user_id = await _seed_user(
        session_factory,
        status=subs.STATUS_ACTIVE,
        mollie_subscription_id="sub_existing",
    )
    monkeypatch.setattr(
        web.mollie,
        "get_payment",
        AsyncMock(
            return_value={
                "id": "tr_recurring",
                "status": "paid",
                "sequenceType": "recurring",
                "subscriptionId": "sub_existing",
                "amount": {"value": "4.99"},
                "paidAt": "2026-08-19T10:00:00+00:00",
            }
        ),
    )
    create_subscription = AsyncMock()
    monkeypatch.setattr(web.mollie, "create_subscription", create_subscription)

    response = await web.webhook(id="tr_recurring")

    assert response.status_code == 200
    create_subscription.assert_not_awaited()
    async with session_factory() as session:
        sub = await session.scalar(
            select(Subscription).where(Subscription.user_id == user_id)
        )
        payment = await session.scalar(
            select(Payment).where(Payment.mollie_payment_id == "tr_recurring")
        )
    assert sub is not None and sub.status == subs.STATUS_ACTIVE
    assert payment is not None and payment.user_id == user_id
    assert payment.status == "paid"


@pytest.mark.asyncio
async def test_failed_recurring_payment_marks_subscription_past_due(
    monkeypatch, session_factory, subscription_db
):
    user_id = await _seed_user(
        session_factory,
        status=subs.STATUS_ACTIVE,
        mollie_subscription_id="sub_failed",
    )
    monkeypatch.setattr(
        web.mollie,
        "get_payment",
        AsyncMock(
            return_value={
                "id": "tr_failed",
                "status": "failed",
                "sequenceType": "recurring",
                "subscriptionId": "sub_failed",
                "amount": {"value": "4.99"},
            }
        ),
    )

    await web.webhook(id="tr_failed")

    async with session_factory() as session:
        sub = await session.scalar(
            select(Subscription).where(Subscription.user_id == user_id)
        )
    assert sub is not None and sub.status == subs.STATUS_PAST_DUE


@pytest.mark.asyncio
async def test_past_due_checkout_is_blocked_with_recovery_guidance(
    monkeypatch, session_factory, subscription_db
):
    user_id = await _seed_user(
        session_factory,
        status=subs.STATUS_PAST_DUE,
        mollie_subscription_id="sub_retrying",
    )
    monkeypatch.setattr(web._settings.subscription, "mollie_api_key", "test_key")
    create_payment = AsyncMock()
    monkeypatch.setattr(web.mollie, "create_first_payment", create_payment)

    response = await web.pay(
        token=make_subscription_token(user_id), email="learner@example.com"
    )

    assert response.status_code == 200
    assert "لغو و شروع دوباره" in response.body.decode("utf-8")
    create_payment.assert_not_awaited()


@pytest.mark.asyncio
async def test_past_due_account_offers_explicit_restart(
    session_factory, subscription_db
):
    user_id = await _seed_user(
        session_factory,
        status=subs.STATUS_PAST_DUE,
        mollie_subscription_id="sub_retrying",
    )

    response = await web.account_page(token=make_subscription_token(user_id))

    body = response.body.decode("utf-8")
    assert 'action="/account/restart"' in body
    assert "خودکار دوباره امتحان می‌کند" in body


@pytest.mark.asyncio
async def test_restart_cancels_remote_subscription_before_clearing_local_id(
    monkeypatch, session_factory, subscription_db
):
    user_id = await _seed_user(
        session_factory,
        status=subs.STATUS_PAST_DUE,
        mollie_subscription_id="sub_old",
    )
    monkeypatch.setattr(
        web.mollie,
        "get_subscription",
        AsyncMock(return_value={"id": "sub_old", "status": "active"}),
    )
    cancel_subscription = AsyncMock(return_value=None)
    monkeypatch.setattr(web.mollie, "cancel_subscription", cancel_subscription)

    token = make_subscription_token(user_id)
    response = await web.account_restart(token=token)

    assert response.status_code == 303
    assert response.headers["location"] == f"/abonnement?token={token}"
    cancel_subscription.assert_awaited_once_with(
        customer_id="cst_test", subscription_id="sub_old"
    )
    async with session_factory() as session:
        sub = await session.scalar(
            select(Subscription).where(Subscription.user_id == user_id)
        )
    assert sub is not None
    assert sub.status == subs.STATUS_PENDING
    assert sub.mollie_subscription_id is None


@pytest.mark.asyncio
async def test_restart_failure_preserves_old_subscription(
    monkeypatch, session_factory, subscription_db
):
    user_id = await _seed_user(
        session_factory,
        status=subs.STATUS_PAST_DUE,
        mollie_subscription_id="sub_keep",
    )
    monkeypatch.setattr(
        web.mollie,
        "get_subscription",
        AsyncMock(side_effect=web.mollie.MollieError("temporary failure")),
    )

    response = await web.account_restart(token=make_subscription_token(user_id))

    assert response.status_code == 200
    assert "پرداخت جدیدی ساخته نشد" in response.body.decode("utf-8")
    async with session_factory() as session:
        sub = await session.scalar(
            select(Subscription).where(Subscription.user_id == user_id)
        )
    assert sub is not None
    assert sub.status == subs.STATUS_PAST_DUE
    assert sub.mollie_subscription_id == "sub_keep"


@pytest.mark.asyncio
async def test_restart_treats_remote_404_as_safe_to_replace(
    monkeypatch, session_factory, subscription_db
):
    user_id = await _seed_user(
        session_factory,
        status=subs.STATUS_PAST_DUE,
        mollie_subscription_id="sub_gone",
    )
    monkeypatch.setattr(
        web.mollie,
        "get_subscription",
        AsyncMock(
            side_effect=web.mollie.MollieError("not found", status_code=404)
        ),
    )

    response = await web.account_restart(token=make_subscription_token(user_id))

    assert response.status_code == 303
    async with session_factory() as session:
        sub = await session.scalar(
            select(Subscription).where(Subscription.user_id == user_id)
        )
    assert sub is not None
    assert sub.status == subs.STATUS_PENDING
    assert sub.mollie_subscription_id is None


@pytest.mark.asyncio
async def test_cancel_failure_does_not_claim_local_cancellation(
    monkeypatch, session_factory, subscription_db
):
    user_id = await _seed_user(
        session_factory,
        status=subs.STATUS_ACTIVE,
        mollie_subscription_id="sub_active",
    )
    monkeypatch.setattr(
        web.mollie,
        "get_subscription",
        AsyncMock(side_effect=web.mollie.MollieError("temporary failure")),
    )

    response = await web.account_cancel(token=make_subscription_token(user_id))

    assert response.status_code == 200
    assert "وضعیت اشتراک محلی تغییر نکرد" in response.body.decode("utf-8")
    async with session_factory() as session:
        sub = await session.scalar(
            select(Subscription).where(Subscription.user_id == user_id)
        )
    assert sub is not None and sub.status == subs.STATUS_ACTIVE


@pytest.mark.asyncio
async def test_duplicate_first_payment_webhook_creates_one_subscription(
    monkeypatch, session_factory, subscription_db
):
    user_id = await _seed_user(session_factory)
    monkeypatch.setattr(
        web.mollie,
        "get_payment",
        AsyncMock(
            return_value={
                "id": "tr_first",
                "status": "paid",
                "sequenceType": "first",
                "customerId": "cst_test",
                "mandateId": "mdt_test",
                "metadata": {"user_id": user_id},
                "amount": {"value": "4.99"},
                "paidAt": "2026-08-19T10:00:00+00:00",
            }
        ),
    )
    create_subscription = AsyncMock(return_value={"id": "sub_new"})
    monkeypatch.setattr(web.mollie, "create_subscription", create_subscription)

    await asyncio.gather(
        web.webhook(id="tr_first"),
        web.webhook(id="tr_first"),
    )

    create_subscription.assert_awaited_once()
    async with session_factory() as session:
        sub = await session.scalar(
            select(Subscription).where(Subscription.user_id == user_id)
        )
        payment_count = await session.scalar(
            select(func.count(Payment.id)).where(
                Payment.mollie_payment_id == "tr_first"
            )
        )
    assert sub is not None and sub.mollie_subscription_id == "sub_new"
    assert payment_count == 1


@pytest.mark.asyncio
async def test_active_subscription_cannot_start_another_checkout(
    monkeypatch, session_factory, subscription_db
):
    user_id = await _seed_user(
        session_factory,
        status=subs.STATUS_ACTIVE,
        mollie_subscription_id="sub_active",
    )
    monkeypatch.setattr(web._settings.subscription, "mollie_api_key", "test_key")
    create_payment = AsyncMock()
    monkeypatch.setattr(web.mollie, "create_first_payment", create_payment)

    response = await web.pay(
        token=make_subscription_token(user_id), email="learner@example.com"
    )

    assert response.status_code == 200
    assert "پرداخت جدیدی ایجاد نشد" in response.body.decode("utf-8")
    create_payment.assert_not_awaited()


@pytest.mark.asyncio
async def test_pending_checkout_is_reused(
    monkeypatch, session_factory, subscription_db
):
    user_id = await _seed_user(session_factory)
    async with session_factory() as session:
        session.add(
            Payment(
                user_id=user_id,
                mollie_payment_id="tr_open",
                amount_eur=4.99,
                status="open",
                sequence_type="first",
            )
        )
        await session.commit()
    monkeypatch.setattr(web._settings.subscription, "mollie_api_key", "test_key")
    monkeypatch.setattr(
        web.mollie,
        "get_payment",
        AsyncMock(
            return_value={
                "id": "tr_open",
                "status": "open",
                "_links": {"checkout": {"href": "https://pay.test/existing"}},
            }
        ),
    )
    create_payment = AsyncMock()
    monkeypatch.setattr(web.mollie, "create_first_payment", create_payment)

    response = await web.pay(
        token=make_subscription_token(user_id), email="learner@example.com"
    )

    assert response.status_code == 303
    assert response.headers["location"] == "https://pay.test/existing"
    create_payment.assert_not_awaited()


def test_membership_tokens_expire(monkeypatch):
    import utils.tokens as tokens

    monkeypatch.setattr(tokens.time, "time", lambda: 1_000)
    token = make_subscription_token(42)
    monkeypatch.setattr(tokens.time, "time", lambda: 5_000)

    assert web._verified_user_id(token) is None


def test_question_api_is_not_publicly_mounted():
    paths = {route.path for route in web.app.routes}
    assert not any(path.startswith("/api/questions") for path in paths)
