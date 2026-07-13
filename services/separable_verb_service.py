"""Read-only access to the Dutch separable-verbs library (افعال جداشدنی).

The data lives in the same remote PostgreSQL database as the B2 vocabulary
(``VOCAB_DATABASE_URL``), in schema ``vajegan_nl``, table
``scheidbarwerkworden``. Each row is one separable verb (e.g. ``aankomen``)
grouped by its *particle* (``aan``, ``af``, ``op`` …).

This module owns a dedicated read-only async engine and never writes. Browsing
is stateless: handlers pass the particle plus an offset and we fetch exactly
the one verb at that position, so navigation survives a bot restart and needs
no large FSM payload.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from bot.config import get_settings

logger = logging.getLogger(__name__)

_settings = get_settings()

_TABLE = "vajegan_nl.scheidbarwerkworden"
# Stable ordering so a given offset always maps to the same verb.
_ORDER = "ORDER BY separable_verb, id"
_VERB_COLUMNS = (
    "id, particle, base_verb, separable_verb, meaning_en, meaning_fa, "
    "usage_context, usage_notes, pronunciation_fa, "
    "example_1_nl, example_1_fa, example_2_nl, example_2_fa"
)


@dataclass(frozen=True)
class SeparableVerb:
    """A single separable verb read from the remote library."""

    id: int
    particle: str
    base_verb: str | None
    separable_verb: str
    meaning_en: str | None
    meaning_fa: str | None
    usage_context: str | None
    usage_notes: str | None
    pronunciation_fa: str | None
    example_1_nl: str | None
    example_1_fa: str | None
    example_2_nl: str | None
    example_2_fa: str | None


@dataclass(frozen=True)
class Particle:
    """A particle (prefix) and how many verbs use it."""

    name: str
    count: int


_engine: AsyncEngine | None = None


def _get_engine() -> AsyncEngine:
    """Return the lazily-created read-only engine for the verbs database."""
    global _engine
    if _engine is None:
        url = _settings.database.vocab_database_url
        if not url:
            raise RuntimeError("VOCAB_DATABASE_URL is not configured.")
        _engine = create_async_engine(url, pool_pre_ping=True, pool_size=3)
    return _engine


def _to_verb(row: dict) -> SeparableVerb:
    return SeparableVerb(
        id=row["id"],
        particle=row["particle"],
        base_verb=row["base_verb"],
        separable_verb=row["separable_verb"],
        meaning_en=row["meaning_en"],
        meaning_fa=row["meaning_fa"],
        usage_context=row["usage_context"],
        usage_notes=row["usage_notes"],
        pronunciation_fa=row["pronunciation_fa"],
        example_1_nl=row["example_1_nl"],
        example_1_fa=row["example_1_fa"],
        example_2_nl=row["example_2_nl"],
        example_2_fa=row["example_2_fa"],
    )


async def list_particles() -> list[Particle]:
    """Return every particle with its verb count, most-populated first."""
    engine = _get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                f"SELECT particle, count(*) AS n FROM {_TABLE} "
                "GROUP BY particle ORDER BY n DESC, particle"
            )
        )
        return [Particle(name=r["particle"], count=int(r["n"])) for r in result.mappings()]


async def count_by_particle(particle: str) -> int:
    """Return how many verbs share the given ``particle``."""
    engine = _get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            text(f"SELECT count(*) FROM {_TABLE} WHERE particle = :p"),
            {"p": particle},
        )
        return int(result.scalar_one())


async def get_verb_by_offset(particle: str, offset: int) -> SeparableVerb | None:
    """Return the verb at ``offset`` within ``particle`` (0-based), or None."""
    if offset < 0:
        return None
    engine = _get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                f"SELECT {_VERB_COLUMNS} FROM {_TABLE} "
                f"WHERE particle = :p {_ORDER} OFFSET :off LIMIT 1"
            ),
            {"p": particle, "off": offset},
        )
        row = result.mappings().first()
        return _to_verb(dict(row)) if row else None


async def dispose() -> None:
    """Dispose of the engine (call on shutdown)."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
