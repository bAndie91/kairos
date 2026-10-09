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

    def test_utc_offset_uses_iso_sign(self) -> None:
        zone = resolve_tz("UTC+0300")
        self.assertEqual(datetime(2026, 10, 9, 8, tzinfo=zone).utcoffset(), timedelta(hours=3))
        self.assertEqual(datetime(2026, 10, 9, 8, tzinfo=resolve_tz("GMT-4:30")).utcoffset(), -timedelta(hours=4, minutes=30))

    def test_offset_validation(self) -> None:
        for token in ("UTC+3:99", "GMT+24", "UTC-23:30"):
            with self.subTest(token=token), self.assertRaises(IntervalKeeperError):
                resolve_tz(token)

    def test_abbreviations_resolve_to_dst_zones(self) -> None:
        berlin = resolve_tz("CEST")
        self.assertEqual(berlin, ZoneInfo("Europe/Berlin"))
        self.assertEqual(datetime(2026, 12, 1, tzinfo=berlin).utcoffset(), timedelta(hours=1))
        self.assertEqual(datetime(2026, 7, 1, tzinfo=berlin).utcoffset(), timedelta(hours=2))

    def test_misplaced_summer_abbreviation_warns_when_date_is_given(self) -> None:
        stream = io.StringIO()
        resolve_tz("CEST", when=datetime(2026, 12, 1), stderr=stream)
        self.assertIn("warning", stream.getvalue())
        self.assertIn("CET", stream.getvalue())

    def test_unknown_ambiguous_abbreviation_errors(self) -> None:
        with self.assertRaisesRegex(IntervalKeeperError, "unknown time zone"):
            resolve_tz("IST")

    def test_default_precedence(self) -> None:
        zone = default_timezone("Europe/Budapest", env={"TZ": "UTC"})
        self.assertEqual(zone, ZoneInfo("Europe/Budapest"))
        zone = default_timezone(env={"TZ": "UTC"})
        self.assertEqual(zone, timezone.utc)

    def test_missing_system_zone_falls_back_with_warning(self) -> None:
        stream = io.StringIO()
        zone = default_timezone(env={}, stderr=stream)
        self.assertEqual(zone, timezone.utc)
        # If tzlocal is installed, the system zone is returned instead.
        if stream.getvalue():
            self.assertIn("warning", stream.getvalue())


if __name__ == "__main__":
    unittest.main()
