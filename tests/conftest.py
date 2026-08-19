"""Shared pytest fixtures using an in-memory SQLite database."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
import pytest_asyncio

# Provide env vars before bot.config is imported anywhere.
os.environ.setdefault("BOT_TOKEN", "123456789:AAEEdummytokenForTestsOnly0000000000")
os.environ.setdefault("ADMIN_USER_ID", "111,222")
os.environ.setdefault("OPENAI_API_KEY", "")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SUBSCRIPTION_TOKEN_SECRET", "test-token-secret-at-least-32-bytes")
os.environ.setdefault("SUBSCRIPTION_TOKEN_MAX_AGE_SECONDS", "3600")

from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from database.models import Base  # noqa: E402


@pytest_asyncio.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """A session factory bound to a fresh in-memory database with tables created."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


@pytest.fixture
def patched_db_session(monkeypatch, session_factory):
    """Patch get_db_session in user_middleware to use the in-memory DB."""

    @asynccontextmanager
    async def _fake_session() -> AsyncIterator[AsyncSession]:
        session = session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    import middlewares.user_middleware as mw

    monkeypatch.setattr(mw, "get_db_session", _fake_session)
    return _fake_session
