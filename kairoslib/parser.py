"""INTERVAL grammar and AST (SPEC §6, §9).

``parse_interval`` turns macro-expanded INTERVAL text into an AST. It validates
structure and value ranges but never evaluates against a clock and never builds
zone objects (``tz`` fields hold the zone token text; resolve with
``timezones.resolve_tz``).

AST conventions (the contract for evaluate.py):

* ``(lo, hi)`` ranges are inclusive; ``lo > hi`` wraps (months, DOM, weekdays, time).
* months are 1..12, weekdays 0..6 with Monday == 0, times are seconds since
  local midnight (``24:00`` == 86400, only as a range end).
* a point time has ``TimeSpec.end is None``; its length is one minute, or one
  second when ``TimeSpec.seconds`` is true.
* ``hours`` (``8h`` == ``8:*``, 0..23) and ``minutes`` (``30m`` == ``*:30``, 0..59)
  are inclusive ranges of whole hours / minutes-of-the-hour; ``lo > hi`` wraps.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Tuple, Union as TUnion

from .errors import IntervalKeeperError
from . import names
from .lexer import UNITS, Token, tokenize, word_kind

Range = Tuple[int, int]


@dataclass(frozen=True)
class TimeSpec:
    start: int
    end: Optional[int] = None  # None: point time
    seconds: bool = False  # the start was written with seconds (HH:MM:SS)


@dataclass(frozen=True)
class DateAtom:
    """An ISODATE; ``None`` is the ``*`` wildcard."""
    year: Optional[int]
    month: Optional[int]
    day: Optional[int]


@dataclass(frozen=True)
class Clause:
    years: Tuple[Range, ...] = ()
    months: Tuple[Range, ...] = ()
    doms: Tuple[Range, ...] = ()
    weekdays: Tuple[Range, ...] = ()
    times: Tuple[TimeSpec, ...] = ()
    dates: Tuple[DateAtom, ...] = ()
    tz: Optional[str] = None
    hours: Tuple[Range, ...] = ()
    minutes: Tuple[Range, ...] = ()


@dataclass(frozen=True)
class DateSide:
    year: Optional[int]  # None: recurring (start) / derived from start (end)
    month: int
    day: int
    time: Optional[int] = None  # seconds since midnight


@dataclass(frozen=True)
class Span:
    """``start -- end``; the end is already resolved against the start (§6.5).

    ``end_year_delta`` (0 or 1) is how many years after the start year the end
    falls when ``end.year`` is None; without times the end day is inclusive.
    """
    start: DateSide
    end: DateSide
    end_year_delta: int = 0
    tz: Optional[str] = None


Term = TUnion[Clause, Span]


@dataclass(frozen=True)
class Union:
    terms: Tuple[Term, ...]


@dataclass(frozen=True)
class Duration:
    """``(count, unit)`` pairs in source order; unit is singular (``day``)."""
    parts: Tuple[Tuple[int, str], ...]


@dataclass(frozen=True)
class RelPlus:
    anchor: Union
    duration: Duration


@dataclass(frozen=True)
class RelUntil:
    duration: Duration
    anchor: Union


@dataclass(frozen=True)
class RelShift:
    """``D before ANCHOR`` (``sign == -1``) / ``D after ANCHOR`` (``sign == 1``): every anchor
    instance moved as a whole by ``sign * D`` (SPEC §9.1)."""
    duration: Duration
    anchor: Union
    sign: int


Part = TUnion[Union, RelPlus, RelUntil, RelShift]


@dataclass(frozen=True)
class Combined:
    """Several comma-separated parts (SPEC §9.2): the union of the parts."""
    parts: Tuple[Part, ...]


Expr = TUnion[Union, RelPlus, RelUntil, RelShift, Combined]

_KIND_FIELD = {
    "YEAR": "years", "MONTH": "months", "DOM": "doms",
    "WEEKDAY": "weekdays", "TIME": "times", "DATE": "dates",
    "HOUR": "hours", "MINUTE": "minutes",
}


class _Fail(Exception):
    pass


def _fail(message: str) -> _Fail:
    return _Fail(message)


def _check_exists(year: Optional[int], month: Optional[int], day: Optional[int], what: str) -> None:
    """Reject dates that can never exist, delegating the calendar to datetime."""
    if month is None or day is None:
        if month is not None and not 1 <= month <= 12:
            raise _fail(f"month out of range in {what}")
        if day is not None and not 1 <= day <= 31:
            raise _fail(f"day out of range in {what}")
        return
    try:
        date(year if year is not None else 2000, month, day)  # 2000 is a leap year: Feb 29 is fine
    except ValueError:
        raise _fail(f"{what} does not exist") from None


def _expand(rng: Range, size: int, first: int) -> List[int]:
    lo, hi = rng
    if lo <= hi:
        return list(range(lo, hi + 1))
    return list(range(lo, first + size)) + list(range(first, hi + 1))


class _Parser:
    def __init__(self, tokens: List[Token]) -> None:
        self.toks = tokens
        self.i = 0

    # -- token helpers -------------------------------------------------
    def peek(self, offset: int = 0) -> Optional[Token]:
        j = self.i + offset
        return self.toks[j] if j < len(self.toks) else None

    def at(self, kind: str, offset: int = 0) -> bool:
        tok = self.peek(offset)
        return tok is not None and tok.kind == kind

    def at_end(self) -> bool:
        return self.i >= len(self.toks)

    def take(self) -> Token:
        tok = self.toks[self.i]
        self.i += 1
        return tok

    @staticmethod
    def kind_of(tok: Optional[Token]) -> Optional[str]:
        if tok is None:
            return None
        if tok.kind == "ISODATE":
            return "DATE"
        if tok.kind == "TIME":
            return "TIME"
        if tok.kind == "TSHORT":
            return "HOUR" if tok.text.endswith("h") else "MINUTE"
        if tok.kind == "NUMBER":
            return "YEAR" if int(tok.text) >= 100 else "DOM"
        wk = word_kind(tok)
        return wk if wk in ("MONTH", "WEEKDAY") else None

    # -- expressions ---------------------------------------------------
    def duration_at(self, offset: int = 0) -> bool:
        """At ``NUMBER unit``: the start of a duration (and so never a list item)."""
        first, second = self.peek(offset), self.peek(offset + 1)
        return first is not None and first.kind == "NUMBER" and second is not None and word_kind(second) == "UNIT"

    def parse_expr(self) -> Expr:
        parts = [self.parse_part()]
        while self.at("COMMA"):
            self.take()
            if self.at_end():
                raise _fail("trailing ','")
            parts.append(self.parse_part())
        self.expect_end()
        return parts[0] if len(parts) == 1 else Combined(tuple(parts))

    def parse_part(self) -> Part:
        if self.duration_at():
            duration = self.parse_duration()
            tok = self.peek()
            keyword = None if tok is None else word_kind(tok)
            if keyword not in ("UNTIL", "BEFORE", "AFTER"):
                raise _fail(
                    "a leading duration must be followed by 'until', 'before' or 'after' "
                    "(e.g. '40 days until Dec 24', '2 days before Apr 10')"
                )
            assert tok is not None
            self.take()
            if self.at_end():
                raise _fail(f"{tok.text!r} needs an anchor interval")
            anchor = self.parse_union()
            if keyword == "UNTIL":
                return RelUntil(duration, anchor)
            return RelShift(duration, anchor, -1 if keyword == "BEFORE" else 1)
        anchor = self.parse_union()
        if self.at("PLUS"):
            self.take()
            duration = self.parse_duration()
            return RelPlus(anchor, duration)
        return anchor

    @staticmethod
    def unexpected(tok: Token, after_tz: Optional[str] = None) -> str:
        if word_kind(tok) == "UNIT":
            hint = f"; {tok.text!r} needs a number before it (a duration is 'NUMBER unit': it follows '+', or comes first before 'until', 'before' or 'after')"
            if after_tz is not None and ("+" in after_tz or "-" in after_tz):
                hint += f"; note that {after_tz!r} is a zone offset, write 'UTC + 2 hours' (with spaces) for a duration"
            return f"unexpected {tok.text!r}{hint}"
        if after_tz is not None:
            return f"unexpected {tok.text!r} after time zone {after_tz!r}; a time zone must end the clause"
        return f"unexpected {tok.text!r}"

    def expect_end(self) -> None:
        if not self.at_end():
            tok = self.peek()
            assert tok is not None
            raise _fail(f"unexpected {tok.text!r}")

    def parse_duration(self) -> Duration:
        parts: List[Tuple[int, str]] = []
        while self.at("NUMBER") and self.peek(1) is not None and word_kind(self.peek(1)) == "UNIT":  # type: ignore[arg-type]
            number = int(self.take().text)
            parts.append((number, UNITS[self.take().text.casefold()]))
        if not parts:
            tok = self.peek()
            raise _fail("expected a duration such as '5 days'" if tok is None else f"expected a duration such as '5 days', got {tok.text!r}")
        if self.at("NUMBER"):
            raise _fail(f"duration number {self.peek().text!r} has no unit")  # type: ignore[union-attr]
        return Duration(tuple(parts))

    # -- unions, terms -------------------------------------------------
    def parse_union(self) -> Union:
        """Terms joined by commas, up to ``+``, a keyword, the end, or a comma before a duration."""
        terms: List[Term] = [self.parse_term()]
        while self.at("COMMA") and not self.duration_at(1):
            self.take()
            if self.at_end() or self.at("PLUS"):
                raise _fail("trailing ','")
            terms.append(self.parse_term())
        return Union(tuple(terms))

    def at_keyword(self) -> bool:
        """At ``until`` / ``before`` / ``after``: the end of a union (and an error unless a duration led)."""
        tok = self.peek()
        return tok is not None and word_kind(tok) in ("UNTIL", "BEFORE", "AFTER")

    def term_end(self) -> int:
        """Index of the first COMMA/PLUS (or end) from here; spans never contain commas."""
        j = self.i
        while j < len(self.toks) and self.toks[j].kind not in ("COMMA", "PLUS"):
            j += 1
        return j

    def parse_term(self) -> Term:
        if self.at_end():
            raise _fail("INTERVAL must not be empty")
        end = self.term_end()
        if any(t.kind == "DASHDASH" for t in self.toks[self.i:end]):
            term: Term = self.parse_span(self.toks[self.i:end])
            self.i = end
            return term
        return self.parse_clause()

    # -- clause --------------------------------------------------------
    def parse_clause(self) -> Clause:
        fields: Dict[str, tuple] = {}
        tz: Optional[str] = None
        while not self.at_end() and not self.at("COMMA") and not self.at("PLUS") and not self.at_keyword():
            tok = self.peek()
            assert tok is not None
            if tok.kind == "TZ":
                tz = self.take().text
                if not (self.at_end() or self.at("COMMA") or self.at("PLUS")):
                    raise _fail(self.unexpected(self.peek(), after_tz=tz))  # type: ignore[arg-type]
                break
            kind = self.kind_of(tok)
            if kind is None:
                if tok.kind == "STAR":
                    raise _fail("'*' is only valid inside a date such as '*-12-25'")
                raise _fail(self.unexpected(tok))
            values = self.parse_item(kind)
            name = _KIND_FIELD[kind]
            if name in fields:
                raise _fail(f"duplicate {kind} item in one clause (join values with ',' to make a list)")
            fields[name] = values
        if not fields:
            tok = self.peek()
            if tok is not None and self.at_keyword():
                raise _fail(
                    f"unexpected {tok.text!r}; 'until', 'before' and 'after' follow a duration, "
                    f"e.g. '5 days {tok.text.casefold()} Dec 24'"
                )
            raise _fail("a clause needs at least one non-time-zone item")
        return self.finish_clause(fields, tz)

    def parse_item(self, kind: str) -> tuple:
        values = []
        while True:
            values.append(self.parse_value(kind))
            if self.at("COMMA") and self.kind_of(self.peek(1)) == kind and not self.duration_at(1):
                self.take()
                continue
            break
        return tuple(values)

    def parse_value(self, kind: str):
        first = self.parse_atom(kind)
        if self.at("DASH"):
            dash = self.take()
            nxt = self.peek()
            if nxt is None:
                raise _fail("range is missing its end after '-'")
            if kind == "DATE":
                raise _fail("date ranges are not allowed; use '--' for spans")
            if self.kind_of(nxt) != kind:
                raise _fail(f"mixed-kind range: {kind.lower()} followed by '-' and {nxt.text!r}")
            second = self.parse_atom(kind)
            return self.make_range(kind, first, second)
        return self.make_point(kind, first)

    def parse_atom(self, kind: str):
        tok = self.take()
        text = tok.text
        if kind == "DATE":
            parts = text.split("-")
            y, m, d = (None if p == "*" else int(p) for p in parts)
            _check_exists(y, m, d, f"date {text!r}")
            return DateAtom(y, m, d)
        if kind == "TIME":
            return self.parse_time(tok)
        if kind == "YEAR":
            year = int(text)
            if not 100 <= year <= 9999:
                raise _fail(f"year {text!r} out of range (100-9999)")
            return year
        if kind == "DOM":
            day = int(text)
            if not 1 <= day <= 31:
                raise _fail(f"day of month {text!r} out of range (1-31)")
            return day
        if kind == "MONTH":
            return names.month_number(text)
        if kind == "HOUR":
            hour = int(text[:-1])
            if hour > 23:
                raise _fail(f"hour {text!r} out of range (0h-23h)")
            return hour
        if kind == "MINUTE":
            minute = int(text[:-3] if text.endswith("min") else text[:-1])
            if minute > 59:
                raise _fail(f"minute {text!r} out of range (0m-59m)")
            return minute
        return names.weekday_number(text)

    @staticmethod
    def parse_time(tok: Token) -> Tuple[int, bool, bool]:
        """Return (seconds since midnight, has_seconds, is_24h)."""
        parts = [int(p) for p in tok.text.split(":")]
        hours, minutes = parts[0], parts[1]
        seconds = parts[2] if len(parts) == 3 else 0
        if hours > 24 or minutes > 59 or seconds > 59 or (hours == 24 and (minutes or seconds)):
            raise _fail(f"time {tok.text!r} out of range")
        return hours * 3600 + minutes * 60 + seconds, len(parts) == 3, hours == 24

    def make_point(self, kind: str, atom):
        if kind == "TIME":
            secs, has_secs, is24 = atom
            if is24:
                raise _fail("'24:00' is only valid as the end of a time range")
            return TimeSpec(secs, None, has_secs)
        if kind == "DATE":
            return atom
        return (atom, atom)

    def make_range(self, kind: str, a, b):
        if kind == "TIME":
            (s1, sec1, is24a), (s2, _sec2, _is24b) = a, b
            if is24a:
                raise _fail("'24:00' is only valid as the end of a time range")
            if s1 == s2:
                raise _fail("time range with equal ends")
            return TimeSpec(s1, s2, sec1)
        if kind == "YEAR" and a > b:
            raise _fail(f"year range {a}-{b} must have start <= end")
        return (a, b)

    def finish_clause(self, fields: Dict[str, tuple], tz: Optional[str]) -> Clause:
        if "dates" in fields and any(k in fields for k in ("years", "months", "doms")):
            raise _fail("a date cannot be combined with a year, month or day-of-month in one clause")
        times = fields.get("times", ())
        if times and len({t.end is None for t in times}) > 1:
            raise _fail("a time list may not mix point times and time ranges")
        if "months" in fields and "doms" in fields:
            months = {m for r in fields["months"] for m in _expand(r, 12, 1)}
            doms = {d for r in fields["doms"] for d in _expand(r, 31, 1)}
            if not any(self.exists(m, d) for m in months for d in doms):
                raise _fail("this month/day combination never exists")
        return Clause(tz=tz, **fields)

    @staticmethod
    def exists(month: int, day: int) -> bool:
        try:
            date(2000, month, day)
        except ValueError:
            return False
        return True

    # -- spans ---------------------------------------------------------
    def parse_span(self, toks: List[Token]) -> Span:
        marks = [k for k, t in enumerate(toks) if t.kind == "DASHDASH"]
        if len(marks) != 1:
            raise _fail("a span has exactly one '--'")
        left_toks, right_toks = toks[:marks[0]], toks[marks[0] + 1:]
        tz: Optional[str] = None
        if right_toks and right_toks[-1].kind == "TZ":
            tz = right_toks[-1].text
            right_toks = right_toks[:-1]
        if not left_toks or not right_toks:
            raise _fail("a span needs a date on both sides of '--'")
        left = self.parse_side(left_toks, "left")
        right = self.parse_side(right_toks, "right")
        return self.build_span(left, right, tz)

    def parse_side(self, toks: List[Token], which: str) -> Tuple[Optional[int], Optional[int], Optional[int], Optional[int]]:
        """Return (year, month, day, time_seconds); month/day may be None only on the right."""
        i = 0
        year = month = day = None
        if toks[0].kind == "ISODATE":
            parts = toks[0].text.split("-")
            year, month, day = (None if p == "*" else int(p) for p in parts)
            i = 1
            if which == "right" and (month is None or day is None):
                raise _fail(f"span end {toks[0].text!r} needs a concrete month and day")
        else:
            if toks[i].kind == "NUMBER" and int(toks[i].text) >= 100:
                year = int(toks[i].text)
                if year > 9999:
                    raise _fail(f"year {toks[i].text!r} out of range (100-9999)")
                i += 1
            if i < len(toks) and word_kind(toks[i]) == "MONTH":
                month = names.month_number(toks[i].text)
                i += 1
            if i < len(toks) and toks[i].kind == "NUMBER" and int(toks[i].text) < 100:
                day = int(toks[i].text)
                if not 1 <= day <= 31:
                    raise _fail(f"day of month {toks[i].text!r} out of range (1-31)")
                i += 1
        time: Optional[int] = None
        if i < len(toks) and toks[i].kind == "TSHORT":
            raise _fail(f"span times must be HH:MM[:SS], not {toks[i].text!r}")
        if i < len(toks) and toks[i].kind == "TIME":
            secs, _has_secs, is24 = self.parse_time(toks[i])
            if is24:
                raise _fail("'24:00' is only valid as the end of a time range")
            time = secs
            i += 1
        if i < len(toks):
            raise _fail(f"unexpected {toks[i].text!r} in a span; sides are '[YEAR] [MONTH] DAY [TIME]' or an ISODATE, no lists, ranges or weekdays")
        if day is None:
            raise _fail(f"span {which} side needs a day of month")
        if which == "left" and month is None:
            raise _fail("span start needs a concrete month and day")
        return year, month, day, time

    def build_span(self, left, right, tz: Optional[str]) -> Span:
        ly, lm, ld, lt = left
        ry, rm, rd, rt = right
        if (lt is None) != (rt is None):
            raise _fail("a span with a time on one side needs a time on both sides")
        _check_exists(ly, lm, ld, "span start")
        delta = 0
        if ry is not None:
            if ly is None:
                raise _fail("span end has a year but the start is recurring (no year)")
            month = rm if rm is not None else lm
            if (ry, month, rd, rt or 0) < (ly, lm, ld, lt or 0) or (lt is not None and (ry, month, rd, rt) == (ly, lm, ld, lt)):
                raise _fail("span end is before its start")
            end_year: Optional[int] = ry
        else:
            if rm is None:
                month = lm
                if rd < ld:
                    month = lm % 12 + 1
                    delta = 1 if month == 1 else 0
            else:
                month = rm
                if (rm, rd) < (lm, ld):
                    delta = 1
            same_day = delta == 0 and month == lm and rd == ld
            if same_day and lt is not None and rt is not None and rt <= lt:
                raise _fail("span end time must be after its start time on the same day")
            end_year = None
        check_year = end_year if end_year is not None else (ly + delta if ly is not None else None)
        _check_exists(check_year, month, rd, "span end")
        return Span(
            DateSide(ly, lm, ld, lt),
            DateSide(end_year, month, rd, rt),
            delta if end_year is None else 0,
            tz,
        )


def parse_interval(text: str, *, path: Optional[str] = None, lineno: Optional[int] = None) -> Expr:
    """Parse macro-expanded INTERVAL text; errors carry *path* and *lineno*."""
    try:
        if not text.strip():
            raise _fail("INTERVAL must not be empty")
        parser = _Parser(tokenize(text))
        return parser.parse_expr()
    except _Fail as exc:
        raise IntervalKeeperError(path, lineno, str(exc)) from None
    except IntervalKeeperError as exc:
        raise IntervalKeeperError(path, lineno, exc.message) from None


__all__ = [
    "Clause", "Combined", "DateAtom", "DateSide", "Duration", "Expr", "Part", "RelPlus", "RelShift", "RelUntil",
    "Span", "TimeSpec", "Union", "parse_interval",
]
