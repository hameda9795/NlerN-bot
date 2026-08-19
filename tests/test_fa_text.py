"""Persian digit and progress-bar helpers."""

from __future__ import annotations

import re

import pytest

from utils.fa_text import fa_digits, progress_bar

FILLED, EMPTY = "🟩", "⬜"


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0, "۰"), (40, "۴۰"), (234, "۲۳۴"),
     ("12/40", "۱۲/۴۰"), ("80%", "۸۰٪")],
)
def test_fa_digits(value, expected):
    assert fa_digits(value) == expected


def test_progress_bar_endpoints():
    assert progress_bar(0, 40) == EMPTY * 5
    assert progress_bar(40, 40) == FILLED * 5


def test_started_and_nearly_done_are_visibly_distinct():
    """Rounding must never make 'just started' look untouched, or vice versa."""
    assert progress_bar(1, 40) == FILLED + EMPTY * 4  # would round to 0 filled
    assert progress_bar(39, 40) == FILLED * 4 + EMPTY  # would round to 5 filled


def test_empty_bank_does_not_divide_by_zero():
    assert progress_bar(0, 0) == EMPTY * 5


def test_bar_uses_only_emoji():
    """Geometric glyphs (▰▱, █░) render as empty boxes on Telegram clients."""
    bar = progress_bar(3, 10)
    assert not re.search(r"[▀-▟■-◿]", bar)
    assert set(bar) <= {FILLED, EMPTY}
