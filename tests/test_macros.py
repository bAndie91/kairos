"""Tests for macro name validation, expansion, and command execution."""
from __future__ import annotations

import datetime as dt
import os
import tempfile
import unittest

from kairoslib.errors import IntervalKeeperError
from kairoslib.macros import MacroScope, expand_macro_text, validate_macro_name


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


if __name__ == "__main__":
    unittest.main()
