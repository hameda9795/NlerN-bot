"""Seed the database with starter Dutch words and A0 lessons.

Idempotent: existing words (by dutch_word) and lessons (by title_dutch)
are skipped, so the script is safe to re-run.

Run with::

    uv run python scripts/seed_database.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

# Allow running as a plain script (add project root to sys.path).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from database.connection import get_db_session, init_db  # noqa: E402
from database.models import Lesson, Word  # noqa: E402

# --- 50 essential A0–A1 Dutch words for Persian speakers -------------------
# Fields: dutch_word, article, persian, example_nl, example_fa, level, category
WORDS: list[dict[str, str | None]] = [
    # Greetings
    {"dutch_word": "hallo", "article": None, "persian_translation": "سلام", "example_sentence_dutch": "Hallo, hoe gaat het?", "example_sentence_persian": "سلام، حالت چطوره؟", "cefr_level": "A0", "category": "greetings"},
    {"dutch_word": "dag", "article": "de", "persian_translation": "روز / بدرود", "example_sentence_dutch": "Goedendag!", "example_sentence_persian": "روز بخیر!", "cefr_level": "A0", "category": "greetings"},
    {"dutch_word": "doei", "article": None, "persian_translation": "خداحافظ (خودمونی)", "example_sentence_dutch": "Doei, tot morgen!", "example_sentence_persian": "خداحافظ، تا فردا!", "cefr_level": "A0", "category": "greetings"},
    {"dutch_word": "alsjeblieft", "article": None, "persian_translation": "لطفاً / بفرما", "example_sentence_dutch": "Een koffie, alsjeblieft.", "example_sentence_persian": "یک قهوه، لطفاً.", "cefr_level": "A1", "category": "greetings"},
    {"dutch_word": "dank je wel", "article": None, "persian_translation": "ممنونم", "example_sentence_dutch": "Dank je wel voor je hulp.", "example_sentence_persian": "ممنون برای کمکت.", "cefr_level": "A0", "category": "greetings"},
    {"dutch_word": "sorry", "article": None, "persian_translation": "ببخشید", "example_sentence_dutch": "Sorry, ik ben te laat.", "example_sentence_persian": "ببخشید، دیر کردم.", "cefr_level": "A0", "category": "greetings"},
    {"dutch_word": "ja", "article": None, "persian_translation": "بله", "example_sentence_dutch": "Ja, dat klopt.", "example_sentence_persian": "بله، درسته.", "cefr_level": "A0", "category": "basics"},
    {"dutch_word": "nee", "article": None, "persian_translation": "نه", "example_sentence_dutch": "Nee, dank je.", "example_sentence_persian": "نه، ممنون.", "cefr_level": "A0", "category": "basics"},
    {"dutch_word": "misschien", "article": None, "persian_translation": "شاید", "example_sentence_dutch": "Misschien morgen.", "example_sentence_persian": "شاید فردا.", "cefr_level": "A1", "category": "basics"},
    {"dutch_word": "goed", "article": None, "persian_translation": "خوب", "example_sentence_dutch": "Het gaat goed.", "example_sentence_persian": "اوضاع خوبه.", "cefr_level": "A0", "category": "basics"},
    # Numbers
    {"dutch_word": "een", "article": None, "persian_translation": "یک", "example_sentence_dutch": "Ik heb een hond.", "example_sentence_persian": "من یک سگ دارم.", "cefr_level": "A0", "category": "numbers"},
    {"dutch_word": "twee", "article": None, "persian_translation": "دو", "example_sentence_dutch": "Twee koffie, graag.", "example_sentence_persian": "دو قهوه، لطفاً.", "cefr_level": "A0", "category": "numbers"},
    {"dutch_word": "drie", "article": None, "persian_translation": "سه", "example_sentence_dutch": "Ik heb drie boeken.", "example_sentence_persian": "من سه کتاب دارم.", "cefr_level": "A0", "category": "numbers"},
    {"dutch_word": "vier", "article": None, "persian_translation": "چهار", "example_sentence_dutch": "Het is vier uur.", "example_sentence_persian": "ساعت چهاره.", "cefr_level": "A0", "category": "numbers"},
    {"dutch_word": "vijf", "article": None, "persian_translation": "پنج", "example_sentence_dutch": "Vijf euro, alsjeblieft.", "example_sentence_persian": "پنج یورو، لطفاً.", "cefr_level": "A0", "category": "numbers"},
    {"dutch_word": "tien", "article": None, "persian_translation": "ده", "example_sentence_dutch": "Tien minuten.", "example_sentence_persian": "ده دقیقه.", "cefr_level": "A0", "category": "numbers"},
    # Colors
    {"dutch_word": "rood", "article": None, "persian_translation": "قرمز", "example_sentence_dutch": "De appel is rood.", "example_sentence_persian": "سیب قرمزه.", "cefr_level": "A1", "category": "colors"},
    {"dutch_word": "blauw", "article": None, "persian_translation": "آبی", "example_sentence_dutch": "De lucht is blauw.", "example_sentence_persian": "آسمون آبیه.", "cefr_level": "A1", "category": "colors"},
    {"dutch_word": "groen", "article": None, "persian_translation": "سبز", "example_sentence_dutch": "Het gras is groen.", "example_sentence_persian": "چمن سبزه.", "cefr_level": "A1", "category": "colors"},
    {"dutch_word": "geel", "article": None, "persian_translation": "زرد", "example_sentence_dutch": "De zon is geel.", "example_sentence_persian": "خورشید زرده.", "cefr_level": "A1", "category": "colors"},
    {"dutch_word": "zwart", "article": None, "persian_translation": "سیاه", "example_sentence_dutch": "De kat is zwart.", "example_sentence_persian": "گربه سیاهه.", "cefr_level": "A1", "category": "colors"},
    {"dutch_word": "wit", "article": None, "persian_translation": "سفید", "example_sentence_dutch": "De melk is wit.", "example_sentence_persian": "شیر سفیده.", "cefr_level": "A1", "category": "colors"},
    # Family
    {"dutch_word": "moeder", "article": "de", "persian_translation": "مادر", "example_sentence_dutch": "Mijn moeder kookt.", "example_sentence_persian": "مادرم آشپزی می‌کنه.", "cefr_level": "A1", "category": "family"},
    {"dutch_word": "vader", "article": "de", "persian_translation": "پدر", "example_sentence_dutch": "Mijn vader werkt.", "example_sentence_persian": "پدرم کار می‌کنه.", "cefr_level": "A1", "category": "family"},
    {"dutch_word": "kind", "article": "het", "persian_translation": "کودک", "example_sentence_dutch": "Het kind speelt.", "example_sentence_persian": "بچه بازی می‌کنه.", "cefr_level": "A1", "category": "family"},
    {"dutch_word": "broer", "article": "de", "persian_translation": "برادر", "example_sentence_dutch": "Ik heb een broer.", "example_sentence_persian": "من یک برادر دارم.", "cefr_level": "A1", "category": "family"},
    {"dutch_word": "zus", "article": "de", "persian_translation": "خواهر", "example_sentence_dutch": "Mijn zus woont in Utrecht.", "example_sentence_persian": "خواهرم در اوترخت زندگی می‌کنه.", "cefr_level": "A1", "category": "family"},
    {"dutch_word": "vriend", "article": "de", "persian_translation": "دوست", "example_sentence_dutch": "Hij is mijn vriend.", "example_sentence_persian": "اون دوستمه.", "cefr_level": "A1", "category": "family"},
    # Food & drink
    {"dutch_word": "brood", "article": "het", "persian_translation": "نان", "example_sentence_dutch": "Ik eet brood.", "example_sentence_persian": "نون می‌خورم.", "cefr_level": "A1", "category": "food"},
    {"dutch_word": "water", "article": "het", "persian_translation": "آب", "example_sentence_dutch": "Een glas water, graag.", "example_sentence_persian": "یک لیوان آب، لطفاً.", "cefr_level": "A0", "category": "food"},
    {"dutch_word": "koffie", "article": "de", "persian_translation": "قهوه", "example_sentence_dutch": "Ik drink koffie.", "example_sentence_persian": "قهوه می‌نوشم.", "cefr_level": "A0", "category": "food"},
    {"dutch_word": "thee", "article": "de", "persian_translation": "چای", "example_sentence_dutch": "Wil je thee?", "example_sentence_persian": "چای می‌خوای؟", "cefr_level": "A0", "category": "food"},
    {"dutch_word": "melk", "article": "de", "persian_translation": "شیر", "example_sentence_dutch": "Melk in de koffie?", "example_sentence_persian": "شیر توی قهوه؟", "cefr_level": "A1", "category": "food"},
    {"dutch_word": "appel", "article": "de", "persian_translation": "سیب", "example_sentence_dutch": "Een appel per dag.", "example_sentence_persian": "روزی یک سیب.", "cefr_level": "A1", "category": "food"},
    {"dutch_word": "kaas", "article": "de", "persian_translation": "پنیر", "example_sentence_dutch": "Nederlandse kaas is lekker.", "example_sentence_persian": "پنیر هلندی خوشمزه‌ست.", "cefr_level": "A1", "category": "food"},
    {"dutch_word": "eten", "article": "het", "persian_translation": "غذا / خوردن", "example_sentence_dutch": "Het eten is klaar.", "example_sentence_persian": "غذا حاضره.", "cefr_level": "A1", "category": "food"},
    # Time / days
    {"dutch_word": "vandaag", "article": None, "persian_translation": "امروز", "example_sentence_dutch": "Vandaag is het maandag.", "example_sentence_persian": "امروز دوشنبه‌ست.", "cefr_level": "A1", "category": "time"},
    {"dutch_word": "morgen", "article": None, "persian_translation": "فردا / صبح", "example_sentence_dutch": "Tot morgen!", "example_sentence_persian": "تا فردا!", "cefr_level": "A1", "category": "time"},
    {"dutch_word": "gisteren", "article": None, "persian_translation": "دیروز", "example_sentence_dutch": "Gisteren regende het.", "example_sentence_persian": "دیروز بارون اومد.", "cefr_level": "A1", "category": "time"},
    {"dutch_word": "week", "article": "de", "persian_translation": "هفته", "example_sentence_dutch": "Volgende week.", "example_sentence_persian": "هفته‌ی بعد.", "cefr_level": "A1", "category": "time"},
    {"dutch_word": "uur", "article": "het", "persian_translation": "ساعت", "example_sentence_dutch": "Het is twee uur.", "example_sentence_persian": "ساعت دوئه.", "cefr_level": "A1", "category": "time"},
    # Common verbs / words
    {"dutch_word": "zijn", "article": None, "persian_translation": "بودن", "example_sentence_dutch": "Ik ben moe.", "example_sentence_persian": "خسته‌ام.", "cefr_level": "A1", "category": "verbs"},
    {"dutch_word": "hebben", "article": None, "persian_translation": "داشتن", "example_sentence_dutch": "Ik heb honger.", "example_sentence_persian": "گرسنمه.", "cefr_level": "A1", "category": "verbs"},
    {"dutch_word": "gaan", "article": None, "persian_translation": "رفتن", "example_sentence_dutch": "Ik ga naar huis.", "example_sentence_persian": "میرم خونه.", "cefr_level": "A1", "category": "verbs"},
    {"dutch_word": "komen", "article": None, "persian_translation": "آمدن", "example_sentence_dutch": "Kom je mee?", "example_sentence_persian": "میای باهام؟", "cefr_level": "A1", "category": "verbs"},
    {"dutch_word": "spreken", "article": None, "persian_translation": "صحبت کردن", "example_sentence_dutch": "Ik spreek een beetje Nederlands.", "example_sentence_persian": "من کمی هلندی صحبت می‌کنم.", "cefr_level": "A1", "category": "verbs"},
    {"dutch_word": "huis", "article": "het", "persian_translation": "خانه", "example_sentence_dutch": "Mijn huis is klein.", "example_sentence_persian": "خونه‌ام کوچیکه.", "cefr_level": "A1", "category": "places"},
    {"dutch_word": "straat", "article": "de", "persian_translation": "خیابان", "example_sentence_dutch": "Ik woon in deze straat.", "example_sentence_persian": "توی این خیابون زندگی می‌کنم.", "cefr_level": "A1", "category": "places"},
    {"dutch_word": "stad", "article": "de", "persian_translation": "شهر", "example_sentence_dutch": "Amsterdam is een mooie stad.", "example_sentence_persian": "آمستردام شهر قشنگیه.", "cefr_level": "A1", "category": "places"},
    {"dutch_word": "school", "article": "de", "persian_translation": "مدرسه", "example_sentence_dutch": "De kinderen gaan naar school.", "example_sentence_persian": "بچه‌ها میرن مدرسه.", "cefr_level": "A1", "category": "places"},
    {"dutch_word": "werk", "article": "het", "persian_translation": "کار", "example_sentence_dutch": "Ik ga naar mijn werk.", "example_sentence_persian": "میرم سر کارم.", "cefr_level": "A1", "category": "places"},
]


# --- 5 sample A0 lessons ----------------------------------------------------
def _lesson_content(vocab: list[str], grammar: str, practice: list[str]) -> str:
    """Build a valid content_json string for a lesson."""
    return json.dumps(
        {"vocabulary": vocab, "grammar_note": grammar, "practice": practice},
        ensure_ascii=False,
    )


LESSONS: list[dict[str, object]] = [
    {
        "title_dutch": "Begroetingen",
        "title_persian": "احوال‌پرسی",
        "cefr_level": "A0",
        "order_index": 1,
        "content_json": _lesson_content(
            ["hallo", "dag", "doei", "dank je wel", "sorry"],
            "در هلندی برای سلام رسمی 'goedendag' و خودمونی 'hallo' به کار می‌رود.",
            ["به یک نفر سلام کن و خداحافظی کن.", "از کسی تشکر کن."],
        ),
    },
    {
        "title_dutch": "Getallen 1-10",
        "title_persian": "اعداد ۱ تا ۱۰",
        "cefr_level": "A0",
        "order_index": 2,
        "content_json": _lesson_content(
            ["een", "twee", "drie", "vier", "vijf", "tien"],
            "اعداد در هلندی پایه‌ی شمارش و خرید کردن هستند.",
            ["تا ده بشمار.", "بگو چند تا برادر یا خواهر داری."],
        ),
    },
    {
        "title_dutch": "Kleuren",
        "title_persian": "رنگ‌ها",
        "cefr_level": "A0",
        "order_index": 3,
        "content_json": _lesson_content(
            ["rood", "blauw", "groen", "geel", "zwart", "wit"],
            "صفت رنگ معمولاً قبل از اسم می‌آید: 'de rode appel'.",
            ["رنگ سه چیز اطرافت را بگو."],
        ),
    },
    {
        "title_dutch": "Familie",
        "title_persian": "خانواده",
        "cefr_level": "A0",
        "order_index": 4,
        "content_json": _lesson_content(
            ["moeder", "vader", "kind", "broer", "zus"],
            "بیشتر اعضای خانواده با article 'de' می‌آیند، ولی 'het kind'.",
            ["خانواده‌ات را به هلندی معرفی کن."],
        ),
    },
    {
        "title_dutch": "Eten en drinken",
        "title_persian": "خوردنی و نوشیدنی",
        "cefr_level": "A0",
        "order_index": 5,
        "content_json": _lesson_content(
            ["brood", "water", "koffie", "thee", "kaas"],
            "برای سفارش می‌گویی: 'Een koffie, alsjeblieft.'",
            ["در یک کافه یک نوشیدنی سفارش بده."],
        ),
    },
]


async def seed() -> None:
    """Insert words and lessons if they are not already present."""
    await init_db()

    words_added = 0
    lessons_added = 0

    async with get_db_session() as session:
        # Words — skip by dutch_word.
        existing_words = set(
            (await session.execute(select(Word.dutch_word))).scalars().all()
        )
        for data in WORDS:
            if data["dutch_word"] in existing_words:
                continue
            session.add(Word(**data))
            words_added += 1

        # Lessons — skip by title_dutch.
        existing_lessons = set(
            (await session.execute(select(Lesson.title_dutch))).scalars().all()
        )
        for data in LESSONS:
            if data["title_dutch"] in existing_lessons:
                continue
            session.add(Lesson(**data))
            lessons_added += 1

    total_words = len(WORDS)
    total_lessons = len(LESSONS)
    print("✅ Seed complete.")
    print(f"   Words:   +{words_added} added ({total_words} in catalog)")
    print(f"   Lessons: +{lessons_added} added ({total_lessons} in catalog)")
    if words_added == 0 and lessons_added == 0:
        print("   (Nothing new — database was already seeded.)")


if __name__ == "__main__":
    asyncio.run(seed())
