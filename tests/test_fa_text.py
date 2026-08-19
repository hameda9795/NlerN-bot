"""Persian digit and progress-bar helpers."""

from __future__ import annotations

import pytest

from utils.fa_text import fa_digits, progress_bar


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0, "۰"), (40, "۴۰"), (234, "۲۳۴"), ("12/40", "۱۲/۴۰"), ("80%", "۸۰٪")],
)
def test_fa_digits(value, expected):
    assert fa_digits(value) == expected


def test_progress_bar_endpoints():
    assert progress_bar(0, 40) == "▱" * 10
    assert progress_bar(40, 40) == "▰" * 10


def test_started_and_nearly_done_are_visibly_distinct():
    """Rounding must never make 'just started' look untouched, or vice versa."""
    assert progress_bar(1, 40) == "▰" + "▱" * 9  # would round to 0 filled
    assert progress_bar(39, 40) == "▰" * 9 + "▱"  # would round to 10 filled


def test_empty_bank_does_not_divide_by_zero():
    assert progress_bar(0, 0) == "▱" * 10
