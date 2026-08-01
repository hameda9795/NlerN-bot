"""Regression test: pressing a main-menu button while a "catch every message"
FSM state is active (contact-admin relay, AI chat, voice recording, ...) must
abandon that state and let the pressed button's own handler run — not
swallow the button press as if it were free-form input for the old state.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from aiogram import Bot, Router
from aiogram.dispatcher.event.bases import UNHANDLED
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Chat, Message
from aiogram.types import User as TgUser

from handlers.ai_chat import ChatStates, router as ai_chat_router
from handlers.contact_admin import ContactStates, router as contact_router
from handlers.sentence_check import SentenceStates, router as sentence_router
from keyboards.main_menu import BTN_SAVED_WORDS, BTN_VAJEGAN


def _make_message(text: str) -> Message:
    chat = Chat(id=100, type="private")
    user = TgUser(id=100, is_bot=False, first_name="Test")
    return Message(
        message_id=1,
        date=datetime.now(timezone.utc),
        chat=chat,
        from_user=user,
        text=text,
    )


async def _dispatch(router: Router, state: FSMContext, message: Message) -> object:
    bot = Bot(token="123456789:AAEEdummytokenForTestsOnly0000000000")
    return await router.propagate_event(
        "message",
        message,
        bot=bot,
        state=state,
        raw_state=await state.get_state(),
        event_from_user=message.from_user,
        event_chat=message.chat,
        user=None,
    )


@pytest.mark.parametrize(
    "router,active_state,button_text",
    [
        (contact_router, ContactStates.messaging, BTN_VAJEGAN),
        (ai_chat_router, ChatStates.chatting, BTN_VAJEGAN),
        (sentence_router, SentenceStates.recording, BTN_SAVED_WORDS),
    ],
    ids=["contact_admin", "ai_chat", "sentence_check"],
)
@pytest.mark.asyncio
async def test_menu_button_escapes_stuck_state(
    router: Router, active_state: State, button_text: str
) -> None:
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=100, user_id=100)
    state = FSMContext(storage=storage, key=key)
    await state.set_state(active_state)

    message = _make_message(button_text)
    result = await _dispatch(router, state, message)

    # The state's own router must NOT claim the update (so the pressed
    # button's actual router further down the chain gets a chance) ...
    assert result is UNHANDLED
    # ... and must give up its state so a later free-text message isn't
    # swallowed by the old flow either.
    assert await state.get_state() is None
