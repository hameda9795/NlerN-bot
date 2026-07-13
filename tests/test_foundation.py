"""Foundation tests: config validation and user auto-registration."""

from __future__ import annotations

import pytest
from aiogram.types import User as TgUser

from bot.config import BotConfig
from database.models import User
from middlewares.user_middleware import UserMiddleware


def test_bot_config_rejects_bad_token():
    with pytest.raises(ValueError):
        BotConfig(BOT_TOKEN="not-a-valid-token", ADMIN_USER_ID="1")


def test_admin_ids_parsing():
    cfg = BotConfig(
        BOT_TOKEN="123456789:AAEEvalidlookingtokenForTests000000",
        ADMIN_USER_ID="111, 222 ,333",
    )
    assert cfg.admin_ids == [111, 222, 333]


@pytest.mark.asyncio
async def test_middleware_creates_new_user(patched_db_session, session_factory):
    tg_user = TgUser(
        id=999001,
        is_bot=False,
        first_name="Ali",
        username="ali_test",
        language_code="fa",
    )

    called = {}

    async def handler(event, data):
        called["user"] = data.get("user")
        return "ok"

    result = await UserMiddleware()(handler, event=object(), data={"event_from_user": tg_user})

    assert result == "ok"
    user = called["user"]
    assert isinstance(user, User)
    assert user.telegram_id == 999001
    assert user.current_cefr_level == "A0"
    assert user.subscription_tier == "free"


@pytest.mark.asyncio
async def test_middleware_updates_existing_user(patched_db_session, session_factory):
    tg_user = TgUser(id=999002, is_bot=False, first_name="Sara", language_code="fa")

    async def handler(event, data):
        return data.get("user")

    mw = UserMiddleware()
    first = await mw(handler, event=object(), data={"event_from_user": tg_user})
    second = await mw(handler, event=object(), data={"event_from_user": tg_user})

    # Same telegram user => same DB row, no duplicate created.
    assert first.telegram_id == second.telegram_id == 999002

    async with session_factory() as session:
        from sqlalchemy import func, select

        count = await session.scalar(
            select(func.count()).select_from(User).where(User.telegram_id == 999002)
        )
        assert count == 1
