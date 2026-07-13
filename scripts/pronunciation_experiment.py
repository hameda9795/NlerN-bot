"""Experimental harness: check whether a user said a Dutch sentence correctly.

Goal of this experiment: validate that Deepgram Nova-3 (Dutch) is good enough
to verify *did the user say the right sentence* (not phonetic quality). It
transcribes an audio clip, then aligns the transcript word-by-word against a
target sentence pulled from the bot database and reports an accuracy verdict.

This is a standalone dev script, separate from the bot — nothing here touches
the running handlers. It speaks to Deepgram's REST API directly via httpx, so
no extra SDK is needed.

Setup:
    Add your key to .env:   DEEPGRAM_API_KEY=...

Usage:
    # 1) See which sample sentences are available
    uv run python scripts/pronunciation_experiment.py --list

    # 2) End-to-end smoke test WITHOUT a microphone: synthesize each sentence
    #    with OpenAI TTS, send it through Deepgram, and score it. This proves
    #    the pipeline works (a perfect TTS voice should score ~100%).
    uv run python scripts/pronunciation_experiment.py --smoke -n 5

    # 3) Test a REAL recording (ogg/mp3/wav/m4a) against a DB sentence by id
    uv run python scripts/pronunciation_experiment.py --audio my_voice.ogg --sentence-id 1

    # 4) Test a real recording against any target text
    uv run python scripts/pronunciation_experiment.py --audio my_voice.ogg --target "Hallo, hoe gaat het?"
"""

from __future__ import annotations

import argparse
import asyncio
import difflib
import sqlite3
import string
import sys
from pathlib import Path

import httpx

# Allow running as a plain script (add project root to sys.path).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DEEPGRAM_URL = "https://api.deepgram.com/v1/listen"
DEEPGRAM_MODEL = "nova-3"
DEEPGRAM_LANGUAGE = "nl"

# How much of the target must be matched for a "correct" verdict, and the
# per-word confidence below which we flag a word as "said unclearly".
PASS_THRESHOLD = 0.85
LOW_CONFIDENCE = 0.60

DB_PATH = Path(__file__).resolve().parent.parent / "bot.db"

# Content types per extension so Deepgram decodes the audio correctly.
_CONTENT_TYPES = {
    ".ogg": "audio/ogg",
    ".oga": "audio/ogg",
    ".opus": "audio/ogg",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".mp4": "audio/mp4",
    ".flac": "audio/flac",
}


def _load_deepgram_key() -> str:
    """Read DEEPGRAM_API_KEY from the environment or the .env file."""
    import os

    key = os.getenv("DEEPGRAM_API_KEY", "").strip()
    if key:
        return key
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("DEEPGRAM_API_KEY") and "=" in line:
                return line.partition("=")[2].strip().strip('"').strip("'")
    return ""


# --------------------------------------------------------------------------- #
# Database access                                                             #
# --------------------------------------------------------------------------- #
def get_sample_sentences(limit: int | None = None) -> list[tuple[int, str, str]]:
    """Return (id, dutch_word, sentence) for words that have an example."""
    con = sqlite3.connect(DB_PATH)
    try:
        rows = con.execute(
            "SELECT id, dutch_word, example_sentence_dutch FROM words "
            "WHERE example_sentence_dutch IS NOT NULL AND example_sentence_dutch != '' "
            "ORDER BY id"
        ).fetchall()
    finally:
        con.close()
    if limit is not None:
        rows = rows[:limit]
    return [(r[0], r[1], r[2]) for r in rows]


def get_sentence_by_id(word_id: int) -> str | None:
    con = sqlite3.connect(DB_PATH)
    try:
        row = con.execute(
            "SELECT example_sentence_dutch FROM words WHERE id = ?", (word_id,)
        ).fetchone()
    finally:
        con.close()
    return row[0] if row else None


# --------------------------------------------------------------------------- #
# Deepgram transcription                                                      #
# --------------------------------------------------------------------------- #
async def transcribe(audio: bytes, content_type: str) -> dict[str, object]:
    """Send audio to Deepgram Nova-3 (Dutch) and return transcript + words.

    Returns a dict: {"transcript": str, "words": [{word, confidence}, ...],
    "overall_confidence": float}.
    """
    key = _load_deepgram_key()
    if not key:
        raise RuntimeError(
            "DEEPGRAM_API_KEY not found. Add it to .env or export it."
        )
    params = {
        "model": DEEPGRAM_MODEL,
        "language": DEEPGRAM_LANGUAGE,
        "punctuate": "true",
        "smart_format": "true",
    }
    headers = {"Authorization": f"Token {key}", "Content-Type": content_type}
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            DEEPGRAM_URL, params=params, headers=headers, content=audio
        )
    resp.raise_for_status()
    data = resp.json()
    alt = data["results"]["channels"][0]["alternatives"][0]
    words = [
        {"word": w.get("word", ""), "confidence": float(w.get("confidence", 0.0))}
        for w in alt.get("words", [])
    ]
    return {
        "transcript": alt.get("transcript", "").strip(),
        "words": words,
        "overall_confidence": float(alt.get("confidence", 0.0)),
    }


# --------------------------------------------------------------------------- #
# OpenAI TTS (only for --smoke mode)                                          #
# --------------------------------------------------------------------------- #
async def synth_tts(text: str) -> bytes:
    """Synthesize ``text`` with OpenAI TTS so we can test without a mic."""
    from services.pronunciation_service import generate_target_audio

    audio, _cost = await generate_target_audio(text)
    return audio


# --------------------------------------------------------------------------- #
# Word-level comparison                                                       #
# --------------------------------------------------------------------------- #
def _tokenize(text: str) -> list[str]:
    table = str.maketrans("", "", string.punctuation + "¿¡«»…")
    return [t for t in text.lower().translate(table).split() if t]


def compare(target: str, heard: str) -> dict[str, object]:
    """Align target vs. heard word lists and produce an accuracy verdict."""
    t_words = _tokenize(target)
    h_words = _tokenize(heard)
    sm = difflib.SequenceMatcher(None, t_words, h_words)

    matched: list[str] = []
    missing: list[str] = []  # in target, not said
    wrong: list[tuple[str, str]] = []  # said something else
    extra: list[str] = []  # said but not in target

    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            matched.extend(t_words[i1:i2])
        elif op == "delete":
            missing.extend(t_words[i1:i2])
        elif op == "insert":
            extra.extend(h_words[j1:j2])
        elif op == "replace":
            for k in range(max(i2 - i1, j2 - j1)):
                tw = t_words[i1 + k] if i1 + k < i2 else "—"
                hw = h_words[j1 + k] if j1 + k < j2 else "—"
                wrong.append((tw, hw))

    total = len(t_words) or 1
    accuracy = round(len(matched) / total * 100)
    return {
        "accuracy": accuracy,
        "passed": accuracy >= PASS_THRESHOLD * 100,
        "matched": matched,
        "missing": missing,
        "wrong": wrong,
        "extra": extra,
    }


# --------------------------------------------------------------------------- #
# Reporting                                                                   #
# --------------------------------------------------------------------------- #
def _report(target: str, result: dict[str, object], cmp: dict[str, object]) -> None:
    print(f"  🎯 target : {target}")
    print(f"  👂 heard  : {result['transcript'] or '—'}")
    print(
        f"  ✅ accuracy: {cmp['accuracy']}%  "
        f"({'PASS' if cmp['passed'] else 'FAIL'})  "
        f"| deepgram confidence: {result['overall_confidence']:.2f}"
    )
    if cmp["missing"]:
        print(f"  ➖ missing words   : {', '.join(cmp['missing'])}")
    if cmp["wrong"]:
        pairs = ", ".join(f"{t}→{h}" for t, h in cmp["wrong"])
        print(f"  ✏️  wrong words     : {pairs}")
    if cmp["extra"]:
        print(f"  ➕ extra words     : {', '.join(cmp['extra'])}")
    low = [
        f"{w['word']} ({w['confidence']:.2f})"
        for w in result["words"]
        if w["confidence"] < LOW_CONFIDENCE
    ]
    if low:
        print(f"  ⚠️  low-confidence  : {', '.join(low)}")
    print()


# --------------------------------------------------------------------------- #
# Commands                                                                    #
# --------------------------------------------------------------------------- #
async def cmd_smoke(n: int) -> None:
    sentences = get_sample_sentences(limit=n)
    print(f"\n=== SMOKE TEST: TTS → Deepgram → compare ({len(sentences)} sentences) ===\n")
    for word_id, word, sentence in sentences:
        print(f"[#{word_id}] {word}")
        try:
            audio = await synth_tts(sentence)
            result = await transcribe(audio, "audio/mpeg")
        except Exception as exc:  # noqa: BLE001 - experiment: show any failure
            print(f"  ❌ error: {exc}\n")
            continue
        cmp = compare(sentence, str(result["transcript"]))
        _report(sentence, result, cmp)


async def cmd_audio(audio_path: str, target: str) -> None:
    path = Path(audio_path)
    if not path.exists():
        print(f"❌ audio file not found: {audio_path}")
        return
    content_type = _CONTENT_TYPES.get(path.suffix.lower(), "audio/ogg")
    audio = path.read_bytes()
    print(f"\n=== REAL AUDIO: {path.name} ({content_type}) ===\n")
    result = await transcribe(audio, content_type)
    cmp = compare(target, str(result["transcript"]))
    _report(target, result, cmp)


def cmd_list() -> None:
    print("\n=== Sample Dutch sentences from bot.db ===\n")
    for word_id, word, sentence in get_sample_sentences():
        print(f"  #{word_id:>3}  [{word}]  {sentence}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="List sample sentences")
    parser.add_argument("--smoke", action="store_true", help="TTS→Deepgram smoke test")
    parser.add_argument("-n", type=int, default=5, help="How many sentences for --smoke")
    parser.add_argument("--audio", help="Path to a recorded audio file to test")
    parser.add_argument("--sentence-id", type=int, help="DB word id for the target")
    parser.add_argument("--target", help="Target sentence text (overrides --sentence-id)")
    args = parser.parse_args()

    if args.list:
        cmd_list()
        return

    if args.smoke:
        asyncio.run(cmd_smoke(args.n))
        return

    if args.audio:
        target = args.target
        if not target and args.sentence_id:
            target = get_sentence_by_id(args.sentence_id)
        if not target:
            print("❌ provide --target \"...\" or --sentence-id <id>")
            return
        asyncio.run(cmd_audio(args.audio, target))
        return

    parser.print_help()


if __name__ == "__main__":
    main()
