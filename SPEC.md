# kairos — specification

Status: **DRAFT 0.1 — for review.** Nothing is implemented yet. See `PLAN.md` for the execution plan.

`kairos` is a modular Python 3 command-line tool for Linux: a **time-based arbitrary state registry**. The command is a small executable launcher backed by a Python package; implementation units belong in separate modules as described in §1.1.
A config file maps time intervals to free-text *state* names. Run the tool and it prints
the states that are active right now. With `--next-change` it prints when that set of
active states will next change.

---

## 0. Review guide: decisions I had to make

Your brief is detailed but leaves some corners open, and one example does not work as written.
Each item below is a decision I took so the spec could be complete. Please confirm or overrule each.
author: i stroke through what i don't want (most your decisions i agree with) and put a Review comment to make things more explicite where needed.

| # | Topic | Decision taken (spec section) | Alternative | Review comment |
|---|-------|-------------------------------|-------------|----------------|
| D1 | `*-*-01` with child `Fri` | Plain intersection: "the 1st of the month **when it is a Friday**". "First Friday of the month" is `1-7 Fri`. The wording in your example comment ("1st Friday of every month") does not match intersection semantics. (§7.2) | ~~Add a dedicated "n-th weekday" syntax~~ |
| D2 | Rollover time range plus day selector on **one line** (`Fri 22:00-02:00`) | Day selectors pick the *starting* day; the range may spill into the next day (Fri 22:00 → Sat 02:00). When the same pieces are on **nested lines** (`Fri` / `  22:00-02:00`) the result is a pure set intersection (Fri 00:00–02:00 ∪ Fri 22:00–24:00). (§7.1) | ~~Always pure intersection~~ |
| D3 | Commas | A comma continues the current list only if the next item is of the **same kind** as the item before the comma; otherwise it separates terms. So `Mon-Fri 08:00-12:00,13:00-17:00` is a cross product, and `Apr 1, Jun 15` is two days. (§6.4) | ~~Comma always separates terms~~ |
| D4 | Command macros (`NAME := ! cmd`) vs. "intervals not covering the current time are skipped" | ~~Commands run eagerly, in file order, during the single parse pass. In the default mode, subtrees under a parent that is **not active at the evaluation time** are skipped (their commands do not run).~~ `--next-change` and `--check` never skip. (§5.4) | Lazy evaluation (run a command when its macro is first used) | do lazy eval |
| D5 | `Easter := ! ncal -e` | `ncal -e` prints a **locale-dependent, US-style** date (`04/05/26` on my test machine), which the INTERVAL grammar (ISO dates only) rejects. The example parses as a macro definition but would fail on use. Use a wrapper such as `! date -d "$(ncal -e)" +%F`. Also: a command's output is a snapshot, so a recurring date computed by a command is only valid for the year it was computed in (§5.5). | ~~Accept `MM/DD/YY` (rejected: locale-dependent, ambiguous)~~ | ignore what you `ncal` outputs. keep that `date` command in the examples. no introduce mm/dd/yy format. |
| D6 | `40 days until Dec 24` | End is the **end of the whole anchor instance** (so Dec 24 itself is included, mirroring `--` whose end date is inclusive). Range = Nov 15 00:00 → Dec 25 00:00. (§9) | ~~End at the *start* of Dec 24~~ | "until Dec 24" means "up to and including Dec 24" |
| D7 | `~` in a STATE whose parent has no STATE | ~~Parse error.~~ | Inherit from the nearest ancestor with a STATE |
| D8 | Macro redefinition | Error if the name is already **visible** (same scope or an enclosing active scope). Sibling scopes may reuse a name. (§5.3) | ~~Error only in the very same scope (allow shadowing)~~ |
| D9 | TZ abbreviations | Use IANA TZDB for zone rules and its supplied abbreviations for display; do not maintain a hand-written abbreviation-to-zone map. Since abbreviations are ambiguous and do not identify a unique zone, accept only IANA zone IDs, numeric UTC offsets, and explicit UTC/GMT/Z forms in §8.1. | ~~Hand-written representative-zone mapping~~ | Examples such as `CEST → Europe/Berlin` were illustrative only, not required mappings. |
| D10 | Dependencies | stdlib (`datetime`, `zoneinfo`) + `python-dateutil` (`relativedelta`) + `tzlocal` (local zone discovery) + system `tzdata`. (§12) | ~~stdlib only (hand-rolled local-zone discovery)~~ |
| D11 | Names | Script `kairos` (no `.py`); config `$XDG_CONFIG_HOME/kairos/intervals.conf`. (§3) | | agreed |
| D12 | `--config PATH` that does not exist | Error (exit 2); the default file is created only when **no** config is specified and none is found. (§3.2) | ~~Create it at PATH~~ |
| D13 | `--next-change` with nothing ahead | No arbitrary horizon; print nothing and exit 0 if no future change exists. (§10) | ~~A fixed horizon and exit 1~~ | Search candidate boundaries, then prove exhaustion using the finite Gregorian recurrence cycle after all finite exceptions and duration tails. Include the future recurrence rules of the active TZif zones; don't scan every second/date to eternity. |

**Additions beyond your brief** (strike any you do not want): options `--at`, `--tz`, `--format`,
`--check`, `--print-default-config`, `--version`; env var
`KAIROS_NOW` for macro commands; bare time-point anchors in relative intervals
(`08:00 + 2 hours`); KAIROS_compound NUM (`4 days 9 hours`); time-of-day in `--` spans.

---

## 1. Scope

In scope: parsing the config, computing the active states at a given instant, computing the next instant
at which the set of active states changes.

Out of scope for v1: daemon/watch mode, notifications, running actions on change, config includes,
locale-specific month/day names, calendars other than Gregorian, sub-second precision,
sandboxing of macro commands.

Document these OOS points.

---


### 1.1 Implementation architecture

The repository must use a modular Python package; **do not consolidate the implementation into one script**. Keep the user-facing command named `kairos` and preserve all CLI behaviour and config compatibility.

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
  fixtures/
Makefile
SPEC.md  PLAN.md  README.md
```

The launcher must work from a source checkout without requiring installation or a manually configured `PYTHONPATH`; it should add the repository root to the import path in a small, predictable way before importing `kairoslib.cli`. Keep it as a thin launcher with no business logic. The package must be importable by tests without invoking the CLI.

Module responsibilities above are a default decomposition, not a requirement to create a separate module for every trivial helper. A module may be split further if that gives a unit clear ownership or reduces conflicts; avoid circular imports. Shared low-level types (`errors.py`, AST types in `parser.py`, and common interval/timezone contracts) must have one canonical definition. Keep dependencies flowing from low-level utilities toward higher-level orchestration; lower-level modules must not import `cli.py`.

Do not use wildcard imports to assemble the package. Cross-module APIs should be explicit and documented with type hints where practical. Tests should import the owning module for unit tests and exercise the `kairos` launcher for CLI integration tests.

## 2. Command line

```
kairos [OPTIONS]
```

| Option | Meaning |
|--------|---------|
| `-c FILE`, `--config FILE` | Use FILE instead of the XDG lookup. `-` reads the config from stdin. |
| `--at DATETIME` | Evaluate at DATETIME instead of now. ISO 8601: `YYYY-MM-DD[ T]HH:MM[:SS][offset]`. Without an offset it is interpreted in the display zone. Sub-seconds are truncated. |
| `-n`, `--next-change` | Print the next instant (after "now" or after DATETIME if `--at` is specified) at which the set of reported states changes, instead of the states. |
| `--tz ZONE` | Default time zone (IANA name, or any form from §8.1). Used for intervals without an explicit zone and for printing. Default: `$TZ`, else the system zone. |
| `--format FMT` | Output format of `--next-change`. A `strftime` string, or the keywords `iso` (ISO 8601 with offset) or `epoch` (Unix seconds). Default `%Y-%m-%d %H:%M:%S`. |
| `--check` | Fully parse the config (no subtree skipping, all macro commands run), print nothing, exit 0 if valid. |
| `--print-default-config` | Print the default config text to stdout and exit. |
| `-V`, `--version`, `-h`, `--help` | As usual. |

### 2.1 Output

* Default mode: one active state per line on stdout, in config order (§7.4), each name once. No active state → no output, exit 0.
* `--next-change`: a single line with the datetime in the display zone, e.g. `2026-10-09 12:00:00`; if no future change exists, empty stdout and exit 0.
* **stdout hygiene:** the config is parsed completely before anything is printed. On any error stdout stays empty.
  Diagnostics go to stderr.

### 2.2 Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success (including "no state active"). |
| 2 | Error: usage, I/O, parse error, macro command failure. |

Error message format on stderr: `kairos: PATH:LINE: error: MESSAGE` (or `kairos: error: MESSAGE` when no line applies).

---

## 3. Config file location

### 3.1 Lookup order

1. `--config FILE` (§3.2).
2. per XDG specs:
   1. `$XDG_CONFIG_HOME/kairos/intervals.conf` (default `$HOME/.config/...`).
   2. For each directory in `$XDG_CONFIG_DIRS` (default `/etc/xdg`), in order: `DIR/kairos/intervals.conf`.

The first file that exists wins; files are not merged. XDG variables holding relative paths are ignored, as the XDG spec requires.

### 3.2 Creating the default config

If no file was found and `--config` was **not** given, the tool creates
`$XDG_CONFIG_HOME/kairos/intervals.conf` (directory mode 0700 if it has to be created, file mode 0644)
with the default content (§3.3), prints `kairos: created default config: PATH` to stderr, and proceeds
using it. If `--config` names a file that does not exist: error, nothing created (D12).

### 3.3 Default config content

The default config has **no active lines**: everything is inside a comment block.
It must contain, in comments:

1. The complete format specification (condensed from §4–§9): line format, indentation, macros,
   INTERVAL syntax with all field kinds, negation, STATE rules (`~`, `@`), relative intervals, time zones.
2. An examples section. Inside it, every example config line is written as `#` followed by the
   original line (indentation preserved after the `#`). **Test requirement:** stripping the leading `#`
   from those lines must yield a config that parses successfully.
   Explanatory prose inside the block goes in lines starting with `## `, which the test ignores.
3. The examples from the brief (all of them, with `Easter` using the working wrapper from D5).

---

## 4. Config syntax

The file is UTF-8 text; with LF line endings.

### 4.1 Line kinds

| Kind | Recognised by |
|------|---------------|
| blank | only whitespace → ignored |
| comment | first non-blank char is `#` → ignored. **No inline comments** (STATE is free text and may contain `#`). |
| macro definition | `INDENT NAME := VALUE`, where NAME matches `[A-Za-z_][A-Za-z0-9_]*` |
| interval line | everything else: `INDENT [!] INTERVAL [= STATE]` |

### 4.2 Interval line

```
INDENT [!] INTERVAL [= STATE]
```

* `INDENT`: spaces or tabs. mixed indentation → parse error. inconsistent indentation → parse error (like python). first line must have indentation 0.
* `!` (optionally followed by whitespace) negates the interval (§7.3).
* The line is split at the **first** `=`. INTERVAL never contains `=`. Both parts are trimmed.
* No `=` → the line has no STATE: it is **not reported**, but its INTERVAL still restricts its children.
* `=` followed by empty STATE → error. Empty INTERVAL → error.

### 4.3 Indentation and hierarchy

Python-style: a line indented deeper than the previous (non-blank, non-comment) line becomes its child;
dedenting must return to an indentation level that is currently open, otherwise error.
The first line must have indentation 0. Any consistent number of spaces per level is fine.
Macro lines take part in indentation (§5.3) but cannot have children.

### 4.4 STATE text

Free text. Escapes: `\~` is a literal `~`, `\@` is a literal `@` (only meaningful as the first character), `\\` is a backslash. Any other
backslash sequence is an error. Macros are **not** expanded in STATE.

* `~` is replaced by the **effective name** of the parent line (after the parent's own `~` substitution and without its leading `@`).
  Parent has no STATE → error (D7). Top-level line using `~` → error.
* A STATE starting with `@\s*` is **hidden**: not reported, but its name (without `@\s*`) is what children see as `~`.
  A bare `@` (empty name) is an error.
* Whitespace inside STATE is preserved; leading/trailing whitespace is trimmed.

---

## 5. Macros

### 5.1 Definition

```
NAME := STRING            literal string
NAME := ! COMMAND         shell command; its stdout is the value
```

* STRING: other macros visible at that point are expanded in it (once, §5.2) and the result is the value.
  A STRING cannot start with a literal `!` (that always means COMMAND).
* COMMAND: run with `${SHELL:-/bin/sh} -c COMMAND`, stdin from `/dev/null`, stderr passed through,
  Multiline output collaptsed into 1 line by `s/\n/ /g`. Trailing newline is stripped. 
  Exit status ≠ 0 → error.
  Macros are **not** expanded in COMMAND text. Instead the environment contains:
  * everything inherited from the caller;
  * `KAIROS_MACRO_<NAME>` for every macro visible at that point (their resolved values);
  * `KAIROS_NOW`: the evaluation instant (ISO 8601 with offset);
  * for interval definitions: `KAIROS_INTERVAL_<LEVEL>` and `KAIROS_STATE_<LEVEL>` for each ancestor line and the line itself where the command-sourced macro is being resolved: LEVEL is the indentation level from 0.
    * `KAIROS_INTERVAL_<LEVEL>`'s value is the ancestor's (or self) INTERVAL text after macro expansion, with a leading `! ` if negated.
    * `KAIROS_STATE_<LEVEL>`'s value is the ancestor's STATE text (as reported in normal mode: ie. after `~` substitution, escape and `^@\s*` processing, may be empty).
* Empty values are valid.

### 5.2 Expansion

Before an INTERVAL (or macro STRING) is lexed, every **whole word** that equals a visible macro name is replaced by its value.
A whole word is a run of chars (including unicode letters) bounded by whitespace, punctuation, `-`, `,`, `/`, or the start/end of the string, so `mary_birthday` is not replaced inside `annamary_birthday`.
Expansion is a **single pass**: replaced text is not rescanned. (Values are already fully expanded when defined.)
Names are case-sensitive for macros.

### 5.3 Names and scope

* names are case sensitive and allowed to have space, punctuation, etc. (eg. `Mary's birthday`)
* longer macro names are tried first, so `birthday` and `Mary's birthday` can coexist.
* Reserved (case-insensitive) → error: month names and weekday names (full and 3-letter, `Sept`), duration units (§9), `until`, `UTC`, `GMT`, and `Z`. Other timezone-looking strings are TZ tokens only if they match §8.1; there is no abbreviation table.
* A macro defined at indentation 0 is visible to all following lines. A macro defined at deeper indentation, as a child of
  line P, is visible to the lines that follow it inside P's subtree. Leaving the subtree ends the scope.
* Redefining a name that is **visible** at that point (same scope or enclosing scope) → error (D8). Two sibling subtrees may define the same name.

### 5.4 When commands run (D4)

Parsing is one pass over the file, top to bottom; each macro command runs when its macro name is being resolved (lazy).

* **Default mode** (print states): when the parser reaches a subtree whose parent's effective set does **not** contain the
  evaluation instant, the subtree is *skipped*: macro commands inside it do not run, and lines that depend on a skipped
  command macro are only structurally validated (indentation, line kind). All other lines are fully parsed and validated.
* **`--next-change` and `--check`**: never skip.

### 5.5 Known limitation

A command macro is a snapshot taken at evaluation time. Example: `ncal -e` yields only the *current* year's Easter, so
`--next-change` run in December cannot know next year's Easter. Commands may read `KAIROS_NOW` to pick a year.

---

## 6. INTERVAL syntax

### 6.1 Lexical rules

After macro expansion the text is tokenised, whitespace being insignificant except as a separator. Longest match, in this order:

| Token | Form |
|-------|------|
| `ISODATE` | `Y-m-D`, `Y` = 4 digits or `*`, `m` and `D` = 1–2 digits or `*`; no inner whitespace |
| `TIME` | `HH:MM`, `HH:MM:SS`, `HHh`, `MMm`, `MMmin` |
| `NUMBER` | digits |
| `--` `-` `+` `,` `*` | punctuation (`--` is a span operator, `-` a range operator) |
| `TZ` | IANA zone IDs, numeric UTC offsets, and explicit UTC/GMT/Z forms of §8.1 |
| `WORD` | letters (month / weekday / unit / `until`, case-insensitive) |

Unknown word → error (`unknown word 'X' (undefined macro?)`).

### 6.2 Item kinds

| Kind | Atom | Range `a-b` |
|------|------|-------------|
| `YEAR` | integer 100–9999 | `a ≤ b` required |
| `MONTH` | name (`Jan`, `January`, … `Sept` accepted) | wraps (`Dec-Feb` = Dec, Jan, Feb) |
| `DOM` | integer 1–31 (leading zero ok) | wraps (`28-3` = 28…31, 1…3) |
| `WEEKDAY` | name (`Mon`, `Monday`, …) | wraps (`Fri-Mon`) |
| `TIME` | `H:MM[:SS]` (`24:00` only as a range end) | wraps past midnight (`23:00-04:00`) |
| `DATE` | `ISODATE` (wildcards allowed) | not allowed (use `--`, §6.5) |

Numbers: < 100 is a DOM, ≥ 100 is a YEAR; 0 and 32–99 are errors. `2026-2028` is a year range.
Names are English, case-insensitive, locale-independent. A single dash needs no whitespace but may have it (`Mon - Fri`), except inside an `ISODATE`.

### 6.3 Clause = conjunction

A *clause* is a whitespace-separated sequence of items, optionally ending with a `TZ`. All items must hold simultaneously
(`Apr-Jun 1-15` = month ∈ Apr–Jun **and** day ∈ 1–15). Rules (violations are errors):

* at most one item group per kind; `DATE` excludes `YEAR`/`MONTH`/`DOM` in the same clause;
* at least one non-`TZ` item;
* `*` is only valid inside an `ISODATE`;
* a `DATE`/`DOM`/`MONTH` combination that can never exist is an error (`Feb 30`, `2026-02-29`, `*-04-31`) - but dont try to be smart here, offload this validation to the datetime library;
  `Feb 29` and `*-*-31` are fine.

A clause with no `TIME` item covers whole days. A clause with no day-level item (`YEAR`, `MONTH`, `DOM`, `WEEKDAY`, `DATE`)
covers every day. A clause without month, only day, covers that day in every months. TIME without minutes covers the whole hour. And so on.

### 6.4 Lists and commas (D3)

`a,b` builds a list inside one kind (`Wed,Fri`, `Jun,Jul,Aug`, `1,15`, `Mon-Wed,Fri`, `08:00-12:00,13:00-17:00`).
**Rule:** a comma continues the current list iff the next item has the same kind as the item right before the comma;
otherwise the comma ends the current *term*, and the next item starts a new clause.

| Text | Meaning |
|------|---------|
| `Apr,Jun 1,15` | (Apr or Jun) and (1 or 15) → Apr 1, Apr 15, Jun 1, Jun 15 |
| `Apr 1, Jun 15` | two terms: Apr 1; Jun 15 |
| `Mon-Fri 08:00-12:00,13:00-17:00` | one clause, two time ranges |
| `Mon 08:00-09:00, Tue 10:00-11:00` | two terms |

A list may not mix point times and time ranges. The union of all terms is the interval.

### 6.5 Spans (`--`)

`A -- B` is a *span* between two dates.

* Side forms: `ISODATE`, or `[YEAR] [MONTH] DOM`, each optionally followed by one `TIME`. No lists, ranges or weekdays. A `TZ` may end the whole span and applies to both sides.
* Left side needs a concrete month and day; the year is optional (absent or `*` → recurring every year).
* Right side may omit year and month: they are inherited from the left side (`2026 Apr 1 -- 20`, `Apr 1 -- Jun 15`, `2026 Apr 1 -- May 15`).
* If the right date is then before the left date: a right side with no month moves to the next month; a right side with no explicit year moves to the next year (so `Dec 20 -- Jan 10` and `2026 Dec 20 -- Jan 10` work).
* Without times: whole days, **end date inclusive** → `[00:00 of first day, 00:00 after last day)`.
  With times: both sides must have one; `[start, end)`.
* Recurring span in a year where an endpoint does not exist (`Feb 29`) → round the date to the latest existing date/time that is before the endpoint in that year  (ie. Febr 28), like Febr 29 would compressed in a virtual zero length instant between Febr 28 and Mar 1.
* thus `2026 Apr 1 -- 20`, `2026 Apr 1-20` and `2026-04-01 -- 20` are equivalent.

### 6.6 Complete grammar

```
interval = expr ;                         (* leading "!" is handled by the line, §4.2 *)
expr     = union
         | union "+" duration             (* §9 *)
         | duration "until" union ;
union    = term { "," term } ;            (* comma grouping per §6.4 *)
term     = span | clause ;
span     = dateside "--" dateside [ TZ ] ;
dateside = ( ISODATE | [ YEAR ] [ MONTH ] DOM ) [ TIME ] ;
clause   = item { item } [ TZ ] ;
item     = value { "," value } ;          (* values of one kind *)
value    = atom [ "-" atom ] ;
duration = NUMBER unit { NUMBER unit } ;
unit     = second | minute | hour | day | week | month | year ;   (* optional plural "s" *)
```

---

## 7. Semantics

### 7.1 Time model

* Time is the real instant line, resolution one second. Every set is a union of **half-open** ranges `[start, end)`; adjacent ranges merge.
  `08:00-16:00` is active at 08:00:00 and not at 16:00:00.
* A clause is evaluated in its zone (§8): for every local calendar day that satisfies the day-level items, and every time range of the clause
  (default `00:00-24:00`), one range `[day+t1, day+t2)` is produced; if `t2 < t1` the end is on the following day (`t1 = t2` is an error). So the day selectors pick the  **starting** day (D2).
* Missing time units are wildcards within their natural ranges. Thus bare `08:00` means the half-open interval `[08:00:00, 08:01:00)`, exactly the same as `08:00-08:01`; it is active at `08:00:59` and not at `08:01:00`. A bare time point used as a relative-interval anchor is point-like: its instance start is `08:00:00`, not a one-minute-long anchor for purposes of `ANCHOR + DURATION`.
* Without minutes, eg. `8h`, the whole hour is selected (`08:00-09:00`); without hours, eg. `30m`, `30min`, the whole minute is selected within eavery hour: `*:30`.
* Wall-clock → instant conversion, DST gaps and folds follow PEP 495 as implemented by `zoneinfo`: a nonexistent local endpoint uses the offset before the transition; an ambiguous endpoint uses the first occurrence (`fold=0`). Resolve each endpoint independently, then form the half-open UTC interval; ranges that become empty are dropped. This means a spring-gap range `02:00-03:00` in `Europe/Budapest` on 2026-03-29 is empty, while the fall-fold range `02:00-03:00` on 2026-10-25 spans both occurrences of local 02:00 and ends at 03:00 standard time. See V14 for mandatory boundary tests. **No calendar or zone arithmetic is hand-written**: use `datetime`, `zoneinfo`, `dateutil.relativedelta`.
* An interval spec denotes an infinite (possibly periodic) set; implementations evaluate it **per window** (§10) with this contract:
  `eval(spec, lo, hi)` returns exactly `spec ∩ [lo, hi)`.

### 7.2 Hierarchy

Let `S(L)` be the set of line L's INTERVAL. Its **effective set** is

```
E(L) = E(parent) ∩ S(L)          if L is not negated
E(L) = E(parent) \ S(L)          if L is negated   ("! INTERVAL")
```

with `E(root)` = all time. Hence a child restricts its parent, and `Mon-Fri` / `  Dec` means "weekdays in December".
Siblings are independent. A line without STATE contributes only through its children.
(D1: `*-*-01` with child `Fri` is the days that are both a 1st and a Friday.)

### 7.3 Negation

`! INTERVAL` as a child subtracts from the parent (`! Sun,Sat` under `*-*-01` = 1st of the month unless it is a weekend).
At top level it is the complement of INTERVAL.

### 7.4 Reported states

* The state *name* is the STATE after `~` substitution and escape processing.
* A line is **reported** iff it has a STATE that does not start with `@` and the resolved *name* is not empty.
* Several lines may yield the same name; the state is active when **any** of them is effective (`U(name)` = union of their effective sets).
* Output order: the order in which a name's first line appears in the file (depth-first, as written). 
* State at instant `t`: `{ name : t ∈ U(name) }`.

---

## 8. Time zones

### 8.1 Accepted `TZ` forms

* IANA zone IDs, e.g. `Europe/Budapest`, `Etc/UTC`, `America/Argentina/Buenos_Aires`, and `UTC`, looked up case-insensitively against `zoneinfo.available_timezones()`.
* Numeric offsets: `UTC±H`, `UTC±HH`, `UTC±HHMM`, `UTC±HH:MM`, and the same with `GMT`. Use the ISO sign convention: `UTC+0300` is three hours east of Greenwich (unlike POSIX `Etc/GMT-3`).
* `Z`, `UTC`, and `GMT` denote UTC. `GMT+1` and similar strings are offset forms.

Alphabetic timezone abbreviations other than `UTC`/`GMT` are **not accepted as input TZ tokens**. There is no standardized, globally unique abbreviation-to-zone registry: the IANA Time Zone Database records abbreviations as part of individual zones' historical and future rules, and the same abbreviation can identify different zones or offsets. Do not infer a zone from a string such as `CST` or `CEST`, and do not ship a hand-written mapping. Use an IANA zone ID when calendar/DST rules are intended, or a numeric offset when a fixed offset is intended.

For diagnostics and display, timezone abbreviations exposed by `zoneinfo`/`datetime.tzname()` come from the installed IANA TZDB (system zoneinfo data, or the Python `tzdata` package fallback where available). Their values may vary with the chosen zone, date, and installed TZDB version; they are labels, not unique identifiers. See the [IANA tz database theory](https://www.iana.org/time-zones/theory), which explicitly warns that abbreviations such as `CST` are ambiguous, and [Python `zoneinfo` documentation](https://docs.python.org/3/library/zoneinfo.html).

No `TZ` → the default zone (`--tz`, else `$TZ`, else system zone via `tzlocal`; fallback UTC with a stderr warning). `$TZ` follows the same accepted forms; POSIX rule strings and bare abbreviations are not interpreted specially.
The zone applies to the whole clause (or span): the calendar days, the times of day and any duration arithmetic of §9.

### 8.2 Abbreviation data and local inspection

Kairos does not define or maintain an abbreviation table. Zone abbreviations are supplied by the selected IANA TZDB zone data and are used only as names returned by the timezone implementation, not as identifiers accepted in interval syntax. To inspect the abbreviation for a particular zone and instant, run:

```sh
python3 -c 'from datetime import datetime; from zoneinfo import ZoneInfo; d=datetime(2026, 10, 9, tzinfo=ZoneInfo("Europe/Budapest")); print(d.tzname(), d.utcoffset())'
```

To list zone IDs available to the same database used by Python:

```sh
python3 -c 'from zoneinfo import available_timezones; print("\\n".join(sorted(available_timezones())))'
```

The installed data source is normally system TZDB; Python's `tzdata` package is the fallback when system zoneinfo data is unavailable. The abbreviation set is not a portable or unique index of zones; select an IANA zone ID explicitly.

---

## 9. Relative intervals

```
ANCHOR + DURATION            e.g.  1-7 Mon + 5 day
DURATION until ANCHOR        e.g.  40 days until Dec 24
```

* DURATION = one or more `NUMBER unit` pairs (`5 days`, `4 days 9 hours`). Units: second, minute, hour, day, week, month, year (singular or plural, either regardless of the number).
* An ANCHOR is a union (§6). Its **instances** are the maximal contiguous ranges of the anchor's set (a point time is an instance of length zero).
* `ANCHOR + D`: for every instance starting at `s`, the result is `[s, s + D)`. The anchor's own length is ignored. (`1-7 Mon + 5 day` = Mon 00:00 → Sat 00:00 → the working week starting on the first Monday.)
* `D until ANCHOR`: for every instance ending at `e` the result is `[e − D, e)` (D6).
* Arithmetic is done in the anchor's zone: day/week/month/year units are calendar (wall-clock) arithmetic (`dateutil.relativedelta`); hour/minute/second units are elapsed time (convert to UTC, add, convert back).
  In a pair list, calendar units are applied first, then elapsed units.
* The result is an ordinary set: it may be negated, have children, carry a STATE.
* Implementation note: an instance may begin long before the evaluation window; evaluation must look back until the first instance.

---

## 10. `--next-change`

A state ending at `T` while another line of the **same name** starts at `T` is no change; hidden (`@`) and STATE-less lines are never change points on their own;
every change point is a range boundary of some `U(name)`. The reported state set is the union of all effective lines grouped by their reported name, so a candidate boundary is a real change only if that complete set differs immediately before and at the boundary.

### 10.1 Candidate-boundary search and termination

Do not sample every second or scan every date as the primary search algorithm. Generate the next possible boundary from the AST:

* A clause yields local start/end boundaries from its matching dates and time ranges; jump directly to the next matching calendar date.
* A span yields its endpoint boundaries. A relative interval yields the starts/ends after applying its duration to anchor-instance starts/ends. Preserve half-open, second-resolution semantics.
* Merge candidate streams in chronological order. At each candidate instant `T`, compare the complete reported state set at `T-1 second` and `T`; return the first candidate where they differ. Boundaries hidden by adjacent/overlapping ranges or another line with the same state name are skipped.
* Split expressions into finite exceptions and recurring parts. Explicit-year clauses/spans and relative intervals derived only from finite anchors contribute only finitely many candidate boundaries; account for their complete duration tails before treating them as finished. Recurring calendar clauses and spans repeat with the Gregorian 400-year cycle (146,097 days). Calendar-duration arithmetic repeats on that cycle as well. Do not assume a recurring anchor has finite tails; derive the boundary stream from its recurring instances.
* For every IANA zone used, account for the TZif future-rule footer: after its last explicit transition, future transitions are either governed by its recurring POSIX rule or, when no footer rule is present, by its final offset. The recurrence fingerprint must include these transition rules and offsets, not just the Gregorian dates. The implementation may parse TZif recurrence metadata for this purpose, but must continue to use `zoneinfo` for actual wall-clock/instant conversion. A 400-year Gregorian cycle is a valid termination period only after all finite exceptions have ended and the time-zone recurrence fingerprints align.
* Once beyond all finite exceptions/tails, search at most one complete combined recurrence cycle for a real state-set change. If no candidate changes the reported state set during that cycle, no later change exists in the representable datetime domain; return no result. Avoid a blind scan over every day of the cycle by using the candidate streams.

The 400-year calendar period follows the Gregorian calendar's exact 146,097-day cycle. For future zone rules, use the TZif footer's POSIX-style rule where present; TZif and its footer are specified by [RFC 9636](https://www.rfc-editor.org/rfc/rfc9636.html). The footer describes future extrapolation, unlike the finite list of historical transition timestamps.

Python's `datetime` domain is finite (years 1 through 9999). "Indefinitely" means no user-configurable horizon or arbitrary cut-off: search until a change is found or the recurrence proof shows none remains, bounded only by the representable datetime domain. If no future change exists, print nothing and exit 0.

Output is formatted in the display zone with `--format`. During a DST fold the default format is ambiguous: show warning.

---

## 11. Errors (all exit 2, stdout empty)

Syntax and semantic errors, each reported with file and line:

bad indentation / first line indented; macro with children; unknown word;
macro name reserved, or already visible; macro command failed; duplicate item kind in a clause;
mixed-kind range; time range with equal ends; numbers out of range; `*` outside `ISODATE`; 
span with lists/ranges, missing time on one side, end before start with explicit year; `~` without parent; empty INTERVAL;
unknown time zone or unsupported abbreviation; bad `--at`/option values.

---

## 12. Implementation constraints

* One executable file `kairos`, `#!/usr/bin/env python3`, Python ≥ 3.9. No other source files are needed to run it.
* Allowed third-party: `python-dateutil`, `tzlocal`; system `tzdata`, may add other imports if need emerges during implementation.
* **All** calendar, weekday, month-length, leap-year, zone, DST and month/year arithmetic goes through `datetime`, `zoneinfo`, `dateutil`. Scanning days with a `for` loop over `datetime.date` is fine but to be minimized;
  re-implementing leap-year or zone rules is not.
* Interval *set algebra* (union / intersection / subtraction / clipping of lists of `(start, end)` instants) is the tool's own code.
* Macro commands are arbitrary code run with the user's privileges. There is no sandbox (documented in the default config).

---

## 13. Conformance vectors

Tests must encode these verbatim. `tz` is the default zone (`--tz`); `at` is `--at`. "→ ∅" means empty stdout, exit 0.
Reference calendar facts: 2026-10-09 is a Friday; 2026-10-01 a Thursday; 2026-11-01 a Sunday; 2026-12-01 a Tuesday; 2026-07-05 a Sunday.

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
| 2026-10-09 12:00:00 | `work`,`lunch` | `2026-10-09 13:00:00` |
| 2026-10-09 12:05 | `work`,`lunch` | `2026-10-09 13:00:00` |
| 2026-10-09 13:01 | `work` | `2026-10-09 16:00:00` |
| 2026-10-09 16:00:00 | ∅ | `2026-10-10 08:00:00` |

**V2** `23:00-04:00 = evening`: at 2026-10-10 02:00 → `evening`, next `2026-10-10 04:00:00`; at 2026-10-09 22:59:59 → ∅; at 2026-10-09 12:00 → next `2026-10-09 23:00:00`.

**V3** `Dec-Feb = winter`: at 2027-01-15 12:00 → `winter`; at 2026-10-09 12:00 → next `2026-12-01 00:00:00`; at 2027-02-28 12:00 → next `2027-03-01 00:00:00`.

**V4** hierarchy and no-STATE parent:
```
Mon-Fri
  Dec = weekdays in December
```
at 2026-12-01 10:00 → `weekdays in December`; at 2026-12-05 10:00 (Sat) → ∅; at 2026-12-04 12:00 → next `2026-12-05 00:00:00`.

**V5** `~` and `@`:
```
Jun,Jul,Aug = summer
  Sun = @Sunday
    20:00-23:00 = evening in summer's ~s
```
at 2026-07-05 21:00 → `summer`, `evening in summer's Sundays`; at 2026-07-05 19:00 → `summer`; next-change at 19:00 → `2026-07-05 20:00:00`; at 2026-07-05 23:00 → next `2026-07-12 20:00:00`.

**V6** negation:
```
*-*-01 = first
  ! Sun,Sat = first, on weekdays
```
at 2026-10-01 12:00 → `first`, `first, on weekdays`; at 2026-11-01 12:00 → `first`.

**V7** relative:
```
1-7 Mon + 5 day = run
```
at 2026-10-09 10:00 → `run`; at 2026-10-10 00:00:00 → ∅; next at 2026-10-09 10:00 → `2026-10-10 00:00:00`; next at 2026-10-10 12:00 → `2026-11-02 00:00:00`.
```
40 days until Dec 24 = runup
```
at 2026-11-14 23:59:59 → ∅; at 2026-11-15 00:00:00 → `runup`; at 2026-12-24 12:00 → `runup`, next `2026-12-25 00:00:00`.

**V8** spans: `Apr 1 -- Jun 15 = spring` active at 2027-06-15 23:59:59, not at 2027-06-16 00:00:00. `Dec 20 -- Jan 10 = holidays`: active at 2027-01-05 12:00; next at 2026-10-09 12:00 → `2026-12-20 00:00:00`.
`2026 Apr 1 -- 20 = x` active at 2026-04-20 12:00, not at 2026-04-21 00:00:00, not at 2027-04-10.

**V9** zones (`tz=UTC`): `*-12-* 08:00-09:00 Europe/Berlin = t` → active at 2026-12-01 07:30:00, not at 2026-12-01 06:59:59. `*-07-* 08:00-09:00 Europe/Berlin = t` → active at 2026-07-01 06:30:00. `08:00-09:00 UTC+0300 = t` → active at 2026-10-09 05:30:00. Bare alphabetic abbreviations such as `CEST` and `CST` as TZ tokens must error and ask for an IANA zone ID or numeric offset.

**V10** macros:
```
Q1 := Jan-Mar
Q1 = first quarter
```
at 2026-02-10 → `first quarter`. Whole-word rule: `mary := Mon` followed by `annamary = x` → error (unknown token `annamary`). Command macro: `A := Tue`, `D := ! echo "$KAIROS_MACRO_A"`, `D = x` → active on a Tuesday. Scope/pruning: a command macro inside `Jun,Jul,Aug = summer` runs under `--at` in July (and `KAIROS_INTERVAL_0` is `Jun,Jul,Aug`, `KAIROS_STATE_0` is `summer`), does not run under `--at` in October, runs in October with `--check`.

**V11** all-lines test: the complete example list from the brief (with the D5 wrapper for `Easter`) parses as one config under `--check`.

**V12** each of these is an error (exit 2, empty stdout): `08:00-25:00 = x`; `Mon Tue = x`; `Foo = x`; `Mon = ~` (top level); `  Mon = x` as the first line; `Mon := x`; `7 := x`; `Q := Jan` twice; `Feb 30 = x`; `2026-02-29 = x`; `Mon =`; `= x`; `X := ! false`; `08:00-08:00 = x`; unknown zone `Mon Foo/Bar = x`.

**V13** brute-force oracle (property test): for each config above and random `at` values, `--next-change` equals the first `t' > at` found by stepping one second (or one minute when the config has no seconds) at which the printed state set differs.

**V14** DST endpoint semantics and crossing ranges (all times below are UTC instants; use `Europe/Budapest` as the interval zone and evaluate exact boundaries with `--at`):

- Spring gap, 2026-03-29 (02:00 local does not exist; transition 01:00 UTC):
  - `02:00-03:00 = gap` is empty for that date because 02:00 resolves with the pre-transition UTC+1 offset to the same instant as 03:00 with UTC+2. It is not active at 2026-03-29 00:59:59 UTC or 01:00:00 UTC.
  - `01:00-04:00 = crossing` is active at 2026-03-29 00:30:00 UTC and 01:30:00 UTC, and inactive at 02:00:00 UTC (the interval is `[00:00,02:00)` UTC).
  - `Mon-Fri 08:00-16:00 = work`: verify the local wall-clock window remains 08:00–16:00 across the transition, while its UTC boundaries move from 07:00/15:00 before DST to 06:00/14:00 after DST.
- Fall fold, 2026-10-25 (02:00 local occurs twice; transition 01:00 UTC):
  - `02:00-03:00 = fold` spans `[00:00,02:00)` UTC: active at 00:30:00 and 01:30:00 UTC, inactive at 02:00:00 UTC.
  - `01:00-04:00 = crossing` spans `[2026-10-24 23:00:00, 2026-10-25 03:00:00)` UTC: active at 00:30:00, 01:30:00, and 02:30:00 UTC, inactive at 03:00:00 UTC.
  - `Mon-Fri 08:00-16:00 = work`: verify local wall-clock endpoints remain 08:00–16:00 and that UTC boundaries are one hour later than in summer after the fall-back.

Also test a bare `08:00` as exactly `[08:00:00,08:01:00)`: active at 08:00:00 and 08:00:59, inactive at 08:01:00; as a relative anchor, `08:00 + 2 hours` begins at 10:00:00.

---

## 14. Possible future work (not in v1)

weekday spans (`Mon 08:00 -- Fri 17:00`), n-th weekday syntax, config includes, man page.
