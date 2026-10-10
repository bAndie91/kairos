"""Unit tests for hierarchy semantics, pruning and reported-state unions (SPEC §7, §5.4)."""
from __future__ import annotations

import random
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from kairoslib.errors import ErrorList
from kairoslib.evaluate import to_epoch
from kairoslib.ranges import RangeSet
from kairoslib.reader import read_config
from kairoslib.states import active_states, build_lines, effective_sets, reported_sets, states_at

TZ = ZoneInfo("Europe/Budapest")
DAY = 86400


def epoch(text: str) -> int:
    return to_epoch(datetime.fromisoformat(text).replace(tzinfo=TZ))


def lines_for(config: str, *, window=None, now: str = "2026-10-09 12:00"):
    return build_lines(
        read_config(config, "t.conf"), path="t.conf", tz=TZ, now=datetime.fromisoformat(now).replace(tzinfo=TZ),
        window=window,
    )


def local(ranges: RangeSet) -> list[tuple[str, str]]:
    fmt = "%Y-%m-%d %H:%M"
    return [
        (datetime.fromtimestamp(a, TZ).strftime(fmt), datetime.fromtimestamp(b, TZ).strftime(fmt))
        for a, b in ranges
    ]


class EffectiveSetTests(unittest.TestCase):
    LO, HI = epoch("2026-10-09 00:00"), epoch("2026-10-10 00:00")

    def test_child_is_restricted_by_its_parent(self) -> None:
        lines = lines_for("08:00-16:00 = work\n  12:00-18:00 = late lunch\n")
        eff = effective_sets(lines, self.LO, self.HI, TZ)
        self.assertEqual(local(eff[lines[0]]), [("2026-10-09 08:00", "2026-10-09 16:00")])
        self.assertEqual(local(eff[lines[1]]), [("2026-10-09 12:00", "2026-10-09 16:00")])

    def test_negated_child_is_subtracted_from_its_parent(self) -> None:
        lines = lines_for("08:00-16:00 = work\n  ! 12:00-13:00 = not lunch\n")
        eff = effective_sets(lines, self.LO, self.HI, TZ)
        self.assertEqual(
            local(eff[lines[1]]),
            [("2026-10-09 08:00", "2026-10-09 12:00"), ("2026-10-09 13:00", "2026-10-09 16:00")],
        )

    def test_top_level_negation_is_the_complement_in_the_window(self) -> None:
        lines = lines_for("! 08:00-16:00 = off\n")
        eff = effective_sets(lines, self.LO, self.HI, TZ)
        self.assertEqual(
            local(eff[lines[0]]),
            [("2026-10-09 00:00", "2026-10-09 08:00"), ("2026-10-09 16:00", "2026-10-10 00:00")],
        )

    def test_siblings_are_independent(self) -> None:
        lines = lines_for("08:00-12:00 = a\n10:00-14:00 = b\n")
        eff = effective_sets(lines, self.LO, self.HI, TZ)
        self.assertEqual(local(eff[lines[1]]), [("2026-10-09 10:00", "2026-10-09 14:00")])

    def test_window_is_respected_exactly(self) -> None:
        lines = lines_for("08:00-16:00 = work\n")
        eff = effective_sets(lines, epoch("2026-10-09 10:00"), epoch("2026-10-09 11:00"), TZ)
        self.assertEqual(local(eff[lines[0]]), [("2026-10-09 10:00", "2026-10-09 11:00")])


class ReportedSetTests(unittest.TestCase):
    LO, HI = epoch("2026-10-09 00:00"), epoch("2026-10-10 00:00")

    def test_same_name_lines_are_united(self) -> None:
        sets = reported_sets(lines_for("08:00-10:00 = busy\n09:00-12:00 = busy\n"), self.LO, self.HI, TZ)
        self.assertEqual(list(sets), ["busy"])
        self.assertEqual(local(sets["busy"]), [("2026-10-09 08:00", "2026-10-09 12:00")])

    def test_adjacent_same_name_ranges_merge_so_no_boundary_remains(self) -> None:
        sets = reported_sets(lines_for("08:00-10:00 = busy\n10:00-12:00 = busy\n"), self.LO, self.HI, TZ)
        self.assertEqual(local(sets["busy"]), [("2026-10-09 08:00", "2026-10-09 12:00")])

    def test_order_is_first_appearance_even_when_never_active(self) -> None:
        config = "Mon = never today\n08:00-09:00 = a\n  Fri = @hidden\n12:00-13:00 = b\n12:30-13:30 = never today\n"
        sets = reported_sets(lines_for(config), self.LO, self.HI, TZ)
        self.assertEqual(list(sets), ["never today", "a", "b"])

    def test_hidden_and_state_less_lines_are_not_reported(self) -> None:
        sets = reported_sets(lines_for("Fri\n  08:00-09:00 = @h\n    10:00-11:00 = ~ visible\n"), self.LO, self.HI, TZ)
        self.assertEqual(list(sets), ["h visible"])

    def test_states_at(self) -> None:
        sets = reported_sets(lines_for("08:00-16:00 = work\n12:00-13:00 = lunch\n"), self.LO, self.HI, TZ)
        self.assertEqual(states_at(sets, epoch("2026-10-09 12:00")), ["work", "lunch"])
        self.assertEqual(states_at(sets, epoch("2026-10-09 13:00")), ["work"])
        self.assertEqual(states_at(sets, epoch("2026-10-09 16:00")), [])


class DefaultModeTests(unittest.TestCase):
    def test_default_mode_agrees_with_the_window_algebra_at_random_instants(self) -> None:
        config = (
            "Mon-Fri 08:00-18:00 = work\n"
            "  12:00-13:00 = lunch\n"
            "  ! Fri = @not friday\n"
            "    16:00-17:00 = ~ review\n"
            "Dec-Feb = winter\n"
            "  Sun = @sunday\n"
            "    ! 06:00-22:00 = ~ night\n"
            "1-7 Mon + 5 day = first week\n"
            "Apr 1 -- Jun 15 = spring\n"
            "23:00-04:00 = late\n"
        )
        full = lines_for(config)
        lo, hi = epoch("2026-01-01 00:00"), epoch("2027-01-01 00:00")
        sets = reported_sets(full, lo, hi, TZ)
        rng = random.Random(20261010)
        for _ in range(60):
            t = rng.randrange(lo, hi)
            pruned = lines_for(config, window=(t, t + 1))
            with self.subTest(at=datetime.fromtimestamp(t, TZ).isoformat()):
                self.assertEqual(active_states(pruned, t), states_at(sets, t))

    def test_commands_below_an_inactive_parent_do_not_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            marker = Path(temp) / "ran"
            config = f"Fri = parent\n  M := ! touch '{marker}'; echo Mon\n  M = child\n    Tue = grandchild\n"
            saturday = epoch("2026-10-10 12:00")
            lines = lines_for(config, window=(saturday, saturday + 1))
            self.assertFalse(marker.exists())
            self.assertIsNone(lines[1].expr)  # needs the command: structure only
            self.assertFalse(lines[1].evaluated)
            self.assertTrue(lines[2].expr is not None)  # no macro: fully parsed
            self.assertEqual(active_states(lines, saturday), [])

            friday = epoch("2026-10-09 12:00")
            lines_for(config, window=(friday, friday + 1))
            self.assertTrue(marker.exists())

    def test_grandchildren_of_a_skipped_line_are_skipped_too(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            marker = Path(temp) / "ran"
            config = f"Fri = parent\n  Mon\n    G := ! touch '{marker}'; echo Mon\n    G = deep\n"
            friday = epoch("2026-10-09 12:00")  # Fri is active but its child Mon is not
            lines_for(config, window=(friday, friday + 1))
            self.assertFalse(marker.exists())

    def test_effective_sets_refuses_a_pruned_build(self) -> None:
        saturday = epoch("2026-10-10 12:00")
        lines = lines_for("Fri\n  M := ! echo Mon\n  M = x\n", window=(saturday, saturday + 1))
        with self.assertRaises(ValueError):
            effective_sets(lines, saturday, saturday + 1, TZ)

    def test_check_style_build_never_skips(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            marker = Path(temp) / "ran"
            lines_for(f"Fri\n  M := ! touch '{marker}'; echo Mon\n  M = x\n")
            self.assertTrue(marker.exists())


class ErrorCollectionTests(unittest.TestCase):
    def test_independent_errors_are_all_collected_in_line_order(self) -> None:
        with self.assertRaises(ErrorList) as caught:
            lines_for("Foo = a\nMon = ok\nQ := Jan\n08:00-25:00 = c\nQ := Feb\n")
        self.assertEqual([error.line for error in caught.exception.errors], [1, 4, 5])
        self.assertTrue(all(error.path == "t.conf" for error in caught.exception.errors))

    def test_children_of_a_broken_line_are_still_checked(self) -> None:
        with self.assertRaises(ErrorList) as caught:
            lines_for("Foo = a\n  Bar = b\n")
        self.assertEqual([error.line for error in caught.exception.errors], [1, 2])

    def test_macro_definition_errors_carry_the_macro_line(self) -> None:
        with self.assertRaises(ErrorList) as caught:
            lines_for("Mon\n  Tue := 1\n  Tue := 2\n")
        self.assertEqual([error.line for error in caught.exception.errors], [2, 3])

    def test_a_failing_command_is_an_error_only_when_a_line_evaluates_it(self) -> None:
        # D18: defining it runs nothing, so an unused failing command is fine ...
        self.assertEqual(lines_for("Mon = a\nX := ! false\n")[0].node.lineno, 1)
        # ... and it is reported, at the macro's line, once a line uses it.
        with self.assertRaises(ErrorList) as caught:
            lines_for("Mon = a\nX := ! false\nTue X = b\n")
        self.assertEqual([error.line for error in caught.exception.errors], [2])

    def test_a_failing_command_in_a_skipped_subtree_is_not_evaluated(self) -> None:
        config = "Fri = parent\n  X := ! false\n  X = child\n"
        saturday = epoch("2026-10-10 12:00")
        lines_for(config, window=(saturday, saturday + 1))  # pruned: no error
        with self.assertRaises(ErrorList):
            lines_for(config)  # --check / --next-change style: evaluated, fails


if __name__ == "__main__":
    unittest.main()
