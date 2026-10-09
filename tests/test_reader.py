"""Tests for config line reading and indentation-tree construction."""
from __future__ import annotations

import unittest

from kairoslib.errors import IntervalKeeperError
from kairoslib.reader import MacroLine, Node, read_config


class ReaderTests(unittest.TestCase):
    def test_first_equals_splits_state_only_once(self) -> None:
        node = read_config("Mon = a=b # literal\n")[0]
        self.assertIsInstance(node, Node)
        self.assertEqual(node.interval_text, "Mon")
        self.assertEqual(node.effective_name, "a=b # literal")

    def test_indentation_creates_tree(self) -> None:
        roots = read_config("Mon = parent\n  Tue = child\n    Wed\n  Thu = sibling\n")
        parent = roots[0]
        self.assertEqual(len(parent.children), 2)
        self.assertEqual(parent.children[0].effective_name, "child")
        self.assertEqual(len(parent.children[0].children), 1)

    def test_tabs_or_spaces_allowed_but_mixing_is_error(self) -> None:
        self.assertEqual(len(read_config("Mon\n\tTue\n")), 1)
        with self.assertRaises(IntervalKeeperError):
            read_config("Mon\n \tTue\n")

    def test_first_line_cannot_be_indented(self) -> None:
        with self.assertRaises(IntervalKeeperError):
            read_config("  Mon = state\n")

    def test_dedent_must_match_open_level(self) -> None:
        with self.assertRaises(IntervalKeeperError):
            read_config("Mon\n    Tue\n  Wed\n")

    def test_macro_lines_are_classified_before_intervals(self) -> None:
        entries = read_config("DAYS := Mon-Fri\nDAYS = weekday\n")
        self.assertIsInstance(entries[0], MacroLine)
        self.assertEqual(entries[0].name, "DAYS")

    def test_macro_cannot_have_children(self) -> None:
        with self.assertRaises(IntervalKeeperError):
            read_config("DAYS := Mon-Fri\n  Tue = child\n")

    def test_state_parent_substitution_and_hidden_names(self) -> None:
        roots = read_config("Mon = parent\n  Tue = @ internal\n    Wed = child ~\n")
        hidden = roots[0].children[0]
        self.assertFalse(hidden.reported)
        self.assertEqual(hidden.effective_name, "internal")
        self.assertEqual(hidden.children[0].effective_name, "child internal")

    def test_escaped_tilde_and_at_are_literals(self) -> None:
        roots = read_config(r"Mon = \~literal" + "\n" + r"Tue = \@visible" + "\n")
        self.assertEqual(roots[0].effective_name, "~literal")
        self.assertTrue(roots[0].reported)
        self.assertEqual(roots[1].effective_name, "@visible")
        self.assertTrue(roots[1].reported)

    def test_tilde_requires_state_ancestor(self) -> None:
        with self.assertRaises(IntervalKeeperError):
            read_config("Mon\n  Tue = ~oops\n")

    def test_bare_hidden_marker_is_error(self) -> None:
        with self.assertRaises(IntervalKeeperError):
            read_config("Mon = @\n")

    def test_unknown_escape_is_error(self) -> None:
        with self.assertRaises(IntervalKeeperError):
            read_config(r"Mon = \q" + "\n")


if __name__ == "__main__":
    unittest.main()
