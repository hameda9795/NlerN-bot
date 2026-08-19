"""KNM exam: grouping, question selection, answering, and progress.

The 234 KNM items are split into fixed groups of :data:`GROUP_SIZE` by their
source ``position``, so the last group is simply whatever is left over (34 with
the current dataset). Groups are positional rather than thematic on purpose —
the themes are uneven (12 to 39 items), which would make some groups four times
longer than others.

Progress is one :class:`KnmAttempt` row per (user, question): a user resumes at
the first question of the group they have not answered yet, and re-taking a
group deletes its rows.

Grouping is computed in Python rather than in SQL. The bank is a couple of
hundred rows, and ``position / GROUP_SIZE`` in SQL would depend on each
backend's integer-division semantics for no benefit.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import delete, func, select

from database.connection import get_db_session
from database.models import KnmAttempt, KnmQuestion

logger = logging.getLogger(__name__)

GROUP_SIZE = 40


@dataclass(frozen=True)
class KnmOption:
    key: str
    text_nl: str


@dataclass(frozen=True)
class KnmQuestionView:
    """Everything the UI needs to render one question, without an ORM session."""

    id: int
    group: int
    # 1-based position of this question inside its group, and the group's size.
    index_in_group: int
    group_total: int
    question_text_nl: str
    options: list[KnmOption]


@dataclass(frozen=True)
class KnmAnswerResult:
    is_correct: bool
    correct_option_key: str
    correct_option_text: str
    feedback_fa: str | None
    explanation_fa: str | None
    key_terms_fa: str | None


@dataclass(frozen=True)
class KnmGroup:
    """One group's summary row for the group menu."""

    index: int  # 0-based
    first_number: int  # 1-based number of the group's first question overall
    last_number: int
    total: int
    answered: int
    correct: int

    @property
    def is_finished(self) -> bool:
        return self.total > 0 and self.answered >= self.total

    @property
    def is_untouched(self) -> bool:
        return self.answered == 0


def _group_of(position: int) -> int:
    return position // GROUP_SIZE


def _key_terms_fa(row: KnmQuestion) -> str | None:
    """Render the Persian glossary as one line, or None when there is none."""
    rendered = " · ".join(
        f"{term['term_nl']}: {term['meaning_fa']}"
        for term in (row.key_terms_json or [])
        if term.get("term_nl") and term.get("meaning_fa")
    )
    return rendered or None


async def list_groups(*, user_id: int) -> list[KnmGroup]:
    """Return every group with this user's progress, ordered by group index."""
    async with get_db_session() as session:
        positions = list(await session.scalars(select(KnmQuestion.position)))
        answers = (
            await session.execute(
                select(KnmQuestion.position, KnmAttempt.is_correct)
                .join(KnmAttempt, KnmAttempt.knm_id == KnmQuestion.id)
                .where(KnmAttempt.user_id == user_id)
            )
        ).all()

    totals: dict[int, int] = {}
    for position in positions:
        totals[_group_of(position)] = totals.get(_group_of(position), 0) + 1

    answered: dict[int, int] = {}
    correct: dict[int, int] = {}
    for position, is_correct in answers:
        group = _group_of(position)
        answered[group] = answered.get(group, 0) + 1
        if is_correct:
            correct[group] = correct.get(group, 0) + 1

    return [
        KnmGroup(
            index=group,
            first_number=group * GROUP_SIZE + 1,
            last_number=group * GROUP_SIZE + totals[group],
            total=totals[group],
            answered=answered.get(group, 0),
            correct=correct.get(group, 0),
        )
        for group in sorted(totals)
    ]


async def get_group(*, user_id: int, group: int) -> KnmGroup | None:
    """Return one group's summary, or None if that group does not exist."""
    for candidate in await list_groups(user_id=user_id):
        if candidate.index == group:
            return candidate
    return None


async def next_question(*, user_id: int, group: int) -> KnmQuestionView | None:
    """Return the group's first unanswered question, or None when it is done."""
    low = group * GROUP_SIZE
    high = low + GROUP_SIZE
    async with get_db_session() as session:
        total = int(
            await session.scalar(
                select(func.count())
                .select_from(KnmQuestion)
                .where(KnmQuestion.position >= low, KnmQuestion.position < high)
            )
            or 0
        )
        if total == 0:
            return None
        answered = select(KnmAttempt.knm_id).where(KnmAttempt.user_id == user_id)
        row = await session.scalar(
            select(KnmQuestion)
            .where(
                KnmQuestion.position >= low,
                KnmQuestion.position < high,
                KnmQuestion.id.not_in(answered),
            )
            .order_by(KnmQuestion.position)
            .limit(1)
        )
    if row is None:
        return None
    return KnmQuestionView(
        id=row.id,
        group=_group_of(row.position),
        index_in_group=(row.position % GROUP_SIZE) + 1,
        group_total=total,
        question_text_nl=row.question_text_nl,
        options=[
            KnmOption(key=option["key"], text_nl=option["text_nl"])
            for option in row.options_json
        ],
    )


async def record_answer(
    *, user_id: int, knm_id: int, selected_option_key: str
) -> KnmAnswerResult | None:
    """Grade an answer and store it. Returns None if the question is gone."""
    selected_option_key = selected_option_key.strip().upper()
    async with get_db_session() as session:
        row = await session.scalar(select(KnmQuestion).where(KnmQuestion.id == knm_id))
        if row is None:
            return None

        options = {option["key"]: option for option in row.options_json}
        chosen = options.get(selected_option_key)
        correct = next(
            (option for option in row.options_json if option["is_correct"]), None
        )
        is_correct = chosen is not None and bool(chosen["is_correct"])

        attempt = await session.scalar(
            select(KnmAttempt).where(
                KnmAttempt.user_id == user_id, KnmAttempt.knm_id == knm_id
            )
        )
        if attempt is None:
            session.add(
                KnmAttempt(
                    user_id=user_id,
                    knm_id=knm_id,
                    selected_option_key=selected_option_key,
                    is_correct=is_correct,
                )
            )
        else:
            attempt.selected_option_key = selected_option_key
            attempt.is_correct = is_correct

        result = KnmAnswerResult(
            is_correct=is_correct,
            correct_option_key=correct["key"] if correct else "",
            correct_option_text=correct["text_nl"] if correct else "",
            feedback_fa=chosen["feedback_fa"] if chosen else None,
            explanation_fa=row.explanation_fa,
            key_terms_fa=_key_terms_fa(row),
        )
        await session.flush()

    logger.info(
        "KNM answer by user %s on question %s: %s",
        user_id, knm_id, "correct" if is_correct else "wrong",
    )
    return result


async def reset_group(*, user_id: int, group: int) -> int:
    """Delete this user's answers for one group. Returns rows removed."""
    low = group * GROUP_SIZE
    high = low + GROUP_SIZE
    async with get_db_session() as session:
        in_group = select(KnmQuestion.id).where(
            KnmQuestion.position >= low, KnmQuestion.position < high
        )
        removed = await session.execute(
            delete(KnmAttempt).where(
                KnmAttempt.user_id == user_id, KnmAttempt.knm_id.in_(in_group)
            )
        )
    logger.info("Reset KNM group %s for user %s (%s rows)", group, user_id, removed.rowcount)
    return removed.rowcount
