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
async def test_cancel_returns_to_overview_and_clears_state(monkeypatch):
    # `_overview_text()` (rendered on cancel) hits real DB-backed service
    # calls; stub them out the same way `admin_module.bc.*` is stubbed
    # elsewhere in this file, so this stays a focused handler-behavior test.
    import handlers.admin as admin_module

    monkeypatch.setattr(admin_module.admin_service, "count_users", AsyncMock(return_value=0))
    monkeypatch.setattr(
        admin_module.admin_service,
        "count_by_subscription_status",
        AsyncMock(
            return_value={
                "active": 0,
                "trialing": 0,
                "past_due": 0,
                "canceled": 0,
                "pending": 0,
                "expired": 0,
                "none": 0,
            }
        ),
    )
    monkeypatch.setattr(
        admin_module.admin_service, "revenue_this_month", AsyncMock(return_value=0.0)
    )

    admin_user = User(id=1, telegram_id=ADMIN_TG_ID)
    state = _fresh_state()
    await state.set_state(AdminStates.broadcast_composing)
    await state.update_data(segment="all", target_count=7, message_html="hi")

    message = _make_message("")
    callback = _make_callback("admin:bc:cancel", message)

    await _dispatch(admin_router, state, callback, bot=_mocked_bot(), user=admin_user)

    assert await state.get_state() is None


@pytest.mark.asyncio
async def test_non_admin_cannot_cancel_broadcast():
    # admin_broadcast_cancel must re-check is_admin like every other handler
    # in this file, even though it only clears state and shows the overview.
    non_admin = User(id=2, telegram_id=NON_ADMIN_TG_ID)
    state = _fresh_state(chat_id=NON_ADMIN_TG_ID)
    await state.set_state(AdminStates.broadcast_composing)
    await state.update_data(segment="all", target_count=7, message_html="hi")

    message = _make_message("", from_id=NON_ADMIN_TG_ID)
    callback = _make_callback("admin:bc:cancel", message)

    await _dispatch(admin_router, state, callback, bot=_mocked_bot(), user=non_admin)

    # state must NOT be cleared for a rejected non-admin request
    assert await state.get_state() == AdminStates.broadcast_composing.state


@pytest.mark.asyncio
async def test_confirm_launches_background_broadcast(monkeypatch):
    import handlers.admin as admin_module

    run_broadcast_mock = AsyncMock(return_value=None)
    monkeypatch.setattr(admin_module.bc, "run_broadcast", run_broadcast_mock)
    monkeypatch.setattr(admin_module.bc, "try_start_broadcast", lambda: True)

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
    monkeypatch.setattr(admin_module.bc, "try_start_broadcast", lambda: False)

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
    # rejected path must leave FSM state untouched (nothing was sent, so the
    # admin should still be able to retry from the same confirmation screen)
    assert await state.get_state() == AdminStates.broadcast_composing.state
    data = await state.get_data()
    assert data["segment"] == "all"
    assert data["target_count"] == 230
    assert data["message_html"] == "hi"


@pytest.mark.asyncio
async def test_broadcast_menu_blocked_when_broadcast_running(monkeypatch):
    """Bonus fix: the spec calls for blocking at the ENTRY POINT ("📢 پیام
    همگانی" button), not just at the final confirm tap. Task 5 only guarded
    admin:bc:go:confirm; admin:bc (the menu/segment-picker entry point) must
    also refuse to open while a broadcast is running.
    """
    import handlers.admin as admin_module
    from aiogram.methods import AnswerCallbackQuery, EditMessageText

    monkeypatch.setattr(admin_module.bc, "is_broadcast_running", lambda: True)

    admin_user = User(id=1, telegram_id=ADMIN_TG_ID)
    message = _make_message("")
    callback = _make_callback("admin:bc", message)
    state = _fresh_state()
    bot = _mocked_bot()

    await _dispatch(admin_router, state, callback, bot=bot, user=admin_user)

    answers = _calls(bot, AnswerCallbackQuery)
    assert any(getattr(a, "show_alert", False) for a in answers), (
        "expected an alert telling the admin a broadcast is already running"
    )
    edits = _calls(bot, EditMessageText)
    assert not edits, "segment picker must not be shown while a broadcast is running"


@pytest.mark.asyncio
async def test_composing_empty_text_rejected_no_preview():
    """Finding 2 regression: message.html_text falls back to "" for a
    sticker/voice-note/photo-without-caption (it never raises, never returns
    None). Sending such a message during compose must NOT be accepted as the
    broadcast text or advance to the preview screen.
    """
    from aiogram.methods import SendMessage

    admin_user = User(id=1, telegram_id=ADMIN_TG_ID)
    state = _fresh_state()
    await state.set_state(AdminStates.broadcast_composing)
    await state.update_data(segment="all", target_count=5)

    # text="" mirrors what message.html_text resolves to for a non-text message
    message = _make_message("")
    bot = _mocked_bot()

    await _dispatch(admin_router, state, message, bot=bot, user=admin_user)

    data = await state.get_data()
    assert "message_html" not in data
    # still composing -- the admin can just send real text next
    assert await state.get_state() == AdminStates.broadcast_composing.state

    sends = _calls(bot, SendMessage)
    assert sends, "expected a rejection message telling the admin to send text"
    assert "خالی" in sends[0].text


@pytest.mark.asyncio
async def test_test_send_failure_shows_alert_not_uncaught():
    """Finding 2 regression: a TelegramAPIError from the test-send (e.g. an
    empty message body Telegram rejects) must be reported to the admin via a
    show_alert callback answer, not left to propagate uncaught.
    """
    from aiogram.exceptions import TelegramAPIError
    from aiogram.methods import AnswerCallbackQuery, SendMessage

    admin_user = User(id=1, telegram_id=ADMIN_TG_ID)
    state = _fresh_state()
    await state.set_state(AdminStates.broadcast_composing)
    await state.update_data(segment="all", target_count=5, message_html="<b>hi</b>")

    message = _make_message("")
    callback = _make_callback("admin:bc:test", message)
    bot = _mocked_bot()

    async def failing_session(bot_arg, method, timeout=None):
        if isinstance(method, SendMessage):
            raise TelegramAPIError(method=method, message="bad request")
        return True

    bot.session = AsyncMock(side_effect=failing_session)

    await _dispatch(admin_router, state, callback, bot=bot, user=admin_user)

    answers = _calls(bot, AnswerCallbackQuery)
    assert answers, "expected an alert callback answer instead of an uncaught exception"
    assert any(getattr(a, "show_alert", False) for a in answers)


@pytest.mark.asyncio
async def test_confirm_rejects_expired_fsm_state_without_claiming_slot(monkeypatch):
    """Finding 1 regression: an empty/expired FSM state at confirm time (the
    bot uses MemoryStorage, wiped on every deploy, while a stale confirm
    keyboard could still be on-screen and tappable) must be rejected BEFORE
    try_start_broadcast() is ever called -- otherwise the concurrency slot
    would be claimed with no task ever scheduled to release it, wedging every
    future broadcast attempt until process restart.
    """
    import handlers.admin as admin_module
    from aiogram.methods import AnswerCallbackQuery

    monkeypatch.setattr(admin_module.bc, "_broadcast_running", False)
    run_broadcast_mock = AsyncMock(return_value=None)
    monkeypatch.setattr(admin_module.bc, "run_broadcast", run_broadcast_mock)

    admin_user = User(id=1, telegram_id=ADMIN_TG_ID)
    state = _fresh_state()  # segment/message_html never set

    message = _make_message("")
    callback = _make_callback("admin:bc:go:confirm", message)
    bot = _mocked_bot()

    await _dispatch(admin_router, state, callback, bot=bot, user=admin_user)

    answers = _calls(bot, AnswerCallbackQuery)
    assert any(getattr(a, "show_alert", False) for a in answers)
    run_broadcast_mock.assert_not_awaited()
    # the slot must not have been claimed at all
    assert not admin_module.bc.is_broadcast_running()

    # Proof the slot wasn't left claimed: an immediate, valid confirm succeeds.
    state2 = _fresh_state()
    await state2.set_state(AdminStates.broadcast_composing)
    await state2.update_data(segment="all", target_count=5, message_html="hi")
    callback2 = _make_callback("admin:bc:go:confirm", _make_message(""))

    await _dispatch(admin_router, state2, callback2, bot=_mocked_bot(), user=admin_user)
    await asyncio.sleep(0.05)

    run_broadcast_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_confirm_launch_releases_slot_on_exception_before_task_creation(monkeypatch):
    """Finding 1 regression: if anything raises between claiming the slot
    (try_start_broadcast) and successfully scheduling run_broadcast via
    asyncio.create_task, the handler must release the slot before re-raising
    -- otherwise the exception's `finally` never runs (there is no task, so
    run_broadcast's own finally never fires either) and the slot stays
    claimed forever.
    """
    import handlers.admin as admin_module
    from aiogram.methods import EditMessageText

    monkeypatch.setattr(admin_module.bc, "_broadcast_running", False)
    run_broadcast_mock = AsyncMock(return_value=None)
    monkeypatch.setattr(admin_module.bc, "run_broadcast", run_broadcast_mock)

    admin_user = User(id=1, telegram_id=ADMIN_TG_ID)
    state = _fresh_state()
    await state.set_state(AdminStates.broadcast_composing)
    await state.update_data(segment="all", target_count=5, message_html="hi")

    message = _make_message("")
    callback = _make_callback("admin:bc:go:confirm", message)
    bot = _mocked_bot()

    # Force a failure between the claim and asyncio.create_task(...): the
    # handler's `callback.message.edit_text("🚀 در حال ارسال…")` call is what
    # sits between try_start_broadcast() and asyncio.create_task().
    async def failing_session(bot_arg, method, timeout=None):
        if isinstance(method, EditMessageText):
            raise RuntimeError("boom")
        return True

    bot.session = AsyncMock(side_effect=failing_session)

    with pytest.raises(RuntimeError, match="boom"):
        await _dispatch(admin_router, state, callback, bot=bot, user=admin_user)

    run_broadcast_mock.assert_not_awaited()
    assert not admin_module.bc.is_broadcast_running()


@pytest.mark.asyncio
async def test_confirm_launch_closes_double_tap_race(monkeypatch):
    """Two back-to-back taps of "✅ مطمئنم، بفرست" (e.g. before the keyboard
    visually updates) must not both schedule a broadcast. `run_broadcast` is
    mocked so its own `finally: _broadcast_running = False` never runs — the
    real `try_start_broadcast()` (not mocked) must still block the second tap
    because it claims the slot synchronously, before either dispatch call
    returns to the caller.
    """
    import handlers.admin as admin_module
    from aiogram.methods import AnswerCallbackQuery

    # Force a clean starting slate regardless of what earlier tests left
    # behind; monkeypatch restores this to its pre-test value automatically,
    # so this can't leak into other tests either.
    monkeypatch.setattr(admin_module.bc, "_broadcast_running", False)

    run_broadcast_mock = AsyncMock(return_value=None)
    monkeypatch.setattr(admin_module.bc, "run_broadcast", run_broadcast_mock)
    # try_start_broadcast is intentionally left real (not mocked): the whole
    # point of this test is to prove *it* is what closes the race.

    admin_user = User(id=1, telegram_id=ADMIN_TG_ID)
    state = _fresh_state()
    await state.set_state(AdminStates.broadcast_composing)
    await state.update_data(segment="all", target_count=42, message_html="hi")

    message = _make_message("")
    bot = _mocked_bot()

    first_tap = _make_callback("admin:bc:go:confirm", message)
    await _dispatch(admin_router, state, first_tap, bot=bot, user=admin_user)

    # Second tap: the first dispatch already cleared FSM state, exactly like
    # it would once the real send is underway. try_start_broadcast() must
    # reject this call before it ever reads segment/message_html from state.
    second_tap = _make_callback("admin:bc:go:confirm", message)
    await _dispatch(admin_router, state, second_tap, bot=bot, user=admin_user)

    await asyncio.sleep(0.05)

    run_broadcast_mock.assert_awaited_once()
    answers = _calls(bot, AnswerCallbackQuery)
    assert any(getattr(a, "show_alert", False) for a in answers), (
        "expected the second tap to be rejected with a show_alert callback answer"
    )
