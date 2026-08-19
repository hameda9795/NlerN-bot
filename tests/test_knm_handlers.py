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
    # A status emoji plus one plain Persian phrase — no bar inside a button,
    # where a left-to-right bar would push the numbers to the wrong end.
    assert rows[0][0].text == "⚪️ دسته ۱ — ۴۰ سؤال"
    assert rows[1][0].text == "⚪️ دسته ۲ — ۵ سؤال"  # the short trailing group
    assert "هنوز شروع نکرده‌ای" in sent[0].text


@pytest.mark.asyncio
async def test_choosing_a_group_serves_its_first_question(seeded):
    bot = _mocked_bot()
    state = _fresh_state()

    await _dispatch(
        knm_router, state, _make_callback("knm:grp:1", _make_message("")), bot=bot, user=seeded
    )

    edit = _calls(bot, EditMessageText)[0]
    assert "دسته ۲" in edit.text
    assert "سؤال ۱ از ۵" in edit.text
    assert "<blockquote>Vraag 40?</blockquote>" in edit.text
    # Each option is its own full-width button carrying its Dutch text, and the
    # message body does not repeat the option list.
    rows = edit.reply_markup.inline_keyboard
    assert [row[0].callback_data for row in rows[:3]] == [
        "knm:ans:A", "knm:ans:B", "knm:ans:C"
    ]
    assert [len(row) for row in rows] == [1, 1, 1, 1]
    assert rows[0][0].text == "Ⓐ  Eerste"
    assert rows[1][0].text == "Ⓑ  Tweede"
    assert "Eerste" not in edit.text
    assert await state.get_state() == KnmStates.answering.state


@pytest.mark.asyncio
async def test_correct_answer_shows_explanation_and_records_progress(seeded):
    bot = _mocked_bot()
    state = _fresh_state()
    message = _make_message("")
    await _dispatch(knm_router, state, _make_callback("knm:grp:1", message), bot=bot, user=seeded)

    await _dispatch(knm_router, state, _make_callback("knm:ans:B", message), bot=bot, user=seeded)

    edit = _calls(bot, EditMessageText)[-1]
    assert "✅ <b>درست!</b>  Ⓑ Tweede" in edit.text
    assert "<blockquote>دو</blockquote>" in edit.text  # chosen option's feedback
    # The long detail is folded away so the verdict stays on screen.
    assert "<blockquote expandable>💡 <b>توضیح بیشتر</b>" in edit.text
    assert "توضیح فارسی" in edit.text
    assert "📖 <b>واژه‌های کلیدی</b>" in edit.text
    assert "MAP: ماژول" in edit.text
    assert _calls(bot, AnswerCallbackQuery)[-1].text == "✅ درست"
    assert (await knm.get_group(user_id=seeded.id, group=1)).answered == 1


@pytest.mark.asyncio
async def test_wrong_answer_reveals_the_correct_option(seeded):
    bot = _mocked_bot()
    state = _fresh_state()
    message = _make_message("")
    await _dispatch(knm_router, state, _make_callback("knm:grp:1", message), bot=bot, user=seeded)

    await _dispatch(knm_router, state, _make_callback("knm:ans:A", message), bot=bot, user=seeded)

    edit = _calls(bot, EditMessageText)[-1]
    # What they picked is struck through; the right answer is spelled out.
    assert "<s>Ⓐ Eerste</s>" in edit.text
    assert "✅ پاسخ درست: <b>Ⓑ Tweede</b>" in edit.text
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

    assert "سؤال ۲ از ۵" in _calls(bot, EditMessageText)[-1].text


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
    assert "🎉 <b>دسته ۲ تمام شد</b>" in edit.text
    assert "۵ از ۵ درست (۱۰۰٪)" in edit.text
    assert "🟩🟩🟩🟩🟩" in edit.text  # a full bar at 100%
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
    assert "سؤال ۱ از ۵" in _calls(bot, EditMessageText)[-1].text


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


@pytest.mark.asyncio
async def test_long_option_text_is_never_truncated_on_its_button(knm_db, session_factory):
    """The real bank has options up to 80 chars; they must survive intact."""
    long_text = "Dit is verboden en kan door de rechter worden bestraft met een boete"
    async with session_factory() as session:
        session.add(User(id=1, telegram_id=TG_ID, first_name="Test"))
        question = _question(0)
        question.options_json = [
            {**question.options_json[0], "text_nl": long_text},
            *question.options_json[1:],
        ]
        session.add(question)
        await session.commit()
    user = User(id=1, telegram_id=TG_ID, first_name="Test")
    bot = _mocked_bot()

    await _dispatch(
        knm_router, _fresh_state(), _make_callback("knm:grp:0", _make_message("")),
        bot=bot, user=user,
    )

    button = _calls(bot, EditMessageText)[0].reply_markup.inline_keyboard[0][0]
    assert button.text == f"Ⓐ  {long_text}"
    assert "…" not in button.text


@pytest.mark.asyncio
async def test_no_western_digits_reach_the_user(seeded):
    """Persian UI: a bare 0-9 anywhere in the rendered text is a bug."""
    import re

    bot = _mocked_bot()
    state = _fresh_state()
    message = _make_message("")
    await _dispatch(knm_router, _fresh_state(), _make_message(BTN_KNM), bot=bot, user=seeded)
    await _dispatch(knm_router, state, _make_callback("knm:grp:1", message), bot=bot, user=seeded)
    await _dispatch(knm_router, state, _make_callback("knm:ans:B", message), bot=bot, user=seeded)

    rendered = [call.text for call in _calls(bot, SendMessage)]
    rendered += [call.text for call in _calls(bot, EditMessageText)]
    rendered += [
        button.text
        for call in _calls(bot, SendMessage) + _calls(bot, EditMessageText)
        if call.reply_markup is not None
        for row in call.reply_markup.inline_keyboard
        for button in row
    ]
    for text in rendered:
        # The Dutch question text is seeded as "Vraag 40?" in these fixtures, so
        # only look at the Persian chrome around the quoted question.
        chrome = re.sub(r"<blockquote.*?</blockquote>", "", text, flags=re.S)
        chrome = re.sub(r"Vraag \d+\?", "", chrome)
        assert not re.search(r"[0-9]", chrome), f"western digits in: {chrome!r}"


@pytest.mark.asyncio
async def test_group_buttons_show_all_three_states(seeded):
    """Untouched / in-progress / finished must be tellable apart at a glance."""
    bot = _mocked_bot()
    state = _fresh_state()
    message = _make_message("")
    # Answer one question in group 1 (5 questions), leaving group 0 untouched.
    await _dispatch(knm_router, state, _make_callback("knm:grp:1", message), bot=bot, user=seeded)
    await _dispatch(knm_router, state, _make_callback("knm:ans:B", message), bot=bot, user=seeded)
    await _dispatch(knm_router, state, _make_callback("knm:home", message), bot=bot, user=seeded)

    rows = _calls(bot, EditMessageText)[-1].reply_markup.inline_keyboard
    assert rows[0][0].text == "⚪️ دسته ۱ — ۴۰ سؤال"
    assert rows[1][0].text == "🔵 دسته ۲ — ۱ از ۵"

    # Finish group 1 and it flips to the finished label.
    for _ in range(4):
        await _dispatch(
            knm_router, state, _make_callback("knm:grp:1", message), bot=bot, user=seeded
        )
        await _dispatch(
            knm_router, state, _make_callback("knm:ans:B", message), bot=bot, user=seeded
        )
    await _dispatch(knm_router, state, _make_callback("knm:home", message), bot=bot, user=seeded)

    rows = _calls(bot, EditMessageText)[-1].reply_markup.inline_keyboard
    assert rows[1][0].text == "✅ دسته ۲ — ۵ از ۵ درست"


@pytest.mark.asyncio
async def test_no_unrenderable_glyphs_reach_the_user(seeded):
    """Block/geometric characters show as empty boxes on Telegram — ban them."""
    import re

    bot = _mocked_bot()
    state = _fresh_state()
    message = _make_message("")
    await _dispatch(knm_router, _fresh_state(), _make_message(BTN_KNM), bot=bot, user=seeded)
    await _dispatch(knm_router, state, _make_callback("knm:grp:1", message), bot=bot, user=seeded)
    await _dispatch(knm_router, state, _make_callback("knm:ans:B", message), bot=bot, user=seeded)

    calls = _calls(bot, SendMessage) + _calls(bot, EditMessageText)
    texts = [call.text for call in calls]
    texts += [
        button.text
        for call in calls
        if call.reply_markup is not None
        for row in call.reply_markup.inline_keyboard
        for button in row
    ]
    # Block Elements (U+2580–259F) and Geometric Shapes (U+25A0–25FF) fall back
    # to the client's own font. A trailing U+FE0F forces emoji presentation, so
    # "◀️" is safe while a bare "▰" is not.
    for text in texts:
        assert not re.search(r"[▀-▟■-◿](?!️)", text), f"tofu risk in: {text!r}"
