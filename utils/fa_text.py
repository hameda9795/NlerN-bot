"""Persian-facing text helpers: Eastern-Arabic digits and progress bars.

The bot's whole UI is Persian, so Western digits in the middle of a Persian
sentence read as foreign. Every number the user sees should go through
:func:`fa_digits`.
"""

from __future__ import annotations

_WESTERN_TO_FA = str.maketrans("0123456789%", "۰۱۲۳۴۵۶۷۸۹٪")

_BAR_FILLED = "▰"
_BAR_EMPTY = "▱"


def fa_digits(value: object) -> str:
    """Return ``value`` as text with Persian digits (and ٪ for percent)."""
    return str(value).translate(_WESTERN_TO_FA)


def progress_bar(done: int, total: int, *, width: int = 10) -> str:
    """A fixed-width bar such as ``▰▰▰▱▱▱▱▱▱▱``.

    A started-but-tiny amount always shows at least one filled cell, so "1 of
    40" never looks identical to "not started"; likewise an unfinished amount
    never fills the last cell.
    """
    if total <= 0:
        return _BAR_EMPTY * width
    filled = round(done * width / total)
    if done > 0:
        filled = max(1, filled)
    if done < total:
        filled = min(width - 1, filled)
    filled = max(0, min(width, filled))
    return _BAR_FILLED * filled + _BAR_EMPTY * (width - filled)
