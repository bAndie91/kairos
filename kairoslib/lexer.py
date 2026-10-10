"""INTERVAL tokenisation (SPEC §6.1) and the shared reserved-word vocabulary.

The lexer never builds zone objects: a ``TZ`` token only carries the zone text,
after checking it is acceptable to :func:`kairoslib.timezones.resolve_tz`.
Month and weekday names are not known here at all: they come from
:mod:`kairoslib.names`, i.e. from the effective ``LC_TIME`` locale.

Public contract used by other modules (notably macros, M3):

* ``UNITS`` / ``KEYWORDS``: grammar words (duration units, ``until`` / ``before`` / ``after``)
* ``is_reserved_word(text)``: True for every word a macro name may not equal
* ``is_tz_token(text)``: True if *text* is an accepted time-zone token
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import re
from typing import List, Optional, Pattern

from . import names
from .errors import IntervalKeeperError
from .timezones import resolve_tz, zone_id_exists

# Duration units (SPEC §9): singular or plural, mapped to the singular form.
UNITS = {}
for _unit in ("second", "minute", "hour", "day", "week", "month", "year"):
    UNITS[_unit] = _unit
    UNITS[_unit + "s"] = _unit

KEYWORDS = {"until": "UNTIL", "before": "BEFORE", "after": "AFTER"}
UTC_WORDS = frozenset({"utc", "gmt", "z"})

_GRAMMAR_WORDS = frozenset(set(UNITS) | set(KEYWORDS) | set(UTC_WORDS))


def is_reserved_word(text: str) -> bool:
    """True if *text* (case-insensitive) is a grammar word or a month/weekday name of the locale."""
    return text.casefold() in _GRAMMAR_WORDS or names.is_calendar_name(text)


@dataclass(frozen=True)
class Token:
    kind: str  # ISODATE TIME TSHORT NUMBER DASHDASH DASH PLUS COMMA STAR TZ WORD
    text: str
    pos: int


_BEFORE_NAMES = r"""
    (?P<WS>\s+)
  | (?P<TZPATH>[A-Za-z][A-Za-z0-9_+\-]*(?:/[A-Za-z0-9_+\-]+)+)
  | (?P<ISODATE>(?:\d{4}|\*)-(?:\d{1,2}|\*)-(?:\d{1,2}|\*)(?!\d))
  | (?P<TIME>\d{1,2}:\d{2}(?::\d{2})?(?!\d))
  | (?P<TSHORT>\d+(?:min|h|m)(?![A-Za-z0-9_]))
  | (?P<TZOFF>(?i:UTC|GMT)[+-]\d+(?::\d+)?)
  | (?P<NUMBER>\d+)
  | (?P<DASHDASH>--)
  | (?P<DASH>-)
  | (?P<PLUS>\+)
  | (?P<COMMA>,)
  | (?P<STAR>\*)
"""
_AFTER_NAMES = r"""
  | (?P<WORD>[^\W\d_]\w*)
"""


@lru_cache(maxsize=16)
def _compiled(locale_key: str) -> Pattern[str]:
    """Token pattern for one effective locale: the locale's own month/weekday spellings, longest first,
    matched as whole words (so punctuation such as the dot in ``janv.`` stays part of the name)."""
    spellings = sorted(names.calendar_names(), key=len, reverse=True)
    if spellings:
        alternatives = "|".join(re.escape(text) for text in spellings)
        name_group = rf"  | (?P<LNAME>(?<!\w)(?i:{alternatives})(?!\w))"
    else:  # pragma: no cover - a locale without any names
        name_group = "  | (?P<LNAME>(?!))"
    return re.compile(_BEFORE_NAMES + name_group + _AFTER_NAMES, re.VERBOSE)


def is_tz_token(text: str) -> bool:
    """True if *text* is a time-zone token accepted by SPEC §8.1."""
    try:
        resolve_tz(text)
    except IntervalKeeperError:
        return False
    return True


def _error(message: str) -> IntervalKeeperError:
    # Path and line are attached by parser.parse_interval.
    return IntervalKeeperError(None, None, message)


def tokenize(text: str) -> List[Token]:
    """Split macro-expanded INTERVAL text into tokens, longest match first."""
    pattern = _compiled(names.current_locale())
    tokens: List[Token] = []
    pos = 0
    while pos < len(text):
        match = pattern.match(text, pos)
        if match is None:
            raise _error(f"unexpected character {text[pos]!r}")
        kind = match.lastgroup or ""
        value = match.group()
        start = pos
        pos = match.end()
        if kind == "WS":
            continue
        if kind in ("TZPATH", "TZOFF"):
            resolve_tz(value)  # validates; raises a user-facing error naming the token
            tokens.append(Token("TZ", value, start))
        elif kind == "LNAME":
            if names.is_ambiguous(value):
                raise _error(f"ambiguous month/weekday name {value!r} in the current locale")
            tokens.append(Token("WORD", value, start))
        elif kind == "WORD":
            folded = value.casefold()
            if folded in UTC_WORDS or (not is_reserved_word(value) and zone_id_exists(value)):
                tokens.append(Token("TZ", value, start))
            elif is_reserved_word(value):
                tokens.append(Token("WORD", value, start))
            else:
                hint = ""
                if re.fullmatch(r"[A-Z]{2,5}", value):
                    hint = "; alphabetic time-zone abbreviations are not supported, use an IANA zone ID or a numeric UTC offset"
                raise _error(f"unknown word {value!r} (undefined macro?){hint}")
        else:
            tokens.append(Token(kind, value, start))
    return tokens


def word_kind(token: Token) -> Optional[str]:
    """Classify a WORD token as ``MONTH``, ``WEEKDAY``, ``UNIT``, ``UNTIL``, ``BEFORE``, ``AFTER`` or None."""
    if token.kind != "WORD":
        return None
    if names.month_number(token.text) is not None:
        return "MONTH"
    if names.weekday_number(token.text) is not None:
        return "WEEKDAY"
    folded = token.text.casefold()
    if folded in UNITS:
        return "UNIT"
    return KEYWORDS.get(folded)


__all__ = ["KEYWORDS", "UNITS", "Token", "is_reserved_word", "is_tz_token", "tokenize", "word_kind"]
