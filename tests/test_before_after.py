"""`D before ANCHOR` / `D after ANCHOR` (SPEC §9.1, D16, V16, PLAN M11)."""
from __future__ import annotations

import unittest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from helpers import run_cli
from kairoslib.errors import IntervalKeeperError
from kairoslib.evaluate import evaluate, to_epoch
from kairoslib.lexer import is_reserved_word
from kairoslib.macros import validate_macro_name
from kairoslib.next_change import finite_end, next_change
from kairoslib.parser import Clause, Duration, RelShift, Union, parse_interval
from kairoslib.reader import read_config
from kairoslib.states import build_lines

BUD = ZoneInfo("Europe/Budapest")
UTC = timezone.utc


def ep(text: str, zone=BUD) -> int:
    return to_epoch(datetime.fromisoformat(text).replace(tzinfo=zone))


def spans(text: str, lo: str = "2026-01-01 00:00", hi: str = "2027-01-01 00:00", zone=BUD):
    fmt = lambda t: datetime.fromtimestamp(t, zone).strftime("%Y-%m-%d %H:%M")
    return [(fmt(a), fmt(b)) for a, b in evaluate(parse_interval(text), ep(lo, zone), ep(hi, zone), zone)]


class Parsing(unittest.TestCase):
    def test_ast(self) -> None:
        parsed = parse_interval("40 days before Dec 24")
        self.assertIsInstance(parsed, RelShift)
        self.assertEqual((parsed.sign, parsed.duration), (-1, Duration(((40, "day"),))))
        self.assertEqual(parse_interval("10 days after Oct 1").sign, 1)
        self.assertEqual(parse_interval("1 year 2 months before Dec 24").duration, Duration(((1, "year"), (2, "month"))))
        self.assertIsInstance(parse_interval("2 days before Apr 10 12:00").anchor, Union)

    def test_keywords_are_reserved_and_case_insensitive(self) -> None:
        for word in ("before", "after", "BEFORE", "After"):
            self.assertTrue(is_reserved_word(word), word)
            with self.assertRaises(IntervalKeeperError):
                validate_macro_name(word)
        self.assertEqual(parse_interval("2 Days BEFORE Dec 24").sign, -1)

    def test_errors(self) -> None:
        for text in (
            "5 days before", "5 days after", "before Dec 24", "after Dec 24", "Mon before Dec 24", "Mon after Dec 24",
            "5 days before Dec 24 + 2 days", "5 days before 5 days after Dec 24", "5 days before until Mon",
            "5 before Dec 24", "5 days Dec 24", "Mon + 5 days before Dec 24",
        ):
            with self.subTest(text=text), self.assertRaises(IntervalKeeperError):
                parse_interval(text)

    def test_stray_keyword_message(self) -> None:
        with self.assertRaises(IntervalKeeperError) as ctx:
            parse_interval("before Dec 24")
        self.assertIn("follow a duration", ctx.exception.message)

    def test_zone_on_the_anchor(self) -> None:
        shifted = parse_interval("1 day before Dec 24 Europe/Berlin")
        self.assertEqual(shifted.anchor.terms[0].tz, "Europe/Berlin")


class V16(unittest.TestCase):
    def test_40_days_before_dec_24(self) -> None:
        self.assertEqual(spans("40 days before Dec 24"), [("2026-11-14 00:00", "2026-11-15 00:00")])

    def test_10_days_after_oct_1(self) -> None:
        self.assertEqual(spans("10 days after Oct 1"), [("2026-10-11 00:00", "2026-10-12 00:00")])

    def test_the_time_of_day_is_kept(self) -> None:
        self.assertEqual(spans("2 days before Apr 10 12:00"), [("2026-04-08 12:00", "2026-04-08 12:01")])
        self.assertEqual(spans("2 days before Apr 10 12:00"), spans("Apr 8 12:00"))

    def test_hours_after_a_bare_time(self) -> None:
        got = spans("3 hours after 08:00", "2026-03-01 00:00", "2026-03-03 00:00")
        self.assertEqual(got, [("2026-03-01 11:00", "2026-03-01 11:01"), ("2026-03-02 11:00", "2026-03-02 11:01")])

    def test_month_arithmetic_clamps(self) -> None:
        self.assertEqual(spans("1 month before Mar 31"), [("2026-02-28 00:00", "2026-03-01 00:00")])
        self.assertEqual(spans("1 month after Jan 31", "2026-01-01 00:00", "2026-04-01 00:00"), [("2026-02-28 00:00", "2026-03-01 00:00")])

    def test_span_is_moved_as_a_whole(self) -> None:
        got = spans("1 year before Dec 20 -- Jan 10", "2025-06-01 00:00", "2027-06-01 00:00")
        self.assertEqual(got, [("2025-12-20 00:00", "2026-01-11 00:00"), ("2026-12-20 00:00", "2027-01-11 00:00")])

    def test_year_arithmetic_on_feb_29(self) -> None:
        # Feb 29 only exists in leap years; one year after is the clamped Feb 28 of the next year
        got = spans("1 year after Feb 29", "2028-01-01 00:00", "2030-01-01 00:00")
        self.assertEqual(got, [("2029-02-28 00:00", "2029-03-01 00:00")])

    def test_zero_duration_is_the_anchor(self) -> None:
        self.assertEqual(spans("0 days before Dec 24"), spans("Dec 24"))
        self.assertEqual(spans("0 days after Dec 24"), spans("Dec 24"))

    def test_wall_clock_across_dst(self) -> None:
        # a day-long anchor stays one calendar day long when shifted over the spring change
        self.assertEqual(spans("1 day before Mar 30", "2026-03-01 00:00", "2026-04-01 00:00"), [("2026-03-29 00:00", "2026-03-30 00:00")])
        rs = evaluate(parse_interval("1 day before Mar 30"), ep("2026-03-01 00:00"), ep("2026-04-01 00:00"), BUD)
        (start, end), = rs.ranges
        self.assertEqual(end - start, 23 * 3600)  # the 29th has only 23 hours

    def test_instances_are_maximal_contiguous_ranges(self) -> None:
        self.assertEqual(spans("1 day after Dec 24,25"), [("2026-12-25 00:00", "2026-12-27 00:00")])

    def test_anchor_far_from_the_window(self) -> None:
        # the anchor instance lies long after / before the evaluation window
        self.assertEqual(spans("11 months before 2030-05-01", "2029-05-30 00:00", "2029-06-02 00:00"), [("2029-06-01 00:00", "2029-06-02 00:00")])
        self.assertEqual(spans("11 months after 2020-05-01", "2021-03-30 00:00", "2021-04-02 00:00"), [("2021-04-01 00:00", "2021-04-02 00:00")])


def lines_for(config: str, zone=BUD):
    return build_lines(read_config(config, "t"), path="t", tz=zone, now=datetime(2026, 10, 9, 12, tzinfo=zone), window=None)


class NextChangeAndStates(unittest.TestCase):
    def test_next_change_vectors(self) -> None:
        lines = lines_for("40 days before Dec 24 = early\n")
        fmt = lambda t: None if t is None else datetime.fromtimestamp(t, BUD).strftime("%Y-%m-%d %H:%M:%S")
        self.assertEqual(fmt(next_change(lines, ep("2026-10-09 12:00"), BUD)), "2026-11-14 00:00:00")
        self.assertEqual(fmt(next_change(lines, ep("2026-11-14 12:00"), BUD)), "2026-11-15 00:00:00")
        self.assertEqual(fmt(next_change(lines, ep("2026-11-15 00:00"), BUD)), "2027-11-14 00:00:00")

    def test_finite_anchor_with_before_has_no_future_change(self) -> None:
        lines = lines_for("2 days before 2026-04-10 = x\n")
        self.assertEqual(next_change(lines, ep("2026-04-08 00:00"), BUD), ep("2026-04-09 00:00"))
        self.assertIsNone(next_change(lines, ep("2026-04-09 00:00"), BUD))
        self.assertGreater(finite_end([line.expr for line in lines]), ep("2026-12-31 00:00"))

    def test_narrowing_by_children(self) -> None:
        config = "2 days before Apr 10\n  08:00-09:00 = x\n"
        for at, expected in (("2026-04-08 08:30", "x\n"), ("2026-04-08 09:30", ""), ("2026-04-09 08:30", ""), ("2026-04-10 08:30", "")):
            with self.subTest(at=at):
                code, out, err = run_cli(["--config", "-", "--tz", "Europe/Budapest", "--at", at], config_text=config)
                self.assertEqual((code, out, err), (0, expected, ""))

    def test_two_lines_with_the_same_state_are_a_union(self) -> None:
        config = "2 days before Apr 10 = x\n3 days after Apr 10 = x\n"
        for at, expected in (("2026-04-08 12:00", "x\n"), ("2026-04-09 12:00", ""), ("2026-04-13 12:00", "x\n")):
            with self.subTest(at=at):
                code, out, _ = run_cli(["--config", "-", "--tz", "Europe/Budapest", "--at", at], config_text=config)
                self.assertEqual((code, out), (0, expected))

    def test_state_on_the_line_and_negation(self) -> None:
        config = "! 2 days before Apr 10 = not dinner day\n"
        for at, expected in (("2026-04-08 12:00", ""), ("2026-04-09 12:00", "not dinner day\n")):
            with self.subTest(at=at):
                code, out, _ = run_cli(["--config", "-", "--tz", "Europe/Budapest", "--at", at], config_text=config)
                self.assertEqual((code, out), (0, expected))

    def test_macros_expand_inside_before_after(self) -> None:
        config = "Xmas := Dec 24\n40 days before Xmas = early\n"
        code, out, err = run_cli(["--config", "-", "--tz", "Europe/Budapest", "--at", "2026-11-14 12:00"], config_text=config)
        self.assertEqual((code, out, err), (0, "early\n", ""))


if __name__ == "__main__":
    unittest.main()
