"""Locale-aware month and weekday names (SPEC §11, §12, V15, PLAN M10)."""
from __future__ import annotations

import locale
import re
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from helpers import ROOT, run_cli
from kairoslib import names
from kairoslib.errors import IntervalKeeperError
from kairoslib.lexer import is_reserved_word, tokenize
from kairoslib.macros import validate_macro_name
from kairoslib.parser import Clause, Span, parse_interval

HU, FR, DE = "hu_HU.UTF-8", "fr_FR.UTF-8", "de_DE.UTF-8"


def installed(name: str) -> bool:
    try:
        names.use_locale(name)
    except locale.Error:
        return False
    finally:
        names.use_locale("C")
    return True


@contextmanager
def using(name: str):
    try:
        names.use_locale(name)
    except locale.Error:
        raise unittest.SkipTest(f"locale {name} is not installed")
    try:
        yield
    finally:
        names.use_locale("C")


def months(text: str):
    (clause,) = parse_interval(text).terms
    return clause.months, clause.doms, clause.weekdays


class CLocale(unittest.TestCase):
    def test_c_locale_names_come_from_the_library(self) -> None:
        self.assertEqual(months("Mar 15"), (((3, 3),), ((15, 15),), ()))
        self.assertEqual(months("march 15")[0], ((3, 3),))
        self.assertEqual(months("MON-FRI")[2], ((0, 4),))
        self.assertEqual(months("sunday")[2], ((6, 6),))
        self.assertEqual(months("Dec-Feb")[0], ((12, 2),))

    def test_no_hand_written_aliases(self) -> None:
        for word in ("Sept", "Tues", "Thur", "Thurs", "március", "hétfő"):
            with self.subTest(word=word), self.assertRaises(IntervalKeeperError) as ctx:
                parse_interval(word)
            self.assertIn("unknown word", ctx.exception.message)

    def test_reserved_words_follow_the_locale(self) -> None:
        self.assertTrue(is_reserved_word("Mar"))
        self.assertTrue(is_reserved_word("sunday"))
        self.assertFalse(is_reserved_word("március"))
        with self.assertRaises(IntervalKeeperError):
            validate_macro_name("Mar")
        validate_macro_name("március")

    def test_no_english_calendar_name_is_written_in_the_source(self) -> None:
        """No executable string literal under kairoslib/ may be a month or weekday name."""
        import ast

        forbidden = {
            "january", "february", "march", "april", "may", "june", "july", "august", "september",
            "october", "november", "december", "monday", "tuesday", "wednesday", "thursday", "friday",
            "saturday", "sunday", "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct",
            "nov", "dec", "mon", "tue", "tues", "wed", "thu", "thur", "thurs", "fri", "sat", "sun",
        }
        offenders = []
        for path in sorted(Path(ROOT, "kairoslib").glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            docstrings = {
                id(node.body[0].value)
                for node in ast.walk(tree)
                if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                and node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant)
            }
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
                    if node.value.strip().casefold() in forbidden:
                        offenders.append(f"{path.name}:{node.lineno}: {node.value!r}")
        self.assertEqual(offenders, [])


class HungarianLocale(unittest.TestCase):
    def test_names_and_forms(self) -> None:
        with using(HU):
            self.assertEqual(months("március 15"), (((3, 3),), ((15, 15),), ()))
            self.assertEqual(months("márc 15")[0], ((3, 3),))
            self.assertEqual(months("MÁRCIUS 15")[0], ((3, 3),))
            self.assertEqual(months("jan-márc")[0], ((1, 3),))
            self.assertEqual(months("január,március")[0], ((1, 1), (3, 3)))
            self.assertEqual(months("hétfő-péntek")[2], ((0, 4),))
            self.assertEqual(months("h-p")[2], ((0, 4),))  # the locale's own abbreviations
            self.assertEqual([months(w)[2] for w in ("sze", "szo", "v")], [((2, 2),), ((5, 5),), ((6, 6),)])
            (span,) = parse_interval("márc 1 -- 20").terms
            self.assertIsInstance(span, Span)
            self.assertEqual((span.start.month, span.start.day, span.end.day), (3, 1, 20))

    def test_english_names_are_unknown_words(self) -> None:
        with using(HU):
            for text in ("Mar 15", "Mon", "Dec-Feb", "march"):
                with self.subTest(text=text), self.assertRaises(IntervalKeeperError) as ctx:
                    parse_interval(text)
                self.assertIn("unknown word", ctx.exception.message)

    def test_reserved_macro_names_follow_the_locale(self) -> None:
        with using(HU):
            with self.assertRaises(IntervalKeeperError):
                validate_macro_name("március")
            with self.assertRaises(IntervalKeeperError):
                validate_macro_name("hétfő")
            validate_macro_name("Mar")
        # and back in C the Hungarian name is just a word
        validate_macro_name("március")

    def test_lexer_cache_follows_locale_changes(self) -> None:
        tokenize("Mar")
        with using(HU):
            tokenize("március")
            with self.assertRaises(IntervalKeeperError):
                tokenize("Mar")
        tokenize("Mar")


class FrenchAndGerman(unittest.TestCase):
    def test_names_with_punctuation(self) -> None:
        with using(FR):
            self.assertEqual(months("janv. 5"), (((1, 1),), ((5, 5),), ()))
            self.assertEqual(months("lun.-ven.")[2], ((0, 4),))
            self.assertEqual(months("mars 3")[0], ((3, 3),))  # abbreviation equals the full name
            self.assertEqual(months("déc.-févr.")[0], ((12, 2),))
            self.assertEqual(months("DÉCEMBRE")[0], ((12, 12),))

    def test_german(self) -> None:
        with using(DE):
            self.assertEqual(months("Mär 5")[0], ((3, 3),))
            self.assertEqual(months("März 5")[0], ((3, 3),))
            self.assertEqual(months("Mo-Fr")[2], ((0, 4),))
            with self.assertRaises(IntervalKeeperError):
                parse_interval("Mon")


class AmbiguousNames(unittest.TestCase):
    def test_a_name_the_locale_gives_to_two_values_is_rejected(self) -> None:
        crafted = names._Tables(
            months={"jan": 1}, weekdays={"mon": 0}, ambiguous=frozenset({"xx"}),
            spellings=frozenset({"jan", "mon", "xx"}),
        )
        with mock.patch.object(names, "_tables", return_value=crafted), \
                mock.patch.object(names, "current_locale", return_value="crafted"):
            self.assertTrue(is_reserved_word("xx"))
            with self.assertRaises(IntervalKeeperError) as ctx:
                tokenize("xx")
            self.assertIn("ambiguous", ctx.exception.message)

    def test_real_tables_have_no_ambiguity_in_the_installed_locales(self) -> None:
        for name in ("C", HU, FR, DE):
            with self.subTest(locale=name):
                with using(name):
                    self.assertEqual(names._current().ambiguous, frozenset())


def cli(config: str, env: dict, at: str = "2026-03-15 12:00"):
    return run_cli(["--config", "-", "--tz", "UTC", "--at", at], config_text=config, env=env)


class EnvironmentPrecedence(unittest.TestCase):
    """V15: one subprocess per case, environment set before Python starts."""

    @staticmethod
    def need(*locales: str) -> None:
        for name in locales:
            if not installed(name):
                raise unittest.SkipTest(f"locale {name} is not installed")

    def accepts(self, config: str, env: dict) -> bool:
        code, out, err = cli(config, env)
        if code == 0:
            self.assertEqual(out, "x\n")
            return True
        self.assertEqual((code, out), (2, ""))
        self.assertIn("unknown word", err)
        return False

    def test_lang_selects_the_locale(self) -> None:
        self.need(HU)
        env = {"LANG": HU, "LC_TIME": None, "LC_ALL": None}
        self.assertTrue(self.accepts("március 15 = x\n", env))
        self.assertFalse(self.accepts("Mar 15 = x\n", env))
        self.assertTrue(self.accepts("vasárnap = x\n", env))  # 2026-03-15 is a Sunday
        self.assertFalse(self.accepts("Sun = x\n", env))

    def test_c_locale_is_english(self) -> None:
        env = {"LC_ALL": "C"}
        self.assertTrue(self.accepts("Mar 15 = x\n", env))
        self.assertTrue(self.accepts("Sunday = x\n", env))
        self.assertFalse(self.accepts("március 15 = x\n", env))

    def test_lc_time_beats_lang(self) -> None:
        self.need(HU, DE)
        env = {"LANG": HU, "LC_TIME": DE, "LC_ALL": None}
        self.assertTrue(self.accepts("März 15 = x\n", env))
        self.assertFalse(self.accepts("március 15 = x\n", env))

    def test_lc_all_beats_both(self) -> None:
        self.need(HU, DE, FR)
        env = {"LC_ALL": HU, "LANG": DE, "LC_TIME": FR}
        self.assertTrue(self.accepts("március 15 = x\n", env))
        self.assertFalse(self.accepts("März 15 = x\n", env))
        self.assertFalse(self.accepts("mars 15 = x\n", env))

    def test_en_us_when_installed(self) -> None:
        self.need("en_US.UTF-8")
        env = {"LANG": "en_US.UTF-8", "LC_TIME": None, "LC_ALL": None}
        self.assertTrue(self.accepts("Mar 15 = x\n", env))
        self.assertFalse(self.accepts("március 15 = x\n", env))

    def test_macros_and_lists_use_the_locale(self) -> None:
        self.need(HU)
        env = {"LC_ALL": HU}
        self.assertTrue(self.accepts("Early := március\nEarly 15 = x\n", env))
        self.assertTrue(self.accepts("jan,márc 10-20 = x\n", env))
        self.assertTrue(self.accepts("hétfő-vasárnap = x\n", env))
        self.assertFalse(self.accepts("Mon-Sun = x\n", env))
        code, _out, err = cli("március := 3\n", env)
        self.assertEqual(code, 2)
        self.assertIn("reserved", err)

    def test_unavailable_locale_warns_and_continues(self) -> None:
        env = {"LC_ALL": "xx_XX.UTF-8"}
        code, out, err = cli("Mar 15 = x\n", env)
        self.assertEqual((code, out), (0, "x\n"))
        self.assertIn("warning", err)
        self.assertIn("locale", err)


if __name__ == "__main__":
    unittest.main()
