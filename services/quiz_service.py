"""Quiz generation from the Word catalog.

Quizzes are generated on the fly (not persisted): a question is a Dutch word
and four Persian options (one correct). State lives in the FSM during a session.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from sqlalchemy import func, select

from database.connection import get_db_session
from database.models import Word

QUIZ_LENGTH = 5
XP_PER_CORRECT = 5


@dataclass(slots=True)
class QuizQuestion:
    """A single multiple-choice question."""

    word_id: int
    prompt: str  # Dutch word (with article)
    options: list[str]  # four Persian options
    correct_index: int
    example_dutch: str | None
    example_persian: str | None


def _with_article(word: Word) -> str:
    return f"{word.article} {word.dutch_word}" if word.article else word.dutch_word


async def generate_quiz(
    *, cefr_level: str | None = None, length: int = QUIZ_LENGTH
) -> list[QuizQuestion]:
    """Build a list of multiple-choice questions.

    Picks ``length`` words (optionally filtered by level) and, for each, three
    distractor translations drawn from other words.
    """
    async with get_db_session() as session:
        stmt = select(Word)
        if cefr_level:
            stmt = stmt.where(Word.cefr_level == cefr_level)
        words = list((await session.execute(stmt)).scalars().all())

        # Fall back to the whole catalog if the level has too few words.
        if len(words) < 4:
            words = list((await session.execute(select(Word))).scalars().all())

    if len(words) < 4:
        return []

    chosen = random.sample(words, min(length, len(words)))
    all_translations = [w.persian_translation for w in words]

    questions: list[QuizQuestion] = []
    for word in chosen:
        distractors = [t for t in all_translations if t != word.persian_translation]
        options = random.sample(distractors, 3) + [word.persian_translation]
        random.shuffle(options)
        questions.append(
            QuizQuestion(
                word_id=word.id,
                prompt=_with_article(word),
                options=options,
                correct_index=options.index(word.persian_translation),
                example_dutch=word.example_sentence_dutch,
                example_persian=word.example_sentence_persian,
            )
        )
    return questions


async def word_count(cefr_level: str | None = None) -> int:
    """Number of words available (optionally for a level)."""
    async with get_db_session() as session:
        stmt = select(func.count()).select_from(Word)
        if cefr_level:
            stmt = stmt.where(Word.cefr_level == cefr_level)
        return int(await session.scalar(stmt) or 0)
