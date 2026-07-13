"""SQLAlchemy 2.x ORM models for the Dutch Learning Bot.

All datetime columns are timezone-aware. Frequently queried columns
(telegram_id, user_id, due_date) are indexed.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    """Return the current timezone-aware UTC time."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Declarative base for all models."""


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # BigInteger: modern Telegram user IDs exceed the 32-bit integer range.
    telegram_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, index=True, nullable=False
    )
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str | None] = mapped_column(String(128))
    last_name: Mapped[str | None] = mapped_column(String(128))
    language_code: Mapped[str | None] = mapped_column(String(8))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    current_cefr_level: Mapped[str] = mapped_column(String(4), default="A0")
    daily_streak: Mapped[int] = mapped_column(Integer, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, default=0)
    xp_points: Mapped[int] = mapped_column(Integer, default=0)
    subscription_tier: Mapped[str] = mapped_column(String(16), default="free")

    # Relationships
    user_words: Mapped[list["UserWord"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    cards: Mapped[list["FSRSCard"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    progress: Mapped[list["UserProgress"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    gamification_events: Mapped[list["GamificationEvent"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    notification_schedules: Mapped[list["NotificationSchedule"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    saved_words: Mapped[list["SavedWord"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    subscription: Mapped["Subscription | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    question_progress: Mapped[list["UserQuestionProgress"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    question_attempts: Mapped[list["UserQuestionAttempt"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Word(Base):
    __tablename__ = "words"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dutch_word: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    persian_translation: Mapped[str] = mapped_column(String(256), nullable=False)
    article: Mapped[str | None] = mapped_column(String(8))  # "de" / "het" / None
    example_sentence_dutch: Mapped[str | None] = mapped_column(Text)
    example_sentence_persian: Mapped[str | None] = mapped_column(Text)
    cefr_level: Mapped[str] = mapped_column(String(4), index=True, default="A0")
    category: Mapped[str | None] = mapped_column(String(64), index=True)
    audio_url: Mapped[str | None] = mapped_column(String(512))

    user_words: Mapped[list["UserWord"]] = relationship(back_populates="word")
    cards: Mapped[list["FSRSCard"]] = relationship(back_populates="word")


class UserWord(Base):
    __tablename__ = "user_words"
    __table_args__ = (UniqueConstraint("user_id", "word_id", name="uq_user_word"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    word_id: Mapped[int] = mapped_column(
        ForeignKey("words.id", ondelete="CASCADE"), index=True, nullable=False
    )
    is_learned: Mapped[bool] = mapped_column(Boolean, default=False)
    learned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    mistake_count: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped["User"] = relationship(back_populates="user_words")
    word: Mapped["Word"] = relationship(back_populates="user_words")


class FSRSCard(Base):
    __tablename__ = "fsrs_cards"
    __table_args__ = (UniqueConstraint("user_id", "word_id", name="uq_card_user_word"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    word_id: Mapped[int] = mapped_column(
        ForeignKey("words.id", ondelete="CASCADE"), index=True, nullable=False
    )
    card_state: Mapped[int] = mapped_column(Integer, default=1)  # FSRS State (Learning=1)
    step: Mapped[int | None] = mapped_column(Integer, default=0)  # FSRS learning step
    due_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, default=_utcnow
    )
    # Null until the card has been reviewed at least once (FSRS semantics).
    stability: Mapped[float | None] = mapped_column(Float, default=None)
    difficulty: Mapped[float | None] = mapped_column(Float, default=None)
    elapsed_days: Mapped[int] = mapped_column(Integer, default=0)
    scheduled_days: Mapped[int] = mapped_column(Integer, default=0)
    reps: Mapped[int] = mapped_column(Integer, default=0)
    lapses: Mapped[int] = mapped_column(Integer, default=0)
    last_review_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(back_populates="cards")
    word: Mapped["Word"] = relationship(back_populates="cards")
    review_logs: Mapped[list["ReviewLog"]] = relationship(
        back_populates="card", cascade="all, delete-orphan"
    )


class ReviewLog(Base):
    __tablename__ = "review_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    card_id: Mapped[int] = mapped_column(
        ForeignKey("fsrs_cards.id", ondelete="CASCADE"), index=True, nullable=False
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-4
    review_datetime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    scheduled_days: Mapped[int] = mapped_column(Integer, default=0)
    elapsed_days: Mapped[int] = mapped_column(Integer, default=0)

    card: Mapped["FSRSCard"] = relationship(back_populates="review_logs")


class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title_dutch: Mapped[str] = mapped_column(String(256), nullable=False)
    title_persian: Mapped[str] = mapped_column(String(256), nullable=False)
    cefr_level: Mapped[str] = mapped_column(String(4), index=True, default="A0")
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    content_json: Mapped[str] = mapped_column(Text, default="{}")  # JSON string
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)

    progress: Mapped[list["UserProgress"]] = relationship(back_populates="lesson")


class UserProgress(Base):
    __tablename__ = "user_progress"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    lesson_id: Mapped[int] = mapped_column(
        ForeignKey("lessons.id", ondelete="CASCADE"), index=True, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    score: Mapped[float | None] = mapped_column(Float)

    user: Mapped["User"] = relationship(back_populates="progress")
    lesson: Mapped["Lesson"] = relationship(back_populates="progress")


class GamificationEvent(Base):
    __tablename__ = "gamification_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    xp_earned: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str | None] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    user: Mapped["User"] = relationship(back_populates="gamification_events")


class AIUsage(Base):
    """Daily AI cost/usage accounting per user (for enforcing spend limits)."""

    __tablename__ = "ai_usage"
    __table_args__ = (UniqueConstraint("user_id", "day", name="uq_ai_usage_user_day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    day: Mapped[str] = mapped_column(String(10), index=True)  # "YYYY-MM-DD" (UTC)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    calls: Mapped[int] = mapped_column(Integer, default=0)


class SavedWord(Base):
    """A vocabulary word a user marked as 'hard' to practice again.

    The word text is snapshotted from the remote vocabulary library so the
    'my hard words' review works without re-querying the remote database.
    ``vocab_word_id`` is the ``id`` of the row in ``vocabulary.words``.
    """

    __tablename__ = "saved_words"
    __table_args__ = (
        UniqueConstraint("user_id", "vocab_word_id", name="uq_saved_user_word"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # BigInteger: verb services use synthetic IDs above the 32-bit range.
    vocab_word_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    nederlands: Mapped[str] = mapped_column(String(256), nullable=False)
    persian: Mapped[str | None] = mapped_column(String(512))
    pronunciation: Mapped[str | None] = mapped_column(String(256))
    category: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    user: Mapped["User"] = relationship(back_populates="saved_words")


class Subscription(Base):
    """A user's subscription state — the source of truth for access gating.

    One row per user. Access is granted while ``status == 'active'`` and
    ``now < current_period_end``. Recurring billing is handled by Mollie: the
    first iDEAL payment creates a SEPA Direct Debit mandate, then Mollie's
    Subscriptions API charges €4.99 monthly and notifies our webhook, which
    extends ``current_period_end``. The ``mollie_*`` columns are filled in by
    the payment flow / webhook.
    """

    __tablename__ = "subscriptions"
    __table_args__ = (UniqueConstraint("user_id", name="uq_subscription_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        unique=True,
        nullable=False,
    )
    # pending | active | past_due | canceled | expired
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    amount_eur: Mapped[float] = mapped_column(Float, default=4.99)
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    mollie_customer_id: Mapped[str | None] = mapped_column(String(64))
    mollie_mandate_id: Mapped[str | None] = mapped_column(String(64))
    mollie_subscription_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Set once, permanently, the first time this user starts a free trial.
    # Never cleared — it's the abuse-prevention flag (a trial is offered once
    # per Telegram account, no matter how many times the sub status changes).
    trial_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(back_populates="subscription")


class Payment(Base):
    """A record of one Mollie payment attempt, for the user-facing history list.

    Written by the webhook for every terminal payment status it observes
    (paid/failed/expired/canceled). ``mollie_payment_id`` is unique so the
    (possibly repeated) webhook call is idempotent.
    """

    __tablename__ = "payments"
    __table_args__ = (UniqueConstraint("mollie_payment_id", name="uq_payment_mollie_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    mollie_payment_id: Mapped[str] = mapped_column(String(64), nullable=False)
    amount_eur: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    sequence_type: Mapped[str | None] = mapped_column(String(16))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    user: Mapped["User"] = relationship()


class NotificationSchedule(Base):
    __tablename__ = "notification_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    notification_type: Mapped[str] = mapped_column(String(64), nullable=False)
    scheduled_time: Mapped[str] = mapped_column(String(8), default="08:00")  # "HH:MM"
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Amsterdam")

    user: Mapped["User"] = relationship(back_populates="notification_schedules")


# ---------------------------------------------------------------------------
# Reusable question bank + per-user progress (dynamic Q&A foundation)
#
# A question is authored once (manually or, later, by AI), reviewed, and then
# served to many users. ``status`` gates which questions are ever shown; only
# ``approved`` questions reach learners. Per-user state (have they seen it, how
# often they got it right) lives in the two ``user_question_*`` tables so the
# bank itself stays user-agnostic and reusable.
# ---------------------------------------------------------------------------


class Question(Base):
    """A single reusable question in the bank (currently 4-option MCQ)."""

    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Composite lookup key for selection — all three are indexed together.
    level: Mapped[str] = mapped_column(String(4), nullable=False)  # A2 / B1 / B2
    section: Mapped[str] = mapped_column(String(32), nullable=False)  # grammar, ...
    topic: Mapped[str] = mapped_column(String(64), nullable=False)  # zijn_hebben, ...
    life_context: Mapped[str | None] = mapped_column(String(64))  # e.g. "work", "doctor"
    question_type: Mapped[str] = mapped_column(String(32), default="mcq_4")
    difficulty: Mapped[int] = mapped_column(Integer, default=1)  # 1..5

    question_text_nl: Mapped[str] = mapped_column(Text, nullable=False)
    question_text_fa: Mapped[str | None] = mapped_column(Text)
    explanation_fa: Mapped[str | None] = mapped_column(Text)
    grammar_rule_fa: Mapped[str | None] = mapped_column(Text)
    extra_example_nl: Mapped[str | None] = mapped_column(Text)
    extra_example_fa: Mapped[str | None] = mapped_column(Text)

    # draft | approved | rejected — only "approved" is ever served.
    status: Mapped[str] = mapped_column(String(16), default="draft", index=True)
    quality_score: Mapped[float | None] = mapped_column(Float)
    created_by: Mapped[str | None] = mapped_column(String(64))  # "manual" / "ai" / id
    reviewed_by: Mapped[str | None] = mapped_column(String(64))  # e.g. "ai_reviewer"
    # Review output (set by the AI reviewer). ``review_notes_fa`` holds the human
    # reason; ``review_issues_json`` is a JSON string of {issues, suggested_fix}.
    review_notes_fa: Mapped[str | None] = mapped_column(Text)
    review_issues_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    options: Mapped[list["QuestionOption"]] = relationship(
        back_populates="question",
        cascade="all, delete-orphan",
        order_by="QuestionOption.option_key",
    )

    __table_args__ = (
        Index("ix_question_level_section_topic", "level", "section", "topic"),
    )


class QuestionOption(Base):
    """One of the four (A/B/C/D) options for a question; exactly one is correct."""

    __tablename__ = "question_options"
    __table_args__ = (
        UniqueConstraint("question_id", "option_key", name="uq_question_option_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    option_key: Mapped[str] = mapped_column(String(1), nullable=False)  # A / B / C / D
    option_text_nl: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    feedback_fa: Mapped[str | None] = mapped_column(Text)

    question: Mapped["Question"] = relationship(back_populates="options")


class UserQuestionProgress(Base):
    """Per-user, per-question mastery state — the 'has this user seen it' record.

    A row exists once a user has been served the question at least once, so the
    selection service treats "question_id present here" as "already seen".
    """

    __tablename__ = "user_question_progress"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "question_id", name="uq_user_question_progress"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    times_seen: Mapped[int] = mapped_column(Integer, default=0)
    times_correct: Mapped[int] = mapped_column(Integer, default=0)
    times_wrong: Mapped[int] = mapped_column(Integer, default=0)
    mastery_score: Mapped[float] = mapped_column(Float, default=0.0)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    user: Mapped["User"] = relationship(back_populates="question_progress")


class UserQuestionAttempt(Base):
    """One immutable record per answer a user submits (full attempt history)."""

    __tablename__ = "user_question_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    selected_option_key: Mapped[str] = mapped_column(String(1), nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    answered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    time_spent_seconds: Mapped[int | None] = mapped_column(Integer)

    user: Mapped["User"] = relationship(back_populates="question_attempts")


class SupportMessage(Base):
    """One relayed message between a user and an admin's Telegram chat.

    Every message the bot copies into an admin's chat (both the original
    user message and the admin's reply) gets a row keyed by where it landed
    (``admin_chat_id`` + ``admin_message_id``). When an admin replies to one
    of these copies, that key is looked up to find which user to relay the
    reply back to — this is what lets a single admin chat hold many
    concurrent support conversations without them getting mixed up.
    """

    __tablename__ = "support_messages"
    __table_args__ = (
        UniqueConstraint(
            "admin_chat_id", "admin_message_id", name="uq_support_admin_msg"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    admin_chat_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    admin_message_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
