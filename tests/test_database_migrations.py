"""Tests for explicit, duplicate-aware production migrations."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

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
