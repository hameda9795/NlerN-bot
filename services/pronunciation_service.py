"""Pronunciation practice: text-to-speech, speech-to-text and comparison.

Uses OpenAI TTS to play a target word and Whisper to transcribe the user's
recording, then scores similarity with difflib and returns Persian feedback.
"""

from __future__ import annotations

import difflib
import io
import logging

from services.openai_client import (
    STT_COST_PER_CALL,
    TTS_COST_PER_CALL,
    get_openai_client,
)

logger = logging.getLogger(__name__)

TTS_MODEL = "tts-1"
TTS_VOICE = "nova"
STT_MODEL = "whisper-1"

# Difficult Dutch sounds for Persian speakers: label, example words, hint.
DIFFICULT_SOUNDS: dict[str, dict[str, object]] = {
    "g_ch": {
        "title": "g / ch (حلقومی)",
        "words": ["goed", "acht", "lachen"],
        "hint": "این صدا را از ته گلو و محکم‌تر از «خ» فارسی تولید کن.",
    },
    "ui": {
        "title": "ui (دیفتانگ)",
        "words": ["huis", "ui", "tuin"],
        "hint": "ترکیبی بین «اَ» و «و»؛ لب‌ها را کمی گرد کن.",
    },
    "sch": {
        "title": "sch (s + حلقومی)",
        "words": ["school", "schrijven", "misschien"],
        "hint": "اول «س» بعد بلافاصله صدای حلقومی g/ch.",
    },
    "ij_ei": {
        "title": "ij / ei (دیفتانگ)",
        "words": ["ijs", "trein", "mij"],
        "hint": "چیزی بین «اِی» انگلیسی و «آی»؛ هر دو املا یک صدا دارن.",
    },
}


class PronunciationError(RuntimeError):
    """Raised when an audio API call cannot be completed."""


async def generate_target_audio(text: str) -> tuple[bytes, float]:
    """Return (mp3_bytes, est_cost) for the spoken form of ``text``."""
    client = get_openai_client()
    if client is None:
        raise PronunciationError("OpenAI client not configured")
    resp = await client.audio.speech.create(
        model=TTS_MODEL, voice=TTS_VOICE, input=text
    )
    audio = resp.read() if hasattr(resp, "read") else resp.content
    return audio, TTS_COST_PER_CALL


async def transcribe_user_audio(
    audio_bytes: bytes, *, filename: str = "voice.ogg", language: str = "nl"
) -> tuple[str, float]:
    """Transcribe user audio with Whisper. Returns (text, est_cost)."""
    client = get_openai_client()
    if client is None:
        raise PronunciationError("OpenAI client not configured")
    buffer = io.BytesIO(audio_bytes)
    buffer.name = filename  # the SDK infers format from the name
    resp = await client.audio.transcriptions.create(
        model=STT_MODEL, file=buffer, language=language
    )
    return (resp.text or "").strip(), STT_COST_PER_CALL


def _normalize(text: str) -> str:
    return "".join(c for c in text.lower().strip() if c.isalnum() or c.isspace())


def compare_pronunciation(target: str, user_spoken: str) -> dict[str, object]:
    """Compare target vs. transcription. Returns score + Persian feedback."""
    t_norm = _normalize(target)
    u_norm = _normalize(user_spoken)
    ratio = difflib.SequenceMatcher(None, t_norm, u_norm).ratio()
    score = round(ratio * 100)

    if score >= 85:
        feedback = "عالی! تلفظت دقیق بود 🎉"
    elif score >= 60:
        feedback = (
            "نزدیک بود! 👍 یک‌بار دیگه آروم‌تر و واضح‌تر بگو، "
            "مخصوصاً به صداهای حلقومی (g/ch) دقت کن."
        )
    else:
        feedback = (
            "هنوز فاصله داری. 🔁 اول به نمونه‌ی صوتی خوب گوش بده، "
            "بعد بخش‌بخش تکرار کن."
        )

    return {
        "accuracy_score": score,
        "heard": user_spoken,
        "feedback_message": feedback,
    }
