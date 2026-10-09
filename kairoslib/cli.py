"""Command-line parsing and top-level error handling."""
from __future__ import annotations

import argparse
import sys

from . import __version__
from .errors import IntervalKeeperError


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


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        if args.print_default_config:
            from .defaults import DEFAULT_CONFIG
            sys.stdout.write(DEFAULT_CONFIG)
            return 0
        raise IntervalKeeperError(None, None, "not implemented")
    except IntervalKeeperError as exc:
        print(exc.diagnostic(), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
