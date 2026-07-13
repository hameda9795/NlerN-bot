"""Deepgram speech-to-text for checking whether a Dutch sentence was said.

Unlike :mod:`services.pronunciation_service` (which scores a single sound),
this verifies that the user spoke the *right words*. It transcribes a voice
recording with Deepgram Nova-3 (Dutch), then aligns the transcript against the
target sentence word-by-word and returns a Persian verdict.

We call Deepgram's REST API directly with httpx, so no extra SDK is required.
"""

from __future__ import annotations

import difflib
import logging
import string

import httpx

from bot.config import get_settings

logger = logging.getLogger(__name__)

DEEPGRAM_URL = "https://api.deepgram.com/v1/listen"
DEEPGRAM_MODEL = "nova-3"
DEEPGRAM_LANGUAGE = "nl"

# Share of target words that must match for a "correct" verdict, and the
# per-word confidence below which a word is flagged as said unclearly.
PASS_THRESHOLD = 0.85
LOW_CONFIDENCE = 0.60


class DeepgramError(RuntimeError):
    """Raised when the Deepgram API call cannot be completed."""


def is_enabled() -> bool:
    """True when a Deepgram API key is configured."""
    return get_settings().ai.deepgram_enabled


async def transcribe(audio: bytes, *, content_type: str = "audio/ogg") -> dict[str, object]:
    """Transcribe audio with Deepgram Nova-3 (Dutch).

    Returns ``{"transcript": str, "words": [{word, confidence}, ...],
    "overall_confidence": float}``.
    """
    settings = get_settings()
    if not settings.ai.deepgram_enabled:
        raise DeepgramError("Deepgram API key not configured")

    params = {
        "model": DEEPGRAM_MODEL,
        "language": DEEPGRAM_LANGUAGE,
        "punctuate": "true",
        "smart_format": "true",
    }
    headers = {
        "Authorization": f"Token {settings.ai.deepgram_api_key.strip()}",
        "Content-Type": content_type,
    }
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                DEEPGRAM_URL, params=params, headers=headers, content=audio
            )
        resp.raise_for_status()
        data = resp.json()
        alt = data["results"]["channels"][0]["alternatives"][0]
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        logger.warning("Deepgram transcription failed: %s", exc)
        raise DeepgramError(str(exc)) from exc

    words = [
        {"word": w.get("word", ""), "confidence": float(w.get("confidence", 0.0))}
        for w in alt.get("words", [])
    ]
    return {
        "transcript": (alt.get("transcript") or "").strip(),
        "words": words,
        "overall_confidence": float(alt.get("confidence", 0.0)),
    }


def _tokenize(text: str) -> list[str]:
    table = str.maketrans("", "", string.punctuation + "¿¡«»…")
    return [t for t in text.lower().translate(table).split() if t]


def compare(target: str, heard: str) -> dict[str, object]:
    """Align target vs. heard words and produce an accuracy verdict."""
    t_words = _tokenize(target)
    h_words = _tokenize(heard)
    sm = difflib.SequenceMatcher(None, t_words, h_words)

    matched: list[str] = []
    missing: list[str] = []
    wrong: list[tuple[str, str]] = []
    extra: list[str] = []

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


def build_feedback(target: str, result: dict[str, object]) -> str:
    """Build a Persian feedback message from transcript + comparison."""
    heard = str(result["transcript"])
    cmp = compare(target, heard)
    accuracy = cmp["accuracy"]

    if cmp["passed"]:
        head = f"✅ آفرین! جمله رو درست گفتی. ({accuracy}٪)"
    elif accuracy >= 50:
        head = f"🔶 نزدیک بود. ({accuracy}٪)"
    else:
        head = f"🔁 هنوز فاصله داری. ({accuracy}٪)"

    lines = [
        head,
        f"🎯 جمله‌ی هدف: <b>{target}</b>",
        f"👂 چیزی که شنیدم: «{heard or '—'}»",
    ]
    if cmp["missing"]:
        lines.append(f"➖ نگفتی: {', '.join(cmp['missing'])}")
    if cmp["wrong"]:
        pairs = ", ".join(f"{t}→{h}" for t, h in cmp["wrong"])
        lines.append(f"✏️ اشتباه گفتی: {pairs}")
    if cmp["extra"]:
        lines.append(f"➕ اضافه گفتی: {', '.join(cmp['extra'])}")

    low = [
        w["word"]
        for w in result["words"]  # type: ignore[union-attr]
        if w["confidence"] < LOW_CONFIDENCE  # type: ignore[index]
    ]
    if low:
        lines.append(f"⚠️ نامفهوم/مبهم: {', '.join(low)} — واضح‌تر بگو.")

    return "\n".join(lines)
