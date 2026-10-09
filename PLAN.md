# kairos — execution plan

Status: **DRAFT 0.1 — for review.** Companion to `SPEC.md`, which is the source of truth for behaviour.
This plan is written so that an agent with no other context can pick it up and continue.

## 0. How to use this plan (read first)

1. Read `SPEC.md` completely, especially §0 (decisions D1–D13) and §13 (conformance vectors).
   Decisions marked as awaiting review in the repo's review thread may change; if `SPEC.md` has changed, it wins over this plan.
2. Work through the milestones **in order**. Each milestone lists tasks (checkboxes) and an **acceptance** block.
   Do not start a milestone before the previous one's acceptance passes.
3. Tick the checkbox in this file in the same commit that completes the task.
4. If the spec is ambiguous or contradicts itself: do **not** guess or automatically choose a parse error. Record the exact conflict in
   "Open questions", compare the relevant normative text and conformance vectors, and resolve it explicitly. Prefer the SPEC's
   stated decisions and examples; make a spec correction in a separate commit if those conflict. Use a parse error only when the
   specification requires rejection or no consistent interpretation is possible.
5. Commit small and often, one task or tightly related group per commit, imperative subject line (`Parse ISO dates with wildcards`).
6. Never change `SPEC.md` behaviour silently. Spec corrections are separate commits whose message starts with `spec:`.

## 1. Hard constraints (from the brief; violating them is a bug)

* Single executable Python 3 script `kairos` in the repo root. Python ≥ 3.9.
* **Never hand-write datetime logic.** All calendar, weekday, leap-year, month-length, time-zone, DST and month/year arithmetic goes through
  `datetime`, `zoneinfo`, `dateutil.relativedelta`. Only interval set algebra (lists of `(start, end)` instants) is custom.
* On parse or semantic errors: message on stderr with file and line(s), try go on parsing to show other failing lines too, exit 2 at the end, **empty stdout**.
  Parse the whole config before printing normal output. Print errors as it goes.
* Config lookup via XDG; create the default config only when no config is found and no `--config` was given. A missing explicit
  `--config PATH` is an error; never create that path.
* May suggest other libs besides the spec's dependency list (stdlib, `python-dateutil`, `tzlocal`, system `tzdata`).

## 2. Repository layout (target)

```
kairos            executable script, single file, sections separated by banner comments
tests/
  helpers.py               loads the script as a module; run() helper for the CLI; ncal stub
  test_*.py                unittest test modules (stdlib unittest; pytest also works)
  fixtures/                config files used by tests
Makefile                   `make test` → python3 -m unittest discover -s tests -v
SPEC.md  PLAN.md  README.md
```

Suggested section order inside the script (keeps merge conflicts and navigation sane):
`errors/exit codes` → `xdg & default config` → `line reader / indentation tree` → `macros` → `timezones` → `lexer` → `interval parser (AST)` →
`range sets` → `AST evaluation` → `hierarchy & states` → `next-change` → `cli`.

## 3. Milestones

Each milestone ends with a green `make test` and a commit.

### M0 — Skeleton and test harness

- [ ] Create `kairos` with shebang, `main()`, `argparse` for **all** options in SPEC §2 (unimplemented ones may raise "not implemented" → exit 2).
- [ ] `class IntervalKeeperError(Exception)` carrying `(path, line, message)`; single top-level handler prints `kairos: PATH:LINE: error: MESSAGE` and exits 2. Nothing else may print to stdout before success.
- [ ] `tests/helpers.py`: `load_module()` via `importlib.machinery.SourceFileLoader`; `run_cli(args, config_text=None, env=None)` returning `(code, stdout, stderr)` (feeds config through `--config -`); a fake `ncal` executable in a temp dir prepended to `PATH`
      that prints `04/05/26`.
- [ ] `Makefile` with `test` target.

**Acceptance:** `kairos --help` and `--version` work; a trivial test runs; an unknown option exits 2 with empty stdout.

### M1 — Config discovery and default config (SPEC §3)

- [ ] XDG lookup: `--config`, `$XDG_CONFIG_HOME`, `$XDG_CONFIG_DIRS`; ignore relative XDG paths; `--config -` reads stdin.
- [ ] Create the default file when nothing found and no `--config` given (dir 0700 if created, file 0644); notice on stderr; missing explicit `--config` → error without creating anything.
- [ ] Default config text as a module constant, emitted by `--print-default-config`. Include the complete user-facing explanation,
      condensed format specification, and examples required by SPEC §3.3; comment every line so a fresh config is inert.
      Keep the final text task in M9, using a marker-only placeholder until then.
- [ ] Tests with a temporary `HOME` / `XDG_*` environment: precedence order, creation, no creation for explicit path, relative XDG vars ignored.

**Acceptance:** all lookup/creation cases tested; running with a fresh empty `HOME` creates the file and prints no states.

### M2 — Line reader and indentation tree (SPEC §4)

- [ ] Tokenise the file into logical lines: skip blank and `#` lines; allow indentation made of spaces or tabs, but reject indentation
      that mixes spaces and tabs; reject an indented first line; use a Python-style indentation stack with a "dedent to an open level" check.
- [ ] Classify lines: macro definition (`NAME := …`, checked first) vs interval line. Split interval line at the first `=`; detect leading `!`; error on empty INTERVAL / empty STATE.
- [ ] Macro lines cannot have children.
- [ ] STATE processing: escapes (`\~`, `\@`, `\\`, others error), `@` hidden marker (bare `@` → error), `~` substitution against the parent's effective name (errors per D7). Produce `effective_name`, `reported` flags.
- [ ] Build a tree of nodes `{lineno, indent, negated, interval_text, state_raw, children}`, keep macro lines in the sequence in file order.

**Acceptance:** unit tests for indentation errors (V12 items on indentation), `=` splitting, `~`/`@` rules (V5 names only, without time evaluation).

### M3 — Macros (SPEC §5)

- [ ] Name validation: pattern, reserved words (months, weekdays, units, `until`, `UTC`/`GMT`/`Z`, abbreviation table from M5 — share one constant), redefinition against **visible** macros.
- [ ] Scope stack tied to the indentation tree; sibling subtrees may reuse names.
- [ ] Whole-word, single-pass expansion on raw text, for both INTERVAL and STRING values; resolve command macros lazily on first use.
- [ ] Command macros: run `${SHELL:-/bin/sh} -c COMMAND`, stdin `/dev/null`, stderr inherited; non-zero exit is an error.
      Pass inherited environment plus resolved visible macros as `KAIROS_MACRO_<NAME>`, `KAIROS_NOW` as ISO 8601 with offset,
      and contextual `KAIROS_INTERVAL_<LEVEL>` / `KAIROS_STATE_<LEVEL>` for each ancestor and the current line (levels start at 0).
      Strip trailing newlines and collapse embedded newlines to spaces. Empty output is valid. Do not add an unspecified timeout.
- [ ] Pruning hook for default mode (SPEC §5.4): the parser asks a callback `parent_active(node)`; when false the subtree is structurally validated only where it depends on skipped commands. `--next-change` and `--check` pass a callback that always returns true.
      (The callback is implemented in M7; use a stub returning true until then.)

**Acceptance:** the macro parts of V10 and V12, including: `annamary` not substituted, env vars visible to commands (use `env`/`printenv` in tests), command not run when pruned (marker file), run under `--check`.

### M4 — Time zones (SPEC §8)

- [ ] `resolve_tz(token)`: IANA (case-insensitive lookup against `zoneinfo.available_timezones()`), `UTC±H[H][[:]MM]` / `GMT±…` with ISO sign (use `datetime.timezone(timedelta)`), the abbreviation table, `Z`. Unsupported abbreviations → error naming the token.
- [ ] Default zone precedence: explicit `--tz`, then `$TZ`, then `tzlocal` system-zone discovery; fallback to UTC with a stderr warning.
- [ ] Document the abbreviation table's source and provide a practical local command/example for listing or searching zone names from
      the same `zoneinfo` database used by the program.
- [ ] Tests: `CEST` in December behaves as `CET`; `UTC+0300` is east of Greenwich; `Etc/UTC`; `Europe/Budapest`; unknown names error.

**Acceptance:** V9 resolution tests (zone objects and offsets on specific dates).

### M5 — Interval lexer and parser → AST (SPEC §6)

- [ ] Lexer with the token order of §6.1 (ISO date before number, `--` before `-`, TZ forms, words).
- [ ] Item kinds and ranges, number classification (< 100 DOM, ≥ 100 YEAR), month/weekday names (full, 3-letter, `Sept`, case-insensitive).
- [ ] Clause conjunction rules and all clause errors (duplicate kind, DATE vs Y/M/D, impossible dates incl. `Feb 30`, `2026-02-29`, `*-04-31`; `Feb 29` ok).
- [ ] Comma grouping rule D3 (same-kind continuation) producing terms.
- [ ] Spans: sides, inheritance of year/month, rollover rules, times on both sides, recurring spans.
- [ ] Relative forms: `union + duration`, `duration until union`, compound durations, TZ placement.
- [ ] AST dataclasses: `Clause`, `Span`, `Union`, `RelPlus`, `RelUntil`. The parser never evaluates dates against the clock; it only validates.

**Acceptance:** every interval string in the brief parses; every parse-error case of V12 fails with a message containing the offending token; table-driven tests `text → AST repr`.

### M6 — Range sets and AST evaluation (SPEC §7.1, §9)

- [ ] `RangeSet`: sorted, disjoint, half-open, adjacent ranges merged; `union`, `intersect`, `subtract`, `clip`, `contains(t)`, `boundaries()`. Property tests against a naive implementation on random small sets.
- [ ] `eval(node, lo, hi, default_tz) -> RangeSet` with the exact-restriction contract `spec ∩ [lo, hi)`.
  - `Clause`: iterate local dates of the clause's zone from `lo − 1 day` to `hi + 1 day` (using `datetime.date`), test the day-level items, emit ranges per time range, localize with `zoneinfo`, clip.
  - `Span`: iterate candidate years (recurring) or the single explicit year; endpoints via `datetime`; skip years where an endpoint does not exist.
  - `Union`: union of terms.
  - `RelPlus` / `RelUntil`: evaluate anchor over a widened window, take instance starts/ends, add/subtract the duration with `relativedelta` (calendar units) and UTC arithmetic (elapsed units); widen until the first instance in the window is complete; clip.
- [ ] DST tests: gap and fold days in `Europe/Budapest` (2026-03-29, 2026-10-25) — `02:00-03:00`, `01:00-04:00`, `Mon-Fri 08:00-16:00` across the switch.

**Acceptance:** evaluation tests for V1, V2, V3, V7, V8, V9 interval texts on single lines (no hierarchy yet).

### M7 — Hierarchy, states and default output (SPEC §7.2–7.4)

- [ ] Effective sets `E(L)` (intersect with parent / subtract when negated).
- [ ] Reported states, `U(name)` union across lines, ordering by first appearance, de-duplication.
- [ ] Default mode: small window `[at, at+1s)`; implement the `parent_active` pruning callback for M3.
- [ ] CLI: `--at`, `--tz`, print states, `--check`.

**Acceptance:** V1 (states column), V4, V5, V6, V7, V8, V9, V10, V11, V12 pass through the CLI with exact stdout.

### M8 — `--next-change` (SPEC §10)

- [ ] Implement `--format` (`strftime`, `iso`, `epoch`) and indefinite `--next-change` search. Do not add a horizon option.
- [ ] Search intelligently from candidate boundaries derived from the parsed interval AST and its calendar/recurrence structure; do not
      scan every second or blindly iterate every date forever. Account for explicit years, recurring clauses/spans, relative intervals,
      merged ranges, and same-name state unions. Establish a defensible stopping/no-future-change condition; if no future change exists,
      print nothing and exit 0 (the SPEC requires empty output but does not explicitly settle the exit code, so record that for resolution).

**Acceptance:** all `--next-change` columns of V1–V8 exactly as listed; oracle test green; performance: `--next-change` on a 100-line config with a leap-day state (`Feb 29`) completes in under 5 s.

### M9 — Default config text, docs, polish

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
| Zone names / abbreviations colliding with macro or month/weekday words | Lexer order and reserved-name list share one constant table |
| Macro text substitution altering zone names | Spec'd limitation (§5.2); do not "fix" silently |
| `ncal -e` output is locale-dependent | Never rely on it in tests; use the fake `ncal` and `date -d` wrapper |

## 6. Definition of done

* All milestones ticked; `make test` passes from a clean checkout on Python 3.9 and the newest available 3.x.
* Every vector in SPEC §13 is covered by a test.
* `kairos` with no config in a fresh environment creates the default file and exits 0 with no output.
* No hand-written date arithmetic remains: grep the script for manual month-length tables, leap-year formulas, or `* 86400` style day arithmetic.

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
- D9: Use the specified representative IANA zones for abbreviations; document the table source and local zone-listing/search method.
- D10: Dependencies are stdlib, `python-dateutil`, `tzlocal`, and system `tzdata`.
- D11: Executable is `kairos`; config is `$XDG_CONFIG_HOME/kairos/intervals.conf`.
- D12: A missing explicitly named config is an error and is never created.
- D13: `--next-change` searches indefinitely without a `--horizon` option; if there truly is no future change, print nothing.

### Open questions to resolve explicitly before or during implementation

- [ ] SPEC §10 / D13: Define an efficient, correct stopping/search strategy for indefinitely recurring and explicit-year expressions, including how to establish that no future state-set change exists without unbounded brute-force scanning.
- [ ] SPEC §7.1: Resolve the bare time-point description: it says a bare `08:00` is a one-minute interval, but gives `08:00:00-08:00:59` as an equivalent example, which is only 60 seconds if the end is exclusive. State the exact endpoint semantics and add a conformance vector.
- [ ] SPEC §7.1: Confirm DST gap/fold behavior for ranges crossing transitions and encode the intended behavior in tests, using `zoneinfo` / PEP 495 rather than custom timezone arithmetic.
- [ ] SPEC §10 / §11: Decide and document the exit status when `--next-change` finds no future change; D13 settles empty stdout but the exit code is not explicit.
- [ ] SPEC §8.2: Add a source URL for the abbreviation mapping and a locally runnable way to list/search IANA zones; do not imply abbreviations are canonical IANA identifiers.
