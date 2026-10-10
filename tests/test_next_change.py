"""Tests for --next-change (SPEC §10, V1-V8 columns, V13 oracle, V14)."""
from __future__ import annotations

import os
import random
import tempfile
import time
import unittest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from helpers import run_cli
from kairoslib.evaluate import to_epoch
from kairoslib.next_change import CYCLE, finite_end, next_change, search_limit
from kairoslib.reader import read_config
from kairoslib.states import build_lines, reported_sets, states_at
from kairoslib.timezones import rules_start

BUD = ZoneInfo("Europe/Budapest")
UTC = timezone.utc


def epoch(text: str, zone=BUD) -> int:
    return to_epoch(datetime.fromisoformat(text).replace(tzinfo=zone))


def make_lines(config: str, zone=BUD, now: str = "2026-10-09 12:00"):
    return build_lines(
        read_config(config, "t.conf"), path="t.conf", tz=zone,
        now=datetime.fromisoformat(now).replace(tzinfo=zone), window=None,
    )


def nc(config: str, at: str, zone=BUD):
    lines = make_lines(config, zone)
    found = next_change(lines, epoch(at, zone), zone)
    return None if found is None else datetime.fromtimestamp(found, zone).strftime("%Y-%m-%d %H:%M:%S")


V1 = "08:00-16:00 = work\n12:00-13:00 = lunch\n"
V4 = "Mon-Fri\n  Dec = weekdays in December\n"
V5 = "Jun,Jul,Aug = summer\n  Sun = @Sunday\n    20:00-23:00 = evening in summer's ~s\n"
V6 = "*-*-01 = first\n  ! Sun,Sat = first, on weekdays\n"


class SpecVectorColumns(unittest.TestCase):
    def check(self, config: str, rows) -> None:
        for at, expected in rows:
            with self.subTest(at=at):
                self.assertEqual(nc(config, at), expected)

    def test_v1(self) -> None:
        self.check(V1, [
            ("2026-10-09 07:59:59", "2026-10-09 08:00:00"),
            ("2026-10-09 09:00", "2026-10-09 12:00:00"),
            ("2026-10-09 10:00", "2026-10-09 12:00:00"),
            ("2026-10-09 12:00:00", "2026-10-09 13:00:00"),
            ("2026-10-09 12:05", "2026-10-09 13:00:00"),
            ("2026-10-09 13:01", "2026-10-09 16:00:00"),
            ("2026-10-09 16:00:00", "2026-10-10 08:00:00"),
        ])

    def test_v2(self) -> None:
        self.check("23:00-04:00 = evening\n", [
            ("2026-10-10 02:00", "2026-10-10 04:00:00"),
            ("2026-10-09 22:59:59", "2026-10-09 23:00:00"),
            ("2026-10-09 12:00", "2026-10-09 23:00:00"),
        ])

    def test_v3(self) -> None:
        self.check("Dec-Feb = winter\n", [
            ("2026-10-09 12:00", "2026-12-01 00:00:00"),
            ("2027-02-28 12:00", "2027-03-01 00:00:00"),
            ("2027-01-15 12:00", "2027-03-01 00:00:00"),
        ])

    def test_v4(self) -> None:
        self.check(V4, [("2026-12-04 12:00", "2026-12-05 00:00:00"), ("2026-12-05 10:00", "2026-12-07 00:00:00")])

    def test_v5(self) -> None:
        self.check(V5, [
            ("2026-07-05 19:00", "2026-07-05 20:00:00"),
            ("2026-07-05 21:00", "2026-07-05 23:00:00"),
            ("2026-07-05 23:00", "2026-07-12 20:00:00"),
        ])

    def test_v6(self) -> None:
        self.check(V6, [("2026-10-01 12:00", "2026-10-02 00:00:00"), ("2026-11-01 12:00", "2026-11-02 00:00:00")])

    def test_v7(self) -> None:
        self.check("1-7 Mon + 5 day = run\n", [
            ("2026-10-09 10:00", "2026-10-10 00:00:00"),
            ("2026-10-10 12:00", "2026-11-02 00:00:00"),
        ])
        self.check("40 days until Dec 24 = runup\n", [
            ("2026-11-14 23:59:59", "2026-11-15 00:00:00"),
            ("2026-12-24 12:00", "2026-12-25 00:00:00"),
        ])

    def test_v8(self) -> None:
        self.check("Dec 20 -- Jan 10 = holidays\n", [("2026-10-09 12:00", "2026-12-20 00:00:00"), ("2027-01-05 12:00", "2027-01-11 00:00:00")])
        self.check("Apr 1 -- Jun 15 = spring\n", [("2027-06-15 23:59:59", "2027-06-16 00:00:00")])
        self.check("2026 Apr 1 -- 20 = x\n", [("2026-04-20 12:00", "2026-04-21 00:00:00")])


class NoChangeAndSkippedBoundaries(unittest.TestCase):
    def test_overlapping_same_name_candidates_are_not_changes(self) -> None:
        # candidate boundaries at 10:00 (second range starts) and 12:00 (first ends) change nothing
        config = "08:00-12:00 = a\n10:00-14:00 = a\n"
        self.assertEqual(nc(config, "2026-10-09 09:00"), "2026-10-09 14:00:00")
        self.assertEqual(nc(config, "2026-10-09 07:00"), "2026-10-09 08:00:00")

    def test_adjacent_same_name_ranges_merge(self) -> None:
        self.assertEqual(nc("08:00-12:00 = a\n12:00-16:00 = a\n", "2026-10-09 09:00"), "2026-10-09 16:00:00")

    def test_different_names_adjacent_do_change(self) -> None:
        self.assertEqual(nc("08:00-12:00 = a\n12:00-16:00 = b\n", "2026-10-09 09:00"), "2026-10-09 12:00:00")

    def test_hidden_and_stateless_lines_are_not_change_points(self) -> None:
        config = "08:00-12:00 = work\n10:00-11:00 = @hidden\n09:00-09:30\n"
        self.assertEqual(nc(config, "2026-10-09 07:00"), "2026-10-09 08:00:00")
        self.assertEqual(nc(config, "2026-10-09 08:30"), "2026-10-09 12:00:00")

    def test_hidden_only_config_never_changes(self) -> None:
        self.assertIsNone(nc("Mon = @hidden\n08:00-09:00\n", "2026-10-09 12:00"))

    def test_finite_exception_ends_and_proof_concludes(self) -> None:
        config = "2026-12-24 = christmas eve\n"
        self.assertEqual(nc(config, "2026-10-09 12:00"), "2026-12-24 00:00:00")
        self.assertEqual(nc(config, "2026-12-24 12:00"), "2026-12-25 00:00:00")
        self.assertIsNone(nc(config, "2026-12-25 00:00:00"))
        self.assertIsNone(nc("2026 Apr 1 -- 20 = x\n", "2026-04-21 00:00:00"))

    def test_finite_relative_tail_is_followed(self) -> None:
        config = "2026-12-24 + 3 months = tail\n"
        self.assertEqual(nc(config, "2026-12-25 12:00"), "2027-03-24 00:00:00")
        self.assertIsNone(nc(config, "2027-03-24 00:00:00"))

    def test_always_on_has_no_future_change(self) -> None:
        self.assertIsNone(nc("00:00-24:00 = always\n", "2026-10-09 12:00"))

    def test_negated_finite_line_becomes_constant_afterwards(self) -> None:
        config = "! 2026 = not 2026\n"
        self.assertEqual(nc(config, "2026-10-09 12:00"), "2027-01-01 00:00:00")
        self.assertIsNone(nc(config, "2027-01-01 00:00:00"))

    def test_last_representable_changes_do_not_crash(self) -> None:
        self.assertEqual(nc("Dec 20 = late\n", "9999-06-01 00:00"), "9999-12-20 00:00:00")
        self.assertIsNone(nc("Dec 20 = late\n", "9999-12-21 00:00"))
        self.assertIsNone(nc("2026-12-24 = x\n", "9999-06-01 00:00"))


class RecurrenceFingerprint(unittest.TestCase):
    def test_finite_end_covers_years_and_tails(self) -> None:
        lines = make_lines("2026-12-24 + 3 months = tail\nMon = m\n")
        exprs = [line.expr for line in lines]
        end = finite_end(exprs)
        self.assertGreater(end, epoch("2027-03-25 00:00", UTC))
        self.assertLess(end, epoch("2027-06-01 00:00", UTC))
        self.assertEqual(finite_end([line.expr for line in make_lines("Mon = m\n")]), 0)

    def test_zone_rules_extend_the_search_cycle(self) -> None:
        at = epoch("2026-10-09 12:00")
        no_zone = search_limit(make_lines("2026-12-24 = x\n", UTC), at, UTC)
        with_zone = search_limit(make_lines("2026-12-24 = x\n"), at, BUD)
        # the TZif rules of Europe/Budapest only take over after its last explicit transition (2037)
        self.assertGreater(rules_start("Europe/Budapest"), epoch("2037-01-01 00:00", UTC))
        self.assertGreaterEqual(with_zone, rules_start("Europe/Budapest") + CYCLE)
        self.assertGreater(with_zone, no_zone)
        self.assertEqual(rules_start("UTC"), 0)

    def test_clause_zone_is_part_of_the_fingerprint(self) -> None:
        lines = make_lines("2026-12-24 America/New_York = x\n", UTC)
        self.assertGreaterEqual(search_limit(lines, epoch("2026-10-09 12:00", UTC), UTC), rules_start("America/New_York") + CYCLE)


class Performance(unittest.TestCase):
    def test_leap_day_config_with_100_lines(self) -> None:
        children = "".join(f"  {h:02d}:{m:02d}-{h:02d}:{m + 5:02d} = s{h}{m}\n" for h in range(20) for m in (0, 10, 20, 30, 40))
        config = "Feb 29 = leap\n" + children
        self.assertEqual(config.count("\n"), 101)
        started = time.time()
        self.assertEqual(nc(config, "2026-10-09 12:00"), "2028-02-29 00:00:00")
        self.assertEqual(nc(config, "2028-03-01 00:00"), "2032-02-29 00:00:00")
        self.assertLess(time.time() - started, 5.0)

    def test_leap_day_alone_after_the_last_leap_year_in_range(self) -> None:
        started = time.time()
        self.assertEqual(nc("Feb 29 = leap\n", "2096-03-01 00:00"), "2104-02-29 00:00:00")  # 2100 is not a leap year
        self.assertLess(time.time() - started, 5.0)

    def test_weekday_and_leap_day_selector(self) -> None:
        # the next Feb 29 that is a Monday after 2026 is 2044
        self.assertEqual(nc("Feb 29 Mon = rare\n", "2026-10-09 12:00"), "2044-02-29 00:00:00")


class DstAndBareTime(unittest.TestCase):
    def test_spring_gap_empty_range_never_changes_anything(self) -> None:
        config = "02:00-03:00 = gap\n"
        self.assertEqual(nc(config, "2026-03-28 12:00"), "2026-03-30 02:00:00")  # skips the empty range on 03-29

    def test_fall_fold_range_changes(self) -> None:
        config = "02:00-03:00 = fold\n"
        self.assertEqual(nc(config, "2026-10-24 23:00"), "2026-10-25 02:00:00")
        # the end is 03:00 standard time = 02:00 UTC
        lines = make_lines(config)
        start = epoch("2026-10-25 00:00", UTC)
        first = next_change(lines, start - 3600, BUD)
        second = next_change(lines, first, BUD)
        self.assertEqual((first, second), (start, epoch("2026-10-25 02:00", UTC)))

    def test_bare_time_is_one_minute(self) -> None:
        self.assertEqual(nc("08:00 = ping\n", "2026-10-09 07:00"), "2026-10-09 08:00:00")
        self.assertEqual(nc("08:00 = ping\n", "2026-10-09 08:00:00"), "2026-10-09 08:01:00")

    def test_relative_anchor_from_bare_time(self) -> None:
        self.assertEqual(nc("08:00 + 2 hours = x\n", "2026-10-09 07:00"), "2026-10-09 08:00:00")
        self.assertEqual(nc("08:00 + 2 hours = x\n", "2026-10-09 08:00:00"), "2026-10-09 10:00:00")
        self.assertEqual(nc("2 hours until 08:00 = x\n", "2026-10-09 07:00"), "2026-10-09 08:00:00")
        self.assertEqual(nc("2 hours until 08:00 = x\n", "2026-10-09 05:00"), "2026-10-09 06:00:00")

    def test_hour_and_minute_items(self) -> None:
        self.assertEqual(nc("8h = h\n", "2026-10-09 07:00"), "2026-10-09 08:00:00")
        self.assertEqual(nc("30m = m\n", "2026-10-09 07:45"), "2026-10-09 08:30:00")


# ---------------------------------------------------------------------------------------------
# V13: brute-force oracle
# ---------------------------------------------------------------------------------------------

ORACLE_CONFIGS = {
    "V1": V1,
    "V2": "23:00-04:00 = evening\n",
    "V4": V4,
    "V5": V5,
    "V6": V6,
    "V7a": "1-7 Mon + 5 day = run\n",
    "V7b": "40 days until Dec 24 = runup\n",
    "overlap": "08:00-12:00 = a\n10:00-14:00 = a\n13:00-15:00 = b\n",
    "hidden": "Mon-Fri 08:00-12:00 = work\n  09:00-10:00 = @h\n  11:00-11:30 = brief\n",
    "dst": "02:00-03:00 = fold\n01:00-04:00 = crossing\n",
    "before": "40 days before Dec 24 = early\n",
    "after": "10 days after 1-7 Mon = later\n3 hours after 08:00 = brunch\n",
}


# instants around which the oracle also probes, so boundaries of sparse configs are hit
FOCUS = {
    "V4": "2026-12-04 12:00", "V5": "2026-07-05 12:00", "V6": "2026-10-01 00:00",
    "V7a": "2026-10-05 00:00", "V7b": "2026-12-23 12:00", "hidden": "2026-10-09 08:00",
    "before": "2026-11-14 00:00", "after": "2026-10-16 00:00",
}


def state_names(lines, t: int, zone):
    return sorted(states_at(reported_sets(lines, t, t + 1, zone), t))


class BruteForceOracle(unittest.TestCase):
    def test_next_change_matches_stepping(self) -> None:
        rng = random.Random(1010)
        base = epoch("2026-09-20 00:00", UTC)
        for name, config in ORACLE_CONFIGS.items():
            lines = make_lines(config)
            for _ in range(14):
                at = base + rng.randint(0, 150 * 86400)
                if name == "dst":
                    at = epoch("2026-10-24 12:00", UTC) + rng.randint(0, 2 * 86400)
                if name in FOCUS and rng.random() < 0.6:
                    at = epoch(FOCUS[name], BUD) + rng.randint(-2 * 86400, 2 * 86400)
                at -= at % 60 - rng.choice([0, 0, 17, 43])  # exercise instants that are not on a minute
                with self.subTest(config=name, at=at):
                    found = next_change(lines, at, BUD)
                    reference = state_names(lines, at, BUD)
                    if found is None or found - at > 3 * 86400:
                        # far away: only check both sides of the answer and a sample in between
                        if found is None:
                            continue
                        self.assertNotEqual(state_names(lines, found, BUD), state_names(lines, found - 1, BUD))
                        self.assertEqual(state_names(lines, found - 1, BUD), reference)
                        for probe in (rng.randint(at, found - 1) for _ in range(120)):
                            self.assertEqual(state_names(lines, probe, BUD), reference)
                        continue
                    # near: step one minute (no config uses seconds), then refine within the minute
                    t = at
                    while state_names(lines, t, BUD) == reference:
                        t += 60
                        self.assertLess(t - at, 4 * 86400)
                    s = t - 60
                    while state_names(lines, s, BUD) == reference:
                        s += 1
                    self.assertEqual(found, s)


class CliNextChange(unittest.TestCase):
    def _cli(self, config, at, tz, extra):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "k.conf")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(config)
            return run_cli(["--tz", tz, "--at", at, "--next-change", *extra, "-c", path])

    def test_default_format(self) -> None:
        code, out, err = self._cli(V1, "2026-10-09 09:00", "Europe/Budapest", ())
        self.assertEqual((code, out, err), (0, "2026-10-09 12:00:00\n", ""))

    def test_formats(self) -> None:
        code, out, _ = self._cli(V1, "2026-10-09 09:00", "Europe/Budapest", ("--format", "iso"))
        self.assertEqual(out, "2026-10-09T12:00:00+02:00\n")
        code, out, _ = self._cli(V1, "2026-10-09 09:00", "Europe/Budapest", ("--format", "epoch"))
        self.assertEqual(out, f"{epoch('2026-10-09 12:00')}\n")
        code, out, _ = self._cli(V1, "2026-10-09 09:00", "Europe/Budapest", ("--format", "%H:%M on %d.%m."))
        self.assertEqual(out, "12:00 on 09.10.\n")

    def test_no_future_change_prints_nothing(self) -> None:
        code, out, err = self._cli("2026 Apr 1 -- 20 = x\n", "2026-04-21 00:00:00", "Europe/Budapest", ())
        self.assertEqual((code, out, err), (0, "", ""))

    def test_dst_fold_warning(self) -> None:
        config = "02:00-03:00 = fold\n"
        code, out, err = self._cli(config, "2026-10-24 23:30", "Europe/Budapest", ())
        self.assertEqual((code, out), (0, "2026-10-25 02:00:00\n"))
        self.assertIn("warning", err)
        self.assertIn("fold", err)
        code, out, err = self._cli(config, "2026-10-24 23:30", "Europe/Budapest", ("--format", "iso"))
        self.assertEqual((out, err), ("2026-10-25T02:00:00+02:00\n", ""))
        code, out, err = self._cli(config, "2026-10-25 01:30 +00:00", "Europe/Budapest", ())  # next change: 03:00 CET
        self.assertEqual((out, err), ("2026-10-25 03:00:00\n", ""))

    def test_next_change_does_not_prune_commands(self) -> None:
        code, out, err = self._cli("Mon = x\n", "2026-10-09 12:00", "Europe/Budapest", ())
        self.assertEqual((code, out), (0, "2026-10-12 00:00:00\n"))


if __name__ == "__main__":
    unittest.main()
