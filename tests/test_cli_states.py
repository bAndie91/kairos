"""CLI conformance tests for default-mode output (SPEC §13 vectors, state columns).

Every test passes ``--at`` and ``--tz``; none depends on the wall clock.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date
from pathlib import Path

from helpers import make_ncal_stub, run_cli

BUDAPEST = "Europe/Budapest"


def states(config: str, at: str, tz: str = BUDAPEST) -> list[str]:
    code, stdout, stderr = run_cli(["--config", "-", "--tz", tz, "--at", at], config_text=config)
    assert code == 0, f"exit {code} for {at!r}: {stderr}"
    assert stderr == "", stderr
    return stdout.splitlines()


class CalendarFactsTests(unittest.TestCase):
    """SPEC §13 reference facts, so a wrong fact in the spec is caught here."""

    def test_reference_calendar_facts(self) -> None:
        self.assertEqual(date(2026, 10, 9).weekday(), 4)  # Friday
        self.assertEqual(date(2026, 10, 1).weekday(), 3)  # Thursday
        self.assertEqual(date(2026, 11, 1).weekday(), 6)  # Sunday
        self.assertEqual(date(2026, 12, 1).weekday(), 1)  # Tuesday
        self.assertEqual(date(2026, 7, 5).weekday(), 6)  # Sunday


class VectorTests(unittest.TestCase):
    def check(self, config: str, rows: list[tuple[str, list[str]]], tz: str = BUDAPEST) -> None:
        for at, expected in rows:
            with self.subTest(at=at):
                self.assertEqual(states(config, at, tz), expected)

    def test_v1_work_and_lunch(self) -> None:
        self.check("08:00-16:00 = work\n12:00-13:00 = lunch\n", [
            ("2026-10-09 07:59:59", []),
            ("2026-10-09 09:00", ["work"]),
            ("2026-10-09 10:00", ["work"]),
            ("2026-10-09 12:00:00", ["work", "lunch"]),
            ("2026-10-09 12:05", ["work", "lunch"]),
            ("2026-10-09 13:01", ["work"]),
            ("2026-10-09 16:00:00", []),
        ])

    def test_v1_output_follows_config_order_not_start_order(self) -> None:
        self.check("12:00-13:00 = lunch\n08:00-16:00 = work\n", [
            ("2026-10-09 12:30", ["lunch", "work"]),
        ])

    def test_v2_range_wrapping_midnight(self) -> None:
        self.check("23:00-04:00 = evening\n", [
            ("2026-10-10 02:00", ["evening"]),
            ("2026-10-09 22:59:59", []),
            ("2026-10-09 23:00:00", ["evening"]),
            ("2026-10-09 12:00", []),
        ])

    def test_v3_month_range_wrapping_year(self) -> None:
        self.check("Dec-Feb = winter\n", [
            ("2027-01-15 12:00", ["winter"]),
            ("2026-10-09 12:00", []),
            ("2027-02-28 12:00", ["winter"]),
            ("2027-03-01 00:00:00", []),
        ])

    def test_v4_state_less_parent_still_restricts_children(self) -> None:
        self.check("Mon-Fri\n  Dec = weekdays in December\n", [
            ("2026-12-01 10:00", ["weekdays in December"]),
            ("2026-12-05 10:00", []),  # Saturday
            ("2026-12-04 12:00", ["weekdays in December"]),
            ("2026-10-09 12:00", []),  # a weekday, but not December
        ])

    def test_v5_tilde_substitution_and_hidden_parent(self) -> None:
        config = "Jun,Jul,Aug = summer\n  Sun = @Sunday\n    20:00-23:00 = evening in summer's ~s\n"
        self.check(config, [
            ("2026-07-05 21:00", ["summer", "evening in summer's Sundays"]),
            ("2026-07-05 19:00", ["summer"]),
            ("2026-07-05 23:00", ["summer"]),
        ])

    def test_v6_negation_under_a_parent(self) -> None:
        config = "*-*-01 = first\n  ! Sun,Sat = first, on weekdays\n"
        self.check(config, [
            ("2026-10-01 12:00", ["first", "first, on weekdays"]),
            ("2026-11-01 12:00", ["first"]),
        ])

    def test_top_level_negation_is_the_complement(self) -> None:
        self.check("! Sat,Sun = weekday\n", [
            ("2026-10-09 12:00", ["weekday"]),
            ("2026-10-10 12:00", []),
        ])

    def test_v7_relative_intervals(self) -> None:
        self.check("1-7 Mon + 5 day = run\n", [
            ("2026-10-09 10:00", ["run"]),
            ("2026-10-10 00:00:00", []),
        ])
        self.check("40 days until Dec 24 = runup\n", [
            ("2026-11-14 23:59:59", []),
            ("2026-11-15 00:00:00", ["runup"]),
            ("2026-12-24 12:00", ["runup"]),
            ("2026-12-25 00:00:00", []),
        ])

    def test_v8_spans(self) -> None:
        self.check("Apr 1 -- Jun 15 = spring\n", [
            ("2027-06-15 23:59:59", ["spring"]),
            ("2027-06-16 00:00:00", []),
        ])
        self.check("Dec 20 -- Jan 10 = holidays\n", [
            ("2027-01-05 12:00", ["holidays"]),
            ("2026-10-09 12:00", []),
        ])
        self.check("2026 Apr 1 -- 20 = x\n", [
            ("2026-04-20 12:00", ["x"]),
            ("2026-04-21 00:00:00", []),
            ("2027-04-10 12:00", []),
        ])

    def test_v9_zones(self) -> None:
        self.check("*-12-* 08:00-09:00 Europe/Berlin = t\n", [
            ("2026-12-01 07:30:00", ["t"]),
            ("2026-12-01 06:59:59", []),
        ], tz="UTC")
        self.check("*-07-* 08:00-09:00 Europe/Berlin = t\n", [("2026-07-01 06:30:00", ["t"])], tz="UTC")
        self.check("08:00-09:00 UTC+0300 = t\n", [("2026-10-09 05:30:00", ["t"])], tz="UTC")

    def test_offset_in_at_overrides_the_display_zone(self) -> None:
        # 07:30 UTC is 08:30 in Budapest (CET, UTC+1) on 2026-12-01.
        self.check("08:00-09:00 = t\n", [
            ("2026-12-01T07:30:00Z", ["t"]),
            ("2026-12-01T07:30:00+00:00", ["t"]),
            ("2026-12-01 08:30:00+0100", ["t"]),
            ("2026-12-01 07:30", []),
        ])

    def test_same_name_in_several_lines_is_reported_once(self) -> None:
        self.check("Mon-Fri = busy\n12:00-13:00 = busy\n", [("2026-10-09 12:30", ["busy"])])

    def test_hidden_and_state_less_lines_are_not_reported(self) -> None:
        self.check("Fri\n  08:00-16:00 = @quiet\n    10:00-11:00 = ~ time\n", [
            ("2026-10-09 10:30", ["quiet time"]),
            ("2026-10-09 09:00", []),
        ])

    def test_no_active_state_prints_nothing(self) -> None:
        code, stdout, stderr = run_cli(
            ["--config", "-", "--tz", BUDAPEST, "--at", "2026-10-09 03:00"], config_text="08:00-16:00 = work\n",
        )
        self.assertEqual((code, stdout, stderr), (0, "", ""))


class MacroVectorTests(unittest.TestCase):
    def test_v10_string_macro(self) -> None:
        self.assertEqual(states("Q1 := Jan-Mar\nQ1 = first quarter\n", "2026-02-10"), ["first quarter"])

    def test_macro_scope_is_the_subtree(self) -> None:
        config = "Mon\n  M := Tue\n  M = inside\nM = outside\n"
        code, stdout, stderr = run_cli(["--config", "-", "--tz", "UTC", "--at", "2026-10-13"], config_text=config)
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("<stdin>:4:", stderr)  # `M` is unknown again after the subtree
        self.assertIn("unknown word 'M'", stderr)

    def test_sibling_subtrees_may_reuse_a_name(self) -> None:
        config = "Mon\n  M := 08:00-09:00\n  M = a\nTue\n  M := 10:00-11:00\n  M = b\n"
        self.assertEqual(states(config, "2026-10-12 08:30", "UTC"), ["a"])
        self.assertEqual(states(config, "2026-10-13 10:30", "UTC"), ["b"])

    def test_v10_command_macro_sees_other_macros(self) -> None:
        config = 'A := Tue\nD := ! echo "$KAIROS_MACRO_A"\nD = x\n'
        self.assertEqual(states(config, "2026-10-13 10:00", "UTC"), ["x"])  # a Tuesday
        self.assertEqual(states(config, "2026-10-14 10:00", "UTC"), [])

    def test_command_macro_output_is_one_line_and_may_be_empty(self) -> None:
        config = 'D := ! printf "Mon\\n,\\nTue\\n\\n"\nD = x\nE := ! true\nMon E = y\n'
        self.assertEqual(states(config, "2026-10-12 10:00", "UTC"), ["x", "y"])

    def test_string_macro_does_not_see_macros_defined_after_it(self) -> None:
        # B is defined before A, so the word A inside B stays a (then unknown) word.
        code, _out, err = run_cli(
            ["--config", "-", "--tz", "UTC", "--at", "2026-10-12"], config_text="B := A\nA := Mon\nB = x\n",
        )
        self.assertEqual(code, 2)
        self.assertIn("unknown word 'A'", err)

    def test_v10_pruning_runs_commands_only_where_the_parent_is_active(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            marker = Path(temp) / "marker"
            config = (
                "Jun,Jul,Aug = summer\n"
                f"  M := ! echo \"$KAIROS_INTERVAL_0|$KAIROS_STATE_0\" > '{marker}'; echo Mon\n"
                "  M = uses the macro\n"
            )
            july = run_cli(["--config", "-", "--tz", "UTC", "--at", "2026-07-15T12:00"], config_text=config)
            self.assertEqual(july[:2], (0, "summer\n"), july[2])
            self.assertEqual(marker.read_text(), "Jun,Jul,Aug|summer\n")

            marker.unlink()
            october = run_cli(["--config", "-", "--tz", "UTC", "--at", "2026-10-15T12:00"], config_text=config)
            self.assertEqual(october[:2], (0, ""), october[2])
            self.assertFalse(marker.exists(), "command ran inside a pruned subtree")

            checked = run_cli(
                ["--config", "-", "--tz", "UTC", "--at", "2026-10-15T12:00", "--check"], config_text=config,
            )
            self.assertEqual(checked[:2], (0, ""), checked[2])
            self.assertTrue(marker.exists(), "--check must run every command")

    def test_pruned_lines_are_still_validated_unless_they_need_a_command(self) -> None:
        config = "Jun,Jul,Aug = summer\n  Foo = broken\n  M := ! true\n  M Mon = needs a command\n"
        code, stdout, stderr = run_cli(["--config", "-", "--tz", "UTC", "--at", "2026-10-15"], config_text=config)
        self.assertEqual((code, stdout), (2, ""))
        self.assertIn("<stdin>:2:", stderr)  # parsed although the subtree is pruned
        self.assertNotIn("<stdin>:4:", stderr)  # structure only: its macro never ran

    def test_command_receives_now_and_the_ancestor_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "env"
            config = (
                "Fri = work day\n"
                f"  C := ! {{ echo \"$KAIROS_NOW\"; echo \"$KAIROS_INTERVAL_0\"; echo \"$KAIROS_STATE_0\"; echo \"$KAIROS_INTERVAL_1\"; echo \"$KAIROS_STATE_1\"; }} > '{out}'; echo 08:00-16:00\n"
                "  ! C = @ ~, off hours\n"
            )
            code, stdout, stderr = run_cli(
                ["--config", "-", "--tz", BUDAPEST, "--at", "2026-10-09 07:00"], config_text=config,
            )
            self.assertEqual(code, 0, stderr)
            self.assertEqual(stdout, "work day\n")  # the negated child is hidden by '@'
            self.assertEqual(out.read_text().splitlines(), [
                "2026-10-09T07:00:00+02:00",
                "Fri",
                "work day",
                "! C",  # the line's own INTERVAL is given unexpanded, negation marked
                "work day, off hours",
            ])

    def test_v11_easter_wrapper_with_the_fake_ncal(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            make_ncal_stub(temp)
            env = {"PATH": f"{temp}{os.pathsep}{os.environ['PATH']}"}
            config = 'Easter := ! date -d "$(ncal -e)" +%F\nEaster = Easter\n'
            code, stdout, stderr = run_cli(
                ["--config", "-", "--tz", "UTC", "--at", "2026-04-05 10:00", "--check"], config_text=config, env=env,
            )
            self.assertEqual((code, stdout), (0, ""), stderr)
            code, stdout, stderr = run_cli(
                ["--config", "-", "--tz", "UTC", "--at", "2026-04-05 10:00"], config_text=config, env=env,
            )
            self.assertEqual((code, stdout), (0, "Easter\n"), stderr)


class ErrorVectorTests(unittest.TestCase):
    """V12: each is an error: exit 2, empty stdout, file and line in stderr."""

    CASES = [
        ("08:00-25:00 = x\n", 1, "25:00"),
        ("Mon Tue = x\n", 1, "WEEKDAY"),
        ("Foo = x\n", 1, "'Foo'"),
        ("Mon = ~\n", 1, "'~'"),
        ("  Mon = x\n", 1, "first line"),
        ("Mon := x\n", 1, "'Mon'"),
        ("7 := x\n", 1, "'7'"),
        ("Q := Jan\nQ := Jan\n", 2, "'Q'"),
        ("Feb 30 = x\n", 1, "never exists"),
        ("2026-02-29 = x\n", 1, "2026-02-29"),
        ("Mon =\n", 1, "STATE"),
        ("= x\n", 1, "INTERVAL"),
        ("08:00-08:00 = x\n", 1, "equal ends"),
        ("Mon Foo/Bar = x\n", 1, "Foo/Bar"),
        ("Mon CEST = x\n", 1, "CEST"),
        ("Mon CST = x\n", 1, "CST"),
        ("mary := Mon\nannamary = x\n", 2, "annamary"),
        ("X := ! false\nX = x\n", 1, "'X'"),
    ]

    def test_each_case_is_rejected_with_location(self) -> None:
        for config, line, keyword in self.CASES:
            with self.subTest(config=config):
                code, stdout, stderr = run_cli(
                    ["--config", "-", "--tz", "UTC", "--at", "2026-10-09 10:00"], config_text=config,
                )
                self.assertEqual(code, 2, stderr)
                self.assertEqual(stdout, "")
                self.assertIn(f"<stdin>:{line}: error:", stderr)
                self.assertIn(keyword, stderr)

    def test_unused_failing_command_is_found_by_check_only(self) -> None:
        config = "X := ! false\n"
        base = ["--config", "-", "--tz", "UTC", "--at", "2026-10-09 10:00"]
        self.assertEqual(run_cli(base, config_text=config)[:2], (0, ""))  # lazy: never used, never run
        code, stdout, stderr = run_cli([*base, "--check"], config_text=config)
        self.assertEqual((code, stdout), (2, ""))
        self.assertIn("<stdin>:1: error:", stderr)

    def test_all_failing_lines_are_reported_before_exiting(self) -> None:
        config = "Foo = a\nMon = fine\n08:00-25:00 = b\nQ := Jan\nQ := Feb\n"
        code, stdout, stderr = run_cli(["--config", "-", "--tz", "UTC", "--at", "2026-10-09"], config_text=config)
        self.assertEqual((code, stdout), (2, ""))
        for line in (1, 3, 5):
            self.assertIn(f"<stdin>:{line}: error:", stderr)
        self.assertNotIn("<stdin>:2:", stderr)

    def test_failing_macro_used_twice_is_reported_once(self) -> None:
        code, _stdout, stderr = run_cli(
            ["--config", "-", "--tz", "UTC", "--at", "2026-10-09"], config_text="X := ! false\nX = a\nX = b\n",
        )
        self.assertEqual(code, 2)
        self.assertEqual(stderr.count("macro command"), 1)

    def test_bad_at_values(self) -> None:
        for value in ("tomorrow", "2026-13-01", "2026-02-30 10:00", "2026-10-09 24:00", "2026-10-09 10"):
            with self.subTest(value=value):
                code, stdout, stderr = run_cli(
                    ["--config", "-", "--tz", "UTC", "--at", value], config_text="Mon = x\n",
                )
                self.assertEqual((code, stdout), (2, ""))
                self.assertIn("--at", stderr)


class DstTests(unittest.TestCase):
    """V14 boundaries through the CLI (instants given as UTC offsets in --at)."""

    def active(self, config: str, at_utc: str) -> bool:
        return states(config, at_utc + "Z") != []

    def test_spring_gap_range_is_empty(self) -> None:
        for at in ("2026-03-29T00:59:59", "2026-03-29T01:00:00"):
            with self.subTest(at=at):
                self.assertFalse(self.active("02:00-03:00 = gap\n", at))

    def test_spring_crossing_range(self) -> None:
        config = "01:00-04:00 = crossing\n"
        for at, expected in (
            ("2026-03-29T00:30:00", True), ("2026-03-29T01:30:00", True), ("2026-03-29T02:00:00", False),
        ):
            with self.subTest(at=at):
                self.assertEqual(self.active(config, at), expected)

    def test_fall_fold_range_spans_both_occurrences(self) -> None:
        for at, expected in (
            ("2026-10-25T00:30:00", True), ("2026-10-25T01:30:00", True), ("2026-10-25T02:00:00", False),
        ):
            with self.subTest(at=at):
                self.assertEqual(self.active("02:00-03:00 = fold\n", at), expected)

    def test_fall_crossing_range(self) -> None:
        config = "01:00-04:00 = crossing\n"
        for at, expected in (
            ("2026-10-24T22:59:59", False), ("2026-10-24T23:00:00", True), ("2026-10-25T00:30:00", True),
            ("2026-10-25T01:30:00", True), ("2026-10-25T02:30:00", True), ("2026-10-25T03:00:00", False),
        ):
            with self.subTest(at=at):
                self.assertEqual(self.active(config, at), expected)

    def test_work_hours_keep_local_wall_clock_across_dst(self) -> None:
        config = "Mon-Fri 08:00-16:00 = work\n"
        for at, expected in (  # Friday 2026-03-27 (CET) and Monday 2026-03-30 (CEST)
            ("2026-03-27T06:59:59", False), ("2026-03-27T07:00:00", True),
            ("2026-03-27T14:59:59", True), ("2026-03-27T15:00:00", False),
            ("2026-03-30T05:59:59", False), ("2026-03-30T06:00:00", True),
            ("2026-03-30T13:59:59", True), ("2026-03-30T14:00:00", False),
            # Autumn: Friday 2026-10-23 (CEST) and Monday 2026-10-26 (CET).
            ("2026-10-23T05:59:59", False), ("2026-10-23T06:00:00", True),
            ("2026-10-26T06:59:59", False), ("2026-10-26T07:00:00", True),
            ("2026-10-26T14:59:59", True), ("2026-10-26T15:00:00", False),
        ):
            with self.subTest(at=at):
                self.assertEqual(self.active(config, at), expected)

    def test_bare_time_is_one_minute(self) -> None:
        for at, expected in (
            ("2026-10-09 07:59:59", []), ("2026-10-09 08:00:00", ["t"]),
            ("2026-10-09 08:00:59", ["t"]), ("2026-10-09 08:01:00", []),
        ):
            with self.subTest(at=at):
                self.assertEqual(states("08:00 = t\n", at, "UTC"), expected)

    def test_bare_time_anchor_is_point_like(self) -> None:
        # SPEC §7.1/§9: the instance starts at 08:00:00 and its own minute is
        # ignored, so the result is [08:00:00, 10:00:00). (V14 words this as
        # "begins at 10:00:00"; see PLAN.md, open questions.)
        for at, expected in (
            ("2026-10-09 07:59:59", []), ("2026-10-09 08:00:00", ["t"]),
            ("2026-10-09 09:59:59", ["t"]), ("2026-10-09 10:00:00", []),
        ):
            with self.subTest(at=at):
                self.assertEqual(states("08:00 + 2 hours = t\n", at, "UTC"), expected)


if __name__ == "__main__":
    unittest.main()
