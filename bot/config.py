"""Application configuration using Pydantic Settings.

All settings are loaded from the ``.env`` file (or real environment variables).
Settings are grouped into logical sections and combined into a single
``Settings`` object, exposed through the cached :func:`get_settings` singleton.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Shared config: read from .env, ignore unknown keys, case-insensitive env names.
_BASE_CONFIG = SettingsConfigDict(
    env_file=".env",
    env_file_encoding="utf-8",
    case_sensitive=False,
    extra="ignore",
)

_BOT_TOKEN_RE = re.compile(r"^\d+:[\w-]{30,}$")


class BotConfig(BaseSettings):
    """Telegram bot settings."""

    model_config = _BASE_CONFIG

    bot_token: str = Field(
        default="",
        alias="BOT_TOKEN",
        description=(
            "Telegram bot token from @BotFather (format: '<digits>:<secret>'). "
            "Empty is allowed for processes that don't run the bot (e.g. the "
            "membership website); the bot itself checks it at startup."
        ),
    )
    # NoDecode stops pydantic-settings from JSON-decoding the raw env value,
    # so our validator can parse a plain comma-separated string instead.
    admin_ids: Annotated[list[int], NoDecode] = Field(
        default_factory=list,
        alias="ADMIN_USER_ID",
        description="Comma-separated Telegram user IDs with admin privileges.",
    )

    @field_validator("admin_ids", mode="before")
    @classmethod
    def _parse_admin_ids(cls, value: object) -> object:
        """Allow a comma-separated string such as '123,456' for ADMIN_USER_ID."""
        if value is None or value == "":
            return []
        if isinstance(value, int):
            return [value]
        if isinstance(value, str):
            return [int(part.strip()) for part in value.split(",") if part.strip()]
        return value

    @field_validator("bot_token")
    @classmethod
    def _validate_bot_token(cls, value: str) -> str:
        """Ensure a non-empty token looks like '<digits>:<secret>'."""
        if value and not _BOT_TOKEN_RE.match(value):
            raise ValueError(
                "BOT_TOKEN must look like '123456789:ABC...' "
                "(digits, a colon, then the secret)."
            )
        return value


class DatabaseConfig(BaseSettings):
    """Database connection settings."""

    model_config = _BASE_CONFIG

    database_url: str = Field(
        default="sqlite+aiosqlite:///./bot.db",
        alias="DATABASE_URL",
        description="SQLAlchemy async database URL.",
    )
    pool_size: int = Field(
        default=5,
        alias="DB_POOL_SIZE",
        ge=1,
        description="Connection pool size (ignored by SQLite).",
    )
    db_schema: str = Field(
        default="nlern",
        alias="DB_SCHEMA",
        description=(
            "Postgres schema that holds the bot's own tables. Set as the "
            "connection search_path so the bot's tables stay isolated from the "
            "other schemas in the shared database. Ignored by SQLite."
        ),
    )
    vocab_database_url: str = Field(
        default="",
        alias="VOCAB_DATABASE_URL",
        description=(
            "Read-only SQLAlchemy async URL for the remote B2 vocabulary library "
            "(schema 'vocabulary', table 'words'). Empty disables the feature."
        ),
    )

    @property
    def vocab_enabled(self) -> bool:
        """True when a remote vocabulary database URL is configured."""
        return bool(self.vocab_database_url.strip())


class AIConfig(BaseSettings):
    """OpenAI / AI routing settings."""

    model_config = _BASE_CONFIG

    openai_api_key: str = Field(
        default="",
        alias="OPENAI_API_KEY",
        description="OpenAI API key. Empty disables AI features.",
    )
    # --- Chat feature (handlers/ai_chat.py) — its own provider knobs so it can
    # point at a different OpenAI-compatible endpoint (e.g. NVIDIA) without
    # affecting pronunciation (Whisper/TTS) or question generation, which keep
    # using OPENAI_API_KEY / AI_API_KEY against OpenAI directly. ---
    chat_api_key: str = Field(
        default="",
        alias="AI_CHAT_API_KEY",
        description="API key for the chat feature. Empty falls back to OPENAI_API_KEY.",
    )
    chat_base_url: str = Field(
        default="",
        alias="AI_CHAT_BASE_URL",
        description=(
            "Base URL override for the chat feature's OpenAI-compatible provider "
            "(e.g. NVIDIA's 'https://integrate.api.nvidia.com/v1'). Empty uses "
            "OpenAI's default endpoint."
        ),
    )
    chat_model: str = Field(
        default="",
        alias="AI_CHAT_MODEL",
        description="Model id for the chat feature. Empty falls back to OPENAI_MODEL_DEFAULT.",
    )
    deepgram_api_key: str = Field(
        default="",
        alias="DEEPGRAM_API_KEY",
        description="Deepgram API key for speech-to-text. Empty disables it.",
    )
    openai_model_default: str = Field(
        default="gpt-4o-mini",
        alias="OPENAI_MODEL_DEFAULT",
        description="Default (cheap) model for most AI calls.",
    )
    openai_max_tokens: int = Field(
        default=800,
        alias="OPENAI_MAX_TOKENS",
        ge=1,
        description="Max tokens per AI response.",
    )
    cost_limit_per_user_per_day: float = Field(
        default=0.10,
        alias="AI_COST_LIMIT_PER_USER_PER_DAY",
        ge=0,
        description="Daily AI spend cap per user, in USD.",
    )
    @property
    def is_enabled(self) -> bool:
        """True when an API key is configured."""
        return bool(self.openai_api_key.strip())

    @property
    def deepgram_enabled(self) -> bool:
        """True when a Deepgram API key is configured."""
        key = self.deepgram_api_key.strip()
        return bool(key) and "replace" not in key.lower()

    @property
    def chat_provider_api_key(self) -> str:
        """Key used by the chat feature (AI_CHAT_API_KEY, else OPENAI_API_KEY)."""
        return (self.chat_api_key or self.openai_api_key).strip()

    @property
    def chat_provider_model(self) -> str:
        """Model used by the chat feature (AI_CHAT_MODEL, else the default)."""
        return self.chat_model.strip() or self.openai_model_default


class FSRSConfig(BaseSettings):
    """Spaced repetition (FSRS) settings."""

    model_config = _BASE_CONFIG

    desired_retention: float = Field(
        default=0.9,
        alias="DESIRED_RETENTION",
        gt=0,
        le=1,
        description="Target probability of recall at review time (0-1).",
    )
    max_daily_reviews: int = Field(
        default=50,
        alias="MAX_DAILY_REVIEWS",
        ge=1,
        description="Maximum review cards served per user per day.",
    )


class SubscriptionConfig(BaseSettings):
    """Subscription / membership-site settings."""

    model_config = _BASE_CONFIG

    site_base_url: str = Field(
        default="https://nlern.techsolutionsutrecht.nl",
        alias="SUBSCRIPTION_SITE_URL",
        description="Base URL of the standalone membership site (no trailing slash).",
    )
    token_secret: str = Field(
        default="",
        alias="SUBSCRIPTION_TOKEN_SECRET",
        description="HMAC secret used to sign the per-user checkout-link token.",
    )
    token_max_age_seconds: int = Field(
        default=3600,
        alias="SUBSCRIPTION_TOKEN_MAX_AGE_SECONDS",
        ge=300,
        le=604800,
        description="Maximum age of checkout/account bearer links, in seconds.",
    )
    price_eur: float = Field(
        default=4.99,
        alias="SUBSCRIPTION_PRICE_EUR",
        gt=0,
        description="Monthly subscription price in EUR.",
    )
    mollie_api_key: str = Field(
        default="",
        alias="MOLLIE_API_KEY",
        description="Mollie API key (test_... or live_...). Empty disables checkout.",
    )

    @property
    def mollie_enabled(self) -> bool:
        """True when a Mollie API key is configured."""
        return bool(self.mollie_api_key.strip())


class NotificationConfig(BaseSettings):
    """Notification scheduling window."""

    model_config = _BASE_CONFIG

    enabled_hours_start: int = Field(
        default=8,
        alias="NOTIFICATION_ENABLED_HOURS_START",
        ge=0,
        le=23,
        description="Earliest hour (0-23) notifications may be sent.",
    )
    enabled_hours_end: int = Field(
        default=22,
        alias="NOTIFICATION_ENABLED_HOURS_END",
        ge=0,
        le=23,
        description="Latest hour (0-23) notifications may be sent.",
    )


class Settings:
    """Top-level settings combining every config group.

    Each group reads independently from the same ``.env`` file, so the
    combined object exposes all sections through attribute access.
    """

    def __init__(self) -> None:
        self.bot = BotConfig()
        self.database = DatabaseConfig()
        self.ai = AIConfig()
        self.fsrs = FSRSConfig()
        self.notifications = NotificationConfig()
        self.subscription = SubscriptionConfig()

    def __repr__(self) -> str:
        # Never expose secrets in the repr.
        return (
            "Settings("
            f"admin_ids={self.bot.admin_ids}, "
            f"database_url={self.database.database_url!r}, "
            f"ai_enabled={self.ai.is_enabled}, "
            f"model={self.ai.openai_model_default!r}, "
            f"desired_retention={self.fsrs.desired_retention})"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached singleton ``Settings`` instance."""
    return Settings()


if __name__ == "__main__":
    # Quick manual check: `python -m bot.config`
    settings = get_settings()
    print(settings)
    print("AI enabled:", settings.ai.is_enabled)
    print("Admins:", settings.bot.admin_ids)
