"""Business logic for CEFR lessons (curriculum)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select

from database.connection import get_db_session
from database.models import Lesson, User, UserProgress
from services.xp import award_xp

# CEFR ladder used to pick the "next" level when suggesting lessons.
CEFR_ORDER = ["A0", "A1", "A2", "B1", "B2"]

XP_LESSON_COMPLETE = 20


@dataclass(slots=True)
class LessonContent:
    """Parsed content_json of a lesson."""

    vocabulary: list[str]
    grammar_note: str
    practice: list[str]

    @classmethod
    def from_json(cls, raw: str) -> "LessonContent":
        try:
            data = json.loads(raw or "{}")
        except json.JSONDecodeError:
            data = {}
        return cls(
            vocabulary=list(data.get("vocabulary", [])),
            grammar_note=str(data.get("grammar_note", "")),
            practice=list(data.get("practice", [])),
        )


async def get_user_current_level(user_id: int) -> str:
    """Return the user's current CEFR level (defaults to 'A0')."""
    async with get_db_session() as session:
        level = await session.scalar(
            select(User.current_cefr_level).where(User.id == user_id)
        )
        return level or "A0"


async def get_available_lessons(user_id: int, cefr_level: str) -> list[Lesson]:
    """Return published lessons for the given level, ordered by order_index."""
    async with get_db_session() as session:
        result = await session.execute(
            select(Lesson)
            .where(Lesson.cefr_level == cefr_level, Lesson.is_published.is_(True))
            .order_by(Lesson.order_index)
        )
        return list(result.scalars().all())


async def get_completed_lesson_ids(user_id: int) -> set[int]:
    """Return the set of lesson ids the user has completed."""
    async with get_db_session() as session:
        result = await session.execute(
            select(UserProgress.lesson_id).where(
                UserProgress.user_id == user_id,
                UserProgress.completed_at.is_not(None),
            )
        )
        return set(result.scalars().all())


async def get_lesson_detail(lesson_id: int) -> Lesson | None:
    """Return a single lesson by id."""
    async with get_db_session() as session:
        return await session.get(Lesson, lesson_id)


async def mark_lesson_completed(
    user_id: int, lesson_id: int, score: float = 100.0
) -> int:
    """Mark a lesson completed (idempotent) and award XP. Returns XP awarded.

    Returns 0 if the lesson was already completed (no double XP).
    """
    now = datetime.now(timezone.utc)
    async with get_db_session() as session:
        existing = await session.scalar(
            select(UserProgress).where(
                UserProgress.user_id == user_id,
                UserProgress.lesson_id == lesson_id,
            )
        )
        if existing and existing.completed_at is not None:
            return 0

        if existing is None:
            existing = UserProgress(user_id=user_id, lesson_id=lesson_id)
            session.add(existing)
        existing.completed_at = now
        existing.score = score

        user = await session.get(User, user_id)
        if user is not None:
            await award_xp(
                session,
                user=user,
                event_type="lesson_complete",
                amount=XP_LESSON_COMPLETE,
                description=f"lesson {lesson_id}",
            )
        return XP_LESSON_COMPLETE


def next_level(current: str) -> str | None:
    """Return the next CEFR level after ``current``, or None if at the top."""
    try:
        idx = CEFR_ORDER.index(current)
    except ValueError:
        return None
    return CEFR_ORDER[idx + 1] if idx + 1 < len(CEFR_ORDER) else None
