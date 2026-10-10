"""Half-open range-set algebra over integers (SPEC §7.1).

Instants are POSIX seconds (UTC, resolution one second), but nothing here is
time-specific: a ``RangeSet`` is a sorted tuple of disjoint, non-adjacent
``(start, end)`` pairs meaning ``[start, end)``. Adjacent and overlapping
ranges are merged on construction, so a boundary is always a real change.

This is Kairos' own set algebra (SPEC §12); calendar and zone logic lives in
``evaluate.py`` and uses ``datetime`` / ``zoneinfo`` / ``dateutil``.
"""
from __future__ import annotations

from bisect import bisect_right
from typing import Iterable, Iterator, List, Optional, Tuple

Pair = Tuple[int, int]


def _normalize(pairs: Iterable[Pair]) -> Tuple[Pair, ...]:
    ordered = sorted((s, e) for s, e in pairs if s < e)
    merged: List[Pair] = []
    for start, end in ordered:
        if merged and start <= merged[-1][1]:
            if end > merged[-1][1]:
                merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))
    return tuple(merged)


class RangeSet:
    """An immutable set of integers stored as merged half-open ranges."""

    __slots__ = ("_ranges", "_starts")

    def __init__(self, pairs: Iterable[Pair] = ()) -> None:
        self._ranges: Tuple[Pair, ...] = _normalize(pairs)
        self._starts: Optional[List[int]] = None

    @classmethod
    def _of_normalized(cls, ranges: Tuple[Pair, ...]) -> "RangeSet":
        obj = cls.__new__(cls)
        obj._ranges = ranges
        obj._starts = None
        return obj

    # -- inspection ----------------------------------------------------
    @property
    def ranges(self) -> Tuple[Pair, ...]:
        return self._ranges

    def __iter__(self) -> Iterator[Pair]:
        return iter(self._ranges)

    def __len__(self) -> int:
        return len(self._ranges)

    def __bool__(self) -> bool:
        return bool(self._ranges)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, RangeSet) and self._ranges == other._ranges

    def __hash__(self) -> int:
        return hash(self._ranges)

    def __repr__(self) -> str:
        return f"RangeSet({list(self._ranges)!r})"

    def contains(self, t: int) -> bool:
        """True if ``start <= t < end`` for one of the ranges."""
        if self._starts is None:
            self._starts = [s for s, _e in self._ranges]
        k = bisect_right(self._starts, t) - 1
        return k >= 0 and t < self._ranges[k][1]

    __contains__ = contains

    def boundaries(self) -> List[int]:
        """Sorted instants where membership changes (every range start and end)."""
        points: List[int] = []
        for start, end in self._ranges:
            points.append(start)
            points.append(end)
        return points

    def next_boundary(self, t: int) -> Optional[int]:
        """The smallest boundary strictly greater than *t*, or None."""
        best: Optional[int] = None
        for start, end in self._ranges:
            if start > t:
                return start
            if end > t:
                best = end
                break
        return best

    # -- algebra -------------------------------------------------------
    def union(self, other: "RangeSet") -> "RangeSet":
        if not other._ranges:
            return self
        if not self._ranges:
            return other
        return RangeSet(self._ranges + other._ranges)

    def intersect(self, other: "RangeSet") -> "RangeSet":
        a, b = self._ranges, other._ranges
        out: List[Pair] = []
        i = j = 0
        while i < len(a) and j < len(b):
            start = max(a[i][0], b[j][0])
            end = min(a[i][1], b[j][1])
            if start < end:
                out.append((start, end))
            if a[i][1] < b[j][1]:
                i += 1
            else:
                j += 1
        return RangeSet._of_normalized(tuple(out))

    def subtract(self, other: "RangeSet") -> "RangeSet":
        out: List[Pair] = []
        b = other._ranges
        j = 0
        for start, end in self._ranges:
            cursor = start
            while j < len(b) and b[j][1] <= cursor:
                j += 1
            k = j
            while k < len(b) and b[k][0] < end:
                if b[k][0] > cursor:
                    out.append((cursor, b[k][0]))
                cursor = max(cursor, b[k][1])
                if cursor >= end:
                    break
                k += 1
            if cursor < end:
                out.append((cursor, end))
        return RangeSet._of_normalized(tuple(out))

    def clip(self, lo: int, hi: int) -> "RangeSet":
        """Restrict to ``[lo, hi)``."""
        if lo >= hi:
            return RangeSet()
        return self.intersect(RangeSet._of_normalized(((lo, hi),)))

    def complement(self, lo: int, hi: int) -> "RangeSet":
        """The part of ``[lo, hi)`` not in this set."""
        return RangeSet._of_normalized(((lo, hi),) if lo < hi else ()).subtract(self)

    def shift(self, delta: int) -> "RangeSet":
        return RangeSet._of_normalized(tuple((s + delta, e + delta) for s, e in self._ranges))


EMPTY = RangeSet()

__all__ = ["EMPTY", "RangeSet"]
