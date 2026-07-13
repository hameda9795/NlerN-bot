"""Business logic for a user's saved 'hard' words (bot's own database)."""

from __future__ import annotations

import logging

from sqlalchemy import delete, func, select

from database.connection import get_db_session
from database.models import SavedWord
from services.vocab_service import VocabWord

logger = logging.getLogger(__name__)


async def save_word(*, user_id: int, word: VocabWord) -> bool:
    """Save a word for a user. Returns True if newly added, False if duplicate."""
    async with get_db_session() as session:
        exists = await session.scalar(
            select(SavedWord.id).where(
                SavedWord.user_id == user_id,
                SavedWord.vocab_word_id == word.id,
            )
        )
        if exists is not None:
            return False
        session.add(
            SavedWord(
                user_id=user_id,
                vocab_word_id=word.id,
                nederlands=word.nederlands,
                persian=word.persian,
                pronunciation=word.pronunciation,
                category=word.category,
            )
        )
        return True


async def is_word_saved(*, user_id: int, vocab_word_id: int) -> bool:
    """Return True if the user already saved the word with this id."""
    async with get_db_session() as session:
        exists = await session.scalar(
            select(SavedWord.id).where(
                SavedWord.user_id == user_id,
                SavedWord.vocab_word_id == vocab_word_id,
            )
        )
        return exists is not None


async def list_saved_words(*, user_id: int) -> list[SavedWord]:
    """Return all saved words for a user, newest first."""
    async with get_db_session() as session:
        result = await session.execute(
            select(SavedWord)
            .where(SavedWord.user_id == user_id)
            .order_by(SavedWord.created_at.desc())
        )
        return list(result.scalars().all())


async def count_saved_words(*, user_id: int) -> int:
    """Return how many words a user has saved."""
    async with get_db_session() as session:
        return int(
            await session.scalar(
                select(func.count(SavedWord.id)).where(SavedWord.user_id == user_id)
            )
            or 0
        )


async def delete_saved_word(*, user_id: int, saved_word_id: int) -> bool:
    """Remove one saved word (e.g. the user learned it). Returns True if removed."""
    async with get_db_session() as session:
        result = await session.execute(
            delete(SavedWord).where(
                SavedWord.id == saved_word_id,
                SavedWord.user_id == user_id,
            )
        )
        return result.rowcount > 0
