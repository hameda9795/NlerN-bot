"""Temporary /demo handler — Rich Message verb card built with Rich Markdown.

Uses the `markdown` field of InputRichMessage (the clean, documented path) so
tables, headings, dividers and the collapsible examples block render natively.
On a dark theme the table shows borders automatically — there is no bot-side
border/color setting (see telegram-bot-api-10.1-rich-messages.md).

Requires aiogram >= 3.29.0. Throwaway preview; delete once design is locked.
"""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import InputRichMessage, Message

logger = logging.getLogger(__name__)

router = Router(name="demo")


def _build_markdown() -> str:
    return (
        "# 📘 opstaan\n"
        "**بلند شدن، بیدار شدن**\n\n"
        "🗣 _اوپ‌ستان_ · ساختار: `op` + `staan`\n\n"
        "---\n\n"
        "## ⏱ صرف زمان حال\n\n"
        "| ضمیر | فعل |\n"
        "|:--|--:|\n"
        "| ik | sta op |\n"
        "| jij / u | staat op |\n"
        "| hij / zij | staat op |\n"
        "| wij / jullie | staan op |\n"
        "| zij | staan op |\n\n"
        "## 🔑 سه‌جزء اصلی فعل\n\n"
        "| infinitief | verleden tijd | voltooid deelwoord |\n"
        "|:--:|:--:|:--:|\n"
        "| opstaan | stond op | opgestaan |\n\n"
        "---\n\n"
        "<details>\n"
        "<summary>💬 مثال‌ها</summary>\n\n"
        "> Ik **sta** om zeven uur ==op==.\n"
        "> _ساعت هفت بیدار می‌شوم._\n\n"
        "> We **staan** vroeg ==op== in het weekend.\n"
        "> _آخر هفته زود بیدار می‌شویم._\n\n"
        "</details>\n"
    )


@router.message(Command("demo"))
async def cmd_demo(message: Message) -> None:
    """Send the Rich Markdown verb card for design review."""
    try:
        await message.answer_rich(
            rich_message=InputRichMessage(markdown=_build_markdown(), is_rtl=True)
        )
    except Exception as exc:  # noqa: BLE001 - surface the real API error for review
        logger.exception("Rich markdown demo failed")
        await message.answer(f"⚠️ ارسال Rich Message خطا داد:\n<code>{exc}</code>")
