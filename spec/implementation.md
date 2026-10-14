# kairos — implementation constraints

Part of the [kairos specification](../SPEC.md).

## 1. Architecture

The implementation is a modular Python package; **do not consolidate it into one script**. The user-facing command stays `kairos`, with all CLI behaviour and config compatibility of this specification.

Recommended layout:

```text
kairos                  executable launcher; delegates to kairoslib.cli:main
kairoslib/
  __init__.py
  cli.py                argument parsing, orchestration, output and exit handling
  errors.py             shared exception/error types and diagnostic formatting
  config.py             XDG lookup, config loading/creation, default-config file I/O
  defaults.py           default config text constant
  reader.py             logical lines, indentation tree, STATE processing
  macros.py             macro scope, expansion and command execution
  names.py              locale-aware month/weekday names (LC_TIME), reserved-word check, wrong-locale hint
  timezones.py          zone resolution using IANA TZDB / zoneinfo
  lexer.py              INTERVAL tokenization
  parser.py             INTERVAL grammar and AST dataclasses
  ranges.py             RangeSet algebra and half-open interval primitives
  evaluate.py           AST-to-RangeSet evaluation and relative intervals
  states.py             hierarchy semantics and reported-state unions
  next_change.py        candidate boundaries and --next-change search
tests/
  helpers.py
  test_*.py
Makefile
SPEC.md  spec/  PLAN.md  README.md
```

* The launcher is thin, with no business logic. It works from a source checkout without installation or a configured `PYTHONPATH`, by adding the repository root to the import path in a small, predictable way before importing `kairoslib.cli`. The package must be importable by tests without invoking the CLI.
* The module list is a default decomposition, not a requirement to create a module for every trivial helper; a module may be split further where that gives a unit clear ownership or reduces conflicts. Avoid circular imports; dependencies flow from low-level utilities toward orchestration, and lower-level modules never import `cli.py`.
* Shared low-level types (`errors.py`, AST types in `parser.py`, common interval/timezone contracts) have one canonical definition.
* No wildcard imports. Cross-module APIs are explicit and, where practical, type-hinted.

## 2. Constraints

* Python ≥ 3.9. The `kairos` launcher is `#!/usr/bin/env python3`.
* Allowed third-party: `python-dateutil`, `tzlocal`; the system `tzdata`. Other imports may be added if a need emerges.
* **All** calendar, weekday, month-length, leap-year, zone, DST and month/year arithmetic, and the interpretation of locale-dependent month/weekday names, goes through the standard or library facilities (`datetime`, `calendar`, `locale`, `zoneinfo`, `dateutil`). Looping over `datetime.date` is fine but to be minimised; re-implementing leap-year, locale precedence, name tables, case rules or zone rules is not.
* Locale handling (what the names are: intervals §1.2): initialise it once, before any locale-sensitive lexing or parsing, through the `locale` module's environment-based selection (`locale.setlocale(locale.LC_TIME, "")`). Do not read `LANG`/`LC_*` by hand, do not force the `C` locale, do not switch locales per token; process-global state is acceptable for a CLI (an in-process or concurrent future must account for it). Name production and recognition are delegated to the locale-aware date/time facilities, and lexing, reserved-word checks and date evaluation use the same locale within one invocation.
* Interval *set algebra* (union, intersection, subtraction, clipping of lists of `(start, end)` instants) is the tool's own code.
* Macro commands are arbitrary code run with the user's privileges; there is no sandbox. This security note is documented in the man page (`man/kairos.1`), not in the default config.

## 3. `--next-change` search

Do not sample every second or scan every date as the primary algorithm. Generate the next possible boundary from the AST:

* A clause yields local start/end boundaries from its matching dates and time ranges; jump directly to the next matching calendar date. A span yields its endpoint boundaries. A relative interval yields the starts/ends after applying its duration to the anchor instances' starts/ends. Keep half-open, second-resolution semantics.
* Merge the candidate streams chronologically. At each candidate instant `T`, compare the complete reported state set at `T-1 second` and at `T` (states §3.3) and return the first candidate where they differ. Boundaries hidden by adjacent or overlapping ranges, or by another line with the same state name, are skipped.
* **Termination.** Split expressions into finite exceptions and recurring parts. Explicit-year clauses and spans, and relative intervals derived only from finite anchors, contribute finitely many boundaries; account for their complete duration tails before treating them as finished. Recurring calendar clauses and spans repeat with the Gregorian 400-year cycle (146,097 days), and calendar-duration arithmetic repeats on it as well; do not assume a recurring anchor has finite tails.
* For every IANA zone used, account for the TZif future-rule footer ([RFC 9636](https://www.rfc-editor.org/rfc/rfc9636.html)): after its last explicit transition, future transitions follow its recurring POSIX rule or, with no footer rule, its final offset. The recurrence fingerprint includes these rules and offsets, not only the Gregorian dates. TZif recurrence metadata may be parsed for this, but actual wall-clock/instant conversion still uses `zoneinfo`. The 400-year cycle is a valid termination period only after all finite exceptions have ended and the zone recurrence fingerprints align.
* Beyond all finite exceptions and tails, search at most one complete combined recurrence cycle for a real change, using the candidate streams (no blind scan of every day). If the reported set does not change in that cycle, no later change exists: print nothing, exit 0.

Python's `datetime` domain is finite (years 1 to 9999). "Indefinitely" means no user-configurable horizon or arbitrary cut-off: search until a change is found or the recurrence proof shows none remains, bounded only by that domain.
