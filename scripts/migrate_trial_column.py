"""Add the ``trial_used_at`` column to an existing ``subscriptions`` table.

``create_all`` only creates missing tables, never alters existing ones, so this
new column needs an explicit (idempotent) ALTER.

Usage::

    uv run python -m scripts.migrate_trial_column
"""

from __future__ import annotations

import asyncio

from sqlalchemy import text

from bot.config import get_settings
from database.connection import engine


async def main() -> None:
    schema = get_settings().database.db_schema
    is_sqlite = get_settings().database.database_url.startswith("sqlite")
    table = "subscriptions" if is_sqlite else f'"{schema}".subscriptions'
    col_type = "TIMESTAMP" if is_sqlite else "TIMESTAMPTZ"
    async with engine.begin() as conn:
        await conn.execute(
            text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS trial_used_at {col_type}")
        )
        print(f"Ensured column trial_used_at on {table}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
