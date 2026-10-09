"""Resolve documented time-zone tokens using Python's IANA zoneinfo data.

Accepted forms are IANA zone IDs (case-insensitive), UTC/GMT-prefixed numeric
offsets, and UTC/GMT/Z. Bare alphabetic abbreviations such as CST and CEST are
intentionally rejected because they are not globally unique identifiers.

To inspect available zone IDs:
    python3 -c 'from zoneinfo import available_timezones; print("\\n".join(sorted(available_timezones()))'
To inspect the abbreviation in effect for a chosen zone and instant:
    python3 -c 'from datetime import datetime; from zoneinfo import ZoneInfo; print(datetime(2026, 7, 1, tzinfo=ZoneInfo("Europe/Berlin")).tzname())'

ZoneInfo uses the system IANA time-zone database and Python's tzdata package
when available as a fallback. Kairos does not maintain an abbreviation map.
"""
from __future__ import annotations

from datetime import timedelta, timezone, tzinfo
import os
import re
import sys
from typing import Mapping, TextIO
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

from .errors import IntervalKeeperError


_OFFSET_RE = re.compile(r"^(?:UTC|GMT)([+-])(\\d{1,2})(?::?(\\d{2}))?$", re.IGNORECASE)


def resolve_tz(token: str, *, when=None, stderr: TextIO | None = None) -> tzinfo:
    """Resolve an accepted time-zone token or raise a user-facing error."""
    raw = token.strip()
    if not raw:
        raise IntervalKeeperError(None, None, "time zone must not be empty")
    upper = raw.upper()
    if upper in {"UTC", "GMT", "Z"}:
        return timezone.utc

    match = _OFFSET_RE.fullmatch(raw)
    if match:
        sign, hour_text, minute_text = match.groups()
        hours = int(hour_text)
        minutes = int(minute_text or "0")
        if minutes > 59 or hours > 23 or (hours == 23 and minutes != 0):
            raise IntervalKeeperError(None, None, f"invalid time-zone offset {raw!r}")
        seconds = (hours * 60 + minutes) * 60
        if sign == "-":
            seconds = -seconds
        return timezone(timedelta(seconds=seconds), name=raw)

    canonical = {name.casefold(): name for name in available_timezones()}.get(raw.casefold())
    if canonical is None:
        if raw.isalpha():
            raise IntervalKeeperError(None, None, f"unsupported alphabetic time-zone abbreviation {raw!r}; use an IANA zone ID or numeric UTC offset")
        raise IntervalKeeperError(None, None, f"unknown IANA time-zone ID {raw!r}")
    try:
        return ZoneInfo(canonical)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise IntervalKeeperError(None, None, f"cannot load time zone {raw!r}: {exc}") from exc


def default_timezone(explicit: str | None = None, *, env: Mapping[str, str] | None = None, stderr: TextIO | None = None) -> tzinfo:
    """Resolve --tz, then $TZ, then the system zone, falling back to UTC."""
    environ = os.environ if env is None else env
    if explicit:
        return resolve_tz(explicit, stderr=stderr)
    env_zone = environ.get("TZ")
    if env_zone:
        return resolve_tz(env_zone, stderr=stderr)
    try:
        from tzlocal import get_localzone  # type: ignore[import-not-found]
        return get_localzone()
    except Exception:
        print("kairos: warning: could not determine system time zone; using UTC", file=stderr or sys.stderr)
        return timezone.utc
