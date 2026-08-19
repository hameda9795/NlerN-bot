"""Question-bank core: shared view types, answer recording and progress upkeep.

This module is the data layer for the reusable question bank. It deliberately
contains **no** AI generation and **no** answer *grading* heuristics — a question
is correct iff the selected option's ``is_correct`` flag is set. Selection of the
next question lives in :mod:`services.question_selection_service`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from database.connection import get_db_session
from database.models import (
    Question,
    User,
    UserQuestionAttempt,
    UserQuestionProgress,
)

logger = logging.getLogger(__name__)

# --- Question status (only APPROVED questions are ever served to learners) ---
STATUS_DRAFT = "draft"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"

# --- Allowed section identifiers (English snake_case; UI labels live elsewhere) ---
SECTIONS: tuple[str, ...] = (
    "grammar",
    "vocab_in_context",
    "reading",
    "meaning",
    "conversation",
    "error_correction",
    "listening",
    "writing",
    "speaking",
    "formal_informal",
)

# Returned by the selection service when the bucket is exhausted for this user.
NO_UNSEEN_QUESTION_AVAILABLE = "NO_UNSEEN_QUESTION_AVAILABLE"


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def user_exists(*, user_id: int) -> bool:
    """Return True if a user row with this id exists.

    Used by the API layer to reject unknown users with a clean 400 instead of
    letting an attempt insert fail on the foreign key (a generic 500).
    """
    async with get_db_session() as session:
        return await session.scalar(
            select(User.id).where(User.id == user_id)
        ) is not None


# ---------------------------------------------------------------------------
# Read-side view models (plain dataclasses, safe to serialize to JSON).
# ``OptionView`` intentionally omits ``is_correct`` so the "next question"
# endpoint never leaks the answer to the client.
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class OptionView:
    key: str  # A / B / C / D
    text_nl: str


@dataclass(slots=True)
class ProgressView:
    times_seen: int
    times_correct: int
    times_wrong: int
    mastery_score: float
    last_seen_at: datetime | None
    next_review_at: datetime | None


@dataclass(slots=True)
class QuestionView:
    id: int
    level: str
    section: str
    topic: str
    question_type: str
    difficulty: int
    question_text_nl: str
    question_text_fa: str | None
    options: list[OptionView]
    progress: ProgressView | None  # None when the user has never seen it


@dataclass(slots=True)
class AnswerResult:
    question_id: int
    is_correct: bool
    selected_option_key: str
    correct_option_key: str
    explanation_fa: str | None
    feedback_fa: str | None
    progress: ProgressView


def _progress_view(row: UserQuestionProgress) -> ProgressView:
    return ProgressView(
        times_seen=row.times_seen,
        times_correct=row.times_correct,
        times_wrong=row.times_wrong,
        mastery_score=row.mastery_score,
        last_seen_at=row.last_seen_at,
        next_review_at=row.next_review_at,
    )


def question_view(question: Question, progress: UserQuestionProgress | None) -> QuestionView:
    """Build a serializable view from an ORM question (options preloaded)."""
    return QuestionView(
        id=question.id,
        level=question.level,
        section=question.section,
        topic=question.topic,
        question_type=question.question_type,
        difficulty=question.difficulty,
        question_text_nl=question.question_text_nl,
        question_text_fa=question.question_text_fa,
        options=[
            OptionView(key=o.option_key, text_nl=o.option_text_nl)
            for o in question.options
        ],
        progress=_progress_view(progress) if progress is not None else None,
    )


async def record_answer(
    *,
    user_id: int,
    question_id: int,
    selected_option_key: str,
    time_spent_seconds: int | None = None,
) -> AnswerResult | None:
    """Grade an answer, store the attempt and update the user's progress.

    Correctness is a pure lookup on the chosen option's ``is_correct`` flag.
    Returns ``None`` if the question does not exist (let the caller 404).
    """
    selected_option_key = selected_option_key.strip().upper()
    async with get_db_session() as session:
        question = await session.scalar(
            select(Question)
            .where(
                Question.id == question_id,
                Question.status == STATUS_APPROVED,
            )
            .options(selectinload(Question.options))
        )
        if question is None:
            return None

        options = {o.option_key: o for o in question.options}
        correct_key = next(
            (o.option_key for o in question.options if o.is_correct), ""
        )
        chosen = options.get(selected_option_key)
        is_correct = chosen is not None and chosen.is_correct

        # 1. Persist the immutable attempt.
        session.add(
            UserQuestionAttempt(
                user_id=user_id,
                question_id=question_id,
                selected_option_key=selected_option_key,
                is_correct=is_correct,
                time_spent_seconds=time_spent_seconds,
            )
        )

        # 2. Upsert the aggregate progress row.
        progress = await session.scalar(
            select(UserQuestionProgress).where(
                UserQuestionProgress.user_id == user_id,
                UserQuestionProgress.question_id == question_id,
            )
        )
        if progress is None:
            # Initialize counters explicitly: column ``default``s are only applied
            # at INSERT flush, so a freshly built (unflushed) row has None here.
            progress = UserQuestionProgress(
                user_id=user_id,
                question_id=question_id,
                times_seen=0,
                times_correct=0,
                times_wrong=0,
                mastery_score=0.0,
            )
            session.add(progress)
        progress.times_seen += 1
        if is_correct:
            progress.times_correct += 1
        else:
            progress.times_wrong += 1
        # Simple mastery = share of correct answers so far (FSRS scheduling later).
        progress.mastery_score = progress.times_correct / progress.times_seen
        progress.last_seen_at = _now()

        await session.flush()
        result = AnswerResult(
            question_id=question_id,
            is_correct=is_correct,
            selected_option_key=selected_option_key,
            correct_option_key=correct_key,
            explanation_fa=question.explanation_fa,
            feedback_fa=chosen.feedback_fa if chosen is not None else None,
            progress=_progress_view(progress),
        )
    logger.info(
        "User %s answered question %s: %s", user_id, question_id,
        "correct" if is_correct else "wrong",
    )
    return result
