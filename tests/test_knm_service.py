"""Grouping, resume, and progress rules for the KNM exam."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import KnmAttempt, KnmQuestion, User
from services import knm_service as knm


@pytest.fixture
def knm_db(monkeypatch, session_factory):
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

    monkeypatch.setattr(knm, "get_db_session", fake_session)
    return fake_session


def _question(position: int) -> KnmQuestion:
    """One item whose correct answer is B, so a wrong answer is easy to send."""
    return KnmQuestion(
        item_id=f"knm-{position}",
        position=position,
        question_text_nl=f"Vraag {position}?",
        correct_option_key="B",
        options_json=[
            {"key": "A", "source_id": "o1", "text_nl": "Eerste",
             "is_correct": False, "feedback_fa": "یک", "feedback_en": "one"},
            {"key": "B", "source_id": "o2", "text_nl": "Tweede",
             "is_correct": True, "feedback_fa": "دو", "feedback_en": "two"},
            {"key": "C", "source_id": "o3", "text_nl": "Derde",
             "is_correct": False, "feedback_fa": "سه", "feedback_en": "three"},
        ],
        explanation_fa="توضیح فارسی",
        key_terms_json=[{"term_nl": "MAP", "meaning_fa": "ماژول", "meaning_en": "Module"}],
    )


async def _seed(session_factory, count: int = 234) -> int:
    """Create a user plus ``count`` questions; returns the user's id."""
    async with session_factory() as session:
        user = User(telegram_id=4242, first_name="Test")
        session.add(user)
        session.add_all([_question(position) for position in range(count)])
        await session.flush()
        user_id = user.id
        await session.commit()
    return user_id


@pytest.mark.asyncio
async def test_full_dataset_splits_into_five_forties_and_one_thirtyfour(
    knm_db, session_factory
):
    user_id = await _seed(session_factory)

    groups = await knm.list_groups(user_id=user_id)

    assert [g.total for g in groups] == [40, 40, 40, 40, 40, 34]
    assert sum(g.total for g in groups) == 234
    assert [(g.first_number, g.last_number) for g in groups] == [
        (1, 40), (41, 80), (81, 120), (121, 160), (161, 200), (201, 234)
    ]
    assert all(g.is_untouched for g in groups)


@pytest.mark.asyncio
async def test_answering_advances_and_progress_is_reported(knm_db, session_factory):
    user_id = await _seed(session_factory)

    first = await knm.next_question(user_id=user_id, group=1)
    assert first.index_in_group == 1
    assert first.group_total == 40
    assert first.question_text_nl == "Vraag 40?"  # group 1 starts at position 40

    result = await knm.record_answer(
        user_id=user_id, knm_id=first.id, selected_option_key="B"
    )
    assert result.is_correct is True
    assert result.correct_option_key == "B"
    assert result.feedback_fa == "دو"
    assert result.explanation_fa == "توضیح فارسی"
    assert result.key_terms_fa == "MAP: ماژول"

    second = await knm.next_question(user_id=user_id, group=1)
    assert second.id != first.id
    assert second.index_in_group == 2

    group = await knm.get_group(user_id=user_id, group=1)
    assert (group.answered, group.correct) == (1, 1)
    # Other groups are unaffected.
    assert (await knm.get_group(user_id=user_id, group=0)).answered == 0


@pytest.mark.asyncio
async def test_wrong_answer_reports_the_correct_option(knm_db, session_factory):
    user_id = await _seed(session_factory, count=3)
    question = await knm.next_question(user_id=user_id, group=0)

    result = await knm.record_answer(
        user_id=user_id, knm_id=question.id, selected_option_key="A"
    )

    assert result.is_correct is False
    assert (result.correct_option_key, result.correct_option_text) == ("B", "Tweede")
    assert result.feedback_fa == "یک"  # feedback for what they actually picked
    group = await knm.get_group(user_id=user_id, group=0)
    assert (group.answered, group.correct) == (1, 0)


@pytest.mark.asyncio
async def test_finished_group_serves_nothing_more(knm_db, session_factory):
    user_id = await _seed(session_factory, count=42)  # group 1 holds 2 questions

    for _ in range(2):
        question = await knm.next_question(user_id=user_id, group=1)
        await knm.record_answer(
            user_id=user_id, knm_id=question.id, selected_option_key="B"
        )

    assert await knm.next_question(user_id=user_id, group=1) is None
    group = await knm.get_group(user_id=user_id, group=1)
    assert group.is_finished is True
    assert (group.answered, group.total) == (2, 2)


@pytest.mark.asyncio
async def test_reanswering_the_same_question_overwrites_one_row(
    knm_db, session_factory
):
    user_id = await _seed(session_factory, count=3)
    question = await knm.next_question(user_id=user_id, group=0)

    await knm.record_answer(user_id=user_id, knm_id=question.id, selected_option_key="A")
    await knm.record_answer(user_id=user_id, knm_id=question.id, selected_option_key="B")

    async with session_factory() as session:
        rows = await session.scalar(select(func.count()).select_from(KnmAttempt))
    assert rows == 1
    group = await knm.get_group(user_id=user_id, group=0)
    assert (group.answered, group.correct) == (1, 1)


@pytest.mark.asyncio
async def test_reset_clears_one_group_only(knm_db, session_factory):
    user_id = await _seed(session_factory, count=50)
    for group in (0, 1):
        question = await knm.next_question(user_id=user_id, group=group)
        await knm.record_answer(
            user_id=user_id, knm_id=question.id, selected_option_key="B"
        )

    assert await knm.reset_group(user_id=user_id, group=1) == 1

    assert (await knm.get_group(user_id=user_id, group=0)).answered == 1
    assert (await knm.get_group(user_id=user_id, group=1)).answered == 0
    resumed = await knm.next_question(user_id=user_id, group=1)
    assert resumed.index_in_group == 1


@pytest.mark.asyncio
async def test_one_users_progress_does_not_leak_into_another(knm_db, session_factory):
    user_id = await _seed(session_factory, count=5)
    async with session_factory() as session:
        other = User(telegram_id=99, first_name="Other")
        session.add(other)
        await session.flush()
        other_id = other.id
        await session.commit()

    question = await knm.next_question(user_id=user_id, group=0)
    await knm.record_answer(user_id=user_id, knm_id=question.id, selected_option_key="B")

    assert (await knm.get_group(user_id=other_id, group=0)).answered == 0
    assert (await knm.next_question(user_id=other_id, group=0)).id == question.id


@pytest.mark.asyncio
async def test_unknown_group_and_missing_question_are_handled(knm_db, session_factory):
    user_id = await _seed(session_factory, count=5)

    assert await knm.next_question(user_id=user_id, group=9) is None
    assert await knm.get_group(user_id=user_id, group=9) is None
    assert await knm.record_answer(
        user_id=user_id, knm_id=99999, selected_option_key="A"
    ) is None
