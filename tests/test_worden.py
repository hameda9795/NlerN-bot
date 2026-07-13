"""Unit tests for the واژگان (worden) chapter browser — pure logic, no DB."""

from __future__ import annotations

from services.worden_service import WordRow, describe_table, pretty_label
from utils import rich_cards


def test_pretty_label_humanises_slug():
    assert pretty_label("home_and_furniture") == "Home And Furniture"


def test_describe_table_parent_vs_subtopic():
    # Full-chapter table (single underscore after fasl_NN).
    number, title, topic = describe_table("fasl_03_home_and_furniture")
    assert number == 3
    assert title == "خانه و مبلمان"
    assert topic == "همه‌ی واژگان فصل"

    # Sub-topic table (double underscore).
    number, title, topic = describe_table("fasl_03__appliances")
    assert number == 3
    assert topic == "Appliances"


def test_describe_table_unknown_chapter_falls_back_to_slug():
    number, title, topic = describe_table("fasl_99_made_up_topic")
    assert number == 99
    assert title == "Made Up Topic"


def test_worden_card_standard_columns():
    row = WordRow(
        table="fasl_01_personal_information",
        id=1,
        data={
            "id": 1,
            "word_num": "1",
            "dutch": "voornaam",
            "pronunciation": "VOH-rnahm",
            "persian_translation": "نام کوچک",
            "additional_meanings": "first name",
            "examples": "1. Mijn voornaam is Ahmad.<br>2. Wat is jouw voornaam?",
            "created_at": None,
        },
    )
    md = rich_cards.worden_card(
        row, index=0, total=46, chapter_title="اطلاعات شخصی", topic_label="همه"
    )
    assert "1 از 46" in md
    assert "# voornaam" in md
    assert "نام کوچک" in md
    # <br> separators are converted, never left as literal tags.
    assert "<br>" not in md
    assert "Mijn voornaam is Ahmad." in md
    assert "Wat is jouw voornaam?" in md


def test_worden_card_strips_html_tags_from_values():
    row = WordRow(
        table="fasl_99_x",
        id=1,
        data={"id": 1, "dutch": "fiets <b>de</b>", "persian_translation": "دوچرخه"},
    )
    md = rich_cards.worden_card(row, index=0, total=1, chapter_title="t", topic_label="l")
    # Embedded HTML tags are removed (markdown content, not HTML).
    assert "<b>" not in md
    assert "fiets de" in md


def test_worden_card_common_mistakes_variant():
    row = WordRow(
        table="fasl_48_common_mistakes_for_persian_speakers",
        id=1,
        data={
            "id": 1,
            "common_mistake": "Morgen ik ga.",
            "correct_form": "Morgen ga ik.",
            "explanation_in_persian": "فعل در جایگاه دوم.",
        },
    )
    md = rich_cards.worden_card(
        row, index=2, total=40, chapter_title="اشتباهات", topic_label="همه"
    )
    assert "Morgen ik ga." in md
    assert "Morgen ga ik." in md
    assert "فعل در جایگاه دوم." in md
