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
