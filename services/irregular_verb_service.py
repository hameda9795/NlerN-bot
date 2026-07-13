"""Read-only access to the Dutch irregular-verbs library (افعال نامنظم / Onregelmatige Werkwoorden).

The data lives in the same remote PostgreSQL database as the B2 vocabulary
(``VOCAB_DATABASE_URL``), in schema ``vajegan-nl``, table
``Onregelmatige_Werkwoorden``. Each row is one irregular verb (e.g. ``bakken``)
with its three principal parts (infinitive / simple past / past participle).

NOTE: both the schema and table identifiers contain a hyphen / capital letters,
so they must stay double-quoted in every statement.

Like the regular-verbs table, there is no natural browse grouping, so for
browsing we group verbs by the first letter of the infinitive (A, B, C …). This
mirrors the letter grid of the regular-verbs flow.

This module owns a dedicated read-only async engine and never writes. Browsing
is stateless: handlers pass the letter plus an offset and we fetch exactly the
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

_TABLE = '"vajegan-nl"."Onregelmatige_Werkwoorden"'
# Group key: the uppercased first letter of the infinitive.
_LETTER = "upper(left(infinitive, 1))"
# Stable ordering so a given offset always maps to the same verb.
_ORDER = "ORDER BY infinitive, id"
_VERB_COLUMNS = (
    "id, rang, infinitive, simple_past, past_participle, translation_fa, "
    "example_present_nl, example_present_fa, example_past_nl, example_past_fa, "
    "example_perfect_nl, example_perfect_fa, category"
)


@dataclass(frozen=True)
class IrregularVerb:
    """A single irregular verb read from the remote library."""

    id: int
    rang: int | None
    infinitive: str
    simple_past: str | None
    past_participle: str | None
    translation_fa: str | None
    example_present_nl: str | None
    example_present_fa: str | None
    example_past_nl: str | None
    example_past_fa: str | None
    example_perfect_nl: str | None
    example_perfect_fa: str | None
    category: str | None


@dataclass(frozen=True)
class Letter:
    """A first-letter group and how many irregular verbs start with it."""

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


def _to_verb(row: dict) -> IrregularVerb:
    return IrregularVerb(
        id=row["id"],
        rang=row["rang"],
        infinitive=row["infinitive"],
        simple_past=row["simple_past"],
        past_participle=row["past_participle"],
        translation_fa=row["translation_fa"],
        example_present_nl=row["example_present_nl"],
        example_present_fa=row["example_present_fa"],
        example_past_nl=row["example_past_nl"],
        example_past_fa=row["example_past_fa"],
        example_perfect_nl=row["example_perfect_nl"],
        example_perfect_fa=row["example_perfect_fa"],
        category=row["category"],
    )


async def list_letters() -> list[Letter]:
    """Return every first-letter group with its verb count, alphabetically."""
    engine = _get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                f"SELECT {_LETTER} AS letter, count(*) AS n FROM {_TABLE} "
                "GROUP BY letter ORDER BY letter"
            )
        )
        return [
            Letter(name=r["letter"], count=int(r["n"]))
            for r in result.mappings()
            if r["letter"]
        ]


async def count_by_letter(letter: str) -> int:
    """Return how many verbs start with the given ``letter``."""
    engine = _get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            text(f"SELECT count(*) FROM {_TABLE} WHERE {_LETTER} = :l"),
            {"l": letter},
        )
        return int(result.scalar_one())


async def get_verb_by_offset(letter: str, offset: int) -> IrregularVerb | None:
    """Return the verb at ``offset`` within ``letter`` (0-based), or None."""
    if offset < 0:
        return None
    engine = _get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                f"SELECT {_VERB_COLUMNS} FROM {_TABLE} "
                f"WHERE {_LETTER} = :l {_ORDER} OFFSET :off LIMIT 1"
            ),
            {"l": letter, "off": offset},
        )
        row = result.mappings().first()
        return _to_verb(dict(row)) if row else None


async def dispose() -> None:
    """Dispose of the engine (call on shutdown)."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
