"""FSRS spaced-repetition service.

Bridges the ``fsrs`` library (v6) ``Card`` object and our ``FSRSCard`` ORM row.
Cards are created per (user, word); reviews update the schedule and log history.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from fsrs import Card, Rating, Scheduler, State
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import get_settings
from database.connection import get_db_session
from database.models import FSRSCard, ReviewLog, Word

logger = logging.getLogger(__name__)

_settings = get_settings()
_scheduler = Scheduler(desired_retention=_settings.fsrs.desired_retention)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _row_to_card(row: FSRSCard) -> Card:
    """Build an fsrs ``Card`` from a DB row."""
    return Card(
        card_id=row.id,
        state=State(row.card_state),
        step=row.step,
        stability=row.stability,
        difficulty=row.difficulty,
        due=_aware(row.due_date),
        last_review=_aware(row.last_review_date),
    )


def _apply_card_to_row(row: FSRSCard, card: Card) -> None:
    """Copy fsrs ``Card`` scheduling fields back onto the DB row."""
    row.card_state = card.state.value
    row.step = card.step
    row.stability = card.stability
    row.difficulty = card.difficulty
    row.due_date = card.due
    row.last_review_date = card.last_review


def _aware(value: datetime | None) -> datetime | None:
    """Ensure a datetime is timezone-aware (SQLite may return naive)."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


@dataclass(slots=True)
class DueCard:
    """A due card joined with its word, for display in handlers."""

    card_id: int
    word_id: int
    dutch_word: str
    article: str | None
    persian_translation: str
    example_dutch: str | None
    example_persian: str | None


async def create_card(user_id: int, word_id: int) -> int:
    """Create an FSRS card for (user, word) if absent. Returns the card id.

    Idempotent: returns the existing card id when one already exists.
    """
    async with get_db_session() as session:
        existing = await session.scalar(
            select(FSRSCard).where(
                FSRSCard.user_id == user_id, FSRSCard.word_id == word_id
            )
        )
        if existing is not None:
            return existing.id

        fresh = Card()  # state=Learning, due=now, stability/difficulty=None
        row = FSRSCard(
            user_id=user_id,
            word_id=word_id,
            card_state=fresh.state.value,
            step=fresh.step,
            stability=fresh.stability,
            difficulty=fresh.difficulty,
            due_date=fresh.due,
            last_review_date=fresh.last_review,
        )
        session.add(row)
        await session.flush()
        return row.id


async def get_due_cards(user_id: int, limit: int = 20) -> list[DueCard]:
    """Return cards due now (or earlier) for the user, with word details."""
    async with get_db_session() as session:
        result = await session.execute(
            select(FSRSCard, Word)
            .join(Word, Word.id == FSRSCard.word_id)
            .where(FSRSCard.user_id == user_id, FSRSCard.due_date <= _now())
            .order_by(FSRSCard.due_date.asc())
            .limit(limit)
        )
        return [
            DueCard(
                card_id=card.id,
                word_id=word.id,
                dutch_word=word.dutch_word,
                article=word.article,
                persian_translation=word.persian_translation,
                example_dutch=word.example_sentence_dutch,
                example_persian=word.example_sentence_persian,
            )
            for card, word in result.all()
        ]


async def review_card(card_id: int, rating: int) -> FSRSCard | None:
    """Apply a review rating (1=Again..4=Easy) and persist the new schedule."""
    rating_enum = Rating(rating)
    now = _now()
    async with get_db_session() as session:
        row = await session.get(FSRSCard, card_id)
        if row is None:
            return None

        card = _row_to_card(row)
        updated_card, _log = _scheduler.review_card(card, rating_enum, now)

        elapsed = 0
        if row.last_review_date is not None:
            elapsed = max((now - _aware(row.last_review_date)).days, 0)
        scheduled = max((updated_card.due - now).days, 0)

        _apply_card_to_row(row, updated_card)
        row.reps = (row.reps or 0) + 1
        if rating_enum is Rating.Again:
            row.lapses = (row.lapses or 0) + 1
        row.elapsed_days = elapsed
        row.scheduled_days = scheduled

        session.add(
            ReviewLog(
                card_id=row.id,
                rating=rating,
                review_datetime=now,
                scheduled_days=scheduled,
                elapsed_days=elapsed,
            )
        )
        await session.flush()
        await session.refresh(row)
        return row


async def get_card_stats(user_id: int) -> dict[str, int]:
    """Return counts of total / due / learning / review / relearning cards."""
    async with get_db_session() as session:
        total = int(
            await session.scalar(
                select(func.count())
                .select_from(FSRSCard)
                .where(FSRSCard.user_id == user_id)
            )
            or 0
        )
        due = int(
            await session.scalar(
                select(func.count())
                .select_from(FSRSCard)
                .where(FSRSCard.user_id == user_id, FSRSCard.due_date <= _now())
            )
            or 0
        )

        async def _by_state(state: State) -> int:
            return int(
                await session.scalar(
                    select(func.count())
                    .select_from(FSRSCard)
                    .where(
                        FSRSCard.user_id == user_id,
                        FSRSCard.card_state == state.value,
                    )
                )
                or 0
            )

        return {
            "total": total,
            "due": due,
            "learning": await _by_state(State.Learning),
            "review": await _by_state(State.Review),
            "relearning": await _by_state(State.Relearning),
        }


async def ensure_cards_for_level(
    session: AsyncSession, user_id: int, cefr_level: str, limit: int = 20
) -> int:
    """Create cards for words at a level that the user doesn't have yet.

    Returns the number of new cards created. Uses the caller's session.
    """
    existing_word_ids = set(
        (
            await session.execute(
                select(FSRSCard.word_id).where(FSRSCard.user_id == user_id)
            )
        )
        .scalars()
        .all()
    )
    words = (
        (
            await session.execute(
                select(Word.id).where(Word.cefr_level == cefr_level).limit(limit)
            )
        )
        .scalars()
        .all()
    )
    created = 0
    for word_id in words:
        if word_id in existing_word_ids:
            continue
        fresh = Card()
        session.add(
            FSRSCard(
                user_id=user_id,
                word_id=word_id,
                card_state=fresh.state.value,
                step=fresh.step,
                stability=fresh.stability,
                difficulty=fresh.difficulty,
                due_date=fresh.due,
            )
        )
        created += 1
    return created
