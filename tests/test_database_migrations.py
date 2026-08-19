"""Tests for explicit, duplicate-aware production migrations."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from database import migrations
from database.migrations import MigrationConflictError, apply_migrations


async def _legacy_subscriptions_table(*, duplicate: bool) -> AsyncEngine:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "CREATE TABLE subscriptions ("
                "id INTEGER PRIMARY KEY, "
                "user_id INTEGER NOT NULL, "
                "mollie_subscription_id VARCHAR(64))"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO subscriptions "
                "(id, user_id, mollie_subscription_id) "
                "VALUES (1, 10, 'sub_same')"
            )
        )
        if duplicate:
            await conn.execute(
                text(
                    "INSERT INTO subscriptions "
                    "(id, user_id, mollie_subscription_id) "
                    "VALUES (2, 20, 'sub_same')"
                )
            )
    return engine


@pytest.mark.asyncio
async def test_migration_reports_duplicate_mollie_ids_before_index_creation():
    engine = await _legacy_subscriptions_table(duplicate=True)
    try:
        with pytest.raises(MigrationConflictError, match="sub_same.*2 rows"):
            await apply_migrations(db_engine=engine)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_migration_creates_unique_index_for_clean_legacy_data():
    engine = await _legacy_subscriptions_table(duplicate=False)
    try:
        await apply_migrations(db_engine=engine)
        async with engine.connect() as conn:
            indexes = list(
                (await conn.execute(text("PRAGMA index_list('subscriptions')"))).all()
            )
    finally:
        await engine.dispose()

    matching = [row for row in indexes if row[1] == "ux_subscription_mollie_subscription_id"]
    assert len(matching) == 1
    assert matching[0][2] == 1


@pytest.mark.asyncio
async def test_migration_adds_position_to_a_pre_existing_knm_table(tmp_path):
    """A knm table created before the exam feature must gain ``position``."""
    from sqlalchemy import inspect, text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path/'legacy.db'}")
    async with engine.begin() as conn:
        # The shape the table had before this feature: no position column.
        await conn.execute(
            text(
                "CREATE TABLE knm (id INTEGER PRIMARY KEY, item_id VARCHAR(64) "
                "NOT NULL UNIQUE, question_text_nl TEXT NOT NULL, "
                "options_json JSON NOT NULL, correct_option_key VARCHAR(1) NOT NULL)"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO knm (item_id, question_text_nl, options_json, "
                "correct_option_key) VALUES ('knm-1', 'Vraag?', '[]', 'A')"
            )
        )

    await migrations.apply_migrations(db_engine=engine)

    async with engine.begin() as conn:
        columns = await conn.run_sync(
            lambda c: [col["name"] for col in inspect(c).get_columns("knm")]
        )
        position = await conn.scalar(text("SELECT position FROM knm WHERE item_id='knm-1'"))
    await engine.dispose()

    assert "position" in columns
    assert position == 0  # existing rows default to 0 until re-imported


@pytest.mark.asyncio
async def test_migration_is_rerunnable(tmp_path):
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path/'twice.db'}")
    await migrations.apply_migrations(db_engine=engine)
    await migrations.apply_migrations(db_engine=engine)  # must not raise
    await engine.dispose()
