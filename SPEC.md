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
| D17 | Macro names | NAME is any text before the first `:=` (no `=`, not starting with `!`, at least one letter): spaces and punctuation are allowed (`Mary's birthday`), and a name may start with or contain another macro's name as long as the whole name differs. Longest name wins when expanding; only identical names clash (D8). (§4.1, §5.2, §5.3) | ~~Identifiers only (`[A-Za-z_][A-Za-z0-9_]*`)~~ | confirmed by the author |
| D18 | Command macro failures | A command macro is not executed when it is defined, so a non-zero exit status is an error when the macro is *evaluated* (first used by a line that is not skipped), never at definition/parse time. An unused macro never runs, even under `--check`. (§2, §5.1, §5.4, §11, V12) | ~~`--check` runs every command macro~~ | confirmed by the author |
| D19 | Unions of relative expressions | `2 days before X, 3 days after Y` and `Apr 1, 2 days before X` are allowed: an INTERVAL is a comma-separated list of *parts*, each a plain term or a whole relative expression (`+`, `until`, `before`, `after`); the result is the union of the parts. The anchor of a relative expression is **one term** (a clause with its lists, or a span), so a comma between terms always separates parts: `2 days before Apr 10, Apr 20` is Apr 8 and Apr 20 (not Apr 8 and Apr 18). A comma followed by `NUMBER unit` never continues a day/year list. (§6.4, §6.6, §9.2) | ~~A relative expression must be the whole INTERVAL; the anchor is a union of all following terms~~ | confirmed by the author |

**Additions beyond your brief** (strike any you do not want): options `--at`, `--tz`, `--format`,
`--check`, `--print-default-config`, `--version`; env var
`KAIROS_NOW` for macro commands; bare time-point anchors in relative intervals
(`08:00 + 2 hours`); KAIROS_compound NUM (`4 days 9 hours`); time-of-day in `--` spans.

---

## 1. Scope

In scope: parsing the config, computing the active states at a given instant, computing the next instant
at which the set of active states changes.

Out of scope for v1: daemon/watch mode, notifications, running actions on change, config includes,
calendars other than Gregorian, sub-second precision, sandboxing of macro commands.

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
| `--check` | Fully parse the config (no subtree skipping, so every command macro that a line uses is evaluated), print nothing, exit 0 if valid. A command macro that no line uses is never evaluated (D18). |
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
| macro definition | `INDENT NAME := VALUE`, where NAME is the text before the first `:=` and contains no `=` (§5.3). A line whose text before the first `:=` contains an `=` is an interval line (`Mon = a := b` is a STATE `a := b`). |
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
  Exit status ≠ 0 → error, reported (with the macro's file and line) at the moment the command is evaluated, i.e. when a line first uses the macro (§5.4, D18). A definition alone never runs anything, so it cannot fail.
  Macros are **not** expanded in COMMAND text. Instead the environment contains:
  * everything inherited from the caller;
  * `KAIROS_MACRO_<NAME>` for every macro visible at that point (their resolved values). NAME is used **as is**, without any transformation: the variable for `Mary's birthday` is named `KAIROS_MACRO_Mary's birthday`. Kairos does not check or special-case anything (not `=`, not `\0`): it hands the variable to the operating system / language runtime like any other. If that refuses a variable, Kairos prints a warning naming the macro to stderr, leaves that variable out and carries on running the command. The shell may well be unable to read such a variable (`$KAIROS_MACRO_Mary's birthday` is not valid shell); that is not Kairos's concern;
  * `KAIROS_NOW`: the evaluation instant (ISO 8601 with offset);
  * for interval definitions: `KAIROS_INTERVAL_<LEVEL>` and `KAIROS_STATE_<LEVEL>` for each ancestor line and the line itself where the command-sourced macro is being resolved: LEVEL is the indentation level from 0.
    * `KAIROS_INTERVAL_<LEVEL>`'s value is the ancestor's (or self) INTERVAL text after macro expansion, with a leading `! ` if negated.
    * `KAIROS_STATE_<LEVEL>`'s value is the ancestor's STATE text (as reported in normal mode: ie. after `~` substitution, escape and `^@\s*` processing, may be empty).
* Empty values are valid.

### 5.2 Expansion

Before an INTERVAL (or macro STRING) is lexed, every occurrence of a visible macro name that stands as a **whole word** is replaced by its value.

* A name is matched literally and case-sensitively, including the inner spaces and punctuation exactly as written in its definition.
* If several visible names match at the same position, the **longest** wins. So `Mary` and `Mary's birthday` can coexist, and `Mary's birthday` is not read as `Mary` followed by `'s birthday`.
* Whole word: when the name starts with a *word character* (a letter, including unicode letters, a digit or `_`), the character before the match must not be a word character; when it ends with one, the character after the match must not be one. So `mary` is not replaced inside `annamary` or `mary_birthday`. Whitespace, punctuation, `-`, `,`, `/` and the start/end of the string are boundaries; a name that starts or ends with punctuation needs no boundary on that side.
* Expansion is a **single pass**: replaced text is not rescanned. (Values are already fully expanded when defined.)

### 5.3 Names and scope

* NAME is the text before the first `:=`, trimmed. It is case sensitive and may contain spaces and punctuation (`Mary's birthday`, `Q1 (first quarter)`, `Easter!`). It must not be empty, must not contain `=` (the line would be an interval line, §4.1), must not start with `!`, and must contain at least one letter (a name made only of digits and punctuation would collide with numbers, times and `*`; `7 := x` is an error) (D17).
* A name may start with, end with or contain the name of another macro, as long as the whole name is different: `Mary`, `Mary's birthday` and `birthday` can all be defined together. Only an identical name is a redefinition (D8). Expansion tries longer names first (§5.2).
* Reserved (case-insensitive) → error: a name that is *entirely* one of the following words (`Mon morning` is fine, `Mon` is not): month names and weekday names recognized in the effective `LC_TIME` locale (full and abbreviated forms supplied by the locale/date-time library), duration units (§9), `until`, `before`, `after`, `UTC`, `GMT`, and `Z`. The month/weekday vocabulary is locale-dependent and must be derived from the same locale-aware date/time facilities used to parse these names; do not hard-code English names or maintain a separate alias list. Other timezone-looking strings are TZ tokens only if they match §8.1; there is no abbreviation table.
* A macro defined at indentation 0 is visible to all following lines. A macro defined at deeper indentation, as a child of
  line P, is visible to the lines that follow it inside P's subtree. Leaving the subtree ends the scope.
* Redefining a name that is **visible** at that point (same scope or enclosing scope) → error (D8). Two sibling subtrees may define the same name.

### 5.4 When commands run (D4)

Parsing is one pass over the file, top to bottom; each macro command runs when its macro name is being resolved (lazy).
Defining a command macro does not run it, so a command failure (non-zero exit status) is an **evaluation-time** error, not a parse-time one (D18): it is raised when the first line that uses the macro is evaluated, and only then. A command macro that is never used, or is used only in a skipped subtree (default mode), never runs and never fails. The value of a command that ran is kept; later uses do not run it again.

* **Default mode** (print states): when the parser reaches a subtree whose parent's effective set does **not** contain the
  evaluation instant, the subtree is *skipped*: macro commands inside it do not run, and lines that depend on a skipped
  command macro are only structurally validated (indentation, line kind). All other lines are fully parsed and validated.
* **`--next-change` and `--check`**: never skip, so every command macro used by any line is evaluated (and a failing one is reported); a macro no line uses still never runs.

### 5.5 Known limitation

A command macro is a snapshot taken at evaluation time. Example: `ncal -e` yields only the *current* year's Easter, so
`--next-change` run in December cannot know next year's Easter. Commands may read `KAIROS_NOW` to pick a year.

---

### Locale-dependent calendar names

Month and weekday names are locale-sensitive input, not a fixed English vocabulary. The active locale is the effective process `LC_TIME` locale as selected by the platform/Python locale facilities:

- An explicitly set `LC_ALL` takes precedence; otherwise `LC_TIME` takes precedence over `LANG`; otherwise the platform locale default applies.
- Initialize locale handling using the standard `locale` module's environment-based locale selection (for example, `locale.setlocale(locale.LC_TIME, "")`), rather than reading environment variables and resolving precedence manually. Do not silently force the `C` locale.
- Use the standard/library locale-aware date/time name tables and parsing/formatting routines as the sole authority for recognized full and abbreviated month and weekday names. No hand-maintained English list, translation table, transliteration, alias list, or fallback vocabulary is permitted. Locale-aware facilities may expose only the names provided by the selected locale; accept exactly those names and forms that the chosen facility recognizes.
- This rule applies equally to month and weekday names wherever they occur: standalone atoms, ranges, comma lists, spans, macros after expansion, reserved macro names, and unknown-word diagnostics. The lexer must not accept an English name merely because it is common or was valid in another locale.
- Locale selection must be initialized before any locale-sensitive lexing/parsing and remain consistent throughout one invocation. Do not temporarily switch locales per token. As this is a CLI process, process-global locale state is acceptable; if the implementation later becomes concurrent/in-process, it must account for the locale module's process-global behavior.
- Locale-sensitive names are distinct from numeric and ISO forms, which remain locale-independent. ISO dates and numeric fields retain the grammar and validation rules elsewhere in this specification.

Conformance examples: with `LC_ALL` unset and `LC_TIME=hu_HU.UTF-8` (or `LANG=hu_HU.UTF-8` and no overriding `LC_TIME`), `március 15 = x` is valid and `Mar 15 = x` is an unknown-word error. With an English effective `LC_TIME` locale, `Mar 15 = x` is valid and `március 15 = x` is an unknown-word error. These examples assume the corresponding locales are installed on the test system; tests must skip a locale-specific case if that locale is unavailable, rather than treating missing system locale data as a parser defect.

---

## 6. INTERVAL syntax

### 6.1 Lexical rules

After macro expansion the text is tokenised, whitespace being insignificant except as a separator. Longest match, in this order:

| Token | Form |
|-------|------|
| `ISODATE` | `Y-m-D`, `Y` = 4 digits or `*`, `m` and `D` = 1–2 digits or `*`; no inner whitespace |
| `TIME` | `HH:MM`, `HH:MM:SS` |
| `HOUR`, `MINUTE` | digits immediately followed by `h` (`8h` = `8:*`, every minute of hour 8), or by `m` / `min` (`30m`, `30min` = `*:30`, minute 30 of every hour); no whitespace between digits and suffix |
| `NUMBER` | digits |
| `--` `-` `+` `,` `*` | punctuation (`--` is a span operator, `-` a range operator) |
| `TZ` | IANA zone IDs, numeric UTC offsets, and explicit UTC/GMT/Z forms of §8.1 |
| `WORD` | generic word after locale-aware month/weekday-name matching; Unicode letters and combining marks, plus characters required by recognized locale names |

Locale-name recognition must be driven by the locale-aware date/time library, not by an English-oriented character regex. Before classifying an alphabetic token as a generic `WORD`, the lexer must recognize any complete locale-provided month or weekday name, including non-ASCII letters, combining marks, and punctuation that the library's name representation requires. Do not split or normalize a recognized name in a way that changes its spelling. Whitespace remains a separator between grammar items; a locale name containing internal whitespace is accepted only if the chosen date/time library represents and parses it as a single name in the grammar's context.

Unknown word → error (`unknown word 'X' (undefined macro?)`).

**All unknown words are reported.** The lexer does not stop at the first unknown word of an INTERVAL: it keeps tokenizing and reports **every** unknown word of the line, each as its own diagnostic with the file and line (in order of appearance). A line with unknown words is not parsed further (its tokens are incomplete), but every other line is still checked (§11), so one run lists all the unknown words of the whole config.

**Wrong locale hint.** Month and weekday names depend on the effective `LC_TIME` locale (§11), so an unknown word is often a valid name in some other locale (`May` while the effective locale is Hungarian; `március` while it is English). For an unknown word the diagnostic therefore also says `wrong locale?` when the word is a month or weekday name (full or abbreviated, case-insensitive) in any other **installed** locale, and names the locale(s): `unknown word 'May' (undefined macro? wrong locale? "May" is in "en_US.UTF-8" locale)`. At most a few matching locales are listed (the first few in the system's listing order, then `…`). Only the locale module (§1.1) deals with this: it enumerates the installed locales (the platform's own list, e.g. the output of `locale -a`), tries each through the same locale-aware `datetime`/`calendar` facilities used for parsing, and restores the effective locale afterwards. Kairos reads no `LANG`/`LC_*` variable and keeps no name table for it. The search runs only when a word is unknown, never on the normal path; if the installed locales cannot be listed, the hint is simply omitted.

### 6.2 Item kinds

| Kind | Atom | Range `a-b` |
|------|------|-------------|
| `YEAR` | integer 100–9999 | `a ≤ b` required |
| `MONTH` | a full or abbreviated month name recognized by the effective `LC_TIME` locale's date/time facilities | wraps across the calendar year (the locale's December-to-February equivalent selects December, January, February) |
| `DOM` | integer 1–31 (leading zero ok) | wraps (`28-3` = 28…31, 1…3) |
| `WEEKDAY` | a full or abbreviated weekday name recognized by the effective `LC_TIME` locale's date/time facilities | wraps from the locale's last weekday to its first weekday |
| `TIME` | `H:MM[:SS]` (`24:00` only as a range end) | wraps past midnight (`23:00-04:00`) |
| `HOUR` | `Nh`, N = 0–23 (`8h` = `8:*`) | inclusive set of whole hours; wraps (`22h-2h` = 22, 23, 0, 1, 2) |
| `MINUTE` | `Nm` or `Nmin`, N = 0–59 (`30m` = `*:30`) | inclusive set of minutes of every hour; wraps (`50m-10m`) |
| `DATE` | `ISODATE` (wildcards allowed) | not allowed (use `--`, §6.5) |

Numbers: < 100 is a DOM, ≥ 100 is a YEAR; 0 and 32–99 are errors. `2026-2028` is a year range.
`HOUR` and `MINUTE` are separate kinds, so `Mon-Fri 8h-12h 30m` is a valid clause (minute 30 of hours 8 to 12 inclusive, i.e. 08:30, 09:30 … 12:30, each lasting one minute); a clause may combine `TIME`, `HOUR` and `MINUTE` items, which must all hold (§6.3). `HOUR`/`MINUTE` are not allowed in a span side (§6.5).
A point `TIME` lasts one minute (`08:00` = `[08:00:00, 08:01:00)`), or exactly one second when written with seconds (`08:00:30` = `[08:00:30, 08:00:31)`).
A numeric zone offset is a single token only when written without spaces (`UTC+2`); `UTC + 2 hours` is the zone `UTC` followed by the `+` of a relative interval (§9), while `UTC+2 hours` is an error (the unit `hours` has no number).
Month and weekday names are case-insensitive and come from the effective `LC_TIME` locale (§11). A single dash needs no whitespace but may have it (`Mon - Fri`), except inside an `ISODATE`.

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

A comma followed by a duration (`NUMBER unit`, e.g. `2 days`) never continues a list: `2` there is the count of a duration, not a day of month. It starts a new *part* of the INTERVAL, a relative expression (§6.6, §9.2): `Apr 1, 2 days before X` is the two parts `Apr 1` and `2 days before X`, never the day list `1,2`.

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
interval = part { "," part } ;           (* union of the parts, §9.2; comma grouping per §6.4 *)
part     = term
         | term "+" duration              (* §9 *)
         | duration "until" term
         | duration "before" term        (* §9.1 *)
         | duration "after" term ;       (* §9.1 *)
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

Alphabetic timezone abbreviations other than `UTC`/`GMT` are **not accepted as input TZ tokens**. There is no standardized, globally unique abbreviation-to-zone registry: the IANA Time Zone Database records abbreviations as part of individual zones' historical and future rules, and the same abbreviation can identify different zones or offsets. A name that is itself an IANA zone ID in `zoneinfo.available_timezones()` (legacy IDs such as `CET`, `EET`, `WET`, `MET`, `EST`, `MST`, `HST`, `PST8PDT`) is accepted as that ID, because the ID lookup comes first; the rejection applies to alphabetic names that are not IANA zone IDs (e.g. `CST`, `CEST`, `IST`, `EDT`, `PST`). Do not infer a zone from a string such as `CST` or `CEST`, and do not ship a hand-written mapping. Use an IANA zone ID when calendar/DST rules are intended, or a numeric offset when a fixed offset is intended.

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
* An ANCHOR is **one term** (§6.3, §6.5): a clause (with its lists, `Mon,Fri`, `1-7 Mon`) or a span. Terms separated by a comma that does not continue a list are separate parts of the INTERVAL (§9.2), so `Apr 10, Apr 20 + 2 days` is `Apr 10` plus `Apr 20 + 2 days`. Its **instances** are the maximal contiguous ranges of the anchor's set (a point time is an instance of length zero).
* `ANCHOR + D`: for every instance starting at `s`, the result is `[s, s + D)`. The anchor's own length is ignored. (`1-7 Mon + 5 day` = Mon 00:00 → Sat 00:00 → the working week starting on the first Monday.)
* `D until ANCHOR`: for every instance ending at `e` the result is `[e − D, e)` (D6).
* Arithmetic is done in the anchor's zone: day/week/month/year units are calendar (wall-clock) arithmetic (`dateutil.relativedelta`); hour/minute/second units are elapsed time (convert to UTC, add, convert back).
  In a pair list, calendar units are applied first, then elapsed units.
* The result is an ordinary set: it may be negated, have children, carry a STATE.
* Implementation note: an instance may begin long before the evaluation window; evaluation must look back until the first instance.

### 9.1 `before` and `after`: shifted anchors

```
DURATION before ANCHOR       e.g.  40 days before Dec 24
DURATION after ANCHOR        e.g.  10 days after Oct 1
```

* `D before ANCHOR` / `D after ANCHOR` is plain date/time arithmetic written out: every instance `[s, e)` of the anchor is moved **as a whole** to `[s − D, e − D)` (`before`) or `[s + D, e + D)` (`after`). The anchor's own length is kept, and its time of day is kept too.
  Thus `40 days before Dec 24` is Nov 14 (one day long, just like `Nov 14`), `10 days after Oct 1` is Oct 11, `2 days before Apr 10 12:00` is `Apr 8 12:00` (i.e. `[Apr 8 12:00, Apr 8 12:01)`), `3 hours after 08:00` is `11:00`, and `1 year before Dec 20 -- Jan 10` is the whole span moved back one year.
* Unlike `+` and `until`, which build a run of length `D` from one end of the anchor, these forms select the shifted anchor itself. A bare point time keeps its one-minute length (§6.2); it is not reduced to a zero-length instance.
* DURATION, units, ANCHOR, zone choice and calendar-vs-elapsed arithmetic are exactly as in §9; both endpoints of an instance are shifted independently (so a day-long instance stays one calendar day long across a DST change, and `1 month before Mar 31` ends at the clamped date given by `dateutil.relativedelta`).
* The result is an ordinary set, so it is narrowed, negated, or given children like any other line: a child `08:00-09:00` under `2 days before Apr 10` selects 08:00–09:00 on Apr 8.
* An instance whose shifted endpoints coincide or invert is dropped.

### 9.2 Several parts in one INTERVAL

Relative expressions are ordinary parts of an INTERVAL (D19). A comma-separated list may mix plain terms and relative expressions in any order, and the INTERVAL is the **union** of its parts:

```
2 days before Apr 10, 3 days after Oct 1      Apr 8 and Oct 4
Apr 1, 2 days before Apr 10                   Apr 1 and Apr 8
Mon + 2 days, Fri                             Mon-Tue and Fri
```

* A comma between terms always starts a new part, unless it continues a list inside a clause (§6.4); a comma followed by `NUMBER unit` never continues a list (§6.4). Otherwise
* Each part is evaluated on its own, with its own anchor, zone choice (§9) and arithmetic; the INTERVAL is their union. A `TZ` applies to the term it ends, as always, and never spills over to another part.
* The anchor of every relative form is a single term (§9) and a relative operator never reaches beyond its own term, in either direction (`+` does not shift the terms before it, `until`/`before`/`after` do not shift the terms after it), so a comma ends the relative expression: `2 days before Apr 10, Apr 20` is the two parts `2 days before Apr 10` and `Apr 20`, i.e. Apr 8 and Apr 20, and `Apr 10, Apr 20 + 2 days` is `Apr 10` and `Apr 20 + 2 days`. To shift several dates, repeat the form (`2 days before Apr 10, 2 days before Apr 20`) or use a list inside one clause (`2 days before Apr 10,20`, `Mon,Fri + 1 day`).
* The result is an ordinary set, like any other INTERVAL.

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

bad indentation / first line indented; macro with children; unknown word (every one of them is reported, with a `wrong locale?` hint where one applies);
macro name reserved, already visible, empty, without a letter or starting with `!`; macro command failed (when evaluated, D18); duplicate item kind in a clause;
mixed-kind range; time range with equal ends; numbers out of range; `*` outside `ISODATE`; 
span with lists/ranges, missing time on one side, end before start with explicit year; `~` without parent; empty INTERVAL;
unknown IANA zone ID, invalid offset, or unsupported alphabetic timezone abbreviation; bad `--at`/option values.

---

## 12. Implementation constraints

* One executable file `kairos`, `#!/usr/bin/env python3`, Python ≥ 3.9. No other source files are needed to run it.
* Allowed third-party: `python-dateutil`, `tzlocal`; system `tzdata`, may add other imports if need emerges during implementation.
* **All** calendar, weekday, month-length, leap-year, zone, DST, month/year arithmetic, and locale-dependent month/weekday name interpretation goes through the relevant standard/library facilities (`datetime`, `calendar`, `locale`, `zoneinfo`, `dateutil`). Scanning days with a `for` loop over `datetime.date` is fine but to be minimized; re-implementing leap-year, locale precedence, name tables, case rules, or zone rules is not.
* Month and weekday names are interpreted according to the process's effective `LC_TIME` locale. Initialize/use locale handling through Python's `locale` module in a way that follows the platform's environment locale selection, including `LC_TIME` taking precedence over `LANG` (and `LC_ALL` taking precedence over both when set). Do not infer the locale by manually inspecting environment variables, and do not hard-code translations, aliases, transliterations, or fallback English names. Delegate name production/recognition to locale-aware date/time facilities (for example, `datetime`/`time` formatting and parsing backed by `locale`, or equivalent library APIs). The locale used for lexing/reserved-word checks and semantic date evaluation must be consistent for one invocation.
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
at 2026-02-10 → `first quarter`. Names with spaces and punctuation, and names that start with another macro's name (D17): `Mary := Mon`, `Mary's birthday := Jun 1`, `Mary's birthday = party`, `Mary = m` → at 2026-06-01 10:00 (a Monday) `party`, `m`; at 2026-06-08 10:00 `m`. Whole-word rule: `mary := Mon` followed by `annamary = x` → error (unknown token `annamary`). Command macro: `A := Tue`, `D := ! echo "$KAIROS_MACRO_A"`, `D = x` → active on a Tuesday. Scope/pruning: a command macro inside `Jun,Jul,Aug = summer` runs under `--at` in July (and `KAIROS_INTERVAL_0` is `Jun,Jul,Aug`, `KAIROS_STATE_0` is `summer`), does not run under `--at` in October, runs in October with `--check`.

**V11** all-lines test: the complete example list from the brief (with the D5 wrapper for `Easter`) parses as one config under `--check`.

**V12** each of these is an error (exit 2, empty stdout): `08:00-25:00 = x`; `Mon Tue = x`; `Foo = x`; `Mon = ~` (top level); `  Mon = x` as the first line; `Mon := x`; `7 := x`; `Q := Jan` twice; `Feb 30 = x`; `2026-02-29 = x`; `Mon =`; `= x`; `X := ! false` followed by a line that uses `X` (`X = x`); `08:00-08:00 = x`; unknown zone `Mon Foo/Bar = x`.

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

Command failures are evaluation-time errors (D18): `X := ! false` on its own is valid (exit 0, even with `--check`: nothing uses `X`, so nothing runs); it is an error only once a line uses `X`, and in default mode not if that line sits in a skipped subtree.

Also test a bare `08:00` as exactly `[08:00:00,08:01:00)`: active at 08:00:00 and 08:00:59, inactive at 08:01:00; as a relative anchor, `08:00 + 2 hours` is `[08:00:00, 10:00:00)` (§9: the result starts at the instance start).

**V16** `before` / `after` (`tz=Europe/Budapest`, year 2026):
```
40 days before Dec 24 = early
10 days after Oct 1 = later
2 days before Apr 10 12:00 = dinner
3 hours after 08:00 = brunch
1 month before Mar 31 = clamped
1 year before Dec 20 -- Jan 10 = last year
```
`early` is `[2026-11-14 00:00, 2026-11-15 00:00)` (active 2026-11-14 12:00:00, inactive 2026-11-13 23:59:59 and 2026-11-15 00:00:00); `later` is exactly 2026-10-11; `dinner` is `[2026-04-08 12:00:00, 2026-04-08 12:01:00)`; `brunch` is `[11:00:00, 11:01:00)` every day; `clamped` is Feb 28, 2026 (the instance `[Mar 31, Apr 1)` becomes `[Feb 28, Mar 1)`, because Mar 31 minus one month clamps to Feb 28); `last year` is `[2025-12-20, 2026-01-11)` and `[2024-12-20, 2025-01-11)` in the year before. `--next-change` at 2026-10-09 12:00 with only `early` is `2026-11-14 00:00:00`, and at 2026-11-15 00:00:00 the next one is `2027-11-14 00:00:00`. An anchor-narrowing check: with `2 days before Apr 10` as a parent and a child `08:00-09:00 = x`, only 2026-04-08 08:00–09:00 shows `x`.

**V17** several parts in one INTERVAL (`tz=Europe/Budapest`, year 2026; D19):
```
2 days before Apr 10, 3 days after Oct 1 = two shifts
Apr 1, 2 days before Apr 10 = day and shift
Mon + 2 days, Fri = week
2 days before Apr 10, Apr 20 = separate parts
Apr 1, 2 days = oops
```
`two shifts` is exactly Apr 8 and Oct 4 (active 2026-04-08 00:00:00, inactive 2026-04-09 00:00:00 and 2026-04-10 12:00); `day and shift` is exactly Apr 1 and Apr 8 (never the days 1 and 2); `week` is every Monday and Tuesday (`[Mon 00:00, Wed 00:00)`) plus every Friday; `separate parts` is exactly Apr 8 and Apr 20 (the shift applies to `Apr 10` only); `2 days before Apr 10,20` is Apr 8 and Apr 18 (a list inside one clause); the last line is an error (`2 days` without `until`, `before` or `after`). A trailing comma (`Apr 1,`, `Apr 1, 2 days before Apr 10,`) is an error. With a union INTERVAL `--next-change` still finds the first change of any part (`two shifts` at 2026-01-01 00:00 is `2026-04-08 00:00:00`).

**V15** locale-sensitive month and weekday names (run in subprocesses with environment variables set before Python starts; skip if the requested locale is not installed):

- Hungarian effective locale: `LANG=hu_HU.UTF-8`, unset `LC_TIME` and `LC_ALL`. `március 15 = x` parses; `Mar 15 = x` fails as an unknown word.
- English effective locale: `LANG=en_US.UTF-8`, unset `LC_TIME` and `LC_ALL`. `Mar 15 = x` parses; `március 15 = x` fails as an unknown word.
- Precedence: with `LANG=hu_HU.UTF-8` and `LC_TIME=en_US.UTF-8` (and `LC_ALL` unset), English month/weekday names are recognized and Hungarian names are rejected. With `LANG=en_US.UTF-8` and `LC_TIME=hu_HU.UTF-8`, Hungarian names are recognized and English names are rejected.
- `LC_ALL` overrides both: with `LC_ALL=hu_HU.UTF-8`, `LANG=en_US.UTF-8`, and `LC_TIME=en_US.UTF-8`, Hungarian names are recognized and English names are rejected.
- Repeat the effective-locale checks for full and abbreviated weekday names, month ranges, weekday ranges, comma lists, macro-expanded names, and macro names reserved by month/weekday vocabulary.
- Locale setup occurs before lexing. Verify locale-aware matching is case-insensitive only to the extent provided by the chosen date/time facilities, and that non-ASCII characters such as `á` survive tokenization and matching.
- Run a subprocess per locale so Python's process-global locale state cannot leak between tests. Never require an unavailable locale to be installed; report a skip for that locale.

---

## 14. Possible future work (not in v1)

weekday spans (`Mon 08:00 -- Fri 17:00`), n-th weekday syntax, config includes, man page.
