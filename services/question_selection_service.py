"""Pick the next question for a user from the reusable bank.

This first iteration does one thing only: serve an *approved* question for the
requested (level, section, topic) that the user has not seen yet. It never
generates a question — if the bucket is exhausted for this user it returns the
sentinel :data:`~services.question_service.NO_UNSEEN_QUESTION_AVAILABLE`, which
the (future) AI top-up flow will use as its trigger.
"""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from database.connection import get_db_session
from database.models import Question, UserQuestionProgress
from services.question_service import (
    NO_UNSEEN_QUESTION_AVAILABLE,
    STATUS_APPROVED,
    QuestionView,
    question_view,
)

logger = logging.getLogger(__name__)


class QuestionSelectionService:
    """Selects which question to show a user next (no AI, no generation yet)."""

    async def get_next_question(
        self, *, user_id: int, level: str, section: str, topic: str
    ) -> QuestionView | str:
        """Return an unseen approved question, or NO_UNSEEN_QUESTION_AVAILABLE.

        A question counts as "seen" once the user has a progress row for it.
        """
        async with get_db_session() as session:
            seen_subq = select(UserQuestionProgress.question_id).where(
                UserQuestionProgress.user_id == user_id
            )
            question = await session.scalar(
                select(Question)
                .where(
                    Question.status == STATUS_APPROVED,
                    Question.level == level,
                    Question.section == section,
                    Question.topic == topic,
                    Question.id.not_in(seen_subq),
                )
                .options(selectinload(Question.options))
                .order_by(func.random())
                .limit(1)
            )

        if question is None:
            logger.info(
                "No unseen approved question for user %s in %s/%s/%s",
                user_id, level, section, topic,
            )
            return NO_UNSEEN_QUESTION_AVAILABLE

        # Unseen by definition, so progress is None.
        return question_view(question, progress=None)

    async def get_next_question_for_section(
        self, *, user_id: int, level: str, section: str
    ) -> QuestionView | str:
        """Like :meth:`get_next_question` but for a whole (level, section).

        Serves an unseen approved question from any topic in the section — this is
        what the Telegram exam flow uses, where the user picks level + section but
        not a specific topic.
        """
        async with get_db_session() as session:
            seen_subq = select(UserQuestionProgress.question_id).where(
                UserQuestionProgress.user_id == user_id
            )
            question = await session.scalar(
                select(Question)
                .where(
                    Question.status == STATUS_APPROVED,
                    Question.level == level,
                    Question.section == section,
                    Question.id.not_in(seen_subq),
                )
                .options(selectinload(Question.options))
                .order_by(func.random())
                .limit(1)
            )

        if question is None:
            logger.info(
                "No unseen approved question for user %s in %s/%s",
                user_id, level, section,
            )
            return NO_UNSEEN_QUESTION_AVAILABLE

        return question_view(question, progress=None)
