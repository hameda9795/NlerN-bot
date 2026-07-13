"""Load and normalize the curated Questions/ JSON tree.

Shared by ``audit_curated_questions.py`` (read-only report) and
``import_curated_questions.py`` (writes to the DB) so both use the exact same
parsing/normalization rules and never drift apart.

Layout: ``Questions/<LEVEL>/<section>/<topic>/*.json``. Each topic folder may
contain a 0-byte placeholder (not yet authored), one real content file, or
(rarely) a real file plus a corrupt/duplicate one — handled below.

Different sections use different field names for the same concepts (a dialogue
snippet, an erroneous sentence, a writing task, a rule explanation). None of
that requires new DB columns: everything folds losslessly onto the existing
``Question``/``QuestionOption`` schema (see the plan this script implements).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

QUESTIONS_ROOT = Path(__file__).resolve().parent.parent / "Questions"
LEVELS = ("A2", "B1", "B2")
VALID_KEYS = ("A", "B", "C", "D")


@dataclass
class Anomaly:
    path: str
    reason: str


@dataclass
class BucketResult:
    level: str
    section: str
    topic: str
    questions: list[dict] = field(default_factory=list)
    source_file: str | None = None


def _normalize_question(
    raw: dict, level: str, section: str, topic: str, source_file: Path, anomalies: list[Anomaly]
) -> dict | None:
    for key, expected in (("level", level), ("section", section), ("topic", topic)):
        if key in raw and raw[key] != expected:
            anomalies.append(
                Anomaly(str(source_file), f"internal {key}={raw[key]!r} != folder path {expected!r}")
            )
            return None

    options = raw.get("options")
    if not isinstance(options, list) or len(options) != 4:
        got = len(options) if isinstance(options, list) else type(options).__name__
        anomalies.append(Anomaly(str(source_file), f"expected exactly 4 options, got {got}"))
        return None
    correct_count = sum(1 for o in options if o.get("is_correct"))
    if correct_count != 1:
        anomalies.append(Anomaly(str(source_file), f"expected exactly 1 correct option, got {correct_count}"))
        return None
    keys = sorted(o.get("key", "") for o in options)
    if keys != sorted(VALID_KEYS):
        anomalies.append(Anomaly(str(source_file), f"option keys {keys} != {sorted(VALID_KEYS)}"))
        return None

    question_text_nl = raw.get("question_text_nl") or ""
    question_text_fa = raw.get("question_text_fa")
    explanation_fa = raw.get("explanation_fa")
    grammar_rule_fa = raw.get("grammar_rule_fa")

    # Section-specific "content the user must read" fields -> prepended to the
    # NL question text (these are not optional decoration, unlike grammar_rule_fa).
    context_nl = (
        raw.get("dialogue_context_nl")
        or raw.get("sentence_with_error_nl")
        or raw.get("sentence_nl")
    )
    if context_nl:
        question_text_nl = f"{context_nl}\n\n{question_text_nl}" if question_text_nl else context_nl

    # writing task instructions (Farsi) -> prepended to the FA question text.
    task_fa = raw.get("writing_task_fa")
    if task_fa:
        question_text_fa = f"{task_fa}\n\n{question_text_fa}" if question_text_fa else task_fa

    # section-specific "rule" fields -> the one generic rule column.
    rule_fa = (
        grammar_rule_fa
        or raw.get("dialogue_rule_fa")
        or raw.get("correction_rule_fa")
        or raw.get("usage_note_fa")
    )

    # meaning-section records describe the meaning instead of an explanation.
    if not explanation_fa:
        explanation_fa = raw.get("meaning_fa")

    norm_options = []
    for o in options:
        # meaning-section options carry text_fa (a Persian meaning) instead of
        # text_nl; stored as-is into option_text_nl (column name is legacy,
        # nothing enforces language at the DB level).
        text = o.get("text_nl")
        if text is None:
            text = o.get("text_fa", "")
        norm_options.append(
            {
                "key": o["key"],
                "text": text,
                "is_correct": bool(o.get("is_correct")),
                "feedback_fa": o.get("feedback_fa"),
            }
        )

    return {
        "level": level,
        "section": section,
        "topic": topic,
        "life_context": raw.get("life_context"),
        "question_type": raw.get("question_type") or "mcq_4",
        "difficulty": raw.get("difficulty") or 1,
        "question_text_nl": question_text_nl,
        "question_text_fa": question_text_fa,
        "explanation_fa": explanation_fa,
        "grammar_rule_fa": rule_fa,
        "extra_example_nl": raw.get("extra_example_nl"),
        "extra_example_fa": raw.get("extra_example_fa"),
        "options": norm_options,
    }


def _load_topic_folder(
    level: str, section: str, topic: str, folder: Path, anomalies: list[Anomaly]
) -> BucketResult:
    import json

    result = BucketResult(level=level, section=section, topic=topic)
    candidates: list[tuple[Path, list]] = []
    for f in sorted(folder.glob("*.json")):
        if f.stat().st_size <= 2:
            continue  # empty placeholder - not yet authored
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            anomalies.append(Anomaly(str(f), f"invalid JSON, skipped: {exc}"))
            continue
        if not isinstance(data, list) or not data:
            anomalies.append(Anomaly(str(f), "expected a non-empty JSON array, skipped"))
            continue
        candidates.append((f, data))

    if not candidates:
        return result

    if len(candidates) > 1:
        # Prefer a specifically-named file over the generic "question.json"
        # placeholder name (that name is also where corrupt duplicates have
        # been found sitting next to a real, properly-named file).
        named = [c for c in candidates if c[0].name != "question.json"]
        pool = named if named else candidates
        chosen = max(pool, key=lambda c: len(c[1]))
        for f, _ in candidates:
            if f != chosen[0]:
                anomalies.append(
                    Anomaly(str(f), f"multiple valid JSON files in this folder; used {chosen[0].name} instead")
                )
    else:
        chosen = candidates[0]

    source_file, raw_list = chosen
    result.source_file = str(source_file)
    for raw in raw_list:
        norm = _normalize_question(raw, level, section, topic, source_file, anomalies)
        if norm is not None:
            result.questions.append(norm)
    return result


def load_all(root: Path = QUESTIONS_ROOT) -> tuple[list[BucketResult], list[Anomaly]]:
    """Walk the curated Questions/ tree and return (buckets, anomalies)."""
    anomalies: list[Anomaly] = []
    buckets: list[BucketResult] = []
    for level in LEVELS:
        level_dir = root / level
        if not level_dir.is_dir():
            continue
        for section_dir in sorted(p for p in level_dir.iterdir() if p.is_dir()):
            for topic_dir in sorted(p for p in section_dir.iterdir() if p.is_dir()):
                buckets.append(
                    _load_topic_folder(level, section_dir.name, topic_dir.name, topic_dir, anomalies)
                )
    return buckets, anomalies


def summarize(buckets: list[BucketResult]) -> dict[tuple[str, str], dict[str, int]]:
    """Per (level, section): topics with content, topics still empty, total questions."""
    by_ls: dict[tuple[str, str], dict[str, int]] = defaultdict(
        lambda: {"topics_ok": 0, "topics_empty": 0, "questions": 0}
    )
    for b in buckets:
        key = (b.level, b.section)
        if b.questions:
            by_ls[key]["topics_ok"] += 1
            by_ls[key]["questions"] += len(b.questions)
        else:
            by_ls[key]["topics_empty"] += 1
    return dict(by_ls)
