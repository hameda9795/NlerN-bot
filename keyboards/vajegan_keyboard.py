"""Inline keyboards for the «واژگان» section and separable-verbs browsing."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from services.main_verb_service import Category
from services.regular_verb_service import Letter
from services.separable_verb_service import Particle
from services.worden_service import Chapter, Topic

# Callback-data scheme (kept short — 64-byte limit):
#   vgsep:list                  -> show the particle list
#   vgsep:go:<particle>:<idx>   -> show the verb at offset <idx> of <particle>
#   vgsep:menu                  -> back to the main menu
#   vgsep:save:<particle>:<idx> -> save that verb to «کلمات سخت من»
CB_SEP_LIST = "vgsep:list"
CB_SEP_MENU = "vgsep:menu"
CB_SEP_GO = "vgsep:go"  # + ":<particle>:<idx>"
CB_SEP_SAVE = "vgsep:save"  # + ":<particle>:<idx>"
CB_SEP_SAVED = "vgsep:saved"  # already-saved no-op

# Main verbs (افعال اصلی / Hoofdwerkwoord) browsing — same scheme, "vgmv" prefix.
# Category slugs are long (<=48 chars) but still fit the 64-byte callback limit.
#   vgmv:list                  -> show the category list
#   vgmv:go:<category>:<idx>   -> show the verb at offset <idx> of <category>
#   vgmv:save:<category>:<idx> -> save that verb to «کلمات سخت من»
CB_MV_LIST = "vgmv:list"
CB_MV_GO = "vgmv:go"  # + ":<category>:<idx>"
CB_MV_SAVE = "vgmv:save"  # + ":<category>:<idx>"
CB_MV_SAVED = "vgmv:saved"  # already-saved no-op

# Regular verbs (افعال منظم / Regelmatige Werkwoorden) browsing — "vgrv" prefix.
# Grouped by the first letter of the infinitive (A, B, C …).
#   vgrv:list                -> show the letter grid
#   vgrv:go:<letter>:<idx>   -> show the verb at offset <idx> of <letter>
#   vgrv:save:<letter>:<idx> -> save that verb to «کلمات سخت من»
CB_RV_LIST = "vgrv:list"
CB_RV_GO = "vgrv:go"  # + ":<letter>:<idx>"
CB_RV_SAVE = "vgrv:save"  # + ":<letter>:<idx>"
CB_RV_SAVED = "vgrv:saved"  # already-saved no-op

# Irregular verbs (افعال نامنظم / Onregelmatige Werkwoorden) browsing — "vgiv" prefix.
# Grouped by the first letter of the infinitive (A, B, C …), like the regular verbs.
#   vgiv:list                -> show the letter grid
#   vgiv:go:<letter>:<idx>   -> show the verb at offset <idx> of <letter>
#   vgiv:save:<letter>:<idx> -> save that verb to «کلمات سخت من»
CB_IV_LIST = "vgiv:list"
CB_IV_GO = "vgiv:go"  # + ":<letter>:<idx>"
CB_IV_SAVE = "vgiv:save"  # + ":<letter>:<idx>"
CB_IV_SAVED = "vgiv:saved"  # already-saved no-op

# Chapter-by-chapter thematic vocabulary (واژگان فصل‌ها) — "vgw" prefix.
# Read straight from the `worden` schema, one table per (sub)topic.
#   vgw:list                 -> show the chapter list
#   vgw:ch:<number>          -> show the tables (topics) of a chapter
#   vgw:go:<table>:<idx>     -> show the word at offset <idx> of <table>
# Table names (e.g. fasl_03__appliances) carry no ':' so they split cleanly.
CB_WD_LIST = "vgw:list"
CB_WD_CH = "vgw:ch"  # + ":<number>"
CB_WD_GO = "vgw:go"  # + ":<table>:<idx>"
CB_WD_SAVE = "vgw:save"  # + ":<table>:<idx>" -> save that word to «کلمات سخت من»
CB_WD_SAVED = "vgw:saved"  # already-saved no-op

# Friendly Persian labels for the Dutch category slugs (browse buttons stay short).
CATEGORY_LABELS_FA: dict[str, str] = {
    "scheidbare_voorvoegsels_en_geavanceerd": "پیشوندی و پیشرفته",
    "kunst_creatief_en_cultuur": "هنر و فرهنگ",
    "recht_maatschappij_en_abstract": "حقوق و جامعه",
    "communicatie_taal_en_media": "ارتباط و رسانه",
    "dagelijks_leven_huis_en_gezin": "زندگی روزمره",
    "emotie_geest_en_zintuigen": "احساس و ذهن",
    "werk_zaken_en_economie": "کار و اقتصاد",
    "basis_hulp_modal_en_bindwoord": "پایه و کمکی",
    "beweging_en_reizen": "حرکت و سفر",
    "natuur_lichaam_en_gezondheid": "طبیعت و سلامت",
    "techniek_technologie_en_vervoer": "فناوری و حمل‌ونقل",
    "academisch_onderwijs_en_wetenschap": "علم و آموزش",
    "religie_filosofie_en_existentialisme": "دین و فلسفه",
    "divers_informeel_social_media_en_samenstellingen": "متفرقه و شبکه‌های اجتماعی",
    "financieel_recht_en_administratief": "مالی و اداری",
    "landbouw_dieren_en_tuinieren": "کشاورزی و حیوانات",
    "ruimte_tijd_meting_en_wiskunde": "زمان و ریاضی",
    "eten_koken_mode_en_schoonheid": "غذا و مد",
    "militair_veiligheid_en_sport": "نظامی و ورزش",
}


def category_label(slug: str) -> str:
    """Persian label for a category slug, falling back to a cleaned-up slug."""
    return CATEGORY_LABELS_FA.get(slug, slug.replace("_", " "))


def vajegan_menu_keyboard() -> InlineKeyboardMarkup:
    """The «واژگان» section menu. New categories can be added here later."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📚 واژگان", callback_data=CB_WD_LIST)],
            [InlineKeyboardButton(text="🔗 افعال جداشدنی", callback_data=CB_SEP_LIST)],
            [InlineKeyboardButton(text="📖 افعال اصلی", callback_data=CB_MV_LIST)],
            [InlineKeyboardButton(text="📝 افعال منظم", callback_data=CB_RV_LIST)],
            [InlineKeyboardButton(text="⚡️ افعال نامنظم", callback_data=CB_IV_LIST)],
        ]
    )


# ---------------------------------------------------------------------------
# Chapter-by-chapter vocabulary (واژگان فصل‌ها)
# ---------------------------------------------------------------------------
def worden_chapters_keyboard(chapters: list[Chapter]) -> InlineKeyboardMarkup:
    """One button per chapter (1 per row): «<number>. <title> (<count>)»."""
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text=f"{c.number}. {c.title} ({c.word_count})",
                callback_data=f"{CB_WD_CH}:{c.number}",
            )
        ]
        for c in chapters
    ]
    rows.append([InlineKeyboardButton(text="🏠 منو", callback_data=CB_SEP_MENU)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def worden_topics_keyboard(topics: list[Topic]) -> InlineKeyboardMarkup:
    """One button per table in the chapter: the full chapter first, then subtopics."""
    rows: list[list[InlineKeyboardButton]] = []
    for t in topics:
        prefix = "📚 " if t.is_parent else "• "
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{prefix}{t.label} ({t.count})",
                    callback_data=f"{CB_WD_GO}:{t.table}:0",
                )
            ]
        )
    rows.append(
        [InlineKeyboardButton(text="🔙 لیست فصل‌ها", callback_data=CB_WD_LIST)]
    )
    rows.append([InlineKeyboardButton(text="🏠 منو", callback_data=CB_SEP_MENU)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def worden_word_nav_keyboard(
    *, table: str, index: int, total: int, chapter_number: int, saved: bool
) -> InlineKeyboardMarkup:
    """Prev/next navigation under a word card, plus save, back-to-topics and menu."""
    nav: list[InlineKeyboardButton] = []
    if index > 0:
        nav.append(
            InlineKeyboardButton(
                text="⬅️ قبلی", callback_data=f"{CB_WD_GO}:{table}:{index - 1}"
            )
        )
    if index < total - 1:
        nav.append(
            InlineKeyboardButton(
                text="بعدی ➡️", callback_data=f"{CB_WD_GO}:{table}:{index + 1}"
            )
        )
    save_btn = (
        InlineKeyboardButton(text="✅ ذخیره شد", callback_data=CB_WD_SAVED)
        if saved
        else InlineKeyboardButton(
            text="💾 ذخیره در کلمات سخت من",
            callback_data=f"{CB_WD_SAVE}:{table}:{index}",
        )
    )
    rows: list[list[InlineKeyboardButton]] = []
    if nav:
        rows.append(nav)
    rows.append([save_btn])
    rows.append(
        [InlineKeyboardButton(text="🔙 موضوع‌ها", callback_data=f"{CB_WD_CH}:{chapter_number}")]
    )
    rows.append([InlineKeyboardButton(text="🏠 منو", callback_data=CB_SEP_MENU)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def particles_keyboard(particles: list[Particle]) -> InlineKeyboardMarkup:
    """One button per particle (3 per row), each showing its verb count."""
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for p in particles:
        row.append(
            InlineKeyboardButton(
                text=f"{p.name} ({p.count})",
                callback_data=f"{CB_SEP_GO}:{p.name}:0",
            )
        )
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="🏠 منو", callback_data=CB_SEP_MENU)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def verb_nav_keyboard(
    *, particle: str, index: int, total: int, saved: bool
) -> InlineKeyboardMarkup:
    """Prev/next navigation under a verb card, plus save, back-to-list and menu."""
    nav: list[InlineKeyboardButton] = []
    if index > 0:
        nav.append(
            InlineKeyboardButton(
                text="⬅️ قبلی", callback_data=f"{CB_SEP_GO}:{particle}:{index - 1}"
            )
        )
    if index < total - 1:
        nav.append(
            InlineKeyboardButton(
                text="بعدی ➡️", callback_data=f"{CB_SEP_GO}:{particle}:{index + 1}"
            )
        )
    save_btn = (
        InlineKeyboardButton(text="✅ ذخیره شد", callback_data=CB_SEP_SAVED)
        if saved
        else InlineKeyboardButton(
            text="💾 ذخیره در کلمات سخت من",
            callback_data=f"{CB_SEP_SAVE}:{particle}:{index}",
        )
    )
    rows: list[list[InlineKeyboardButton]] = []
    if nav:
        rows.append(nav)
    rows.append([save_btn])
    rows.append(
        [InlineKeyboardButton(text="🔙 لیست پیشوندها", callback_data=CB_SEP_LIST)]
    )
    rows.append([InlineKeyboardButton(text="🏠 منو", callback_data=CB_SEP_MENU)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def categories_keyboard(categories: list[Category]) -> InlineKeyboardMarkup:
    """One button per category (1 per row), each showing its verb count."""
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text=f"{category_label(c.name)} ({c.count})",
                callback_data=f"{CB_MV_GO}:{c.name}:0",
            )
        ]
        for c in categories
    ]
    rows.append([InlineKeyboardButton(text="🏠 منو", callback_data=CB_SEP_MENU)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def main_verb_nav_keyboard(
    *, category: str, index: int, total: int, saved: bool
) -> InlineKeyboardMarkup:
    """Prev/next navigation under a main-verb card, plus save, back and menu."""
    nav: list[InlineKeyboardButton] = []
    if index > 0:
        nav.append(
            InlineKeyboardButton(
                text="⬅️ قبلی", callback_data=f"{CB_MV_GO}:{category}:{index - 1}"
            )
        )
    if index < total - 1:
        nav.append(
            InlineKeyboardButton(
                text="بعدی ➡️", callback_data=f"{CB_MV_GO}:{category}:{index + 1}"
            )
        )
    save_btn = (
        InlineKeyboardButton(text="✅ ذخیره شد", callback_data=CB_MV_SAVED)
        if saved
        else InlineKeyboardButton(
            text="💾 ذخیره در کلمات سخت من",
            callback_data=f"{CB_MV_SAVE}:{category}:{index}",
        )
    )
    rows: list[list[InlineKeyboardButton]] = []
    if nav:
        rows.append(nav)
    rows.append([save_btn])
    rows.append(
        [InlineKeyboardButton(text="🔙 لیست دسته‌ها", callback_data=CB_MV_LIST)]
    )
    rows.append([InlineKeyboardButton(text="🏠 منو", callback_data=CB_SEP_MENU)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def letters_keyboard(letters: list[Letter]) -> InlineKeyboardMarkup:
    """One button per first letter (4 per row), each showing its verb count."""
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for letter in letters:
        row.append(
            InlineKeyboardButton(
                text=f"{letter.name} ({letter.count})",
                callback_data=f"{CB_RV_GO}:{letter.name}:0",
            )
        )
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="🏠 منو", callback_data=CB_SEP_MENU)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def regular_verb_nav_keyboard(
    *, letter: str, index: int, total: int, saved: bool
) -> InlineKeyboardMarkup:
    """Prev/next navigation under a regular-verb card, plus save, back and menu."""
    nav: list[InlineKeyboardButton] = []
    if index > 0:
        nav.append(
            InlineKeyboardButton(
                text="⬅️ قبلی", callback_data=f"{CB_RV_GO}:{letter}:{index - 1}"
            )
        )
    if index < total - 1:
        nav.append(
            InlineKeyboardButton(
                text="بعدی ➡️", callback_data=f"{CB_RV_GO}:{letter}:{index + 1}"
            )
        )
    save_btn = (
        InlineKeyboardButton(text="✅ ذخیره شد", callback_data=CB_RV_SAVED)
        if saved
        else InlineKeyboardButton(
            text="💾 ذخیره در کلمات سخت من",
            callback_data=f"{CB_RV_SAVE}:{letter}:{index}",
        )
    )
    rows: list[list[InlineKeyboardButton]] = []
    if nav:
        rows.append(nav)
    rows.append([save_btn])
    rows.append(
        [InlineKeyboardButton(text="🔙 لیست حروف", callback_data=CB_RV_LIST)]
    )
    rows.append([InlineKeyboardButton(text="🏠 منو", callback_data=CB_SEP_MENU)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def irregular_letters_keyboard(letters: list[Letter]) -> InlineKeyboardMarkup:
    """One button per first letter (4 per row), each showing its verb count."""
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for letter in letters:
        row.append(
            InlineKeyboardButton(
                text=f"{letter.name} ({letter.count})",
                callback_data=f"{CB_IV_GO}:{letter.name}:0",
            )
        )
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="🏠 منو", callback_data=CB_SEP_MENU)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def irregular_verb_nav_keyboard(
    *, letter: str, index: int, total: int, saved: bool
) -> InlineKeyboardMarkup:
    """Prev/next navigation under an irregular-verb card, plus save, back and menu."""
    nav: list[InlineKeyboardButton] = []
    if index > 0:
        nav.append(
            InlineKeyboardButton(
                text="⬅️ قبلی", callback_data=f"{CB_IV_GO}:{letter}:{index - 1}"
            )
        )
    if index < total - 1:
        nav.append(
            InlineKeyboardButton(
                text="بعدی ➡️", callback_data=f"{CB_IV_GO}:{letter}:{index + 1}"
            )
        )
    save_btn = (
        InlineKeyboardButton(text="✅ ذخیره شد", callback_data=CB_IV_SAVED)
        if saved
        else InlineKeyboardButton(
            text="💾 ذخیره در کلمات سخت من",
            callback_data=f"{CB_IV_SAVE}:{letter}:{index}",
        )
    )
    rows: list[list[InlineKeyboardButton]] = []
    if nav:
        rows.append(nav)
    rows.append([save_btn])
    rows.append(
        [InlineKeyboardButton(text="🔙 لیست حروف", callback_data=CB_IV_LIST)]
    )
    rows.append([InlineKeyboardButton(text="🏠 منو", callback_data=CB_SEP_MENU)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
