"""Add the AI-review columns to an existing ``questions`` table.

``create_all`` only creates missing tables, never alters existing ones, so the
two new review columns need an explicit (idempotent) ALTER. SQLite and Postgres
both support ``ADD COLUMN IF NOT EXISTS`` here.

Usage::

    uv run python -m scripts.migrate_review_columns
"""

from __future__ import annotations

import asyncio

from sqlalchemy import text

from bot.config import get_settings
from database.connection import engine

_COLUMNS = ("review_notes_fa", "review_issues_json")


async def main() -> None:
    schema = get_settings().database.db_schema
    is_sqlite = get_settings().database.database_url.startswith("sqlite")
    table = "questions" if is_sqlite else f'"{schema}".questions'
    async with engine.begin() as conn:
        for col in _COLUMNS:
            await conn.execute(
                text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} TEXT")
            )
            print(f"Ensured column {col} on {table}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
