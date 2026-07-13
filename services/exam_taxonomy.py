"""Exam taxonomy derived from NL.md: levels x sections x subtopics + question types.

This is the single source of truth for what the exam covers. Each (level, section)
bucket carries the required subtopics and question-type guidance straight from
NL.md; the AI generator and reviewer build their per-(level, section) prompts from
here, and the Telegram exam menu builds level/section keyboards from here.

Section keys match ``database.models.Question.section`` (and
``services.question_service.SECTIONS``). Levels: A2, B1, B2.
"""

from __future__ import annotations

import re

LEVELS: tuple[str, ...] = ("A2", "B1", "B2")

# Default question-bank limits per *subtopic* for non-grammar sections (kept small
# so a section fills with variety without over-generating). A2/grammar keeps its
# own larger per-topic configs from earlier phases.
SUBTOPIC_DEFAULT_LIMITS: tuple[int, int, int] = (4, 8, 12)  # (min, soft, hard)

# Ordered section keys + Persian menu labels (the 10 NL.md sections).
SECTION_ORDER: tuple[str, ...] = (
    "grammar",
    "vocab_in_context",
    "reading",
    "meaning",
    "dialogue",
    "error_correction",
    "listening",
    "writing",
    "speaking",
    "formal_informal",
)

SECTION_LABELS_FA: dict[str, str] = {
    "grammar": "گرامر",
    "vocab_in_context": "واژگان در بافت",
    "reading": "خواندن",
    "meaning": "معنا و منظور",
    "dialogue": "مکالمه",
    "error_correction": "تصحیح خطا",
    "listening": "شنیداری",
    "writing": "نوشتن",
    "speaking": "گفتار",
    "formal_informal": "رسمی / غیررسمی",
}

LEVEL_GOALS: dict[str, str] = {
    "A2": (
        "کاربر بتواند در موقعیت‌های ساده‌ی روزمره جمله‌های کوتاه را بفهمد، جواب بدهد "
        "و اشتباهات پایه را کم کند."
    ),
    "B1": (
        "کاربر بتواند مستقل‌تر صحبت کند، مشکل را توضیح دهد، دلیل بدهد، درخواست بنویسد "
        "و متن‌های واقعی را بهتر بفهمد."
    ),
    "B2": (
        "کاربر بتواند دقیق‌تر، طبیعی‌تر و حرفه‌ای‌تر صحبت و نوشتار داشته باشد؛ نظر بدهد، "
        "استدلال کند، پیام رسمی قوی بنویسد و معنی‌های غیرمستقیم را بفهمد."
    ),
}

# Sections whose NL.md "نوع سؤال" is naturally multiple-choice. In v1 every section
# is served as 4-option MCQ; writing/speaking free-form and listening audio are a
# later enhancement (see module note). This flag lets the UI mark them.
MCQ_NATIVE_SECTIONS: frozenset[str] = frozenset({
    "grammar", "vocab_in_context", "reading", "meaning", "dialogue",
    "error_correction", "formal_informal",
})


# Per (level, section): required subtopics + question-type guidance (from NL.md).
# Kept faithful to NL.md; phrasing is intentionally short so it slots into prompts.
TAXONOMY: dict[tuple[str, str], dict[str, list[str]]] = {
    # ---------------- A2 ----------------
    ("A2", "grammar"): {
        "required": [
            "zijn / hebben", "present tense", "perfect tense ساده",
            "modal verbs: kunnen, moeten, mogen, willen", "question structure",
            "word order ساده", "niet / geen", "de / het / een", "plural nouns",
            "prepositions ساده: in, op, naar, bij, met", "separable verbs ساده",
            "time, days, dates",
        ],
        "question_types": [
            "جای خالی", "انتخاب جمله درست", "تصحیح جمله کوتاه", "انتخاب فعل درست",
        ],
    },
    ("A2", "vocab_in_context"): {
        "required": [
            "خانه", "خانواده", "خرید", "سوپرمارکت", "دکتر و داروخانه", "مدرسه",
            "کار ساده", "حمل‌ونقل", "آب‌وهوا", "زمان و قرار", "غذا و نوشیدنی", "لباس",
        ],
        "question_types": [
            "معنی کلمه در جمله", "انتخاب کلمه مناسب", "فرق دو کلمه ساده",
            "کاربرد کلمه در موقعیت واقعی",
        ],
    },
    ("A2", "reading"): {
        "required": [
            "پیام واتساپ کوتاه", "ایمیل ساده", "تابلو و اعلان", "پیام مدرسه",
            "پیام دکتر", "پیام gemeente", "آگهی ساده", "برنامه زمانی ساده",
        ],
        "question_types": [
            "متن چه می‌گوید؟", "کاربر باید چه کاری انجام دهد؟",
            "زمان/مکان/شخص را پیدا کن", "درست یا غلط",
        ],
    },
    ("A2", "meaning"): {
        "required": [
            "منظور جمله چیست؟", "درخواست ساده", "عذرخواهی", "پیشنهاد",
            "قبول یا رد کردن", "هشدار ساده", "یادآوری",
        ],
        "question_types": [
            "گوینده چه می‌خواهد؟", "جمله در این موقعیت یعنی چه؟", "بهترین واکنش چیست؟",
        ],
    },
    ("A2", "dialogue"): {
        "required": [
            "سلام و احوالپرسی", "خرید", "وقت گرفتن", "دکتر", "مدرسه بچه", "کار",
            "همسایه", "رستوران", "مسیر پرسیدن",
        ],
        "question_types": [
            "جمله بعدی در مکالمه", "جواب مناسب", "کامل کردن دیالوگ",
            "انتخاب واکنش طبیعی",
        ],
    },
    ("A2", "error_correction"): {
        "required": [
            "اشتباه فعل", "اشتباه de/het", "اشتباه word order", "اشتباه niet/geen",
            "اشتباه preposition", "اشتباه جمع", "اشتباه سوال ساختن",
        ],
        "question_types": [
            "جمله اشتباه را درست کن", "کدام جمله درست است؟", "اشتباه جمله کجاست؟",
        ],
    },
    ("A2", "listening"): {
        "required": [
            "جمله کوتاه روزمره", "عددها", "ساعت", "روزها", "قرار ملاقات",
            "آدرس ساده", "خرید ساده", "پیام کوتاه",
        ],
        "question_types": [
            "چه شنیدی؟", "کدام گزینه با صوت یکی است؟", "زمان یا مکان چیست؟",
            "گوینده چه می‌خواهد؟",
        ],
    },
    ("A2", "writing"): {
        "required": [
            "پیام کوتاه واتساپ", "عذرخواهی ساده", "گفتن تأخیر", "درخواست وقت",
            "جواب به ایمیل ساده", "توضیح کوتاه مشکل",
        ],
        "question_types": [
            "جمله را کامل کن", "پیام کوتاه بنویس", "جمله ساده را بهتر کن",
            "ترجمه فارسی به هلندی ساده",
        ],
    },
    ("A2", "speaking"): {
        "required": [
            "معرفی خود", "گفتن مشکل", "جواب کوتاه", "درخواست کمک",
            "توضیح برنامه روزانه", "تلفظ جمله‌های کوتاه",
        ],
        "question_types": [
            "انتخاب جمله‌ی گفتاری درست", "بهترین جواب کوتاه در مکالمه",
            "جمله‌ی طبیعی برای گفتن",
        ],
    },
    ("A2", "formal_informal"): {
        "required": [
            "jij / u", "سلام رسمی و غیررسمی", "درخواست رسمی ساده", "پیام به دوست",
            "پیام به gemeente یا دکتر", "تشکر و پایان پیام",
        ],
        "question_types": [
            "رسمی یا غیررسمی؟", "کدام جمله برای دکتر بهتر است؟",
            "کدام جمله برای دوست بهتر است؟", "جمله را ساده‌تر و طبیعی‌تر کن",
        ],
    },
    # ---------------- B1 ----------------
    ("B1", "grammar"): {
        "required": [
            "perfect tense کامل‌تر", "imperfect tense ساده",
            "subordinate clauses با omdat, als, dat", "word order بعد از omdat/als/dat",
            "modal verbs در جمله‌های طولانی‌تر", "separable verbs در گذشته",
            "reflexive verbs ساده", "comparative / superlative", "pronouns",
            "conjunctions: en, maar, want, omdat, dus", "prepositions پرکاربرد",
            "relative ساده با die/dat",
        ],
        "question_types": [
            "انتخاب ساختار درست", "کامل کردن جمله", "تشخیص ترتیب کلمات", "تصحیح جمله",
        ],
    },
    ("B1", "vocab_in_context"): {
        "required": [
            "کار و قرارداد", "بیماری و دکتر", "مدرسه و فرزند", "خانه و اجاره",
            "gemeente", "بانک و پرداخت", "شکایت ساده", "حمل‌ونقل", "بیمه",
            "قرار رسمی", "خرید آنلاین", "خدمات مشتری",
        ],
        "question_types": [
            "انتخاب واژه مناسب در متن", "معنی اصطلاح ساده", "فرق کلمات نزدیک",
            "کاربرد کلمه در موقعیت واقعی",
        ],
    },
    ("B1", "reading"): {
        "required": [
            "ایمیل رسمی ساده", "نامه gemeente", "پیام مدرسه", "دستورالعمل کوتاه",
            "آگهی کار", "قرارداد ساده", "اطلاعیه خدمات", "قوانین کوتاه",
        ],
        "question_types": [
            "هدف متن چیست؟", "چه کاری باید انجام شود؟", "کدام گزینه درست است؟",
            "اطلاعات مهم را پیدا کن", "نتیجه متن چیست؟",
        ],
    },
    ("B1", "meaning"): {
        "required": [
            "منظور غیرمستقیم", "درخواست مودبانه", "شکایت", "پیشنهاد", "توصیه",
            "هشدار", "موافقت/مخالفت", "دلیل آوردن",
        ],
        "question_types": [
            "گوینده واقعاً چه می‌خواهد؟", "بهترین واکنش چیست؟", "لحن جمله چیست؟",
            "جمله چه احساسی دارد؟",
        ],
    },
    ("B1", "dialogue"): {
        "required": [
            "تماس با دکتر", "صحبت با کارفرما", "مکالمه در مدرسه", "تماس با gemeente",
            "مکالمه با همسایه", "شکایت از سرویس", "رزرو وقت", "پرسیدن توضیح بیشتر",
        ],
        "question_types": [
            "ادامه طبیعی مکالمه", "انتخاب جواب مودبانه", "کامل کردن دیالوگ",
            "تشخیص سوءتفاهم",
        ],
    },
    ("B1", "error_correction"): {
        "required": [
            "word order در جمله فرعی", "زمان گذشته", "modal verbs", "prepositions",
            "pronouns", "conjunctions", "formal/informal mix",
            "جمله‌های خیلی فارسی‌وار",
        ],
        "question_types": [
            "جمله را طبیعی‌تر کن", "اشتباه گرامری را پیدا کن", "کدام نسخه بهتر است؟",
            "جمله را اصلاح کن",
        ],
    },
    ("B1", "listening"): {
        "required": [
            "voicemail ساده", "پیام مدرسه", "اعلامیه قطار/اتوبوس", "مکالمه کاری ساده",
            "تماس دکتر", "گفت‌وگوی خدمات مشتری", "قرار ملاقات",
        ],
        "question_types": [
            "موضوع اصلی چیست؟", "گوینده چه می‌خواهد؟", "زمان/مکان چیست؟",
            "چه اقدامی لازم است؟",
        ],
    },
    ("B1", "writing"): {
        "required": [
            "ایمیل کوتاه رسمی", "توضیح مشکل", "درخواست اطلاعات", "عذرخواهی",
            "شکایت ساده", "جواب به دعوت", "پیام به مدرسه/دکتر/کارفرما",
        ],
        "question_types": [
            "انتخاب جمله مناسب برای ایمیل", "بهتر کردن متن", "تبدیل فارسی به هلندی B1",
            "انتخاب ساختار درست ایمیل",
        ],
    },
    ("B1", "speaking"): {
        "required": [
            "توضیح مشکل", "توضیح تجربه", "گفتن دلیل", "درخواست کمک", "بیان نظر ساده",
            "صحبت درباره کار، خانه، خانواده، برنامه",
        ],
        "question_types": [
            "انتخاب جمله‌ی گفتاری مناسب", "بهترین جواب در مکالمه‌ی موقعیتی",
            "جمله‌ی طبیعی برای توضیح",
        ],
    },
    ("B1", "formal_informal"): {
        "required": [
            "تفاوت پیام به دوست و سازمان", "درخواست مودبانه", "شکایت رسمی ساده",
            "شروع و پایان ایمیل", "استفاده از u / jij", "نرم‌تر کردن جمله مستقیم",
        ],
        "question_types": [
            "کدام جمله رسمی‌تر است؟", "کدام جمله طبیعی‌تر است؟", "جمله را مودبانه‌تر کن",
            "جمله مناسب موقعیت را انتخاب کن",
        ],
    },
    # ---------------- B2 ----------------
    ("B2", "grammar"): {
        "required": [
            "complex subordinate clauses", "passive voice", "conditional sentences",
            "advanced word order", "relative clauses", "er constructions",
            "om te / te + infinitive", "hoewel, ondanks dat",
            "nuance با zou, kunnen, mogen", "indirect speech", "advanced connectors",
        ],
        "question_types": [
            "انتخاب ساختار طبیعی‌تر", "بازنویسی جمله", "تشخیص خطای ظریف",
            "انتخاب بهترین ساختار رسمی",
        ],
    },
    ("B2", "vocab_in_context"): {
        "required": [
            "کار حرفه‌ای", "مصاحبه شغلی", "قرارداد و قانون ساده", "مالیات و administratie",
            "خدمات رسمی", "اختلاف و مذاکره", "نظر دادن", "مزایا/معایب",
            "اقتصاد شخصی", "آموزش و جامعه", "تکنولوژی و رسانه",
        ],
        "question_types": [
            "معنی واژه در متن", "تفاوت nuance کلمات", "انتخاب واژه حرفه‌ای‌تر",
            "collocationهای رایج", "اصطلاحات رایج رسمی",
        ],
    },
    ("B2", "reading"): {
        "required": [
            "مقاله کوتاه", "ایمیل رسمی پیچیده‌تر", "متن نظر/تحلیل", "متن کاری",
            "شرایط قرارداد", "دستورالعمل چندمرحله‌ای", "شکایت و پاسخ رسمی",
            "متن خبری ساده‌شده",
        ],
        "question_types": [
            "نویسنده چه نظری دارد؟", "نتیجه منطقی چیست؟", "کدام برداشت درست‌تر است؟",
            "هدف پاراگراف چیست؟", "کدام جمله خلاصه بهتر است؟",
        ],
    },
    ("B2", "meaning"): {
        "required": [
            "معنی غیرمستقیم", "طعنه یا نارضایتی نرم", "دیپلماسی در جمله",
            "رد کردن مودبانه", "پیشنهاد غیرمستقیم", "هشدار حرفه‌ای", "انتقاد سازنده",
        ],
        "question_types": [
            "منظور پنهان چیست؟", "لحن جمله چیست؟", "جمله چقدر مستقیم/نرم است؟",
            "بهترین پاسخ حرفه‌ای چیست؟",
        ],
    },
    ("B2", "dialogue"): {
        "required": [
            "جلسه کاری", "مصاحبه شغلی", "مذاکره با مشتری", "تماس رسمی", "حل اختلاف",
            "توضیح پروژه", "دفاع از نظر", "درخواست شفاف‌سازی",
        ],
        "question_types": [
            "بهترین پاسخ در مکالمه حرفه‌ای", "ادامه منطقی بحث", "پاسخ دیپلماتیک",
            "مدیریت سوءتفاهم", "انتخاب جمله طبیعی‌تر",
        ],
    },
    ("B2", "error_correction"): {
        "required": [
            "جمله‌های غیرطبیعی اما قابل فهم", "word order پیشرفته", "register اشتباه",
            "ترجمه مستقیم از فارسی", "prepositionهای ظریف",
            "جمله‌های بیش‌ازحد مستقیم", "متن رسمی ضعیف",
        ],
        "question_types": [
            "متن را طبیعی‌تر کن", "بهترین بازنویسی کدام است؟", "اشتباه ظریف چیست؟",
            "جمله را حرفه‌ای‌تر کن",
        ],
    },
    ("B2", "listening"): {
        "required": [
            "مکالمه کاری", "بحث دو نفره", "voicemail رسمی", "توضیح طولانی‌تر",
            "جلسه کوتاه", "خبر ساده", "شکایت مشتری", "مصاحبه",
        ],
        "question_types": [
            "نظر گوینده چیست؟", "گوینده چه چیزی را پیشنهاد می‌کند؟",
            "کدام نتیجه درست است؟", "لحن گوینده چیست؟", "نکته اصلی چیست؟",
        ],
    },
    ("B2", "writing"): {
        "required": [
            "ایمیل رسمی کامل", "شکایت حرفه‌ای", "درخواست همکاری", "پاسخ به مشتری",
            "توضیح پروژه", "نظر موافق/مخالف", "متن LinkedIn ساده", "motivation کوتاه",
        ],
        "question_types": [
            "انتخاب جمله‌ی رسمی‌تر", "بهترین بازنویسی", "خلاصه‌سازی درست",
            "انتخاب ساختار حرفه‌ای متن",
        ],
    },
    ("B2", "speaking"): {
        "required": [
            "بیان نظر با دلیل", "توضیح تجربه کاری", "دفاع از انتخاب", "مکالمه کاری",
            "توضیح مشکل پیچیده", "مقایسه گزینه‌ها", "پاسخ به سؤال مصاحبه",
        ],
        "question_types": [
            "انتخاب پاسخ حرفه‌ای", "بهترین جمله در roleplay کاری",
            "جمله‌ی طبیعی‌تر برای بیان نظر",
        ],
    },
    ("B2", "formal_informal"): {
        "required": [
            "تفاوت neutral / formal / professional", "نرم کردن جمله",
            "جلوگیری از بی‌ادبی ناخواسته", "پیام به مشتری", "پیام به سازمان",
            "پیام به همکار", "درخواست حرفه‌ای", "follow-up مودبانه",
        ],
        "question_types": [
            "کدام جمله حرفه‌ای‌تر است؟", "کدام جمله زیادی مستقیم است؟",
            "جمله را دیپلماتیک‌تر کن", "بهترین لحن برای مشتری چیست؟",
            "پیام رسمی را طبیعی‌تر کن",
        ],
    },
}

# Canonical set of supported exam buckets (level, section).
EXAM_BUCKETS: frozenset[tuple[str, str]] = frozenset(TAXONOMY.keys())


def is_supported(level: str, section: str) -> bool:
    return (level, section) in EXAM_BUCKETS


def get_entry(level: str, section: str) -> dict[str, list[str]] | None:
    return TAXONOMY.get((level, section))


def _slugify(text: str, fallback: str) -> str:
    """ASCII slug from the first few Latin words; ``fallback`` if none (e.g. Persian)."""
    tokens = re.findall(r"[A-Za-z]+", text.lower())
    if not tokens:
        return fallback
    return "_".join(tokens[:3])[:40]


def subtopics(level: str, section: str) -> list[tuple[str, str]]:
    """Return [(slug, descriptive_text), ...] for a bucket's required subtopics.

    Slugs are stable (derived from the text, deduplicated) and used as the
    ``topic`` column value; the text drives the AI prompt focus.
    """
    entry = TAXONOMY.get((level, section))
    if entry is None:
        return []
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for i, text in enumerate(entry["required"]):
        slug = _slugify(text, f"{section}_{i}")
        while slug in seen:
            slug = f"{slug}_{i}"
        seen.add(slug)
        out.append((slug, text))
    return out


def subtopic_text(level: str, section: str, slug: str) -> str | None:
    """Reverse-map a topic slug back to its descriptive subtopic text."""
    for s, text in subtopics(level, section):
        if s == slug:
            return text
    return None
