"""The default config text (SPEC §3.3, PLAN M9) and the stderr text of every V12 error."""
from __future__ import annotations

import os
import re
import tempfile
import unittest
from pathlib import Path

from helpers import make_ncal_stub, run_cli
from kairoslib.defaults import DEFAULT_CONFIG
from kairoslib.reader import read_config

TZ = "Europe/Budapest"


def examples_block(text: str) -> list[str]:
    """Lines after the EXAMPLES banner: ``# `` + config line, ``## `` prose, or blank."""
    lines = text.splitlines()
    marker = next(i for i, line in enumerate(lines) if line == "## EXAMPLES")
    return lines[marker + 1:]


def example_config(text: str = DEFAULT_CONFIG) -> str:
    out = []
    for line in examples_block(text):
        if line.startswith("## ") or line in ("", "##"):
            continue
        assert line.startswith("# "), f"example line without the '# ' prefix: {line!r}"
        out.append(line[2:])
    return "\n".join(out) + "\n"


class Structure(unittest.TestCase):
    def test_no_active_lines(self) -> None:
        for number, line in enumerate(DEFAULT_CONFIG.splitlines(), 1):
            self.assertTrue(line == "" or line.lstrip().startswith("#"), f"line {number}: {line!r}")
        self.assertEqual(read_config(DEFAULT_CONFIG, "default"), [])
        self.assertTrue(DEFAULT_CONFIG.endswith("\n"))

    def test_documentation_lines_are_all_prose_comments(self) -> None:
        lines = DEFAULT_CONFIG.splitlines()
        marker = lines.index("## EXAMPLES")
        for number, line in enumerate(lines[:marker], 1):
            self.assertTrue(line == "" or line.startswith("##"), f"line {number}: {line!r}")

    def test_example_lines_have_the_documented_shape(self) -> None:
        for line in examples_block(DEFAULT_CONFIG):
            self.assertTrue(line == "" or line.startswith("# ") or line.startswith("##"), repr(line))
            self.assertNotIn("\t", line)
        stripped = example_config()
        self.assertTrue(stripped.splitlines()[0][0] != " ", "the first example line must not be indented")

    def test_the_documentation_covers_every_feature(self) -> None:
        for needle in (
            "INDENTATION", "STATE", "INTERVAL: ONE CLAUSE", "INTERVAL: SPANS", "INTERVAL: RELATIVE", "INTERVAL: TIME ZONES",
            "MACROS", "SECURITY", "D before ANCHOR", "D after ANCHOR", "D until ANCHOR", "ANCHOR + D", "Mary's birthday",
            "LC_TIME", "LC_ALL", "KAIROS_NOW", "KAIROS_MACRO_", "KAIROS_INTERVAL_", "UTC+0300", "HOUR", "MINUTE",
            '# Easter := ! date -d "$(ncal -e)" +%F', "--check", "--format iso",
        ):
            self.assertIn(needle, DEFAULT_CONFIG)


class EndToEnd(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        make_ncal_stub(self.temp.name)
        self.env = {"PATH": f"{self.temp.name}{os.pathsep}{os.environ['PATH']}"}

    def run_cli(self, args, config):
        return run_cli(["--config", "-", "--tz", TZ, *args], config_text=config, env=self.env)

    def test_examples_pass_check(self) -> None:
        code, out, err = self.run_cli(["--check"], example_config())
        self.assertEqual((code, out, err), (0, "", ""))

    def test_the_whole_default_text_passes_check(self) -> None:
        code, out, err = self.run_cli(["--check"], DEFAULT_CONFIG)
        self.assertEqual((code, out, err), (0, "", ""))

    def test_print_default_config_equals_the_file_created_on_first_run(self) -> None:
        code, printed, err = run_cli(["--print-default-config"])
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(printed, DEFAULT_CONFIG)
        with tempfile.TemporaryDirectory() as home:
            env = {"HOME": home, "XDG_CONFIG_HOME": "", "XDG_CONFIG_DIRS": ""}
            code, out, err = run_cli(["--tz", "UTC", "--at", "2026-10-09 10:00"], env=env)
            self.assertEqual((code, out), (0, ""))
            self.assertIn("created default config", err)
            created = Path(home, ".config", "kairos", "intervals.conf").read_text(encoding="utf-8")
        self.assertEqual(created, printed)

    def test_the_default_config_itself_reports_nothing(self) -> None:
        code, out, _ = self.run_cli(["--at", "2026-10-09 12:00"], DEFAULT_CONFIG)
        self.assertEqual((code, out), (0, ""))

    def states(self, at: str) -> list[str]:
        code, out, err = self.run_cli(["--at", at], example_config())
        self.assertEqual((code, err), (0, ""), err)
        return out.splitlines()

    def test_documented_examples_behave_as_described(self) -> None:
        cases = [
            # (instant, states that must be active, states that must not be)
            ("2026-10-09 09:00", ["work", "weekday, outside lunch", "at work", "working week of the month"], ["lunch", "night"]),
            ("2026-10-09 12:30", ["work", "lunch", "at work"], ["weekday, outside lunch"]),
            ("2026-10-10 02:00", ["night"], ["work"]),
            ("2027-01-05 12:00", ["winter", "holidays"], ["night"]),
            ("2026-07-05 21:00", ["summer", "evening in summer's Sundays"], ["Sunday"]),
            ("2026-07-05 19:00", ["summer"], ["evening in summer's Sundays", "Sunday"]),
            ("2026-10-01 12:00", ["first of the month", "first of the month, on a weekday"], ["first Friday"]),
            ("2026-11-01 12:00", ["first of the month"], ["first of the month, on a weekday"]),
            ("2026-10-02 12:00", ["first Friday"], []),
            ("2026-12-25 12:00", ["Christmas"], ["Christmas run-up"]),  # the run-up ends with Dec 24
            ("2026-12-24 12:00", ["Christmas 2026", "Christmas run-up"], ["Christmas"]),
            ("2026-11-14 12:00", ["start of the run-up"], ["Christmas run-up"]),
            ("2026-11-15 12:00", ["Christmas run-up"], ["start of the run-up"]),
            ("2026-10-11 12:00", ["Oct 11, by arithmetic"], []),
            ("2026-04-08 12:00", ["Apr 8 and Oct 4"], []),
            ("2026-10-04 12:00", ["Apr 8 and Oct 4"], []),
            ("2026-04-09 12:00", [], ["Apr 8 and Oct 4"]),
            ("2026-04-10 12:00", ["project phase", "spring season"], []),
            ("2026-03-29 12:00", ["release day, working hours"], []),
            ("2026-03-29 18:00", [], ["release day, working hours"]),
            ("2026-10-12 08:00", ["shifts"], []),   # Monday morning
            ("2026-10-14 08:00", ["shifts"], []),   # Wednesday morning
            ("2026-10-09 14:00", ["shifts"], []),   # Friday afternoon
            ("2026-10-09 09:00", [], ["shifts"]),   # Friday morning
            ("2026-10-09 08:30", ["hour 8"], []),
            ("2026-10-09 09:30", ["half past, in the morning"], ["hour 8"]),
            ("2026-10-09 09:15", [], ["half past, in the morning"]),
            ("2026-07-01 08:30", ["Berlin office, July mornings"], []),
            ("2026-10-09 07:30", ["stand-up"], []),  # 07:30 CEST is 08:30 at UTC+03:00
            ("2026-06-14 12:00", ["Mary is celebrating"], []),
            ("2026-01-15 09:00", ["first quarter mornings"], []),
            ("2026-04-03 12:00", ["Good Friday"], ["Easter Sunday"]),
            ("2026-04-05 12:00", ["Easter Sunday"], ["Good Friday", "Easter Monday"]),
            ("2026-04-06 12:00", ["Easter Monday"], []),
            ("2026-05-24 12:00", ["Pentecost"], []),
            ("2026-12-10 12:00", ["December of the current year"], []),
            ("2026-10-09 12:00", [], ["December of the current year"]),
        ]
        for at, present, absent in cases:
            with self.subTest(at=at):
                got = self.states(at)
                for name in present:
                    self.assertIn(name, got, f"{name!r} should be active at {at}: {got}")
                for name in absent:
                    self.assertNotIn(name, got, f"{name!r} should not be active at {at}: {got}")


# V12: every one is an error: exit 2, empty stdout, "kairos: FILE:LINE: error: MESSAGE" naming the token.
V12 = [
    ("08:00-25:00 = x\n", 1, "25:00"),
    ("Mon Tue = x\n", 1, "Tue"),
    ("Foo = x\n", 1, "Foo"),
    ("Mon = ~\n", 1, "~"),
    ("  Mon = x\n", 1, "indented"),
    ("Mon := x\n", 1, "Mon"),
    ("7 := x\n", 1, "7"),
    ("Q := Jan\nQ := Jan\n", 2, "Q"),
    ("Feb 30 = x\n", 1, "Feb 30"),
    ("2026-02-29 = x\n", 1, "2026-02-29"),
    ("Mon =\n", 1, "STATE"),
    ("= x\n", 1, "INTERVAL"),
    ("X := ! false\nX = x\n", 1, "X"),
    ("08:00-08:00 = x\n", 1, "08:00-08:00"),
    ("Mon Foo/Bar = x\n", 1, "Foo/Bar"),
]


class V12Messages(unittest.TestCase):
    def test_every_error_names_file_line_and_token(self) -> None:
        for config, line, token in V12:
            with self.subTest(config=config), tempfile.TemporaryDirectory() as directory:
                path = Path(directory, "bad.conf")
                path.write_text(config, encoding="utf-8")
                code, out, err = run_cli(["--config", str(path), "--tz", "UTC", "--at", "2026-10-09 10:00"])
                self.assertEqual((code, out), (2, ""))
                match = re.fullmatch(r"kairos: (.+):(\d+): error: (.+)\n", err)
                self.assertIsNotNone(match, err)
                self.assertEqual((match.group(1), int(match.group(2))), (str(path), line), err)
                self.assertIn(token, match.group(3), err)
                self.assertEqual(err.count("\n"), 1, err)  # one diagnostic, no traceback


if __name__ == "__main__":
    unittest.main()
