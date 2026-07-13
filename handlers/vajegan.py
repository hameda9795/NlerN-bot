"""«واژگان» section — currently the separable-verbs browser (افعال جداشدنی).

Flow, all reached from the main menu:

* «📂 واژگان» → a section menu with the «🔗 افعال جداشدنی» button.
* «🔗 افعال جداشدنی» → a grid of particle buttons (aan, af, op …) with counts.
* tap a particle → the verbs for that particle, shown one by one with full
  details and ⬅️/➡️ navigation.

Verbs are *read* from the remote PostgreSQL library
(``services.separable_verb_service``). Browsing is stateless: the current
particle and position are encoded in the inline-button callback data, so no
FSM state is needed and navigation survives a restart.
"""

from __future__ import annotations

import hashlib
import html as _html
import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.config import get_settings
from database.models import User
from utils import rich_cards
from keyboards.main_menu import BTN_VAJEGAN, get_main_menu_keyboard
from keyboards.vajegan_keyboard import (
    CB_IV_LIST,
    CB_IV_SAVED,
    CB_MV_LIST,
    CB_MV_SAVED,
    CB_RV_LIST,
    CB_RV_SAVED,
    CB_SEP_LIST,
    CB_SEP_MENU,
    CB_SEP_SAVED,
    CB_WD_LIST,
    CB_WD_SAVE,
    CB_WD_SAVED,
    categories_keyboard,
    category_label,
    irregular_letters_keyboard,
    irregular_verb_nav_keyboard,
    letters_keyboard,
    main_verb_nav_keyboard,
    particles_keyboard,
    regular_verb_nav_keyboard,
    vajegan_menu_keyboard,
    verb_nav_keyboard,
    worden_chapters_keyboard,
    worden_topics_keyboard,
    worden_word_nav_keyboard,
)
from services import irregular_verb_service as iv
from services import main_verb_service as mv
from services import regular_verb_service as rv
from services import saved_word_service as saved_svc
from services import separable_verb_service as sep
from services import worden_service as wd
from services.irregular_verb_service import IrregularVerb
from services.main_verb_service import MainVerb
from services.regular_verb_service import RegularVerb
from services.separable_verb_service import SeparableVerb
from services.vocab_service import VocabWord

logger = logging.getLogger(__name__)

router = Router(name="vajegan")

_settings = get_settings()

_DISABLED_MSG = (
    "📂 بخش واژگان فعلاً در دسترس نیست.\n"
    "<i>(VOCAB_DATABASE_URL تنظیم نشده.)</i>"
)
_REMOTE_ERROR_MSG = (
    "⚠️ ارتباط با سرور واژگان برقرار نشد. چند لحظه‌ی دیگر دوباره امتحان کن."
)
_EXPIRED_MSG = "این نشست تموم شده 🙂 دوباره از منو «📂 واژگان» رو بزن."

# Saved separable verbs share the bot's `saved_words` table with the B2 words.
# To keep their ids from colliding with `vocabulary.words` ids, they are stored
# under a high offset; the review flow («کلمات سخت من») treats them uniformly.
_SEP_SAVED_ID_OFFSET = 2_000_000_000


def _verb_to_vocab(v: SeparableVerb) -> VocabWord:
    """Map a separable verb onto the saved-word fields used by the review flow."""
    return VocabWord(
        id=_SEP_SAVED_ID_OFFSET + v.id,
        nederlands=v.separable_verb,
        persian=v.meaning_fa,
        pronunciation=v.pronunciation_fa,
        category=f"فعل جداشدنی · پیشوند {v.particle}",
    )


# ---------------------------------------------------------------------------
# Rich-card rendering
# ---------------------------------------------------------------------------
async def _edit_card(callback: CallbackQuery, markdown: str, reply_markup) -> None:
    """Edit the callback's message in place with a rich card (see rich_cards.edit_card)."""
    await rich_cards.edit_card(callback.message, markdown, reply_markup)


# ---------------------------------------------------------------------------
# Entry: «واژگان» section menu
# ---------------------------------------------------------------------------
@router.message(Command("vajegan"))
@router.message(F.text == BTN_VAJEGAN)
async def open_vajegan(message: Message) -> None:
    if not _settings.database.vocab_enabled:
        await message.answer(_DISABLED_MSG, reply_markup=get_main_menu_keyboard())
        return
    await message.answer(
        "📂 <b>واژگان</b>\nیک بخش را انتخاب کن:",
        reply_markup=vajegan_menu_keyboard(),
    )


# ---------------------------------------------------------------------------
# Separable verbs: particle list
# ---------------------------------------------------------------------------
async def _show_particle_list(callback: CallbackQuery) -> None:
    try:
        particles = await sep.list_particles()
    except Exception as exc:  # noqa: BLE001 - friendly message, never crash
        logger.error("Failed to load particles: %s", exc)
        await callback.answer(_REMOTE_ERROR_MSG, show_alert=True)
        return
    if not particles:
        await callback.answer("هیچ فعلی پیدا نشد.", show_alert=True)
        return
    total = sum(p.count for p in particles)
    await callback.message.edit_text(
        f"🔗 <b>افعال جداشدنی</b> — {total} فعل در {len(particles)} پیشوند\n"
        "<i>یک پیشوند را انتخاب کن تا افعالش را یکی‌یکی ببینی.</i>",
        reply_markup=particles_keyboard(particles),
    )
    await callback.answer()


@router.callback_query(F.data == CB_SEP_LIST)
async def cb_particle_list(callback: CallbackQuery) -> None:
    await _show_particle_list(callback)


# ---------------------------------------------------------------------------
# Separable verbs: one verb at a time
# ---------------------------------------------------------------------------
async def _render_verb(
    callback: CallbackQuery, particle: str, index: int, user: User | None
) -> None:
    """Fetch and display the verb at ``index`` of ``particle`` (editing in place)."""
    try:
        total = await sep.count_by_particle(particle)
        verb = await sep.get_verb_by_offset(particle, index)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to load verb %s[%s]: %s", particle, index, exc)
        await callback.answer(_REMOTE_ERROR_MSG, show_alert=True)
        return

    if verb is None or total == 0:
        await callback.answer("این فعل پیدا نشد.", show_alert=True)
        return

    saved = False
    if user is not None:
        saved = await saved_svc.is_word_saved(
            user_id=user.id, vocab_word_id=_SEP_SAVED_ID_OFFSET + verb.id
        )

    await _edit_card(
        callback,
        rich_cards.separable_card(verb, index=index, total=total),
        verb_nav_keyboard(particle=particle, index=index, total=total, saved=saved),
    )


def _parse_particle_index(data: str) -> tuple[str, int] | None:
    """Parse 'prefix:action:<particle>:<index>' -> (particle, index)."""
    _, _, particle, raw_index = data.split(":", 3)
    try:
        return particle, int(raw_index)
    except ValueError:
        return None


@router.callback_query(F.data.startswith("vgsep:go:"))
async def cb_show_verb(callback: CallbackQuery, user: User | None) -> None:
    parsed = _parse_particle_index(callback.data)
    if parsed is None:
        await callback.answer()
        return
    await _render_verb(callback, parsed[0], parsed[1], user)
    await callback.answer()


@router.callback_query(F.data.startswith("vgsep:save:"))
async def cb_save_verb(callback: CallbackQuery, user: User | None) -> None:
    parsed = _parse_particle_index(callback.data)
    if parsed is None or user is None:
        await callback.answer(_EXPIRED_MSG, show_alert=True)
        return
    particle, index = parsed
    try:
        verb = await sep.get_verb_by_offset(particle, index)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to load verb for save %s[%s]: %s", particle, index, exc)
        await callback.answer(_REMOTE_ERROR_MSG, show_alert=True)
        return
    if verb is None:
        await callback.answer("این فعل پیدا نشد.", show_alert=True)
        return

    added = await saved_svc.save_word(user_id=user.id, word=_verb_to_vocab(verb))
    await callback.answer(
        "ذخیره شد ⭐ (در «کلمات سخت من» می‌بینیش)"
        if added
        else "قبلاً ذخیره شده بود ✅"
    )
    # Re-render so the button switches to «✅ ذخیره شد».
    await _render_verb(callback, particle, index, user)


@router.callback_query(F.data == CB_SEP_SAVED)
async def cb_already_saved(callback: CallbackQuery) -> None:
    await callback.answer("این فعل ذخیره شده ✅")


# ===========================================================================
# Main verbs (افعال اصلی / Hoofdwerkwoord) — browse by thematic category.
# Mirrors the separable-verbs flow but reads from `main_verb_service` and keeps
# saved ids under their own offset so they never collide with the others.
# ===========================================================================
_MV_SAVED_ID_OFFSET = 3_000_000_000


def _main_verb_to_vocab(v: MainVerb) -> VocabWord:
    """Map a main verb onto the saved-word fields used by the review flow."""
    return VocabWord(
        id=_MV_SAVED_ID_OFFSET + v.id,
        nederlands=v.verb,
        persian=v.translation_fa,
        pronunciation=v.pronunciation_fa,
        category=f"فعل اصلی · {category_label(v.category)}" if v.category else "فعل اصلی",
    )


async def _show_category_list(callback: CallbackQuery) -> None:
    try:
        categories = await mv.list_categories()
    except Exception as exc:  # noqa: BLE001 - friendly message, never crash
        logger.error("Failed to load categories: %s", exc)
        await callback.answer(_REMOTE_ERROR_MSG, show_alert=True)
        return
    if not categories:
        await callback.answer("هیچ فعلی پیدا نشد.", show_alert=True)
        return
    total = sum(c.count for c in categories)
    await callback.message.edit_text(
        f"📖 <b>افعال اصلی</b> — {total} فعل در {len(categories)} دسته\n"
        "<i>یک دسته را انتخاب کن تا افعالش را یکی‌یکی ببینی.</i>",
        reply_markup=categories_keyboard(categories),
    )
    await callback.answer()


@router.callback_query(F.data == CB_MV_LIST)
async def cb_category_list(callback: CallbackQuery) -> None:
    await _show_category_list(callback)


async def _render_main_verb(
    callback: CallbackQuery, category: str, index: int, user: User | None
) -> None:
    """Fetch and display the verb at ``index`` of ``category`` (editing in place)."""
    try:
        total = await mv.count_by_category(category)
        verb = await mv.get_verb_by_offset(category, index)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to load main verb %s[%s]: %s", category, index, exc)
        await callback.answer(_REMOTE_ERROR_MSG, show_alert=True)
        return

    if verb is None or total == 0:
        await callback.answer("این فعل پیدا نشد.", show_alert=True)
        return

    saved = False
    if user is not None:
        saved = await saved_svc.is_word_saved(
            user_id=user.id, vocab_word_id=_MV_SAVED_ID_OFFSET + verb.id
        )

    await _edit_card(
        callback,
        rich_cards.main_card(
            verb,
            index=index,
            total=total,
            category_label=category_label(verb.category or ""),
        ),
        main_verb_nav_keyboard(
            category=category, index=index, total=total, saved=saved
        ),
    )


@router.callback_query(F.data.startswith("vgmv:go:"))
async def cb_show_main_verb(callback: CallbackQuery, user: User | None) -> None:
    parsed = _parse_particle_index(callback.data)
    if parsed is None:
        await callback.answer()
        return
    await _render_main_verb(callback, parsed[0], parsed[1], user)
    await callback.answer()


@router.callback_query(F.data.startswith("vgmv:save:"))
async def cb_save_main_verb(callback: CallbackQuery, user: User | None) -> None:
    parsed = _parse_particle_index(callback.data)
    if parsed is None or user is None:
        await callback.answer(_EXPIRED_MSG, show_alert=True)
        return
    category, index = parsed
    try:
        verb = await mv.get_verb_by_offset(category, index)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to load main verb for save %s[%s]: %s", category, index, exc)
        await callback.answer(_REMOTE_ERROR_MSG, show_alert=True)
        return
    if verb is None:
        await callback.answer("این فعل پیدا نشد.", show_alert=True)
        return

    added = await saved_svc.save_word(user_id=user.id, word=_main_verb_to_vocab(verb))
    await callback.answer(
        "ذخیره شد ⭐ (در «کلمات سخت من» می‌بینیش)"
        if added
        else "قبلاً ذخیره شده بود ✅"
    )
    # Re-render so the button switches to «✅ ذخیره شد».
    await _render_main_verb(callback, category, index, user)


@router.callback_query(F.data == CB_MV_SAVED)
async def cb_main_verb_already_saved(callback: CallbackQuery) -> None:
    await callback.answer("این فعل ذخیره شده ✅")


# ===========================================================================
# Regular verbs (افعال منظم / Regelmatige Werkwoorden) — browse by first letter.
# Mirrors the separable-verbs flow but reads from `regular_verb_service` and keeps
# saved ids under their own offset so they never collide with the others.
# ===========================================================================
_RV_SAVED_ID_OFFSET = 4_000_000_000


def _regular_verb_to_vocab(v: RegularVerb) -> VocabWord:
    """Map a regular verb onto the saved-word fields used by the review flow."""
    return VocabWord(
        id=_RV_SAVED_ID_OFFSET + v.id,
        nederlands=v.infinitive,
        persian=v.translation_fa,
        pronunciation=None,
        category="فعل منظم",
    )


async def _show_letter_list(callback: CallbackQuery) -> None:
    try:
        letters = await rv.list_letters()
    except Exception as exc:  # noqa: BLE001 - friendly message, never crash
        logger.error("Failed to load letters: %s", exc)
        await callback.answer(_REMOTE_ERROR_MSG, show_alert=True)
        return
    if not letters:
        await callback.answer("هیچ فعلی پیدا نشد.", show_alert=True)
        return
    total = sum(letter.count for letter in letters)
    await callback.message.edit_text(
        f"📝 <b>افعال منظم</b> — {total} فعل در {len(letters)} حرف\n"
        "<i>یک حرف را انتخاب کن تا افعالش را یکی‌یکی ببینی.</i>",
        reply_markup=letters_keyboard(letters),
    )
    await callback.answer()


@router.callback_query(F.data == CB_RV_LIST)
async def cb_letter_list(callback: CallbackQuery) -> None:
    await _show_letter_list(callback)


async def _render_regular_verb(
    callback: CallbackQuery, letter: str, index: int, user: User | None
) -> None:
    """Fetch and display the verb at ``index`` of ``letter`` (editing in place)."""
    try:
        total = await rv.count_by_letter(letter)
        verb = await rv.get_verb_by_offset(letter, index)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to load regular verb %s[%s]: %s", letter, index, exc)
        await callback.answer(_REMOTE_ERROR_MSG, show_alert=True)
        return

    if verb is None or total == 0:
        await callback.answer("این فعل پیدا نشد.", show_alert=True)
        return

    saved = False
    if user is not None:
        saved = await saved_svc.is_word_saved(
            user_id=user.id, vocab_word_id=_RV_SAVED_ID_OFFSET + verb.id
        )

    await _edit_card(
        callback,
        rich_cards.principal_verb_card(
            verb, index=index, total=total, kind="افعال منظم"
        ),
        regular_verb_nav_keyboard(
            letter=letter, index=index, total=total, saved=saved
        ),
    )


@router.callback_query(F.data.startswith("vgrv:go:"))
async def cb_show_regular_verb(callback: CallbackQuery, user: User | None) -> None:
    parsed = _parse_particle_index(callback.data)
    if parsed is None:
        await callback.answer()
        return
    await _render_regular_verb(callback, parsed[0], parsed[1], user)
    await callback.answer()


@router.callback_query(F.data.startswith("vgrv:save:"))
async def cb_save_regular_verb(callback: CallbackQuery, user: User | None) -> None:
    parsed = _parse_particle_index(callback.data)
    if parsed is None or user is None:
        await callback.answer(_EXPIRED_MSG, show_alert=True)
        return
    letter, index = parsed
    try:
        verb = await rv.get_verb_by_offset(letter, index)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to load regular verb for save %s[%s]: %s", letter, index, exc)
        await callback.answer(_REMOTE_ERROR_MSG, show_alert=True)
        return
    if verb is None:
        await callback.answer("این فعل پیدا نشد.", show_alert=True)
        return

    added = await saved_svc.save_word(user_id=user.id, word=_regular_verb_to_vocab(verb))
    await callback.answer(
        "ذخیره شد ⭐ (در «کلمات سخت من» می‌بینیش)"
        if added
        else "قبلاً ذخیره شده بود ✅"
    )
    # Re-render so the button switches to «✅ ذخیره شد».
    await _render_regular_verb(callback, letter, index, user)


@router.callback_query(F.data == CB_RV_SAVED)
async def cb_regular_verb_already_saved(callback: CallbackQuery) -> None:
    await callback.answer("این فعل ذخیره شده ✅")


# ===========================================================================
# Irregular verbs (افعال نامنظم / Onregelmatige Werkwoorden) — browse by first letter.
# Mirrors the regular-verbs flow but reads from `irregular_verb_service` and keeps
# saved ids under their own offset so they never collide with the others.
# ===========================================================================
_IV_SAVED_ID_OFFSET = 5_000_000_000


def _irregular_verb_to_vocab(v: IrregularVerb) -> VocabWord:
    """Map an irregular verb onto the saved-word fields used by the review flow."""
    return VocabWord(
        id=_IV_SAVED_ID_OFFSET + v.id,
        nederlands=v.infinitive,
        persian=v.translation_fa,
        pronunciation=None,
        category="فعل نامنظم",
    )


async def _show_irregular_letter_list(callback: CallbackQuery) -> None:
    try:
        letters = await iv.list_letters()
    except Exception as exc:  # noqa: BLE001 - friendly message, never crash
        logger.error("Failed to load irregular letters: %s", exc)
        await callback.answer(_REMOTE_ERROR_MSG, show_alert=True)
        return
    if not letters:
        await callback.answer("هیچ فعلی پیدا نشد.", show_alert=True)
        return
    total = sum(letter.count for letter in letters)
    await callback.message.edit_text(
        f"⚡️ <b>افعال نامنظم</b> — {total} فعل در {len(letters)} حرف\n"
        "<i>یک حرف را انتخاب کن تا افعالش را یکی‌یکی ببینی.</i>",
        reply_markup=irregular_letters_keyboard(letters),
    )
    await callback.answer()


@router.callback_query(F.data == CB_IV_LIST)
async def cb_irregular_letter_list(callback: CallbackQuery) -> None:
    await _show_irregular_letter_list(callback)


async def _render_irregular_verb(
    callback: CallbackQuery, letter: str, index: int, user: User | None
) -> None:
    """Fetch and display the verb at ``index`` of ``letter`` (editing in place)."""
    try:
        total = await iv.count_by_letter(letter)
        verb = await iv.get_verb_by_offset(letter, index)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to load irregular verb %s[%s]: %s", letter, index, exc)
        await callback.answer(_REMOTE_ERROR_MSG, show_alert=True)
        return

    if verb is None or total == 0:
        await callback.answer("این فعل پیدا نشد.", show_alert=True)
        return

    saved = False
    if user is not None:
        saved = await saved_svc.is_word_saved(
            user_id=user.id, vocab_word_id=_IV_SAVED_ID_OFFSET + verb.id
        )

    await _edit_card(
        callback,
        rich_cards.principal_verb_card(
            verb, index=index, total=total, kind="افعال نامنظم"
        ),
        irregular_verb_nav_keyboard(
            letter=letter, index=index, total=total, saved=saved
        ),
    )


@router.callback_query(F.data.startswith("vgiv:go:"))
async def cb_show_irregular_verb(callback: CallbackQuery, user: User | None) -> None:
    parsed = _parse_particle_index(callback.data)
    if parsed is None:
        await callback.answer()
        return
    await _render_irregular_verb(callback, parsed[0], parsed[1], user)
    await callback.answer()


@router.callback_query(F.data.startswith("vgiv:save:"))
async def cb_save_irregular_verb(callback: CallbackQuery, user: User | None) -> None:
    parsed = _parse_particle_index(callback.data)
    if parsed is None or user is None:
        await callback.answer(_EXPIRED_MSG, show_alert=True)
        return
    letter, index = parsed
    try:
        verb = await iv.get_verb_by_offset(letter, index)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to load irregular verb for save %s[%s]: %s", letter, index, exc)
        await callback.answer(_REMOTE_ERROR_MSG, show_alert=True)
        return
    if verb is None:
        await callback.answer("این فعل پیدا نشد.", show_alert=True)
        return

    added = await saved_svc.save_word(user_id=user.id, word=_irregular_verb_to_vocab(verb))
    await callback.answer(
        "ذخیره شد ⭐ (در «کلمات سخت من» می‌بینیش)"
        if added
        else "قبلاً ذخیره شده بود ✅"
    )
    # Re-render so the button switches to «✅ ذخیره شد».
    await _render_irregular_verb(callback, letter, index, user)


@router.callback_query(F.data == CB_IV_SAVED)
async def cb_irregular_verb_already_saved(callback: CallbackQuery) -> None:
    await callback.answer("این فعل ذخیره شده ✅")


# ===========================================================================
# Chapter-by-chapter thematic vocabulary (واژگان فصل‌ها) — browse by `worden`
# table. Two levels: chapter → topic (table) → words one-by-one. Stateless: the
# table name and offset ride in the callback data, validated against a cached
# allow-list before any query (see `services.worden_service`).
# ===========================================================================
# Saved worden words share the bot's `saved_words` table with the verbs. Unlike
# the verbs, the worden schema spans many tables, so a row id is unique only
# within its own table; combine table name + row id into a stable id in a
# dedicated high band so it never collides with the verb id offsets.
_WD_SAVED_ID_OFFSET = 6_000_000_000


def _worden_vocab_id(table: str, row_id: int) -> int:
    """Stable, collision-resistant saved-word id for a worden row."""
    digest = hashlib.sha1(f"{table}:{row_id}".encode()).hexdigest()[:12]
    return _WD_SAVED_ID_OFFSET + int(digest, 16)


def _worden_to_vocab(
    row, *, table: str, chapter_title: str, topic_label: str
) -> VocabWord:
    """Map a worden row onto the saved-word fields used by the review flow."""
    d = row.data
    head = d.get("dutch") or d.get("dutch_phrase") or d.get("dutch_pattern") or "—"
    persian = d.get("persian_translation") or d.get("persian_meaning")
    pronunciation = d.get("pronunciation")
    return VocabWord(
        id=_worden_vocab_id(table, row.id),
        nederlands=str(head).strip(),
        persian=str(persian).strip() if persian else None,
        pronunciation=str(pronunciation).strip() if pronunciation else None,
        category=f"واژگان · {chapter_title} · {topic_label}",
    )


# Column → display, applied in this order. Missing columns are simply skipped,
# so every table variant (notes / sentence-patterns / common-mistakes / verb
# conjugations) renders with whatever fields it actually has.
async def _show_chapter_list(callback: CallbackQuery) -> None:
    try:
        chapters = await wd.list_chapters()
    except Exception as exc:  # noqa: BLE001 - friendly message, never crash
        logger.error("Failed to load worden chapters: %s", exc)
        await callback.answer(_REMOTE_ERROR_MSG, show_alert=True)
        return
    if not chapters:
        await callback.answer("هیچ فصلی پیدا نشد.", show_alert=True)
        return
    total = sum(c.word_count for c in chapters)
    await callback.message.edit_text(
        f"📚 <b>واژگان</b> — {total} واژه در {len(chapters)} فصل\n"
        "<i>یک فصل را انتخاب کن.</i>",
        reply_markup=worden_chapters_keyboard(chapters),
    )
    await callback.answer()


@router.callback_query(F.data == CB_WD_LIST)
async def cb_worden_chapters(callback: CallbackQuery) -> None:
    await _show_chapter_list(callback)


@router.callback_query(F.data.startswith("vgw:ch:"))
async def cb_worden_topics(callback: CallbackQuery) -> None:
    try:
        number = int(callback.data.split(":", 2)[2])
    except (IndexError, ValueError):
        await callback.answer()
        return
    try:
        topics = await wd.list_topics(number)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to load worden topics for %s: %s", number, exc)
        await callback.answer(_REMOTE_ERROR_MSG, show_alert=True)
        return
    if not topics:
        await callback.answer("این فصل خالی است.", show_alert=True)
        return
    title = await wd.chapter_title(number)
    await callback.message.edit_text(
        f"📚 <b>{_html.escape(title)}</b> — فصل {number}\n"
        "<i>یک موضوع را انتخاب کن تا واژه‌هایش را یکی‌یکی ببینی.</i>",
        reply_markup=worden_topics_keyboard(topics),
    )
    await callback.answer()


async def _render_worden_word(
    callback: CallbackQuery, table: str, index: int, user: User | None
) -> None:
    """Fetch and display the word at ``index`` of ``table`` (editing in place)."""
    try:
        total = await wd.count_rows(table)
        row = await wd.get_row_by_offset(table, index)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to load worden word %s[%s]: %s", table, index, exc)
        await callback.answer(_REMOTE_ERROR_MSG, show_alert=True)
        return
    if row is None or total == 0:
        await callback.answer("این واژه پیدا نشد.", show_alert=True)
        return

    saved = False
    if user is not None:
        saved = await saved_svc.is_word_saved(
            user_id=user.id, vocab_word_id=_worden_vocab_id(table, row.id)
        )

    number, chapter_title, topic_label = wd.describe_table(table)
    await _edit_card(
        callback,
        rich_cards.worden_card(
            row,
            index=index,
            total=total,
            chapter_title=chapter_title,
            topic_label=topic_label,
        ),
        worden_word_nav_keyboard(
            table=table, index=index, total=total, chapter_number=number, saved=saved
        ),
    )


@router.callback_query(F.data.startswith("vgw:go:"))
async def cb_worden_word(callback: CallbackQuery, user: User | None) -> None:
    # vgw:go:<table>:<idx>
    parts = callback.data.split(":", 3)
    if len(parts) != 4:
        await callback.answer()
        return
    table, raw_index = parts[2], parts[3]
    try:
        index = int(raw_index)
    except ValueError:
        await callback.answer()
        return
    await _render_worden_word(callback, table, index, user)
    await callback.answer()


@router.callback_query(F.data.startswith("vgw:save:"))
async def cb_worden_save(callback: CallbackQuery, user: User | None) -> None:
    # vgw:save:<table>:<idx>
    parts = callback.data.split(":", 3)
    if len(parts) != 4 or user is None:
        await callback.answer(_EXPIRED_MSG, show_alert=True)
        return
    table, raw_index = parts[2], parts[3]
    try:
        index = int(raw_index)
    except ValueError:
        await callback.answer()
        return
    try:
        row = await wd.get_row_by_offset(table, index)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to load worden word for save %s[%s]: %s", table, index, exc)
        await callback.answer(_REMOTE_ERROR_MSG, show_alert=True)
        return
    if row is None:
        await callback.answer("این واژه پیدا نشد.", show_alert=True)
        return

    _, chapter_title, topic_label = wd.describe_table(table)
    added = await saved_svc.save_word(
        user_id=user.id,
        word=_worden_to_vocab(
            row, table=table, chapter_title=chapter_title, topic_label=topic_label
        ),
    )
    await callback.answer(
        "ذخیره شد ⭐ (در «کلمات سخت من» می‌بینیش)"
        if added
        else "قبلاً ذخیره شده بود ✅"
    )
    # Re-render so the button switches to «✅ ذخیره شد».
    await _render_worden_word(callback, table, index, user)


@router.callback_query(F.data == CB_WD_SAVED)
async def cb_worden_already_saved(callback: CallbackQuery) -> None:
    await callback.answer("این واژه ذخیره شده ✅")


# ---------------------------------------------------------------------------
# Back to main menu
# ---------------------------------------------------------------------------
@router.callback_query(F.data == CB_SEP_MENU)
async def cb_back_to_menu(callback: CallbackQuery) -> None:
    await callback.message.answer(
        "برگشتی به منوی اصلی. 🏠", reply_markup=get_main_menu_keyboard()
    )
    await callback.answer()
