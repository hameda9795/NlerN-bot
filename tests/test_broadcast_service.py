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
