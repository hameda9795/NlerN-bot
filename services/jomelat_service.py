"""Read-only access to the aggregated sentence library (``public.jomelat``).

The table is built by :mod:`scripts.build_jomelat` and holds every Dutch
example sentence from the vocabulary library (verbs + chapter words). This
module pulls a random sentence for the /zin pronunciation drill.

Like the other vocabulary services, it owns a dedicated read-only async engine
on ``VOCAB_DATABASE_URL`` and never writes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from bot.config import get_settings

logger = logging.getLogger(__name__)

_settings = get_settings()

_TABLE = "public.jomelat"

_engine: AsyncEngine | None = None


@dataclass(frozen=True)
class Sentence:
    """One Dutch example sentence with its Persian translation and origin."""

    id: int
    dutch: str
    persian: str | None
    source: str


def _get_engine() -> AsyncEngine:
    """Return the lazily-created read-only engine for the sentence library."""
    global _engine
    if _engine is None:
        url = _settings.database.vocab_database_url
        if not url:
            raise RuntimeError("VOCAB_DATABASE_URL is not configured.")
        _engine = create_async_engine(url, pool_pre_ping=True, pool_size=3)
    return _engine


def is_enabled() -> bool:
    """True when the vocabulary database is configured."""
    return bool(_settings.database.vocab_database_url)


async def get_random_sentence() -> Sentence | None:
    """Return one random sentence from the library, or None if unavailable."""
    engine = _get_engine()
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    f"SELECT id, dutch, persian, source FROM {_TABLE} "
                    "ORDER BY random() LIMIT 1"
                )
            )
        ).first()
    if not row:
        return None
    return Sentence(id=row[0], dutch=row[1], persian=row[2], source=row[3])


async def dispose() -> None:
    """Dispose of the engine (call on shutdown)."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
