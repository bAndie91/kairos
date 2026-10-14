# kairos — INTERVAL syntax and evaluation

Part of the [kairos specification](../SPEC.md). An INTERVAL is the part of an interval line before `=` (states §1.2), after macro expansion (macros §3).

## 1. Lexical rules

### 1.1 Tokens

The expanded text is tokenised; whitespace is insignificant except as a separator. Longest match, in this order:

| Token | Form |
|-------|------|
| `ISODATE` | `Y-m-D`, `Y` = 4 digits or `*`, `m` and `D` = 1–2 digits or `*`; no inner whitespace |
| `TIME` | `H:MM[:SS]`: hour `H` = 1–2 digits, `MM` and `SS` = 2 digits (`8:00` = `08:00`); also the form used by `--at` (cli §1.3) |
| `HOUR`, `MINUTE` | `HOUR`: digits immediately followed by `h` (`8h`), or digits, `:` and `*` (`8:*`): two spellings of one token kind with one meaning, every minute of hour 8. `MINUTE`: digits immediately followed by `m` / `min` (`30m`, `30min`), or `*`, `:` and two digits (`*:30`): two spellings of one kind, minute 30 of every hour. No whitespace inside a token. Only the `*:MM` spelling of `MINUTE` can be a range end (§2) |
| `NUMBER` | digits |
| `--` `-` `+` `,` `*` | punctuation (`--` is the span operator, `-` the range operator) |
| `TZ` | a time-zone form (§8.1) |
| `WORD` | any other word, after the month/weekday-name matching of §1.2 |

### 1.2 Month and weekday names

Month and weekday names, full and abbreviated, case-insensitive, are those of the effective `LC_TIME` locale and nothing else: no English fallback, no alias, translation or transliteration table, no hand-maintained list. They are recognised by the locale-aware facilities of the standard library (implementation §2), which decide which locale is effective (`LC_ALL`, else `LC_TIME`, else `LANG`, else the platform default). The locale is fixed for one invocation.

A complete locale name is matched before a token is classified as a generic `WORD`, including non-ASCII letters, combining marks and punctuation the name needs; it is never split or normalised. A name with internal whitespace is accepted only if the library treats it as a single name. This applies wherever a name occurs: atoms, ranges, lists, spans, macro-expanded text, reserved macro names (macros §2) and diagnostics. ISO dates and numeric fields are locale-independent.

With `LC_TIME=hu_HU.UTF-8`, `március 15 = x` is valid and `Mar 15 = x` is an unknown word; with an English locale the reverse (V15).

### 1.3 Unknown words

An unknown word is an error (`unknown word 'X' (undefined macro?)`). **All unknown words are reported:** the lexer keeps going after the first one and reports every unknown word of the line, each as its own diagnostic with file and line, in order of appearance. A line with unknown words is not parsed further, but every other line is still checked.

**Wrong-locale hint.** An unknown word is often a valid name in another locale (`May` while the effective locale is Hungarian, `március` while it is English). The diagnostic therefore also says `wrong locale?` when the word is a month or weekday name (full or abbreviated, case-insensitive) in any other **installed** locale, naming the first few such locales (then `…`): `unknown word 'May' (undefined macro? wrong locale? "May" is in "en_US.UTF-8" locale)`. Only the locale module (implementation §1) does this: it enumerates the installed locales (the platform's own list, e.g. `locale -a`), tries each through the same facilities used for parsing, and restores the effective locale. It runs only for an unknown word, never on the normal path; if the installed locales cannot be listed the hint is omitted.

## 2. Items

| Kind | Atom | Range `a-b` |
|------|------|-------------|
| `YEAR` | integer 100–9999 | `a ≤ b` required |
| `MONTH` | a month name (§1.2) | wraps across the calendar year (December-to-February selects December, January, February) |
| `DOM` | integer 1–31 (leading zero ok) | wraps (`28-3` = 28…31, 1…3) |
| `WEEKDAY` | a weekday name (§1.2) | wraps from the locale's last weekday to its first |
| `TIME` | `H:MM[:SS]`, H = 0–23 with or without a leading zero (`24:00` only as a range end) | wraps past midnight (`23:00-04:00`); equal ends are an error |
| `HOUR` | `Nh` or `N:*`, N = 0–23 | not allowed in either spelling (see below) |
| `MINUTE` | `Nm` or `Nmin`, or `*:MM`; N, MM = 0–59 (`30m` = `*:30`) | only as `*:MM-*:MM` (see below) |
| `DATE` | `ISODATE` (wildcards allowed) | not allowed (use `--`, §5) |

* Numbers: < 100 is a DOM, ≥ 100 a YEAR; 0 and 32–99 are errors. `2026-2028` is a year range. Any number or time out of its range is an error.
* `TIME`, `HOUR` and `MINUTE` are separate kinds: a range may not mix them (`15:00-*:20` is an error), but the spellings of one kind are interchangeable as atoms (`8h` = `8:*`, `30m` = `*:30`).
* A `TIME` that is not part of a range lasts one minute (`08:00` = `[08:00:00, 08:01:00)`), or exactly one second when written with seconds (`08:00:30` = `[08:00:30, 08:00:31)`).
* A single dash needs no whitespace but may have it (`Mon - Fri`), except inside an `ISODATE`.

**No hour ranges, no `Nm` ranges.** `15h-16h` could mean the hour 15:00–16:00 or the two hours 15 and 16, and `15m-20m` could mean the minutes 15 up to 20 or 15 through 20 inclusive. Instead of guessing, such ranges (`15h-16h`, `8:*-12:*`, `15m-20m`, `15m-*:20`) are errors, and the message names the replacement: write `15:00-16:00`, and `*:15-*:20` for minutes. A `*:MM-*:MM` range is left-closed and right-open like every time range: `*:15-*:20` is 15 up to, not including, 20 past every hour, equal ends are an error, and a smaller end wraps into the next hour (`*:50-*:10` is `[h:50, h+1:10)` for every hour h). Atoms and lists of atoms (`8h,10h`, `15m,45m`) stay valid.

## 3. Clauses

### 3.1 A clause is a conjunction

A *clause* is a whitespace-separated sequence of items, optionally ending with a `TZ`. All items must hold simultaneously: `Apr-Jun 1-15` is month ∈ Apr–Jun **and** day ∈ 1–15. Violations are errors:

* at most one item group per kind; `DATE` excludes `YEAR`/`MONTH`/`DOM` in the same clause;
* at least one non-`TZ` item;
* `*` is only valid inside an `ISODATE`, as the minutes of an `HOUR` item (`8:*`) and as the hour of a `MINUTE` item (`*:30`, `*:15-*:20`);
* a `DATE`/`DOM`/`MONTH` combination that can never exist (`Feb 30`, `2026-02-29`, `*-04-31`); this validation is delegated to the datetime library, not hand-written. `Feb 29` and `*-*-31` are fine.

A clause may combine `TIME`, `HOUR` and `MINUTE` items, which must all hold: `Mon-Fri 08:00-13:00 30m` is minute 30 of the hours 8 to 12 on weekdays, i.e. 08:30, 09:30 … 12:30, each lasting one minute.

### 3.2 Evaluating a clause

A clause is evaluated in its zone (§8). A clause with no time item covers whole days; with no day-level item (`YEAR`, `MONTH`, `DOM`, `WEEKDAY`, `DATE`) it covers every day; a clause with a day but no month covers that day in every month.

For every local calendar day that satisfies the day-level items and every time range of the clause (default `00:00-24:00`) one range `[day+t1, day+t2)` is produced; if `t2 < t1` the end is on the following day. So the day selectors pick the **starting** day: `Fri 22:00-02:00` runs from Fri 22:00 to Sat 02:00.

Missing time units are wildcards within their natural ranges and a wildcard selects every value of its field: `8h` (≡ `8:*`) is `[08:00, 09:00)`, `30m` (≡ `*:30`) is `[h:30, h:31)` for every hour h, and `*:15-*:20` is `[h:15, h:20)` for every hour.

## 4. Lists and commas

`a,b` builds a list inside one kind (`Wed,Fri`, `Jun,Jul,Aug`, `1,15`, `Mon-Wed,Fri`, `08:00-12:00,13:00-17:00`). **Rule:** a comma continues the current list iff the next item has the same kind as the item right before the comma; otherwise the comma ends the current *term* and the next item starts a new one. Whitespace around a comma is insignificant (`10,20` = `10, 20`, `Jun 1,Jul 2` = `Jun 1, Jul 2`). A trailing comma is an error. A list may not mix single `TIME` atoms and time ranges. The union of all terms is the interval.

| Text | Meaning |
|------|---------|
| `Apr,Jun 1,15` | (Apr or Jun) and (1 or 15) → Apr 1, Apr 15, Jun 1, Jun 15 |
| `Apr 1, Jun 15` | two terms: Apr 1; Jun 15 |
| `Mon-Fri 08:00-12:00,13:00-17:00` | one clause, two time ranges |
| `Mon 08:00-09:00, Tue 10:00-11:00` | two terms |
| `1 -- 5, 10 -- 12` | two spans: days 1–5 and days 10–12 |
| `1 -- 5, 10` | a span and a clause: days 1–5, and day 10 |
| `5, 10 -- 12` | a clause and a span: day 5, and days 10–12 |
| `Apr 1 -- Apr 5, Apr 10 -- Apr 12` | two spans |

**Spans.** A span side is a single date, never a list (§5): a span cannot end on 5 and on 10 too, nor start on 5 and on 10 too. So a comma never continues a list into or out of a span: a comma directly after a span ends its term, and a comma directly before a span (the text after the comma has the form `dateside -- dateside`) ends the term before it. In `1 -- 5, 10 -- 12` the `5` and the `10` are both days of the month, yet they are not a list.

**Durations.** A comma followed by a duration (`NUMBER unit`, e.g. `2 days`) never continues a list: `2` there is the count of a duration, not a day of month. It starts a new *part* (§6.3): `Apr 1, 2 days before X` is the parts `Apr 1` and `2 days before X`, never the day list `1,2`.

## 5. Spans

`A -- B` is a *span* between two dates.

* Side forms: `ISODATE`, or `[YEAR] [MONTH] DOM`, each optionally followed by one `TIME`. Lists, ranges, weekdays, `HOUR` and `MINUTE` items on a side are errors, and a comma ends the span instead of extending a side (§4). A `TZ` may end the whole span and applies to both sides.
* The left side may be a lone DOM (`1 -- 5` is days 1 through 5 of every month, the same as `1-5`) or a concrete month and day; the year is optional (absent or `*` → recurring every year).
* The right side may omit year and month, which are inherited from the left side (`2026 Apr 1 -- 20`, `Apr 1 -- Jun 15`, `2026 Apr 1 -- May 15`); `2026 Apr 1 -- 20`, `2026 Apr 1-20` and `2026-04-01 -- 20` are equivalent.
* If the right date is then before the left date, a right side with no month moves to the next month and a right side with no explicit year moves to the next year (so `Dec 20 -- Jan 10` and `2026 Dec 20 -- Jan 10` work). A right side with an explicit year that is before the left date is an error.
* Without times: whole days, **end date inclusive**, `[00:00 of the first day, 00:00 after the last day)`. With times: both sides must have one (else error) and the span is `[start, end)`.
* A date that does not exist in a given year (`Feb 29` in a non-leap year) is not a day of the span: the span covers exactly those of its days that exist. So `Feb 29 -- Mar 1` is two days (Feb 29, Mar 1) in a leap year and one day (Mar 1) otherwise; `Feb 20 -- Feb 29` ends on Feb 29 in a leap year and on Feb 28 otherwise; `Feb 29 -- Feb 29` is Feb 29 in a leap year and empty otherwise. As instants, a nonexistent endpoint, whether the start or the (exclusive) end, is the boundary between Feb 28 and Mar 1, i.e. Mar 1 00:00 in the span's zone; a `TIME` written on such a side is ignored.

## 6. Relative intervals

```
ANCHOR + DURATION            1-7 Mon + 5 day
DURATION until ANCHOR        40 days until Dec 24
DURATION before ANCHOR       40 days before Dec 24
DURATION after ANCHOR        10 days after Oct 1
```

* DURATION is one or more `NUMBER unit` pairs (`5 days`, `4 days 9 hours`). Units: second, minute, hour, day, week, month, year, singular or plural regardless of the number.
* An ANCHOR is **one term**: a clause with its lists (`Mon,Fri`, `1-7 Mon`) or a span. A relative operator never reaches beyond its own term, in either direction (`+` does not shift the terms before it, `until`/`before`/`after` do not shift the terms after it), so a comma that does not continue a list (§4) ends the expression whether or not whitespace follows it: `2 days before Apr 10,Apr 20` is the parts `2 days before Apr 10` and `Apr 20`, and `Apr 10,Apr 20 + 2 days` is `Apr 10` and `Apr 20 + 2 days`. To shift several dates, repeat the form. The *instances* of an anchor are the maximal contiguous ranges of its set; in `+` and `until` a bare point time is an instance of length zero.
* Arithmetic is done in the anchor's zone. `day`, `week`, `month` and `year` are calendar (wall-clock) arithmetic (`dateutil.relativedelta`); `hour`, `minute` and `second` are elapsed time (convert to UTC, add, convert back). In a pair list calendar units are applied first, then elapsed units.
* The result is an ordinary set: it may be negated, have children, carry a STATE. An instance may begin long before the evaluation window, so evaluation looks back until the first instance.

### 6.1 `+` and `until`

* `ANCHOR + D`: for every instance starting at `s` the result is `[s, s + D)`. The anchor's own length is ignored: `1-7 Mon + 5 day` is Mon 00:00 → Sat 00:00, the working week starting on the first Monday. `08:00 + 2 hours` is `[08:00:00, 10:00:00)`.
* `D until ANCHOR`: for every instance ending at `e` the result is `[e − D, e)`. The end is the end of the whole instance, so "until Dec 24" includes Dec 24, as the end date of a span does: `40 days until Dec 24` is Nov 15 00:00 → Dec 25 00:00. `2 hours until 08:00` is `[06:00:00, 08:00:00)`.

### 6.2 `before` and `after`: shifted anchors

`D before ANCHOR` and `D after ANCHOR` are date/time arithmetic written out: every instance `[s, e)` of the anchor is moved **as a whole** to `[s − D, e − D)` or `[s + D, e + D)`. Unlike `+` and `until`, which build a run of length `D` from one end of the anchor, these select the shifted anchor itself: its length and time of day are kept, and a bare point time keeps its one-minute length (§2).

* `40 days before Dec 24` is Nov 14 (one day long, like `Nov 14`); `10 days after Oct 1` is Oct 11; `2 days before Apr 10 12:00` is `[Apr 8 12:00, Apr 8 12:01)`; `3 hours after 08:00` is `[11:00, 11:01)`; `1 year before Dec 20 -- Jan 10` is the whole span moved back one year.
* Both endpoints of an instance are shifted independently, so a day-long instance stays one calendar day long across a DST change, and `1 month before Mar 31` ends at the clamped date `dateutil.relativedelta` gives.
* An instance whose shifted endpoints coincide or invert is dropped.
* The result is an ordinary set: a child `08:00-09:00` under `2 days before Apr 10` selects 08:00–09:00 on Apr 8.

### 6.3 Several parts in one INTERVAL

An INTERVAL is a comma-separated list of *parts*, each a plain term or a whole relative expression, in any order; it is the **union** of its parts:

```
2 days before Apr 10, 3 days after Oct 1      Apr 8 and Oct 4
Apr 1, 2 days before Apr 10                   Apr 1 and Apr 8
Mon + 2 days, Fri                             Mon-Tue and Fri
```

Each part is evaluated on its own, with its own anchor, zone and arithmetic. A `TZ` applies to the term it ends and never spills over to another part. Commas within an ordinary clause still form lists (`Mon,Fri + 1 day`, §4).

## 7. Time model

* Time is the real instant line with a resolution of one second. Every set is a union of **half-open** ranges `[start, end)`; adjacent ranges merge. `08:00-16:00` is active at 08:00:00 and not at 16:00:00.
* Wall-clock → instant conversion, DST gaps and folds follow PEP 495 as implemented by `zoneinfo`: a nonexistent local endpoint uses the offset before the transition, an ambiguous endpoint uses the first occurrence (`fold=0`). Each endpoint is resolved independently, then the half-open UTC range is formed; ranges that become empty are dropped. So a spring-gap range `02:00-03:00` in `Europe/Budapest` on 2026-03-29 is empty, while the fall-fold range `02:00-03:00` on 2026-10-25 spans both occurrences of local 02:00 and ends at 03:00 standard time (V14).
* An interval spec denotes an infinite (possibly periodic) set. Implementations evaluate it **per window** with this contract: `eval(spec, lo, hi)` returns exactly `spec ∩ [lo, hi)`.

## 8. Time zones

### 8.1 Accepted `TZ` forms

* IANA zone IDs (`Europe/Budapest`, `Etc/UTC`, `America/Argentina/Buenos_Aires`, `UTC`), looked up case-insensitively against `zoneinfo.available_timezones()`.
* Numeric offsets: `UTC±H`, `UTC±HH`, `UTC±HHMM`, `UTC±HH:MM`, and the same with `GMT`, with the ISO sign convention (`UTC+0300` is three hours east of Greenwich, unlike POSIX `Etc/GMT-3`). `GMT+1` and similar strings are offset forms. An offset is a single token only when written without spaces: `UTC + 2 hours` is the zone `UTC` followed by the `+` of a relative expression (§6), while `UTC+2 hours` is an error (the unit `hours` has no number).
* `Z`, `UTC` and `GMT` denote UTC.

The set of zone IDs is whatever the installed system TZDB supplies. Kairos has no list of time-zone names of its own and reserves none (macros §2). An unknown zone ID or an invalid offset is an error. Two machines may know different IDs, so a config that is valid on one may fail with an unknown-zone error on the other. A name that is itself a zone ID (legacy IDs such as `CET`, `EET`, `WET`, `MET`, `EST`, `MST`, `HST`, `PST8PDT`) is accepted as that ID, because the ID lookup comes first.

Alphabetic abbreviations that are not zone IDs (`CEST`, `CST`, `IST`, `EDT`, `PST`) are **not accepted as a `TZ`**. There is no standard, globally unique abbreviation registry: the same abbreviation can identify different zones or offsets (see the IANA tz database theory notes, which warn about `CST`), so kairos infers no zone from one and ships no mapping. Use a zone ID when calendar/DST rules are intended and an offset when a fixed offset is. A config that wants an abbreviation defines it as a macro (`CEST := Europe/Berlin`, macros §2).

### 8.2 Default and display zone

A clause or span without a `TZ` uses the default zone: `--tz`, else `$TZ`, else the system zone found through `tzlocal` (fallback UTC with a stderr warning). `$TZ` follows the same accepted forms; POSIX rule strings and bare abbreviations are not interpreted specially. The default zone is also the display zone: `--next-change` output is formatted in it, and so is an `--at` without a `TZ`.

The zone of a clause (or span) applies to all of it: the calendar days, the times of day and any duration arithmetic (§6).

## 9. Grammar

```
interval = part { "," part } ;           (* union of the parts, §6.3; comma grouping per §4 *)
part     = term
         | anchor "+" duration
         | duration "until" anchor
         | duration "before" anchor
         | duration "after" anchor ;
anchor   = span | clause ;
term     = span | clause ;
span     = dateside "--" dateside [ TZ ] ;
dateside = ( ISODATE | [ YEAR ] [ MONTH ] DOM ) [ TIME ] ;
clause   = item { item } [ TZ ] ;
item     = value { "," value } ;          (* values of one kind *)
value    = atom [ "-" atom ] ;            (* no ranges of HOUR or Nm/Nmin atoms, §2 *)
duration = NUMBER unit { NUMBER unit } ;
unit     = second | minute | hour | day | week | month | year ;   (* optional plural "s" *)
```
