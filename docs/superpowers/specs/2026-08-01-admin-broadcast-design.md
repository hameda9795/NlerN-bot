# Admin Broadcast — Design Spec

**Date:** 2026-08-01
**Status:** Approved for planning

## Problem

The admin has no way to message all (or a segment of) bot users at once — e.g. to
nudge the 127 users who never started a free trial, or to announce something to
everyone. This adds a "send one message to many users" capability to the
existing in-bot admin dashboard (`handlers/admin.py`).

## Goals

- Admin can compose one message and send it to a chosen segment of users.
- Admin can test-send to themselves before committing to the real broadcast.
- Sending never risks a Telegram rate-limit ban and degrades gracefully when
  individual users have blocked the bot.
- Every broadcast is auditable after the fact (who sent what, to how many, with
  what result).

## Non-goals (v1, YAGNI)

- No media/photo broadcasts — text only (with Telegram bold/italic formatting).
- No inline buttons/CTAs inside the broadcast message.
- No scheduling ("send at 6pm tomorrow") — sends immediately after final
  confirmation.
- No custom/ad-hoc audience beyond the four predefined segments below.

## User flow

1. Admin dashboard (`/admin`) gets a new button: **📢 پیام همگانی**.
2. Segment picker (inline keyboard), each showing a live recipient count:
   - همه‌ی کاربران (all users)
   - هرگز مشترک نشده (never started a subscription/trial — the 127-user segment)
   - trial/اشتراک منقضی‌شده (had a subscription row that is not currently active —
     covers expired trials and lapsed paid subs)
   - مشترک فعال الان (currently has access right now, per `subs.is_active()`)
3. Admin sends the message text. Telegram bold/italic/etc. formatting is
   preserved via `message.html_text` (aiogram 3 renders entities as HTML), so
   the same text can be re-sent later with `parse_mode=HTML`.
4. Preview screen: recipient count + rendered preview + three buttons:
   - **🧪 ارسال آزمایشی به خودم** — sends the exact message to the admin's own
     chat only; re-shows the same preview screen afterward (repeatable).
   - **🚀 ارسال نهایی** — proceeds to final confirmation.
   - **❌ لغو** — aborts, returns to admin home.
5. Final confirmation (same "مطمئنی؟" pattern already used for extend/cancel):
   "مطمئنی می‌خوای این پیام رو برای N نفر بفرستی؟" with ✅/↩️.
6. On confirm: the status message is immediately edited to "🚀 در حال ارسال به N
   نفر…" and a background `asyncio.Task` starts the actual send loop. The admin
   is free to keep using the dashboard while it runs.
7. The status message is edited periodically (every 5s) with progress
   ("ارسال‌شده: 140/230"), and once with the final summary:
   "✅ ارسال کامل شد!\nموفق: X\nمسدود شده: Y\nخطا: Z"
8. While one broadcast is running, the "📢 پیام همگانی" entry point is blocked
   (a module-level in-memory flag) — only one broadcast admin action, so a
   simple flag is enough; no distributed lock needed.

## Data model (`database/models.py`)

New `Broadcast` table — audit trail, one row per broadcast attempt (same
pattern as `Payment` / `BlockedAccessEvent`):

```python
class Broadcast(Base):
    __tablename__ = "broadcasts"

    id: Mapped[int]
    admin_user_id: Mapped[int]        # FK -> users.id
    segment: Mapped[str]              # "all" | "never_subscribed" | "lapsed" | "active"
    message_html: Mapped[str]         # Text
    target_count: Mapped[int]
    sent_count: Mapped[int]           # default 0, updated as it progresses
    blocked_count: Mapped[int]        # default 0
    failed_count: Mapped[int]         # default 0
    started_at: Mapped[datetime]
    finished_at: Mapped[datetime | None]  # null while in progress
```

New table → created automatically by `init_db()` (`Base.metadata.create_all`)
on the next bot restart/deploy, same as `blocked_access_events` — no manual
migration script needed.

## Service layer (`services/broadcast_service.py` — new module)

Kept separate from `admin_service.py` because it needs a live `Bot` instance
to actually send messages, not just DB reads — a different kind of dependency
than the rest of that module's read-only aggregate queries.

- `SEGMENTS = {"all": ..., "never_subscribed": ..., "lapsed": ..., "active": ...}`
  — human labels for the keyboard.
- `async def resolve_segment_user_ids(segment: str) -> list[int]` — returns the
  target `User.id` list. Reuses `subscription_service.is_active()` semantics:
  - `all` → every `User.id`.
  - `never_subscribed` → users with no `Subscription` row at all.
  - `lapsed` → users with a `Subscription` row where `is_active()` is False.
  - `active` → users with a `Subscription` row where `is_active()` is True.
- `async def run_broadcast(bot: Bot, *, admin_user_id: int, segment: str, message_html: str, status_chat_id: int, status_message_id: int) -> None`
  — the background task body:
  - Creates the `Broadcast` row up front (`started_at=now`, counts at 0).
  - Loads target `telegram_id`s fresh from DB (not a stale count from step 2).
  - For each recipient, in order:
    - `await bot.send_message(chat_id, message_html, parse_mode="HTML")`
    - `await asyncio.sleep(BROADCAST_DELAY_SECONDS)` — **0.05s (20 msg/s)**,
      comfortably under Telegram's ~30 msg/s global cap.
    - `TelegramForbiddenError` (user blocked the bot / deleted account) →
      `blocked_count += 1`, continue — not treated as a failure.
    - `TelegramRetryAfter` (429 flood control) → `await asyncio.sleep(e.retry_after)`,
      retry that one recipient once; if it fails again, count as `failed_count += 1`
      and move on. The rest of the queue is never blocked by one recipient's
      retry.
    - Any other exception → `failed_count += 1`, `logger.exception(...)`,
      continue (never let one bad send kill the whole broadcast).
    - Every 5 seconds (wall-clock), edit the status message with progress.
  - On completion, edit the status message with the final summary and set
    `finished_at`, `sent_count`, `blocked_count`, `failed_count` on the
    `Broadcast` row.
- Module-level `_broadcast_running: bool` flag, set True before the loop
  starts and False in a `finally` block — checked by the handler before
  allowing a new broadcast to start.

## UI layer (`handlers/admin.py` + `keyboards/admin_keyboard.py`)

- `AdminStates.broadcast_composing` — new FSM state, waiting for the message
  text after a segment is picked (segment stored via `state.update_data`).
- New callback-data prefix `admin:bc:*`:
  - `admin:bc` → open segment picker
  - `admin:bc:seg:<segment>` → segment chosen, prompt for text, enter
    `broadcast_composing`
  - `admin:bc:test` → test-send to self
  - `admin:bc:go` → show final "مطمئنی؟" confirmation
  - `admin:bc:go:confirm` → launch the background task
  - `admin:bc:cancel` → abort, back to admin home
- New keyboards in `keyboards/admin_keyboard.py`:
  - `broadcast_segment_keyboard(counts: dict[str, int])`
  - `broadcast_preview_keyboard()` — test / send / cancel row
  - Reuse the existing "مطمئنی" confirm pattern for the final step (a small
    dedicated keyboard rather than overloading `confirm_keyboard`, since that
    one's cancel button is hardcoded to a user-profile callback which doesn't
    apply here).
- `overview_keyboard()` gets one new row: «📢 پیام همگانی» → `admin:bc`.

## Error handling summary

| Situation | Handling |
|---|---|
| Recipient blocked the bot | Counted as `blocked_count`, not fatal |
| Telegram flood-control (429) | Sleep `retry_after`, retry once, else count as `failed_count` |
| Any other send error | Logged, counted as `failed_count`, loop continues |
| Two broadcasts triggered near-simultaneously | Second one rejected via the `_broadcast_running` flag with a short admin-facing message |
| Bot restarts mid-broadcast | In-progress `Broadcast` row is left with `finished_at=None` — visible as an anomaly if ever queried; not auto-resumed (acceptable at this scale, no user-facing impact beyond an incomplete send) |

## Testing

- Unit tests for `resolve_segment_user_ids` covering all four segments against
  a small fixture set (never-subscribed / lapsed / currently-active users),
  mirroring the real production shapes already observed via SQL.
- Unit tests for `run_broadcast`'s error classification using a fake `Bot`
  whose `send_message` raises `TelegramForbiddenError` / `TelegramRetryAfter` /
  a generic exception for specific recipients — assert final counts are
  correct and the loop doesn't stop early.
- Manual test: run a real test-send to the admin's own chat before ever
  approving a real broadcast (this is precisely what the 🧪 button is for).

## Deployment note

Same pattern as previous deploys: re-tar changed dirs to `/opt/nlern-bot`,
`docker build -f deploy/Dockerfile.bot`, `docker rm -f` + re-run. The new
`broadcasts` table is created automatically by `init_db()` on startup.
