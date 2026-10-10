"""``--next-change``: the next instant at which the reported states change (SPEC §10).

A reported-state change is exactly a boundary of some ``U(name)`` (SPEC §7.4):
``U(name)`` is a merged half-open :class:`~kairoslib.ranges.RangeSet`, so a state
ending at ``T`` while another line of the same name starts at ``T`` leaves no
boundary, and hidden or STATE-less lines never appear in it. The complete
reported set therefore differs between ``T-1`` and ``T`` iff ``T`` is a boundary
of some ``U(name)``.

Search
------
* The future is explored in consecutive segments of growing length, each one
  evaluated from the AST (clauses jump straight to matching dates, spans emit
  their endpoints, relative intervals are shifted anchor instances); no
  second-by-second or date-by-date scan is done and there is no fixed horizon.
* Termination (SPEC §10.1): explicit-year contributions and relative-interval
  duration tails are *finite exceptions* and end at :func:`finite_end`. Every
  IANA zone in use follows its recurring TZif rule only after
  :func:`~kairoslib.timezones.recurrence_start`. Everything else repeats with the
  Gregorian 400-year cycle (146,097 days), so once past all of those, one
  complete cycle without a change proves that no later change exists.
  The search is bounded only by the representable ``datetime`` domain.
"""
from __future__ import annotations

from datetime import datetime, timezone, tzinfo
from typing import Iterable, Iterator, List, Optional, Sequence, Set, Tuple

from .evaluate import MAX_T, MIN_T, _duration_bound, from_epoch, to_epoch
from .parser import Clause, Expr, RelPlus, RelShift, RelUntil, Span, Union
from .ranges import RangeSet
from .states import Line, reported_sets
from .timezones import recurrence_start, resolve_tz

CYCLE_DAYS = 146_097  # days in 400 Gregorian years
CYCLE = CYCLE_DAYS * 86400

_FIRST_SEGMENT = 2 * 86400
_GROWTH = 4


def _terms(expr: Expr) -> Iterator:
    """Every clause/span of an expression, including relative anchors."""
    union = expr if isinstance(expr, Union) else expr.anchor
    yield from union.terms


def _explicit_years(term) -> Iterator[int]:
    """Years named explicitly by a clause or span (finite contributions)."""
    if isinstance(term, Clause):
        for _lo, hi in term.years:
            yield hi
        for atom in term.dates:
            if atom.year is not None:
                yield atom.year
    elif isinstance(term, Span):
        for year in (term.start.year, term.end.year):
            if year is not None:
                yield year
        if term.start.year is not None:
            yield term.start.year + term.end_year_delta


def finite_end(exprs: Iterable[Expr]) -> int:
    """First instant after which no explicit-year term or duration tail can still matter (0 if none)."""
    last_year = 0
    tail = 0
    for expr in exprs:
        for term in _terms(expr):
            for year in _explicit_years(term):
                last_year = max(last_year, year)
        if isinstance(expr, (RelPlus, RelUntil, RelShift)):
            tail = max(tail, _duration_bound(expr.duration))
    if not last_year:
        return 0
    if last_year >= 9999:
        return MAX_T
    # end of the last named year, plus slack for zone offsets, then every duration tail
    return min(MAX_T, to_epoch(datetime(last_year + 1, 1, 1, tzinfo=timezone.utc)) + 2 * 86400 + tail)


def zones_in_use(exprs: Iterable[Expr], default_tz: tzinfo) -> List[tzinfo]:
    zones: List[tzinfo] = [default_tz]
    seen: Set[str] = set()
    for expr in exprs:
        for term in _terms(expr):
            token = term.tz
            if token is not None and token not in seen:
                seen.add(token)
                zones.append(resolve_tz(token))
    return zones


def search_limit(lines: Sequence[Line], at: int, tz: tzinfo) -> int:
    """Last instant that has to be searched before concluding that nothing changes any more."""
    exprs = [line.expr for line in lines if line.expr is not None]
    start = max(
        at,
        finite_end(exprs),
        max(recurrence_start(zone) for zone in zones_in_use(exprs, tz)),
    )
    return min(MAX_T, start + CYCLE)


def next_change(lines: Sequence[Line], at: int, tz: tzinfo) -> Optional[int]:
    """The first instant ``T > at`` where the reported state set differs from the one at ``T - 1``.

    Returns None if the states never change again (within the representable datetime domain).
    *lines* must come from ``build_lines`` without a window (nothing pruned).
    """
    at = max(MIN_T, min(MAX_T, at))
    limit = search_limit(lines, at, tz)
    lo = at
    length = _FIRST_SEGMENT
    while lo < limit:
        hi = min(limit, lo + length)
        sets = reported_sets(lines, lo, hi, tz)
        best: Optional[int] = None
        for ranges in sets.values():
            # Boundaries at ``lo`` and ``hi`` come from clipping the window, not from the schedule.
            boundary = ranges.next_boundary(lo)
            if boundary is not None and boundary < hi and (best is None or boundary < best):
                best = boundary
        if best is not None:
            return best
        if hi >= limit:
            break  # a complete recurrence cycle past every finite exception had no change
        lo = hi - 1  # overlap one second so a boundary exactly at ``hi`` is compared next time
        length *= _GROWTH
    return None


def format_instant(t: int, zone: tzinfo, fmt: str) -> Tuple[str, bool]:
    """Format *t* in *zone* per ``--format``; also report whether the local time is ambiguous (DST fold)."""
    local = from_epoch(t, zone)
    ambiguous = local.replace(fold=0).utcoffset() != local.replace(fold=1).utcoffset()
    if fmt == "epoch":
        return str(t), ambiguous
    if fmt == "iso":
        return local.isoformat(), ambiguous
    return local.strftime(fmt), ambiguous


def format_is_offset_aware(fmt: str) -> bool:
    """True if the output identifies the instant unambiguously (keyword or an offset/zone directive)."""
    return fmt in ("epoch", "iso") or any(d in fmt for d in ("%z", "%Z", "%s", "%c", "%+"))


__all__ = [
    "CYCLE", "CYCLE_DAYS", "finite_end", "format_instant", "format_is_offset_aware",
    "next_change", "search_limit", "zones_in_use",
]
