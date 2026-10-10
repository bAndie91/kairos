"""Evaluation tests: single-line intervals (SPEC §7.1, §9, V1-V3, V7-V9, V14)."""
from __future__ import annotations

import random
import unittest
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from kairoslib.evaluate import evaluate, to_epoch
from kairoslib.parser import parse_interval

BUD = ZoneInfo("Europe/Budapest")
UTC = timezone.utc


def ep(text: str, zone=UTC) -> int:
    return to_epoch(datetime.fromisoformat(text).replace(tzinfo=zone))


def active(text: str, at: str, zone=BUD, instant_zone=None) -> bool:
    t = ep(at, instant_zone or zone)
    return bool(evaluate(parse_interval(text), t, t + 1, zone))


def utc(rs):
    """RangeSet -> list of (start, end) ISO strings in UTC for readable assertions."""
    fmt = lambda t: datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%d %H:%M:%S")
    return [(fmt(s), fmt(e)) for s, e in rs]


def run(text: str, lo: str, hi: str, zone=BUD):
    return evaluate(parse_interval(text), ep(lo, UTC), ep(hi, UTC), zone)


class CalendarFacts(unittest.TestCase):
    def test_reference_calendar(self) -> None:
        self.assertEqual(date(2026, 10, 9).weekday(), 4)
        self.assertEqual(date(2026, 10, 1).weekday(), 3)
        self.assertEqual(date(2026, 11, 1).weekday(), 6)
        self.assertEqual(date(2026, 12, 1).weekday(), 1)
        self.assertEqual(date(2026, 7, 5).weekday(), 6)


class V1V2V3(unittest.TestCase):
    def test_v1_work_hours(self) -> None:
        self.assertFalse(active("08:00-16:00", "2026-10-09T07:59:59"))
        self.assertTrue(active("08:00-16:00", "2026-10-09T08:00:00"))
        self.assertTrue(active("08:00-16:00", "2026-10-09T15:59:59"))
        self.assertFalse(active("08:00-16:00", "2026-10-09T16:00:00"))
        self.assertTrue(active("12:00-13:00", "2026-10-09T12:00:00"))
        self.assertFalse(active("12:00-13:00", "2026-10-09T13:00:00"))

    def test_v2_rollover(self) -> None:
        self.assertTrue(active("23:00-04:00", "2026-10-10T02:00:00"))
        self.assertFalse(active("23:00-04:00", "2026-10-09T22:59:59"))
        self.assertTrue(active("23:00-04:00", "2026-10-09T23:00:00"))
        self.assertFalse(active("23:00-04:00", "2026-10-10T04:00:00"))

    def test_v3_winter(self) -> None:
        self.assertTrue(active("Dec-Feb", "2027-01-15T12:00:00"))
        self.assertFalse(active("Dec-Feb", "2026-10-09T12:00:00"))
        self.assertTrue(active("Dec-Feb", "2026-12-01T00:00:00"))
        self.assertFalse(active("Dec-Feb", "2026-11-30T23:59:59"))
        self.assertFalse(active("Dec-Feb", "2027-03-01T00:00:00"))
        self.assertTrue(active("Dec-Feb", "2027-02-28T23:59:59"))

    def test_d2_start_day_selects_rollover(self) -> None:
        # Fri 22:00-02:00 spills into Saturday; Saturday 01:00 is covered, Friday 01:00 is not.
        self.assertTrue(active("Fri 22:00-02:00", "2026-10-10T01:00:00"))
        self.assertFalse(active("Fri 22:00-02:00", "2026-10-09T01:00:00"))
        self.assertTrue(active("Fri 22:00-02:00", "2026-10-09T23:30:00"))

    def test_day_level_items(self) -> None:
        self.assertTrue(active("*-*-01", "2026-10-01T12:00:00"))
        self.assertFalse(active("*-*-01", "2026-10-02T12:00:00"))
        self.assertTrue(active("Apr-Jun 1-15", "2026-05-10T00:00:00"))
        self.assertFalse(active("Apr-Jun 1-15", "2026-05-16T00:00:00"))
        self.assertTrue(active("28-3", "2026-11-02T10:00:00"))
        self.assertTrue(active("28-3", "2026-11-29T10:00:00"))
        self.assertFalse(active("28-3", "2026-11-15T10:00:00"))
        self.assertTrue(active("2026-2028", "2027-06-01T00:00:00"))
        self.assertFalse(active("2026-2028", "2029-01-01T00:00:00"))
        self.assertTrue(active("Feb 29", "2028-02-29T12:00:00"))
        self.assertFalse(active("Feb 29", "2027-02-28T12:00:00"))
        self.assertTrue(active("Fri-Mon", "2026-10-11T12:00:00"))  # Sunday
        self.assertFalse(active("Fri-Mon", "2026-10-14T12:00:00"))  # Wednesday

    def test_commas_union_terms(self) -> None:
        text = "Mon 08:00-09:00, Tue 10:00-11:00"
        self.assertTrue(active(text, "2026-10-12T08:30:00"))
        self.assertTrue(active(text, "2026-10-13T10:30:00"))
        self.assertFalse(active(text, "2026-10-12T10:30:00"))


class BareTimeAndHourMinute(unittest.TestCase):
    def test_bare_time_is_one_minute(self) -> None:
        self.assertTrue(active("08:00", "2026-10-09T08:00:00"))
        self.assertTrue(active("08:00", "2026-10-09T08:00:59"))
        self.assertFalse(active("08:00", "2026-10-09T08:01:00"))
        self.assertFalse(active("08:00", "2026-10-09T07:59:59"))

    def test_point_time_with_seconds_is_one_second(self) -> None:
        self.assertFalse(active("08:00:30", "2026-10-09T08:00:29"))
        self.assertTrue(active("08:00:30", "2026-10-09T08:00:30"))
        self.assertFalse(active("08:00:30", "2026-10-09T08:00:31"))

    def test_whole_hour_8h(self) -> None:
        self.assertFalse(active("8h", "2026-10-09T07:59:59"))
        self.assertTrue(active("8h", "2026-10-09T08:00:00"))
        self.assertTrue(active("8h", "2026-10-09T08:59:59"))
        self.assertFalse(active("8h", "2026-10-09T09:00:00"))

    def test_hour_ranges_and_lists(self) -> None:
        self.assertTrue(active("8h-12h", "2026-10-09T12:59:59"))
        self.assertFalse(active("8h-12h", "2026-10-09T13:00:00"))
        self.assertTrue(active("22h-2h", "2026-10-10T02:30:00"))  # Fri 22h-2h spills into Saturday
        self.assertFalse(active("Fri 22h-2h", "2026-10-09T02:30:00"))
        self.assertTrue(active("8h,13h", "2026-10-09T13:10:00"))
        self.assertFalse(active("8h,13h", "2026-10-09T10:10:00"))

    def test_minute_of_every_hour(self) -> None:
        for hour in (0, 7, 13, 23):
            with self.subTest(hour=hour):
                self.assertFalse(active("30m", f"2026-10-09T{hour:02d}:29:59"))
                self.assertTrue(active("30m", f"2026-10-09T{hour:02d}:30:00"))
                self.assertTrue(active("30min", f"2026-10-09T{hour:02d}:30:59"))
                self.assertFalse(active("30min", f"2026-10-09T{hour:02d}:31:00"))

    def test_minute_ranges_wrap(self) -> None:
        self.assertTrue(active("50m-10m", "2026-10-09T09:55:00"))
        self.assertTrue(active("50m-10m", "2026-10-09T10:10:59"))
        self.assertFalse(active("50m-10m", "2026-10-09T10:11:00"))
        self.assertFalse(active("50m-10m", "2026-10-09T10:30:00"))

    def test_hour_and_minute_conjunction(self) -> None:
        self.assertTrue(active("8h 30m", "2026-10-09T08:30:30"))
        self.assertFalse(active("8h 30m", "2026-10-09T09:30:30"))
        self.assertFalse(active("8h 30m", "2026-10-09T08:00:30"))
        self.assertTrue(active("Mon-Fri 8h-12h 30m", "2026-10-09T11:30:10"))
        self.assertFalse(active("Mon-Fri 8h-12h 30m", "2026-10-10T11:30:10"))  # Saturday


class V7Relative(unittest.TestCase):
    def test_run_week_after_first_monday(self) -> None:
        text = "1-7 Mon + 5 day"
        self.assertTrue(active(text, "2026-10-09T10:00:00"))
        self.assertFalse(active(text, "2026-10-10T00:00:00"))
        self.assertTrue(active(text, "2026-10-09T23:59:59"))
        self.assertFalse(active(text, "2026-10-12T12:00:00"))
        self.assertTrue(active(text, "2026-11-02T00:00:00"))
        self.assertTrue(active(text, "2026-11-06T23:59:59"))

    def test_run_up_to_christmas(self) -> None:
        text = "40 days until Dec 24"
        self.assertFalse(active(text, "2026-11-14T23:59:59"))
        self.assertTrue(active(text, "2026-11-15T00:00:00"))
        self.assertTrue(active(text, "2026-12-24T12:00:00"))
        self.assertFalse(active(text, "2026-12-25T00:00:00"))

    def test_bare_time_anchor_starts_at_the_point(self) -> None:
        text = "08:00 + 2 hours"
        self.assertFalse(active(text, "2026-10-09T07:59:59"))
        self.assertTrue(active(text, "2026-10-09T08:00:00"))
        self.assertTrue(active(text, "2026-10-09T09:59:59"))
        self.assertFalse(active(text, "2026-10-09T10:00:00"))

    def test_calendar_then_elapsed_units(self) -> None:
        # Fri 08:00 + 1 day (wall clock) + 2 hours (elapsed) -> Sat 10:00
        rs = run("Fri 08:00 + 1 day 2 hours", "2026-10-09T00:00:00", "2026-10-12T00:00:00", UTC)
        self.assertEqual(utc(rs), [("2026-10-09 08:00:00", "2026-10-10 10:00:00")])

    def test_long_lookback_and_month_arithmetic(self) -> None:
        # anchor Jan 31 + 1 month: relativedelta clamps to the end of February
        self.assertTrue(active("Jan 31 + 1 month", "2027-02-27T12:00:00", UTC))
        # a duration far longer than the window: instance began almost a year before the window
        self.assertTrue(active("Mar 1 + 11 months", "2026-12-15T00:00:00", UTC))
        self.assertFalse(active("Mar 1 + 11 months", "2027-02-01T00:00:00", UTC))

    def test_calendar_units_use_wall_clock_across_dst(self) -> None:
        # 2026-03-28 12:00 Budapest + 1 day = 2026-03-29 12:00 local (23 elapsed hours across the gap)
        rs = run("Mar 28 12:00 + 1 day", "2026-03-28T00:00:00", "2026-03-30T00:00:00")
        self.assertEqual(utc(rs), [("2026-03-28 11:00:00", "2026-03-29 10:00:00")])

    def test_always_on_anchor_terminates(self) -> None:
        # An anchor that never ends/starts has no instance start; the look-back is capped, so this
        # must simply return (see PLAN risks), not loop forever.
        rs = evaluate(parse_interval("00:00-24:00 + 1 day"), ep("2026-10-09T00:00:00"), ep("2026-10-10T00:00:00"), UTC)
        self.assertIsNotNone(rs)


class V8Spans(unittest.TestCase):
    def test_recurring_span_end_is_inclusive(self) -> None:
        self.assertTrue(active("Apr 1 -- Jun 15", "2027-06-15T23:59:59", UTC))
        self.assertFalse(active("Apr 1 -- Jun 15", "2027-06-16T00:00:00", UTC))
        self.assertTrue(active("Apr 1 -- Jun 15", "2027-04-01T00:00:00", UTC))
        self.assertFalse(active("Apr 1 -- Jun 15", "2027-03-31T23:59:59", UTC))

    def test_year_wrapping_span(self) -> None:
        self.assertTrue(active("Dec 20 -- Jan 10", "2027-01-05T12:00:00", UTC))
        self.assertTrue(active("Dec 20 -- Jan 10", "2026-12-20T00:00:00", UTC))
        self.assertFalse(active("Dec 20 -- Jan 10", "2027-01-11T00:00:00", UTC))
        self.assertFalse(active("Dec 20 -- Jan 10", "2026-10-09T12:00:00", UTC))

    def test_explicit_year_span(self) -> None:
        text = "2026 Apr 1 -- 20"
        self.assertTrue(active(text, "2026-04-20T12:00:00", UTC))
        self.assertFalse(active(text, "2026-04-21T00:00:00", UTC))
        self.assertFalse(active(text, "2027-04-10T00:00:00", UTC))
        self.assertTrue(active("2026-04-01 -- 20", "2026-04-20T12:00:00", UTC))

    def test_span_with_times(self) -> None:
        text = "Apr 1 08:00 -- Apr 3 17:00"
        self.assertFalse(active(text, "2026-04-01T07:59:59", UTC))
        self.assertTrue(active(text, "2026-04-01T08:00:00", UTC))
        self.assertTrue(active(text, "2026-04-03T16:59:59", UTC))
        self.assertFalse(active(text, "2026-04-03T17:00:00", UTC))

    def test_feb_29_endpoint_collapses(self) -> None:
        # non-leap year: Feb 29 as the end day contributes nothing -> ends at Mar 1 00:00
        self.assertTrue(active("Feb 25 -- Feb 29", "2027-02-28T23:59:59", UTC))
        self.assertFalse(active("Feb 25 -- Feb 29", "2027-03-01T00:00:00", UTC))
        self.assertTrue(active("Feb 25 -- Feb 29", "2028-02-29T12:00:00", UTC))
        # as a start day it begins at Mar 1 00:00
        self.assertFalse(active("Feb 29 -- Mar 2", "2027-02-28T23:59:59", UTC))
        self.assertTrue(active("Feb 29 -- Mar 2", "2027-03-01T00:00:00", UTC))

    def test_span_zone(self) -> None:
        self.assertTrue(active("Apr 1 -- 2 Europe/Budapest", "2026-03-31T22:00:00", UTC))
        self.assertFalse(active("Apr 1 -- 2 Europe/Budapest", "2026-03-31T21:59:59", UTC))


class V9Zones(unittest.TestCase):
    def test_named_zone(self) -> None:
        text = "*-12-* 08:00-09:00 Europe/Berlin"
        self.assertTrue(active(text, "2026-12-01T07:30:00", UTC))
        self.assertFalse(active(text, "2026-12-01T06:59:59", UTC))
        self.assertTrue(active("*-07-* 08:00-09:00 Europe/Berlin", "2026-07-01T06:30:00", UTC))

    def test_numeric_offset(self) -> None:
        self.assertTrue(active("08:00-09:00 UTC+0300", "2026-10-09T05:30:00", UTC))
        self.assertFalse(active("08:00-09:00 UTC+0300", "2026-10-09T08:30:00", UTC))
        self.assertTrue(active("08:00-09:00 UTC-04:30", "2026-10-09T12:45:00", UTC))


class V14Dst(unittest.TestCase):
    def test_spring_gap_empty_range(self) -> None:
        self.assertEqual(utc(run("02:00-03:00", "2026-03-29T00:00:00", "2026-03-30T00:00:00")), [])
        self.assertFalse(active("02:00-03:00", "2026-03-29T00:59:59", BUD, UTC))
        self.assertFalse(active("02:00-03:00", "2026-03-29T01:00:00", BUD, UTC))

    def test_spring_crossing_range(self) -> None:
        text = "01:00-04:00"
        self.assertEqual(utc(run(text, "2026-03-29T00:00:00", "2026-03-29T12:00:00")), [("2026-03-29 00:00:00", "2026-03-29 02:00:00")])
        self.assertTrue(active(text, "2026-03-29T00:30:00", BUD, UTC))
        self.assertTrue(active(text, "2026-03-29T01:30:00", BUD, UTC))
        self.assertFalse(active(text, "2026-03-29T02:00:00", BUD, UTC))

    def test_fall_fold_range(self) -> None:
        text = "02:00-03:00"
        self.assertEqual(utc(run(text, "2026-10-25T00:00:00", "2026-10-26T00:00:00")), [("2026-10-25 00:00:00", "2026-10-25 02:00:00")])
        self.assertTrue(active(text, "2026-10-25T00:30:00", BUD, UTC))
        self.assertTrue(active(text, "2026-10-25T01:30:00", BUD, UTC))
        self.assertFalse(active(text, "2026-10-25T02:00:00", BUD, UTC))

    def test_fall_crossing_range(self) -> None:
        text = "01:00-04:00"
        self.assertEqual(utc(run(text, "2026-10-24T12:00:00", "2026-10-26T00:00:00")), [("2026-10-24 23:00:00", "2026-10-25 03:00:00")])
        for at in ("2026-10-25T00:30:00", "2026-10-25T01:30:00", "2026-10-25T02:30:00"):
            self.assertTrue(active(text, at, BUD, UTC))
        self.assertFalse(active(text, "2026-10-25T03:00:00", BUD, UTC))

    def test_weekday_work_hours_keep_wall_clock(self) -> None:
        text = "Mon-Fri 08:00-16:00"
        # Fri 2026-03-27 (CET, UTC+1) and Mon 2026-03-30 (CEST, UTC+2)
        self.assertEqual(utc(run(text, "2026-03-27T00:00:00", "2026-03-28T00:00:00")), [("2026-03-27 07:00:00", "2026-03-27 15:00:00")])
        self.assertEqual(utc(run(text, "2026-03-30T00:00:00", "2026-03-31T00:00:00")), [("2026-03-30 06:00:00", "2026-03-30 14:00:00")])
        # fall back: Fri 2026-10-23 (CEST) vs Mon 2026-10-26 (CET): boundaries move one hour later
        self.assertEqual(utc(run(text, "2026-10-23T00:00:00", "2026-10-24T00:00:00")), [("2026-10-23 06:00:00", "2026-10-23 14:00:00")])
        self.assertEqual(utc(run(text, "2026-10-26T00:00:00", "2026-10-27T00:00:00")), [("2026-10-26 07:00:00", "2026-10-26 15:00:00")])

    def test_full_day_clauses_merge_across_dst(self) -> None:
        rs = run("Sun", "2026-03-28T00:00:00", "2026-03-30T00:00:00")
        self.assertEqual(utc(rs), [("2026-03-28 23:00:00", "2026-03-29 22:00:00")])  # a 23-hour Sunday
        self.assertEqual(len(run("Sat,Sun", "2026-03-28T00:00:00", "2026-03-30T00:00:00")), 1)  # adjacent days merge


class WindowContract(unittest.TestCase):
    """eval(spec, lo, hi) == eval(spec, LO, HI) ∩ [lo, hi) for any enclosing window."""

    TEXTS = [
        "08:00-16:00", "23:00-04:00", "Mon-Fri 08:00-12:00,13:00-17:00", "Dec-Feb", "*-*-01", "Fri 22:00-02:00",
        "Mon 8h 30m", "30m", "22h-2h", "Apr 1 -- Jun 15", "Dec 20 -- Jan 10", "Feb 25 -- Feb 29",
        "1-7 Mon + 5 day", "40 days until Dec 24", "08:00 + 2 hours", "Jan 31 + 1 month", "Mar 1 + 11 months",
        "Mon-Fri 08:00-16:00 Europe/Berlin", "02:00-03:00", "01:00-04:00 America/New_York",
        "Mon 10:00 + 3 hours 30 minutes", "2 weeks until Mar 29",
        "40 days before Dec 24", "10 days after Oct 1", "2 days before Apr 10 12:00", "3 hours after 08:00",
        "1 month before Mar 31", "1 year before Dec 20 -- Jan 10", "2 years after Feb 29", "1 day before 02:00-03:00",
        "1 week after Mon-Fri 08:00-16:00 Europe/Berlin",
    ]

    def test_window_independence(self) -> None:
        rng = random.Random(4242)
        base = ep("2026-01-01T00:00:00")
        for text in self.TEXTS:
            expr = parse_interval(text)
            big_lo, big_hi = base - 400 * 86400, base + 800 * 86400
            whole = evaluate(expr, big_lo, big_hi, BUD)
            for _ in range(12):
                lo = rng.randint(base, base + 400 * 86400)
                hi = lo + rng.choice([1, 60, 3600, 86400, 9 * 86400, 70 * 86400])
                with self.subTest(text=text, lo=lo, hi=hi):
                    self.assertEqual(evaluate(expr, lo, hi, BUD), whole.clip(lo, hi))


if __name__ == "__main__":
    unittest.main()
