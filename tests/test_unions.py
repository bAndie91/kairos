"""Several parts in one INTERVAL: relative expressions in unions (SPEC §6.4, §9.2, D19, V17)."""
from __future__ import annotations

import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from helpers import run_cli
from kairoslib.errors import IntervalKeeperError
from kairoslib.evaluate import evaluate, to_epoch
from kairoslib.next_change import finite_end, next_change
from kairoslib.parser import Clause, Combined, RelPlus, RelShift, RelUntil, Union, parse_interval
from kairoslib.reader import read_config
from kairoslib.states import build_lines

BUD = ZoneInfo("Europe/Budapest")


def ep(text: str) -> int:
    return to_epoch(datetime.fromisoformat(text).replace(tzinfo=BUD))


def spans(text: str, lo: str = "2026-01-01 00:00", hi: str = "2027-01-01 00:00"):
    fmt = lambda t: datetime.fromtimestamp(t, BUD).strftime("%Y-%m-%d %H:%M")
    return [(fmt(a), fmt(b)) for a, b in evaluate(parse_interval(text), ep(lo), ep(hi), BUD)]


class Parsing(unittest.TestCase):
    def test_shapes(self) -> None:
        parsed = parse_interval("2 days before Apr 10, 3 days after Oct 1")
        self.assertIsInstance(parsed, Combined)
        self.assertEqual([type(p) for p in parsed.parts], [RelShift, RelShift])
        self.assertEqual([p.sign for p in parsed.parts], [-1, 1])

        parsed = parse_interval("Apr 1, 2 days before Apr 10")
        self.assertEqual([type(p) for p in parsed.parts], [Union, RelShift])

        parsed = parse_interval("Mon + 2 days, Fri, 1 day until Dec 24")
        self.assertEqual([type(p) for p in parsed.parts], [RelPlus, Union, RelUntil])

    def test_a_single_part_is_not_wrapped(self) -> None:
        self.assertIsInstance(parse_interval("Apr 1, Jun 3"), Union)
        self.assertIsInstance(parse_interval("2 days before Apr 10"), RelShift)

    def test_a_comma_before_a_duration_never_continues_a_list(self) -> None:
        parsed = parse_interval("Apr 1, 2 days before Apr 10")
        first = parsed.parts[0]
        self.assertEqual(len(first.terms), 1)
        self.assertIsInstance(first.terms[0], Clause)
        self.assertEqual(first.terms[0].doms, ((1, 1),))  # the day list is `1`, not `1,2`

    def test_a_list_of_numbers_is_still_a_list(self) -> None:
        self.assertEqual(parse_interval("Apr 1,2").terms[0].doms, ((1, 1), (2, 2)))

    def test_the_anchor_of_a_leading_form_takes_the_plain_terms_after_it(self) -> None:
        parsed = parse_interval("2 days before Apr 10, Apr 20")
        self.assertIsInstance(parsed, RelShift)
        self.assertEqual(len(parsed.anchor.terms), 2)

    def test_a_plus_form_ends_at_its_duration(self) -> None:
        parsed = parse_interval("Mon + 2 days, Fri")
        self.assertEqual([type(p) for p in parsed.parts], [RelPlus, Union])

    def test_errors(self) -> None:
        for text in (
            "Apr 1, 2 days",  # a leading duration needs until/before/after
            "Apr 1,",
            "Apr 1, 2 days before Apr 10,",
            "Mon + 2 days,",
            ", 2 days before Apr 10",
            "2 days before Apr 10, 3 days",
            "2 days before Apr 10, + 2 days",
            "Mon + 2 days, 3 days",
        ):
            with self.subTest(text=text), self.assertRaises(IntervalKeeperError):
                parse_interval(text)


class Semantics(unittest.TestCase):
    def test_two_shifts(self) -> None:
        self.assertEqual(
            spans("2 days before Apr 10, 3 days after Oct 1"),
            [("2026-04-08 00:00", "2026-04-09 00:00"), ("2026-10-04 00:00", "2026-10-05 00:00")],
        )

    def test_plain_term_and_shift(self) -> None:
        self.assertEqual(
            spans("Apr 1, 2 days before Apr 10"),
            [("2026-04-01 00:00", "2026-04-02 00:00"), ("2026-04-08 00:00", "2026-04-09 00:00")],
        )

    def test_plus_form_then_plain_term(self) -> None:
        got = spans("Mon + 2 days, Fri", "2026-10-05 00:00", "2026-10-12 00:00")
        self.assertEqual(got, [("2026-10-05 00:00", "2026-10-07 00:00"), ("2026-10-09 00:00", "2026-10-10 00:00")])

    def test_until_and_after_together_and_adjacent_ranges_merge(self) -> None:
        # `4 days until Dec 24` is [Dec 21, Dec 25) and `1 day after Dec 24` is Dec 25: they touch and merge
        self.assertEqual(spans("4 days until Dec 24, 1 day after Dec 24"), [("2026-12-21 00:00", "2026-12-26 00:00")])
        self.assertEqual(
            spans("3 days until Dec 24, 2 days after Dec 24"),
            [("2026-12-22 00:00", "2026-12-25 00:00"), ("2026-12-26 00:00", "2026-12-27 00:00")],
        )

    def test_anchor_union_is_shifted_as_a_whole(self) -> None:
        self.assertEqual(
            spans("2 days before Apr 10, Apr 20"),
            [("2026-04-08 00:00", "2026-04-09 00:00"), ("2026-04-18 00:00", "2026-04-19 00:00")],
        )

    def test_parts_use_their_own_zone(self) -> None:
        got = evaluate(parse_interval("1 hour after 08:00 UTC, 1 hour after 08:00"), ep("2026-10-09 00:00"), ep("2026-10-10 00:00"), BUD)
        starts = sorted(datetime.fromtimestamp(a, BUD).strftime("%H:%M") for a, _ in got)
        self.assertEqual(starts, ["09:00", "11:00"])  # 09:00 UTC is 11:00 Budapest (summer), 09:00 local

    def test_window_independence(self) -> None:
        text = "Apr 1, 2 days before Apr 10, 3 days after Oct 1"
        whole = evaluate(parse_interval(text), ep("2026-01-01 00:00"), ep("2027-01-01 00:00"), BUD)
        pieces = None
        edges = [ep("2026-01-01 00:00"), ep("2026-04-01 12:00"), ep("2026-04-08 06:00"), ep("2026-10-04 12:00"), ep("2027-01-01 00:00")]
        for a, b in zip(edges, edges[1:]):
            part = evaluate(parse_interval(text), a, b, BUD)
            pieces = part if pieces is None else pieces.union(part)
        self.assertEqual(pieces, whole)


class Hierarchy(unittest.TestCase):
    def test_states_and_next_change(self) -> None:
        config = "2 days before 2026-04-10, 3 days after 2026-10-01 = marks\n  08:00-09:00 = ~ morning\n"
        lines = build_lines(read_config(config, "t"), path="t", tz=BUD, now=datetime(2026, 1, 1, tzinfo=BUD), window=None)
        fmt = lambda t: None if t is None else datetime.fromtimestamp(t, BUD).strftime("%Y-%m-%d %H:%M:%S")
        self.assertEqual(fmt(next_change(lines, ep("2026-01-01 00:00"), BUD)), "2026-04-08 00:00:00")
        self.assertEqual(fmt(next_change(lines, ep("2026-04-09 00:00"), BUD)), "2026-10-04 00:00:00")
        self.assertIsNone(next_change(lines, ep("2026-10-05 00:00"), BUD))

    def test_finite_end_sees_every_part(self) -> None:
        both = finite_end([parse_interval("2025-05-01, Mon + 2 days")])
        self.assertEqual(both, finite_end([parse_interval("Mon + 2 days, 2025-05-01")]))
        self.assertGreater(both, ep("2026-01-01 00:00"))
        late = finite_end([parse_interval("2025-05-01, 3 days after 2027-01-01")])
        self.assertGreater(late, ep("2027-01-04 00:00"))


class Cli(unittest.TestCase):
    def test_config_line_with_a_union_of_relative_expressions(self) -> None:
        config = "2 days before Apr 10, 3 days after Oct 1 = marks\n"
        code, out, err = run_cli(["--config", "-", "--tz", "Europe/Budapest", "--at", "2026-04-08 12:00"], config)
        self.assertEqual((code, out.strip()), (0, "marks"), err)
        code, out, _ = run_cli(["--config", "-", "--tz", "Europe/Budapest", "--at", "2026-04-09 00:00"], config)
        self.assertEqual((code, out.strip()), (0, ""))
        code, out, _ = run_cli(["--config", "-", "--tz", "Europe/Budapest", "--at", "2026-10-04 12:00"], config)
        self.assertEqual(out.strip(), "marks")

    def test_trailing_comma_is_a_located_error(self) -> None:
        code, out, err = run_cli(["--config", "-", "--check"], "Mon = a\nApr 1, 2 days before Apr 10, = b\n")
        self.assertEqual((code, out), (2, ""))
        self.assertIn(":2:", err)


if __name__ == "__main__":
    unittest.main()
