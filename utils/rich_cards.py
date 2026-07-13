"""Rich Markdown builders for the vocabulary (vajegan) cards.

Turns verb/word records into Telegram Rich Message Markdown (Bot API 10.1),
following telegram-bot-api-10.1-rich-messages.md. Each card uses a heading,
the meaning, optional chips, a Markdown table for principal parts when the data
has them, and a collapsible examples block.

`to_input()` wraps the Markdown as an ``InputRichMessage`` (RTL on). `to_plain()`
produces a degraded plain-text fallback for clients without rich support.
`edit_card()` does the edit-with-fallback dance shared by every caller.

The exam feature (`handlers/exam.py`) used to render its questions this way
too, but reverted to plain HTML text (2026-07-04): Telegram's mobile clients
currently mis-render mixed RTL(Persian)/LTR(Dutch) alignment in Rich Messages
- confirmed, still-open platform bug, bugs.telegram.org/c/62680. Every exam
question mixes the two languages, so the bug was unavoidable there. The same
risk applies to this module's tables (Persian labels + Dutch values) and
headings (a Dutch word as `# heading`), but hasn't been reported as an issue
here yet - keep it in mind if it ever is.
"""

from __future__ import annotations

import html as _html
import logging
import re

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InputRichMessage, Message

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def to_input(markdown: str) -> InputRichMessage:
    """Wrap Markdown as a right-to-left rich message."""
    return InputRichMessage(markdown=markdown, is_rtl=True)


async def edit_card(message: Message, markdown: str, reply_markup=None) -> None:
    """Edit a message in place with a rich card, falling back to plain text.

    Rich Markdown is the primary path; if Telegram rejects it (malformed markup
    or an unusually old client), degrade to a plain-text rendering rather than
    dropping the content. 'Message is not modified' is treated as a no-op.
    """
    try:
        await message.edit_text(rich_message=to_input(markdown), reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "not modified" in str(exc).lower():
            return
        logger.warning("Rich card edit failed, using plain fallback: %s", exc)
        await message.edit_text(to_plain(markdown), reply_markup=reply_markup)


def _clean(value: object) -> str:
    """Plain text from a possibly HTML-bearing DB value (worden stores HTML)."""
    text = re.sub(r"<br\s*/?>", " ", str(value), flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)  # drop any stray tags
    return _html.unescape(text).strip()


def _cell(value: object) -> str:
    """Escape a value for safe use inside a Markdown table cell."""
    return _clean(value).replace("|", "\\|").replace("\n", " ")


def _line(value: object) -> str:
    """Collapse a value to a single safe Markdown line."""
    return _clean(value).replace("\n", " ")


# ---------------------------------------------------------------------------
# Card assembly
# ---------------------------------------------------------------------------
def _header(position: str, word: str, meaning: str | None) -> list[str]:
    parts = [f"_{_line(position)}_", "", f"# {_line(word)}"]
    if meaning:
        parts.append(f"**{_line(meaning)}**")
    return parts


def _principal_table(rows: list[tuple[str, str]]) -> list[str]:
    """A two-column 'label | value' table for conjugation/principal parts."""
    out = ["", "## 🔑 صرف فعل", "", "| بخش | شکل |", "|:--|--:|"]
    out += [f"| {_cell(label)} | {_cell(value)} |" for label, value in rows]
    return out


def _examples_block(examples: list[tuple[str | None, str, str | None]]) -> list[str]:
    """A collapsible details block of example sentences (Dutch + Persian)."""
    if not examples:
        return []
    out = ["", "<details>", "<summary>💬 مثال‌ها</summary>", ""]
    for label, nl, fa in examples:
        prefix = f"_{_line(label)}:_ " if label else ""
        out.append(f"> {prefix}**{_line(nl)}**")
        if fa:
            out.append(f"> _{_line(fa)}_")
        out.append(">")
    if out[-1] == ">":
        out.pop()
    out += ["", "</details>"]
    return out


def _assemble(
    *,
    position: str,
    word: str,
    meaning: str | None,
    pron: str | None = None,
    structure: tuple[str, str] | None = None,
    meaning_en: str | None = None,
    conjugation: list[tuple[str, str]] | None = None,
    notes: list[str] | None = None,
    usage: list[str] | None = None,
    examples: list[tuple[str | None, str, str | None]] | None = None,
) -> str:
    parts = _header(position, word, meaning)

    chips: list[str] = []
    if pron:
        chips.append(f"🗣 _{_line(pron)}_")
    if structure:
        chips.append(f"`{_line(structure[0])}` + `{_line(structure[1])}`")
    if chips:
        parts += ["", " · ".join(chips)]
    if meaning_en:
        parts += ["", f"🇬🇧 _{_line(meaning_en)}_"]

    if conjugation:
        parts += _principal_table(conjugation)

    extra = [f"🗂 {_line(u)}" for u in (usage or [])]
    extra += [f"📝 {_line(n)}" for n in (notes or [])]
    if extra:
        parts += ["", *extra]

    parts += _examples_block(examples or [])
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Per-type cards (duck-typed on the service dataclasses)
# ---------------------------------------------------------------------------
def separable_card(v, *, index: int, total: int) -> str:
    examples: list[tuple[str | None, str, str | None]] = []
    if v.example_1_nl:
        examples.append((None, v.example_1_nl, v.example_1_fa))
    if v.example_2_nl:
        examples.append((None, v.example_2_nl, v.example_2_fa))
    notes = [v.usage_notes] if v.usage_notes else []
    usage = [v.usage_context] if v.usage_context else []
    return _assemble(
        position=f"{index + 1} از {total} — پیشوند «{v.particle}»",
        word=v.separable_verb,
        meaning=v.meaning_fa,
        pron=v.pronunciation_fa,
        structure=(v.particle, v.base_verb) if v.base_verb else None,
        meaning_en=v.meaning_en,
        notes=notes,
        usage=usage,
        examples=examples,
    )


def main_card(v, *, index: int, total: int, category_label: str) -> str:
    examples: list[tuple[str | None, str, str | None]] = []
    if v.example_1_nl:
        examples.append((None, v.example_1_nl, v.example_1_fa))
    if v.example_2_nl:
        examples.append((None, v.example_2_nl, v.example_2_fa))
    return _assemble(
        position=f"{index + 1} از {total} — {category_label}",
        word=v.verb,
        meaning=v.translation_fa,
        pron=v.pronunciation_fa,
        meaning_en=v.meaning_en,
        examples=examples,
    )


def principal_verb_card(v, *, index: int, total: int, kind: str) -> str:
    """Regular and irregular verbs share this shape (principal parts + examples)."""
    conj: list[tuple[str, str]] = [("infinitief", v.infinitive)]
    if v.simple_past:
        conj.append(("verleden tijd", v.simple_past))
    if v.past_participle:
        conj.append(("voltooid deelwoord", v.past_participle))

    examples: list[tuple[str | None, str, str | None]] = []
    for label, nl, fa in (
        ("حال", v.example_present_nl, v.example_present_fa),
        ("گذشته", v.example_past_nl, v.example_past_fa),
        ("ماضی نقلی", v.example_perfect_nl, v.example_perfect_fa),
    ):
        if nl:
            examples.append((label, nl, fa))

    return _assemble(
        position=f"{index + 1} از {total} — {kind}",
        word=v.infinitive,
        meaning=v.translation_fa,
        conjugation=conj if len(conj) > 1 else None,
        examples=examples,
    )


def worden_card(
    row, *, index: int, total: int, chapter_title: str, topic_label: str
) -> str:
    d = row.data
    head = d.get("dutch") or d.get("dutch_phrase") or d.get("dutch_pattern") or "—"
    meaning = d.get("persian_translation") or d.get("persian_meaning")

    notes: list[str] = []
    if d.get("common_mistake"):
        notes.append(f"❌ {d['common_mistake']}")
    if d.get("correct_form"):
        notes.append(f"✅ {d['correct_form']}")
    if d.get("explanation_in_persian"):
        notes.append(d["explanation_in_persian"])
    for col in (
        "additional_notes",
        "notes",
        "prefix_notes",
        "reflexive_pronoun_notes",
        "present_conjugation_notes",
    ):
        if d.get(col):
            notes.append(d[col])

    usage = [d[c] for c in ("usage_context", "when_to_use") if d.get(c)]

    conj: list[tuple[str, str]] | None = None
    if d.get("key_conjugations_past_sg_past_pl_participle"):
        conj = [("صرف کلیدی", d["key_conjugations_past_sg_past_pl_participle"])]

    examples: list[tuple[str | None, str, str | None]] = []
    for col in ("examples", "usage_examples"):
        if d.get(col):
            for piece in re.split(r"<br\s*/?>|\n", str(d[col])):
                piece = _clean(piece)
                if piece:
                    examples.append((None, piece, None))

    return _assemble(
        position=f"{index + 1} از {total} — {chapter_title} · {topic_label}",
        word=head,
        meaning=meaning,
        pron=d.get("pronunciation"),
        meaning_en=d.get("additional_meanings"),
        conjugation=conj,
        notes=notes,
        usage=usage,
        examples=examples,
    )


# ---------------------------------------------------------------------------
# Plain-text fallback (for clients without rich-message support)
# ---------------------------------------------------------------------------
def to_plain(markdown: str) -> str:
    """Degrade rich Markdown to readable plain text (HTML parse mode safe)."""
    lines: list[str] = []
    for raw in markdown.splitlines():
        line = raw.strip()
        if not line or line in {"---", "<details>", "</details>", ">"}:
            continue
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(set(c) <= {":", "-", " "} for c in cells):
                continue  # table separator row
            lines.append(" — ".join(c.replace("\\|", "|") for c in cells if c))
            continue
        line = re.sub(r"^#+\s*", "", line)
        line = line.replace("<summary>", "").replace("</summary>", "")
        line = line.lstrip("> ")
        line = line.replace("**", "").replace("==", "").replace("`", "")
        # Lookarounds keep runs of underscores (e.g. a "___" fill-in-the-blank
        # placeholder) intact instead of misreading two of them as italics.
        line = re.sub(r"(?<!_)_(?!_)(.+?)(?<!_)_(?!_)", r"\1", line)
        line = _html.escape(line, quote=False)
        if line.strip():
            lines.append(line)
    return "\n".join(lines)
