"""Safety guarantees for the KNM dataset importer."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models import Question, QuestionOption
from scripts import import_knm_questions as knm
from services.question_service import STATUS_APPROVED, STATUS_DRAFT


def _item(item_id: str, *, correct: str = "o1", theme: str = "1") -> dict:
    return {
        "item_id": item_id,
        "revision": 4,
        "status": "draft",
        "alignment": {
            "theme_id": theme,
            "section_id": f"{theme}.1",
            "eindterm_id": f"{theme}.1.1",
            "indicator_id": "ind-1",
            "fact_id": "fact-1",
        },
        "difficulty": {"intended_level": "medium"},
        "content": {
            "item_type": "single_choice_3",
            "stem": {"nl-NL": f"Vraag {item_id}?"},
            "options": [
                {"id": "o1", "text": {"nl-NL": "Eerste"}},
                {"id": "o2", "text": {"nl-NL": "Tweede"}},
                {"id": "o3", "text": {"nl-NL": "Derde"}},
            ],
            "correct_option_id": correct,
            "shuffle_options": True,
        },
        "explanations": {
            "fa": {
                "why_correct": "توضیح فارسی",
                "option_feedback": {"o1": "یک", "o2": "دو", "o3": "سه"},
                "key_terms": [{"term_nl": "MAP", "meaning": "ماژول"}],
            }
        },
    }


def _dataset(items: list[dict]) -> dict:
    return {
        "schema_version": "1.0.0",
        "dataset_id": "knm-test",
        "metadata": {"item_count": len(items)},
        "items": items,
    }


def _write(tmp_path, items: list[dict]):
    path = tmp_path / "knm.json"
    path.write_text(json.dumps(_dataset(items), ensure_ascii=False), encoding="utf-8")
    return path


@pytest.fixture
def knm_db(monkeypatch, session_factory):
    """Point the importer at the in-memory test database."""

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

    async def noop_init_db() -> None:
        return None

    monkeypatch.setattr(knm, "get_db_session", fake_session)
    monkeypatch.setattr(knm, "init_db", noop_init_db)
    return fake_session


@pytest.mark.asyncio
async def test_import_writes_draft_rows_with_shuffled_options(knm_db, session_factory, tmp_path):
    path = _write(tmp_path, [_item("knm-1"), _item("knm-2", theme="2")])

    inserted = await knm.import_knm(path=path)

    assert inserted == 2
    async with session_factory() as session:
        questions = list(
            await session.scalars(
                select(Question)
                .options(selectinload(Question.options))
                .order_by(Question.question_text_nl)
            )
        )
        options = list(await session.scalars(select(QuestionOption)))
    assert {q.status for q in questions} == {STATUS_DRAFT}
    assert {q.section for q in questions} == {"knm"}
    assert {q.topic for q in questions} == {"thema_1", "thema_2"}
    assert len(options) == 6
    # Exactly one correct option per question, whatever position it landed in.
    for question in questions:
        keys = sorted(o.option_key for o in question.options)
        assert keys == ["A", "B", "C"]
        assert sum(1 for o in question.options if o.is_correct) == 1
        provenance = json.loads(question.review_issues_json)
        assert provenance["knm_item_id"] == question.question_text_nl[6:-1]


@pytest.mark.asyncio
async def test_shuffle_is_deterministic_across_runs(knm_db, session_factory, tmp_path):
    """A re-import must not reshuffle answers under users who already saw them."""
    path = _write(tmp_path, [_item(f"knm-{n}") for n in range(12)])

    await knm.import_knm(path=path)
    async with session_factory() as session:
        first = {
            q.question_text_nl: next(o.option_key for o in q.options if o.is_correct)
            for q in await session.scalars(
                select(Question).options(selectinload(Question.options))
            )
        }

    await knm.import_knm(path=path)
    async with session_factory() as session:
        second = {
            q.question_text_nl: next(o.option_key for o in q.options if o.is_correct)
            for q in await session.scalars(
                select(Question).options(selectinload(Question.options))
            )
        }

    assert first == second
    # And the shuffle actually spreads a dataset whose answer is always o1.
    assert len(set(first.values())) > 1


@pytest.mark.asyncio
async def test_reimport_replaces_only_the_knm_bucket(knm_db, session_factory, tmp_path):
    """Curated and AI rows must survive a re-import untouched."""
    async with session_factory() as session:
        session.add_all([
            Question(
                level="A2",
                section="grammar",
                topic="zijn_hebben",
                question_text_nl="Curated blijft.",
                status=STATUS_APPROVED,
                created_by="curated_import",
            ),
            Question(
                level="B1",
                section="knm",
                topic="thema_9",
                question_text_nl="Andere knm-bron blijft.",
                status=STATUS_APPROVED,
                created_by="someone_else",
            ),
        ])
        await session.commit()

    path = _write(tmp_path, [_item("knm-1")])
    await knm.import_knm(path=path)
    await knm.import_knm(path=path)

    async with session_factory() as session:
        total = await session.scalar(select(func.count()).select_from(Question))
        mine = await session.scalar(
            select(func.count())
            .select_from(Question)
            .where(Question.created_by == knm.CREATED_BY)
        )
    assert mine == 1
    assert total == 3  # the two foreign rows are still there


@pytest.mark.asyncio
async def test_invalid_dataset_writes_nothing(knm_db, session_factory, tmp_path):
    broken = _item("knm-bad")
    broken["content"]["correct_option_id"] = "o9"
    path = _write(tmp_path, [_item("knm-ok"), broken])

    with pytest.raises(knm.KnmImportError, match="correct_option_id"):
        await knm.import_knm(path=path)

    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(Question)) == 0


@pytest.mark.asyncio
async def test_dry_run_writes_nothing(knm_db, session_factory, tmp_path):
    path = _write(tmp_path, [_item("knm-1")])

    assert await knm.import_knm(path=path, dry_run=True) == 0

    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(Question)) == 0


@pytest.mark.asyncio
async def test_item_count_mismatch_is_rejected(tmp_path):
    payload = _dataset([_item("knm-1")])
    payload["metadata"]["item_count"] = 5
    path = tmp_path / "knm.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(knm.KnmImportError, match="item_count"):
        knm.load_items(path)
