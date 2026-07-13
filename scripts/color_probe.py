"""Send a worden card with its new save button for review.

Run: uv run python scripts/color_probe.py <chat_id>
"""

from __future__ import annotations

import asyncio
import sys
import types

from bot.loader import create_bot
from keyboards.vajegan_keyboard import worden_word_nav_keyboard
from utils import rich_cards

WORDEN = types.SimpleNamespace(
    id=5,
    data={
        "dutch": "het huis",
        "persian_translation": "خانه",
        "pronunciation": "هاوس",
        "common_mistake": "de huis",
        "correct_form": "het huis",
        "examples": "Het huis is groot.<br>خانه بزرگ است.",
    },
)


async def main() -> None:
    chat_id = int(sys.argv[1]) if len(sys.argv) > 1 else 741378837
    bot = create_bot()
    md = rich_cards.worden_card(
        WORDEN, index=0, total=46, chapter_title="خانه و مبلمان", topic_label="همه"
    )
    kb = worden_word_nav_keyboard(
        table="fasl_03_home", index=0, total=46, chapter_number=3, saved=False
    )
    try:
        await bot.send_message(chat_id, "⬇️ <b>واژگان فصل — حالا با دکمه‌ی ذخیره</b>")
        await bot.send_rich_message(
            chat_id=chat_id, rich_message=rich_cards.to_input(md), reply_markup=kb
        )
        print("sent worden card with save button")
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR -> {exc}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
