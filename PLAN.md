# kairos — work plan

Status: **the implementation covers the SPEC except for the items in §4.** `SPEC.md` is the source of truth for behaviour; the `kairos(1)` man page (`man/kairos.1`) is the user-facing reference; the generated default config contains examples only.
This plan lists what is done (§3, traces only) and what remains (§4, one item per work session).

## 0. How to use this plan (read first)

1. Pick **one** item from §4 (the lowest-numbered one whose dependencies are done, unless told otherwise). Do only that item, then stop. Each item is sized for a single short session: read only the SPEC sections it names, run the focused tests while working and the full suite (`make test`, about 35 s) once at the end.
2. `SPEC.md` wins over this plan. If the spec is ambiguous or contradicts itself, record the exact conflict in §5 and ask the author; do not guess and do not silently pick a parse error. Behaviour is changed in `SPEC.md` only in a separate commit whose message starts with `spec:` (decisions are D1–D25 in SPEC §0).
3. When an item is finished and its acceptance checks pass, **delete it from §4** and, if it completes part of the spec, add a one-line trace to §3.
4. Commit small, imperative subject line (`Run unused command macros under --check`). Never commit credentials.

## 1. Hard constraints

* Python ≥ 3.9. The root `kairos` is a thin executable launcher; implementation code lives in the `kairoslib/` package, in module files.
* **No hand-written calendar logic.** Month lengths, leap years, weekdays, time zones, DST and month/year arithmetic come from `datetime`, `calendar`, `zoneinfo`, `dateutil.relativedelta`; month/weekday names from the locale-aware library tables.
* On parse or semantic errors: message on stderr with file and line, keep parsing to report the other failing lines, exit 2 at the end, **empty stdout**.
* Config lookup via XDG; the default config is created only when none is found and no `--config` was given; a missing explicit `--config PATH` is an error and is never created.
* Dependencies: stdlib, `python-dateutil`, `tzlocal`, system `tzdata`.

## 2. Repository layout

```
kairos            thin executable launcher importing kairoslib.cli:main
kairoslib/        cli, errors, config, defaults, reader, macros, names, timezones,
                  lexer, parser, ranges, evaluate, states, next_change   (SPEC §1.1)
man/kairos.1      full syntax and CLI reference, security note
tests/            helpers.py (run_cli, fake ncal), test_*.py (unittest), fixtures
Makefile          test, install, uninstall (PREFIX respected)
SPEC.md  PLAN.md  README.md
```

Module `names.py` is the only place that knows about locales; AST dataclasses live in `parser.py`; shared errors in `errors.py`.

## 3. Done (traces; details are in SPEC and tests)

* SPEC §2 options `-c`, `-n`, `--tz`, `--format`, `--print-default-config`, `-V`, `-h`; full-form `--at` and bare-date `--at`. (`--check` and bare-time `--at` are T1, T2.)
* §3 config lookup, creation of the default config, `--config -`; `--print-default-config` equals the created file.
* §4 line reader: indentation tree, `=` split, `!`, STATE escapes, `@`, `~` inheriting from the nearest ancestor with a STATE (D7).
* §5 macros: names with spaces and punctuation, longest-first whole-word expansion, scopes, lazy command macros, `KAIROS_*` environment, default-mode pruning; command macros fail at evaluation time (D18).
* §5.3, §6.1–6.2, §11, V15 locale-aware month/weekday names (`names.py`), reserved-word checks, every unknown word reported, `wrong locale?` hint.
* §6 lexer and parser: items, clauses, lists (D3, whitespace around commas), spans including `1 -- 5` and Feb 29 endpoints, `HOUR`/`MINUTE` kinds, `+` / `until` / `before` / `after`, several parts per INTERVAL; AST nodes `Clause`, `Span`, `Union`, `RelPlus`, `RelUntil`, `RelShift`, `Combined`.
* §7 and §9 evaluation: `RangeSet` algebra, windowed evaluation (`spec ∩ [lo, hi)`), DST gap/fold (V14), hierarchy, negation, reported states.
* §8 time zones: IANA IDs, numeric offsets, legacy-ID rule (D14), no abbreviation table, default-zone precedence.
* §10 `--next-change`: candidate boundaries, finite tails, 400-year / TZif-footer recurrence proof, `--format`, fold warning.
* §13 vectors V1–V17 have tests (V18 is T2). Man page, README, Makefile targets and default config exist (install fix: T3; default-config trim: T4).

## 4. Remaining work: one item per session

Items T1–T8 and T10–T13 are independent of each other; T9 comes after T1, T2, T4 and T10–T13.

### T1 — `--at` bare date and bare time (SPEC §2.3, D20, V18)

Read: SPEC §2.3, D20, V18. Files: `kairoslib/cli.py` (`parse_at`; move to a small module only if that is cleaner), new `tests/test_at.py`; `man/kairos.1`; `README.md`.

* Bare date (`2026-10-09` = 00:00) already works: add the test, make no change to it.
* Bare time `HH:MM[:SS]`: `parse_at(text, zone, now)` takes the current time as a parameter (tests never read the wall clock; `_run` passes `datetime.now(zone)`). Rule: today's date in the display zone; if that instant is **more than 12 hours** in the past use the next day and print the stderr warning of SPEC §2.3; otherwise keep today (exactly 12 h stays today; later-today times stay today). DST gap/fold follows §7.1.
* Offsets on bare forms and out-of-range times (`24:00`, `06:00Z`, `2026-10-09Z`) are errors with the usual `--at` message; update the message and the `--at` help text.
* Tests: every V18 row via `parse_at` with an injected clock (and the warning text), plus one CLI run with a bare date.
* Docs: man page and README `--at` rows list the three forms and the 12-hour rule.

Acceptance: V18 rows pass; `kairos --at 2026-10-09` and `kairos --at 06:00` work from the command line.

### T2 — `--check` evaluates every command macro (SPEC §2, §5.4, D18, V12 tail)

Read: SPEC §5.1, §5.4, D18, the V12 tail. Files: `kairoslib/states.py`, `kairoslib/cli.py`, `kairoslib/macros.py` (only if needed); tests; `man/kairos.1`; `README.md`.

* in `--check` mode, command macros are evaluated at definition time, not lazy.
* Default mode and `--next-change` stay lazy: an unused command macro never runs there.
* Update the tests that assert the old behaviour: `tests/test_cli_states.py::test_command_failure_is_an_evaluation_time_error` (`X := ! false` alone: exit 0 in default mode and `--next-change`, exit 2 with `--check`, error at `<stdin>:1`) and `tests/test_states.py::test_a_failing_command_is_an_error_only_when_a_line_evaluates_it`.
* Docs: man page macro section ("`--check` also runs command macros that no line uses"), README `--check` row, `--check` help text.

Acceptance: `make test` green; the three cases above behave as stated.

### T3 - done

### T4 — Default config: examples only (SPEC §3.3)

Files: `kairoslib/defaults.py`, `tests/test_defaults.py`. Read: SPEC §3.3.

* Keep the file inert (every line starts with `#`), the `## ` / `# ` conventions and all examples; shorten the header to a few `## ` lines saying where the documentation is (`man kairos`, `--check`, `--print-default-config`); reduce explanatory prose to one-line captions; remove the dangling "(a snapshot, see section 3)" reference.
* No reference material and no security note in the default config (that note lives in the man page; it is already there).
* Tests: extend `tests/test_defaults.py` so that the default text does not contain the security note while `man/kairos.1` does; the examples still pass `--check` with the fake `ncal`; `--print-default-config` still equals the created file.

Acceptance: `make test` green; default config is examples plus a short header.

### T5 — Conformance tests: comma whitespace and lone-day spans (SPEC §6.4, §6.5)

Files: `tests/test_parser.py`, `tests/test_evaluate.py`. Fix the parser only if a case below fails.

* Whitespace around commas is insignificant: table-driven equality of the parse results for `Jun 1,Jul 2` / `Jun 1, Jul 2` / `Jun 1 ,Jul 2`; `1,15` / `1, 15` / `1 ,15`; `Mon-Wed,Fri` / `Mon-Wed, Fri`; `08:00-12:00,13:00-17:00` / `08:00-12:00, 13:00-17:00`; and `Apr 1,2 days before Apr 10` / `Apr 1, 2 days before Apr 10`.
* Lone-day spans: `1 -- 5` equals `1-5`; days 1–5 of every month (evaluation); `28 -- 3` rolls over into the next month; the right-side inheritance cases of §6.5 (`2026 Apr 1 -- 20`, `Apr 1 -- Jun 15`).

Acceptance: new tests pass.

### T6 — Pin the Feb 29 span rounding (SPEC §6.5)

Files: `tests/test_evaluate.py`; `SPEC.md` only for a `spec:` clarification.

* Add tests for `Feb 29 -- Mar 1`, `Feb 20 -- Feb 29` and `Feb 29 -- Feb 29` in a leap year and in a non-leap year (including `--next-change`): a Feb 29 endpoint that does not exist collapses to the zero-length instant between Feb 28 and Mar 1, for the start and for the (exclusive) end; the two start/end cases `Feb 29 -- Mar 1` and `Feb 20 -- Feb 29` were probed and already behave this way.
* If the sentence in SPEC §6.5 ("round the date to the latest existing date/time … i.e. Feb 28") reads as if it contradicted the tests, reword it in a separate `spec:` commit without changing the behaviour; if you think the behaviour itself should change, put the question in §5 instead.

Acceptance: new tests pass; spec wording is unambiguous.

### T7 — Audit for hand-written calendar logic (definition of done)

Files: `kairoslib/*.py` (comments only unless a violation is found), new `tests/test_no_handwritten_calendar.py`.

* Search the package for month-length tables, leap-year formulas (`% 4`, `% 400`), manual weekday computations and `monthrange`-like re-implementations. Library calls (`calendar.monthrange`, `relativedelta`, `date.weekday()`) are fine.
* Search margins and bounds (`366 * DAY`, `31 * DAY + 3600` in `evaluate.py`, `last + 366 * 86400` in `timezones.py`, `CYCLE_DAYS`, `MAX_T` in `next_change.py`) get a one-line comment saying they are bounds, not calendar arithmetic.
* The test greps the package source for the forbidden patterns (leap-year formulas, `[31, 28`/`31, 28`-style tables, `% 400`) and fails on a match.

Acceptance: audit finds no violation (or the violation is replaced by a library call); the new test passes.

### T8 — Python 3.9 / 3.10 run and `tzlocal` check (definition of done)

Files: depends on what breaks; optionally `.github/workflows/test.yml` (matrix 3.9–3.13, `pip install python-dateutil tzlocal`; pushing a workflow needs a token with the `workflow` scope, otherwise leave it as a file for the author).

* Run `make test` on a real Python 3.9 and 3.10 (`uv python install 3.9 3.10` or pyenv/docker; the sandbox has only 3.13) and fix incompatibilities. All modules use `from __future__ import annotations`; look for runtime-evaluated annotations (`dataclasses`, `typing.get_type_hints`), `zoneinfo`/`tzdata` availability and other 3.10+ features.
* Confirm the V14 boundary tests pass there (no discrepancy has been seen on 3.11–3.13).
* With `tzlocal` installed, check that `default_timezone` finds the system zone without `--tz` and `$TZ` (the sandbox could not install it before).

Acceptance: suite green on 3.9 and the newest 3.x; §5 entries for V14 and `tzlocal` closed.

### T9 — Documentation consistency pass (after T1, T2, T4)

Files: `man/kairos.1`, `README.md`, `kairoslib/cli.py` help texts. Read: SPEC §2, §5, §6 headings.

* Check the man page and README against SPEC §2 (options, `--at` forms, `--check`), §5.1 (`KAIROS_*`), §5.4, §9.1–9.2, §11, §12 (security note present in the man page only).
* Fix drift in the docs, never in the SPEC. Anything that looks like a spec bug goes to §5.

Acceptance: every option and rule in SPEC §2 appears in the man page; no statement in man/README contradicts the SPEC.

### T10 — Python-style indentation (SPEC §4.2, §4.3, D21, V19)

Read: SPEC §4.3, D21, V19. Files: `kairoslib/reader.py` (`read_config`), `tests/test_reader.py`; `man/kairos.1` (its indentation paragraph still says "never both in one line").

* Replace the "indentation may not mix spaces and tabs" rejection and the `expandtabs(8)` comparison by the two-measure rule of §4.3: every line gets a (column, alt-column) pair, compared with the pairs of the open levels, which therefore have to be kept on the stack, not only the columns. Messages: `inconsistent use of tabs and spaces in indentation` and `unindent does not match any outer indentation level`.
* Unchanged: blank and comment lines are not measured; the first line has no indentation; macro lines have no children; `KAIROS_*_<LEVEL>` still counts depth, not columns.
* Tests: every V19 row, plus a randomized comparison of `read_config` with Python's own tokenizer (random tab/space prefixes; compare consistent / `TabError` / dedent error with `tokenize.generate_tokens`). A reference implementation of the SPEC rule agreed with the tokenizer on 20 000 random cases.

Acceptance: V19 passes; `make test` green.

### T11 — Commas next to spans (SPEC §6.4, §6.5, D22, V20)

Read: SPEC §6.4, §6.5, D22, V20. Files: `kairoslib/parser.py` (list and term splitting), `kairoslib/lexer.py` only if needed; `tests/test_parser.py`, `tests/test_evaluate.py`, one `--next-change` row in `tests/test_next_change.py`; `man/kairos.1` (lists and spans).

* A comma after the right side of a span ends the term; a comma before a value that starts a span (a date side followed by `--`) ends the term. So `1 -- 5, 10 -- 12` is two spans, `1 -- 5, 10` a span and a clause, `5, 10 -- 12` a clause and a span. This needs a lookahead for `--` after `[YEAR] [MONTH] DOM [TIME]` / `ISODATE [TIME]`.
* Outside spans the list rule (D3) and the `NUMBER unit` rule (D19) stay as they are.
* Tests: every V20 row, including the "still errors" list; whitespace around these commas is insignificant like everywhere else.

Acceptance: V20 passes; `make test` green.

### T12 — TZ tokens are reserved macro names; `/` is not a word boundary (SPEC §5.2, §5.3, D23, D24, V21)

Read: SPEC §5.2, §5.3, D23, D24, V21. Files: `kairoslib/timezones.py` (new `is_tz_token(text) -> bool`: true iff `resolve_tz` accepts the text; no zone list of its own), `kairoslib/macros.py` (`validate_macro_name`, `_expansion_pattern`), `tests/test_macros.py`, `tests/test_timezone.py`; `man/kairos.1` (macro names, reserved words).

* `validate_macro_name` rejects a name that is entirely a TZ token (`macro name … is reserved`); `lexer.is_reserved_word` keeps covering month/weekday names and grammar words. `macros` may import `timezones`; `timezones` must not import `macros` or `lexer`.
* `_expansion_pattern`: use `(?<![\w/])` and `(?![\w/])` instead of `(?<!\w)` and `(?!\w)`, on the sides where the name starts or ends with a word character.
* Tests: every V21 row; a zone-ID case is skipped when that ID is not in the installed TZDB.

Acceptance: V21 passes; `make test` green.

### T13 — No hour ranges; `*:MM-*:MM` minute ranges (SPEC §6.1–§6.3, §7.1, D25, V22)

Read: SPEC §6.1–§6.3, §7.1, D25, V22. Files: `kairoslib/lexer.py`, `kairoslib/parser.py` (HOUR/MINUTE handling, around lines 200 and 420), `kairoslib/evaluate.py` (minute windows), `kairoslib/defaults.py` (the example `Mon-Fri 8h-12h 30m` becomes `Mon-Fri 08:00-13:00 30m` and its caption changes; V11 must keep passing), `tests/test_parser.py` (~lines 108–113), `tests/test_evaluate.py` (~lines 124–150 and 302), `tests/test_defaults.py`; `man/kairos.1` (HOUR/MINUTE table rows).

* HOUR ranges in either spelling and ranges with an `Nm`/`Nmin` end are errors whose message names the replacement (`15:00-16:00`, `*:15-*:20`).
* `*:MM-*:MM` is a half-open minute range: `[h:MM1, h:MM2)` for every hour h, wrapping into the next hour when the end is smaller; equal ends are an error; mixing with another kind is the usual mixed-kind error. `*` is also valid as the hour of a `MINUTE` item (§6.3).
* Rewrite the tests that assert inclusive ranges (`8h-12h`, `22h-2h`, `50m-10m`, `Mon-Fri 8h-12h 30m`) so that they use the new forms.

Acceptance: V22 and V11 pass; `make test` green.

## 5. Open questions and implementation notes for the author

Open:

* D20 details I chose, please confirm: bare date and bare time take no offset; a bare time exactly 12 hours in the past stays today; the warning text in SPEC §2.3. – author acknowledges
* `--check` runs an unused command macro with the context of its enclosing lines only (SPEC §5.4); the previous implementation note spoke of "lines above its definition". - author acknowledges
* V14 on Python 3.9/3.10 and `tzlocal` discovery: T8.
* D24 makes `/` part of a word for macro expansion, but `-` is still a boundary (it is the range operator, `Mon-Fri`). So a macro named `Prince` or `au` can still alter `America/Port-au-Prince`; likewise `Porto-Novo`, `Blanc-Sablon`, `Ust-Nera`. Options: leave it (the author named the macro like a fragment of a zone ID), or never expand inside a token that is a TZ token. Which one? (D23 already stops a macro from being named like a whole zone ID.)
* D23 reading to confirm: only what `resolve_tz` accepts is reserved, so `CEST`, `CST`, `IST` stay usable as macro names (`CEST := Europe/Berlin` works). Reserving every alphabetic abbreviation would need an abbreviation list, which D9 rules out. Also note that the reserved set follows the installed TZDB, so a config may be valid on one machine and rejected on another when a macro is named like a zone ID that only one of them has (`CET`, `Factory`, `localtime` are IDs on some systems).

Implementation choices not in the SPEC (promote into the SPEC with a `spec:` commit, or reject):

* A clause's `TIME`, `HOUR` and `MINUTE` items are turned into daily windows and intersected - author needs explanation
* a wrapping hour range (`22h-2h`) spills into the next day, a wrapping minute range (`50m-10m`) into the next hour. - author acknowledges. Superseded by D25: hour ranges are gone, and the minute range is written `*:50-*:10` (T13).
* Duration arithmetic for `+`, `until`, `before`, `after` uses the zone of the first anchor term that names a zone, else the default zone. - author acknowledges
* An anchor with no instance start/end (always on, e.g. `00:00-24:00 + 1 day`) has no meaningful result; the look-back is capped at 100 years so evaluation terminates. - author acknowledges
* `--next-change` searches up to `MAX_T`, two days before 9999-12-31 (a margin for zone-offset conversion); changes in the last two days of year 9999 are out of reach. - author acknowledges
* Pruning detail: below an inactive parent, a line that needs an uncached command is only structurally validated and so are its descendants; a value cached earlier is reused anywhere. - author: this needs spec tuning: cache command macro´s output only when all the KAIROS_INTERVAL_* and KAIROS_STATE_* and KAIROS_MACRO_* env vars are the same.
* A string macro expands only names visible where it was defined. - author: yes, string macros should resolve immediately to a flat string
* The `wrong locale?` hint names the built-in `C`/`POSIX` locales only if no other installed locale knows the word. - author acknowledges

## 6. Testing notes

* Always pass `--at` and `--tz` in tests; never depend on the wall clock (bare-time `--at` takes the clock as a parameter). For tests that need a fixed environment also set `TZ`.
* Calendar facts of SPEC §13 are asserted with `datetime` in tests, so a wrong fact in the spec is caught.
* Error tests assert exit code 2, empty stdout, and `PATH:LINE` plus a keyword in stderr.
* Table-driven tests are preferred (`(config, args, expected_stdout)`); each V-vector is one row.
* Locale tests run in subprocesses and `skipTest` when the locale is not installed.

## 7. Risks

| Risk                                                                                        | Mitigation                                                                                       |
| ------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| Relative intervals whose anchor starts long before the window                               | Widen look-back until the first relevant anchor instance is complete; tests with long durations. |
| Adjacent ranges across midnight or DST must merge, or `--next-change` reports false changes | Merge in `RangeSet`; V13 oracle test.                                                            |
| Zone IDs colliding with macro or month/weekday words                                        | Explicit lexer order and reserved-name rules; no abbreviation table.                             |
| Macro text substitution altering zone names                                                 | `/` is not a word boundary (SPEC §5.2, D24); hyphenated IDs stay a limitation (§5, open).        |
| `ncal -e` output is locale-dependent                                                        | Never rely on it in tests; use the fake `ncal` and the `date -d` wrapper.                        |

## 8. Definition of done

* §4 is empty; `make test` passes from a clean checkout on Python 3.9 and the newest available 3.x.
* Every vector in SPEC §13 (V1–V18) is covered by a test.
* `kairos` with no config in a fresh environment creates the default file and exits 0 with no output.
* No hand-written month-length, leap-year or weekday logic remains in the package (T7 checks this).
