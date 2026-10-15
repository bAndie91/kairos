# kairos — work plan

Status: **the implementation covers the SPEC except for the items in §4.** `SPEC.md` (an index of the files in `spec/`) is the source of truth for behaviour; the `kairos(1)` man page (`man/kairos.1`) is the user-facing reference; the generated default config contains examples only.
This plan lists what is done (§3, traces only) and what remains (§4, one item per work session).

## 0. How to use this plan (read first)

1. Pick **one** item from §4 (the lowest-numbered one whose dependencies are done, unless told otherwise). Do only that item, then stop. Each item is sized for a single short session: read only the spec parts it names, run the focused tests while working and the full suite (`make test`, about 35 s) once at the end.
2. `SPEC.md` wins over this plan. If the spec is ambiguous or contradicts itself, record the exact conflict in §5 and ask the author; do not guess and do not silently pick a parse error. Behaviour is changed in `SPEC.md` only in a separate commit whose message starts with `spec:` (the spec has no decision table: the reason for a rule is written next to it).
3. When an item is finished and its acceptance checks pass, **delete it from §4** and, if it completes part of the spec, add a one-line trace to §3.
4. Commit small, imperative subject line (`Run unused command macros under --check`). Never commit credentials.

## 1. Hard constraints

Python version, dependencies, the thin launcher, "no hand-written calendar logic" and the error behaviour are in `spec/implementation.md` §2 and `spec/cli.md` §1.1–§1.2. They are not repeated here.

## 2. Repository layout

```
kairos, kairoslib/   launcher and package (module list in spec/implementation.md)
man/kairos.1         full syntax and CLI reference, security note
tests/               helpers.py (run_cli, fake ncal), test_*.py (unittest), fixtures
Makefile             test, install, uninstall (PREFIX respected)
SPEC.md, spec/       the specification: SPEC.md is the index of spec/*.md
PLAN.md  README.md
```

## 3. Done (traces; details are in SPEC and tests)

* cli §1 options `-c`, `-n`, `--tz`, `--format`, `--print-default-config`, `-V`, `-h`; full-form `--at` and bare-date `--at`. (`--check` and bare-time `--at` are T1, T2.)
* cli §2 config lookup, creation of the default config, `--config -`; `--print-default-config` equals the created file.
* states §1 line reader: indentation tree, `=` split, `!`, STATE escapes, `@`, `~` inheriting from the nearest ancestor with a STATE.
* macros §2–§4: names with spaces and punctuation, longest-first whole-word expansion, scopes, lazy command macros, `KAIROS_*` environment, default-mode pruning; command macros fail at evaluation time.
* intervals §1.2 and macros §2, V15: locale-aware month/weekday names (`names.py`), reserved macro names, every unknown word reported, `wrong locale?` hint.
* intervals §1–§6 lexer and parser: items, clauses, lists (whitespace around commas), spans including `1 -- 5` and Feb 29 endpoints, `HOUR`/`MINUTE` kinds, `+` / `until` / `before` / `after`, several parts per INTERVAL; AST nodes `Clause`, `Span`, `Union`, `RelPlus`, `RelUntil`, `RelShift`, `Combined`.
* intervals §6–§7 relative intervals and time model, states §3 hierarchy: `RangeSet` algebra, windowed evaluation (`spec ∩ [lo, hi)`), DST gap/fold (V14), hierarchy, negation, reported states.
* intervals §8 time zones: IANA IDs, numeric offsets, legacy-ID rule, no abbreviation table, default-zone precedence.
* states §3.3 and implementation §3 next change: candidate boundaries, finite tails, 400-year / TZif-footer recurrence proof, `--format`, fold warning.
* tests §2 vectors V1–V17 have tests (V18 is T1, V19–V22 are T10–T13). Man page, README, Makefile targets and default config exist (install fix: T3; default-config trim: T4).

## 4. Remaining work: one item per session

Items T1–T8 and T10–T14 are independent of each other; T9 comes after T1, T2, T4 and T10–T14.

### T1 — `--at` bare date and bare time (cli §1.3, V18)

Read: cli §1.3, V18. Files: `kairoslib/cli.py` (`parse_at`; move to a small module only if that is cleaner), new `tests/test_at.py`; `man/kairos.1`; `README.md`.

* Bare date (`2026-10-09` = 00:00) already works: add the test, make no change to it.
* Bare time `HH:MM[:SS]`: `parse_at(text, zone, now)` takes the current time as a parameter (tests never read the wall clock; `_run` passes `datetime.now(zone)`). Rule: today's date in the display zone; if that instant is **more than 12 hours** in the past use the next day and print the stderr warning of the spec; otherwise keep today (exactly 12 h stays today; later-today times stay today). DST gap/fold follows intervals §7.
* Offsets on bare forms and out-of-range times (`24:00`, `06:00Z`, `2026-10-09Z`) are errors with the usual `--at` message; update the message and the `--at` help text.
* Tests: every V18 row via `parse_at` with an injected clock (and the warning text), plus one CLI run with a bare date.
* Docs: man page and README `--at` rows list the three forms and the 12-hour rule.

Acceptance: V18 rows pass; `kairos --at 2026-10-09` and `kairos --at 06:00` work from the command line.

### T2 — `--check` evaluates every command macro (macros §4.3, V12)

Read: macros §4, V12. Files: `kairoslib/states.py`, `kairoslib/cli.py`, `kairoslib/macros.py` (only if needed); tests; `man/kairos.1`; `README.md`.

* in `--check` mode, command macros are evaluated at definition time, not lazy.
* Default mode and `--next-change` stay lazy: an unused command macro never runs there.
* Update the tests that assert the old behaviour: `tests/test_cli_states.py::test_command_failure_is_an_evaluation_time_error` (`X := ! false` alone: exit 0 in default mode and `--next-change`, exit 2 with `--check`, error at `<stdin>:1`) and `tests/test_states.py::test_a_failing_command_is_an_error_only_when_a_line_evaluates_it`.
* Docs: man page macro section ("`--check` also runs command macros that no line uses"), README `--check` row, `--check` help text.

Acceptance: `make test` green; the three cases above behave as stated.

### T3 - done

### T4 — Default config: examples only (cli §2.3)

Files: `kairoslib/defaults.py`, `tests/test_defaults.py`. Read: cli §2.3.

* Keep the file inert (every line starts with `#`), the `## ` / `# ` conventions and all examples; shorten the header to a few `## ` lines saying where the documentation is (`man kairos`, `--check`, `--print-default-config`); reduce explanatory prose to one-line captions; remove the dangling "(a snapshot, see section 3)" reference.
* No reference material and no security note in the default config (that note lives in the man page; it is already there).
* Tests: extend `tests/test_defaults.py` so that the default text does not contain the security note while `man/kairos.1` does; the examples still pass `--check` with the fake `ncal`; `--print-default-config` still equals the created file.

Acceptance: `make test` green; default config is examples plus a short header.

### T5 — Conformance tests: comma whitespace and lone-day spans (intervals §4, §5)

Files: `tests/test_parser.py`, `tests/test_evaluate.py`. Fix the parser only if a case below fails.

* Whitespace around commas is insignificant: table-driven equality of the parse results for `Jun 1,Jul 2` / `Jun 1, Jul 2` / `Jun 1 ,Jul 2`; `1,15` / `1, 15` / `1 ,15`; `Mon-Wed,Fri` / `Mon-Wed, Fri`; `08:00-12:00,13:00-17:00` / `08:00-12:00, 13:00-17:00`; and `Apr 1,2 days before Apr 10` / `Apr 1, 2 days before Apr 10`.
* Lone-day spans: `1 -- 5` equals `1-5`; days 1–5 of every month (evaluation); `28 -- 3` rolls over into the next month; the right-side inheritance cases of Spans (`2026 Apr 1 -- 20`, `Apr 1 -- Jun 15`).

Acceptance: new tests pass.

### T6 — Pin the Feb 29 span rounding (intervals §5)

Files: `tests/test_evaluate.py`; `spec/intervals.md` only for a `spec:` clarification.

* Add tests for `Feb 29 -- Mar 1`, `Feb 20 -- Feb 29` and `Feb 29 -- Feb 29` in a leap year and in a non-leap year (including `--next-change`): a Feb 29 endpoint that does not exist collapses to the zero-length instant between Feb 28 and Mar 1, for the start and for the (exclusive) end; the two start/end cases `Feb 29 -- Mar 1` and `Feb 20 -- Feb 29` were probed and already behave this way.
* If the Feb 29 wording in intervals §5 reads as if it contradicted the tests, reword it in a separate `spec:` commit without changing the behaviour; if you think the behaviour itself should change, put the question in §5 instead.

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

Files: `man/kairos.1`, `README.md`, `kairoslib/cli.py` help texts. Read: the headings of cli.md, macros.md and intervals.md.

* Check the man page and README against cli.md (options, `--at`, `--check`), macros.md (`KAIROS_*`, evaluation time), intervals.md (relative intervals, several parts) and implementation §2 (the security note is in the man page only).
* Fix drift in the docs, never in the SPEC. Anything that looks like a spec bug goes to §5.

Acceptance: every option and rule in cli.md appears in the man page; no statement in man/README contradicts the SPEC.

### T10 — Indentation as in Python (states §1.3, V19)

Read: states §1.3 and the Python language reference it cites. Files: `kairoslib/reader.py` (`read_config`), `tests/test_reader.py`; `man/kairos.1` (its indentation paragraph still says "never both in one line").

* Replace the "indentation may not mix spaces and tabs" rejection and the `expandtabs(8)` comparison by what the reference prescribes for tabs and spaces: reimplement it, or reuse a standard library. A trial that fed `prefix + "x"` for each non-blank, non-comment line to Python's tokenizer matched the reference on 20 000 random cases on 3.13; before 3.12 the pure-Python `tokenize` may not check tab consistency (only `compile` does), and the project supports 3.9, so verify a library route there (T8) or reimplement.
* Error messages follow Python's (`inconsistent use of tabs and spaces in indentation`, `unindent does not match any outer indentation level`).
* Unchanged: blank and comment lines are not measured; the first line is not indented; a macro line has no children; `KAIROS_*_<LEVEL>` counts depth, not columns.
* Tests as described in tests §1 (mixed cases, and a random comparison with Python's own tokenizer).

Acceptance: V19 / the Testing cases pass; `make test` green.

### T11 — Commas next to spans (intervals §4, §5, V20)

Read: intervals §4, §5, V20. Files: `kairoslib/parser.py` (list and term splitting), `kairoslib/lexer.py` only if needed; `tests/test_parser.py`, `tests/test_evaluate.py`, one `--next-change` row in `tests/test_next_change.py`; `man/kairos.1` (lists and spans).

* A comma after the right side of a span ends the term; a comma before a value that starts a span (a date side followed by `--`) ends the term. So `1 -- 5, 10 -- 12` is two spans, `1 -- 5, 10` a span and a clause, `5, 10 -- 12` a clause and a span. This needs a lookahead for `--` after `[YEAR] [MONTH] DOM [TIME]` / `ISODATE [TIME]`.
* Outside spans the list rule and the `NUMBER unit` rule stay as they are.
* Tests: every V20 row, including the "still errors" list; whitespace around these commas is insignificant like everywhere else.

Acceptance: V20 passes; `make test` green.

### T12 — `/` is not a word boundary; no reserved time-zone names (macros §2–§3, V21)

Read: macros §2 and §3, V21. Files: `kairoslib/macros.py` (`_expansion_pattern`), `kairoslib/lexer.py` (`_GRAMMAR_WORDS`, `is_reserved_word`), `tests/test_macros.py`, `tests/test_unknown_words.py` if it covers `UTC`; `man/kairos.1` (macro names, reserved words).

* `_expansion_pattern`: use `(?<![\w/])` and `(?![\w/])` instead of `(?<!\w)` and `(?!\w)`, on the sides where the name starts or ends with a word character.
* No time-zone name is reserved any more. `UTC_WORDS` (`utc`, `gmt`, `z`) is part of `_GRAMMAR_WORDS`, which `is_reserved_word` (and so `validate_macro_name`) uses: take it out of the reserved set, but keep it for tokenizing a `TZ`. Check every other user of `is_reserved_word`. Do not add a zone list: a macro may be named like a zone, and expansion happens before tokenization.
* Tests: every V21 row.

Acceptance: V21 passes; `make test` green.

### T13 — No hour ranges; `*:MM-*:MM` minute ranges (intervals §1, §2, §7, V22)

Read: intervals §1, §2, §7, V22. Files: `kairoslib/lexer.py`, `kairoslib/parser.py` (HOUR/MINUTE handling, around lines 200 and 420), `kairoslib/evaluate.py` (minute windows), `kairoslib/defaults.py` (the example `Mon-Fri 8h-12h 30m` becomes `Mon-Fri 08:00-13:00 30m` and its caption changes; V11 must keep passing), `tests/test_parser.py` (~lines 108–113), `tests/test_evaluate.py` (~lines 124–150 and 302), `tests/test_defaults.py`; `man/kairos.1` (HOUR/MINUTE table rows).

* HOUR ranges in either spelling and ranges with an `Nm`/`Nmin` end are errors whose message names the replacement (`15:00-16:00`, `*:15-*:20`).
* `*:MM-*:MM` is a half-open minute range: `[h:MM1, h:MM2)` for every hour h, wrapping into the next hour when the end is smaller; equal ends are an error; mixing with another kind is the usual mixed-kind error. `*` is also valid as the hour of a `MINUTE` item (intervals §3).
* Rewrite the tests that assert inclusive ranges (`8h-12h`, `22h-2h`, `50m-10m`, `Mon-Fri 8h-12h 30m`) so that they use the new forms.

Acceptance: V22 and V11 pass; `make test` green.

### T14 — Point code, tests and docs at the new spec files

Comments and docstrings in `kairoslib/*.py` and `tests/*.py`, plus `README.md` and `man/kairos.1`, still cite the old `SPEC §N` and `D<n>` numbers (about 90 places: `grep -rnE 'SPEC|§[0-9]|\bD[0-9]+\b' --exclude-dir=.git --exclude-dir=spec --exclude=PLAN.md .`). Replace each citation by the file and heading in the new spec (`macros §3`) or drop it where the comment says enough. D-numbers no longer exist; V-numbers are unchanged.

Old section to new file: §1.1, §12 → implementation; §13 → tests; §2, §3 → cli; §4, §7.2–§7.4 → states; §10 → states §3.3 and implementation §3; §5 → macros; §6, §7.1, §8, §9 → intervals; §11 → the rule it lists (there is no error list any more). New citations read `file §N`, as in the spec (`macros §3`).

Comment-only change.

Acceptance: the grep above finds no `SPEC §` or `D<n>` citation; `make test` green.
\1 and implementation notes for the author

Open:

* `--at` details I chose: bare date and bare time take no offset; a bare time exactly 12 hours in the past stays today; the warning text in cli §1.3. – author acknowledges
* `--check` runs an unused command macro with the context of its enclosing lines only (macros §4.3); the previous implementation note spoke of "lines above its definition". - author acknowledges
* V14 on Python 3.9/3.10 and `tzlocal` discovery: T8.

Implementation choices not in the SPEC (promote into the SPEC with a `spec:` commit, or reject):

* A clause's `TIME`, `HOUR` and `MINUTE` items are turned into daily windows and intersected - author needs explanation
* a wrapping hour range (`22h-2h`) spills into the next day, a wrapping minute range (`50m-10m`) into the next hour. - author acknowledges. Superseded: hour ranges are gone, and the minute range is written `*:50-*:10` (T13).
* Duration arithmetic for `+`, `until`, `before`, `after` uses the zone of the first anchor term that names a zone, else the default zone. - author acknowledges
* An anchor with no instance start/end (always on, e.g. `00:00-24:00 + 1 day`) has no meaningful result; the look-back is capped at 100 years so evaluation terminates. - author acknowledges
* `--next-change` searches up to `MAX_T`, two days before 9999-12-31 (a margin for zone-offset conversion); changes in the last two days of year 9999 are out of reach. - author acknowledges
* Pruning detail: below an inactive parent, a line that needs an uncached command is only structurally validated and so are its descendants; a value cached earlier is reused anywhere. - author: this needs spec tuning: cache command macro´s output only when all the KAIROS_INTERVAL_* and KAIROS_STATE_* and KAIROS_MACRO_* env vars are the same.
* A string macro expands only names visible where it was defined. - author: yes, string macros should resolve immediately to a flat string
* The `wrong locale?` hint names the built-in `C`/`POSIX` locales only if no other installed locale knows the word. - author acknowledges

## 6. Testing notes

See `spec/tests.md` §1.

## 7. Risks

| Risk                                                                                        | Mitigation                                                                                       |
| ------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| Relative intervals whose anchor starts long before the window                               | Widen look-back until the first relevant anchor instance is complete; tests with long durations. |
| Adjacent ranges across midnight or DST must merge, or `--next-change` reports false changes | Merge in `RangeSet`; V13 oracle test.                                                            |
| Zone IDs colliding with macro or month/weekday words                                        | Explicit lexer order and reserved-name rules; no abbreviation table.                             |
| Macro text substitution altering zone names                                                 | `/` is not a word boundary (macros §3); a hyphenated ID can still be altered: accepted.  |
| `ncal -e` output is locale-dependent                                                        | Never rely on it in tests; use the fake `ncal` and the `date -d` wrapper.                        |

## 8. Definition of done

* §4 is empty; `make test` passes from a clean checkout on Python 3.9 and the newest available 3.x.
* Every vector in spec/tests.md (V1–V22) is covered by a test.
* `kairos` with no config in a fresh environment creates the default file and exits 0 with no output.
* No hand-written month-length, leap-year or weekday logic remains in the package (T7 checks this).
