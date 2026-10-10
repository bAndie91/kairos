# kairos — execution plan

Status: **DRAFT 0.1 — in progress, M0/M1/M2/M3/M4 accepted. M5 intentionally deferred.** Companion to `SPEC.md`, which is the source of truth for behaviour.
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

- [x] Name validation: pattern, reserved words (months, weekdays, units, `until`, `UTC`/`GMT`/`Z`, and the agreed timezone-token rules), redefinition against **visible** macros. Consume the shared constant/interface agreed with M4; do not duplicate the table.
- [x] Scope stack tied to the indentation tree; sibling subtrees may reuse names.
- [x] Whole-word, single-pass expansion on raw text, for both INTERVAL and STRING values; resolve command macros lazily on first use.
- [x] Command macros: run `${SHELL:-/bin/sh} -c COMMAND`, stdin `/dev/null`, stderr inherited; non-zero exit is an error.
      Pass inherited environment plus resolved visible macros as `KAIROS_MACRO_<NAME>`, `KAIROS_NOW` as ISO 8601 with offset,
      and contextual `KAIROS_INTERVAL_<LEVEL>` / `KAIROS_STATE_<LEVEL>` for each ancestor and the current line (levels start at 0).
      Strip trailing newlines and collapse embedded newlines to spaces. Empty output is valid. Do not add an unspecified timeout.
- [x] Pruning hook for default mode (SPEC §5.4): the parser asks a callback `parent_active(node)`; when false the subtree is structurally validated only where it depends on skipped commands. `--next-change` and `--check` pass a callback that always returns true.
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

- [ ] Implement `RangeSet` in `kairoslib/ranges.py`: sorted, disjoint, half-open, adjacent ranges merged; `union`, `intersect`, `subtract`, `clip`, `contains(t)`, `boundaries()`. Property tests against a naive implementation on random small sets.
- [ ] Implement `eval(node, lo, hi, default_tz) -> RangeSet` in `kairoslib/evaluate.py` with the exact-restriction contract `spec ∩ [lo, hi)`.
  - `Clause`: iterate local dates of the clause's zone from `lo − 1 day` to `hi + 1 day` (using `datetime.date`), test the day-level items, emit ranges per time range, localize with `zoneinfo`, clip.
  - `Span`: iterate candidate years (recurring) or the single explicit year; endpoints via `datetime`; skip years where an endpoint does not exist.
  - `Union`: union of terms.
  - `RelPlus` / `RelUntil`: evaluate anchor over a widened window, take instance starts/ends, and apply duration pairs in the specified order: all calendar units (day/week/month/year) first via `relativedelta`, then elapsed units (hour/minute/second) in UTC. Widen until the first instance in the window is complete; clip.
- [ ] Implement the exact bare-time semantics: `08:00` is `[08:00:00,08:01:00)`; as a relative anchor its instance start is 08:00:00 and its one-minute duration is ignored.
- [ ] DST tests from SPEC V14: `Europe/Budapest` gap (2026-03-29) and fold (2026-10-25), including exact UTC boundary assertions for `02:00-03:00`, `01:00-04:00`, and `Mon-Fri 08:00-16:00`. Check both activity and inactivity at each stated boundary; use `zoneinfo` / PEP 495 semantics, not custom timezone arithmetic.

**Acceptance:** evaluation tests for V1, V2, V3, V7, V8, V9 interval texts on single lines (no hierarchy yet).

### M7 — Hierarchy, states and default output (SPEC §7.2–7.4)

- [ ] Implement effective sets `E(L)` (intersect with parent / subtract when negated).
- [ ] Implement reported-state unions, `U(name)` across lines, ordering by first appearance, and de-duplication in `kairoslib/states.py`.
- [ ] Default mode: small window `[at, at+1s)`; implement the `parent_active` pruning callback for M3.
- [ ] CLI: `--at`, `--tz`, print states, `--check`.

**Acceptance:** V1 (states column), V4, V5, V6, V7, V8, V9, V10, V11, V12 pass through the CLI with exact stdout.

### M8 — `--next-change` (SPEC §10)

- [ ] Implement candidate boundary generation and search in `kairoslib/next_change.py`; implement `--format` (`strftime`, `iso`, `epoch`) and indefinite `--next-change` search. Do not add a horizon option.
- [ ] Implement AST-derived candidate-boundary streams: clauses jump directly to matching local dates/times; spans emit endpoints;
      relative intervals emit duration-adjusted anchor-instance boundaries. Merge candidates chronologically and compare the complete
      reported state set immediately before and at each candidate, ignoring boundaries hidden by overlapping ranges or same-name unions.
- [ ] Separate finite exceptions from recurring terms. Track the end of explicit-year contributions and every finite relative-interval
      duration tail before treating the remaining schedule as recurring.
- [ ] Implement a no-future-change proof: recurring Gregorian calendar patterns (including weekday/leap-day selectors and calendar
      durations) repeat on the 400-year / 146,097-day cycle. Include each used TZif zone's future-rule footer in the recurrence
      fingerprint: after explicit transitions, use its recurring POSIX rule, or its final offset if no footer rule exists. It is acceptable
      to parse TZif recurrence metadata to establish the cycle, but use `zoneinfo` for actual conversions. Only use a cycle as proof
      after finite exceptions/tails end and timezone recurrence fingerprints align. Search one complete combined recurrence cycle
      for real changes; if none occur, conclude there is no future change in the representable datetime domain.
- [ ] No arbitrary horizon and no second-by-second or date-by-date brute-force scan. Python `datetime` represents years 1–9999;
      search until the next real change is found or the recurrence proof establishes none remains. If none remains, empty stdout,
      exit 0.

**Acceptance:** all `--next-change` columns of V1–V8 and the no-future-change cases pass; V13 brute-force oracle agrees; V14 DST/bare-time boundary tests pass. A 100-line config with a leap-day state (`Feb 29`) completes in under 5 s without scanning every second or every date. Include a case where overlapping same-name intervals create candidate boundaries but no reported state change.

### M9 — Default config text, docs, polish

This milestone can draft prose and README material during M6, but executable-example checks and final acceptance depend on M1 and M7 being integrated.

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

### Decisions recorded from SPEC §0 (D1–D13)

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
