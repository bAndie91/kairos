# kairos — test instructions and conformance vectors

Part of the [kairos specification](../SPEC.md).

## 1. Test instructions

* Tests encode the vectors of §2 verbatim. In a vector `tz` is the default zone (`--tz`) and `at` is `--at`; "→ ∅" means empty stdout and exit 0.
* Always pass `--at` and `--tz`; never depend on the wall clock (the bare-time `--at` resolver takes the current time as a parameter). Tests that need a fixed environment also set `TZ`.
* Calendar facts the vectors rely on (below) are asserted with `datetime` in the tests, so that a wrong fact in this specification is caught.
* Error tests assert exit status 2, empty stdout, and `PATH:LINE` plus a keyword on stderr.
* Locale tests run in one subprocess per locale, with the environment set before Python starts, so that process-global locale state cannot leak between tests. They skip a locale that is not installed: missing system locale data is not a parser defect.
* Table-driven tests are preferred (`(config, args, expected_stdout)`); each vector is a row. Unit tests import the owning module; CLI integration tests run the `kairos` launcher.
* V13 is a property test and V11 checks the default config.

## 2. Conformance vectors

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

**V9** zones (`tz=UTC`): `*-12-* 08:00-09:00 Europe/Berlin = t` → active at 2026-12-01 07:30:00, not at 2026-12-01 06:59:59. `*-07-* 08:00-09:00 Europe/Berlin = t` → active at 2026-07-01 06:30:00. `08:00-09:00 UTC+0300 = t` → active at 2026-10-09 05:30:00. Bare alphabetic abbreviations such as `CEST` and `CST` that no macro defines must error, and the message asks for an IANA zone ID or a numeric offset (a macro is the third way, V21).

**V10** macros:
```
Q1 := Jan-Mar
Q1 = first quarter
```
at 2026-02-10 → `first quarter`. Names with spaces and punctuation, and names that start with another macro's name: `Mary := Mon`, `Mary's birthday := Jun 1`, `Mary's birthday = party`, `Mary = m` → at 2026-06-01 10:00 (a Monday) `party`, `m`; at 2026-06-08 10:00 `m`. Whole-word rule: `mary := Mon` followed by `annamary = x` → error (unknown token `annamary`). Command macro: `A := Tue`, `D := ! echo "$KAIROS_MACRO_A"`, `D = x` → active on a Tuesday. Scope/pruning: a command macro inside `Jun,Jul,Aug = summer` runs under `--at` in July (and `KAIROS_INTERVAL_0` is `Jun,Jul,Aug`, `KAIROS_STATE_0` is `summer`), does not run under `--at` in October, runs in October with `--check` (and with `--next-change`). A command macro at the root level has no `KAIROS_INTERVAL_*` / `KAIROS_STATE_*` variables at all, and one at a deeper level never sees its own line there, only its ancestors' (`D := ! env` at level 1 under `Jun,Jul,Aug = summer` sees `KAIROS_INTERVAL_0` and `KAIROS_STATE_0`, not `..._1`). The command runs once, at its definition, even if no line uses the macro; a later use does not run it again. A command failure is an error at the macro's line, whether or not a line uses the macro: `X := ! false` on its own exits 2 in default mode, with `--next-change` and with `--check`. The one exception is a command inside a subtree skipped in default mode, which does not run and cannot fail; `--next-change` and `--check` never skip.

**V11** all-lines test: the default config (cli §2.3), with the leading `# ` of its example lines stripped (`Easter` using the wrapper of macros §4.4), parses as one config under `--check`.

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

Also test a bare `08:00` as exactly `[08:00:00,08:01:00)`: active at 08:00:00 and 08:00:59, inactive at 08:01:00; as a relative anchor, `08:00 + 2 hours` is `[08:00:00, 10:00:00)` (intervals §6.1: the result starts at the instance start) and `2 hours until 08:00` is `[06:00:00, 08:00:00)` (intervals §6.1: the result ends at the instance end, the instant `08:00:00`).

**V15** locale-sensitive month and weekday names (intervals §1.2; one subprocess per case, skipped if the locale is not installed, §1):

- `LANG=hu_HU.UTF-8`, `LC_TIME` and `LC_ALL` unset: `március 15 = x` parses; `Mar 15 = x` fails as an unknown word. With `LANG=en_US.UTF-8` the reverse.
- Precedence: with `LANG=hu_HU.UTF-8` and `LC_TIME=en_US.UTF-8` English names are recognised and Hungarian ones rejected; with `LANG=en_US.UTF-8` and `LC_TIME=hu_HU.UTF-8` the reverse. `LC_ALL` overrides both: with `LC_ALL=hu_HU.UTF-8`, `LANG=en_US.UTF-8` and `LC_TIME=en_US.UTF-8`, Hungarian names are recognised and English ones rejected.
- Repeat the checks for full and abbreviated weekday names, month ranges, weekday ranges, comma lists, macro-expanded names and macro names reserved by the month/weekday vocabulary; check that case-insensitivity goes no further than the date/time facilities provide and that non-ASCII characters such as `á` survive tokenization and matching.

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

**V17** several parts in one INTERVAL (`tz=Europe/Budapest`, year 2026):
```
2 days before Apr 10, 3 days after Oct 1 = two shifts
Apr 1, 2 days before Apr 10 = day and shift
Mon + 2 days, Fri = week
2 days before Apr 10, Apr 20 = separate parts
Apr 1, 2 days = oops
```
`two shifts` is exactly Apr 8 and Oct 4 (active 2026-04-08 00:00:00, inactive 2026-04-09 00:00:00 and 2026-04-10 12:00); `day and shift` is exactly Apr 1 and Apr 8 (never the days 1 and 2); `week` is every Monday and Tuesday (`[Mon 00:00, Wed 00:00)`) plus every Friday; `separate parts` is exactly Apr 8 and Apr 20 (the shift applies to `Apr 10` only); `2 days before Apr 10,20` is also Apr 8 and Apr 20 because the comma ends the relative expression regardless of whitespace; the last line is an error (`2 days` without `until`, `before` or `after`). A trailing comma (`Apr 1,`, `Apr 1, 2 days before Apr 10,`) is an error. With a union INTERVAL `--next-change` still finds the first change of any part (`two shifts` at 2026-01-01 00:00 is `2026-04-08 00:00:00`).

**V18** `--at` forms (`tz=Europe/Budapest`; the current time is a parameter of the resolving function, so tests never read the wall clock). Config `06:00-07:00 = x`:
- `--at 2026-10-09` is `2026-10-09 00:00:00`: `x` is not active; `--at 2026-10-09` with `00:00-01:00 = y` shows `y`. `--at 2026-10-09Z` is `2026-10-09 00:00:00` UTC, i.e. `02:00:00` in Budapest, so `y` is not active but `00:00-03:00 = z` shows `z`.
- A `TZ` is read as in an INTERVAL: `--at "2026-10-09 12:00 Europe/Berlin"` and `--at "2026-10-09 12:00:00UTC+2"` are both the instant `2026-10-09 10:00:00 UTC`; `--at "2026-10-09 12:00Z"` is `12:00:00 UTC`. `8:05` is the same as `08:05`.
- Now = `2026-10-09 20:00:00` (= `18:00:00 UTC`): `--at 06:00` → `2026-10-10 06:00:00` (`x`, plus the stderr warning naming `06:00` and `2026-10-10`); `--at 08:00:01` → today `2026-10-09 08:00:01`, no warning (11 h 59 m 59 s ago); `--at 08:00` → today (exactly 12 hours ago is not "more than"), no warning; `--at 07:59:59` → tomorrow, with the warning; `--at 22:00` → today (later today), no warning.
- Bare time with a `TZ` counts today and the 12 hours in that zone (now = `2026-10-09 20:00:00` Budapest = `18:00:00 UTC`): `--at 05:00Z` is 13 hours in the past in UTC → `2026-10-10 05:00:00 UTC` with the warning; `--at 06:00Z` is exactly 12 hours → `2026-10-09 06:00:00 UTC`, no warning.
- Now = `2026-10-09 15:00:00`: `--at 14:00` → `2026-10-09 14:00:00`, no warning.
- Now = `2026-10-09 01:06:00`: `--at 23:00` → today `2026-10-09 23:00:00` (still ahead), no warning.
- Errors: `24:00`, `25:00`, `6:60`, `6:00x` (unknown zone token), `2026-10-09 06:00 Foo/Bar` (unknown zone), `2026-10-09T06:00` and abbreviations such as `CEST` (intervals §8.1). With `--next-change`, `--at 06:00` (now 20:00 as above) searches from `2026-10-10 06:00:00`.

**V19** indentation (states §1.3): tabs and spaces are judged as the Python reference prescribes, so the expected result of every case is what Python's own tokenizer says about the same text (compare with `tokenize`). Cover a tab-indented child, a child indented with spaces and a tab, consistent and inconsistent mixes of tabs and spaces across lines (an error with exit 2 and `PATH:LINE`), a dedent to no open level, a first line that starts with whitespace, and blank or comment lines, which are not measured.

**V20** commas and spans (`tz=Europe/Budapest`, year 2026). `1 -- 5, 10 -- 12 = x`: active at 2026-10-05 23:59:59 and at 2026-10-12 23:59:59, inactive at 2026-10-06 00:00:00 and at 2026-10-13 00:00:00 (the ranges are `[1st 00:00, 6th 00:00)` and `[10th 00:00, 13th 00:00)` in every month); `--next-change` at 2026-10-06 12:00 is `2026-10-10 00:00:00`, at 2026-10-12 12:00 it is `2026-10-13 00:00:00`. `1 -- 5, 10 = y` is days 1–5 plus day 10 (active at 2026-10-10 12:00, inactive at 2026-10-06 12:00). `5, 10 -- 12 = z` is day 5 plus days 10–12 (active at 2026-10-05 12:00 and 2026-10-11 12:00, inactive at 2026-10-09 12:00 and 2026-10-13 12:00). `Apr 1 -- Apr 5, Apr 10 -- Apr 12 = w` is two spans (active at 2026-04-12 12:00, inactive at 2026-04-07 12:00). Still errors: `1-3 -- 10 = x` and `Mon -- Fri = x` (a range or weekday on a side), `1 -- 5, = x` (trailing comma, V17).

**V21** macros and time-zone words (`tz=UTC`, 2026-10-12 is a Monday). Expansion precedes tokenization: `Berlin := London` and `08:00-09:00 Europe/Berlin = x` is read as `08:00-09:00 Europe/London`, so `x` is active at 07:30:00 UTC (London is UTC+1) and inactive at 06:30:00 UTC. `au := x`, `Prince := y` and `Mon America/Port-au-Prince = z` is an error (unknown zone `America/Port-x-y`). An abbreviation defined as a macro works as a `TZ`: `CEST := UTC+2` and `08:00-09:00 CEST = x` is active at 06:30:00 UTC and inactive at 05:59:59 UTC; without the macro `CEST` stays an error (V9). No time-zone word is reserved, so each of these definitions is valid: `Europe/Budapest := Mon`, `UTC := Europe/Budapest` (then `08:00-09:00 UTC = x` is active at 06:30:00 UTC and inactive at 05:59:59 UTC), `CET := Europe/Berlin`, `Z := Mon`, `UTC+2 := Mon`, `Budapest`, `CEST`.

**V22** hour and minute ranges (`tz=Europe/Budapest`, Friday 2026-10-09). Errors (exit 2, empty stdout, the message names the replacement): `15h-16h = x`, `8h-12h = x`, `22h-2h = x`, `8:*-12:* = x`, `8h-12:* = x`, `15m-20m = x`, `15min-20min = x`, `15m-*:20 = x`, `*:15-20m = x`, `*:15-*:15 = x` (equal ends), `15:00-*:20 = x` (mixed kinds). Valid: `15:00-16:00 = a` is active at 15:00:00 and 15:59:59, inactive at 16:00:00. `*:15-*:20 = b` is active at 03:15:00 and 03:19:59, inactive at 03:14:59 and 03:20:00; `--next-change` at 03:15:00 is `03:20:00` and at 03:20:00 it is `04:15:00`. `*:50-*:10 = c` is active at 03:50:00, 03:59:59, 04:00:00 and 04:09:59, inactive at 03:49:59 and 04:10:00. `8h = d` is `[08:00, 09:00)`; `8h,10h = e` is 08:00–09:00 and 10:00–11:00; `30m = f` is `[h:30, h:31)` every hour. `Mon-Fri 08:00-13:00 30m = g` is active at 08:30:00 and 12:30:59 on the Friday, inactive at 08:29:59, at 13:30:00 and on the Saturday 2026-10-10 at 10:30.
