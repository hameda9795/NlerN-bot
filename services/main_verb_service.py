"""Read-only access to the Dutch main-verbs library (افعال اصلی / Hoofdwerkwoord).

The data lives in the same remote PostgreSQL database as the B2 vocabulary
(``VOCAB_DATABASE_URL``), in schema ``vajegan-nl``, table ``Hoofdwerkwoord``.
Each row is one main verb (e.g. ``zijn``) grouped by a thematic *category*
(``basis_hulp_modal_en_bindwoord``, ``beweging_en_reizen`` …).

NOTE: both the schema and table identifiers contain a hyphen / capital letters,
so they must stay double-quoted in every statement.

This module owns a dedicated read-only async engine and never writes. Browsing
is stateless: handlers pass the category plus an offset and we fetch exactly the
one verb at that position, so navigation survives a bot restart and needs no
large FSM payload.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from bot.config import get_settings

logger = logging.getLogger(__name__)

_settings = get_settings()

_TABLE = '"vajegan-nl"."Hoofdwerkwoord"'
# Stable ordering so a given offset always maps to the same verb.
_ORDER = "ORDER BY rang, id"
_VERB_COLUMNS = (
    "id, rang, verb, meaning_en, translation_fa, pronunciation_fa, "
    "example_1_nl, example_1_fa, example_2_nl, example_2_fa, category"
)


@dataclass(frozen=True)
class MainVerb:
    """A single main verb read from the remote library."""

    id: int
    rang: int | None
    verb: str
    meaning_en: str | None
    translation_fa: str | None
    pronunciation_fa: str | None
    example_1_nl: str | None
    example_1_fa: str | None
    example_2_nl: str | None
    example_2_fa: str | None
    category: str | None


@dataclass(frozen=True)
class Category:
    """A thematic category and how many main verbs belong to it."""

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


def _to_verb(row: dict) -> MainVerb:
    return MainVerb(
        id=row["id"],
        rang=row["rang"],
        verb=row["verb"],
        meaning_en=row["meaning_en"],
        translation_fa=row["translation_fa"],
        pronunciation_fa=row["pronunciation_fa"],
        example_1_nl=row["example_1_nl"],
        example_1_fa=row["example_1_fa"],
        example_2_nl=row["example_2_nl"],
        example_2_fa=row["example_2_fa"],
        category=row["category"],
    )


async def list_categories() -> list[Category]:
    """Return every category with its verb count, most-populated first."""
    engine = _get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                f"SELECT category, count(*) AS n FROM {_TABLE} "
                "GROUP BY category ORDER BY n DESC, category"
            )
        )
        return [
            Category(name=r["category"], count=int(r["n"])) for r in result.mappings()
        ]


async def count_by_category(category: str) -> int:
    """Return how many verbs belong to the given ``category``."""
    engine = _get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            text(f"SELECT count(*) FROM {_TABLE} WHERE category = :c"),
            {"c": category},
        )
        return int(result.scalar_one())


async def get_verb_by_offset(category: str, offset: int) -> MainVerb | None:
    """Return the verb at ``offset`` within ``category`` (0-based), or None."""
    if offset < 0:
        return None
    engine = _get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                f"SELECT {_VERB_COLUMNS} FROM {_TABLE} "
                f"WHERE category = :c {_ORDER} OFFSET :off LIMIT 1"
            ),
            {"c": category, "off": offset},
        )
        row = result.mappings().first()
        return _to_verb(dict(row)) if row else None


async def dispose() -> None:
    """Dispose of the engine (call on shutdown)."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
