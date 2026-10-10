"""Evaluate an INTERVAL AST to a RangeSet of UTC epoch seconds (SPEC §7.1, §9).

Contract: ``evaluate(expr, lo, hi, default_tz)`` returns exactly
``spec ∩ [lo, hi)`` for the half-open window ``[lo, hi)`` (POSIX seconds).

All calendar, weekday, month-length, zone and DST logic is delegated to
``datetime``, ``zoneinfo`` and ``dateutil.relativedelta``. Wall-clock to instant
conversion follows PEP 495 (a nonexistent local time uses the offset before the
transition, an ambiguous one its first occurrence); each endpoint is resolved
independently and ranges that become empty are dropped.
"""
from __future__ import annotations

import calendar
from datetime import date, datetime, timezone, tzinfo
from typing import Dict, Iterator, List, Optional, Sequence, Tuple

from dateutil.relativedelta import relativedelta

from .parser import Clause, Combined, Duration, Expr, RelPlus, RelShift, RelUntil, Span, Term, Union
from .ranges import EMPTY, RangeSet
from .timezones import resolve_tz

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
DAY = 86400

# datetime only represents years 1..9999; stay one day inside both ends.
MIN_T = int((datetime(1, 1, 3, tzinfo=timezone.utc) - _EPOCH).total_seconds())
MAX_T = int((datetime(9999, 12, 29, tzinfo=timezone.utc) - _EPOCH).total_seconds())

_PAD = 3 * DAY  # slack around relative-interval windows (DST, zone offsets)
_MAX_LOOKBACK = 100 * 366 * DAY  # widening cap for anchors that never start/end (always-on)

_ELAPSED = {"second": 1, "minute": 60, "hour": 3600}
_CALENDAR = {"day": "days", "week": "weeks", "month": "months", "year": "years"}
# Upper bound in seconds for one unit, used only to size look-back/forward windows.
_UNIT_MAX = {
    "second": 1, "minute": 60, "hour": 3600, "day": DAY + 3600, "week": 7 * DAY + 3600,
    "month": 31 * DAY + 3600, "year": 366 * DAY + 3600,
}


def to_epoch(dt: datetime) -> int:
    """Aware datetime -> POSIX seconds (uses ``utcoffset``, i.e. PEP 495 ``fold``)."""
    delta = dt - _EPOCH
    return delta.days * DAY + delta.seconds


def from_epoch(t: int, zone: tzinfo) -> datetime:
    return datetime.fromtimestamp(t, zone)


def _clamp(t: int) -> int:
    return max(MIN_T, min(MAX_T, t))


def _local_instant(day: date, secs: int, zone: tzinfo) -> Optional[int]:
    """Instant of local midnight of *day* plus *secs* wall-clock seconds (``secs`` may exceed one day)."""
    ordinal = day.toordinal() + secs // DAY
    if not 1 <= ordinal <= date.max.toordinal():
        return None
    d = date.fromordinal(ordinal)
    tod = secs % DAY
    return to_epoch(datetime(d.year, d.month, d.day, tod // 3600, tod // 60 % 60, tod % 60, tzinfo=zone))


def _in_wrap(value: int, lo: int, hi: int) -> bool:
    return lo <= value <= hi if lo <= hi else (value >= lo or value <= hi)


def _in_any(value: int, ranges: Sequence[Tuple[int, int]]) -> bool:
    return any(_in_wrap(value, a, b) for a, b in ranges)


def _day_matches(clause: Clause, d: date) -> bool:
    if clause.years and not any(a <= d.year <= b for a, b in clause.years):
        return False
    if clause.months and not _in_any(d.month, clause.months):
        return False
    if clause.doms and not _in_any(d.day, clause.doms):
        return False
    if clause.weekdays and not _in_any(d.weekday(), clause.weekdays):
        return False
    if clause.dates and not any(
        (a.year is None or a.year == d.year) and (a.month is None or a.month == d.month) and (a.day is None or a.day == d.day)
        for a in clause.dates
    ):
        return False
    return True


def _expanded(ranges: Sequence[Tuple[int, int]], low: int, high: int) -> List[int]:
    """Sorted values of ``low..high`` selected by inclusive, possibly wrapping *ranges*."""
    return [v for v in range(low, high + 1) if _in_any(v, ranges)]


def _date_atom_values(atoms, attr: str) -> Optional[set]:
    values = {getattr(a, attr) for a in atoms}
    return None if None in values else values


def matching_days(clause: Clause, first: int, last: int) -> Iterator[date]:
    """Dates (ordinals ``first..last``) the clause's day selectors accept, in order.

    Jumps over years and months that cannot match instead of testing every day,
    so a sparse clause such as ``Feb 29`` costs one step per year.
    """
    first, last = max(first, 1), min(last, date.max.toordinal())
    if first > last:
        return
    d_first, d_last = date.fromordinal(first), date.fromordinal(last)
    year_ranges = clause.years
    atoms = clause.dates
    atom_years = _date_atom_values(atoms, "year") if atoms else None
    atom_months = _date_atom_values(atoms, "month") if atoms else None
    atom_days = _date_atom_values(atoms, "day") if atoms else None
    month_set = _expanded(clause.months, 1, 12) if clause.months else list(range(1, 13))
    if atom_months is not None:
        month_set = [m for m in month_set if m in atom_months]
    dom_set = _expanded(clause.doms, 1, 31) if clause.doms else None
    if atom_days is not None:
        dom_set = [d for d in (dom_set if dom_set is not None else range(1, 32)) if d in atom_days]
    for year in range(d_first.year, d_last.year + 1):
        if year_ranges and not any(a <= year <= b for a, b in year_ranges):
            continue
        if atom_years is not None and year not in atom_years:
            continue
        for month in month_set:
            month_len = calendar.monthrange(year, month)[1]
            start = date(year, month, 1).toordinal()
            if start + month_len - 1 < first or start > last:
                continue
            days = range(1, month_len + 1) if dom_set is None else [d for d in dom_set if d <= month_len]
            for dom in days:
                ordinal = start + dom - 1
                if ordinal < first or ordinal > last:
                    continue
                day = date.fromordinal(ordinal)
                if _day_matches(clause, day):
                    yield day


def day_windows(clause: Clause) -> RangeSet:
    """Local time-of-day windows (seconds after the start day's midnight) of a clause.

    ``times``, ``hours`` and ``minutes`` groups must all hold, so they are intersected.
    A window may end after 86400 (it spills into the next day: the day selectors pick
    the *starting* day, D2). Without any of the three the clause covers the whole day.
    """
    groups: List[RangeSet] = []
    if clause.times:
        pairs = []
        for t in clause.times:
            if t.end is None:
                pairs.append((t.start, t.start + (1 if t.seconds else 60)))
            else:
                pairs.append((t.start, t.end if t.end > t.start else t.end + DAY))
        groups.append(RangeSet(pairs))
    if clause.hours:
        groups.append(RangeSet(
            (a * 3600, (b + 1) * 3600 + (0 if a <= b else DAY)) for a, b in clause.hours
        ))
    if clause.minutes:
        pairs = []
        for a, b in clause.minutes:
            for hour in range(24):
                start = hour * 3600 + a * 60
                end = hour * 3600 + (b + 1) * 60 + (0 if a <= b else 3600)
                pairs.append((start, end))
        groups.append(RangeSet(pairs))
    if not groups:
        return RangeSet([(0, DAY)])
    result = groups[0]
    for group in groups[1:]:
        result = result.intersect(group)
    return result


class _Context:
    """Per-evaluation zone cache."""

    def __init__(self, default_tz: tzinfo) -> None:
        self.default_tz = default_tz
        self._zones: Dict[str, tzinfo] = {}

    def zone(self, token: Optional[str]) -> tzinfo:
        if token is None:
            return self.default_tz
        zone = self._zones.get(token)
        if zone is None:
            zone = self._zones[token] = resolve_tz(token)
        return zone


def _local_date(t: int, zone: tzinfo) -> date:
    return from_epoch(_clamp(t), zone).date()


def _eval_clause(clause: Clause, lo: int, hi: int, ctx: _Context) -> RangeSet:
    zone = ctx.zone(clause.tz)
    first = max(1, _local_date(lo, zone).toordinal() - 2)
    last = min(date.max.toordinal(), _local_date(hi - 1, zone).toordinal() + 1)
    windows = day_windows(clause).ranges
    out: List[Tuple[int, int]] = []
    for day in matching_days(clause, first, last):
        for a, b in windows:
            start = _local_instant(day, a, zone)
            end = _local_instant(day, b, zone)
            if start is not None and end is not None and start < end:
                out.append((start, end))
    return RangeSet(out).clip(lo, hi)


def _side_instant(year: int, month: int, day: int, time: Optional[int], is_end: bool, zone: tzinfo) -> Optional[int]:
    """Instant of one span endpoint; an end without a time is exclusive (start of the next day)."""
    try:
        d = date(year, month, day)
    except ValueError:
        # The endpoint does not exist in this year (Feb 29): it collapses to the zero-length
        # instant between the previous existing day and the next one (SPEC §6.5).
        previous = day - 1
        while previous > 0:
            try:
                d = date(year, month, previous)
                break
            except ValueError:
                previous -= 1
        else:
            return None
        return _local_instant(d, DAY, zone)
    if time is not None:
        return _local_instant(d, time, zone)
    return _local_instant(d, DAY if is_end else 0, zone)


def _eval_span(span: Span, lo: int, hi: int, ctx: _Context) -> RangeSet:
    zone = ctx.zone(span.tz)
    if span.start.year is not None:
        years: Sequence[int] = [span.start.year]
    else:
        years = range(max(1, _local_date(lo, zone).year - 2), min(9999, _local_date(hi - 1, zone).year + 1) + 1)
    out: List[Tuple[int, int]] = []
    for year in years:
        end_year = span.end.year if span.end.year is not None else year + span.end_year_delta
        if end_year > 9999:
            continue
        start = _side_instant(year, span.start.month, span.start.day, span.start.time, False, zone)
        end = _side_instant(end_year, span.end.month, span.end.day, span.end.time, True, zone)
        if start is not None and end is not None and start < end:
            out.append((start, end))
    return RangeSet(out).clip(lo, hi)


def _eval_term(term: Term, lo: int, hi: int, ctx: _Context) -> RangeSet:
    if isinstance(term, Clause):
        return _eval_clause(term, lo, hi, ctx)
    return _eval_span(term, lo, hi, ctx)


def _eval_union(union: Union, lo: int, hi: int, ctx: _Context) -> RangeSet:
    if lo >= hi:
        return EMPTY
    result = EMPTY
    for term in union.terms:
        result = result.union(_eval_term(term, lo, hi, ctx))
    return result


def _anchor_zone(anchor: Union, ctx: _Context) -> tzinfo:
    """Zone for duration arithmetic: the zone of the first term that names one, else the default."""
    for term in anchor.terms:
        if term.tz is not None:
            return ctx.zone(term.tz)
    return ctx.default_tz


def _duration_bound(duration: Duration) -> int:
    return sum(count * _UNIT_MAX[unit] for count, unit in duration.parts) + DAY


def _shift(instant: int, duration: Duration, sign: int, zone: tzinfo) -> Optional[int]:
    """``instant ± duration``: calendar units on the wall clock first, then elapsed units."""
    calendar: Dict[str, int] = {}
    elapsed = 0
    for count, unit in duration.parts:
        if unit in _CALENDAR:
            key = _CALENDAR[unit]
            calendar[key] = calendar.get(key, 0) + count
        else:
            elapsed += count * _ELAPSED[unit]
    try:
        local = from_epoch(_clamp(instant), zone)
        if calendar:
            local = local + relativedelta(**{k: sign * v for k, v in calendar.items()})
        return to_epoch(local) + sign * elapsed
    except (OverflowError, ValueError):
        return None


def _eval_plus(expr: RelPlus, lo: int, hi: int, ctx: _Context) -> RangeSet:
    """``ANCHOR + D``: ``[s, s + D)`` for every anchor instance starting at ``s``."""
    zone = _anchor_zone(expr.anchor, ctx)
    reach = _duration_bound(expr.duration) + _PAD
    window_lo = _clamp(lo - reach)
    while True:
        anchor = _eval_union(expr.anchor, window_lo, hi, ctx)
        # An instance beginning exactly at the window start may have begun earlier: look further back.
        truncated = bool(anchor) and anchor.ranges[0][0] == window_lo and window_lo > MIN_T
        if not truncated or lo - window_lo >= _MAX_LOOKBACK:
            break
        window_lo = _clamp(lo - 2 * (lo - window_lo))
    out: List[Tuple[int, int]] = []
    for start, _end in anchor:
        end = _shift(start, expr.duration, 1, zone)
        if end is not None and start < end:
            out.append((start, end))
    return RangeSet(out).clip(lo, hi)


def _is_point_clause(term: Term) -> bool:
    """A bare point time (``08:00``): SPEC §9 calls it an instance of length zero."""
    return (
        isinstance(term, Clause) and bool(term.times) and not term.hours and not term.minutes
        and all(t.end is None for t in term.times)
    )


def _eval_until(expr: RelUntil, lo: int, hi: int, ctx: _Context) -> RangeSet:
    """``D until ANCHOR``: ``[e - D, e)`` for every anchor instance ending at ``e``."""
    zone = _anchor_zone(expr.anchor, ctx)
    reach = _duration_bound(expr.duration) + _PAD
    window_hi = min(MAX_T, hi + reach)
    point_terms = tuple(t for t in expr.anchor.terms if _is_point_clause(t))
    other = Union(tuple(t for t in expr.anchor.terms if not _is_point_clause(t)))
    while True:
        anchor = _eval_union(other, lo, window_hi, ctx) if other.terms else EMPTY
        truncated = bool(anchor) and anchor.ranges[-1][1] == window_hi and window_hi < MAX_T
        if not truncated or window_hi - hi >= _MAX_LOOKBACK:
            break
        window_hi = min(MAX_T, hi + 2 * (window_hi - hi))
    ends = [end for _start, end in anchor]
    if point_terms:
        ends.extend(start for start, _end in _eval_union(Union(point_terms), lo, window_hi, ctx))
    out: List[Tuple[int, int]] = []
    for end in ends:
        begin = _shift(end, expr.duration, -1, zone)
        if begin is not None and begin < end:
            out.append((begin, end))
    return RangeSet(out).clip(lo, hi)


def _eval_shift(expr: RelShift, lo: int, hi: int, ctx: _Context) -> RangeSet:
    """``D before/after ANCHOR``: every anchor instance ``[s, e)`` moved to ``[s ± D, e ± D)``.

    Both endpoints are shifted independently (calendar units on the wall clock, then elapsed
    units), so the instance keeps its length and time of day; a bare point time keeps its
    one-minute length. Only the anchor side that could be cut off by the window is widened.
    """
    zone = _anchor_zone(expr.anchor, ctx)
    reach = _duration_bound(expr.duration) + _PAD
    if expr.sign > 0:  # after: the anchor lies before the result; an instance may begin long before lo
        window_lo, window_hi = _clamp(lo - reach), hi
        while True:
            anchor = _eval_union(expr.anchor, window_lo, window_hi, ctx)
            truncated = bool(anchor) and anchor.ranges[0][0] == window_lo and window_lo > MIN_T
            if not truncated or lo - window_lo >= _MAX_LOOKBACK:
                break
            window_lo = _clamp(lo - 2 * (lo - window_lo))
    else:  # before: the anchor lies after the result; an instance may end long after hi
        window_lo, window_hi = lo, min(MAX_T, hi + reach)
        while True:
            anchor = _eval_union(expr.anchor, window_lo, window_hi, ctx)
            truncated = bool(anchor) and anchor.ranges[-1][1] == window_hi and window_hi < MAX_T
            if not truncated or window_hi - hi >= _MAX_LOOKBACK:
                break
            window_hi = min(MAX_T, hi + 2 * (window_hi - hi))
    out: List[Tuple[int, int]] = []
    for start, end in anchor:
        new_start = _shift(start, expr.duration, expr.sign, zone)
        new_end = _shift(end, expr.duration, expr.sign, zone)
        if new_start is not None and new_end is not None and new_start < new_end:
            out.append((new_start, new_end))
    return RangeSet(out).clip(lo, hi)


def evaluate(expr: Expr, lo: int, hi: int, default_tz: tzinfo) -> RangeSet:
    """Return ``expr ∩ [lo, hi)`` as a RangeSet of POSIX seconds."""
    lo, hi = _clamp(lo), _clamp(hi)
    if lo >= hi:
        return EMPTY
    ctx = _Context(default_tz)
    return _eval_expr(expr, lo, hi, ctx)


def _eval_expr(expr: Expr, lo: int, hi: int, ctx: _Context) -> RangeSet:
    if isinstance(expr, Union):
        return _eval_union(expr, lo, hi, ctx)
    if isinstance(expr, Combined):
        result = EMPTY
        for part in expr.parts:
            result = result.union(_eval_expr(part, lo, hi, ctx))
        return result
    if isinstance(expr, RelPlus):
        return _eval_plus(expr, lo, hi, ctx)
    if isinstance(expr, RelUntil):
        return _eval_until(expr, lo, hi, ctx)
    if isinstance(expr, RelShift):
        return _eval_shift(expr, lo, hi, ctx)
    raise TypeError(f"cannot evaluate {type(expr).__name__}")


__all__ = ["day_windows", "evaluate", "from_epoch", "matching_days", "to_epoch"]
