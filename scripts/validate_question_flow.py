"""Validate the question flow against the seeded A2/grammar/zijn_hebben bank.

Drives the real services (one event loop) for two scenarios, then cleans up the
test progress/attempts it created so the bank is left fresh.

Scenario A: user 9 pulls + answers every question; never sees a repeat; after the
            bucket is exhausted, the next pull returns NO_UNSEEN_QUESTION_AVAILABLE.
Scenario B: a different real user gets the *same* full set independently, with
            per-user progress.

Usage::

    uv run python -m scripts.validate_question_flow
"""

from __future__ import annotations

import asyncio

from sqlalchemy import delete, func, select

from database.connection import get_db_session
from database.models import (
    Question,
    UserQuestionAttempt,
    UserQuestionProgress,
)
from services.question_selection_service import QuestionSelectionService
from services.question_service import (
    NO_UNSEEN_QUESTION_AVAILABLE,
    QuestionView,
    record_answer,
)

LEVEL, SECTION, TOPIC = "A2", "grammar", "zijn_hebben"
USER_A = 9  # scenario A
USER_B = 5  # scenario B (independent)

_svc = QuestionSelectionService()
_passes = 0
_fails = 0


def _check(label: str, ok: bool) -> None:
    global _passes, _fails
    mark = "PASS" if ok else "FAIL"
    if ok:
        _passes += 1
    else:
        _fails += 1
    print(f"  [{mark}] {label}")


async def _bucket_size() -> int:
    async with get_db_session() as s:
        return int(
            await s.scalar(
                select(func.count())
                .select_from(Question)
                .where(
                    Question.level == LEVEL,
                    Question.section == SECTION,
                    Question.topic == TOPIC,
                    Question.status == "approved",
                )
            )
            or 0
        )


async def _run_user(user_id: int, total: int) -> list[int]:
    """Pull+answer until exhausted; return the ordered list of question ids seen."""
    seen: list[int] = []
    for _ in range(total + 1):  # one extra pull to hit the sentinel
        result = await _svc.get_next_question(
            user_id=user_id, level=LEVEL, section=SECTION, topic=TOPIC
        )
        if isinstance(result, str):
            _check(f"user {user_id}: sentinel == NO_UNSEEN after {len(seen)} answered",
                   result == NO_UNSEEN_QUESTION_AVAILABLE and len(seen) == total)
            return seen
        assert isinstance(result, QuestionView)
        _check(f"user {user_id}: pulled qid={result.id} not a repeat",
               result.id not in seen)
        _check(f"user {user_id}: qid={result.id} has exactly 4 options",
               len(result.options) == 4)
        seen.append(result.id)
        # Answer with option A (correctness is irrelevant to the seen/unseen flow).
        ans = await record_answer(
            user_id=user_id, question_id=result.id,
            selected_option_key="A", time_spent_seconds=3,
        )
        assert ans is not None
    return seen


async def _progress_count(user_id: int) -> int:
    async with get_db_session() as s:
        return int(
            await s.scalar(
                select(func.count())
                .select_from(UserQuestionProgress)
                .where(UserQuestionProgress.user_id == user_id)
            )
            or 0
        )


async def _cleanup() -> None:
    async with get_db_session() as s:
        await s.execute(
            delete(UserQuestionAttempt).where(
                UserQuestionAttempt.user_id.in_((USER_A, USER_B))
            )
        )
        await s.execute(
            delete(UserQuestionProgress).where(
                UserQuestionProgress.user_id.in_((USER_A, USER_B))
            )
        )


async def main() -> None:
    total = await _bucket_size()
    print(f"Approved questions in {LEVEL}/{SECTION}/{TOPIC}: {total}\n")

    # Start from a clean slate for both test users.
    await _cleanup()

    print(f"--- Scenario A (user {USER_A}) ---")
    seen_a = await _run_user(USER_A, total)
    _check(f"user {USER_A}: saw all {total} distinct questions",
           len(set(seen_a)) == total)

    print(f"\n--- Scenario B (user {USER_B}, independent) ---")
    seen_b = await _run_user(USER_B, total)
    _check(f"user {USER_B}: saw all {total} distinct questions",
           len(set(seen_b)) == total)
    _check("both users saw the same question set",
           set(seen_a) == set(seen_b))
    _check(f"user {USER_A} progress rows == {total}",
           await _progress_count(USER_A) == total)
    _check(f"user {USER_B} progress rows == {total}",
           await _progress_count(USER_B) == total)

    await _cleanup()
    print("\nCleaned up test progress/attempts.")
    print(f"\nRESULT: {_passes} passed, {_fails} failed")
    if _fails:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
