"""Tests for the default config text (SPEC §3.3, PLAN M9)."""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from helpers import make_ncal_stub, run_cli
from kairoslib.defaults import DEFAULT_CONFIG

_EXAMPLE_RE = re.compile(r"^#(?: (.*))?$")  # "#" or "# " + the original config line


def example_lines(text: str) -> list[str]:
    """The example config lines: strip "# ", ignore "## " prose lines."""
    lines = []
    for raw in text.splitlines():
        if raw.startswith("##"):
            continue
        match = _EXAMPLE_RE.match(raw)
        if match is None:
            raise AssertionError(f"line is neither prose ('## ') nor an example ('# '): {raw!r}")
        lines.append(match.group(1) or "")
    return lines


def _gnu_date_works() -> bool:
    try:
        done = subprocess.run(
            ["date", "-d", "04/05/26", "+%F"], capture_output=True, text=True, check=False
        )
    except OSError:
        return False
    return done.returncode == 0 and done.stdout.strip() == "2026-04-05"


class DefaultConfigTextTests(unittest.TestCase):
    def test_every_line_is_a_comment_so_a_fresh_config_is_inert(self) -> None:
        for number, line in enumerate(DEFAULT_CONFIG.splitlines(), 1):
            self.assertTrue(line.startswith("#"), f"line {number} is not a comment: {line!r}")
        self.assertTrue(DEFAULT_CONFIG.endswith("\n"))

    def test_fresh_default_config_checks_and_prints_nothing(self) -> None:
        code, stdout, stderr = run_cli(["--check", "--tz", "UTC", "--config", "-"], config_text=DEFAULT_CONFIG)
        self.assertEqual((code, stdout, stderr), (0, "", ""))

    def test_text_covers_the_required_topics(self) -> None:
        # The full reference moved to the man page; keep examples in the
        # generated config and verify both sources for their respective roles.
        manpage = (Path(__file__).resolve().parents[1] / "man" / "kairos.1").read_text(encoding="utf-8")
        for needle in (
            "DURATION before ANCHOR",
            "DURATION after ANCHOR",
            "Apr 1, 2 days before Apr 10",  # several parts in one INTERVAL
            "Mary's birthday",  # macro names with spaces and punctuation
            "LC_TIME",  # locale-dependent month and weekday names
            "SECURITY",  # macro commands run with the user's privileges
            "daemon or watch mode",  # out-of-scope points are documented (SPEC §1)
            "KAIROS_MACRO_<NAME>",
        ):
            self.assertIn(needle, manpage)
        self.assertIn('Easter := ! date -d "$(ncal -e)" +%F', DEFAULT_CONFIG)

    def test_examples_extraction_is_strict_and_nonempty(self) -> None:
        lines = example_lines(DEFAULT_CONFIG)
        self.assertGreater(len([line for line in lines if line.strip()]), 30)
        self.assertIn("Mon-Fri", lines)
        self.assertIn("  Dec = weekdays in December", lines)  # indentation survives
        with self.assertRaises(AssertionError):
            example_lines("#no-space-after-hash\n")


class DefaultConfigExamplesTests(unittest.TestCase):
    def setUp(self) -> None:
        if not _gnu_date_works():
            self.skipTest("GNU date (date -d MM/DD/YY) is required by the Easter example")
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        make_ncal_stub(self._temp.name)
        self.env = {"PATH": f"{self._temp.name}{os.pathsep}{os.environ.get('PATH', '')}"}
        self.config = "\n".join(example_lines(DEFAULT_CONFIG)) + "\n"

    def run_examples(self, *args: str) -> tuple[int, str, str]:
        return run_cli([*args, "--tz", "UTC", "--config", "-"], config_text=self.config, env=self.env)

    def test_examples_pass_check(self) -> None:
        code, stdout, stderr = self.run_examples("--check")
        self.assertEqual((code, stdout, stderr), (0, "", ""))

    def test_examples_work_through_the_fake_easter(self) -> None:
        # The stub prints 04/05/26, so Easter is 2026-04-05 and Holy Friday the 3rd.
        code, stdout, stderr = self.run_examples("--at", "2026-04-03 10:00")
        self.assertEqual(code, 0, stderr)
        self.assertIn("Good Friday\n", stdout)
        self.assertNotIn("Easter Sunday", stdout)
        code, stdout, stderr = self.run_examples("--at", "2026-04-05 10:00")
        self.assertEqual(code, 0, stderr)
        self.assertIn("Easter Sunday\n", stdout)
        self.assertIn("Easter weekend\n", stdout)

    def test_examples_follow_the_documented_semantics(self) -> None:
        # V5: ~ and @ (hidden "Sunday" is not reported, children see it as ~)
        code, stdout, stderr = self.run_examples("--at", "2026-07-05 21:00")
        self.assertEqual(code, 0, stderr)
        states = stdout.splitlines()
        self.assertIn("evening in summer's Sundays", states)
        self.assertIn("summer", states)
        self.assertNotIn("Sunday", states)
        # V6: negation under the 1st of the month; 2026-11-01 is a Sunday
        code, stdout, stderr = self.run_examples("--at", "2026-11-01 12:00")
        self.assertEqual(code, 0, stderr)
        self.assertIn("first of the month", stdout.splitlines())
        self.assertNotIn("first of the month, on a weekday", stdout.splitlines())

    def test_examples_also_work_with_next_change(self) -> None:
        code, stdout, stderr = self.run_examples("--next-change", "--at", "2026-10-09 07:59:00")
        self.assertEqual(code, 0, stderr)
        self.assertRegex(stdout, r"^2026-10-09 0[0-9]:[0-9]{2}:[0-9]{2}\n$")


class PrintDefaultConfigTests(unittest.TestCase):
    def test_print_default_config_equals_the_constant(self) -> None:
        code, stdout, stderr = run_cli(["--print-default-config"])
        self.assertEqual((code, stderr), (0, ""))
        self.assertEqual(stdout, DEFAULT_CONFIG)

    def test_created_file_equals_print_default_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            env = {"HOME": temp, "XDG_CONFIG_HOME": "", "XDG_CONFIG_DIRS": ""}
            code, stdout, stderr = run_cli(["--tz", "UTC", "--at", "2026-10-09 10:00"], env=env)
            self.assertEqual(code, 0, stderr)
            self.assertEqual(stdout, "")
            created = Path(temp) / ".config" / "kairos" / "intervals.conf"
            printed_code, printed, _ = run_cli(["--print-default-config"])
            self.assertEqual(printed_code, 0)
            self.assertEqual(created.read_text(encoding="utf-8"), printed)


if __name__ == "__main__":
    unittest.main()
