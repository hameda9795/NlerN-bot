# Admin Broadcast Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the admin compose one message from the in-bot admin dashboard and send it to a chosen segment of users (all / never-subscribed / lapsed / currently-active), safely within Telegram's rate limits, with a test-send option and a full audit trail.

**Architecture:** A new `services/broadcast_service.py` owns segment targeting, the rate-limited send loop, and the audit row (`Broadcast` model in `database/models.py`). `handlers/admin.py` gets new FSM states and callback handlers that orchestrate the compose → preview → confirm → background-send UI flow, using new pure-rendering keyboard builders in `keyboards/admin_keyboard.py`. Sending runs as a detached `asyncio.Task` so the admin isn't blocked while it runs.

**Tech Stack:** Python 3.12, aiogram 3.29 (async, long-polling), SQLAlchemy 2.x async ORM, Postgres (prod) / SQLite in-memory (tests), pytest + pytest-asyncio (`asyncio_mode = "auto"` in `pyproject.toml`).

## Global Constraints

- Spec source of truth: `docs/superpowers/specs/2026-08-01-admin-broadcast-design.md`.
- Text-only broadcasts, no media, no inline buttons in the sent message, no scheduling — v1 scope only.
- Send delay: **0.05s between messages (20 msg/s)**, safely under Telegram's ~30 msg/s cap.
- `TelegramForbiddenError` → counted as `blocked`, never fatal to the loop.
- `TelegramRetryAfter` → sleep `retry_after`, retry once, then count as `failed` if it fails again.
- Any other send exception → counted as `failed`, logged, loop continues.
- Only one broadcast may run at a time (module-level flag in `broadcast_service`).
- New DB table (`broadcasts`) is created automatically by `init_db()` on next deploy — no manual migration.
- Follow existing project layering: handlers (I/O only) / services (logic) / database (schema) / keyboards (pure rendering, no service imports) / middlewares.
- All new admin callback handlers for this feature must explicitly re-check `is_admin(user.telegram_id)` (the file's stated intent — "every entry point re-checks is_admin directly" — even though some pre-existing handlers don't; this feature is the highest-blast-radius action in the dashboard, so it gets the check).
- Persian UI copy, HTML formatting (`parse_mode=HTML` is the bot's default, set in `bot/loader.py`).

---

### Task 1: `Broadcast` model + segment resolution

**Files:**
- Modify: `database/models.py` (add `Broadcast` class, after the existing `Payment` class, before `NotificationSchedule`)
- Create: `services/broadcast_service.py`
- Test: `tests/test_broadcast_service.py`

**Interfaces:**
- Consumes: `database.connection.get_db_session`, `database.models.User`, `database.models.Subscription`, `services.subscription_service.is_active`, `services.subscription_service.STATUS_ACTIVE` (already exist).
- Produces:
  - `database.models.Broadcast` — ORM model, columns: `id`, `admin_user_id: int`, `segment: str`, `message_html: str`, `target_count: int`, `sent_count: int`, `blocked_count: int`, `failed_count: int`, `started_at: datetime`, `finished_at: datetime | None`.
  - `services.broadcast_service.SEGMENTS: dict[str, str]` — ordered `{key: label}` for the 4 segments.
  - `async def resolve_segment_user_ids(segment: str) -> list[int]` — raises `ValueError` on an unknown segment key.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_broadcast_service.py`:

```python
"""Tests for broadcast segment targeting."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import pytest

from database.models import Subscription, User
from services import subscription_service as subs


@pytest.fixture
def patched_broadcast_db(monkeypatch, session_factory):
    """Point broadcast_service.get_db_session at the in-memory database."""

    @asynccontextmanager
    async def _fake_session():
        session = session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    import services.broadcast_service as bc

    monkeypatch.setattr(bc, "get_db_session", _fake_session)
    return session_factory


async def _make_user(session_factory, telegram_id: int) -> int:
    async with session_factory() as session:
        user = User(telegram_id=telegram_id)
        session.add(user)
        await session.flush()
        uid = user.id
        await session.commit()
    return uid


async def _add_subscription(session_factory, user_id: int, *, status: str, period_end) -> None:
    async with session_factory() as session:
        session.add(
            Subscription(user_id=user_id, status=status, current_period_end=period_end)
        )
        await session.commit()


@pytest.mark.asyncio
async def test_resolve_segment_all_returns_every_user(patched_broadcast_db):
    import services.broadcast_service as bc

    u1 = await _make_user(patched_broadcast_db, 1001)
    u2 = await _make_user(patched_broadcast_db, 1002)

    result = await bc.resolve_segment_user_ids("all")
    assert set(result) == {u1, u2}


@pytest.mark.asyncio
async def test_resolve_segment_never_subscribed(patched_broadcast_db):
    import services.broadcast_service as bc

    never = await _make_user(patched_broadcast_db, 2001)
    has_sub = await _make_user(patched_broadcast_db, 2002)
    await _add_subscription(
        patched_broadcast_db,
        has_sub,
        status=subs.STATUS_ACTIVE,
        period_end=datetime.now(timezone.utc) + timedelta(days=1),
    )

    result = await bc.resolve_segment_user_ids("never_subscribed")
    assert result == [never]


@pytest.mark.asyncio
async def test_resolve_segment_active_vs_lapsed(patched_broadcast_db):
    """Mirrors real production data: a subscription row with status='active'
    but an expired current_period_end is 'lapsed', not 'active' — the same
    stale-status pattern found in the live DB (100 of 102 'active' rows were
    actually expired trials)."""
    import services.broadcast_service as bc

    active_user = await _make_user(patched_broadcast_db, 3001)
    lapsed_user = await _make_user(patched_broadcast_db, 3002)
    await _add_subscription(
        patched_broadcast_db,
        active_user,
        status=subs.STATUS_ACTIVE,
        period_end=datetime.now(timezone.utc) + timedelta(days=1),
    )
    await _add_subscription(
        patched_broadcast_db,
        lapsed_user,
        status=subs.STATUS_ACTIVE,  # stale status; period already ended
        period_end=datetime.now(timezone.utc) - timedelta(days=1),
    )

    assert await bc.resolve_segment_user_ids("active") == [active_user]
    assert await bc.resolve_segment_user_ids("lapsed") == [lapsed_user]


@pytest.mark.asyncio
async def test_resolve_segment_unknown_raises(patched_broadcast_db):
    import services.broadcast_service as bc

    with pytest.raises(ValueError):
        await bc.resolve_segment_user_ids("bogus")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_broadcast_service.py -v`
Expected: `ModuleNotFoundError: No module named 'services.broadcast_service'` (or collection error) — the module doesn't exist yet.

- [ ] **Step 3: Add the `Broadcast` model**

In `database/models.py`, insert this class immediately after the `Payment` class (after its `user: Mapped["User"] = relationship()` line) and before `class NotificationSchedule(Base):`:

```python
class Broadcast(Base):
    """Audit row for one admin broadcast attempt (one row per send action)."""

    __tablename__ = "broadcasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admin_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    segment: Mapped[str] = mapped_column(String(32), nullable=False)
    message_html: Mapped[str] = mapped_column(Text, nullable=False)
    target_count: Mapped[int] = mapped_column(Integer, default=0)
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    blocked_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

- [ ] **Step 4: Create `services/broadcast_service.py` with segment resolution**

```python
"""Admin broadcast: segment targeting and the rate-limited send loop.

Kept separate from ``admin_service`` because it needs a live ``Bot`` instance
to actually send messages (see ``run_broadcast``), not just DB reads.
"""

from __future__ import annotations

from database.connection import get_db_session
from database.models import Subscription, User
from services import subscription_service as subs
from sqlalchemy import select

SEGMENTS: dict[str, str] = {
    "all": "همه‌ی کاربران",
    "never_subscribed": "هرگز مشترک نشده",
    "lapsed": "trial/اشتراک منقضی‌شده",
    "active": "مشترک فعال الان",
}


async def resolve_segment_user_ids(segment: str) -> list[int]:
    """Return the target `User.id` list for a segment.

    Raises ``ValueError`` for an unrecognized segment key.
    """
    if segment not in SEGMENTS:
        raise ValueError(f"Unknown segment: {segment}")

    async with get_db_session() as session:
        all_user_ids = list(await session.scalars(select(User.id)))
        if segment == "all":
            return all_user_ids
        all_subs = list(await session.scalars(select(Subscription)))

    subscribed_ids = {sub.user_id for sub in all_subs}
    if segment == "never_subscribed":
        return [uid for uid in all_user_ids if uid not in subscribed_ids]

    active_ids = {sub.user_id for sub in all_subs if subs.is_active(sub)}
    if segment == "active":
        return [uid for uid in all_user_ids if uid in active_ids]

    # segment == "lapsed": has a subscription row, but it's not currently active
    return [uid for uid in all_user_ids if uid in subscribed_ids and uid not in active_ids]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_broadcast_service.py -v`
Expected: all 4 tests PASS

- [ ] **Step 6: Run the full suite to check nothing else broke**

Run: `uv run pytest -q`
Expected: all tests PASS (previous 15 + these 4 new ones)

- [ ] **Step 7: Commit**

```bash
git add database/models.py services/broadcast_service.py tests/test_broadcast_service.py
git commit -m "feat: add Broadcast model and segment resolution for admin broadcast"
```

---

### Task 2: Rate-limited send loop + audit persistence

**Files:**
- Modify: `services/broadcast_service.py`
- Test: `tests/test_broadcast_service.py` (append)

**Interfaces:**
- Consumes: `resolve_segment_user_ids` (Task 1), `database.models.Broadcast`, `database.models.User`, `aiogram.Bot`, `aiogram.exceptions.TelegramForbiddenError`, `aiogram.exceptions.TelegramRetryAfter`.
- Produces:
  - `services.broadcast_service.BROADCAST_DELAY_SECONDS: float` (module-level constant, `0.05`)
  - `services.broadcast_service.STATUS_UPDATE_INTERVAL_SECONDS: float` (module-level constant, `5.0`)
  - `def is_broadcast_running() -> bool`
  - `async def run_broadcast(bot: Bot, *, admin_user_id: int, segment: str, message_html: str, status_chat_id: int, status_message_id: int) -> None`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_broadcast_service.py`:

```python
from sqlalchemy import select as sa_select

from database.models import Broadcast


class FakeBot:
    """Minimal stand-in for aiogram.Bot's send_message/edit_message_text."""

    def __init__(self, behaviors: dict[int, list[Exception | None]] | None = None):
        self.behaviors = behaviors or {}
        self.sent_to: list[int] = []
        self.edits: list[str] = []

    async def send_message(self, chat_id, text, parse_mode=None):
        queue = self.behaviors.get(chat_id)
        self.sent_to.append(chat_id)
        if queue:
            outcome = queue.pop(0)
            if outcome is not None:
                raise outcome
        return None

    async def edit_message_text(self, text, chat_id=None, message_id=None):
        self.edits.append(text)


@pytest.mark.asyncio
async def test_run_broadcast_counts_success_blocked_and_failed(patched_broadcast_db, monkeypatch):
    import services.broadcast_service as bc
    from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter

    monkeypatch.setattr(bc, "BROADCAST_DELAY_SECONDS", 0)

    ok_user = await _make_user(patched_broadcast_db, 4001)
    blocked_user = await _make_user(patched_broadcast_db, 4002)
    retry_then_ok_user = await _make_user(patched_broadcast_db, 4003)
    failing_user = await _make_user(patched_broadcast_db, 4004)

    bot = FakeBot({
        4002: [TelegramForbiddenError(method=None, message="blocked")],
        4003: [TelegramRetryAfter(method=None, message="flood", retry_after=0), None],
        4004: [RuntimeError("boom")],
    })

    await bc.run_broadcast(
        bot,
        admin_user_id=ok_user,
        segment="all",
        message_html="<b>hi</b>",
        status_chat_id=555,
        status_message_id=1,
    )

    async with patched_broadcast_db() as session:
        row = (await session.scalars(sa_select(Broadcast))).one()

    assert row.target_count == 4
    assert row.sent_count == 2  # ok_user + retry_then_ok_user (succeeds on retry)
    assert row.blocked_count == 1
    assert row.failed_count == 1
    assert row.finished_at is not None
    assert "✅" in bot.edits[-1]
    assert "موفق: 2" in bot.edits[-1]
    assert not bc.is_broadcast_running()


@pytest.mark.asyncio
async def test_run_broadcast_sets_running_flag_during_send(patched_broadcast_db, monkeypatch):
    import services.broadcast_service as bc

    monkeypatch.setattr(bc, "BROADCAST_DELAY_SECONDS", 0)
    user_id = await _make_user(patched_broadcast_db, 5001)
    seen_running = []

    class ObservingBot(FakeBot):
        async def send_message(self, chat_id, text, parse_mode=None):
            seen_running.append(bc.is_broadcast_running())
            return await super().send_message(chat_id, text, parse_mode=parse_mode)

    bot = ObservingBot()
    assert not bc.is_broadcast_running()

    await bc.run_broadcast(
        bot, admin_user_id=user_id, segment="all", message_html="hi",
        status_chat_id=1, status_message_id=1,
    )

    assert seen_running == [True]
    assert not bc.is_broadcast_running()


@pytest.mark.asyncio
async def test_run_broadcast_reports_progress_before_final_summary(patched_broadcast_db, monkeypatch):
    import services.broadcast_service as bc

    monkeypatch.setattr(bc, "BROADCAST_DELAY_SECONDS", 0)
    monkeypatch.setattr(bc, "STATUS_UPDATE_INTERVAL_SECONDS", 0)

    u1 = await _make_user(patched_broadcast_db, 6001)
    await _make_user(patched_broadcast_db, 6002)

    bot = FakeBot()
    await bc.run_broadcast(
        bot, admin_user_id=u1, segment="all", message_html="hi",
        status_chat_id=1, status_message_id=1,
    )

    assert any("ارسال‌شده" in e for e in bot.edits[:-1])
    assert "✅" in bot.edits[-1]
    assert "موفق: 2" in bot.edits[-1]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_broadcast_service.py -v`
Expected: FAIL — `run_broadcast` / `is_broadcast_running` / `BROADCAST_DELAY_SECONDS` don't exist yet.

- [ ] **Step 3: Implement the send loop**

Append to `services/broadcast_service.py` (add these imports at the top alongside the existing ones):

```python
import asyncio
import logging
import time
from datetime import datetime, timezone

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter

from database.models import Broadcast
```

Then add, after `resolve_segment_user_ids`:

```python
logger = logging.getLogger(__name__)

BROADCAST_DELAY_SECONDS = 0.05
STATUS_UPDATE_INTERVAL_SECONDS = 5.0

_broadcast_running = False


def is_broadcast_running() -> bool:
    return _broadcast_running


async def _safe_edit_status(bot: Bot, chat_id: int, message_id: int, text: str) -> None:
    try:
        await bot.edit_message_text(text, chat_id=chat_id, message_id=message_id)
    except Exception:
        logger.exception("Failed to edit broadcast status message")


async def run_broadcast(
    bot: Bot,
    *,
    admin_user_id: int,
    segment: str,
    message_html: str,
    status_chat_id: int,
    status_message_id: int,
) -> None:
    """Send ``message_html`` to every user in ``segment``, rate-limited.

    Runs as a detached background task (see ``handlers/admin.py``). Never
    raises — every per-recipient error is caught, classified, and counted so
    one bad send can't stop the rest of the broadcast.
    """
    global _broadcast_running
    _broadcast_running = True
    try:
        target_user_ids = await resolve_segment_user_ids(segment)
        async with get_db_session() as session:
            users = list(
                await session.scalars(select(User).where(User.id.in_(target_user_ids)))
            )

        async with get_db_session() as session:
            broadcast = Broadcast(
                admin_user_id=admin_user_id,
                segment=segment,
                message_html=message_html,
                target_count=len(users),
                started_at=datetime.now(timezone.utc),
            )
            session.add(broadcast)
            await session.flush()
            await session.refresh(broadcast)
            broadcast_id = broadcast.id

        sent = blocked = failed = 0
        last_update = time.monotonic()

        for tg_user in users:
            try:
                await bot.send_message(tg_user.telegram_id, message_html, parse_mode="HTML")
                sent += 1
            except TelegramForbiddenError:
                blocked += 1
            except TelegramRetryAfter as exc:
                await asyncio.sleep(exc.retry_after)
                try:
                    await bot.send_message(tg_user.telegram_id, message_html, parse_mode="HTML")
                    sent += 1
                except Exception:
                    failed += 1
                    logger.exception("Broadcast retry failed for user %s", tg_user.telegram_id)
            except Exception:
                failed += 1
                logger.exception("Broadcast send failed for user %s", tg_user.telegram_id)

            await asyncio.sleep(BROADCAST_DELAY_SECONDS)

            now = time.monotonic()
            if now - last_update >= STATUS_UPDATE_INTERVAL_SECONDS:
                last_update = now
                await _safe_edit_status(
                    bot,
                    status_chat_id,
                    status_message_id,
                    f"🚀 در حال ارسال…\nارسال‌شده: {sent + blocked + failed}/{len(users)}",
                )

        await _safe_edit_status(
            bot,
            status_chat_id,
            status_message_id,
            f"✅ ارسال کامل شد!\nموفق: {sent}\nمسدود شده: {blocked}\nخطا: {failed}",
        )

        async with get_db_session() as session:
            row = await session.get(Broadcast, broadcast_id)
            row.sent_count = sent
            row.blocked_count = blocked
            row.failed_count = failed
            row.finished_at = datetime.now(timezone.utc)
    finally:
        _broadcast_running = False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_broadcast_service.py -v`
Expected: all 7 tests PASS

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest -q`
Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add services/broadcast_service.py tests/test_broadcast_service.py
git commit -m "feat: add rate-limited broadcast send loop with audit trail"
```

---

### Task 3: Broadcast keyboards

**Files:**
- Modify: `keyboards/admin_keyboard.py`
- Test: `tests/test_admin_keyboard.py` (new)

**Interfaces:**
- Consumes: nothing beyond `aiogram.types` — these are pure rendering functions, no service imports (matches project layering: keyboards don't depend on services).
- Produces:
  - `def broadcast_segment_keyboard(segments: list[tuple[str, str, int]]) -> InlineKeyboardMarkup` — each tuple is `(segment_key, label, count)`.
  - `def broadcast_preview_keyboard() -> InlineKeyboardMarkup`
  - `def broadcast_confirm_keyboard() -> InlineKeyboardMarkup`
  - `overview_keyboard()` (existing function) gets one new row: `📢 پیام همگانی` → `admin:bc`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_admin_keyboard.py`:

```python
"""Tests for admin dashboard keyboards, including the broadcast feature."""

from __future__ import annotations

from keyboards.admin_keyboard import (
    broadcast_confirm_keyboard,
    broadcast_preview_keyboard,
    broadcast_segment_keyboard,
    overview_keyboard,
)


def test_broadcast_segment_keyboard_builds_one_row_per_segment():
    keyboard = broadcast_segment_keyboard([
        ("all", "همه‌ی کاربران", 230),
        ("never_subscribed", "هرگز مشترک نشده", 127),
    ])
    rows = keyboard.inline_keyboard
    assert rows[0][0].callback_data == "admin:bc:seg:all"
    assert "230" in rows[0][0].text
    assert rows[1][0].callback_data == "admin:bc:seg:never_subscribed"
    assert rows[-1][0].callback_data == "admin:home"


def test_broadcast_preview_keyboard_has_test_send_and_cancel():
    keyboard = broadcast_preview_keyboard()
    callbacks = [btn.callback_data for row in keyboard.inline_keyboard for btn in row]
    assert callbacks == ["admin:bc:test", "admin:bc:go", "admin:bc:cancel"]


def test_broadcast_confirm_keyboard_has_confirm_and_cancel():
    keyboard = broadcast_confirm_keyboard()
    callbacks = [btn.callback_data for row in keyboard.inline_keyboard for btn in row]
    assert callbacks == ["admin:bc:go:confirm", "admin:bc:cancel"]


def test_overview_keyboard_includes_broadcast_entry():
    keyboard = overview_keyboard()
    callbacks = [btn.callback_data for row in keyboard.inline_keyboard for btn in row]
    assert "admin:bc" in callbacks
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_admin_keyboard.py -v`
Expected: FAIL — `ImportError: cannot import name 'broadcast_segment_keyboard'`

- [ ] **Step 3: Implement the keyboards**

In `keyboards/admin_keyboard.py`, modify `overview_keyboard()`:

```python
def overview_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 کاربران", callback_data="admin:users")],
        [InlineKeyboardButton(text="⚠️ نیاز به پیگیری", callback_data="admin:pastdue")],
        [InlineKeyboardButton(text="💳 پرداخت‌ها", callback_data="admin:pay")],
        [InlineKeyboardButton(text="📢 پیام همگانی", callback_data="admin:bc")],
    ])
```

Then append these three new functions at the end of the file:

```python
def broadcast_segment_keyboard(segments: list[tuple[str, str, int]]) -> InlineKeyboardMarkup:
    """``segments`` is a list of (segment_key, label, recipient_count)."""
    rows = [
        [
            InlineKeyboardButton(
                text=f"{label} ({count} نفر)",
                callback_data=f"admin:bc:seg:{key}",
            )
        ]
        for key, label, count in segments
    ]
    rows.append([InlineKeyboardButton(text="↩️ بازگشت", callback_data="admin:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def broadcast_preview_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧪 ارسال آزمایشی به خودم", callback_data="admin:bc:test")],
        [InlineKeyboardButton(text="🚀 ارسال نهایی", callback_data="admin:bc:go")],
        [InlineKeyboardButton(text="❌ لغو", callback_data="admin:bc:cancel")],
    ])


def broadcast_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ مطمئنم، بفرست", callback_data="admin:bc:go:confirm"),
            InlineKeyboardButton(text="↩️ انصراف", callback_data="admin:bc:cancel"),
        ],
    ])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_admin_keyboard.py -v`
Expected: all 4 tests PASS

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest -q`
Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add keyboards/admin_keyboard.py tests/test_admin_keyboard.py
git commit -m "feat: add broadcast keyboards to admin dashboard"
```

---

### Task 4: Compose flow handlers (segment pick → text → preview → test-send)

**Files:**
- Modify: `handlers/admin.py`
- Test: `tests/test_admin_broadcast_handlers.py` (new)

**Interfaces:**
- Consumes: `services.broadcast_service.SEGMENTS`, `services.broadcast_service.resolve_segment_user_ids` (Task 1); `keyboards.admin_keyboard.broadcast_segment_keyboard`, `broadcast_preview_keyboard` (Task 3); `utils.admin.is_admin`; existing `AdminStates` class.
- Produces:
  - `AdminStates.broadcast_composing` — new FSM state.
  - Callback handlers on `admin:bc` and `admin:bc:seg:<segment>`.
  - A message handler on `AdminStates.broadcast_composing` that stores `message.html_text` and shows the preview (re-sending new text while still in this state simply refreshes the preview — this doubles as the "edit before sending" path, no separate edit flow needed).
  - A callback handler on `admin:bc:test`.
  - FSM data keys used by later tasks: `segment: str`, `target_count: int`, `message_html: str`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_admin_broadcast_handlers.py`:

```python
"""Tests for the admin broadcast UI flow (compose, preview, test-send, confirm)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.base import StorageKey
from aiogram.types import CallbackQuery, Chat, Message
from aiogram.types import User as TgUser

from database.models import User
from handlers.admin import AdminStates, router as admin_router

ADMIN_TG_ID = 111  # matches ADMIN_USER_ID="111,222" set in tests/conftest.py
NON_ADMIN_TG_ID = 999


def _make_message(text: str, *, from_id: int = ADMIN_TG_ID) -> Message:
    chat = Chat(id=from_id, type="private")
    tg_user = TgUser(id=from_id, is_bot=False, first_name="Admin")
    return Message(
        message_id=1, date=datetime.now(timezone.utc), chat=chat, from_user=tg_user, text=text
    )


def _make_callback(data: str, message: Message) -> CallbackQuery:
    return CallbackQuery(
        id="1", from_user=message.from_user, chat_instance="test", data=data, message=message
    )


async def _dispatch(router: Router, state: FSMContext, event, *, bot: Bot, user: User | None):
    """Bind ``event`` (and its nested message, for callbacks) to ``bot``, then
    propagate it through the router.

    Manually-constructed Message/CallbackQuery objects have no bot bound
    (that normally happens via Pydantic's validation context when aiogram
    parses a real incoming update). Without binding, any shortcut call —
    ``message.answer()``, ``callback.message.edit_text()``, ``callback.answer()``
    — raises ``RuntimeError: This method is not mounted to any bot instance``.
    """
    if isinstance(event, CallbackQuery):
        event.as_(bot)
        if event.message is not None:
            event.message.as_(bot)
        message = event.message
        event_type = "callback_query"
    else:
        event.as_(bot)
        message = event
        event_type = "message"

    return await router.propagate_event(
        event_type,
        event,
        bot=bot,
        state=state,
        raw_state=await state.get_state(),
        event_from_user=message.from_user,
        event_chat=message.chat,
        user=user,
    )


def _fresh_state(chat_id: int = ADMIN_TG_ID) -> FSMContext:
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=chat_id, user_id=chat_id)
    return FSMContext(storage=storage, key=key)


def _mocked_bot() -> Bot:
    """A real Bot with the network layer stubbed out.

    ``Message.edit_text()``, ``CallbackQuery.answer()``, and even direct calls
    like ``bot.send_message()`` all end up calling ``await bot(method)``
    (``Bot.__call__``), which does ``return await self.session(self, method,
    timeout=...)``. Mocking individual named methods (``bot.send_message``,
    ``bot.edit_message_text``, ...) does NOT intercept the shortcut methods —
    only ``bot.session`` is common to every call path, so that's the one
    seam to stub.
    """
    bot = Bot(token="123456789:AAEEdummytokenForTestsOnly0000000000")
    bot.session = AsyncMock(return_value=True)
    return bot


def _calls(bot: Bot, method_cls: type) -> list:
    """Every TelegramMethod instance of ``method_cls`` sent through this bot.

    ``bot.session`` is called as ``session(bot, method, timeout=...)``, so
    the method instance is the second positional arg of each recorded call.
    """
    return [
        call.args[1]
        for call in bot.session.await_args_list
        if isinstance(call.args[1], method_cls)
    ]


@pytest.mark.asyncio
async def test_broadcast_menu_shows_segment_picker(monkeypatch):
    import handlers.admin as admin_module
    from aiogram.methods import EditMessageText

    async def fake_resolve(segment):
        return [1, 2, 3]

    monkeypatch.setattr(admin_module.bc, "resolve_segment_user_ids", fake_resolve)

    admin_user = User(id=1, telegram_id=ADMIN_TG_ID)
    message = _make_message("")
    callback = _make_callback("admin:bc", message)
    state = _fresh_state()
    bot = _mocked_bot()

    await _dispatch(admin_router, state, callback, bot=bot, user=admin_user)

    edits = _calls(bot, EditMessageText)
    assert edits, "expected a message edit showing the segment picker"
    assert "پیام همگانی" in edits[-1].text


@pytest.mark.asyncio
async def test_broadcast_segment_chosen_enters_composing_state(monkeypatch):
    import handlers.admin as admin_module

    async def fake_resolve(segment):
        return [1, 2] if segment == "never_subscribed" else [1, 2, 3]

    monkeypatch.setattr(admin_module.bc, "resolve_segment_user_ids", fake_resolve)

    admin_user = User(id=1, telegram_id=ADMIN_TG_ID)
    message = _make_message("")
    callback = _make_callback("admin:bc:seg:never_subscribed", message)
    state = _fresh_state()

    await _dispatch(admin_router, state, callback, bot=_mocked_bot(), user=admin_user)

    assert await state.get_state() == AdminStates.broadcast_composing.state
    data = await state.get_data()
    assert data["segment"] == "never_subscribed"
    assert data["target_count"] == 2


@pytest.mark.asyncio
async def test_composing_text_stores_html_and_shows_preview():
    admin_user = User(id=1, telegram_id=ADMIN_TG_ID)
    state = _fresh_state()
    await state.set_state(AdminStates.broadcast_composing)
    await state.update_data(segment="all", target_count=5)

    message = _make_message("<b>سلام</b> به همه")
    await _dispatch(admin_router, state, message, bot=_mocked_bot(), user=admin_user)

    data = await state.get_data()
    assert "سلام" in data["message_html"]


@pytest.mark.asyncio
async def test_non_admin_cannot_compose_broadcast():
    non_admin = User(id=2, telegram_id=NON_ADMIN_TG_ID)
    state = _fresh_state(chat_id=NON_ADMIN_TG_ID)
    await state.set_state(AdminStates.broadcast_composing)
    await state.update_data(segment="all", target_count=5)

    message = _make_message("متن مخرب", from_id=NON_ADMIN_TG_ID)
    await _dispatch(admin_router, state, message, bot=_mocked_bot(), user=non_admin)

    data = await state.get_data()
    assert "message_html" not in data


@pytest.mark.asyncio
async def test_test_send_sends_to_admins_own_chat():
    from aiogram.methods import SendMessage

    admin_user = User(id=1, telegram_id=ADMIN_TG_ID)
    state = _fresh_state()
    await state.set_state(AdminStates.broadcast_composing)
    await state.update_data(segment="all", target_count=5, message_html="<b>hi</b>")

    message = _make_message("")
    callback = _make_callback("admin:bc:test", message)
    bot = _mocked_bot()

    await _dispatch(admin_router, state, callback, bot=bot, user=admin_user)

    sends = _calls(bot, SendMessage)
    assert len(sends) == 1
    assert sends[0].chat_id == ADMIN_TG_ID
    assert sends[0].text == "<b>hi</b>"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_admin_broadcast_handlers.py -v`
Expected: FAIL — `AdminStates` has no `broadcast_composing`, no `admin:bc` handler exists yet, `handlers.admin` has no `bc` attribute.

- [ ] **Step 3: Implement the compose flow**

In `handlers/admin.py`, add these imports (alongside the existing ones):

```python
from aiogram import Bot
```

and:

```python
from keyboards.admin_keyboard import (
    broadcast_preview_keyboard,
    broadcast_segment_keyboard,
    confirm_keyboard,
    list_row_keyboard,
    overview_keyboard,
    payments_list_keyboard,
    user_profile_keyboard,
    users_menu_keyboard,
)
from services import broadcast_service as bc
```

Extend `AdminStates`:

```python
class AdminStates(StatesGroup):
    searching = State()
    broadcast_composing = State()
```

Add these handlers (place them in a new `# --- broadcast ---` section, after the `# --- payments ---` section and before `# --- pagination ---`):

```python
# --- broadcast ---------------------------------------------------------------

@router.callback_query(F.data == "admin:bc")
async def admin_broadcast_menu(callback: CallbackQuery, state: FSMContext, user: User | None) -> None:
    if user is None or not is_admin(user.telegram_id):
        await callback.answer()
        return
    await state.clear()
    segments = [
        (key, label, len(await bc.resolve_segment_user_ids(key)))
        for key, label in bc.SEGMENTS.items()
    ]
    await callback.message.edit_text(
        "📢 <b>پیام همگانی</b>\nگروه هدف رو انتخاب کن:",
        reply_markup=broadcast_segment_keyboard(segments),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:bc:seg:"))
async def admin_broadcast_segment_chosen(
    callback: CallbackQuery, state: FSMContext, user: User | None
) -> None:
    if user is None or not is_admin(user.telegram_id):
        await callback.answer()
        return
    segment = callback.data.split(":")[3]
    target_count = len(await bc.resolve_segment_user_ids(segment))
    await state.set_state(AdminStates.broadcast_composing)
    await state.update_data(segment=segment, target_count=target_count)
    await callback.message.edit_text(
        f"✍️ متن پیام رو بفرست (گیرنده‌ها: {target_count} نفر).\n"
        "فرمت بولد/ایتالیک تلگرام حفظ می‌شه."
    )
    await callback.answer()


@router.message(AdminStates.broadcast_composing)
async def admin_broadcast_text_received(
    message: Message, state: FSMContext, user: User | None
) -> None:
    if user is None or not is_admin(user.telegram_id):
        await _denied(message)
        return
    html_text = message.html_text or ""
    await state.update_data(message_html=html_text)
    data = await state.get_data()
    await message.answer(
        f"👀 <b>پیش‌نمایش</b> (برای {data['target_count']} نفر):\n\n{html_text}\n\n"
        "می‌تونی متن جدیدی بفرستی تا جایگزین بشه، یا یکی از گزینه‌های زیر رو انتخاب کن.",
        reply_markup=broadcast_preview_keyboard(),
    )


@router.callback_query(F.data == "admin:bc:test")
async def admin_broadcast_test_send(
    callback: CallbackQuery, state: FSMContext, user: User | None, bot: Bot
) -> None:
    if user is None or not is_admin(user.telegram_id):
        await callback.answer()
        return
    data = await state.get_data()
    html_text = data.get("message_html", "")
    await bot.send_message(user.telegram_id, html_text, parse_mode="HTML")
    await callback.answer("✅ برای خودت فرستاده شد.", show_alert=True)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_admin_broadcast_handlers.py -v`
Expected: all 5 tests PASS

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest -q`
Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add handlers/admin.py tests/test_admin_broadcast_handlers.py
git commit -m "feat: add broadcast compose/preview/test-send flow to admin dashboard"
```

---

### Task 5: Final confirmation + background launch + concurrency guard

**Files:**
- Modify: `handlers/admin.py`
- Test: `tests/test_admin_broadcast_handlers.py` (append)

**Interfaces:**
- Consumes: `services.broadcast_service.is_broadcast_running`, `services.broadcast_service.run_broadcast` (Task 2); `keyboards.admin_keyboard.broadcast_confirm_keyboard` (Task 3); `AdminStates.broadcast_composing` (Task 4).
- Produces: callback handlers on `admin:bc:go`, `admin:bc:cancel`, `admin:bc:go:confirm`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_admin_broadcast_handlers.py`:

```python
import asyncio

from keyboards.admin_keyboard import broadcast_confirm_keyboard  # noqa: F401 (import sanity)


@pytest.mark.asyncio
async def test_confirm_prompt_shows_final_confirmation():
    from aiogram.methods import EditMessageText

    admin_user = User(id=1, telegram_id=ADMIN_TG_ID)
    state = _fresh_state()
    await state.set_state(AdminStates.broadcast_composing)
    await state.update_data(segment="all", target_count=7, message_html="hi")

    message = _make_message("")
    callback = _make_callback("admin:bc:go", message)
    bot = _mocked_bot()

    await _dispatch(admin_router, state, callback, bot=bot, user=admin_user)

    edits = _calls(bot, EditMessageText)
    assert edits, "expected the final confirmation prompt to be shown"
    assert "7 نفر" in edits[-1].text


@pytest.mark.asyncio
async def test_cancel_returns_to_overview_and_clears_state():
    admin_user = User(id=1, telegram_id=ADMIN_TG_ID)
    state = _fresh_state()
    await state.set_state(AdminStates.broadcast_composing)
    await state.update_data(segment="all", target_count=7, message_html="hi")

    message = _make_message("")
    callback = _make_callback("admin:bc:cancel", message)

    await _dispatch(admin_router, state, callback, bot=_mocked_bot(), user=admin_user)

    assert await state.get_state() is None


@pytest.mark.asyncio
async def test_confirm_launches_background_broadcast(monkeypatch):
    import handlers.admin as admin_module

    run_broadcast_mock = AsyncMock(return_value=None)
    monkeypatch.setattr(admin_module.bc, "run_broadcast", run_broadcast_mock)
    monkeypatch.setattr(admin_module.bc, "is_broadcast_running", lambda: False)

    admin_user = User(id=1, telegram_id=ADMIN_TG_ID)
    state = _fresh_state()
    await state.set_state(AdminStates.broadcast_composing)
    await state.update_data(segment="never_subscribed", target_count=127, message_html="<b>hi</b>")

    message = _make_message("")
    callback = _make_callback("admin:bc:go:confirm", message)
    bot = _mocked_bot()

    await _dispatch(admin_router, state, callback, bot=bot, user=admin_user)
    await asyncio.sleep(0.05)  # let the scheduled background task run

    run_broadcast_mock.assert_awaited_once()
    _, kwargs = run_broadcast_mock.call_args
    assert kwargs["admin_user_id"] == 1
    assert kwargs["segment"] == "never_subscribed"
    assert kwargs["message_html"] == "<b>hi</b>"
    assert await state.get_state() is None


@pytest.mark.asyncio
async def test_confirm_rejects_when_broadcast_already_running(monkeypatch):
    import handlers.admin as admin_module
    from aiogram.methods import AnswerCallbackQuery

    run_broadcast_mock = AsyncMock(return_value=None)
    monkeypatch.setattr(admin_module.bc, "run_broadcast", run_broadcast_mock)
    monkeypatch.setattr(admin_module.bc, "is_broadcast_running", lambda: True)

    admin_user = User(id=1, telegram_id=ADMIN_TG_ID)
    state = _fresh_state()
    await state.set_state(AdminStates.broadcast_composing)
    await state.update_data(segment="all", target_count=230, message_html="hi")

    message = _make_message("")
    callback = _make_callback("admin:bc:go:confirm", message)
    bot = _mocked_bot()

    await _dispatch(admin_router, state, callback, bot=bot, user=admin_user)
    await asyncio.sleep(0.05)

    run_broadcast_mock.assert_not_awaited()
    answers = _calls(bot, AnswerCallbackQuery)
    assert answers, "expected an alert telling the admin a broadcast is already running"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_admin_broadcast_handlers.py -v`
Expected: FAIL — no handler for `admin:bc:go` / `admin:bc:cancel` / `admin:bc:go:confirm` yet.

- [ ] **Step 3: Implement confirm + launch**

Add `import asyncio` at the top of `handlers/admin.py` (alongside the existing `from datetime import datetime`).

Add these handlers after `admin_broadcast_test_send` (still inside the `# --- broadcast ---` section):

```python
@router.callback_query(F.data == "admin:bc:go")
async def admin_broadcast_confirm_prompt(
    callback: CallbackQuery, state: FSMContext, user: User | None
) -> None:
    if user is None or not is_admin(user.telegram_id):
        await callback.answer()
        return
    data = await state.get_data()
    await callback.message.edit_text(
        f"مطمئنی می‌خوای این پیام رو برای <b>{data['target_count']} نفر</b> بفرستی؟",
        reply_markup=broadcast_confirm_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:bc:cancel")
async def admin_broadcast_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(await _overview_text(), reply_markup=overview_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:bc:go:confirm")
async def admin_broadcast_launch(
    callback: CallbackQuery, state: FSMContext, user: User | None, bot: Bot
) -> None:
    if user is None or not is_admin(user.telegram_id):
        await callback.answer()
        return
    if bc.is_broadcast_running():
        await callback.answer("⏳ یه ارسال همگانی دیگه در حال اجراست.", show_alert=True)
        return

    data = await state.get_data()
    segment, html_text = data["segment"], data["message_html"]
    await state.clear()
    await callback.message.edit_text("🚀 در حال ارسال…")
    await callback.answer()

    asyncio.create_task(
        bc.run_broadcast(
            bot,
            admin_user_id=user.id,
            segment=segment,
            message_html=html_text,
            status_chat_id=callback.message.chat.id,
            status_message_id=callback.message.message_id,
        )
    )
```

Update `keyboards/admin_keyboard` import line in `handlers/admin.py` to also include `broadcast_confirm_keyboard`:

```python
from keyboards.admin_keyboard import (
    broadcast_confirm_keyboard,
    broadcast_preview_keyboard,
    broadcast_segment_keyboard,
    confirm_keyboard,
    list_row_keyboard,
    overview_keyboard,
    payments_list_keyboard,
    user_profile_keyboard,
    users_menu_keyboard,
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_admin_broadcast_handlers.py -v`
Expected: all 9 tests PASS

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest -q`
Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add handlers/admin.py tests/test_admin_broadcast_handlers.py
git commit -m "feat: add broadcast confirm/launch flow and concurrency guard"
```

---

## Post-plan: deployment

Not part of this plan's tasks (no test cycle applies to a deploy step). Once
all 5 tasks are merged, follow the existing deploy pattern (same as previous
sessions): re-tar the changed directories to `/opt/nlern-bot`, `docker build
-f deploy/Dockerfile.bot -t nlern-bot .`, `docker rm -f nlern-bot` + re-run
with the existing `--env-file`. The new `broadcasts` table is created
automatically by `init_db()` on startup — no manual migration needed. Do a
real 🧪 test-send to the admin's own chat before ever approving a real
broadcast to a live segment.
