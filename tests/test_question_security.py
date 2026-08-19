"""Security boundaries for the internal question bank."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Question, User, UserQuestionAttempt
from services import question_service


@pytest.mark.asyncio
async def test_draft_question_cannot_be_graded(monkeypatch, session_factory):
    """Knowing a draft id must not reveal its answer or create progress."""

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

    monkeypatch.setattr(question_service, "get_db_session", fake_session)
    async with session_factory() as session:
        user = User(telegram_id=333)
        question = Question(
            level="A2",
            section="grammar",
            topic="draft-topic",
            question_text_nl="Verborgen vraag?",
            status=question_service.STATUS_DRAFT,
        )
        session.add_all([user, question])
        await session.commit()
        user_id = user.id
        question_id = question.id

    result = await question_service.record_answer(
        user_id=user_id,
        question_id=question_id,
        selected_option_key="A",
    )

    assert result is None
    async with session_factory() as session:
        attempt_count = await session.scalar(select(func.count(UserQuestionAttempt.id)))
    assert attempt_count == 0

