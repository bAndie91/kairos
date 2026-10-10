"""INTERVAL tokenisation (SPEC §6.1) and the shared reserved-word vocabulary.

The lexer never builds zone objects: a ``TZ`` token only carries the zone text,
after checking it is acceptable to :func:`kairoslib.timezones.resolve_tz`.

Public contract used by other modules (notably macros, M3):

* ``MONTHS`` / ``WEEKDAYS`` / ``UNITS``: casefolded name -> number / canonical unit
* ``RESERVED_WORDS``: every casefolded word a macro name may not equal
* ``is_tz_token(text)``: True if *text* is an accepted time-zone token
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import List, Optional

from .errors import IntervalKeeperError
from .timezones import resolve_tz, zone_id_exists

_MONTH_FULL = (
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
)
_WEEKDAY_FULL = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")

# English, case-insensitive, locale-independent (SPEC §6.2). Months are 1..12;
# weekdays follow datetime.weekday() (Monday == 0).
MONTHS = {}
for _i, _name in enumerate(_MONTH_FULL, 1):
    MONTHS[_name] = _i
    MONTHS[_name[:3]] = _i
MONTHS["sept"] = 9

WEEKDAYS = {}
for _i, _name in enumerate(_WEEKDAY_FULL):
    WEEKDAYS[_name] = _i
    WEEKDAYS[_name[:3]] = _i

# Duration units (SPEC §9): singular or plural, mapped to the singular form.
UNITS = {}
for _unit in ("second", "minute", "hour", "day", "week", "month", "year"):
    UNITS[_unit] = _unit
    UNITS[_unit + "s"] = _unit

UTC_WORDS = frozenset({"utc", "gmt", "z"})

RESERVED_WORDS = frozenset(set(MONTHS) | set(WEEKDAYS) | set(UNITS) | {"until"} | set(UTC_WORDS))


@dataclass(frozen=True)
class Token:
    kind: str  # ISODATE TIME TSHORT NUMBER DASHDASH DASH PLUS COMMA STAR TZ WORD
    text: str
    pos: int


_TOKEN_RE = re.compile(
    r"""
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
  | (?P<WORD>[^\W\d_]\w*)
    """,
    re.VERBOSE,
)


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
    tokens: List[Token] = []
    pos = 0
    while pos < len(text):
        match = _TOKEN_RE.match(text, pos)
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
        elif kind == "WORD":
            folded = value.casefold()
            if folded in UTC_WORDS or (folded not in RESERVED_WORDS and zone_id_exists(value)):
                tokens.append(Token("TZ", value, start))
            elif folded in RESERVED_WORDS:
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
    """Classify a WORD token as ``MONTH``, ``WEEKDAY``, ``UNIT``, ``UNTIL`` or None."""
    if token.kind != "WORD":
        return None
    folded = token.text.casefold()
    if folded in MONTHS:
        return "MONTH"
    if folded in WEEKDAYS:
        return "WEEKDAY"
    if folded in UNITS:
        return "UNIT"
    if folded == "until":
        return "UNTIL"
    return None


__all__ = [
    "MONTHS", "WEEKDAYS", "UNITS", "RESERVED_WORDS", "Token",
    "is_tz_token", "tokenize", "word_kind",
]
