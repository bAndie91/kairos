# kairos — execution plan

Status: **DRAFT 0.1 — in progress, M0–M7 accepted; M8 (`--next-change`) and M9 (default config text, docs) remain.** Companion to `SPEC.md`, which is the source of truth for behaviour.
This plan is written so that an agent with no other context can pick it up and continue.

## 0. How to use this plan (read first)

1. Read `SPEC.md` completely, especially §0 (decisions D1–D13) and §13 (conformance vectors).
   Decisions marked as awaiting review in the repo's review thread may change; if `SPEC.md` has changed, it wins over this plan.
2. Follow the dependency graph in §2.1. Milestones may run in parallel only where the graph says so; acceptance gates apply before dependent work is integrated, not before unrelated work starts.
3. Each agent works on a separate branch/worktree and submits commits or a patch to the integrator. **Do not have multiple agents push to `master` or edit the same working tree.** The integrator alone updates `master` and this plan's checkboxes.
4. Tick a checkbox only when its task is integrated and its acceptance checks pass; do not tick it merely because an agent's branch is ready.
5. If the spec is ambiguous or contradicts itself: do **not** guess or automatically choose a parse error. Record the exact conflict in
   "Open questions", compare the relevant normative text and conformance vectors, and resolve it explicitly. Prefer the SPEC's
   stated decisions and examples; make a spec correction in a separate commit if those conflict. Use a parse error only when the
   specification requires rejection or no consistent interpretation is possible.
6. Commit small and often, one task or tightly related group per commit, imperative subject line (`Parse ISO dates with wildcards`).
7. Never change `SPEC.md` behaviour silently. Spec corrections are separate commits whose message starts with `spec:`.

## 1. Hard constraints (from the brief; violating them is a bug)

* Python ≥ 3.9. Keep a small executable launcher named `kairos` in the repository root and place implementation code in the `kairoslib/` package. The launcher contains no business logic.
* **Never hand-write datetime logic.** All calendar, weekday, leap-year, month-length, time-zone, DST and month/year arithmetic goes through
  `datetime`, `zoneinfo`, `dateutil.relativedelta`. Only interval set algebra (lists of `(start, end)` instants) is custom.
* On parse or semantic errors: message on stderr with file and line(s), try go on parsing to show other failing lines too, exit 2 at the end, **empty stdout**.
  Parse the whole config before printing normal output. Print errors as it goes.
* Config lookup via XDG; create the default config only when no config is found and no `--config` was given. A missing explicit
  `--config PATH` is an error; never create that path.
* May suggest other libs besides the spec's dependency list (stdlib, `python-dateutil`, `tzlocal`, system `tzdata`).

## 2. Repository layout (target)

```
`kairos`          thin executable launcher importing `kairoslib.cli:main`
kairoslib/        Python package with implementation modules (see SPEC §1.1)
tests/
  helpers.py               imports package modules; run() helper for the CLI; ncal stub
  test_*.py                unittest test modules (stdlib unittest; pytest also works)
  fixtures/                config files used by tests
Makefile                   `make test` → python3 -m unittest discover -s tests -v
SPEC.md  PLAN.md  README.md
```

Module ownership follows SPEC §1.1. Keep each agent's edits within its assigned module(s) and test module(s); do not re-create the old single-file section ordering. Shared APIs and cross-module changes are coordinated by the integrator.


## 2.1 Parallel-work rules and dependency graph

Implementation units live in separate `kairoslib/` modules to reduce merge conflicts. Parallelism still means **isolated branches and bounded ownership**, not concurrent edits to a shared checkout.

- The integrator creates one branch/worktree per agent from the same current `master`. Agents must not push directly to `master`, rewrite another agent's branch, or edit `PLAN.md` checkboxes.
- Give each agent a narrow deliverable: named milestone(s), owned `kairoslib/*.py` module(s), and its own test module(s). Avoid overlapping file ownership. Code branches are integration-ready proposals, not permission to merge blindly. The launcher, shared errors/interfaces, package exports, `Makefile`, and `PLAN.md` are integrator-owned unless explicitly delegated.
- Test-file ownership should be disjoint: for example, `test_config.py`, `test_reader.py`, `test_macros.py`, `test_timezone.py`, `test_parser.py`, `test_ranges.py`, and `test_next_change.py`. Shared helpers and `Makefile` belong to the integrator; agents request helper changes rather than editing them concurrently.
- Agree on public function names, AST dataclasses, node fields, error representation, and the shared timezone-token/reserved-word contract before dependent work begins. Do not create parallel, incompatible interfaces. Put AST dataclasses in `parser.py` initially; if a separate `ast.py` becomes necessary, the integrator makes that change once and updates the import contract.
- The integrator integrates one change to `kairos` at a time, rebases/cherry-picks as needed, runs affected tests, then the full `make test`. Resolve conflicts by preserving section ownership and the spec, not by choosing one branch wholesale. Update checkboxes only after integration and acceptance.
- If an agent discovers a spec ambiguity, pause only the affected dependency chain; unrelated tasks may continue. Record the question here and make any behavioural change in a separate `spec:` commit.

Dependency graph (arrows mean “must be accepted before the dependent task”; independent branches can progress at once):

```text
                           ┌─ M1 config discovery/default-config plumbing ────────────────┐
M0 skeleton + test harness ├─ M2 line reader/tree ─ M3 macros ─────────────────────────┐  │
                           ├─ M4 timezone resolver ────────────────────────┐           ├─ M7 hierarchy/CLI ─ M8 next-change ─┐
                           └─ M5 lexer/parser AST (after M2; shared interfaces) ─ M6 range sets/evaluation ─────────────────┘  ├─ M9 final checks
                                                                                                                              ┘
```

Practical waves:

1. **Bootstrap:** M0. It defines the test harness and stable error/CLI skeleton; do not parallelize edits to these shared foundations.
2. **Parallel wave A:** M1, M2, and M4 may be developed on separate branches. M1 owns `config.py`/`defaults.py` config plumbing and `test_config.py`; M2 owns `reader.py` and `test_reader.py`; M4 owns `timezones.py` and `test_timezone.py`. The integrator lands them one at a time.
3. **Parallel wave B:** after M2 is accepted and interfaces are agreed, M3 and M5 may proceed in parallel. M3 owns `macros.py` and `test_macros.py`; M5 owns `lexer.py`, `parser.py`, and `test_parser.py`. Both use the agreed timezone/reserved-name constants and AST/node contracts. M5 must not independently implement timezone resolution.
4. **Parallel wave C:** once M4 and M5 are accepted, M6 owns `ranges.py`, `evaluate.py`, and `test_ranges.py`; M9 drafts README/default-config prose and owns `defaults.py` only if M1 has not started it (otherwise coordinate with M1). M9's executable-example checks and final default-config equality test wait until M1 and M7 are integrated.
5. **Serial integration chain:** M7 waits for M2, M3, and M6. M8 waits for M5–M7 and the required boundary semantics. Do not implement M7/M8 against unfinished evaluator semantics.
6. **Final gate:** the integrator runs the full suite on a clean integrated branch, checks every SPEC vector is covered, and only then marks milestones complete.

## 3. Milestones

Each milestone has focused acceptance checks. Run focused tests during development; the integrator runs full `make test` after each integration batch and at the final gate. The dependency graph above, rather than milestone numbering alone, determines what may proceed concurrently.

### M0 — Skeleton and test harness

- [x] Create the thin root `kairos` launcher and `kairoslib/` package skeleton (`__init__.py`, `cli.py`, `errors.py`); the launcher imports and calls `kairoslib.cli:main`. Add `argparse` for **all** options in SPEC §2 (unimplemented ones may raise "not implemented" → exit 2).
- [x] Define `IntervalKeeperError` in `kairoslib/errors.py`, carrying `(path, line, message)`; the top-level handler in `cli.py` prints `kairos: PATH:LINE: error: MESSAGE` and exits 2. Nothing else may print to stdout before success.
- [x] `tests/helpers.py`: package import helpers (no `SourceFileLoader` for a monolithic script); `run_cli(args, config_text=None, env=None)` returning `(code, stdout, stderr)` (feeds config through `--config -`); a fake `ncal` executable in a temp dir prepended to `PATH`
      that prints `04/05/26`.
- [x] `Makefile` with `test` target.

**Acceptance:** `kairos --help` and `--version` work from a clean source checkout without installation or `PYTHONPATH`; package modules import independently; a trivial test runs; an unknown option exits 2 with empty stdout.

### M1 — Config discovery and default config (SPEC §3)

- [x] XDG lookup: `--config`, `$XDG_CONFIG_HOME`, `$XDG_CONFIG_DIRS`; ignore relative XDG paths; `--config -` reads stdin.
- [x] Create the default file when nothing found and no `--config` given (dir 0700 if created, file 0644); notice on stderr; missing explicit `--config` → error without creating anything.
- [x] Default config text as a module constant in `kairoslib/defaults.py`, emitted by `--print-default-config`. Include the complete user-facing explanation,
      condensed format specification, and examples required by SPEC §3.3; comment every line so a fresh config is inert.
      Keep the final text task in M9, using a marker-only placeholder until then.
- [x] Tests with a temporary `HOME` / `XDG_*` environment: precedence order, creation, no creation for explicit path, relative XDG vars ignored.

**Acceptance:** all lookup/creation cases tested; running with a fresh empty `HOME` creates the file and prints no states.

### M2 — Line reader and indentation tree (SPEC §4)

- [x] Tokenise the file into logical lines: skip blank and `#` lines; allow indentation made of spaces or tabs, but reject indentation
      that mixes spaces and tabs; reject an indented first line; use a Python-style indentation stack with a "dedent to an open level" check.
- [x] Classify lines: macro definition (`NAME := …`, checked first) vs interval line. Split interval line at the first `=`; detect leading `!`; error on empty INTERVAL / empty STATE.
- [x] Macro lines cannot have children.
- [x] STATE processing: escapes (`\~`, `\@`, `\\`, others error), `@` hidden marker (bare `@` → error), and `~` substitution against the nearest ancestor with a STATE; error if no such ancestor exists (D7). Produce `effective_name` and `reported` flags.
- [x] Build a tree of nodes `{lineno, indent, negated, interval_text, state_raw, children}`, keep macro lines in the sequence in file order.

**Acceptance:** unit tests for indentation errors (V12 items on indentation), `=` splitting, `~`/`@` rules (V5 names only, without time evaluation).

### M3 — Macros (SPEC §5)

- [x] Name validation: SPEC §5.3 rules (any text; see M12), reserved words (a whole name equal to a locale month/weekday name, unit, `until`/`before`/`after`, `UTC`/`GMT`/`Z`, and the agreed timezone-token rules), redefinition against **visible** macros. Consume the shared constant/interface agreed with M4; do not duplicate the table.
- [x] Scope stack tied to the indentation tree; sibling subtrees may reuse names.
- [x] Whole-word, single-pass expansion on raw text, for both INTERVAL and STRING values; resolve command macros lazily on first use.
- [x] Command macros: run `${SHELL:-/bin/sh} -c COMMAND`, stdin `/dev/null`, stderr inherited; non-zero exit is an error, raised when the command is evaluated (M12, D18).
      Pass inherited environment plus resolved visible macros as `KAIROS_MACRO_<NAME>`, `KAIROS_NOW` as ISO 8601 with offset,
      and contextual `KAIROS_INTERVAL_<LEVEL>` / `KAIROS_STATE_<LEVEL>` for each ancestor and the current line (levels start at 0).
      Strip trailing newlines and collapse embedded newlines to spaces. Empty output is valid. Do not add an unspecified timeout.
- [x] Pruning hook for default mode (SPEC §5.4): the parser asks a callback `parent_active(node)`; when false the subtree is structurally validated only where it depends on skipped commands. `--next-change` and `--check` pass a callback that always returns true (a command macro that no line uses still never runs, D18).
      (The callback is implemented in M7; use a stub returning true until then.)

Completed in this branch without selecting M5; verification: `python3 -m unittest discover -s tests -v` passes with the macro tests included.

**Acceptance:** the macro parts of V10 and V12, including: `annamary` not substituted, env vars visible to commands (use `env`/`printenv` in tests), command not run when pruned (marker file), run under `--check`.

### M4 — Time zones (SPEC §8)

- [x] Implement `resolve_tz(token)` using `zoneinfo.available_timezones()` and `ZoneInfo`: IANA IDs are case-insensitive; support `UTC`, `GMT`, `Z`, and `UTC±H[H][[:]MM]` / `GMT±…` numeric offsets with ISO sign convention.
- [x] Do not maintain an application-owned abbreviation-to-zone map. Reject bare alphabetic abbreviations other than UTC/GMT (for example `CST`, `CEST`) with a clear error; abbreviations may be displayed only as labels produced by the selected zone's rules for a specific instant.
- [x] Default zone precedence: explicit `--tz`, then `$TZ`, then `tzlocal` system-zone discovery; fall back to UTC with a stderr warning if discovery fails.
- [x] Document the IANA database source and provide practical commands to list available IDs and inspect the abbreviation produced for a chosen zone and instant.
- [x] Tests: `UTC+0300` is east of Greenwich; offset validation; `Etc/UTC`; `Europe/Budapest`; case-insensitive IDs; bare `CEST`/`CST` rejected; unknown IDs error; default-zone precedence/fallback.

**Acceptance:** M4 tests confirm zone objects and offsets on specific dates, and no abbreviation mapping remains in application code.

### M5 — Interval lexer and parser → AST (SPEC §6)

- [x] Lexer with the token order of §6.1 (ISO date before number, `--` before `-`, supported TZ forms, words). Use the M4 timezone-token/reserved-name interface; the parser does not resolve zone objects. Alphabetic timezone abbreviations other than `UTC`/`GMT` are not TZ tokens.
- [x] Item kinds and ranges, number classification (< 100 DOM, ≥ 100 YEAR), month/weekday names (full, 3-letter, `Sept`, case-insensitive).
- [x] Clause conjunction rules and all clause errors (duplicate kind, DATE vs Y/M/D, impossible dates incl. `Feb 30`, `2026-02-29`, `*-04-31`; `Feb 29` ok).
- [x] Comma grouping rule D3 (same-kind continuation) producing terms.
- [x] Spans: sides, inheritance of year/month, rollover rules, times on both sides, recurring spans.
- [x] Relative forms: `union + duration`, `duration until union`, compound durations, TZ placement.
- [x] AST dataclasses: `Clause`, `Span`, `Union`, `RelPlus`, `RelUntil`, defined canonically in `kairoslib/parser.py` and imported by consumers. The parser never evaluates dates against the clock; it only validates.

**Acceptance:** every interval string in the brief parses; every parse-error case of V12 fails with a message containing the offending token; table-driven tests `text → AST repr`.

Completed on branch `work/m5-parser` (`kairoslib/lexer.py`, `kairoslib/parser.py`, `tests/test_parser.py`). The lexer owns the shared vocabulary (`RESERVED_WORDS`, `MONTHS`, `WEEKDAYS`, `UNITS`, `is_tz_token`); `macros.py` imports it. `HHh`/`MMm`/`MMmin` are the `HOUR`/`MINUTE` kinds (D15). The author will extend the parser acceptance cases (the brief's own interval list) in the test suite.

### M6 — Range sets and AST evaluation (SPEC §7.1, §9)

- [x] Implement `RangeSet` in `kairoslib/ranges.py`: sorted, disjoint, half-open, adjacent ranges merged; `union`, `intersect`, `subtract`, `clip`, `contains(t)`, `boundaries()`. Property tests against a naive implementation on random small sets.
- [x] Implement `eval(node, lo, hi, default_tz) -> RangeSet` in `kairoslib/evaluate.py` with the exact-restriction contract `spec ∩ [lo, hi)`.
  - `Clause`: iterate local dates of the clause's zone from `lo − 1 day` to `hi + 1 day` (using `datetime.date`), test the day-level items, emit ranges per time range, localize with `zoneinfo`, clip.
  - `Span`: iterate candidate years (recurring) or the single explicit year; endpoints via `datetime`; skip years where an endpoint does not exist.
  - `Union`: union of terms.
  - `RelPlus` / `RelUntil`: evaluate anchor over a widened window, take instance starts/ends, and apply duration pairs in the specified order: all calendar units (day/week/month/year) first via `relativedelta`, then elapsed units (hour/minute/second) in UTC. Widen until the first instance in the window is complete; clip.
- [x] Implement the exact bare-time semantics: `08:00` is `[08:00:00,08:01:00)`; as a relative anchor its instance start is 08:00:00 and its one-minute duration is ignored.
- [x] DST tests from SPEC V14: `Europe/Budapest` gap (2026-03-29) and fold (2026-10-25), including exact UTC boundary assertions for `02:00-03:00`, `01:00-04:00`, and `Mon-Fri 08:00-16:00`. Check both activity and inactivity at each stated boundary; use `zoneinfo` / PEP 495 semantics, not custom timezone arithmetic.

**Acceptance:** evaluation tests for V1, V2, V3, V7, V8, V9 interval texts on single lines (no hierarchy yet).

Completed on branch `work/m6-evaluate` (`kairoslib/ranges.py`, `kairoslib/evaluate.py`, `tests/test_ranges.py`, `tests/test_evaluate.py`). Instants are integer POSIX seconds; `evaluate(expr, lo, hi, default_tz)` returns `expr ∩ [lo, hi)`, checked by a window-independence property test. Interpretation choices made while implementing (review these):

- `times`, `hours` and `minutes` of one clause are each turned into daily windows and **intersected**; a wrapping hour range (`22h-2h`) spills into the next day like a wrapping time range (D2), a wrapping minute range (`50m-10m`) spills into the next hour.
- A recurring-span endpoint that does not exist in a year (`Feb 29`) collapses to the instant between Feb 28 and Mar 1 (start of Mar 1 in the span's zone), for both the start and the (exclusive) end.
- Duration arithmetic for `+` / `until` happens in the zone of the first anchor term that names a zone, else the default zone.
- An anchor with no instance start/end (always on, e.g. `00:00-24:00 + 1 day`) has no meaningful result; the look-back is capped at 100 years so evaluation terminates instead of looping.

### M7 — Hierarchy, states and default output (SPEC §7.2–7.4)

- [x] Implement effective sets `E(L)` (intersect with parent / subtract when negated).
- [x] Implement reported-state unions, `U(name)` across lines, ordering by first appearance, and de-duplication in `kairoslib/states.py`.
- [x] Default mode: small window `[at, at+1s)`; implement the `parent_active` pruning callback for M3.
- [x] CLI: `--at`, `--tz`, print states, `--check`.

**Acceptance:** V1 (states column), V4, V5, V6, V7, V8, V9, V10, V11, V12 pass through the CLI with exact stdout.

Completed (`kairoslib/states.py`, `kairoslib/cli.py`, small changes in `macros.py`, `reader.py`, `errors.py`; tests in `tests/test_states.py`, `tests/test_cli_states.py`, extended `tests/test_macros.py`). `build_lines` is the single place that ties reader, macros and parser together; `effective_sets` / `reported_sets` / `states_at` take any window `[lo, hi)` and are what M8 builds on. A randomized test checks that the pruned default-mode path and the window algebra agree at 60 instants of a year. Interpretation choices made while implementing (review these):

- **Pruning (§5.4).** A line's commands may run only if its parent's effective set contains the evaluation instant (top-level lines always may). Below an inactive parent, a line whose INTERVAL needs a command that is not cached is only structurally validated (reader); every other line there is fully parsed and validated. Descendants of such a line are treated as skipped too, since its effective set is unknown. A value already cached by an earlier use is reused anywhere.
- **Command macros are cached on the scope that defines them**, so one command runs at most once, on first use, whichever subtree uses it first. A string macro expands only names visible where it was defined, even though it is evaluated lazily.
- **`--check` runs every command macro**, including unused ones (§2: "all macro commands run"); an unused macro sees the lines above its definition as `KAIROS_INTERVAL_<LEVEL>`/`KAIROS_STATE_<LEVEL>` context. Default mode stays strictly lazy (D4), so an unused failing command is not an error there.
- **Command context.** `LEVEL` is the depth in the tree (0 = top-level line). The using line's own `KAIROS_INTERVAL_<LEVEL>` is its *unexpanded* text (expansion is still in progress), with `! ` for a negated line; `KAIROS_STATE_<LEVEL>` is the effective name (empty if none). `KAIROS_MACRO_<NAME>` uses the exact macro name (names are case-sensitive, so `a` and `A` do not collide) and only macros visible at the definition. `KAIROS_NOW` is the evaluation instant in the display zone.
- **Error collection.** Reader errors (indentation, line shape, STATE) are all reported, then processing stops; if the reader is clean, every macro/parse error is reported in line order, once each (a failing command used by several lines is reported once, at the macro line). A line below a broken line is still checked.
- `--at` accepts a bare date (00:00), `T` or space, optional seconds, and `Z` / `±HH[:MM]`; without an offset the time is local to the display zone (an ambiguous time takes its first occurrence). Options are validated before the config is read, so a bad option never creates the default config.
- `--next-change` is parsed and fully validated, then fails with "not implemented" until M8.

### M8 — `--next-change` (SPEC §10)

- [x] Implement candidate boundary generation and search in `kairoslib/next_change.py`; implement `--format` (`strftime`, `iso`, `epoch`) and indefinite `--next-change` search. Do not add a horizon option.
- [x] Implement AST-derived candidate-boundary streams: clauses jump directly to matching local dates/times; spans emit endpoints;
      relative intervals emit duration-adjusted anchor-instance boundaries. Merge candidates chronologically and compare the complete
      reported state set immediately before and at each candidate, ignoring boundaries hidden by overlapping ranges or same-name unions.
- [x] Separate finite exceptions from recurring terms. Track the end of explicit-year contributions and every finite relative-interval
      duration tail before treating the remaining schedule as recurring.
- [x] Implement a no-future-change proof: recurring Gregorian calendar patterns (including weekday/leap-day selectors and calendar
      durations) repeat on the 400-year / 146,097-day cycle. Include each used TZif zone's future-rule footer in the recurrence
      fingerprint: after explicit transitions, use its recurring POSIX rule, or its final offset if no footer rule exists. It is acceptable
      to parse TZif recurrence metadata to establish the cycle, but use `zoneinfo` for actual conversions. Only use a cycle as proof
      after finite exceptions/tails end and timezone recurrence fingerprints align. Search one complete combined recurrence cycle
      for real changes; if none occur, conclude there is no future change in the representable datetime domain.
- [x] No arbitrary horizon and no second-by-second or date-by-date brute-force scan. Python `datetime` represents years 1–9999;
      search until the next real change is found or the recurrence proof establishes none remains. If none remains, empty stdout,
      exit 0.

**Acceptance:** all `--next-change` columns of V1–V8 and the no-future-change cases pass; V13 brute-force oracle agrees; V14 DST/bare-time boundary tests pass. A 100-line config with a leap-day state (`Feb 29`) completes in under 5 s without scanning every second or every date. Include a case where overlapping same-name intervals create candidate boundaries but no reported state change.

Completed on branch `work/m8-next-change` (`kairoslib/next_change.py`, plus `matching_days` in `evaluate.py`, child evaluation restricted to the parent's set in `states.py`, `rules_start`/`recurrence_start` in `timezones.py`, `tests/test_next_change.py`). How it works and what to review:

- A reported-state change is exactly a boundary of some `U(name)` (a merged `RangeSet`), so same-name overlaps/adjacency and hidden lines are skipped by construction; the search takes the first boundary `> at` over consecutive, growing segments evaluated from the AST (no per-second or per-date scan; clauses jump to matching dates via `matching_days`).
- Termination: `finite_end` (last explicit year + every relative duration tail) and each used zone's `rules_start` (last explicit TZif transition + 1 year, parsed from the TZif file; conversions still use `zoneinfo`) give the start of the recurring regime; one 146,097-day cycle after the latest of those and `at` is searched, then "no change" is concluded. The domain end is `MAX_T` (two days before 9999-12-31, a margin for zone-offset conversion), so changes in the very last two days of year 9999 are out of reach.
- Measured: the 100-line leap-day config takes about 0.1 s; V13 is a minute-stepping oracle for near answers (<= 3 days) and a both-sides-plus-sampling check for far ones.
- `--format`: `iso`, `epoch` or a strftime string; a fold-ambiguous local result prints a stderr warning unless the format carries the offset (`iso`, `epoch`, `%z`, `%Z`).
### M10 — Locale-aware month and weekday names (SPEC §5.3, §6.2, §11, §12, V15)

Owner: names module + lexer/parser/macros. Depends on M5, M3.

No hand-maintained English vocabulary and no reading of `LANG`/`LC_*` by Kairos itself: one module owns locale handling and everything else asks it.

- [x] New `kairoslib/names.py`, the only module that knows about locales: `init_from_environment()` calls `locale.setlocale(locale.LC_TIME, "")` (Python's `locale` module resolves `LC_ALL` > `LC_TIME` > `LANG`; Kairos never inspects those variables); a `locale.Error` (requested locale not installed) is reported once as a stderr warning, never silent, and the process keeps its current locale. `use_locale(name)` is for tests (explicit locale, same code path).
- [x] Month and weekday names come only from the library's locale-aware tables (`calendar.month_name`, `month_abbr`, `day_name`, `day_abbr`, i.e. `datetime` formatting), case-folded; no English list, alias, transliteration or fallback. A string that the locale maps to two different months/weekdays is ambiguous and is reported as such, not guessed.
- [x] Tables are cached per effective `LC_TIME` value and never switched per token; a library import without `init_from_environment()` sees whatever `LC_TIME` the process has (the C locale in a fresh interpreter), so unit tests stay deterministic.
- [x] Lexer: remove `MONTHS` and `WEEKDAYS`; match names found in the locale tables as whole words, longest first, including names with punctuation (`janv.`) and non-ASCII letters; reserved-word checks (macro names, TZ detection, unknown-word diagnostics) use the same tables.
- [x] Parser and macros use the names module (`month_number`, `weekday_number`, reserved check) instead of lexer constants.
- [x] CLI calls `init_from_environment()` before reading the config. Subprocess tests set `LC_ALL`/`LANG`/`LC_TIME` before Python starts and `skipTest` when the locale is not installed (V15). Existing English-name tests pin the C locale.
- [x] Acceptance: V15 holds for hu_HU, en and C locales including precedence (`LC_ALL` > `LC_TIME` > `LANG`), full and abbreviated names, ranges, lists, macro-expanded names and reserved macro names; with a French locale `janv.` and `lun.` work; no English month/weekday literal remains under `kairoslib/`.

Completed on branch `work/m10-locale-before-after` (`kairoslib/names.py`, lexer/parser/macros/cli changes, `tests/test_locale_names.py`). Names are looked up through `calendar` (locale-aware `datetime` formatting) for the effective `LC_TIME` locale; Kairos never reads `LANG`/`LC_*`. Verified here with hu_HU, fr_FR, de_DE (generated with `localedef`) and C; `en_US` cases skip when not installed. Findings worth knowing: the English alias `Sept` (and `Tues`, `Thur`) is gone because the locale tables do not provide it; macro names now accept Unicode letters (§5.2); in Hungarian the library's weekday abbreviations are single letters (`h`, `k`, `p`, `v`), so a macro called `H` is reserved there, which is the spec working as written. **Not done (M3 gap, not part of M10):** SPEC §5.3 says macro names may contain spaces and punctuation and that longer names are tried first; the implementation still accepts identifier-like names only.

### M11 — `before` / `after` relative intervals (SPEC §9.1, D16, V16)

Owner: lexer/parser/evaluate. Depends on M5, M6; M8 must keep working.

- [x] Reserved keywords `before` and `after` (macro names, TZ detection, diagnostics).
- [x] Grammar: `duration "before" union` and `duration "after" union`; AST node `RelShift(duration, anchor, sign)`; same error rules as `until` (leading duration must be followed by a keyword, anchor must not be empty, nothing may follow the anchor).
- [x] Evaluator: shift both endpoints of every anchor instance in the anchor's zone, calendar units first then elapsed; shifted bare point times keep their one-minute length; dropped if empty/inverted; window-independent (widen the anchor window on the side where an instance would be cut off).
- [x] `--next-change`: duration tails of `before`/`after` count as finite tails; V13 oracle covers the new forms.
- [x] Acceptance: V16 holds, narrowing by children works, window-independence property test includes `before`/`after`.

Completed on the same branch (`RelShift` in `parser.py`, `_eval_shift` in `evaluate.py`, `tests/test_before_after.py`, plus the new forms in the window-independence property test and the V13 oracle). `before`/`after` are reserved words; a leading duration must be followed by `until`, `before` or `after`.

### M12 — Macro names and evaluation-time command errors (SPEC §4.1, §5.2, §5.3, §5.4, D17, D18)

Owner: reader/macros/states. Depends on M2, M3, M7.

- [x] `NAME := VALUE`: NAME is the text before the first `:=`, trimmed, containing no `=` (`reader._split_macro`). Validity is `macros.validate_macro_name`: non-empty, no `=`, no leading `!`, at least one letter, not entirely a reserved word (`Mon morning` is fine).
- [x] A name may start with, end with or contain another macro's name; only an identical name is a redefinition (D8).
- [x] Expansion is a single regex pass, longest visible name first, whole-word boundary only on the sides where the name starts/ends with a word character (names with punctuation need none there); names match literally (inner whitespace, case).
- [x] `KAIROS_MACRO_<NAME>`: NAME is used as is (`KAIROS_MACRO_Mary's birthday`), no transformation; a variable the OS/runtime would refuse (`=` or NUL, which a macro name cannot contain anyway) is left out with a stderr warning and the command still runs. The shell being unable to read such names is not our concern.
- [x] D18: defining a command macro runs nothing; a failing command is an error at the macro's line when a non-skipped line first uses it. `--check` evaluates only the command macros some line uses. The command value is cached on the defining scope.
- [x] Acceptance: V10 (Mary vectors), V12 (`7 := x`, `X := ! false` followed by a use), tests in `tests/test_macros.py`, `tests/test_states.py`, `tests/test_cli_states.py`.

Interpretation choices: the "at least one letter" rule is mine (a name of only digits/punctuation would collide with numbers, times and `*`); a macro name with leading or trailing whitespace is impossible since NAME is trimmed.

### M13 — Several parts in one INTERVAL (SPEC §6.4, §6.6, §9.2, D19, V17)

Owner: parser/evaluate/next_change. Depends on M5, M6, M8, M11.

- [x] Grammar: `interval = part {"," part}`, `part = term | term + D | D until|before|after term`; AST node `Combined(parts)` (a single part stays unwrapped; consecutive plain terms are merged into one `Union`). A comma followed by `NUMBER unit` never continues a day/year list (`Apr 1, 2 days before X` is two parts).
- [x] The anchor of every relative form is **one term** (a clause with its lists, or a span): a comma between terms ends the relative expression, so `2 days before Apr 10, Apr 20` is Apr 8 and Apr 20, and `Apr 10, Apr 20 + 2 days` is `Apr 10` plus `Apr 20 + 2 days`; `2 days before Apr 10,20` (a list in one clause) shifts both. `parse_expr` consumes the commas between parts and raises `trailing ','`.
- [x] `evaluate`: union of the parts, each with its own zone choice and window handling. `next_change`: `_terms`/`finite_end` walk every part.
- [x] Acceptance: V17 in `tests/test_unions.py` (parser shapes, errors, semantics, window independence, `--next-change`, CLI); the old test that forbade unions of relative forms was removed.

### M14 — Diagnostics for unknown words (SPEC §6.2)

Owner: lexer/names/states (error aggregation). Depends on M10, M7.

- [x] **Report every unknown word.** Today the lexer raises at the first unknown word of a line, so a config with several typos needs one run per typo. Make `tokenize` collect all unknown words of the INTERVAL (keep tokenizing after one; a line with unknown words is not parsed further) and report each as its own located diagnostic through the existing `ErrorList` aggregation (dedupe/sort by line already exist). Other lines are still checked, so one run lists all unknown words of the config. Other lexical errors (`unexpected character`, bad zone) may stay first-error-per-line unless collecting them is trivial.
- [x] **`wrong locale?` hint.** Message form: `unknown word 'May' (undefined macro? wrong locale? "May" is in "en_US.UTF-8" locale)`. For an unknown word the `names` module (the only module that handles locales) enumerates the installed locales (the platform list, e.g. `locale -a` run in a subprocess, with a short timeout; omit the hint if it cannot be listed), and for each one builds the month/weekday name tables with the same `calendar`/`datetime` facilities used for parsing (switch `LC_TIME`, read the names, always restore the effective locale in a `finally`). Report at most a few matching locales (listing order, then `…`); match case-insensitively on full and abbreviated names. No `LANG`/`LC_*` inspection, no hand-written name list. The search runs only on the error path; cache the per-locale tables for the duration of the process so several unknown words do not repeat the work.
- [x] Interface sketch: `names.locales_with_name(word) -> list[str]`; `lexer.tokenize` takes/returns the diagnostics (for example it raises an `ErrorList` of located `IntervalKeeperError`s); the hint text is built in the lexer from that list.
- [x] Tests: several unknown words in one INTERVAL and across lines are all reported (exit 2, empty stdout, one `PATH:LINE` diagnostic per word); `May` under `LC_ALL=hu_HU.UTF-8` hints at an English locale and `március` under `LC_ALL=en_US.UTF-8` hints at `hu_HU` (subprocess tests, `skipTest` if the locales are not installed; the sandbox can build them with `localedef`); a word that is a name in no locale gets no hint; the effective locale is unchanged after the search (the next word still parses); a missing `locale` command omits the hint without failing.

Completed (`names.installed_locales` / `names.locales_with_name`, `lexer.tokenize`, `parser.parse_interval`, `states._collect`, `tests/test_unknown_words.py`). `tokenize` collects every unknown word and raises one `ErrorList` (a single problem stays a plain error); `parse_interval` locates each; `build_lines` flattens them. The locale list comes from `locale -a` (so tests put a fake `locale` first on `PATH` to control it, and `LOCPATH` points at `localedef`-built locales); the built-in `C`/`POSIX` locales are named only if no other locale knows the word; the index of names per installed locale is built once, lazily, and the effective locale is restored afterwards. Other lexical errors (bad character, bad zone, ambiguous name) end the line's tokenizing but are reported together with the unknown words found so far.

### M9 — Default config text, docs, polish

This milestone can draft prose and README material during M6, but executable-example checks and final acceptance depend on M1 and M7 being integrated.

- [ ] The default config text and docs describe `D before ANCHOR` / `D after ANCHOR` (SPEC §9.1), several parts in one INTERVAL (`Apr 1, 2 days before X`, SPEC §9.2), macro names with spaces and punctuation (SPEC §5.3) and that month/weekday names follow the `LC_TIME` locale (SPEC §11).
- [ ] Write the final default config text (SPEC §3.3), including the brief's examples with the working `Easter` wrapper
      (`Easter := ! date -d "$(ncal -e)" +%F`) and the security note about macro commands.
- [ ] Test: extract the examples block, strip `# `, ignore `## ` lines, run `--check` (with the fake `ncal`) → exit 0. Also: `--print-default-config` equals the file created in M1.
- [ ] `README.md`: purpose, install (list of dependencies, Debian package names `python3-dateutil python3-tzlocal tzdata`), usage examples, pointer to SPEC.
- [ ] Review stderr messages for every V12 case: file, line, and the token.

**Acceptance:** `make test` green on a clean checkout; a manual run on the reviewer's own config produces sensible output.

## 4. Testing notes

* Always pass `--at` and `--tz` in tests; never depend on the wall clock. For tests that need a fixed environment also set `TZ`.
* The reference calendar facts in SPEC §13 are checked by tests with `datetime` (a test asserts `date(2026,10,9).weekday() == 4`, etc.) so a wrong fact in the spec is caught.
* Error tests assert three things: exit code 2, empty stdout, stderr contains `PATH:LINE` and a keyword.
* Table-driven tests are preferred (list of `(config, args, expected_stdout)`); add each V-vector as one row.

## 5. Risks and where to be careful

| Risk | Mitigation |
|------|-----------|
| Relative intervals whose anchor starts long before the window | Widen look-back until the first relevant anchor instance is complete; test long durations and anchors with recurring and explicit years. |
| Adjacent ranges across midnight or DST must merge or `--next-change` reports false changes | Merge in `RangeSet`; oracle test (V13) |
| Zone IDs / timezone tokens colliding with macro or month/weekday words | Lexer order and reserved-name rules are explicit; no abbreviation-to-zone table exists |
| Macro text substitution altering zone names | Spec'd limitation (§5.2); do not "fix" silently |
| `ncal -e` output is locale-dependent | Never rely on it in tests; use the fake `ncal` and `date -d` wrapper |

## 6. Definition of done

* All milestones ticked; `make test` passes from a clean checkout on Python 3.9 and the newest available 3.x.
* Every vector in SPEC §13 is covered by a test.
* `kairos` with no config in a fresh environment creates the default file and exits 0 with no output.
* No hand-written date arithmetic remains: grep the package for manual month-length tables, leap-year formulas, or `* 86400` style day arithmetic.

## 7. Open questions (append here)

### Decisions recorded from SPEC §0 (D1–D19)

- D1: Semantics are intersection; use `1-7 Fri` for the first Friday of each month.
- D2: A day selector on a single clause selects the starting day of a rollover range; nested clauses intersect.
- D3: A comma continues a list only when the next item has the same kind as the preceding item; otherwise it starts a new term.
- D4: Command macros resolve lazily. Default mode prunes inactive subtrees; `--next-change` and `--check` evaluate fully.
- D5: Do not add locale-dependent `MM/DD/YY`; use the documented `Easter := ! date -d "$(ncal -e)" +%F` example.
- D6: `D until ANCHOR` includes the entire anchor instance, including the all-day end date.
- D7: `~` inherits from the nearest ancestor with a STATE; error if none exists.
- D8: A macro redefinition fails when the name is visible in the current/enclosing scope; sibling scopes may reuse names.
- D9: The `CEST → Europe/Berlin` and similar mappings were examples, not requirements. Use IANA TZDB for zone rules and returned abbreviations; do not map bare abbreviations to representative zones. Bare alphabetic abbreviations other than `UTC`/`GMT` are rejected as input because no globally unique abbreviation-to-zone registry exists.
- D10: Dependencies are stdlib, `python-dateutil`, `tzlocal`, and system `tzdata`.
- D11: Executable is `kairos`; config is `$XDG_CONFIG_HOME/kairos/intervals.conf`.
- D12: A missing explicitly named config is an error and is never created.
- D19: An INTERVAL is a comma-separated list of parts (plain terms and whole relative expressions), evaluated as their union; the anchor of a relative expression is a single term, so a comma between terms always ends it (`2 days before Apr 10, Apr 20` = Apr 8 and Apr 20); a comma before `NUMBER unit` never continues a list. SPEC §6.4, §9.2.
- D18: A command macro failure is an evaluation-time error (when a non-skipped line first uses the macro), never a definition-time one; an unused macro never runs, not even under `--check`. SPEC §5.4.
- D17: Macro names are any text before the first `:=` (no `=`, no leading `!`, at least one letter), may contain spaces and punctuation and may contain other macro names; longest name first. SPEC §5.3.
- D16: `D before ANCHOR` / `D after ANCHOR` shift each anchor instance as a whole (both endpoints, length kept); they are not runs like `+`/`until`. SPEC §9.1.
- D15: `Nh` is the whole hour `N:*`, `Nm`/`Nmin` is minute `*:N`; separate kinds `HOUR`/`MINUTE` (ranges/lists inclusive, wrapping). See SPEC §6.1-6.2.
- D14: Alphabetic tokens that are legacy IANA zone IDs (`CET`, `EET`, `EST`, …) resolve as those zones; other bare abbreviations (`CST`, `CEST`, `IST`) are rejected. See SPEC §8.1.
- D13: `--next-change` searches indefinitely without a `--horizon` option; if there truly is no future change, print nothing.

### Open questions to resolve explicitly before or during implementation

- [x] SPEC §8: Cite IANA TZDB and Python `zoneinfo`; explain that zone abbreviations are zone/date-dependent labels, not unique IDs; add local commands for listing IANA zone IDs and inspecting an abbreviation at an instant.
- [x] SPEC §8.1: legacy IANA IDs that look like abbreviations (`CET`, `EET`, `WET`, `MET`, `EST`, `MST`, `HST`, `PST8PDT`) conflict with "reject bare abbreviations". Resolved: the IANA ID lookup comes first, so those IDs are accepted as zones; only alphabetic names absent from `available_timezones()` are rejected (D14).
- [ ] Validate the V14 transition expectations against the actual `zoneinfo` behavior on supported Python versions and make any discrepancy an explicit spec decision, not an undocumented implementation adjustment.
- [x] SPEC §6.1 `HHh`/`MMm`/`MMmin`: resolved (D15). `8h` = `8:*`, `30m`/`30min` = `*:30`; they are the kinds `HOUR`/`MINUTE`, with inclusive wrapping ranges and lists, combinable with `TIME` in one clause (all must hold). Evaluation: each group yields the daily windows, which are intersected.
- [x] Point times: `08:00` lasts one minute, `08:00:30` lasts exactly one second (SPEC §6.2; `TimeSpec.seconds`).
- [x] `UTC + 2 hours` is a zone plus a duration; `UTC+2 hours` is an error because `hours` has no number (SPEC §6.2).
- [x] SPEC V14 says a bare-time anchor `08:00 + 2 hours` "begins at 10:00:00", but §9 (`[s, s + D)`) and §7.1 (the anchor instance starts at `08:00:00`) give `[08:00:00, 10:00:00)`, which is what M6 implements and `tests/test_evaluate.py` / `tests/test_cli_states.py` assert. Most likely V14 meant "ends at 10:00:00". Needs a `spec:` correction by the author. Resolved: author confirmed `[08:00, 10:00)`; spec fixed.
- [x] SPEC §5.3 says macro names may contain spaces and punctuation (`Mary's birthday`) and that longer names are tried first, but §4.1 (and the reader) require `[A-Za-z_][A-Za-z0-9_]*`, and `NAME := …` lines with other names are rejected ("invalid macro name"). The implementation follows §4.1; the author should confirm or extend the grammar. Resolved (D17, M12): the reader and validator follow §5.3.
- [x] SPEC V12 lists a bare `X := ! false` as an error, but D4 makes command macros lazy, so an unused one never runs in default mode. Implemented: it is an error when used, and under `--check` (which runs all commands, §2). Confirm that is enough for V12. Resolved (D18, M12): V12 now needs a line that uses `X`.
- [ ] `tzlocal` could not be installed in the development sandbox (no distribution reachable); `default_timezone` therefore fell back to UTC with a warning there. Tests always pass `--tz`, so they are unaffected.
- [x] SPEC V14's last paragraph said `08:00 + 2 hours` "begins at 10:00:00": author confirmed the result is `[08:00, 10:00)`; the sentence is fixed.
- [x] Locale-aware month/weekday names are now planned as M10.
- [x] SPEC §5.3 macro names (spaces, punctuation, longest name first) are not implemented by M3; names are identifier-like (now with Unicode letters). Decide whether this is a new milestone. Done as M12.
