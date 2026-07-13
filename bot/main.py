"""Application entry point.

Sets up logging, builds the bot/dispatcher, initializes the database and
runs the bot in long-polling mode.

Polling (vs. webhooks) is chosen for the MVP because it needs no public
HTTPS endpoint or reverse proxy — you can run it locally or on any host
without inbound networking. Webhooks can be added at deploy time (Phase 5).
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, BotCommandScopeChat

from bot.config import get_settings
from bot.loader import create_bot, create_dispatcher
from database.connection import close_db, init_db
from services import (
    irregular_verb_service,
    jomelat_service,
    main_verb_service,
    regular_verb_service,
    separable_verb_service,
    vocab_service,
    worden_service,
)

# Public command list — "/chat" (AI chat) and "/admin" (dashboard) are
# admin-only, so they're added separately below via a per-chat scope for each
# admin, not shown to everyone.
_COMMANDS = [
    BotCommand(command="start", description="شروع و منوی اصلی"),
    BotCommand(command="vajegan", description="واژگان (افعال جداشدنی)"),
    BotCommand(command="quiz", description="کوییز واژگان"),
    BotCommand(command="zin", description="تمرین جمله (گفتن درست جمله)"),
    BotCommand(command="subscribe", description="اشتراک و پرداخت"),
    BotCommand(command="contact", description="تماس با مدیریت"),
    BotCommand(command="help", description="راهنما"),
    BotCommand(command="cancel", description="لغو و بازگشت به منو"),
]
_ADMIN_COMMANDS = _COMMANDS + [
    BotCommand(command="chat", description="چت با AI"),
    BotCommand(command="admin", description="داشبورد ادمین"),
]

logger = logging.getLogger(__name__)

_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"


def setup_logging() -> None:
    """Configure console + rotating file logging."""
    _LOG_DIR.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(_LOG_DIR / "bot.log", encoding="utf-8"),
        ],
    )
    # aiogram is chatty at DEBUG; keep it at INFO.
    logging.getLogger("aiogram").setLevel(logging.INFO)


async def on_startup(bot: Bot) -> None:
    """Initialize resources and log bot identity."""
    await init_db()
    await bot.set_my_commands(_COMMANDS)
    for admin_id in get_settings().bot.admin_ids:
        await bot.set_my_commands(
            _ADMIN_COMMANDS, scope=BotCommandScopeChat(chat_id=admin_id)
        )
    me = await bot.get_me()
    logger.info("Bot started: @%s (id=%s, name=%s)", me.username, me.id, me.full_name)


async def on_shutdown() -> None:
    """Release resources on shutdown."""
    await vocab_service.dispose()
    await separable_verb_service.dispose()
    await main_verb_service.dispose()
    await regular_verb_service.dispose()
    await irregular_verb_service.dispose()
    await worden_service.dispose()
    await jomelat_service.dispose()
    await close_db()
    logger.info("Bot stopped.")


async def main() -> None:
    """Build the bot and run long polling."""
    setup_logging()
    bot: Bot = create_bot()
    dp: Dispatcher = create_dispatcher()

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    try:
        # Drop any updates queued while the bot was offline.
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Interrupted by user.")
