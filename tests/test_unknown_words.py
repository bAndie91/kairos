"""Every unknown word is reported, with a "wrong locale?" hint (SPEC §6.2, PLAN M14)."""
from __future__ import annotations

import locale
import os
import stat
import tempfile
import unittest
from pathlib import Path

from helpers import run_cli
from kairoslib import names
from kairoslib.errors import ErrorList, IntervalKeeperError
from kairoslib.parser import parse_interval


def have(name: str) -> bool:
    saved = names.current_locale()
    try:
        names.use_locale(name)
    except locale.Error:
        return False
    finally:
        names.use_locale(saved)
    return True


def fake_locale_command(directory: str, listing: str) -> dict:
    """A directory with a `locale` program that prints *listing*, as the only PATH entry."""
    path = Path(directory) / "locale"
    path.write_text(f"#!/bin/sh\nprintf '%s\\n' {listing}\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return {"PATH": f"{directory}:/usr/bin:/bin"}


class CollectingUnknownWords(unittest.TestCase):
    def messages(self, text: str) -> list:
        with self.assertRaises(IntervalKeeperError) as caught:
            parse_interval(text, path="t", lineno=3)
        exc = caught.exception
        return [e.message for e in exc.errors] if isinstance(exc, ErrorList) else [exc.message]

    def test_one_unknown_word_stays_a_plain_error(self) -> None:
        with self.assertRaises(IntervalKeeperError) as caught:
            parse_interval("Foo Mon")
        self.assertNotIsInstance(caught.exception, ErrorList)
        self.assertIn("unknown word 'Foo'", caught.exception.message)

    def test_every_unknown_word_of_a_line_is_reported_in_order(self) -> None:
        messages = self.messages("Foo Mon Bar, Baz")
        self.assertEqual(len(messages), 3)
        for message, word in zip(messages, ("Foo", "Bar", "Baz")):
            self.assertIn(f"unknown word '{word}'", message)

    def test_diagnostics_carry_file_and_line(self) -> None:
        with self.assertRaises(ErrorList) as caught:
            parse_interval("Foo Bar", path="t.conf", lineno=7)
        self.assertEqual([(e.path, e.line) for e in caught.exception.errors], [("t.conf", 7)] * 2)

    def test_a_non_word_error_after_unknown_words_is_included(self) -> None:
        self.assertEqual(len(self.messages("Foo Bar @")), 3)

    def test_all_unknown_words_of_all_lines_in_one_run(self) -> None:
        config = "Foo = a\nMon Bar Baz = b\n  Quux = c\nTue = fine\n"
        code, out, err = run_cli(["--config", "-", "--check"], config)
        self.assertEqual((code, out), (2, ""))
        got = [line for line in err.splitlines() if "unknown word" in line]
        self.assertEqual(len(got), 4, err)
        for line, word, number in zip(got, ("Foo", "Bar", "Baz", "Quux"), (1, 2, 2, 3)):
            self.assertIn(f"<stdin>:{number}:", line)
            self.assertIn(f"'{word}'", line)

    def test_the_default_mode_reports_them_all_too(self) -> None:
        code, out, err = run_cli(["--config", "-", "--at", "2026-10-09 12:00", "--tz", "UTC"], "Foo Bar = a\n")
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(err.count("unknown word"), 2)


class WrongLocaleHint(unittest.TestCase):
    HU, EN = "hu_HU.UTF-8", "en_US.UTF-8"

    def setUp(self) -> None:
        if not (have(self.HU) and have(self.EN)):
            self.skipTest("hu_HU.UTF-8 / en_US.UTF-8 locales are not installed")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = fake_locale_command(self.tmp.name, f"C {self.HU} {self.EN}")

    def run_config(self, locale_name: str, config: str):
        env = {"LC_ALL": locale_name, **self.env}
        if os.environ.get("LOCPATH"):
            env["LOCPATH"] = os.environ["LOCPATH"]
        return run_cli(["--config", "-", "--check"], config, env=env)

    def test_an_english_name_in_a_hungarian_locale(self) -> None:
        code, _, err = self.run_config(self.HU, "May 5 = x\n")
        self.assertEqual(code, 2)
        self.assertIn(f'unknown word \'May\' (undefined macro? wrong locale? "May" is in "{self.EN}" locale)', err)

    def test_a_hungarian_name_in_an_english_locale(self) -> None:
        code, _, err = self.run_config(self.EN, "március 15 = x\n")
        self.assertEqual(code, 2)
        self.assertIn(f'wrong locale? "március" is in "{self.HU}" locale', err)

    def test_a_word_that_is_a_name_nowhere_has_no_hint(self) -> None:
        _, _, err = self.run_config(self.EN, "Foo 15 = x\n")
        self.assertIn("unknown word 'Foo' (undefined macro?)", err)
        self.assertNotIn("wrong locale", err)

    def test_the_effective_locale_is_untouched_by_the_search(self) -> None:
        # the word after the unknown one still parses in the effective locale
        code, out, err = self.run_config(self.EN, "március May = x\n")
        self.assertEqual(code, 2)
        self.assertEqual(err.count("unknown word"), 1, err)


class LocaleSearchInProcess(unittest.TestCase):
    def test_search_restores_the_effective_locale_and_skips_it(self) -> None:
        names._name_index.cache_clear()
        before = names.current_locale()
        with tempfile.TemporaryDirectory() as tmp:
            env = fake_locale_command(tmp, "C C.utf8 POSIX")
            old = os.environ["PATH"]
            os.environ["PATH"] = env["PATH"]
            try:
                found = names.locales_with_name("May")
            finally:
                os.environ["PATH"] = old
                names._name_index.cache_clear()
        self.assertEqual(names.current_locale(), before)
        self.assertNotIn(before, found)

    def test_a_missing_locale_command_gives_no_hint_and_no_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            old = os.environ["PATH"]
            os.environ["PATH"] = tmp  # nothing to run
            names._name_index.cache_clear()
            try:
                self.assertEqual(names.installed_locales(), [])
                self.assertEqual(names.locales_with_name("Foo"), [])
                with self.assertRaises(IntervalKeeperError) as caught:
                    parse_interval("Foo")
            finally:
                os.environ["PATH"] = old
                names._name_index.cache_clear()
        self.assertIn("unknown word 'Foo' (undefined macro?)", caught.exception.message)


if __name__ == "__main__":
    unittest.main()
