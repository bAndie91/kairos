"""Property tests for RangeSet against a naive set-of-integers model."""
from __future__ import annotations

import random
import unittest

from kairoslib.ranges import RangeSet

DOMAIN = range(-5, 45)


def naive(pairs):
    return {t for s, e in pairs for t in range(s, e)}


def to_naive(rs: RangeSet):
    return {t for t in DOMAIN if rs.contains(t)}


def random_pairs(rng: random.Random):
    pairs = []
    for _ in range(rng.randint(0, 6)):
        a = rng.randint(-3, 42)
        pairs.append((a, a + rng.randint(-1, 9)))  # includes empty/inverted pairs
    return pairs


class RangeSetBasics(unittest.TestCase):
    def test_normalisation_merges_adjacent_and_overlapping(self) -> None:
        self.assertEqual(RangeSet([(5, 8), (1, 3), (3, 5), (7, 9), (4, 4), (9, 8)]).ranges, ((1, 9),))
        self.assertEqual(RangeSet([(1, 2), (3, 4)]).ranges, ((1, 2), (3, 4)))
        self.assertFalse(RangeSet())

    def test_half_open_membership(self) -> None:
        rs = RangeSet([(10, 20)])
        self.assertTrue(rs.contains(10))
        self.assertTrue(rs.contains(19))
        self.assertFalse(rs.contains(20))
        self.assertFalse(rs.contains(9))
        self.assertIn(15, rs)

    def test_boundaries_and_next_boundary(self) -> None:
        rs = RangeSet([(1, 3), (5, 8)])
        self.assertEqual(rs.boundaries(), [1, 3, 5, 8])
        self.assertEqual([rs.next_boundary(t) for t in (0, 1, 2, 3, 4, 5, 7, 8)], [1, 3, 3, 5, 5, 8, 8, None])
        self.assertIsNone(RangeSet().next_boundary(0))

    def test_adjacent_ranges_have_no_internal_boundary(self) -> None:
        self.assertEqual(RangeSet([(0, 5), (5, 9)]).boundaries(), [0, 9])

    def test_clip_complement_shift(self) -> None:
        rs = RangeSet([(1, 4), (6, 10)])
        self.assertEqual(rs.clip(3, 7).ranges, ((3, 4), (6, 7)))
        self.assertEqual(rs.clip(7, 3).ranges, ())
        self.assertEqual(rs.complement(0, 12).ranges, ((0, 1), (4, 6), (10, 12)))
        self.assertEqual(rs.shift(10).ranges, ((11, 14), (16, 20)))


class RangeSetProperties(unittest.TestCase):
    def test_algebra_matches_naive_model(self) -> None:
        rng = random.Random(20261010)
        for _ in range(600):
            pa, pb = random_pairs(rng), random_pairs(rng)
            a, b = RangeSet(pa), RangeSet(pb)
            na, nb = naive(pa), naive(pb)
            self.assertEqual(to_naive(a), na & set(DOMAIN))
            self.assertEqual(to_naive(a.union(b)), (na | nb) & set(DOMAIN))
            self.assertEqual(to_naive(a.intersect(b)), (na & nb) & set(DOMAIN))
            self.assertEqual(to_naive(a.subtract(b)), (na - nb) & set(DOMAIN))
            lo, hi = sorted((rng.randint(-5, 45), rng.randint(-5, 45)))
            self.assertEqual(to_naive(a.clip(lo, hi)), {t for t in na if lo <= t < hi} & set(DOMAIN))
            self.assertEqual(to_naive(a.complement(lo, hi)), {t for t in range(lo, hi) if t not in na} & set(DOMAIN))

    def test_results_are_normalised(self) -> None:
        rng = random.Random(7)
        for _ in range(300):
            a, b = RangeSet(random_pairs(rng)), RangeSet(random_pairs(rng))
            for result in (a.union(b), a.intersect(b), a.subtract(b)):
                ranges = result.ranges
                self.assertEqual(ranges, RangeSet(ranges).ranges)
                for (s1, e1), (s2, _e2) in zip(ranges, ranges[1:]):
                    self.assertLess(e1, s2)  # sorted, disjoint and not adjacent
                self.assertTrue(all(s < e for s, e in ranges))

    def test_next_boundary_matches_naive(self) -> None:
        rng = random.Random(11)
        for _ in range(300):
            rs = RangeSet(random_pairs(rng))
            members = [rs.contains(t) for t in range(-6, 60)]
            for t in range(-5, 50):
                expected = next((u for u in range(t + 1, 59) if members[u + 6] != members[u + 5]), None)
                self.assertEqual(rs.next_boundary(t), expected, (rs, t))


if __name__ == "__main__":
    unittest.main()
