"""Command-line parsing and top-level error handling."""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timedelta, timezone, tzinfo

from . import __version__
from .config import load_config
from .errors import IntervalKeeperError
from .evaluate import to_epoch
from .reader import read_config
from .states import active_states, build_lines
from .timezones import default_timezone


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kairos",
        description="Print the states active at a given instant.",
    )
    parser.add_argument("-c", "--config", metavar="FILE", help="read FILE instead of the XDG config; '-' reads stdin")
    parser.add_argument("--at", metavar="DATETIME", help="evaluate at an ISO 8601 datetime instead of now")
    parser.add_argument("-n", "--next-change", action="store_true", help="print the next instant when reported states change")
    parser.add_argument("--tz", metavar="ZONE", help="default time zone (IANA name or supported zone form)")
    parser.add_argument("--format", metavar="FMT", default="%Y-%m-%d %H:%M:%S", help="format for --next-change (strftime, iso, or epoch)")
    parser.add_argument("--check", action="store_true", help="validate the complete configuration without output")
    parser.add_argument("--print-default-config", action="store_true", help="print the default configuration")
    parser.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
    return parser


_AT_RE = re.compile(
    r"""^\s*(\d{4})-(\d{2})-(\d{2})
        (?:[ T](\d{2}):(\d{2})(?::(\d{2})(?:[.,]\d+)?)?
           \s*(Z|[+-]\d{2}(?::?\d{2})?)?)?
        \s*$""",
    re.VERBOSE | re.IGNORECASE,
)


def parse_at(text: str, zone: tzinfo) -> datetime:
    """Parse ``--at`` (SPEC §2): ``YYYY-MM-DD[ T]HH:MM[:SS][offset]``.

    A bare date means 00:00. Without an offset the time is local to *zone*
    (an ambiguous time takes its first occurrence, PEP 495). Sub-seconds are
    truncated. Calendar validity is left to ``datetime``.
    """
    match = _AT_RE.match(text)
    if match is None:
        raise IntervalKeeperError(None, None, f"invalid --at value {text!r}; expected YYYY-MM-DD[ T]HH:MM[:SS][offset]")
    year, month, day, hour, minute, second, offset = match.groups()
    tzinfo_: tzinfo = zone
    if offset:
        if offset.upper() == "Z":
            tzinfo_ = timezone.utc
        else:
            digits = offset[1:].replace(":", "")
            delta = timedelta(hours=int(digits[:2]), minutes=int(digits[2:] or 0))
            tzinfo_ = timezone(-delta if offset[0] == "-" else delta)
    try:
        return datetime(
            int(year), int(month), int(day), int(hour or 0), int(minute or 0), int(second or 0),
            tzinfo=tzinfo_,
        )
    except ValueError as exc:
        raise IntervalKeeperError(None, None, f"invalid --at value {text!r}: {exc}") from None


def _run(args: argparse.Namespace) -> int:
    # Validate the options before the config is loaded, so a bad option never
    # leads to a default config being created.
    zone = default_timezone(args.tz)
    moment = parse_at(args.at, zone) if args.at is not None else datetime.now(zone).replace(microsecond=0)
    at = to_epoch(moment)

    path, text = load_config(args.config)
    entries = read_config(text, path)

    # --check and --next-change never skip a subtree (SPEC §5.4); the default
    # mode only needs the window [at, at+1s) and prunes inactive subtrees.
    full_parse = args.check or args.next_change
    lines = build_lines(
        entries, path=path, tz=zone, now=moment,
        window=None if full_parse else (at, at + 1),
        run_all_commands=args.check,
    )
    if args.check:
        return 0
    if args.next_change:
        raise IntervalKeeperError(None, None, "--next-change is not implemented yet")

    names = active_states(lines, at)
    if names:
        sys.stdout.write("\n".join(names) + "\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        if args.print_default_config:
            from .defaults import DEFAULT_CONFIG
            sys.stdout.write(DEFAULT_CONFIG)
            return 0
        return _run(args)
    except IntervalKeeperError as exc:
        for diagnostic in exc.diagnostics():
            print(diagnostic, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
