# kairos — implementation constraints and testing

Part of the [kairos specification](../SPEC.md).

## Implementation

The command is `kairos` (no `.py`), a thin executable launcher (`#!/usr/bin/env python3`) that delegates to the `kairoslib` package. **Do not consolidate the implementation into one script**: keep it in modules, and add modules where that gives a unit clear ownership.

```text
kairos                  launcher; adds the repository root to the import path, then runs kairoslib.cli:main
kairoslib/
  cli.py                argument parsing, orchestration, output and exit handling
  errors.py             error types and diagnostic formatting
  config.py             XDG lookup, config loading and creation
  defaults.py           default config text
  reader.py             logical lines, indentation tree, STATE processing
  macros.py             macro scope, expansion, command execution
  names.py              locale-aware month/weekday names, reserved-word check, wrong-locale hint
  timezones.py          TZ resolution with IANA tzdata / zoneinfo
  lexer.py              INTERVAL tokenization
  parser.py             INTERVAL grammar and AST dataclasses
  ranges.py             RangeSet algebra, half-open range primitives
  evaluate.py           AST to RangeSet, relative intervals
  states.py             hierarchy semantics, reported-state unions
  next_change.py        candidate boundaries, --next-change search
tests/                  helpers.py, test_*.py
Makefile  SPEC.md  spec/  PLAN.md  README.md  man/kairos.1
```

* The launcher works from a source checkout with no installation and no `PYTHONPATH`, and holds no logic. The package imports without running the CLI.
* Dependencies flow from low-level utilities up to orchestration; lower modules never import `cli.py`, there are no circular imports and no wildcard imports. Shared types (errors, AST in `parser.py`, range and timezone contracts) are defined once. Cross-module APIs are explicit and type-hinted where practical.
* `names.py` is the only module that knows about locales.

**Constraints.**

* Python ≥ 3.9. Allowed third-party: `python-dateutil` (`relativedelta`), `tzlocal` (local zone discovery), and the system `tzdata`; other imports may be added if a need emerges.
* **No hand-written calendar logic.** Month lengths, leap years, weekdays, locale precedence, month/weekday names, zones, DST and month/year arithmetic all come from `datetime`, `calendar`, `locale`, `zoneinfo` and `dateutil`. Looping over `datetime.date` is acceptable but to be minimised. Only the interval *set algebra* (union, intersection, difference and clipping of lists of `(start, end)` instants) is the tool's own code.
* Indentation follows the Python reference ([states.md](states.md#indentation)); the implementation may reimplement it or reuse a standard library for it.
* Macro commands are arbitrary code run with the user's privileges; there is no sandbox. The security note belongs in `man/kairos.1`, not in the default config.

## Testing

* Tests encode the vectors below verbatim. Pass `--at` and `--tz` explicitly and never depend on the wall clock (bare-time `--at` takes the clock as a parameter); set `TZ` too when the environment matters. Assert calendar facts with `datetime` so a wrong fact in this specification is caught.
* Error tests assert exit status 2, empty stdout, and `PATH:LINE` plus a keyword on stderr. Every rule in the specification that says "error" needs such a test; V12 lists samples. Prefer table-driven tests (`config, args, expected stdout`).
* Locale tests run in a subprocess per locale (process-global state must not leak) and skip a locale that is not installed.
* **Indentation:** test mixed tab/space cases the Python reference accepts and rejects (for example a tab-indented child followed by a sibling indented with eight spaces), and compare the reader on random tab/space prefixes with Python's own tokenizer (`tokenize`). Blank and comment lines are not measured, a first indented line, a macro with children and a dedent to a level that is not open are errors.
* **Default config** (V11): the examples parse under `--check` with a fake `ncal` on `PATH`, and `--print-default-config` equals the created file.
* **Oracle** (V13): `--next-change` is checked against stepping forward.

## Conformance vectors

`tz` is the default zone (`--tz`), `at` is `--at`, "→ ∅" is empty stdout with exit 0. Calendar facts: 2026-10-09 is a Friday; 2026-10-01 a Thursday; 2026-11-01 a Sunday; 2026-12-01 a Tuesday; 2026-07-05 a Sunday.

**V1** `tz=Europe/Budapest`, config:
```
08:00-16:00 = work
12:00-13:00 = lunch
```
| at | states | `--next-change` |
|----|--------|-----------------|
| 2026-10-09 07:59:59 | ∅ | `2026-10-09 08:00:00` |
| 2026-10-09 09:00 | `work` | `2026-10-09 12:00:00` |
| 2026-10-09 10:00 | `work` | `2026-10-09 12:00:00` |
| 2026-10-09 12:00:00 | `work`, `lunch` | `2026-10-09 13:00:00` |
| 2026-10-09 12:05 | `work`, `lunch` | `2026-10-09 13:00:00` |
| 2026-10-09 13:01 | `work` | `2026-10-09 16:00:00` |
| 2026-10-09 16:00:00 | ∅ | `2026-10-10 08:00:00` |

A bare `08:00` is exactly `[08:00:00, 08:01:00)`: active at 08:00:00 and 08:00:59, inactive at 08:01:00. As an anchor, `08:00 + 2 hours` is `[08:00:00, 10:00:00)` and `2 hours until 08:00` is `[06:00:00, 08:00:00)`.

**V2** `23:00-04:00 = evening`: at 2026-10-10 02:00 → `evening`, next `2026-10-10 04:00:00`; at 2026-10-09 22:59:59 → ∅; at 2026-10-09 12:00 → next `2026-10-09 23:00:00`.

**V3** `Dec-Feb = winter`: at 2027-01-15 12:00 → `winter`; at 2026-10-09 12:00 → next `2026-12-01 00:00:00`; at 2027-02-28 12:00 → next `2027-03-01 00:00:00`.

**V4** a parent without STATE:
```
Mon-Fri
  Dec = weekdays in December
```
at 2026-12-01 10:00 → `weekdays in December`; at 2026-12-05 10:00 (Saturday) → ∅; at 2026-12-04 12:00 → next `2026-12-05 00:00:00`.

**V5** `~` and `@`:
```
Jun,Jul,Aug = summer
  Sun = @Sunday
    20:00-23:00 = evening in summer's ~s
```
at 2026-07-05 21:00 → `summer`, `evening in summer's Sundays`; at 2026-07-05 19:00 → `summer`, next `2026-07-05 20:00:00`; at 2026-07-05 23:00 → next `2026-07-12 20:00:00`.

**V6** negation:
```
*-*-01 = first
  ! Sun,Sat = first, on weekdays
```
at 2026-10-01 12:00 → `first`, `first, on weekdays`; at 2026-11-01 12:00 → `first`.

**V7** relative: `1-7 Mon + 5 days = run`: at 2026-10-09 10:00 → `run`; at 2026-10-10 00:00:00 → ∅; next at 2026-10-09 10:00 is `2026-10-10 00:00:00`, and at 2026-10-10 12:00 `2026-11-02 00:00:00`. `40 days until Dec 24 = runup`: at 2026-11-14 23:59:59 → ∅; at 2026-11-15 00:00:00 → `runup`; at 2026-12-24 12:00 → `runup`, next `2026-12-25 00:00:00`.

**V8** spans: `Apr 1 -- Jun 15 = spring` is active at 2027-06-15 23:59:59 and not at 2027-06-16 00:00:00. `Dec 20 -- Jan 10 = holidays` is active at 2027-01-05 12:00; next at 2026-10-09 12:00 is `2026-12-20 00:00:00`. `2026 Apr 1 -- 20 = x` is active at 2026-04-20 12:00, not at 2026-04-21 00:00:00, not at 2027-04-10.

**V9** zones (`tz=UTC`): `*-12-* 08:00-09:00 Europe/Berlin = t` is active at 2026-12-01 07:30:00 and not at 06:59:59; `*-07-* 08:00-09:00 Europe/Berlin = t` at 2026-07-01 06:30:00; `08:00-09:00 UTC+0300 = t` at 2026-10-09 05:30:00. Bare alphabetic abbreviations such as `CEST` and `CST` as TZ tokens are errors that ask for an IANA zone ID or a numeric offset.

**V10** macros:
```
Q1 := Jan-Mar
Q1 = first quarter
```
at 2026-02-10 → `first quarter`.
* Names with spaces, punctuation and a common start: `Mary := Mon`, `Mary's birthday := Jun 1`, `Mary's birthday = party`, `Mary = m`: at 2026-06-01 10:00 (a Monday) `party`, `m`; at 2026-06-08 10:00 `m`. Whole word: `mary := Mon` followed by `annamary = x` is an error (unknown word `annamary`).
* Command macro: `A := Tue`, `D := ! echo "$KAIROS_MACRO_A"`, `D = x` is active on a Tuesday. It runs once at its definition even when unused; later uses do not run it again.
* Pruning: a command macro inside `Jun,Jul,Aug = summer` runs under `--at` in July (with `KAIROS_INTERVAL_0` = `Jun,Jul,Aug` and `KAIROS_STATE_0` = `summer`), does not run under `--at` in October, and runs in October with `--check` and with `--next-change`. A root-level command macro has no `KAIROS_INTERVAL_*` or `KAIROS_STATE_*`; a deeper one sees only its ancestors' (`D := ! env` at level 1 sees `_0`, not `_1`).

**V11** the default config with the leading `# ` of its example lines stripped (`Easter` using the `date` wrapper) parses as one config under `--check`.

**V12** each is an error (exit 2, empty stdout): `08:00-25:00 = x`; `Mon Tue = x`; `Foo = x`; `Mon = ~` (top level); `  Mon = x` as the first line; `Mon := x`; `7 := x`; `Q := Jan` twice; `Feb 30 = x`; `2026-02-29 = x`; `Mon =`; `= x`; `08:00-08:00 = x`; `Mon Foo/Bar = x` (unknown zone); `X := ! false` on its own, or followed by `X = x`. The last exits 2 in default mode, with `--next-change` and with `--check`; the one exception is a command inside a subtree skipped in default mode.

**V13** property test: for each config above and random `at` values, `--next-change` equals the first `t' > at` found by stepping one second (one minute when the config has no seconds) at which the printed state set differs.

**V14** DST (all instants UTC; interval zone `Europe/Budapest`; check with `--at`):
* Spring gap, 2026-03-29 (02:00 local does not exist; transition 01:00 UTC): `02:00-03:00 = gap` is empty that day: not active at 00:59:59 or 01:00:00. `01:00-04:00 = crossing` is `[00:00, 02:00)`: active at 00:30:00 and 01:30:00, inactive at 02:00:00. `Mon-Fri 08:00-16:00 = work` keeps the local window 08:00–16:00 while its UTC boundaries move from 07:00/15:00 to 06:00/14:00.
* Fall fold, 2026-10-25 (02:00 occurs twice; transition 01:00 UTC): `02:00-03:00 = fold` is `[00:00, 02:00)`: active at 00:30:00 and 01:30:00, inactive at 02:00:00. `01:00-04:00 = crossing` is `[2026-10-24 23:00:00, 2026-10-25 03:00:00)`: active at 00:30:00, 01:30:00 and 02:30:00, inactive at 03:00:00. `Mon-Fri 08:00-16:00 = work` keeps local 08:00–16:00 while its UTC boundaries are one hour later than in summer.

**V15** locale names (subprocess per case, skip if the locale is missing):
* `LANG=hu_HU.UTF-8`, no `LC_TIME` or `LC_ALL`: `március 15 = x` parses, `Mar 15 = x` is an unknown word. With `LANG=en_US.UTF-8` the reverse.
* Precedence: `LANG=hu_HU.UTF-8` with `LC_TIME=en_US.UTF-8` accepts English names and rejects Hungarian ones, and the reverse; `LC_ALL=hu_HU.UTF-8` with `LANG` and `LC_TIME` English accepts Hungarian and rejects English.
* Repeat for full and abbreviated weekday names, month and weekday ranges, comma lists, macro-expanded names and macro names reserved by the vocabulary; non-ASCII characters such as `á` survive tokenization.

**V16** `before` / `after` (`tz=Europe/Budapest`, year 2026):
```
40 days before Dec 24 = early
10 days after Oct 1 = later
2 days before Apr 10 12:00 = dinner
3 hours after 08:00 = brunch
1 month before Mar 31 = clamped
1 year before Dec 20 -- Jan 10 = last year
```
`early` is `[2026-11-14 00:00, 2026-11-15 00:00)` (active 2026-11-14 12:00:00, inactive 2026-11-13 23:59:59 and 2026-11-15 00:00:00); `later` is exactly 2026-10-11; `dinner` is `[2026-04-08 12:00:00, 2026-04-08 12:01:00)`; `brunch` is `[11:00:00, 11:01:00)` every day; `clamped` is Feb 28, 2026 (`[Mar 31, Apr 1)` becomes `[Feb 28, Mar 1)`); `last year` is `[2025-12-20, 2026-01-11)`, and `[2024-12-20, 2025-01-11)` the year before. `--next-change` with only `early`: at 2026-10-09 12:00 `2026-11-14 00:00:00`, at 2026-11-15 00:00:00 `2027-11-14 00:00:00`. With `2 days before Apr 10` as a parent and a child `08:00-09:00 = x`, only 2026-04-08 08:00–09:00 shows `x`.

**V17** several parts (`tz=Europe/Budapest`, year 2026):
```
2 days before Apr 10, 3 days after Oct 1 = two shifts
Apr 1, 2 days before Apr 10 = day and shift
Mon + 2 days, Fri = week
2 days before Apr 10, Apr 20 = separate parts
Apr 1, 2 days = oops
```
`two shifts` is exactly Apr 8 and Oct 4; `day and shift` exactly Apr 1 and Apr 8 (never the days 1 and 2); `week` is every Monday and Tuesday plus every Friday; `separate parts` is Apr 8 and Apr 20, and so is `2 days before Apr 10,20`. The last line is an error (`2 days` without `until`, `before` or `after`), and so is a trailing comma (`Apr 1,`, `Apr 1, 2 days before Apr 10,`). `--next-change` of `two shifts` at 2026-01-01 00:00 is `2026-04-08 00:00:00`.

**V18** `--at` forms (`tz=Europe/Budapest`; the current time is a parameter). Config `06:00-07:00 = x`:
* `--at 2026-10-09` is `2026-10-09 00:00:00` (`x` inactive; `00:00-01:00 = y` shows `y`). `--at 2026-10-09Z` is `00:00:00` UTC, that is 02:00:00 in Budapest (`y` inactive, `00:00-03:00 = z` shows `z`).
* `--at "2026-10-09 12:00 Europe/Berlin"` and `--at "2026-10-09 12:00:00UTC+2"` are both `2026-10-09 10:00:00 UTC`; `--at "2026-10-09 12:00Z"` is 12:00:00 UTC; `8:05` equals `08:05`.
* Now = `2026-10-09 20:00:00` (18:00:00 UTC): `--at 06:00` → `2026-10-10 06:00:00` with the warning naming `06:00` and `2026-10-10`; `--at 08:00:01` → today, no warning; `--at 08:00` → today (exactly 12 hours), no warning; `--at 07:59:59` → tomorrow, with the warning; `--at 22:00` → today. With a `TZ` the day and the 12 hours count in that zone: `--at 05:00Z` → `2026-10-10 05:00:00 UTC` with the warning; `--at 06:00Z` → `2026-10-09 06:00:00 UTC`, no warning. `--next-change` with `--at 06:00` searches from `2026-10-10 06:00:00`.
* Now = `2026-10-09 15:00:00`: `--at 14:00` → today, no warning. Now = `2026-10-09 01:06:00`: `--at 23:00` → today, no warning.
* Errors: `24:00`, `25:00`, `6:60`, `6:00x`, `2026-10-09 06:00 Foo/Bar`, `2026-10-09T06:00`, and abbreviations such as `CEST`.

**V19** indentation: see [Testing](#testing); no separate rows, the Python reference decides.

**V20** commas and spans (`tz=Europe/Budapest`, year 2026):
* `1 -- 5, 10 -- 12 = x` is `[1st 00:00, 6th 00:00)` and `[10th 00:00, 13th 00:00)` of every month: active at 2026-10-05 23:59:59 and 2026-10-12 23:59:59, inactive at 2026-10-06 00:00:00 and 2026-10-13 00:00:00. `--next-change` at 2026-10-06 12:00 is `2026-10-10 00:00:00`; at 2026-10-12 12:00 it is `2026-10-13 00:00:00`.
* `1 -- 5, 10 = y` is days 1–5 plus day 10 (active 2026-10-10 12:00, inactive 2026-10-06 12:00). `5, 10 -- 12 = z` is day 5 plus days 10–12 (active 2026-10-05 12:00 and 2026-10-11 12:00, inactive 2026-10-09 12:00 and 2026-10-13 12:00). `Apr 1 -- Apr 5, Apr 10 -- Apr 12 = w` is two spans.
* Still errors: `1-3 -- 10 = x`, `Mon -- Fri = x`, `1 -- 5, = x`.

**V21** macros and time zones: no time-zone name is reserved, and expansion does not touch a zone ID that merely contains a macro name. With `tz=UTC`, `Budapest := Mon`, `Europe := Tue` and `Budapest 08:00-09:00 Europe/Budapest = x`, only the stand-alone `Budapest` is expanded (`Mon 08:00-09:00 Europe/Budapest`): `x` is active at 2026-10-12 06:30:00 UTC (a Monday), inactive at 05:59:59 UTC and at 2026-10-13 06:30:00 UTC. `CEST := Europe/Berlin` with `08:00-09:00 CEST = x` is active at 2026-10-09 06:30:00 UTC, and `UTC := Mon` or `Z := Mon` are valid definitions. `Mon := x` stays an error (V12).

**V22** hour and minute ranges (`tz=Europe/Budapest`, Friday 2026-10-09):
* Errors, with a message that names the replacement: `15h-16h = x`, `8h-12h = x`, `22h-2h = x`, `8:*-12:* = x`, `8h-12:* = x`, `15m-20m = x`, `15min-20min = x`, `15m-*:20 = x`, `*:15-20m = x`, `*:15-*:15 = x` (equal ends), `15:00-*:20 = x` (mixed kinds).
* `15:00-16:00 = a` is active at 15:00:00 and 15:59:59, inactive at 16:00:00. `*:15-*:20 = b` is active at 03:15:00 and 03:19:59, inactive at 03:14:59 and 03:20:00; `--next-change` at 03:15:00 is `03:20:00`, at 03:20:00 it is `04:15:00`. `*:50-*:10 = c` is active at 03:50:00, 03:59:59, 04:00:00 and 04:09:59, inactive at 03:49:59 and 04:10:00.
* `8h = d` is `[08:00, 09:00)`; `8h,10h = e` is 08:00–09:00 and 10:00–11:00; `30m = f` is `[h:30, h:31)` every hour. `Mon-Fri 08:00-13:00 30m = g` is active at 08:30:00 and 12:30:59 on the Friday, inactive at 08:29:59, at 13:30:00 and on Saturday 2026-10-10 at 10:30.
