"""Bootstrap acceptance tests for the Kairos CLI."""
from __future__ import annotations

import unittest

from helpers import run_cli


class BootstrapCliTests(unittest.TestCase):
    def test_help_works_from_source_checkout(self) -> None:
        code, stdout, stderr = run_cli(["--help"])
        self.assertEqual(code, 0, stderr)
        self.assertIn("usage: kairos", stdout)
        self.assertEqual(stderr, "")

    def test_version_works(self) -> None:
        code, stdout, stderr = run_cli(["--version"])
        self.assertEqual(code, 0, stderr)
        self.assertIn("kairos 0.1.0", stdout)
        self.assertEqual(stderr, "")

    def test_unknown_option_has_empty_stdout(self) -> None:
        code, stdout, _stderr = run_cli(["--not-a-real-option"])
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")

    def test_bad_option_values_fail_before_the_config_is_read(self) -> None:
        for args in (["--at", "tomorrow"], ["--tz", "Mars/Olympus"], ["--tz", "CEST"]):
            with self.subTest(args=args):
                # A missing config would be a different error, so this also shows
                # the option is validated first.
                code, stdout, stderr = run_cli([*args, "--config", "/nonexistent/kairos.conf"])
                self.assertEqual(code, 2)
                self.assertEqual(stdout, "")
                self.assertNotIn("does not exist", stderr)


if __name__ == "__main__":
    unittest.main()
