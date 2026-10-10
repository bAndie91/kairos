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
        code, stdout, stderr = run_cli(
            ["--config", "-", "--tz", "UTC", "--at", "2026-10-09 10:00"],
            config_text="Fri = from stdin\n",
        )
        self.assertEqual(code, 0, stderr)
        self.assertEqual(stdout, "from stdin\n")
        self.assertEqual(stderr, "")

    def test_fresh_home_creates_default_config_and_prints_no_states(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            env = {"HOME": temp}
            for name in ("XDG_CONFIG_HOME", "XDG_CONFIG_DIRS"):
                env[name] = ""  # empty values count as unset
            code, stdout, stderr = run_cli(["--tz", "UTC", "--at", "2026-10-09 10:00"], env=env)
            created = Path(temp) / ".config" / "kairos" / "intervals.conf"
            self.assertEqual(code, 0, stderr)
            self.assertEqual(stdout, "")
            self.assertIn("created default config", stderr)
            self.assertTrue(created.is_file())

    def test_errors_in_config_name_the_file_and_line(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            conf = Path(temp) / "bad.conf"
            conf.write_text("Mon = ok\nFoo = bad\n", encoding="utf-8")
            code, stdout, stderr = run_cli(["--config", str(conf), "--tz", "UTC"])
            self.assertEqual(code, 2)
            self.assertEqual(stdout, "")
            self.assertIn(f"{conf}:2: error:", stderr)


if __name__ == "__main__":
    unittest.main()
