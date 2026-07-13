"""Seed 10 approved A2 / grammar / zijn_hebben questions for flow testing.

Manual fixtures only — no AI. Each question has exactly 4 options (A-D), exactly
one correct, a Persian explanation, and per-option Persian feedback. Re-running
is idempotent: it removes any previous seed for this exact bucket first (which
cascades to options + any user progress/attempts on them), then inserts a fresh 10.

Usage::

    uv run python -m scripts.seed_zijn_hebben
"""

from __future__ import annotations

import asyncio

from sqlalchemy import delete

from database.connection import get_db_session, init_db
from database.models import Question, QuestionOption
from services.question_service import STATUS_APPROVED

LEVEL, SECTION, TOPIC = "A2", "grammar", "zijn_hebben"

# Author identity for these manual fixtures (also used to find+replace on reseed).
_CREATED_BY = "manual_seed"
# Older throwaway fixture from phase 1 we also clear so the bucket holds exactly 10.
_OLD_SEED = "seed_sample"

# Each entry: prompt (NL with a ___ blank), Persian hint, Persian rule explanation,
# and 4 options as (text_nl, is_correct, feedback_fa). Order here becomes A,B,C,D.
_QUESTIONS: list[dict] = [
    {
        "nl": "Ik ___ ziek.",
        "fa": "کدام شکل درست فعل است؟",
        "explanation": "با ضمیر «ik» از «ben» (شکل فعل zijn) استفاده می‌شود.",
        "options": [
            ("ben", True, "✅ درست! «ik ben» یعنی «من هستم»."),
            ("is", False, "«is» برای سوم‌شخص مفرد (hij/zij/het) است."),
            ("zijn", False, "«zijn» برای جمع (wij/jullie/zij) است."),
            ("bent", False, "«bent» برای «jij/u» است."),
        ],
    },
    {
        "nl": "Ik ___ een afspraak.",
        "fa": "کدام شکل درست فعل است؟",
        "explanation": "با ضمیر «ik» از «heb» (شکل فعل hebben) استفاده می‌شود.",
        "options": [
            ("hebt", False, "«hebt» برای «jij» است."),
            ("heb", True, "✅ درست! «ik heb» یعنی «من دارم»."),
            ("heeft", False, "«heeft» برای سوم‌شخص مفرد است."),
            ("hebben", False, "«hebben» برای جمع است."),
        ],
    },
    {
        "nl": "Zij ___ mijn docent.",
        "fa": "کدام شکل درست فعل است؟ (zij = او، مفرد)",
        "explanation": "برای سوم‌شخص مفرد «zij» (او) از «is» استفاده می‌شود.",
        "options": [
            ("ben", False, "«ben» فقط برای «ik» است."),
            ("bent", False, "«bent» برای «jij/u» است."),
            ("is", True, "✅ درست! «zij is» یعنی «او هست»."),
            ("zijn", False, "«zijn» برای جمع است، نه مفرد."),
        ],
    },
    {
        "nl": "Wij ___ huiswerk.",
        "fa": "کدام شکل درست فعل است؟",
        "explanation": "با ضمیر جمع «wij» از «hebben» استفاده می‌شود.",
        "options": [
            ("heb", False, "«heb» برای «ik» است."),
            ("heeft", False, "«heeft» برای سوم‌شخص مفرد است."),
            ("hebt", False, "«hebt» برای «jij» است."),
            ("hebben", True, "✅ درست! «wij hebben» یعنی «ما داریم»."),
        ],
    },
    {
        "nl": "Het ___ koud vandaag.",
        "fa": "کدام شکل درست فعل است؟ (het = آن)",
        "explanation": "برای «het» (سوم‌شخص مفرد) از «is» استفاده می‌شود.",
        "options": [
            ("is", True, "✅ درست! «het is» یعنی «آن هست»."),
            ("ben", False, "«ben» فقط برای «ik» است."),
            ("zijn", False, "«zijn» برای جمع است."),
            ("bent", False, "«bent» برای «jij/u» است."),
        ],
    },
    {
        "nl": "Mijn zoon ___ koorts.",
        "fa": "کدام شکل درست فعل است؟ (پسرِ من = سوم‌شخص مفرد)",
        "explanation": "فاعل سوم‌شخص مفرد است، پس از «heeft» استفاده می‌شود.",
        "options": [
            ("heb", False, "«heb» برای «ik» است."),
            ("hebt", False, "«hebt» برای «jij» است."),
            ("hebben", False, "«hebben» برای جمع است."),
            ("heeft", True, "✅ درست! «hij/zij heeft» یعنی «او دارد»."),
        ],
    },
    {
        "nl": "De winkel ___ open.",
        "fa": "کدام شکل درست فعل است؟ (مغازه = سوم‌شخص مفرد)",
        "explanation": "فاعل سوم‌شخص مفرد است، پس از «is» استفاده می‌شود.",
        "options": [
            ("ben", False, "«ben» فقط برای «ik» است."),
            ("is", True, "✅ درست! «de winkel is open» یعنی «مغازه باز است»."),
            ("bent", False, "«bent» برای «jij/u» است."),
            ("zijn", False, "«zijn» برای جمع است."),
        ],
    },
    {
        "nl": "Mijn buren ___ aardig.",
        "fa": "کدام شکل درست فعل است؟ (همسایه‌ها = جمع)",
        "explanation": "فاعل جمع است (buren = همسایه‌ها)، پس از «zijn» استفاده می‌شود.",
        "options": [
            ("is", False, "«is» برای مفرد است، نه جمع."),
            ("ben", False, "«ben» فقط برای «ik» است."),
            ("zijn", True, "✅ درست! «zij zijn» یعنی «آن‌ها هستند»."),
            ("bent", False, "«bent» برای «jij/u» است."),
        ],
    },
    {
        "nl": "Jij ___ een nieuwe fiets.",
        "fa": "کدام شکل درست فعل است؟ (jij = تو)",
        "explanation": "با ضمیر «jij» از «hebt» استفاده می‌شود.",
        "options": [
            ("heb", False, "«heb» برای «ik» است."),
            ("hebt", True, "✅ درست! «jij hebt» یعنی «تو داری»."),
            ("heeft", False, "«heeft» برای سوم‌شخص مفرد است."),
            ("hebben", False, "«hebben» برای جمع است."),
        ],
    },
    {
        "nl": "Jullie ___ vrienden.",
        "fa": "کدام شکل درست فعل است؟ (jullie = شما، جمع)",
        "explanation": "با ضمیر جمع «jullie» از «zijn» استفاده می‌شود.",
        "options": [
            ("is", False, "«is» برای مفرد است."),
            ("ben", False, "«ben» فقط برای «ik» است."),
            ("bent", False, "«bent» برای «jij/u» مفرد است."),
            ("zijn", True, "✅ درست! «jullie zijn» یعنی «شما هستید»."),
        ],
    },
]

_KEYS = ("A", "B", "C", "D")


def _build(entry: dict) -> Question:
    options = entry["options"]
    assert len(options) == 4, "each question needs exactly 4 options"
    assert sum(1 for _, ok, _ in options if ok) == 1, "exactly one option must be correct"
    return Question(
        level=LEVEL, section=SECTION, topic=TOPIC,
        question_type="mcq_4", difficulty=1,
        question_text_nl=entry["nl"],
        question_text_fa=entry["fa"],
        explanation_fa=entry["explanation"],
        grammar_rule_fa="فعل‌های «zijn» و «hebben» بسته به فاعل صرف می‌شوند.",
        status=STATUS_APPROVED,
        quality_score=9.0,
        created_by=_CREATED_BY,
        reviewed_by=_CREATED_BY,
        options=[
            QuestionOption(
                option_key=_KEYS[i],
                option_text_nl=text,
                is_correct=is_correct,
                feedback_fa=feedback,
            )
            for i, (text, is_correct, feedback) in enumerate(options)
        ],
    )


async def main() -> None:
    await init_db()  # ensure tables exist (idempotent)
    async with get_db_session() as session:
        # Idempotent reseed: clear prior fixtures for this bucket (cascades to
        # options + any user progress/attempts) so we always end with exactly 10.
        removed = await session.execute(
            delete(Question).where(
                Question.level == LEVEL,
                Question.section == SECTION,
                Question.topic == TOPIC,
                Question.created_by.in_((_CREATED_BY, _OLD_SEED)),
            )
        )
        for entry in _QUESTIONS:
            session.add(_build(entry))
        await session.flush()
    print(f"Removed {removed.rowcount} old fixture(s); inserted {len(_QUESTIONS)} "
          f"approved questions for {LEVEL}/{SECTION}/{TOPIC}.")


if __name__ == "__main__":
    asyncio.run(main())
