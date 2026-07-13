"""Read-only access to the remote B2 vocabulary library.

The vocabulary lives in a separate PostgreSQL database (schema ``vocabulary``,
table ``words``) configured via ``VOCAB_DATABASE_URL``. This module owns a
dedicated async engine for that database and exposes simple read helpers; it
never writes. Per-user data (saved words) lives in the bot's own database.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from bot.config import get_settings

logger = logging.getLogger(__name__)

_settings = get_settings()

# Columns selected for every word (kept in one place for consistency).
_WORD_COLUMNS = "id, nederlands, persian, pronunciation, category"


@dataclass(frozen=True)
class VocabWord:
    """A single vocabulary entry read from the remote library."""

    id: int
    nederlands: str
    persian: str | None
    pronunciation: str | None
    category: str | None


_engine: AsyncEngine | None = None


def _get_engine() -> AsyncEngine:
    """Return the lazily-created read-only engine for the vocabulary database."""
    global _engine
    if _engine is None:
        url = _settings.database.vocab_database_url
        if not url:
            raise RuntimeError("VOCAB_DATABASE_URL is not configured.")
        # pool_pre_ping recovers transparently if the remote drops idle conns.
        _engine = create_async_engine(url, pool_pre_ping=True, pool_size=3)
    return _engine


def _to_word(row: dict) -> VocabWord:
    return VocabWord(
        id=row["id"],
        nederlands=row["nederlands"],
        persian=row["persian"],
        pronunciation=row["pronunciation"],
        category=row["category"],
    )


async def get_random_words(*, limit: int = 10) -> list[VocabWord]:
    """Return ``limit`` random words from the whole library (992 entries)."""
    engine = _get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                f"SELECT {_WORD_COLUMNS} FROM vocabulary.words "
                "ORDER BY random() LIMIT :limit"
            ),
            {"limit": limit},
        )
        return [_to_word(dict(r)) for r in result.mappings()]


async def get_words_by_ids(ids: list[int]) -> list[VocabWord]:
    """Return the words with the given ``vocabulary.words.id`` values."""
    if not ids:
        return []
    engine = _get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                f"SELECT {_WORD_COLUMNS} FROM vocabulary.words "
                "WHERE id = ANY(:ids)"
            ),
            {"ids": ids},
        )
        return [_to_word(dict(r)) for r in result.mappings()]


async def count_words() -> int:
    """Return the total number of words in the library."""
    engine = _get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT count(*) FROM vocabulary.words"))
        return int(result.scalar_one())


async def dispose() -> None:
    """Dispose of the vocabulary engine (call on shutdown)."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
