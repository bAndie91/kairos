"""CLI integration tests for configuration input handling."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from helpers import run_cli


class CliConfigTests(unittest.TestCase):
    def test_missing_explicit_config_fails_without_creating_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            missing = Path(temp) / "not-created.conf"
            code, stdout, stderr = run_cli(
                ["--config", str(missing)],
                env={"HOME": temp, "XDG_CONFIG_HOME": str(Path(temp) / "xdg")},
            )
            self.assertEqual(code, 2)
            self.assertEqual(stdout, "")
            self.assertIn("config file does not exist", stderr)
            self.assertFalse(missing.exists())

    def test_config_dash_reads_stdin(self) -> None:
        code, stdout, stderr = run_cli(["--config", "-"], config_text="# inert config\n")
        # Config discovery works; execution remains deliberately unimplemented
        # until parsing and evaluation milestones land.
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("not implemented", stderr)


if __name__ == "__main__":
    unittest.main()
