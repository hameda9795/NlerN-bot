"""Explicit, duplicate-aware database migrations for production deploys."""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine

from bot.config import get_settings
from database.connection import engine
from database.models import Base

logger = logging.getLogger(__name__)

_MOLLIE_INDEX = "ux_subscription_mollie_subscription_id"
_KNM_POSITION_INDEX = "ix_knm_position"


def _has_knm_position(sync_conn) -> bool:
    """True when the knm table already carries the ``position`` column.

    Also true when the table is absent, since ``create_all`` will have just
    built it with the column in place.
    """
    inspector = inspect(sync_conn)
    if "knm" not in inspector.get_table_names():
        return True
    return any(column["name"] == "position" for column in inspector.get_columns("knm"))


class MigrationConflictError(RuntimeError):
    """Raised when existing production data makes a migration unsafe."""


async def apply_migrations(*, db_engine: AsyncEngine = engine) -> None:
    """Create missing tables and apply validated payment-safety indexes.

    Run this command as a dedicated deployment step before starting either
    the bot or web container: ``python -m database.migrations``.
    """
    settings = get_settings()
    async with db_engine.begin() as conn:
        if db_engine.dialect.name != "sqlite":
            await conn.execute(
                text(
                    f'CREATE SCHEMA IF NOT EXISTS "{settings.database.db_schema}"'
                )
            )
        await conn.run_sync(Base.metadata.create_all)

        duplicates = list(
            (
                await conn.execute(
                    text(
                        "SELECT mollie_subscription_id, COUNT(*) AS row_count "
                        "FROM subscriptions "
                        "WHERE mollie_subscription_id IS NOT NULL "
                        "GROUP BY mollie_subscription_id "
                        "HAVING COUNT(*) > 1"
                    )
                )
            ).all()
        )
        if duplicates:
            summary = ", ".join(
                f"{subscription_id} ({count} rows)"
                for subscription_id, count in duplicates
            )
            raise MigrationConflictError(
                "Cannot create the unique Mollie subscription index; resolve "
                f"duplicate local ids first: {summary}"
            )

        await conn.execute(
            text(
                f"CREATE UNIQUE INDEX IF NOT EXISTS {_MOLLIE_INDEX} "
                "ON subscriptions (mollie_subscription_id)"
            )
        )

        # ``create_all`` creates missing *tables* but never adds a column to a
        # table that already exists, so ``knm.position`` needs saying out loud.
        # Existing rows land on 0; re-running the importer fills in real values.
        # Checked via the inspector rather than ``ADD COLUMN IF NOT EXISTS``,
        # which SQLite does not support.
        if not await conn.run_sync(_has_knm_position):
            await conn.execute(
                text("ALTER TABLE knm ADD COLUMN position INTEGER NOT NULL DEFAULT 0")
            )
        await conn.execute(
            text(f"CREATE INDEX IF NOT EXISTS {_KNM_POSITION_INDEX} ON knm (position)")
        )

    logger.info("Database migrations applied successfully.")


def main() -> None:
    """Run all database migrations from the command line."""
    asyncio.run(apply_migrations())


if __name__ == "__main__":
    main()
