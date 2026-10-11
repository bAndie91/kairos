"""stderr text of every V12 error: file, line and the offending token (PLAN M9)."""
from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from helpers import run_cli

# V12: each is an error: exit 2, empty stdout, "kairos: FILE:LINE: error: MESSAGE" naming the token.
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
