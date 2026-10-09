# interval-keeper — specification

Status: **DRAFT 0.1 — for review.** Nothing is implemented yet. See `PLAN.md` for the execution plan.

`interval-keeper` is a single-file Python 3 command-line tool for Linux: a **time-based arbitrary state registry**.
A config file maps time intervals to free-text *state* names. Run the tool and it prints
the states that are active right now. With `--next-change` it prints when that set of
active states will next change.

---

## 0. Review guide: decisions I had to make

Your brief is detailed but leaves some corners open, and one example does not work as written.
Each item below is a decision I took so the spec could be complete. Please confirm or overrule each.

| # | Topic | Decision taken (spec section) | Alternative |
|---|-------|-------------------------------|-------------|
| D1 | `*-*-01` with child `Fri` | Plain intersection: "the 1st of the month **when it is a Friday**". "First Friday of the month" is `1-7 Fri`. The wording in your example comment ("1st Friday of every month") does not match intersection semantics. (§7.2) | Add a dedicated "n-th weekday" syntax |
| D2 | Rollover time range plus day selector on **one line** (`Fri 22:00-02:00`) | Day selectors pick the *starting* day; the range may spill into the next day (Fri 22:00 → Sat 02:00). When the same pieces are on **nested lines** (`Fri` / `  22:00-02:00`) the result is a pure set intersection (Fri 00:00–02:00 ∪ Fri 22:00–24:00). (§7.1) | Always pure intersection |
| D3 | Commas | A comma continues the current list only if the next item is of the **same kind** as the item before the comma; otherwise it separates terms. So `Mon-Fri 08:00-12:00,13:00-17:00` is a cross product, and `Apr 1, Jun 15` is two days. (§6.4) | Comma always separates terms |
| D4 | Command macros (`NAME := ! cmd`) vs. "intervals not covering the current time are skipped" | Commands run eagerly, in file order, during the single parse pass. In the default mode, subtrees under a parent that is **not active at the evaluation time** are skipped (their commands do not run). `--next-change` and `--check` never skip. (§5.4) | Lazy evaluation (run a command when its macro is first used) |
| D5 | `Easter := ! ncal -e` | `ncal -e` prints a **locale-dependent, US-style** date (`04/05/26` on my test machine), which the INTERVAL grammar (ISO dates only) rejects. The example parses as a macro definition but would fail on use. Use a wrapper such as `! date -d "$(ncal -e)" +%F`. Also: a command's output is a snapshot, so a recurring date computed by a command is only valid for the year it was computed in (§5.5). | Accept `MM/DD/YY` (rejected: locale-dependent, ambiguous) |
| D6 | `40 days until Dec 24` | End is the **end of the whole anchor instance** (so Dec 24 itself is included, mirroring `--` whose end date is inclusive). Range = Nov 15 00:00 → Dec 25 00:00. (§9) | End at the *start* of Dec 24 |
| D7 | `~` in a STATE whose parent has no STATE | Parse error. | Inherit from the nearest ancestor with a STATE |
| D8 | Macro redefinition | Error if the name is already **visible** (same scope or an enclosing active scope). Sibling scopes may reuse a name. (§5.3) | Error only in the very same scope (allow shadowing) |
| D9 | TZ abbreviations | Fixed table mapping to representative IANA zones, e.g. `CET`/`CEST` → `Europe/Berlin`. Ambiguous abbreviations (`IST`, `CST` as China, …) are deliberately **not** supported; use IANA names. (§8.2) | Different representative zones / bigger table |
| D10 | Dependencies | stdlib (`datetime`, `zoneinfo`) + `python-dateutil` (`relativedelta`) + `tzlocal` (local zone discovery) + system `tzdata`. (§12) | stdlib only (hand-rolled local-zone discovery) |
| D11 | Names | Script `interval-keeper` (no `.py`); config `$XDG_CONFIG_HOME/interval-keeper/intervals.conf`. (§3) | |
| D12 | `--config PATH` that does not exist | Error (exit 2); the default file is created only when **no** config is specified and none is found. (§3.2) | Create it at PATH |
| D13 | `--next-change` with nothing ahead | Looks ahead at most 10 years (`--horizon`); prints nothing and exits 1 if there is no change. (§10) | |

**Additions beyond your brief** (strike any you do not want): options `--at`, `--tz`, `--format`,
`--check`, `--print-default-config`, `--horizon`, `--cmd-timeout`, `--version`; env var
`INTERVAL_KEEPER_AT` for macro commands; bare time-point anchors in relative intervals
(`08:00 + 2 hours`); compound durations (`4 days 9 hours`); time-of-day in `--` spans.

---

## 1. Scope

In scope: parsing the config, computing the active states at a given instant, computing the next instant
at which the set of active states changes.

Out of scope for v1: daemon/watch mode, notifications, running actions on change, config includes,
locale-specific month/day names, calendars other than Gregorian, sub-second precision,
sandboxing of macro commands.

---

## 2. Command line

```
interval-keeper [OPTIONS]
```

| Option | Meaning |
|--------|---------|
| `-c FILE`, `--config FILE` | Use FILE instead of the XDG lookup. `-` reads the config from stdin. |
| `-n`, `--next-change` | Print the next instant (strictly after "now") at which the set of reported states changes, instead of the states. |
| `--at DATETIME` | Evaluate at DATETIME instead of now. ISO 8601: `YYYY-MM-DD[ T]HH:MM[:SS][offset]`. Without an offset it is interpreted in the display zone. Sub-seconds are truncated. |
| `--tz ZONE` | Default time zone (IANA name, or any form from §8.1). Used for intervals without an explicit zone and for printing. Default: `$TZ`, else the system zone. |
| `--format FMT` | Output format of `--next-change`. A `strftime` string, or the keywords `iso` (ISO 8601 with offset) or `epoch` (Unix seconds). Default `%Y-%m-%d %H:%M:%S`. |
| `--horizon YEARS` | How far ahead `--next-change` searches. Default 10. |
| `--cmd-timeout SECONDS` | Timeout for each macro command. Default 10. |
| `--check` | Fully parse the config (no subtree skipping, all macro commands run), print nothing, exit 0 if valid. |
| `--print-default-config` | Print the default config text to stdout and exit. |
| `-V`, `--version`, `-h`, `--help` | As usual. |

### 2.1 Output

* Default mode: one active state per line on stdout, in config order (§7.4), each name once. No active state → no output, exit 0.
* `--next-change`: a single line with the datetime in the display zone, e.g. `2026-10-09 12:00:00`.
* **stdout hygiene:** the config is parsed completely before anything is printed. On any error stdout stays empty.
  Diagnostics go to stderr.

### 2.2 Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success (including "no state active"). |
| 1 | `--next-change` only: no change within the horizon. Nothing printed. |
| 2 | Error: usage, I/O, parse error, macro command failure. Nothing on stdout. |

Error message format on stderr: `interval-keeper: PATH:LINE: error: MESSAGE` (or `interval-keeper: error: MESSAGE` when no line applies).

---

## 3. Config file location

### 3.1 Lookup order

1. `--config FILE` (§3.2).
2. `$XDG_CONFIG_HOME/interval-keeper/intervals.conf` (default `$HOME/.config/...`).
3. For each directory in `$XDG_CONFIG_DIRS` (default `/etc/xdg`), in order: `DIR/interval-keeper/intervals.conf`.

The first file that exists wins; files are not merged. XDG variables holding relative paths are ignored, as the XDG spec requires.

### 3.2 Creating the default config

If no file was found and `--config` was **not** given, the tool creates
`$XDG_CONFIG_HOME/interval-keeper/intervals.conf` (directory mode 0700 if it has to be created, file mode 0644)
with the default content (§3.3), prints `interval-keeper: created default config: PATH` to stderr, and proceeds
using it. If `--config` names a file that does not exist: error, nothing created (D12).

### 3.3 Default config content

The default config has **no active lines**: everything is inside a comment block.
It must contain, in comments:

1. A one-paragraph description of the tool.
2. The complete format specification (condensed from §4–§9): line format, indentation, macros,
   INTERVAL syntax with all field kinds, negation, STATE rules (`~`, `@`), relative intervals, time zones.
3. An examples section, delimited by the exact marker lines `# --- examples begin ---` and
   `# --- examples end ---`. Inside it, every example config line is written as `# ` followed by the
   original line (indentation preserved after the `# `). **Test requirement:** stripping the leading `# `
   from those lines must yield a config that parses successfully (with `ncal` stubbed).
   Explanatory prose inside the block goes in lines starting with `## `, which the test ignores.
4. The examples from the brief (all of them, with `Easter` using the working wrapper from D5).

---

## 4. Config syntax

The file is UTF-8 text; `\r\n` and `\n` are both accepted.

### 4.1 Line kinds

| Kind | Recognised by |
|------|---------------|
| blank | only whitespace → ignored |
| comment | first non-blank char is `#` → ignored. **No inline comments** (STATE is free text and may contain `#`). |
| macro definition | `NAME := VALUE`, where NAME matches `[A-Za-z_][A-Za-z0-9_]*` (checked **first**) |
| interval line | everything else: `[!] INTERVAL [= STATE]` |

### 4.2 Interval line

```
INDENT [!] INTERVAL [= STATE]
```

* `INDENT`: spaces only. A tab in the indentation is an error.
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
* A STATE starting with `@` is **hidden**: not reported, but its name (without `@`) is what children see as `~`.
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
* COMMAND: run with `/bin/sh -c COMMAND`, stdin from `/dev/null`, stderr passed through,
  timeout `--cmd-timeout`. Exit status ≠ 0, timeout, empty output, or multi-line output (after stripping trailing newlines) → error.
  Macros are **not** expanded in COMMAND text. Instead the environment contains:
  * everything inherited from the caller;
  * `MACRO_<NAME>` for every macro visible at that point (their resolved values);
  * `INTERVAL_KEEPER_AT`: the evaluation instant (ISO 8601 with offset);
  * for **indented** definitions: `INTERVAL_<STATE>` for each ancestor line that has a STATE (hidden `@` ones included),
    where `<STATE>` is the ancestor's effective name with every character outside `[A-Za-z0-9_]` replaced by `_`,
    and the value is the ancestor's INTERVAL text after macro expansion, with a leading `! ` if negated.
    On a name clash the innermost ancestor wins. This is static information about the config, not about the clock.
* Empty value → error.

### 5.2 Expansion

Before an INTERVAL (or macro STRING) is lexed, every **whole word** that equals a visible macro name is replaced by its value.
A word is a maximal run of `[A-Za-z0-9_]`, so `mary_birthday` is not replaced inside `annamary_birthday`.
Expansion is a **single pass**: replaced text is not rescanned. (Values are already fully expanded when defined.)
Names are case-sensitive for macros. Note that expansion works on raw text, so a macro named like a path component of a zone
name (`Europe/Q1`) would be altered; do not do that.

### 5.3 Names and scope

* Allowed names: `[A-Za-z_][A-Za-z0-9_]*`. Anything else (numbers, `1st`, `a-b`) → error.
* Reserved (case-insensitive) → error: month names and weekday names (full and 3-letter, `Sept`), duration units (§9), `until`,
  `UTC`, `GMT`, `Z`, and every abbreviation in the §8.2 table.
* A macro defined at indentation 0 is visible to all following lines. A macro defined at deeper indentation, as a child of
  line P, is visible to the lines that follow it inside P's subtree. Leaving the subtree ends the scope.
* Redefining a name that is **visible** at that point (same scope or enclosing scope) → error (D8). Two sibling subtrees may define the same name.

### 5.4 When commands run (D4)

Parsing is one pass over the file, top to bottom; each macro command runs when its line is reached.

* **Default mode** (print states): when the parser reaches a subtree whose parent's effective set does **not** contain the
  evaluation instant, the subtree is *skipped*: macro commands inside it do not run, and lines that depend on a skipped
  command macro are only structurally validated (indentation, line kind). All other lines are fully parsed and validated.
* **`--next-change` and `--check`**: never skip.

### 5.5 Known limitation

A command macro is a snapshot taken at evaluation time. Example: `ncal -e` yields only the *current* year's Easter, so
`--next-change` run in December cannot know next year's Easter. Commands may read `INTERVAL_KEEPER_AT` to pick a year.

---

## 6. INTERVAL syntax

### 6.1 Lexical rules

After macro expansion the text is tokenised, whitespace being insignificant except as a separator. Longest match, in this order:

| Token | Form |
|-------|------|
| `ISODATE` | `Y-m-D`, `Y` = 4 digits or `*`, `m` and `D` = 1–2 digits or `*`; no inner whitespace |
| `TIME` | `H:MM` or `HH:MM` or `HH:MM:SS` |
| `NUMBER` | digits |
| `--` `-` `+` `,` `*` | punctuation (`--` is a span operator, `-` a range operator) |
| `TZ` | forms of §8.1 |
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
* a `DATE`/`DOM`/`MONTH` combination that can never exist is an error (`Feb 30`, `2026-02-29`, `*-04-31`);
  `Feb 29` and `*-*-31` are fine.

A clause with no `TIME` item covers whole days. A clause with no day-level item (`YEAR`, `MONTH`, `DOM`, `WEEKDAY`, `DATE`)
covers every day.

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
* If the right date is then before the left date: a right side with no month moves to the next month; a right side with no explicit year moves to the next year
  (so `Dec 20 -- Jan 10` and `2026 Dec 20 -- Jan 10` work); an explicit year → error.
* Without times: whole days, **end date inclusive** → `[00:00 of first day, 00:00 after last day)`.
  With times: both sides must have one; `[start, end)`.
* Recurring span in a year where an endpoint does not exist (`Feb 29`) → that year has no instance.
* `2026 Apr 1 -- 20`, `2026 Apr 1-20` and `2026-04-01 -- 20` are equivalent.

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
  (default `00:00-24:00`), one range `[day+t1, day+t2)` is produced; if `t2 < t1` the end is on the following day (`t1 = t2` is an error). So the day selectors pick the
  **starting** day (D2).
* A bare time point (`08:00`, not a range) is a zero-length instant. It is valid only as the anchor of a relative interval (§9); alone it is an error.
* Wall-clock → instant conversion, DST gaps and folds follow PEP 495 as implemented by `zoneinfo` (nonexistent times use the offset before the transition, ambiguous
  times take the first occurrence). Ranges that become empty are dropped. **No calendar or zone arithmetic is hand-written**: use `datetime`, `zoneinfo`, `dateutil.relativedelta`.
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

* A line is **reported** iff it has a STATE that does not start with `@`.
* The state *name* is the STATE after `~` substitution and escape processing.
* Several lines may yield the same name; the state is active when **any** of them is effective (`U(name)` = union of their effective sets).
* Output order: the order in which a name's first line appears in the file (depth-first, as written). Each name is printed once.
* State at instant `t`: `{ name : t ∈ U(name) }`.

---

## 8. Time zones

### 8.1 Accepted `TZ` forms

* IANA names: `Europe/Budapest`, `Etc/UTC`, `America/Argentina/Buenos_Aires`, `UTC` (looked up case-insensitively against `zoneinfo.available_timezones()`).
* Offsets: `UTC±H`, `UTC±HH`, `UTC±HHMM`, `UTC±HH:MM` and the same with `GMT` — **ISO sign convention**: `UTC+0300` is three hours *east* of Greenwich
  (unlike POSIX `Etc/GMT-3`). Also `Z`.
* Abbreviations from §8.2.

No `TZ` → the default zone (`--tz`, else `$TZ`, else system zone via `tzlocal`; fallback UTC with a stderr warning).
The zone applies to the whole clause (or span): the calendar days, the times of day and any duration arithmetic of §9.

### 8.2 Abbreviation table

An abbreviation names a **zone with DST rules**, so both members of a pair are accepted for any date (D9); the actual offset is whatever the zone has on that date.
`*-12-* 08:00-09:00 CEST` is therefore 08:00–09:00 in CET.

| Abbreviations | Zone |
|---------------|------|
| `CET`, `CEST` | `Europe/Berlin` |
| `EET`, `EEST` | `Europe/Helsinki` |
| `WET`, `WEST` | `Europe/Lisbon` |
| `EST`, `EDT` | `America/New_York` |
| `CST`, `CDT` | `America/Chicago` |
| `MST`, `MDT` | `America/Denver` |
| `PST`, `PDT` | `America/Los_Angeles` |
| `UTC`, `GMT`, `Z` | UTC (fixed offset, no DST). `GMT+1` etc. are offset forms (§8.1) |

Not supported (ambiguous): `IST`, `BST`, `CAT`, `AST`, … → error asking for an IANA name.

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
* Implementation note: an instance may begin long before the evaluation window; evaluation must look back until the first instance in the window is complete
  (widen and retry; the bound is the horizon, anything unresolved beyond it is dropped).

---

## 10. `--next-change`

Let `A(t)` be the set of reported state names active at `t`. The result is

```
min { t' : t' > at,  A(t') ≠ A(at),  t' ≤ at + horizon }
```

Consequences: a state ending at `T` while another line of the **same name** starts at `T` is no change; hidden (`@`) and STATE-less lines are never change points on their own;
every change point is a range boundary of some `U(name)`.

Algorithm contract (implementation free to optimise as long as results are identical to this):

1. Evaluate `U(name)` for all reported names over a window `[at, hi)`; initial `hi` = at + 2 days, then +32 days, +400 days, then the full horizon.
2. Boundaries equal to the window's own end are artefacts and ignored (they are not changes).
3. If any boundary `> at` remains, the smallest one is the answer; otherwise grow the window; after the horizon → exit 1.

`at` is the evaluation instant truncated to whole seconds. Output is formatted in the display zone with `--format`. During a DST fold the default format is ambiguous; use `--format iso` for an unambiguous result.

---

## 11. Errors (all exit 2, stdout empty)

Syntax and semantic errors, each reported with file and line:

bad indentation / tab in indentation / first line indented; macro with children; unknown word; undefined macro used as a word;
macro name invalid, reserved, or already visible; macro command failed / timed out / empty or multi-line output; duplicate item kind in a clause;
mixed-kind range; time range with equal ends; numbers out of range; impossible date; `*` outside `ISODATE`; bare time point as a standalone interval;
span with lists/ranges, missing time on one side, end before start with explicit year; `~` without parent STATE; empty STATE or empty INTERVAL;
unknown time zone or unsupported abbreviation; bad `--at`/option values.

---

## 12. Implementation constraints

* One executable file `interval-keeper`, `#!/usr/bin/env python3`, Python ≥ 3.9. No other source files are needed to run it.
* Allowed third-party: `python-dateutil`, `tzlocal`; system `tzdata`. If a dependency is missing, say which on stderr and exit 2.
* **All** calendar, weekday, month-length, leap-year, zone, DST and month/year arithmetic goes through `datetime`, `zoneinfo`, `dateutil`. Scanning days with a `for` loop over `datetime.date` is fine;
  re-implementing leap-year or zone rules is not.
* Interval *set algebra* (union / intersection / subtraction / clipping of lists of `(start, end)` instants) is the tool's own code.
* Macro commands are arbitrary code run with the user's privileges, including from `$XDG_CONFIG_DIRS`. There is no sandbox (documented in the default config).

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

**V9** zones (`tz=UTC`): `*-12-* 08:00-09:00 CEST = t` → active at 2026-12-01 07:30:00, not at 2026-12-01 06:59:59. `*-07-* 08:00-09:00 CET = t` → active at 2026-07-01 06:30:00. `08:00-09:00 UTC+0300 = t` → active at 2026-10-09 05:30:00.

**V10** macros:
```
Q1 := Jan-Mar
Q1 = first quarter
```
at 2026-02-10 → `first quarter`. Whole-word rule: `mary := Mon` followed by `annamary = x` → error. Command macro: `A := Tue`, `D := ! echo "$MACRO_A"`, `D = x` → active on a Tuesday. Scope/pruning: a command macro inside `Jun,Jul,Aug = summer` runs under `--at` in July (and `INTERVAL_summer` is `Jun,Jul,Aug`), does not run under `--at` in October, runs in October with `--check`.

**V11** all-lines test: the complete example list from the brief (with the D5 wrapper for `Easter`) parses as one config under `--check`.

**V12** each of these is an error (exit 2, empty stdout): `08:00-25:00 = x`; `Mon Tue = x`; `Foo = x`; `Mon = ~` (top level); `  Mon = x` as the first line; tab indentation; `Mon := x`; `7 := x`; `Q := Jan` twice; `Feb 30 = x`; `2026-02-29 = x`; `08:00 = x`; `Mon =`; `= x`; `X := ! false`; `Apr 1 -- Jun = x`; `Mon IST = x`; `08:00-08:00 = x`; unknown zone `Mon Foo/Bar = x`.

**V13** brute-force oracle (property test): for each config above and random `at` values, `--next-change` equals the first `t' > at` found by stepping one second (or one minute when the config has no seconds) at which the printed state set differs.

---

## 14. Possible future work (not in v1)

`--watch`, a `--has STATE` exit-code query, per-year re-evaluation of command macros, weekday spans (`Mon 08:00 -- Fri 17:00`), n-th weekday syntax, config includes, man page.
