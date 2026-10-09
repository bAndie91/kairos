# kairos — execution plan

Status: **DRAFT 0.1 — for review.** Companion to `SPEC.md`, which is the source of truth for behaviour.
This plan is written so that an agent with no other context can pick it up and continue.

## 0. How to use this plan (read first)

1. Read `SPEC.md` completely, especially §0 (decisions D1–D13) and §13 (conformance vectors).
   Decisions marked as awaiting review in the repo's review thread may change; if `SPEC.md` has changed, it wins over this plan.
2. Work through the milestones **in order**. Each milestone lists tasks (checkboxes) and an **acceptance** block.
   Do not start a milestone before the previous one's acceptance passes.
3. Tick the checkbox in this file in the same commit that completes the task.
4. If the spec is ambiguous or contradicts itself: do **not** guess. Choose the stricter behaviour (raise a parse error),
   and append an entry to the "Open questions" list at the end of this file with the spec section, the question and what you chose.
5. Commit small and often, one task or tightly related group per commit, imperative subject line (`Parse ISO dates with wildcards`).
6. Never change `SPEC.md` behaviour silently. Spec corrections are separate commits whose message starts with `spec:`.

## 1. Hard constraints (from the brief; violating them is a bug)

* Single executable Python 3 script `kairos` in the repo root. Python ≥ 3.9.
* **Never hand-write datetime logic.** All calendar, weekday, leap-year, month-length, time-zone, DST and month/year arithmetic goes through
  `datetime`, `zoneinfo`, `dateutil.relativedelta`. Only interval set algebra (lists of `(start, end)` instants) is custom.
* On parse or semantic errors: message on stderr with file and line(s), try go on parsing to show other failing lines too, exit 2 at the end, **empty stdout**.
  Parse the whole config before printing normal output. Print errors as it goes.
* Config lookup via XDG; create the default config when none is found (and no `--config` was given).
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
- [ ] Default config text as a module constant, emitted by `--print-default-config`. It contains the description, the condensed format spec and an examples block (SPEC §3.3), with all lines commented out.
      Write the final text **after** M9; for now a placeholder that only has the marker lines.
- [ ] Tests with a temporary `HOME` / `XDG_*` environment: precedence order, creation, no creation for explicit path, relative XDG vars ignored.

**Acceptance:** all lookup/creation cases tested; running with a fresh empty `HOME` creates the file and prints no states.

### M2 — Line reader and indentation tree (SPEC §4)

- [ ] Tokenise the file into logical lines: skip blank and `#` lines; reject tabs in indentation; reject indented first line; Python-style indentation stack with "dedent to an open level" check.
- [ ] Classify lines: macro definition (`NAME := …`, checked first) vs interval line. Split interval line at the first `=`; detect leading `!`; error on empty INTERVAL / empty STATE.
- [ ] Macro lines cannot have children.
- [ ] STATE processing: escapes (`\~`, `\@`, `\\`, others error), `@` hidden marker (bare `@` → error), `~` substitution against the parent's effective name (errors per D7). Produce `effective_name`, `reported` flags.
- [ ] Build a tree of nodes `{lineno, indent, negated, interval_text, state_raw, children}`, keep macro lines in the sequence in file order.

**Acceptance:** unit tests for indentation errors (V12 items on indentation), `=` splitting, `~`/`@` rules (V5 names only, without time evaluation).

### M3 — Macros (SPEC §5)

- [ ] Name validation: pattern, reserved words (months, weekdays, units, `until`, `UTC`/`GMT`/`Z`, abbreviation table from M5 — share one constant), redefinition against **visible** macros.
- [ ] Scope stack tied to the indentation tree; sibling subtrees may reuse names.
- [ ] Whole-word, single-pass expansion on raw text, for both INTERVAL and STRING values.
- [ ] Command macros: `/bin/sh -c`, stdin `/dev/null`, timeout, env `MACRO_*`, `INTERVAL_KEEPER_AT`, `INTERVAL_<STATE>` for indented definitions (sanitised names, innermost wins). Error rules for exit status, empty and multi-line output.
- [ ] Pruning hook for default mode (SPEC §5.4): the parser asks a callback `parent_active(node)`; when false the subtree is structurally validated only where it depends on skipped commands. `--next-change` and `--check` pass a callback that always returns true.
      (The callback is implemented in M7; use a stub returning true until then.)

**Acceptance:** the macro parts of V10 and V12, including: `annamary` not substituted, env vars visible to commands (use `env`/`printenv` in tests), command not run when pruned (marker file), run under `--check`.

### M4 — Time zones (SPEC §8)

- [ ] `resolve_tz(token)`: IANA (case-insensitive lookup against `zoneinfo.available_timezones()`), `UTC±H[H][[:]MM]` / `GMT±…` with ISO sign (use `datetime.timezone(timedelta)`), the abbreviation table, `Z`. Unsupported abbreviations → error naming the token.
- [ ] Default zone: `--tz`, else `tzlocal.get_localzone()` (honours `$TZ`), fallback UTC + warning.
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

- [ ] `--format` (`strftime`, `iso`, `epoch`), `--horizon`.

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
| Relative intervals whose anchor starts long before the window | |
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

_none yet — the reviewer's answers to SPEC §0 D1–D13 go here as decisions, one line each._
