"""The standalone ``knm`` archive table and its importer."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import KnmQuestion
from scripts import import_knm_table as knm_table
from tests.test_knm_import import _dataset, _item


def _with_en(item: dict) -> dict:
    item["language"] = {"cefr_target": "A2"}
    item["alignment"]["knowledge_type"] = "procedure"
    item["explanations"]["en"] = {
        "why_correct": "English explanation",
        "option_feedback": {"o1": "one", "o2": "two", "o3": "three"},
        "key_terms": [{"term_nl": "MAP", "meaning": "Labour Market Module"}],
    }
    return item


def _write(tmp_path, items: list[dict]):
    path = tmp_path / "knm.json"
    path.write_text(json.dumps(_dataset(items), ensure_ascii=False), encoding="utf-8")
    return path


@pytest.fixture
def knm_table_db(monkeypatch, session_factory):
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

    monkeypatch.setattr(knm_table, "get_db_session", fake_session)
    monkeypatch.setattr(knm_table, "init_db", noop_init_db)
    return fake_session


@pytest.mark.asyncio
async def test_row_keeps_both_languages_and_source_order(
    knm_table_db, session_factory, tmp_path
):
    path = _write(tmp_path, [_with_en(_item("knm-1", correct="o2"))])

    assert await knm_table.import_knm_table(path=path) == (1, 0)

    async with session_factory() as session:
        row = await session.scalar(select(KnmQuestion))

    assert row.item_id == "knm-1"
    assert row.explanation_fa == "توضیح فارسی"
    assert row.explanation_en == "English explanation"
    assert row.cefr_target == "A2"
    assert row.knowledge_type == "procedure"
    assert row.correct_option_key == "B"
    # Options keep the file's own order, each carrying both feedback languages.
    assert [o["source_id"] for o in row.options_json] == ["o1", "o2", "o3"]
    assert [o["key"] for o in row.options_json] == ["A", "B", "C"]
    assert [o["is_correct"] for o in row.options_json] == [False, True, False]
    assert row.options_json[1]["feedback_fa"] == "دو"
    assert row.options_json[1]["feedback_en"] == "two"
    assert row.key_terms_json == [
        {"term_nl": "MAP", "meaning_fa": "ماژول", "meaning_en": "Labour Market Module"}
    ]


@pytest.mark.asyncio
async def test_reimport_updates_in_place(knm_table_db, session_factory, tmp_path):
    item = _with_en(_item("knm-1"))
    path = _write(tmp_path, [item])
    assert await knm_table.import_knm_table(path=path) == (1, 0)

    item["explanations"]["en"]["why_correct"] = "Revised English explanation"
    item["revision"] = 5
    path = _write(tmp_path, [item])
    assert await knm_table.import_knm_table(path=path) == (0, 1)

    async with session_factory() as session:
        total = await session.scalar(select(func.count()).select_from(KnmQuestion))
        row = await session.scalar(select(KnmQuestion))
    assert total == 1
    assert row.revision == 5
    assert row.explanation_en == "Revised English explanation"


@pytest.mark.asyncio
async def test_missing_english_is_stored_as_null(knm_table_db, session_factory, tmp_path):
    path = _write(tmp_path, [_item("knm-1")])  # Persian only, no "en" block

    await knm_table.import_knm_table(path=path)

    async with session_factory() as session:
        row = await session.scalar(select(KnmQuestion))
    assert row.explanation_fa == "توضیح فارسی"
    assert row.explanation_en is None
    assert all(o["feedback_en"] is None for o in row.options_json)
    assert row.options_json[0]["feedback_fa"] == "یک"


@pytest.mark.asyncio
async def test_invalid_dataset_writes_nothing(knm_table_db, session_factory, tmp_path):
    broken = _with_en(_item("knm-bad"))
    broken["content"]["stem"]["nl-NL"] = "  "
    path = _write(tmp_path, [broken])

    with pytest.raises(knm_table.KnmImportError, match="empty nl-NL stem"):
        await knm_table.import_knm_table(path=path)

    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(KnmQuestion)) == 0


@pytest.mark.asyncio
async def test_dry_run_writes_nothing(knm_table_db, session_factory, tmp_path):
    path = _write(tmp_path, [_with_en(_item("knm-1"))])

    assert await knm_table.import_knm_table(path=path, dry_run=True) == (0, 0)

    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(KnmQuestion)) == 0
