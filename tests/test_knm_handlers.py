"""The KNM exam's Telegram flow: group menu, question, feedback, reset."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import AnswerCallbackQuery, EditMessageText, SendMessage
from aiogram.types import CallbackQuery, Chat, Message
from aiogram.types import User as TgUser
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import KnmQuestion, User
from handlers.knm import KnmStates, router as knm_router
from keyboards.main_menu import BTN_KNM
from services import knm_service as knm
from tests.test_knm_service import _question

TG_ID = 555


@pytest.fixture
def knm_db(monkeypatch, session_factory):
    @asynccontextmanager
    async def fake_session() -> AsyncIterator[AsyncSession]:
        session = session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    monkeypatch.setattr(knm, "get_db_session", fake_session)
    return fake_session


@pytest.fixture
async def seeded(knm_db, session_factory):
    """A user plus 45 questions — group 0 has 40, group 1 has 5."""
    async with session_factory() as session:
        user = User(id=1, telegram_id=TG_ID, first_name="Test")
        session.add(user)
        session.add_all([_question(position) for position in range(45)])
        await session.commit()
    return User(id=1, telegram_id=TG_ID, first_name="Test")


def _make_message(text: str) -> Message:
    return Message(
        message_id=1,
        date=datetime.now(timezone.utc),
        chat=Chat(id=TG_ID, type="private"),
        from_user=TgUser(id=TG_ID, is_bot=False, first_name="Test"),
        text=text,
    )


def _make_callback(data: str, message: Message) -> CallbackQuery:
    return CallbackQuery(
        id="1", from_user=message.from_user, chat_instance="t", data=data, message=message
    )


def _mocked_bot() -> Bot:
    bot = Bot(token="42:TEST")
    bot.session = AsyncMock()
    bot.session.side_effect = lambda _bot, method, timeout=None: None
    return bot


def _calls(bot: Bot, method_type) -> list:
    return [
        call.args[1]
        for call in bot.session.await_args_list
        if isinstance(call.args[1], method_type)
    ]


def _fresh_state() -> FSMContext:
    return FSMContext(
        storage=MemoryStorage(), key=StorageKey(bot_id=1, chat_id=TG_ID, user_id=TG_ID)
    )


async def _dispatch(router: Router, state: FSMContext, event, *, bot: Bot, user: User):
    if isinstance(event, CallbackQuery):
        event.as_(bot)
        if event.message is not None:
            event.message.as_(bot)
        message, event_type = event.message, "callback_query"
    else:
        event.as_(bot)
        message, event_type = event, "message"
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


@pytest.mark.asyncio
async def test_menu_button_lists_every_group_with_progress(seeded):
    bot = _mocked_bot()

    await _dispatch(knm_router, _fresh_state(), _make_message(BTN_KNM), bot=bot, user=seeded)

    sent = _calls(bot, SendMessage)
    assert len(sent) == 1
    rows = sent[0].reply_markup.inline_keyboard
    assert [row[0].callback_data for row in rows] == ["knm:grp:0", "knm:grp:1"]
    assert "دسته 1 · 1–40" in rows[0][0].text
    assert "دسته 2 · 41–45" in rows[1][0].text
    assert "شروع نشده" in rows[0][0].text


@pytest.mark.asyncio
async def test_choosing_a_group_serves_its_first_question(seeded):
    bot = _mocked_bot()
    state = _fresh_state()

    await _dispatch(
        knm_router, state, _make_callback("knm:grp:1", _make_message("")), bot=bot, user=seeded
    )

    edit = _calls(bot, EditMessageText)[0]
    assert "دسته 2 · سؤال 1 از 5" in edit.text
    assert "Vraag 40?" in edit.text
    assert [b.callback_data for b in edit.reply_markup.inline_keyboard[0]] == [
        "knm:ans:A", "knm:ans:B", "knm:ans:C"
    ]
    assert await state.get_state() == KnmStates.answering.state


@pytest.mark.asyncio
async def test_correct_answer_shows_explanation_and_records_progress(seeded):
    bot = _mocked_bot()
    state = _fresh_state()
    message = _make_message("")
    await _dispatch(knm_router, state, _make_callback("knm:grp:1", message), bot=bot, user=seeded)

    await _dispatch(knm_router, state, _make_callback("knm:ans:B", message), bot=bot, user=seeded)

    edit = _calls(bot, EditMessageText)[-1]
    assert "✅ <b>درست!</b>" in edit.text
    assert "دو" in edit.text  # the chosen option's Persian feedback
    assert "💡 توضیح فارسی" in edit.text
    assert "📖 MAP: ماژول" in edit.text
    assert _calls(bot, AnswerCallbackQuery)[-1].text == "✅"
    assert (await knm.get_group(user_id=seeded.id, group=1)).answered == 1


@pytest.mark.asyncio
async def test_wrong_answer_reveals_the_correct_option(seeded):
    bot = _mocked_bot()
    state = _fresh_state()
    message = _make_message("")
    await _dispatch(knm_router, state, _make_callback("knm:grp:1", message), bot=bot, user=seeded)

    await _dispatch(knm_router, state, _make_callback("knm:ans:A", message), bot=bot, user=seeded)

    edit = _calls(bot, EditMessageText)[-1]
    assert "❌ <b>اشتباه بود.</b>" in edit.text
    assert "B) Tweede" in edit.text
    group = await knm.get_group(user_id=seeded.id, group=1)
    assert (group.answered, group.correct) == (1, 0)


@pytest.mark.asyncio
async def test_next_resumes_after_the_answered_question(seeded):
    bot = _mocked_bot()
    state = _fresh_state()
    message = _make_message("")
    await _dispatch(knm_router, state, _make_callback("knm:grp:1", message), bot=bot, user=seeded)
    await _dispatch(knm_router, state, _make_callback("knm:ans:B", message), bot=bot, user=seeded)

    await _dispatch(knm_router, state, _make_callback("knm:next", message), bot=bot, user=seeded)

    assert "سؤال 2 از 5" in _calls(bot, EditMessageText)[-1].text


@pytest.mark.asyncio
async def test_finishing_a_group_shows_the_score(seeded, session_factory):
    bot = _mocked_bot()
    state = _fresh_state()
    message = _make_message("")
    # Group 1 holds 5 questions; answer all of them correctly.
    await _dispatch(knm_router, state, _make_callback("knm:grp:1", message), bot=bot, user=seeded)
    for _ in range(5):
        await _dispatch(
            knm_router, state, _make_callback("knm:ans:B", message), bot=bot, user=seeded
        )
        await _dispatch(
            knm_router, state, _make_callback("knm:next", message), bot=bot, user=seeded
        )

    edit = _calls(bot, EditMessageText)[-1]
    assert "🎉 <b>دسته 2 تمام شد!</b>" in edit.text
    assert "5 از 5 درست (100٪)" in edit.text
    assert edit.reply_markup.inline_keyboard[0][0].callback_data == "knm:reset:1"
    assert await state.get_state() is None


@pytest.mark.asyncio
async def test_reset_asks_first_then_clears_the_group(seeded):
    bot = _mocked_bot()
    state = _fresh_state()
    message = _make_message("")
    await _dispatch(knm_router, state, _make_callback("knm:grp:1", message), bot=bot, user=seeded)
    await _dispatch(knm_router, state, _make_callback("knm:ans:B", message), bot=bot, user=seeded)

    # Asking does not delete anything yet.
    await _dispatch(knm_router, state, _make_callback("knm:reset:1", message), bot=bot, user=seeded)
    assert "مطمئنی؟" in _calls(bot, EditMessageText)[-1].text
    assert (await knm.get_group(user_id=seeded.id, group=1)).answered == 1

    await _dispatch(
        knm_router, state, _make_callback("knm:reset:go:1", message), bot=bot, user=seeded
    )

    assert (await knm.get_group(user_id=seeded.id, group=1)).answered == 0
    assert "سؤال 1 از 5" in _calls(bot, EditMessageText)[-1].text


@pytest.mark.asyncio
async def test_stop_returns_to_the_main_menu(seeded):
    bot = _mocked_bot()
    state = _fresh_state()
    message = _make_message("")
    await _dispatch(knm_router, state, _make_callback("knm:grp:1", message), bot=bot, user=seeded)

    await _dispatch(knm_router, state, _make_callback("knm:stop", message), bot=bot, user=seeded)

    assert await state.get_state() is None
    assert "متوقف شد" in _calls(bot, SendMessage)[-1].text


@pytest.mark.asyncio
async def test_empty_bank_does_not_crash(knm_db, session_factory):
    async with session_factory() as session:
        session.add(User(id=1, telegram_id=TG_ID, first_name="Test"))
        await session.commit()
    bot = _mocked_bot()

    await _dispatch(
        knm_router,
        _fresh_state(),
        _make_message(BTN_KNM),
        bot=bot,
        user=User(id=1, telegram_id=TG_ID, first_name="Test"),
    )

    assert "هنوز سؤالی وارد نشده" in _calls(bot, SendMessage)[0].text
