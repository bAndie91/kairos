"""Tests for macro name validation, expansion, and command execution."""
from __future__ import annotations

import datetime as dt
import os
import tempfile
import unittest

from kairoslib.errors import IntervalKeeperError
from kairoslib.macros import CommandNotRun, MacroScope, expand_macro_text, validate_macro_name


class MacroTests(unittest.TestCase):
    def test_macro_name_validation_rejects_reserved_words(self) -> None:
        with self.assertRaises(IntervalKeeperError):
            validate_macro_name("Mon")
        with self.assertRaises(IntervalKeeperError):
            validate_macro_name("UTC")

    def test_expand_macro_text_is_single_pass_and_whole_word(self) -> None:
        self.assertEqual(
            expand_macro_text("annamary and birthday", {"birthday": "party", "mary": "x"}),
            "annamary and party",
        )
        self.assertEqual(
            expand_macro_text("A,B/C", {"A": "alpha", "B": "beta", "C": "gamma"}),
            "alpha,beta/gamma",
        )

    def test_visible_macro_redefinition_is_rejected(self) -> None:
        scope = MacroScope()
        scope.define("WORKDAY", "Mon")
        with self.assertRaises(IntervalKeeperError):
            scope.define("WORKDAY", "Tue")

        child = MacroScope(parent=scope)
        with self.assertRaises(IntervalKeeperError):
            child.define("WORKDAY", "Wed")

    def test_command_macro_receives_visible_values_and_now(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            script = os.path.join(tmpdir, "probe.sh")
            with open(script, "w", encoding="utf-8") as fh:
                fh.write("#!/bin/sh\n")
                fh.write("env | sort\n")
            os.chmod(script, 0o755)

            scope = MacroScope()
            scope.define("WORKDAY", "Mon")
            scope.define("GREETING", f"! {script}", command=True)

            value = scope.resolve("GREETING", now=dt.datetime(2026, 10, 9, 12, 0, tzinfo=dt.timezone.utc))
            self.assertIn("KAIROS_MACRO_WORKDAY=Mon", value)
            self.assertIn("KAIROS_NOW=2026-10-09T12:00:00+00:00", value)

    def test_suppressed_commands_raise_but_strings_and_cached_values_still_resolve(self) -> None:
        scope = MacroScope()
        scope.define("S", "Mon")
        scope.define("C", "! echo Tue", command=True)
        self.assertEqual(scope.resolve("S", allow_run=False), "Mon")
        with self.assertRaises(CommandNotRun):
            scope.resolve("C", allow_run=False)
        self.assertEqual(scope.resolve("C"), "Tue")  # runs and caches
        self.assertEqual(scope.resolve("C", allow_run=False), "Tue")

    def test_a_string_macro_that_needs_a_suppressed_command_is_suppressed_too(self) -> None:
        scope = MacroScope()
        scope.define("C", "! echo Tue", command=True)
        scope.define("S", "C 08:00")
        with self.assertRaises(CommandNotRun):
            scope.expand("S", allow_run=False)
        self.assertEqual(scope.expand("S"), "Tue 08:00")

    def test_a_command_runs_once_even_when_used_from_several_scopes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            counter = os.path.join(tmpdir, "count")
            root = MacroScope()
            root.define("C", f"! echo x >> '{counter}'; echo Tue", command=True)
            first, second = MacroScope(parent=root), MacroScope(parent=root)
            self.assertEqual(first.expand("C"), "Tue")
            self.assertEqual(second.expand("C"), "Tue")
            self.assertEqual(root.expand("C"), "Tue")
            with open(counter, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "x\n")

    def test_a_string_macro_only_expands_names_visible_where_it_was_defined(self) -> None:
        scope = MacroScope()
        scope.define("B", "A or Mon")  # A does not exist yet
        scope.define("A", "Tue")
        self.assertEqual(scope.expand("B"), "A or Mon")
        self.assertEqual(scope.expand("A"), "Tue")

    def test_macro_environment_uses_the_exact_name_and_only_earlier_macros(self) -> None:
        scope = MacroScope()
        scope.define("a", "lower")
        scope.define("A", "UPPER")
        scope.define("E", "! env", command=True)
        scope.define("late", "defined afterwards")
        env = scope.resolve("E").split(" ")
        self.assertIn("KAIROS_MACRO_a=lower", env)
        self.assertIn("KAIROS_MACRO_A=UPPER", env)
        self.assertFalse(any(item.startswith("KAIROS_MACRO_late=") for item in env))

    def test_failed_command_reports_the_macro_and_status(self) -> None:
        scope = MacroScope()
        scope.define("X", "! exit 3", command=True, lineno=7)
        with self.assertRaises(IntervalKeeperError) as caught:
            scope.resolve("X")
        self.assertEqual(caught.exception.line, 7)
        self.assertIn("'X'", caught.exception.message)
        self.assertIn("3", caught.exception.message)


if __name__ == "__main__":
    unittest.main()
