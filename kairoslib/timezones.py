"""Time-zone token and default-zone resolution (SPEC §8).

Abbreviation mappings intentionally name DST-observing IANA zones. The table
follows the mapping published in SPEC.md §8.2; use IANA names when ambiguity
matters. To inspect names available to this Python runtime, run:
    python3 -c 'from zoneinfo import available_timezones; print("\\n".join(sorted(available_timezones())))'
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone, tzinfo
import re
import sys
from typing import Mapping, TextIO
from zoneinfo import ZoneInfo, available_timezones, ZoneInfoNotFoundError

from .errors import IntervalKeeperError

ABBREVIATION_ZONES: dict[str, str] = {
    "CET": "Europe/Berlin",
    "CEST": "Europe/Berlin",
    "EET": "Europe/Helsinki",
    "EEST": "Europe/Helsinki",
    "WET": "Europe/Lisbon",
    "WEST": "Europe/Lisbon",
    "EST": "America/New_York",
    "EDT": "America/New_York",
    "CST": "America/Chicago",
    "CDT": "America/Chicago",
    "MST": "America/Denver",
    "MDT": "America/Denver",
    "PST": "America/Los_Angeles",
    "PDT": "America/Los_Angeles",
    "UTC": "UTC",
    "GMT": "UTC",
    "Z": "UTC",
}

_OFFSET_RE = re.compile(r"^(?:UTC|GMT)([+-])(\d{1,2})(?::?(\d{2}))?$", re.IGNORECASE)


def resolve_tz(token: str, *, when: datetime | None = None, stderr: TextIO | None = None) -> tzinfo:
    """Resolve an accepted time-zone token or raise a user-facing error."""
    raw = token.strip()
    if not raw:
        raise IntervalKeeperError(None, None, "time zone must not be empty")
    upper = raw.upper()

    match = _OFFSET_RE.fullmatch(raw)
    if match:
        sign, hour_text, minute_text = match.groups()
        hours = int(hour_text)
        minutes = int(minute_text or "0")
        if minutes > 59 or hours > 23:
            raise IntervalKeeperError(None, None, f"invalid time-zone offset {raw!r}")
        seconds = (hours * 60 + minutes) * 60
        if sign == "-":
            seconds = -seconds
        return timezone(timedelta(seconds=seconds), name=raw)

    if upper in ABBREVIATION_ZONES:
        zone_name = ABBREVIATION_ZONES[upper]
        zone = ZoneInfo(zone_name)
        if when is not None and upper not in {"UTC", "GMT", "Z"}:
            local = when.astimezone(zone) if when.tzinfo is not None else when.replace(tzinfo=zone)
            actual = local.tzname()
            if upper in {"CEST", "EEST", "WEST", "EDT", "CDT", "MDT", "PDT"} and actual != upper:
                print(f"kairos: warning: {upper} is not in effect at this date; {actual} applies in {zone_name}", file=stderr or sys.stderr)
            elif upper in {"CET", "EET", "WET", "EST", "CST", "MST", "PST"}:
                summer_name = {"CET": "CEST", "EET": "EEST", "WET": "WEST", "EST": "EDT", "CST": "CDT", "MST": "MDT", "PST": "PDT"}[upper]
                if actual == summer_name:
                    print(f"kairos: warning: {upper} is not in effect at this date; {actual} applies in {zone_name}", file=stderr or sys.stderr)
        return zone

    # IANA lookup is case-insensitive, but return the canonical database key.
    names = {name.casefold(): name for name in available_timezones()}
    canonical = names.get(raw.casefold())
    if canonical is None:
        raise IntervalKeeperError(None, None, f"unknown time zone {raw!r}; use an IANA name or supported abbreviation")
    try:
        return ZoneInfo(canonical)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise IntervalKeeperError(None, None, f"cannot load time zone {raw!r}: {exc}") from exc


def default_timezone(
    explicit: str | None = None,
    *,
    env: Mapping[str, str] | None = None,
    stderr: TextIO | None = None,
) -> tzinfo:
    """Resolve --tz, then TZ, then the system zone, falling back to UTC."""
    environ = __import__("os").environ if env is None else env
    if explicit:
        return resolve_tz(explicit, stderr=stderr)
    env_zone = environ.get("TZ")
    if env_zone:
        # POSIX TZ strings are not generally IANA identifiers; Kairos deliberately
        # accepts the documented IANA/offset/abbreviation vocabulary instead.
        return resolve_tz(env_zone, stderr=stderr)
    try:
        from tzlocal import get_localzone  # type: ignore[import-not-found]
        return get_localzone()
    except Exception:
        print("kairos: warning: could not determine system time zone; using UTC", file=stderr or sys.stderr)
        return timezone.utc
