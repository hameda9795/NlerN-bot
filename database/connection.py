"""Async database engine, session factory and helpers.

Usage::

    async with get_db_session() as session:
        ...

Call :func:`init_db` once on startup to create all tables.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from bot.config import get_settings
from database.models import Base

logger = logging.getLogger(__name__)

_settings = get_settings()

_IS_SQLITE = _settings.database.database_url.startswith("sqlite")

# SQLite (aiosqlite) does not use a real connection pool; pool_size is only
# passed for non-sqlite backends to keep the call portable.
_engine_kwargs: dict[str, object] = {"echo": False, "future": True}
if not _IS_SQLITE:
    _engine_kwargs["pool_size"] = _settings.database.pool_size
    # Pin every connection to the bot's own schema so unqualified table names
    # (including those created by ``create_all``) resolve there, keeping the
    # bot isolated from the other schemas in the shared database.
    _engine_kwargs["connect_args"] = {
        "server_settings": {"search_path": _settings.database.db_schema}
    }

engine = create_async_engine(_settings.database.database_url, **_engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


@asynccontextmanager
async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Yield an async session, committing on success and rolling back on error."""
    session = AsyncSessionLocal()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def init_db() -> None:
    """Create the bot's schema (Postgres) and all tables on ``Base`` metadata."""
    async with engine.begin() as conn:
        if not _IS_SQLITE:
            # Idempotent; create_all then resolves unqualified names into it.
            await conn.execute(
                text(f'CREATE SCHEMA IF NOT EXISTS "{_settings.database.db_schema}"')
            )
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialized: %s", _settings.database.database_url)


async def close_db() -> None:
    """Dispose of the engine and its connections."""
    await engine.dispose()
    logger.info("Database connection closed.")
