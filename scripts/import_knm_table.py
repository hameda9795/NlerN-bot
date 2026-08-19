"""Import the KNM dataset into the standalone ``knm`` table.

Unlike ``import_knm_questions.py`` (which files the items into the shared
question bank so the exam can one day serve them), this keeps the dataset in
its own table with the source's own shape: options in their original order and
**both** the Persian and English explanation sets.

Rows are matched on the source ``item_id``, so re-running updates in place and
never duplicates. Nothing outside the ``knm`` table is touched.

Usage::

    uv run python -m scripts.import_knm_table path/to/KNM-Full234.json
    uv run python -m scripts.import_knm_table path/to/file.json --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import Any

from sqlalchemy import select

from database.connection import get_db_session, init_db
from database.models import KnmQuestion
from scripts.import_knm_questions import (
    OPTION_KEYS,
    KnmImportError,
    _stem,
    _validate,
    load_items,
)


def _key_terms(item: dict[str, Any]) -> list[dict[str, str]]:
    """Zip the Persian and English glossaries into one bilingual list."""
    fa_terms = (item["explanations"].get("fa") or {}).get("key_terms") or []
    en_by_term = {
        term.get("term_nl"): term.get("meaning")
        for term in ((item["explanations"].get("en") or {}).get("key_terms") or [])
    }
    return [
        {
            "term_nl": term.get("term_nl"),
            "meaning_fa": term.get("meaning"),
            "meaning_en": en_by_term.get(term.get("term_nl")),
        }
        for term in fa_terms
    ]


def _fields(item: dict[str, Any], *, dataset_id: str) -> dict[str, Any]:
    """Map one source item onto the ``knm`` table's columns."""
    content = item["content"]
    alignment = item["alignment"]
    fa = item["explanations"].get("fa") or {}
    en = item["explanations"].get("en") or {}
    fa_feedback = fa.get("option_feedback") or {}
    en_feedback = en.get("option_feedback") or {}
    correct_id = content["correct_option_id"]

    # Source order is preserved here on purpose: this table is the archive, and
    # the serving copy in ``questions`` is the one that gets shuffled.
    options = [
        {
            "key": OPTION_KEYS[position],
            "source_id": option["id"],
            "text_nl": option["text"]["nl-NL"].strip(),
            "is_correct": option["id"] == correct_id,
            "feedback_fa": (fa_feedback.get(option["id"]) or "").strip() or None,
            "feedback_en": (en_feedback.get(option["id"]) or "").strip() or None,
        }
        for position, option in enumerate(content["options"])
    ]

    return {
        "item_id": item["item_id"],
        "dataset_id": dataset_id,
        "revision": item.get("revision"),
        "source_status": item.get("status"),
        "theme_id": alignment.get("theme_id"),
        "section_id": alignment.get("section_id"),
        "eindterm_id": alignment.get("eindterm_id"),
        "indicator_id": alignment.get("indicator_id"),
        "fact_id": alignment.get("fact_id"),
        "knowledge_type": alignment.get("knowledge_type"),
        "item_type": content.get("item_type"),
        "difficulty_level": (item.get("difficulty") or {}).get("intended_level"),
        "cefr_target": (item.get("language") or {}).get("cefr_target"),
        "question_text_nl": _stem(item),
        "options_json": options,
        "correct_option_key": next(o["key"] for o in options if o["is_correct"]),
        "explanation_fa": (fa.get("why_correct") or "").strip() or None,
        "explanation_en": (en.get("why_correct") or "").strip() or None,
        "key_terms_json": _key_terms(item) or None,
    }


async def import_knm_table(*, path: Path, dry_run: bool = False) -> tuple[int, int]:
    """Upsert every item into the ``knm`` table. Returns (inserted, updated)."""
    items, dataset_id = load_items(path)
    problems = _validate(items)
    if problems:
        shown = "\n  ".join(problems[:20])
        raise KnmImportError(
            f"{len(problems)} problem(s) found; nothing was written:\n  {shown}"
        )

    rows = [_fields(item, dataset_id=dataset_id) for item in items]
    missing_en = sum(1 for r in rows if not r["explanation_en"])

    print(f"Dataset      : {dataset_id}")
    print(f"Items        : {len(rows)} -> table 'knm'")
    print(f"English text : {len(rows) - missing_en}/{len(rows)} items have an English explanation")

    if dry_run:
        print("\nDry run — no database changes were made.")
        return (0, 0)

    await init_db()
    inserted = updated = 0
    async with get_db_session() as session:
        existing = {
            row.item_id: row
            for row in await session.scalars(
                select(KnmQuestion).where(
                    KnmQuestion.item_id.in_([r["item_id"] for r in rows])
                )
            )
        }
        for fields in rows:
            current = existing.get(fields["item_id"])
            if current is None:
                session.add(KnmQuestion(**fields))
                inserted += 1
            else:
                for column, value in fields.items():
                    setattr(current, column, value)
                updated += 1
        await session.flush()

    print(f"\nDone. Inserted {inserted}, updated {updated}.")
    return (inserted, updated)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Path to the KNM dataset JSON file.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and report without writing anything.",
    )
    args = parser.parse_args()
    asyncio.run(import_knm_table(path=args.path, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
