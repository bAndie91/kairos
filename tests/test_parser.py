"""Tests for INTERVAL lexing and parsing (SPEC §6, §9)."""
from __future__ import annotations

import unittest

from kairoslib.errors import IntervalKeeperError
from kairoslib.lexer import RESERVED_WORDS, is_tz_token, tokenize
from kairoslib.parser import (
    Clause, DateAtom, DateSide, Duration, RelPlus, RelUntil, Span, TimeSpec, Union, parse_interval,
)

H = 3600


def clause(**kw) -> Clause:
    return Clause(**kw)


def one(**kw) -> Union:
    return Union((Clause(**kw),))


def kinds(text: str):
    return [(t.kind, t.text) for t in tokenize(text)]


class LexerTests(unittest.TestCase):
    def test_token_kinds(self) -> None:
        self.assertEqual(
            kinds("Mon-Fri 08:00-12:00,13:00:30"),
            [("WORD", "Mon"), ("DASH", "-"), ("WORD", "Fri"), ("TIME", "08:00"), ("DASH", "-"),
             ("TIME", "12:00"), ("COMMA", ","), ("TIME", "13:00:30")],
        )
        self.assertEqual(kinds("2026-04-01 -- 20"), [("ISODATE", "2026-04-01"), ("DASHDASH", "--"), ("NUMBER", "20")])
        self.assertEqual(kinds("*-*-31"), [("ISODATE", "*-*-31")])
        self.assertEqual(kinds("2026-2028"), [("NUMBER", "2026"), ("DASH", "-"), ("NUMBER", "2028")])

    def test_zone_tokens(self) -> None:
        for text in ("Europe/Berlin", "europe/berlin", "UTC+0300", "GMT-4:30", "utc", "Z", "CET", "Etc/GMT+3"):
            with self.subTest(text=text):
                self.assertEqual(kinds(text)[0][0], "TZ")
        self.assertEqual(kinds("08:00 UTC + 2 hours")[1:], [("TZ", "UTC"), ("PLUS", "+"), ("NUMBER", "2"), ("WORD", "hours")])

    def test_unknown_words_and_abbreviations_error(self) -> None:
        for text, needle in (("Foo", "'Foo'"), ("CEST", "IANA zone ID"), ("Mon Foo/Bar", "Foo/Bar"), ("UTC+25", "UTC+25"), ("Mon $", "'$'")):
            with self.subTest(text=text), self.assertRaises(IntervalKeeperError) as ctx:
                tokenize(text)
            self.assertIn(needle, ctx.exception.message)

    def test_shared_vocabulary(self) -> None:
        for word in ("mon", "sept", "dec", "days", "until", "utc", "gmt", "z", "sunday"):
            self.assertIn(word, RESERVED_WORDS)
        self.assertTrue(is_tz_token("Europe/Budapest"))
        self.assertFalse(is_tz_token("CST"))


class ClauseTests(unittest.TestCase):
    def test_simple_clauses(self) -> None:
        cases = {
            "08:00-16:00": one(times=(TimeSpec(8 * H, 16 * H),)),
            "23:00-04:00": one(times=(TimeSpec(23 * H, 4 * H),)),
            "Dec-Feb": one(months=((12, 2),)),
            "Mon-Fri": one(weekdays=((0, 4),)),
            "Mon - Fri": one(weekdays=((0, 4),)),
            "Jun,Jul,Aug": one(months=((6, 6), (7, 7), (8, 8))),
            "Sept": one(months=((9, 9),)),
            "*-*-01": one(dates=(DateAtom(None, None, 1),)),
            "*-12-*": one(dates=(DateAtom(None, 12, None),)),
            "2026-12-24,2026-12-25": one(dates=(DateAtom(2026, 12, 24), DateAtom(2026, 12, 25))),
            "2026-2028": one(years=((2026, 2028),)),
            "28-3": one(doms=((28, 3),)),
            "Feb 29": one(months=((2, 2),), doms=((29, 29),)),
            "*-*-31": one(dates=(DateAtom(None, None, 31),)),
            "01:00-24:00": one(times=(TimeSpec(H, 24 * H),)),
            "08:00": one(times=(TimeSpec(8 * H, None),)),
            "08:00:30": one(times=(TimeSpec(8 * H + 30, None, True),)),
            "Fri 22:00-02:00": one(weekdays=((4, 4),), times=(TimeSpec(22 * H, 2 * H),)),
            "mon TUE": None,
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                if expected is None:
                    with self.assertRaises(IntervalKeeperError):
                        parse_interval(text)
                else:
                    self.assertEqual(parse_interval(text), expected)

    def test_clause_is_a_conjunction(self) -> None:
        self.assertEqual(
            parse_interval("Apr-Jun 1-15"),
            one(months=((4, 6),), doms=((1, 15),)),
        )

    def test_zone_ends_clause(self) -> None:
        self.assertEqual(
            parse_interval("*-12-* 08:00-09:00 Europe/Berlin"),
            one(dates=(DateAtom(None, 12, None),), times=(TimeSpec(8 * H, 9 * H),), tz="Europe/Berlin"),
        )
        self.assertEqual(parse_interval("08:00-09:00 UTC+0300").terms[0].tz, "UTC+0300")
        self.assertEqual(parse_interval("Mon CET").terms[0].tz, "CET")


class HourMinuteTests(unittest.TestCase):
    """`8h` is `8:*` (whole hour 8), `30m`/`30min` is `*:30` (minute 30 of every hour)."""

    def test_hour_and_minute_items(self) -> None:
        cases = {
            "8h": one(hours=((8, 8),)),
            "8h-12h": one(hours=((8, 12),)),
            "22h-2h": one(hours=((22, 2),)),
            "8h,9h,13h": one(hours=((8, 8), (9, 9), (13, 13))),
            "30m": one(minutes=((30, 30),)),
            "30min": one(minutes=((30, 30),)),
            "50m-10m": one(minutes=((50, 10),)),
            "Mon 8h 30m": one(weekdays=((0, 0),), hours=((8, 8),), minutes=((30, 30),)),
            "8h 12:00-13:00": one(hours=((8, 8),), times=(TimeSpec(12 * H, 13 * H),)),
            "0h": one(hours=((0, 0),)),
            "59min": one(minutes=((59, 59),)),
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(parse_interval(text), expected)

    def test_hour_minute_comma_rule(self) -> None:
        # same-kind continuation: hours stay a list, a minute starts a new term
        self.assertEqual(parse_interval("8h,30m"), Union((clause(hours=((8, 8),)), clause(minutes=((30, 30),)))))

    def test_relative_and_zone_with_hours(self) -> None:
        self.assertEqual(
            parse_interval("8h + 30 minutes"),
            RelPlus(one(hours=((8, 8),)), Duration(((30, "minute"),))),
        )
        self.assertEqual(parse_interval("8h Europe/Berlin").terms[0].tz, "Europe/Berlin")

    def test_point_time_with_seconds(self) -> None:
        # `8:00:30` lasts one whole second; `08:00` lasts one minute (evaluate.py).
        self.assertEqual(parse_interval("8:00:30"), one(times=(TimeSpec(8 * H + 30, None, True),)))
        self.assertEqual(parse_interval("08:00"), one(times=(TimeSpec(8 * H, None, False),)))


class ZoneOffsetVersusDurationTests(unittest.TestCase):
    def test_spaced_plus_is_a_duration(self) -> None:
        parsed = parse_interval("08:00 UTC + 2 hours")
        self.assertIsInstance(parsed, RelPlus)
        self.assertEqual(parsed.anchor.terms[0].tz, "UTC")
        self.assertEqual(parsed.duration, Duration(((2, "hour"),)))

    def test_attached_offset_with_unit_word_is_incomplete(self) -> None:
        for text in ("UTC+2 hours", "08:00 UTC+2 hours", "08:00 GMT-3 days"):
            with self.subTest(text=text), self.assertRaises(IntervalKeeperError) as ctx:
                parse_interval(text)
            self.assertIn("needs a number", ctx.exception.message)
            self.assertIn("UTC + 2 hours", ctx.exception.message)

    def test_bare_unit_word_is_incomplete(self) -> None:
        with self.assertRaises(IntervalKeeperError) as ctx:
            parse_interval("Mon hours")
        self.assertIn("needs a number", ctx.exception.message)


class CommaTests(unittest.TestCase):
    """D3: a comma continues a list only for the same kind as the item before it."""

    def test_comma_rules(self) -> None:
        self.assertEqual(parse_interval("Apr,Jun 1,15"), one(months=((4, 4), (6, 6)), doms=((1, 1), (15, 15))))
        self.assertEqual(
            parse_interval("Apr 1, Jun 15"),
            Union((clause(months=((4, 4),), doms=((1, 1),)), clause(months=((6, 6),), doms=((15, 15),)))),
        )
        self.assertEqual(
            parse_interval("Mon-Fri 08:00-12:00,13:00-17:00"),
            one(weekdays=((0, 4),), times=(TimeSpec(8 * H, 12 * H), TimeSpec(13 * H, 17 * H))),
        )
        self.assertEqual(
            parse_interval("Mon 08:00-09:00, Tue 10:00-11:00"),
            Union((
                clause(weekdays=((0, 0),), times=(TimeSpec(8 * H, 9 * H),)),
                clause(weekdays=((1, 1),), times=(TimeSpec(10 * H, 11 * H),)),
            )),
        )
        self.assertEqual(parse_interval("Mon-Wed,Fri"), one(weekdays=((0, 2), (4, 4))))

    def test_zone_before_comma_belongs_to_its_clause(self) -> None:
        union = parse_interval("Mon 08:00 CET, Tue 09:00")
        self.assertEqual([t.tz for t in union.terms], ["CET", None])


class SpanTests(unittest.TestCase):
    def test_span_forms(self) -> None:
        self.assertEqual(
            parse_interval("Apr 1 -- Jun 15"),
            Union((Span(DateSide(None, 4, 1), DateSide(None, 6, 15)),)),
        )
        self.assertEqual(
            parse_interval("Dec 20 -- Jan 10"),
            Union((Span(DateSide(None, 12, 20), DateSide(None, 1, 10), 1),)),
        )
        self.assertEqual(
            parse_interval("2026 Dec 20 -- Jan 10"),
            Union((Span(DateSide(2026, 12, 20), DateSide(None, 1, 10), 1),)),
        )
        self.assertEqual(
            parse_interval("Apr 25 -- 3"),
            Union((Span(DateSide(None, 4, 25), DateSide(None, 5, 3)),)),
        )
        self.assertEqual(
            parse_interval("Dec 25 -- 3"),
            Union((Span(DateSide(None, 12, 25), DateSide(None, 1, 3), 1),)),
        )

    def test_equivalent_spellings(self) -> None:
        expected = Union((Span(DateSide(2026, 4, 1), DateSide(None, 4, 20)),))
        self.assertEqual(parse_interval("2026 Apr 1 -- 20"), expected)
        self.assertEqual(parse_interval("2026-04-01 -- 20"), expected)

    def test_span_times_and_zone(self) -> None:
        self.assertEqual(
            parse_interval("Apr 1 08:00 -- Apr 3 17:00 Europe/Berlin"),
            Union((Span(DateSide(None, 4, 1, 8 * H), DateSide(None, 4, 3, 17 * H), 0, "Europe/Berlin"),)),
        )

    def test_recurring_feb_29_endpoint_is_allowed(self) -> None:
        parse_interval("Feb 29 -- Mar 2")
        with self.assertRaises(IntervalKeeperError):
            parse_interval("2026 Feb 29 -- Mar 2")

    def test_span_in_union(self) -> None:
        union = parse_interval("Apr 1 -- 5, Dec 1 -- 3")
        self.assertEqual(len(union.terms), 2)
        self.assertTrue(all(isinstance(t, Span) for t in union.terms))

    def test_span_errors(self) -> None:
        for text in (
            "Mon -- Fri",
            "Apr 1,2 -- 5",
            "Apr 1-3 -- 5",
            "Apr 1 08:00 -- Apr 5",
            "2026 Apr 5 -- 2026 Apr 1",
            "2026 Apr 1 -- 2025 Mar 3",
            "Apr 1 -- 2027 Apr 5",
            "Apr 1 10:00 -- Apr 1 08:00",
            "Apr 1 --",
            "-- Apr 1",
            "20 -- Apr 5",
            "Apr 1 -- Jun 15 --",
            "Apr 1 -- Jun 31",
        ):
            with self.subTest(text=text), self.assertRaises(IntervalKeeperError):
                parse_interval(text)


class RelativeTests(unittest.TestCase):
    def test_plus(self) -> None:
        self.assertEqual(
            parse_interval("1-7 Mon + 5 day"),
            RelPlus(one(doms=((1, 7),), weekdays=((0, 0),)), Duration(((5, "day"),))),
        )
        self.assertEqual(
            parse_interval("08:00 + 2 hours"),
            RelPlus(one(times=(TimeSpec(8 * H, None),)), Duration(((2, "hour"),))),
        )
        self.assertEqual(
            parse_interval("Mon+1 week 2 days"),
            RelPlus(one(weekdays=((0, 0),)), Duration(((1, "week"), (2, "day")))),
        )

    def test_until(self) -> None:
        self.assertEqual(
            parse_interval("40 days until Dec 24"),
            RelUntil(Duration(((40, "day"),)), one(months=((12, 12),), doms=((24, 24),))),
        )
        self.assertEqual(
            parse_interval("4 days 9 hours until Dec 24").duration,
            Duration(((4, "day"), (9, "hour"))),
        )

    def test_relative_errors(self) -> None:
        for text in ("5 days", "Mon + 5", "Mon +", "40 days until", "Mon until Dec 24", "Mon + 5 day + 1 day", "Mon + 5 day Tue"):
            with self.subTest(text=text), self.assertRaises(IntervalKeeperError):
                parse_interval(text)


class ErrorTests(unittest.TestCase):
    def test_v12_interval_errors(self) -> None:
        for text in (
            "08:00-25:00", "Mon Tue", "Foo", "Feb 30", "2026-02-29", "08:00-08:00", "Mon Foo/Bar",
        ):
            with self.subTest(text=text), self.assertRaises(IntervalKeeperError):
                parse_interval(text)

    def test_more_syntax_errors(self) -> None:
        for text in (
            "", "   ", "*", "Mon *", "Mon,", ",Mon", "0", "32", "99", "10000", "Mon-Jun", "2028-2026", "100-99",
            "UTC", "Mon UTC Tue", "08:00,09:00-10:00", "24:00", "24:00-02:00", "25:00", "08:60", "08:00:60",
            "*-04-31", "Apr,Jun 31", "2026-2028 2030", "2026-12-24 Dec", "2026-12-24-2026-12-25", "24h", "60m", "8h 9h", "Apr 1 8h -- 5",
            "CST 08:00", "Mon - ", "- Mon", "Mon--Fri",
        ):
            with self.subTest(text=text), self.assertRaises(IntervalKeeperError):
                parse_interval(text)

    def test_day_month_existence_is_left_to_datetime(self) -> None:
        parse_interval("Apr-Jun 31")  # May has a 31st
        parse_interval("Apr-Jun 30")
        parse_interval("Feb,Mar 31")
        with self.assertRaises(IntervalKeeperError):
            parse_interval("Feb 30")

    def test_errors_carry_path_and_line(self) -> None:
        with self.assertRaises(IntervalKeeperError) as ctx:
            parse_interval("Mon Tue", path="conf", lineno=7)
        self.assertEqual((ctx.exception.path, ctx.exception.line), ("conf", 7))
        self.assertEqual(ctx.exception.diagnostic().split(": error: ")[0], "kairos: conf:7")
        with self.assertRaises(IntervalKeeperError) as ctx:
            parse_interval("Foo", path="conf", lineno=3)
        self.assertEqual(ctx.exception.line, 3)

    def test_error_messages_name_the_problem(self) -> None:
        cases = {
            "Foo": "unknown word 'Foo'",
            "Mon Tue": "duplicate WEEKDAY",
            "08:00-08:00": "equal ends",
            "Mon-Jun": "mixed-kind range",
            "*": "'*'",
            "Mon,": "trailing ','",
        }
        for text, needle in cases.items():
            with self.subTest(text=text), self.assertRaises(IntervalKeeperError) as ctx:
                parse_interval(text)
            self.assertIn(needle, ctx.exception.message)

    def test_spec_example_intervals_parse(self) -> None:
        for text in (
            "08:00-16:00", "12:00-13:00", "Jun,Jul,Aug", "Sun", "20:00-23:00", "*-*-01", "Sun,Sat", "1-7 Mon + 5 day",
            "40 days until Dec 24", "Apr 1 -- Jun 15", "Dec 20 -- Jan 10", "2026 Apr 1 -- 20",
            "*-07-* 08:00-09:00 Europe/Berlin", "08:00-09:00 UTC+0300", "Mon-Fri 08:00-12:00,13:00-17:00",
        ):
            with self.subTest(text=text):
                parse_interval(text)


if __name__ == "__main__":
    unittest.main()
