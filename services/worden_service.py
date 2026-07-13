"""Read-only access to the chapter-by-chapter Dutch vocabulary (واژگان فصل‌ها).

The data lives in the same remote PostgreSQL database as the rest of the
vocabulary (``VOCAB_DATABASE_URL``), in schema ``worden``. Each *chapter* is a
group of tables named ``fasl_NN_<topic>`` (the full chapter) plus, where the
chapter is split into sub-topics, ``fasl_NN__<subtopic>`` tables. Every row is
one word/phrase, but the column layout varies a little between tables (some
have ``additional_meanings``/``notes``/``examples``, the sentence-pattern and
common-mistakes chapters use their own columns). Browsing is therefore done
generically: we hand the whole row to the formatter.

This module owns a dedicated read-only async engine and never writes. Browsing
is stateless: handlers pass the table name plus an offset and we fetch exactly
the one row at that position, so navigation survives a bot restart and needs no
large FSM payload. Table names arrive from inline-button callback data, so they
are always validated against a cached allow-list of real ``worden`` tables
before being interpolated into a query (identifiers can't be bound params).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from bot.config import get_settings

logger = logging.getLogger(__name__)

_settings = get_settings()

_SCHEMA = "worden"
# A table belonging to a chapter: fasl_<2+ digits>_<rest>. Double underscore
# (``fasl_03__rooms``) marks a sub-topic; single underscore the full chapter.
_TABLE_RE = re.compile(r"^fasl_(\d{2,})_+([a-z0-9_]+)$")

# Persian titles for the chapters (keyed by chapter number). Falls back to a
# prettified version of the table slug when a number isn't listed here.
CHAPTER_TITLES_FA: dict[int, str] = {
    1: "اطلاعات شخصی",
    2: "خانواده",
    3: "خانه و مبلمان",
    4: "غذا و نوشیدنی",
    5: "خرید",
    6: "پول و پرداخت",
    7: "زمان و تاریخ",
    8: "روزها، ماه‌ها و فصل‌ها",
    9: "آب‌وهوا",
    10: "اعداد و مقادیر",
    12: "پوشاک",
    13: "بدن و سلامتی",
    14: "دکتر و داروخانه",
    15: "کار و مشاغل",
    16: "درخواست شغل",
    17: "مدرسه و آموزش",
    18: "حمل‌ونقل",
    19: "سفر",
    20: "شهر و مسیریابی",
    21: "دولت و شهرداری",
    22: "مسکن و اجاره",
    23: "مهاجرت و مدارک رسمی",
    24: "ارتباط اجتماعی",
    25: "احساسات و عواطف",
    26: "نظرها و استدلال",
    27: "مشکلات و شکایت‌ها",
    28: "فناوری و اینترنت",
    29: "موبایل و اپلیکیشن‌ها",
    30: "ایمیل و پیام‌ها",
    31: "کارهای روزمره",
    32: "سرگرمی و اوقات فراغت",
    33: "ورزش",
    34: "طبیعت و محیط‌زیست",
    35: "اخبار و رسانه",
    36: "فرهنگ و جامعه",
    38: "افعال بی‌قاعده",
    39: "افعال جداشدنی",
    40: "افعال انعکاسی",
    41: "افعال کمکی (مدال)",
    42: "صفت‌ها",
    43: "قیدها",
    44: "حروف اضافه",
    45: "حروف ربط",
    46: "کلمات پرسشی",
    47: "الگوهای جمله‌ی کاربردی",
    48: "اشتباهات رایج فارسی‌زبانان",
    49: "هلندی رسمی",
    50: "هلندی محاوره‌ای",
}


@dataclass(frozen=True)
class Chapter:
    """One chapter (a ``fasl_NN`` group) and how many tables/words it holds."""

    number: int
    title: str
    table_count: int
    word_count: int


@dataclass(frozen=True)
class Topic:
    """One table within a chapter (the full chapter or a sub-topic)."""

    table: str
    label: str
    count: int
    is_parent: bool


@dataclass(frozen=True)
class WordRow:
    """One vocabulary row, kept as a raw column→value mapping for the formatter."""

    table: str
    id: int
    data: dict


_engine: AsyncEngine | None = None
# Cached allow-list of real ``worden`` table names; gates every interpolation.
_valid_tables: set[str] | None = None


def _get_engine() -> AsyncEngine:
    """Return the lazily-created read-only engine for the vocabulary database."""
    global _engine
    if _engine is None:
        url = _settings.database.vocab_database_url
        if not url:
            raise RuntimeError("VOCAB_DATABASE_URL is not configured.")
        _engine = create_async_engine(url, pool_pre_ping=True, pool_size=3)
    return _engine


def pretty_label(slug: str) -> str:
    """Turn a table slug like ``home_and_furniture`` into ``Home And Furniture``."""
    return slug.replace("_", " ").strip().title()


async def _load_tables() -> set[str]:
    """Load (and cache) the set of ``fasl_*`` table names in the worden schema."""
    global _valid_tables
    if _valid_tables is None:
        engine = _get_engine()
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = :schema AND table_name LIKE 'fasl\\_%'"
                ),
                {"schema": _SCHEMA},
            )
            _valid_tables = {
                r[0] for r in result if _TABLE_RE.match(r[0])
            }
    return _valid_tables


def _qualified(table: str) -> str:
    """Return a safely-quoted ``schema.table`` for an already-validated name."""
    # table is guaranteed (by caller) to be in the cached allow-list.
    return f'{_SCHEMA}."{table}"'


async def list_chapters() -> list[Chapter]:
    """Return every chapter (sorted by number) with its table and word counts."""
    tables = await _load_tables()
    # Group table names by chapter number.
    by_chapter: dict[int, list[str]] = {}
    for t in tables:
        m = _TABLE_RE.match(t)
        if not m:
            continue
        by_chapter.setdefault(int(m.group(1)), []).append(t)

    engine = _get_engine()
    chapters: list[Chapter] = []
    async with engine.connect() as conn:
        for number in sorted(by_chapter):
            names = by_chapter[number]
            # Word count for the chapter = the parent (full) table if present,
            # else the sum of its tables. Parent = single underscore after fasl_NN.
            parent = _parent_table(number, names)
            if parent is not None:
                count = await conn.scalar(
                    text(f"SELECT count(*) FROM {_qualified(parent)}")
                )
            else:
                count = 0
                for n in names:
                    count += await conn.scalar(
                        text(f"SELECT count(*) FROM {_qualified(n)}")
                    )
            slug = _TABLE_RE.match(parent or names[0]).group(2)
            title = CHAPTER_TITLES_FA.get(number, pretty_label(slug))
            chapters.append(
                Chapter(
                    number=number,
                    title=title,
                    table_count=len(names),
                    word_count=int(count or 0),
                )
            )
    return chapters


def _parent_table(number: int, names: list[str]) -> str | None:
    """The full-chapter table (single underscore after ``fasl_NN``), if any."""
    prefix = f"fasl_{number:02d}"
    for n in names:
        # Parent has exactly one underscore separating prefix and slug.
        if n.startswith(prefix + "_") and not n.startswith(prefix + "__"):
            return n
    return None


async def list_topics(number: int) -> list[Topic]:
    """Return the tables of chapter ``number``: the full chapter first, then subs."""
    tables = await _load_tables()
    prefix = f"fasl_{number:02d}_"
    names = sorted(n for n in tables if n.startswith(prefix))
    if not names:
        return []
    parent = _parent_table(number, names)

    engine = _get_engine()
    topics: list[Topic] = []
    async with engine.connect() as conn:
        for n in names:
            count = await conn.scalar(text(f"SELECT count(*) FROM {_qualified(n)}"))
            m = _TABLE_RE.match(n)
            slug = m.group(2) if m else n
            is_parent = n == parent
            label = "همه‌ی واژگان فصل" if is_parent else pretty_label(slug)
            topics.append(
                Topic(table=n, label=label, count=int(count or 0), is_parent=is_parent)
            )
    # Full-chapter table first, then the sub-topics.
    topics.sort(key=lambda t: (not t.is_parent, t.label))
    return topics


async def is_valid_table(table: str) -> bool:
    """True when ``table`` is a real ``fasl_*`` table (guards interpolation)."""
    return table in await _load_tables()


async def count_rows(table: str) -> int:
    """Return how many rows ``table`` has (0 if the table is unknown)."""
    if not await is_valid_table(table):
        return 0
    engine = _get_engine()
    async with engine.connect() as conn:
        return int(await conn.scalar(text(f"SELECT count(*) FROM {_qualified(table)}")) or 0)


async def get_row_by_offset(table: str, offset: int) -> WordRow | None:
    """Return the row at ``offset`` within ``table`` (0-based), or None."""
    if offset < 0 or not await is_valid_table(table):
        return None
    engine = _get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                f"SELECT * FROM {_qualified(table)} ORDER BY id OFFSET :off LIMIT 1"
            ),
            {"off": offset},
        )
        row = result.mappings().first()
        return WordRow(table=table, id=int(row["id"]), data=dict(row)) if row else None


def describe_table(table: str) -> tuple[int, str, str]:
    """Return ``(chapter_number, chapter_title, topic_label)`` for a table name.

    Pure string work (no DB), used to label a word card. The full-chapter table
    is labelled «همه‌ی واژگان فصل»; sub-topics get a prettified slug.
    """
    m = _TABLE_RE.match(table)
    if not m:
        return (0, "واژگان", pretty_label(table))
    number = int(m.group(1))
    slug = m.group(2)
    title = CHAPTER_TITLES_FA.get(number, pretty_label(slug))
    prefix = f"fasl_{number:02d}"
    is_parent = table.startswith(prefix + "_") and not table.startswith(prefix + "__")
    topic_label = "همه‌ی واژگان فصل" if is_parent else pretty_label(slug)
    return (number, title, topic_label)


async def chapter_title(number: int) -> str:
    """Persian title for a chapter number (best-effort)."""
    if number in CHAPTER_TITLES_FA:
        return CHAPTER_TITLES_FA[number]
    parent = _parent_table(number, sorted(await _load_tables()))
    if parent:
        return pretty_label(_TABLE_RE.match(parent).group(2))
    return f"فصل {number}"


async def dispose() -> None:
    """Dispose of the engine (call on shutdown)."""
    global _engine, _valid_tables
    if _engine is not None:
        await _engine.dispose()
        _engine = None
    _valid_tables = None
