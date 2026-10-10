"""Locale-aware month and weekday names (SPEC §11 "Locale-dependent calendar names", §12).

This is the only module that knows about locales. Everything else asks it
whether a word is a month or a weekday.

* Kairos never reads ``LANG`` / ``LC_*`` itself: :func:`init_from_environment`
  hands that to Python's ``locale`` module (``setlocale(LC_TIME, "")``), which
  applies the platform precedence ``LC_ALL`` > ``LC_TIME`` > ``LANG``.
* No month or weekday name is written in this code base. The names are the ones
  the locale-aware ``calendar`` tables (``datetime`` formatting) return for the
  effective ``LC_TIME`` locale: full and abbreviated forms, nothing else.
* The tables are cached per effective locale and never switched per token.
  Process-global locale state is acceptable for a CLI (SPEC §11).
"""
from __future__ import annotations

import calendar
import locale
import sys
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, FrozenSet, Optional, Set, TextIO


def init_from_environment(error_stream: Optional[TextIO] = None) -> bool:
    """Select the ``LC_TIME`` locale from the environment, as Python's ``locale`` module does.

    Returns True on success. If the requested locale is not installed the failure is
    reported once on stderr (never silent) and the process keeps its current locale.
    """
    try:
        locale.setlocale(locale.LC_TIME, "")
    except locale.Error as exc:
        print(
            f"kairos: warning: cannot use the locale requested by the environment ({exc}); "
            f"month and weekday names follow the locale {current_locale()!r}",
            file=error_stream if error_stream is not None else sys.stderr,
        )
        return False
    return True


def use_locale(name: str) -> None:
    """Select an explicit ``LC_TIME`` locale (tests); raises ``locale.Error`` if it is not installed."""
    locale.setlocale(locale.LC_TIME, name)


def current_locale() -> str:
    """The effective ``LC_TIME`` locale name; also the cache key for everything derived from it."""
    return locale.setlocale(locale.LC_TIME)


@dataclass(frozen=True)
class _Tables:
    months: Dict[str, int]
    weekdays: Dict[str, int]
    ambiguous: FrozenSet[str]
    spellings: FrozenSet[str]  # the names as the locale spells them (for building a matching pattern)


def _collect(sources, table: Dict[str, Set[int]], spellings: Set[str]) -> None:
    for number, forms in sources:
        for form in forms:
            text = form.strip()
            if text:
                spellings.add(text)
                table.setdefault(text.casefold(), set()).add(number)


@lru_cache(maxsize=16)
def _tables(locale_key: str) -> _Tables:  # noqa: ARG001 - the key only selects the cache entry
    months: Dict[str, Set[int]] = {}
    weekdays: Dict[str, Set[int]] = {}
    spellings: Set[str] = set()
    _collect(((i, (calendar.month_name[i], calendar.month_abbr[i])) for i in range(1, 13)), months, spellings)
    _collect(((i, (calendar.day_name[i], calendar.day_abbr[i])) for i in range(7)), weekdays, spellings)
    ambiguous = {n for n, v in months.items() if len(v) > 1}
    ambiguous |= {n for n, v in weekdays.items() if len(v) > 1}
    ambiguous |= set(months) & set(weekdays)
    return _Tables(
        {n: next(iter(v)) for n, v in months.items() if n not in ambiguous},
        {n: next(iter(v)) for n, v in weekdays.items() if n not in ambiguous},
        frozenset(ambiguous),
        frozenset(spellings),
    )


def _current() -> _Tables:
    return _tables(current_locale())


def month_number(text: str) -> Optional[int]:
    """1..12 if *text* is a month name of the effective locale (case-insensitive), else None."""
    return _current().months.get(text.casefold())


def weekday_number(text: str) -> Optional[int]:
    """0..6 (Monday == 0) if *text* is a weekday name of the effective locale, else None."""
    return _current().weekdays.get(text.casefold())


def is_ambiguous(text: str) -> bool:
    """True if the locale gives *text* to more than one month/weekday (it is then rejected)."""
    return text.casefold() in _current().ambiguous


def is_calendar_name(text: str) -> bool:
    """True for every month/weekday name of the locale, including ambiguous ones (reserved words)."""
    folded = text.casefold()
    tables = _current()
    return folded in tables.months or folded in tables.weekdays or folded in tables.ambiguous


def calendar_names() -> FrozenSet[str]:
    """Every month/weekday name as the locale spells it (not case-folded)."""
    return _current().spellings


__all__ = [
    "calendar_names", "current_locale", "init_from_environment", "is_ambiguous",
    "is_calendar_name", "month_number", "use_locale", "weekday_number",
]
