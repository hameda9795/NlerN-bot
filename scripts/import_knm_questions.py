"""Import the external KNM (inburgering) dataset into the question bank.

Deliberately separate from ``import_curated_questions.py``: that script owns the
``Questions/`` tree and *purges* rows (every ``created_by='ai'`` question, plus
whole level/section/topic buckets). This one only ever touches its own bucket —
``section='knm'`` AND ``created_by='knm_import'`` — so re-running it can never
disturb curated or AI content.

The source schema differs from the bank's:

* items carry 3 options (``o1``/``o2``/``o3``), not 4 — nothing in the model or
  the exam UI requires 4, both iterate whatever options a question has;
* items carry no level/section/topic, so they are filed under a fixed bucket;
* stems are Dutch-only, so ``question_text_fa`` stays empty (the explanation and
  the per-option feedback are fully Persian).

**Option order is shuffled on purpose.** The dataset marks every item
``shuffle_options: true`` and its correct answer is ``o1`` in 150 of 234 items;
NLern never shuffles at serve time (options render in ``option_key`` order), so
a straight o1->A mapping would make "A" correct 64% of the time. The shuffle is
seeded from ``item_id``, so re-running the import reproduces the same order.

Usage::

    uv run python -m scripts.import_knm_questions path/to/KNM-Full234.json
    uv run python -m scripts.import_knm_questions path/to/file.json --dry-run
    uv run python -m scripts.import_knm_questions path/to/file.json --status approved
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, select

from database.connection import get_db_session, init_db
from database.models import (
    Question,
    QuestionOption,
    UserQuestionAttempt,
    UserQuestionProgress,
)
from services.question_service import STATUS_APPROVED, STATUS_DRAFT

LEVEL = "A2"
SECTION = "knm"
CREATED_BY = "knm_import"
QUESTION_TYPE = "mcq_3"
OPTION_KEYS = ("A", "B", "C", "D")
_DIFFICULTY = {"easy": 1, "medium": 3, "hard": 4}


class KnmImportError(RuntimeError):
    """Raised when the source file cannot be imported safely."""


def _stem(item: dict[str, Any]) -> str:
    return (item["content"]["stem"].get("nl-NL") or "").strip()


def _key_terms_fa(item: dict[str, Any]) -> str | None:
    """Render the Persian key-term glossary, kept for a future UI that shows it."""
    terms = item["explanations"]["fa"].get("key_terms") or []
    rendered = " · ".join(
        f"{t['term_nl']}: {t['meaning']}" for t in terms if t.get("term_nl")
    )
    return rendered or None


def _validate(items: list[dict[str, Any]]) -> list[str]:
    """Return every problem found; the import aborts unless this is empty."""
    problems: list[str] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(items):
        item_id = item.get("item_id") or f"<index {index}>"
        if item_id in seen_ids:
            problems.append(f"{item_id}: duplicate item_id")
        seen_ids.add(item_id)

        content = item.get("content") or {}
        options = content.get("options") or []
        if not _stem(item):
            problems.append(f"{item_id}: empty nl-NL stem")
        if not 2 <= len(options) <= len(OPTION_KEYS):
            problems.append(f"{item_id}: {len(options)} options (need 2..{len(OPTION_KEYS)})")
        option_ids = [o.get("id") for o in options]
        if len(set(option_ids)) != len(option_ids):
            problems.append(f"{item_id}: duplicate option ids {option_ids}")
        if content.get("correct_option_id") not in option_ids:
            problems.append(
                f"{item_id}: correct_option_id {content.get('correct_option_id')!r} "
                f"is not one of {option_ids}"
            )
        for option in options:
            if not (option.get("text", {}).get("nl-NL") or "").strip():
                problems.append(f"{item_id}: option {option.get('id')} has no nl-NL text")

        fa = (item.get("explanations") or {}).get("fa") or {}
        if not (fa.get("why_correct") or "").strip():
            problems.append(f"{item_id}: missing Persian why_correct")
        feedback = fa.get("option_feedback") or {}
        missing = [o for o in option_ids if not (feedback.get(o) or "").strip()]
        if missing:
            problems.append(f"{item_id}: missing Persian feedback for {missing}")

        if not (item.get("alignment") or {}).get("theme_id"):
            problems.append(f"{item_id}: missing alignment.theme_id")
    return problems


def _build(item: dict[str, Any], *, dataset_id: str, status: str) -> Question:
    """Map one source item onto a Question with deterministically shuffled options."""
    content = item["content"]
    alignment = item["alignment"]
    fa = item["explanations"]["fa"]

    options = list(content["options"])
    # Seeded by item_id so every run produces the identical option order.
    random.Random(item["item_id"]).shuffle(options)

    correct_id = content["correct_option_id"]
    provenance = {
        "knm_item_id": item["item_id"],
        "dataset_id": dataset_id,
        "revision": item.get("revision"),
        "source_status": item.get("status"),
        "theme_id": alignment.get("theme_id"),
        "section_id": alignment.get("section_id"),
        "eindterm_id": alignment.get("eindterm_id"),
        "indicator_id": alignment.get("indicator_id"),
        "fact_id": alignment.get("fact_id"),
        "source_option_order": [o["id"] for o in content["options"]],
        "shuffled_option_order": [o["id"] for o in options],
    }

    return Question(
        level=LEVEL,
        section=SECTION,
        topic=f"thema_{alignment['theme_id']}",
        life_context=alignment.get("eindterm_id"),
        question_type=QUESTION_TYPE,
        difficulty=_DIFFICULTY.get(
            (item.get("difficulty") or {}).get("intended_level", ""), 3
        ),
        question_text_nl=_stem(item),
        question_text_fa=None,  # the source carries no Persian stem
        explanation_fa=fa["why_correct"].strip(),
        grammar_rule_fa=_key_terms_fa(item),
        status=status,
        created_by=CREATED_BY,
        reviewed_by=CREATED_BY,
        review_issues_json=json.dumps(provenance, ensure_ascii=False),
        options=[
            QuestionOption(
                option_key=OPTION_KEYS[position],
                option_text_nl=option["text"]["nl-NL"].strip(),
                is_correct=option["id"] == correct_id,
                feedback_fa=(fa["option_feedback"].get(option["id"]) or "").strip() or None,
            )
            for position, option in enumerate(options)
        ],
    )


def load_items(path: Path) -> tuple[list[dict[str, Any]], str]:
    """Read the dataset file and return its items plus the dataset id."""
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("items")
    if not isinstance(items, list) or not items:
        raise KnmImportError(f"{path} has no 'items' list.")
    declared = (data.get("metadata") or {}).get("item_count")
    if declared is not None and declared != len(items):
        raise KnmImportError(
            f"metadata.item_count={declared} but the file holds {len(items)} items."
        )
    return items, str(data.get("dataset_id") or path.stem)


async def import_knm(
    *, path: Path, status: str = STATUS_DRAFT, dry_run: bool = False
) -> int:
    """Replace the KNM bucket with the file's contents. Returns rows inserted."""
    items, dataset_id = load_items(path)
    problems = _validate(items)
    if problems:
        shown = "\n  ".join(problems[:20])
        raise KnmImportError(
            f"{len(problems)} problem(s) found; nothing was written:\n  {shown}"
        )

    questions = [_build(item, dataset_id=dataset_id, status=status) for item in items]
    correct_spread: dict[str, int] = {}
    for question in questions:
        key = next(o.option_key for o in question.options if o.is_correct)
        correct_spread[key] = correct_spread.get(key, 0) + 1

    print(f"Dataset : {dataset_id}")
    print(f"Items   : {len(questions)} -> {LEVEL}/{SECTION}, status={status}")
    print(f"Answers : {dict(sorted(correct_spread.items()))}")

    if dry_run:
        print("\nDry run — no database changes were made.")
        return 0

    await init_db()
    async with get_db_session() as session:
        mine = select(Question.id).where(
            Question.section == SECTION, Question.created_by == CREATED_BY
        )
        existing = await session.scalar(
            select(func.count()).select_from(mine.subquery())
        )
        # Delete children explicitly instead of relying on ON DELETE CASCADE:
        # SQLite leaves foreign keys off by default, which would strand the old
        # option rows and collide with a reused question id on the next insert.
        for child in (UserQuestionAttempt, UserQuestionProgress, QuestionOption):
            await session.execute(
                delete(child).where(child.question_id.in_(mine))
            )
        removed = await session.execute(
            delete(Question).where(
                Question.section == SECTION, Question.created_by == CREATED_BY
            )
        )
        # Never let a mismatch here silently widen the delete beyond our bucket.
        if removed.rowcount != existing:
            raise KnmImportError(
                f"Delete touched {removed.rowcount} rows but only {existing} were "
                "expected; transaction rolled back."
            )
        session.add_all(questions)
        await session.flush()

    print(f"\nDone. Replaced {removed.rowcount} previous KNM row(s) with {len(questions)}.")
    return len(questions)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Path to the KNM dataset JSON file.")
    parser.add_argument(
        "--status",
        choices=(STATUS_DRAFT, STATUS_APPROVED),
        default=STATUS_DRAFT,
        help="Row status to import with (default: draft — never served to users).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and report without writing anything.",
    )
    args = parser.parse_args()
    asyncio.run(import_knm(path=args.path, status=args.status, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
