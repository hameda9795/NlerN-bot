"""Tests for broadcast segment targeting."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import pytest

from database.models import Subscription, User
from services import subscription_service as subs


@pytest.fixture
def patched_broadcast_db(monkeypatch, session_factory):
    """Point broadcast_service.get_db_session at the in-memory database."""

    @asynccontextmanager
    async def _fake_session():
        session = session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    import services.broadcast_service as bc

    monkeypatch.setattr(bc, "get_db_session", _fake_session)
    return session_factory


async def _make_user(session_factory, telegram_id: int) -> int:
    async with session_factory() as session:
        user = User(telegram_id=telegram_id)
        session.add(user)
        await session.flush()
        uid = user.id
        await session.commit()
    return uid


async def _add_subscription(session_factory, user_id: int, *, status: str, period_end) -> None:
    async with session_factory() as session:
        session.add(
            Subscription(user_id=user_id, status=status, current_period_end=period_end)
        )
        await session.commit()


@pytest.mark.asyncio
async def test_resolve_segment_all_returns_every_user(patched_broadcast_db):
    import services.broadcast_service as bc

    u1 = await _make_user(patched_broadcast_db, 1001)
    u2 = await _make_user(patched_broadcast_db, 1002)

    result = await bc.resolve_segment_user_ids("all")
    assert set(result) == {u1, u2}


@pytest.mark.asyncio
async def test_resolve_segment_never_subscribed(patched_broadcast_db):
    import services.broadcast_service as bc

    never = await _make_user(patched_broadcast_db, 2001)
    has_sub = await _make_user(patched_broadcast_db, 2002)
    await _add_subscription(
        patched_broadcast_db,
        has_sub,
        status=subs.STATUS_ACTIVE,
        period_end=datetime.now(timezone.utc) + timedelta(days=1),
    )

    result = await bc.resolve_segment_user_ids("never_subscribed")
    assert result == [never]


@pytest.mark.asyncio
async def test_resolve_segment_active_vs_lapsed(patched_broadcast_db):
    """Mirrors real production data: a subscription row with status='active'
    but an expired current_period_end is 'lapsed', not 'active' — the same
    stale-status pattern found in the live DB (100 of 102 'active' rows were
    actually expired trials)."""
    import services.broadcast_service as bc

    active_user = await _make_user(patched_broadcast_db, 3001)
    lapsed_user = await _make_user(patched_broadcast_db, 3002)
    await _add_subscription(
        patched_broadcast_db,
        active_user,
        status=subs.STATUS_ACTIVE,
        period_end=datetime.now(timezone.utc) + timedelta(days=1),
    )
    await _add_subscription(
        patched_broadcast_db,
        lapsed_user,
        status=subs.STATUS_ACTIVE,  # stale status; period already ended
        period_end=datetime.now(timezone.utc) - timedelta(days=1),
    )

    assert await bc.resolve_segment_user_ids("active") == [active_user]
    assert await bc.resolve_segment_user_ids("lapsed") == [lapsed_user]


@pytest.mark.asyncio
async def test_resolve_segment_unknown_raises(patched_broadcast_db):
    import services.broadcast_service as bc

    with pytest.raises(ValueError):
        await bc.resolve_segment_user_ids("bogus")


from sqlalchemy import select as sa_select

from database.models import Broadcast


class FakeBot:
    """Minimal stand-in for aiogram.Bot's send_message/edit_message_text."""

    def __init__(self, behaviors: dict[int, list[Exception | None]] | None = None):
        self.behaviors = behaviors or {}
        self.sent_to: list[int] = []
        self.edits: list[str] = []

    async def send_message(self, chat_id, text, parse_mode=None):
        queue = self.behaviors.get(chat_id)
        self.sent_to.append(chat_id)
        if queue:
            outcome = queue.pop(0)
            if outcome is not None:
                raise outcome
        return None

    async def edit_message_text(self, text, chat_id=None, message_id=None):
        self.edits.append(text)


@pytest.mark.asyncio
async def test_run_broadcast_counts_success_blocked_and_failed(patched_broadcast_db, monkeypatch):
    import services.broadcast_service as bc
    from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter

    monkeypatch.setattr(bc, "BROADCAST_DELAY_SECONDS", 0)

    ok_user = await _make_user(patched_broadcast_db, 4001)
    blocked_user = await _make_user(patched_broadcast_db, 4002)
    retry_then_ok_user = await _make_user(patched_broadcast_db, 4003)
    failing_user = await _make_user(patched_broadcast_db, 4004)

    bot = FakeBot({
        4002: [TelegramForbiddenError(method=None, message="blocked")],
        4003: [TelegramRetryAfter(method=None, message="flood", retry_after=0), None],
        4004: [RuntimeError("boom")],
    })

    await bc.run_broadcast(
        bot,
        admin_user_id=ok_user,
        segment="all",
        message_html="<b>hi</b>",
        status_chat_id=555,
        status_message_id=1,
    )

    async with patched_broadcast_db() as session:
        row = (await session.scalars(sa_select(Broadcast))).one()

    assert row.target_count == 4
    assert row.sent_count == 2  # ok_user + retry_then_ok_user (succeeds on retry)
    assert row.blocked_count == 1
    assert row.failed_count == 1
    assert row.finished_at is not None
    assert "✅" in bot.edits[-1]
    assert "موفق: 2" in bot.edits[-1]
    assert not bc.is_broadcast_running()


@pytest.mark.asyncio
async def test_run_broadcast_sets_running_flag_during_send(patched_broadcast_db, monkeypatch):
    import services.broadcast_service as bc

    monkeypatch.setattr(bc, "BROADCAST_DELAY_SECONDS", 0)
    user_id = await _make_user(patched_broadcast_db, 5001)
    seen_running = []

    class ObservingBot(FakeBot):
        async def send_message(self, chat_id, text, parse_mode=None):
            seen_running.append(bc.is_broadcast_running())
            return await super().send_message(chat_id, text, parse_mode=parse_mode)

    bot = ObservingBot()
    assert not bc.is_broadcast_running()

    await bc.run_broadcast(
        bot, admin_user_id=user_id, segment="all", message_html="hi",
        status_chat_id=1, status_message_id=1,
    )

    assert seen_running == [True]
    assert not bc.is_broadcast_running()


@pytest.mark.asyncio
async def test_run_broadcast_reports_progress_before_final_summary(patched_broadcast_db, monkeypatch):
    import services.broadcast_service as bc

    monkeypatch.setattr(bc, "BROADCAST_DELAY_SECONDS", 0)
    monkeypatch.setattr(bc, "STATUS_UPDATE_INTERVAL_SECONDS", 0)

    u1 = await _make_user(patched_broadcast_db, 6001)
    await _make_user(patched_broadcast_db, 6002)

    bot = FakeBot()
    await bc.run_broadcast(
        bot, admin_user_id=u1, segment="all", message_html="hi",
        status_chat_id=1, status_message_id=1,
    )

    assert any("ارسال‌شده" in e for e in bot.edits[:-1])
    assert "✅" in bot.edits[-1]
    assert "موفق: 2" in bot.edits[-1]
