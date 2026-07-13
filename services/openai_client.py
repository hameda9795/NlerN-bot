"""Shared async OpenAI client and pricing helpers.

The client is created lazily and cached. If no API key is configured (or it
is the placeholder), :func:`get_openai_client` returns ``None`` so callers can
degrade gracefully instead of raising.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from openai import AsyncOpenAI

from bot.config import get_settings

logger = logging.getLogger(__name__)

# Per-1M-token prices (USD), approximate. Used only for daily-limit accounting.
MODEL_PRICES: dict[str, tuple[float, float]] = {
    # model: (input_per_1m, output_per_1m)
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    # NVIDIA build.nvidia.com endpoint — free-tier API key, no per-token cost.
    "nvidia/nemotron-3-ultra-550b-a55b": (0.0, 0.0),
}

# Flat per-call estimates for audio endpoints (rough, for accounting only).
TTS_COST_PER_CALL = 0.002
STT_COST_PER_CALL = 0.006


def _looks_like_placeholder(key: str) -> bool:
    return (not key) or "replace" in key.lower() or len(key) < 20


@lru_cache(maxsize=1)
def get_openai_client() -> AsyncOpenAI | None:
    """Return a cached AsyncOpenAI client, or None if not configured."""
    settings = get_settings()
    key = settings.ai.openai_api_key.strip()
    if _looks_like_placeholder(key):
        logger.warning("OpenAI key missing/placeholder — AI features disabled.")
        return None
    return AsyncOpenAI(api_key=key)


@lru_cache(maxsize=1)
def get_chat_client() -> AsyncOpenAI | None:
    """Return a cached AsyncOpenAI client for the chat feature, or None.

    Separate from :func:`get_openai_client` so the chat feature can point at a
    different OpenAI-compatible provider (base URL + key) without affecting
    pronunciation (Whisper/TTS) or question generation, which need OpenAI
    itself.
    """
    settings = get_settings()
    key = settings.ai.chat_provider_api_key
    if _looks_like_placeholder(key):
        logger.warning("Chat AI key missing/placeholder — AI chat disabled.")
        return None
    base_url = settings.ai.chat_base_url.strip() or None
    return AsyncOpenAI(api_key=key, base_url=base_url)


def estimate_chat_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Estimate USD cost of a chat completion from token counts."""
    in_price, out_price = MODEL_PRICES.get(model, MODEL_PRICES["gpt-4o-mini"])
    return (prompt_tokens / 1_000_000) * in_price + (
        completion_tokens / 1_000_000
    ) * out_price
