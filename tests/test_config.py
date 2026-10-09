"""Tests for XDG configuration discovery and default creation."""
from __future__ import annotations

import io
import os
import tempfile
import unittest
from pathlib import Path

from kairoslib.config import load_config
from kairoslib.defaults import DEFAULT_CONFIG
from kairoslib.errors import IntervalKeeperError


class ConfigDiscoveryTests(unittest.TestCase):
    def test_user_config_precedes_system_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            user = root / "user" / "kairos" / "intervals.conf"
            system = root / "system" / "kairos" / "intervals.conf"
            user.parent.mkdir(parents=True)
            system.parent.mkdir(parents=True)
            user.write_text("user config\n", encoding="utf-8")
            system.write_text("system config\n", encoding="utf-8")
            path, text = load_config(None, env={
                "XDG_CONFIG_HOME": str(root / "user"),
                "XDG_CONFIG_DIRS": str(root / "system"),
                "HOME": str(root / "home"),
            }, stderr=io.StringIO())
            self.assertEqual(path, str(user))
            self.assertEqual(text, "user config\n")

    def test_system_dirs_are_searched_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first, second = root / "first", root / "second"
            for directory, text in ((first, "first"), (second, "second")):
                target = directory / "kairos" / "intervals.conf"
                target.parent.mkdir(parents=True)
                target.write_text(text, encoding="utf-8")
            _path, text = load_config(None, env={
                "XDG_CONFIG_HOME": str(root / "missing"),
                "XDG_CONFIG_DIRS": os.pathsep.join((str(first), str(second))),
            }, stderr=io.StringIO())
            self.assertEqual(text, "first")

    def test_relative_xdg_values_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / "home"
            stream = io.StringIO()
            path, text = load_config(None, env={
                "HOME": str(home),
                "XDG_CONFIG_HOME": "relative/config",
                "XDG_CONFIG_DIRS": os.pathsep.join(("relative/system", str(root / "system"))),
            }, stderr=stream)
            self.assertEqual(Path(path), home / ".config" / "kairos" / "intervals.conf")
            self.assertEqual(text, DEFAULT_CONFIG)
            self.assertIn("kairos: created default config:", stream.getvalue())

    def test_default_file_and_new_directory_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / "home"
            path, _text = load_config(None, env={
                "HOME": str(home),
                "XDG_CONFIG_DIRS": str(root / "empty-system"),
            }, stderr=io.StringIO())
            config_path = Path(path)
            self.assertEqual(stat_mode(config_path.parent), 0o700)
            self.assertEqual(stat_mode(config_path), 0o644)

    def test_explicit_missing_path_is_not_created(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            missing = Path(temp) / "missing.conf"
            with self.assertRaises(IntervalKeeperError):
                load_config(str(missing), env={"HOME": temp}, stderr=io.StringIO())
            self.assertFalse(missing.exists())

    def test_dash_reads_stdin(self) -> None:
        path, text = load_config("-", stdin=io.StringIO("Mon = work\n"), env={})
        self.assertEqual(path, "<stdin>")
        self.assertEqual(text, "Mon = work\n")


def stat_mode(path: Path) -> int:
    return path.stat().st_mode & 0o777


if __name__ == "__main__":
    unittest.main()
