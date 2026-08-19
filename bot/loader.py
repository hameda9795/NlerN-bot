"""Dispatcher and Bot factory.

Builds the aiogram ``Bot`` and ``Dispatcher``, installs middlewares and
includes the feature routers. Keeping this separate from ``main.py`` lets
tests and scripts build the dispatcher without starting polling.
"""

from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import get_settings
from handlers import (
    admin,
    ai_chat,
    common,
    contact_admin,
    exam,
    knm,
    quiz,
    sentence_check,
    subscription,
    vajegan,
    vocab_b2,
)
from middlewares.subscription_middleware import SubscriptionMiddleware
from middlewares.user_middleware import UserMiddleware


def create_bot() -> Bot:
    """Create the Bot instance with HTML parse mode as default."""
    settings = get_settings()
    if not settings.bot.bot_token:
        raise RuntimeError("BOT_TOKEN is not configured (set it in .env).")
    return Bot(
        token=settings.bot.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher() -> Dispatcher:
    """Create the Dispatcher, install middlewares and include routers."""
    dp = Dispatcher(storage=MemoryStorage())

    # User auto-registration runs on messages and callback queries.
    user_mw = UserMiddleware()
    dp.message.middleware(user_mw)
    dp.callback_query.middleware(user_mw)

    # Access gate runs after user registration: features need a subscription.
    sub_mw = SubscriptionMiddleware()
    dp.message.middleware(sub_mw)
    dp.callback_query.middleware(sub_mw)

    # Active feature routers: واژگان (vajegan), امتحان (quiz),
    # تمرین جمله (sentence_check), کلمات سخت من (vocab_b2's saved-words
    # review — the B2 browse flow stays hidden: it has no menu button/command)
    # and چت با AI (ai_chat).
    dp.include_router(common.router)
    dp.include_router(contact_admin.router)
    dp.include_router(subscription.router)
    dp.include_router(vajegan.router)
    dp.include_router(exam.router)
    dp.include_router(knm.router)
    dp.include_router(quiz.router)
    dp.include_router(sentence_check.router)
    dp.include_router(vocab_b2.router)
    dp.include_router(ai_chat.router)
    dp.include_router(admin.router)

    return dp
