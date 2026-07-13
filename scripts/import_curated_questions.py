"""Import the curated Questions/ JSON tree into the question bank.

Replaces AI-generated content entirely: on every run this first deletes every
AI-generated question anywhere in the database (``created_by="ai"``, cascades
to its options + any user progress/attempts on those specific questions), then
for each (level, section, topic) bucket found in Questions/, deletes any prior
rows for that exact bucket and inserts the curated set fresh with
``status=STATUS_APPROVED`` (hand-curated content needs no AI review cycle) and
``created_by="curated_import"``.

Idempotent and safe to re-run after adding more curated JSON later — each
re-run just replaces the buckets it finds; sections with no JSON yet are left
untouched (they were already emptied by the very first run's AI purge and stay
empty until authored).

Usage::

    uv run python -m scripts.import_curated_questions
"""

from __future__ import annotations

import asyncio

from sqlalchemy import delete

from database.connection import get_db_session, init_db
from database.models import Question, QuestionOption
from scripts.curated_questions_loader import load_all
from services.question_service import STATUS_APPROVED

CREATED_BY = "curated_import"
_KEYS = ("A", "B", "C", "D")


def _build(entry: dict) -> Question:
    options = sorted(entry["options"], key=lambda o: o["key"])
    assert [o["key"] for o in options] == list(_KEYS), f"bad option keys: {options}"
    assert sum(1 for o in options if o["is_correct"]) == 1, "exactly one option must be correct"
    return Question(
        level=entry["level"],
        section=entry["section"],
        topic=entry["topic"],
        life_context=entry["life_context"],
        question_type=entry["question_type"],
        difficulty=entry["difficulty"],
        question_text_nl=entry["question_text_nl"],
        question_text_fa=entry["question_text_fa"],
        explanation_fa=entry["explanation_fa"],
        grammar_rule_fa=entry["grammar_rule_fa"],
        extra_example_nl=entry["extra_example_nl"],
        extra_example_fa=entry["extra_example_fa"],
        status=STATUS_APPROVED,
        created_by=CREATED_BY,
        reviewed_by=CREATED_BY,
        options=[
            QuestionOption(
                option_key=o["key"],
                option_text_nl=o["text"],
                is_correct=o["is_correct"],
                feedback_fa=o["feedback_fa"],
            )
            for o in options
        ],
    )


async def main() -> None:
    buckets, anomalies = load_all()
    populated = [b for b in buckets if b.questions]

    if anomalies:
        print(f"NOTE: {len(anomalies)} anomalies were skipped during load "
              f"(run `python -m scripts.audit_curated_questions` for details).")

    await init_db()
    async with get_db_session() as session:
        purged = await session.execute(delete(Question).where(Question.created_by == "ai"))
        print(f"Purged {purged.rowcount} AI-generated question(s) (created_by='ai').")

        total_inserted = 0
        for bucket in populated:
            removed = await session.execute(
                delete(Question).where(
                    Question.level == bucket.level,
                    Question.section == bucket.section,
                    Question.topic == bucket.topic,
                )
            )
            for q in bucket.questions:
                session.add(_build(q))
            total_inserted += len(bucket.questions)
            print(
                f"  {bucket.level}/{bucket.section}/{bucket.topic}: "
                f"removed {removed.rowcount}, inserted {len(bucket.questions)}"
            )
        await session.flush()

    print(f"\nDone. {len(populated)} buckets imported, {total_inserted} questions total.")


if __name__ == "__main__":
    asyncio.run(main())
