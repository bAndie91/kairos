"""Resolve documented time-zone tokens using Python's IANA zoneinfo data.

Accepted forms are IANA zone IDs (case-insensitive), UTC/GMT-prefixed numeric
offsets, and UTC/GMT/Z. Bare alphabetic abbreviations such as CST and CEST are
intentionally rejected because they are not globally unique identifiers.

To inspect available zone IDs:
    python3 -c 'from zoneinfo import available_timezones; print("\\n".join(sorted(available_timezones())))'
To inspect the abbreviation in effect for a chosen zone and instant:
    python3 -c 'from datetime import datetime; from zoneinfo import ZoneInfo; print(datetime(2026, 7, 1, tzinfo=ZoneInfo("Europe/Berlin")).tzname())'

ZoneInfo uses the system IANA time-zone database and Python's tzdata package
when available as a fallback. Kairos does not maintain an abbreviation map.
"""
from __future__ import annotations

import functools
import os
import re
import struct
import sys
from datetime import datetime, timedelta, timezone, tzinfo
from typing import Mapping, Optional, TextIO, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

from .errors import IntervalKeeperError


_OFFSET_RE = re.compile(r"^(?:UTC|GMT)([+-])(\d{1,2})(?::?(\d{2}))?$", re.IGNORECASE)


@functools.lru_cache(maxsize=1)
def _zone_index() -> Mapping[str, str]:
    """Casefolded IANA zone ID -> canonical ID (available_timezones() is slow, so cache it)."""
    return {name.casefold(): name for name in available_timezones()}


def zone_id_exists(token: str) -> bool:
    """True if *token* is an IANA zone ID (case-insensitive), e.g. ``Europe/Berlin`` or ``CET``."""
    return token.casefold() in _zone_index()


def resolve_tz(token: str, *, when: datetime | None = None, stderr: TextIO | None = None) -> tzinfo:
    """Resolve an accepted time-zone token or raise a user-facing error."""
    raw = (token or "").strip()
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
        if hours > 23 or minutes > 59:
            raise IntervalKeeperError(None, None, f"invalid time-zone offset {raw!r}")
        delta = timedelta(hours=hours, minutes=minutes)
        if sign == "-":
            delta = -delta
        return timezone(delta, name=raw)

    canonical = _zone_index().get(raw.casefold())
    if canonical is None:
        if raw.isalpha():
            raise IntervalKeeperError(
                None,
                None,
                f"unsupported alphabetic time-zone abbreviation {raw!r}; use an IANA zone ID or numeric UTC offset",
            )
        raise IntervalKeeperError(None, None, f"unknown IANA time-zone ID {raw!r}")

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
    """Resolve --tz, then $TZ, then the system zone, falling back to UTC."""
    environ = os.environ if env is None else env
    error_stream = sys.stderr if stderr is None else stderr

    if explicit is not None:
        value = explicit.strip()
        if value:
            return resolve_tz(value, stderr=error_stream)

    env_zone = environ.get("TZ", "").strip()
    if env_zone:
        return resolve_tz(env_zone, stderr=error_stream)

    try:
        from tzlocal import get_localzone  # type: ignore[import-not-found]
        zone = get_localzone()
        if zone is not None:
            return zone
    except Exception:
        pass

    print("kairos: warning: could not determine system time zone; using UTC", file=error_stream)
    return timezone.utc


__all__ = ["default_timezone", "recurrence_start", "resolve_tz", "rules_start", "zone_id_exists"]

# --- zone recurrence (SPEC §10.1) ---------------------------------------------------------

_CONSERVATIVE_RULES_START = 4_102_444_800  # 2100-01-01 UTC: used when a zone's TZif file cannot be read


def _tzif_bytes(key: str) -> Optional[bytes]:
    import zoneinfo

    for base in zoneinfo.TZPATH:
        path = os.path.join(base, *key.split("/"))
        if os.path.isfile(path):
            with open(path, "rb") as handle:
                return handle.read()
    try:  # the optional ``tzdata`` package, used when the system has no zoneinfo database
        from importlib import resources

        package, _, name = key.rpartition("/")
        resource = resources.files("tzdata.zoneinfo" + ("." + package.replace("/", ".") if package else "")) / name
        return resource.read_bytes()
    except (ImportError, OSError, ValueError, AttributeError):
        return None


def _last_transition(data: bytes) -> Optional[int]:
    """Last explicit transition time (POSIX seconds) of a TZif file; None if it has none.

    Only the recurrence metadata is read here; every wall-clock/instant conversion
    still goes through ``zoneinfo``. After this instant the zone follows the TZif
    footer's recurring POSIX rule, or its final fixed offset if the footer has no rule.
    """
    if data[:4] != b"TZif":
        raise ValueError("not a TZif file")
    version = data[4:5]

    def counts(offset: int) -> Tuple[int, ...]:
        return struct.unpack(">6l", data[offset + 20:offset + 44])

    isutcnt, isstdcnt, leapcnt, timecnt, typecnt, charcnt = counts(0)
    if version >= b"2":
        v1_size = timecnt * 4 + timecnt + typecnt * 6 + charcnt + leapcnt * 8 + isstdcnt + isutcnt
        offset = 44 + v1_size
        isutcnt, isstdcnt, leapcnt, timecnt, typecnt, charcnt = counts(offset)
        times_at, width, fmt = offset + 44, 8, ">q"
    else:
        times_at, width, fmt = 44, 4, ">l"
    if timecnt == 0:
        return None
    last_at = times_at + (timecnt - 1) * width
    return struct.unpack(fmt, data[last_at:last_at + width])[0]


@functools.lru_cache(maxsize=None)
def rules_start(key: str) -> int:
    """First instant from which zone *key* is governed only by its recurring rule.

    This is the last explicit TZif transition plus one year of margin; zones without
    transitions (fixed offsets, ``UTC``) return 0. A zone whose file cannot be read
    conservatively returns 2100-01-01.
    """
    try:
        data = _tzif_bytes(key)
        if data is None:
            return _CONSERVATIVE_RULES_START
        last = _last_transition(data)
    except (ValueError, struct.error, OSError):
        return _CONSERVATIVE_RULES_START
    return 0 if last is None else last + 366 * 86400


def recurrence_start(zone: "tzinfo") -> int:
    """:func:`rules_start` for a tzinfo (0 for fixed offsets and other non-IANA zones)."""
    key = getattr(zone, "key", None)
    return rules_start(key) if isinstance(key, str) else 0

