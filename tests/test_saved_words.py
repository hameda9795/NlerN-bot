"""Tests for the saved 'hard words' service (bot's own database)."""

from __future__ import annotations

from contextlib import asynccontextmanager

import pytest

from database.models import User
from services.vocab_service import VocabWord


def _word(word_id: int) -> VocabWord:
    return VocabWord(
        id=word_id,
        nederlands=f"woord{word_id}",
        persian=f"کلمه{word_id}",
        pronunciation="پ",
        category="01. Test",
    )


@pytest.fixture
def patched_saved_db(monkeypatch, session_factory):
    """Point saved_word_service.get_db_session at the in-memory database."""

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

    import services.saved_word_service as svc

    monkeypatch.setattr(svc, "get_db_session", _fake_session)
    return session_factory


async def _make_user(session_factory, telegram_id: int = 555001) -> int:
    async with session_factory() as session:
        user = User(telegram_id=telegram_id, current_cefr_level="B2")
        session.add(user)
        await session.flush()
        uid = user.id
        await session.commit()
    return uid


@pytest.mark.asyncio
async def test_save_list_and_dedupe(patched_saved_db):
    import services.saved_word_service as svc

    user_id = await _make_user(patched_saved_db)

    assert await svc.save_word(user_id=user_id, word=_word(10)) is True
    assert await svc.save_word(user_id=user_id, word=_word(11)) is True
    # Saving the same word again is a no-op (deduped).
    assert await svc.save_word(user_id=user_id, word=_word(10)) is False

    assert await svc.count_saved_words(user_id=user_id) == 2
    saved = await svc.list_saved_words(user_id=user_id)
    assert {w.vocab_word_id for w in saved} == {10, 11}
    assert saved[0].nederlands.startswith("woord")


@pytest.mark.asyncio
async def test_delete_saved_word(patched_saved_db):
    import services.saved_word_service as svc

    user_id = await _make_user(patched_saved_db, telegram_id=555002)
    await svc.save_word(user_id=user_id, word=_word(20))
    saved = await svc.list_saved_words(user_id=user_id)
    saved_id = saved[0].id

    assert await svc.delete_saved_word(user_id=user_id, saved_word_id=saved_id) is True
    assert await svc.count_saved_words(user_id=user_id) == 0
    # Deleting again returns False (nothing removed).
    assert await svc.delete_saved_word(user_id=user_id, saved_word_id=saved_id) is False
