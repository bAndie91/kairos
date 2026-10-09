"""Tests for Kairos time-zone resolution."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import io
import unittest
from zoneinfo import ZoneInfo

from kairoslib.errors import IntervalKeeperError
from kairoslib.timezones import default_timezone, resolve_tz


class TimezoneTests(unittest.TestCase):
    def test_iana_names_are_case_insensitive(self) -> None:
        self.assertEqual(resolve_tz("europe/budapest"), ZoneInfo("Europe/Budapest"))
        self.assertEqual(resolve_tz("Etc/UTC"), ZoneInfo("Etc/UTC"))

    def test_utc_aliases(self) -> None:
        for token in ("UTC", "utc", "GMT", "gmt", "Z", "z"):
            with self.subTest(token=token):
                self.assertEqual(resolve_tz(token), timezone.utc)

    def test_utc_offset_uses_iso_sign(self) -> None:
        zone = resolve_tz("UTC+0300")
        self.assertEqual(datetime(2026, 10, 9, 8, tzinfo=zone).utcoffset(), timedelta(hours=3))
        self.assertEqual(datetime(2026, 10, 9, 8, tzinfo=resolve_tz("GMT-4:30")).utcoffset(), -timedelta(hours=4, minutes=30))
        self.assertEqual(resolve_tz("UTC+3").utcoffset(None), timedelta(hours=3))
        self.assertEqual(resolve_tz("GMT+03:00").utcoffset(None), timedelta(hours=3))

    def test_offset_validation(self) -> None:
        for token in ("UTC+3:99", "GMT+24", "UTC-24"):
            with self.subTest(token=token), self.assertRaises(IntervalKeeperError):
                resolve_tz(token)

    def test_bare_abbreviations_are_rejected(self) -> None:
        for token in ("CEST", "CET", "CST", "IST", "EDT", "PST"):
            with self.subTest(token=token), self.assertRaisesRegex(IntervalKeeperError, "unsupported alphabetic time-zone abbreviation"):
                resolve_tz(token)

    def test_unknown_iana_zone_errors(self) -> None:
        with self.assertRaisesRegex(IntervalKeeperError, "unknown IANA time-zone ID"):
            resolve_tz("Foo/Bar")

    def test_default_precedence(self) -> None:
        zone = default_timezone("Europe/Budapest", env={"TZ": "UTC"})
        self.assertEqual(zone, ZoneInfo("Europe/Budapest"))
        self.assertEqual(default_timezone(env={"TZ": "UTC"}), timezone.utc)

    def test_missing_system_zone_falls_back_with_warning(self) -> None:
        stream = io.StringIO()
        zone = default_timezone(env={}, stderr=stream)
        if stream.getvalue():
            self.assertEqual(zone, timezone.utc)
            self.assertIn("warning", stream.getvalue())
        else:
            self.assertIsNotNone(zone)


if __name__ == "__main__":
    unittest.main()
