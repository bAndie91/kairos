# kairos — INTERVAL syntax and semantics

Part of the [kairos specification](../SPEC.md). An INTERVAL denotes a set of instants, possibly infinite and periodic. Macros are expanded before the text reaches the lexer ([macros](macros.md#expansion)); how INTERVALs combine into states is in [states.md](states.md).

## Lexical rules

After macro expansion the text is tokenised; whitespace only separates tokens. Longest match, in this order:

| Token | Form |
|-------|------|
| `ISODATE` | `Y-m-D`: `Y` is 4 digits or `*`, `m` and `D` 1–2 digits or `*`; no inner whitespace |
| `TIME` | `H:MM[:SS]`: `H` 1–2 digits, `MM` and `SS` 2 digits (`8:00` = `08:00`); also the time form of `--at` |
| `HOUR` | `Nh` or `N:*`: two spellings of one token, every minute of hour N |
| `MINUTE` | `Nm`, `Nmin` or `*:MM`: two spellings of one token, minute MM of every hour |
| `NUMBER` | digits |
| `--` `-` `+` `,` `*` | punctuation: `--` is the span operator, `-` the range operator |
| `TZ` | a [time-zone token](#time-zones) |
| `WORD` | a month or weekday name of the effective locale, a duration unit, `until`, `before` or `after` |

A token has no inner whitespace. A numeric zone offset is one token only when written without spaces: `UTC+2` is a zone, `UTC + 2 hours` is the zone `UTC` followed by the `+` of a relative interval, and `UTC+2 hours` is an error (the unit has no number).

Any other word is an error: `unknown word 'X' (undefined macro?)`. The lexer does not stop at the first one: **every** unknown word of the line is reported, each with file and line, in order of appearance. That line is not parsed further, but all other lines are still checked.

**Wrong locale hint.** An unknown word is often a month or weekday name in another locale (`May` under a Hungarian locale), so the diagnostic then adds `wrong locale?` and names the first few installed locales (in the system's listing order, then `…`) that know the word: `unknown word 'May' (undefined macro? wrong locale? "May" is in "en_US.UTF-8" locale)`. Only the locale module does this: it enumerates the installed locales (the platform's own list, e.g. `locale -a`), tries each through the same locale-aware facilities used for parsing and restores the effective locale afterwards. The search runs only for an unknown word, never on the normal path; if the locales cannot be listed the hint is omitted.

### Month and weekday names

Names come from the effective `LC_TIME` locale and from nothing else: not a fixed English vocabulary, no alias list, no translation or transliteration table, no fallback names. They are case-insensitive as far as the locale-aware facilities provide, full and abbreviated forms are accepted, and non-ASCII letters, combining marks and punctuation that a name needs (the dot in `janv.`) are part of it and survive tokenization unchanged. A name with internal whitespace is accepted only if the library treats it as one name. ISO dates and numbers are locale-independent.

* The locale is chosen with Python's `locale` module from the environment (`locale.setlocale(locale.LC_TIME, "")`), which gives `LC_ALL` over `LC_TIME` over `LANG` over the platform default; kairos never reads those variables or resolves precedence itself, and never forces the `C` locale.
* It is set once, before any lexing, and not switched per token (process-global state is fine for a CLI).
* The name tables come from the locale-aware date/time facilities (`calendar`, `datetime` formatting). The lexer recognises complete names from there before it classifies a word as generic.

With `LC_TIME=hu_HU.UTF-8`, `március 15 = x` is valid and `Mar 15 = x` is an unknown word; under an English locale it is the other way round (tests skip a locale that is not installed).

## Items

| Kind | Atom | Range `a-b` |
|------|------|-------------|
| `YEAR` | integer 100–9999 | `a ≤ b` required |
| `MONTH` | month name | wraps across the year (December–February selects December, January, February) |
| `DOM` | integer 1–31 (leading zero ok) | wraps (`28-3` = 28…31, 1…3) |
| `WEEKDAY` | weekday name | wraps from the locale's last weekday to its first |
| `TIME` | `H:MM[:SS]`, H = 0–23 (`24:00` only as a range end) | wraps past midnight (`23:00-04:00`) |
| `HOUR` | `Nh` or `N:*`, N = 0–23 | not allowed |
| `MINUTE` | `Nm`, `Nmin` or `*:MM`, N and MM = 0–59 | only as `*:MM-*:MM` |
| `DATE` | `ISODATE` (wildcards allowed) | not allowed (use a [span](#spans)) |

* Numbers below 100 are a DOM, 100 and above a YEAR; 0 and 32–99 are errors. `2026-2028` is a year range.
* A single `-` needs no whitespace but may have it (`Mon - Fri`), except inside an `ISODATE`.
* A `TIME` outside a range lasts one minute (`08:00` = `[08:00:00, 08:01:00)`), or one second when written with seconds (`08:00:30`).
* `TIME`, `HOUR` and `MINUTE` are separate kinds and a range cannot mix them (`15:00-*:20` is an error). A clause may combine items of the three kinds, which must all hold: `Mon-Fri 08:00-13:00 30m` is minute 30 of the hours 8 to 12 on weekdays.

**No hour ranges, no `Nm` ranges.** `15h-16h` could be the hour 15:00–16:00 or the two hours 15 and 16, and `15m-20m` the minutes 15 up to 20 or 15 through 20, so these are errors and the message names the replacement: write `15:00-16:00`, and `*:15-*:20` for minutes. Like every time range these are left-closed and right-open, so `*:15-*:20` is `[15, 20)` minutes past every hour, the ends must differ, and a smaller end wraps into the next hour (`*:50-*:10` is `[h:50, h+1:10)` for every hour h). Atoms and lists of atoms (`8h`, `30m`, `8h,10h`) stay valid; `8h` is `08:00-09:00` and `30m` is `[h:30, h:31)` every hour.

## Clauses

A *clause* is a whitespace-separated sequence of items, optionally ending with a `TZ`. All items must hold at once: `Apr-Jun 1-15` is month in Apr–Jun **and** day in 1–15. Violations are errors:

* at most one item group per kind; `DATE` excludes `YEAR`, `MONTH` and `DOM`;
* at least one item that is not a `TZ`;
* `*` only inside an `ISODATE`, as the minutes of an `HOUR` and as the hour of a `MINUTE`;
* a `DATE`/`DOM`/`MONTH` combination that can never exist (`Feb 30`, `2026-02-29`, `*-04-31`); the datetime library decides, nothing is hand-written. `Feb 29` and `*-*-31` are fine.

Without a `TIME`-like item a clause covers whole days; without a day-level item (`YEAR`, `MONTH`, `DOM`, `WEEKDAY`, `DATE`) it covers every day; with only a day it covers that day in every month.

## Lists and commas

`a,b` builds a list inside one kind: `Wed,Fri`, `Jun,Jul,Aug`, `1,15`, `Mon-Wed,Fri`, `08:00-12:00,13:00-17:00`. A comma continues the current list iff the next item has the same kind as the item right before it; otherwise it ends the current *term* and the next item starts a new one. A list cannot mix single `TIME` atoms with time ranges. The INTERVAL is the union of its terms. Whitespace around commas is insignificant: `10,20` equals `10, 20`.

| Text | Meaning |
|------|---------|
| `Apr,Jun 1,15` | (Apr or Jun) and (1 or 15): Apr 1, Apr 15, Jun 1, Jun 15 |
| `Apr 1, Jun 15` | two terms: Apr 1 and Jun 15 |
| `Mon-Fri 08:00-12:00,13:00-17:00` | one clause with two time ranges |
| `Mon 08:00-09:00, Tue 10:00-11:00` | two terms |
| `1 -- 5, 10 -- 12` | two spans: days 1–5 and days 10–12 |
| `1 -- 5, 10` | a span and a clause: days 1–5, and day 10 |
| `Apr 1, 2 days before X` | the term `Apr 1` and the part `2 days before X`, never the day list `1,2` |

A span side is one date and never a list, since a span cannot end on 5 and on 10 too, nor start on 5 and on 10 too. A comma therefore never continues a list into or out of a span: a comma directly after a span ends its term, and a comma directly before one (the text after it has the form `dateside -- dateside`) ends the term before it, even though `5` and `10` are both days of the month. A comma before a duration (`NUMBER unit`) never continues a list either: that `2` is the count of a duration, not a day. Nor does one in the anchor of `until`, `before` or `after` ([several parts](#several-parts-in-one-interval)).

## Spans

`A -- B` is a *span* between two dates.

* A side is an `ISODATE` or `[YEAR] [MONTH] DOM`, each optionally followed by one `TIME`; no lists, ranges or weekdays. A `TZ` may end the span and applies to both sides.
* The left side may be a lone DOM (`1 -- 5` is days 1 to 5 of every month, the same as `1-5`) or a concrete month and day. An absent or `*` year recurs every year.
* The right side may omit year and month and inherits them from the left: `2026 Apr 1 -- 20`, `2026 Apr 1-20` and `2026-04-01 -- 20` are equivalent, and `Apr 1 -- Jun 15` has no year at all, so it recurs.
* If the right date then lies before the left: with no month it moves to the next month, with no explicit year to the next year (`Dec 20 -- Jan 10` works).
* Without times the span is whole days, **end date inclusive**: `[00:00 of the first day, 00:00 after the last day)`. With times both sides need one: `[start, end)`.
* A date that does not exist in a year (`Feb 29` in a non-leap year) is not a day of the span, which covers exactly those of its days that exist. `Feb 29 -- Mar 1` is two days in a leap year and one (Mar 1) otherwise; `Feb 20 -- Feb 29` ends on Feb 28 in a non-leap year; `Feb 29 -- Feb 29` is empty there. As instants a nonexistent endpoint, start or exclusive end, is the boundary between Feb 28 and Mar 1 (Mar 1 00:00 in the span's zone); a `TIME` on such a side is ignored.

## Relative intervals

```
ANCHOR + DURATION            1-7 Mon + 5 days
DURATION until ANCHOR        40 days until Dec 24
DURATION before ANCHOR       40 days before Dec 24
DURATION after ANCHOR        10 days after Oct 1
```

A DURATION is one or more `NUMBER unit` pairs (`5 days`, `4 days 9 hours`) with the units second, minute, hour, day, week, month, year, singular or plural regardless of the number. An ANCHOR is **one term**, a clause (with its lists: `Mon,Fri`, `1-7 Mon`) or a span. Its **instances** are the maximal contiguous ranges of its set; a point time has an instance of length zero for `+` and `until`.

* `ANCHOR + D`: for every instance starting at `s`, `[s, s + D)`. The anchor's own length is ignored: `1-7 Mon + 5 days` runs Monday 00:00 to Saturday 00:00, the working week of the first Monday.
* `D until ANCHOR`: for every instance ending at `e`, `[e − D, e)`. The end is the end of the whole instance, so `40 days until Dec 24` is Nov 15 00:00 to Dec 25 00:00: "until Dec 24" includes Dec 24, as a span's end date does.
* `D before ANCHOR` / `D after ANCHOR`: every instance `[s, e)` is moved **as a whole** to `[s − D, e − D)` or `[s + D, e + D)`, keeping its length and time of day. `40 days before Dec 24` is Nov 14, `10 days after Oct 1` is Oct 11, `2 days before Apr 10 12:00` is `[Apr 8 12:00, Apr 8 12:01)` (a bare point time keeps its one-minute length), `3 hours after 08:00` is 11:00, and `1 year before Dec 20 -- Jan 10` is the whole span moved back a year. Both endpoints are shifted independently, so a day-long instance stays one calendar day across a DST change, and `1 month before Mar 31` ends at the date `dateutil.relativedelta` clamps to. An instance whose shifted endpoints coincide or invert is dropped.
* Arithmetic is in the anchor's zone: day, week, month and year units are calendar arithmetic (`dateutil.relativedelta`), hour, minute and second units are elapsed time (convert to UTC, add, convert back). In a pair list calendar units apply first, then elapsed ones.
* The result is an ordinary set: it can be negated, have children and carry a STATE; a child `08:00-09:00` under `2 days before Apr 10` selects 08:00–09:00 on Apr 8.
* An instance may start long before an evaluation window; evaluation looks back until the first instance.

### Several parts in one INTERVAL

An INTERVAL is a comma-separated list of *parts*, each a plain term or a whole relative expression, and is the **union** of its parts:

```
2 days before Apr 10, 3 days after Oct 1      Apr 8 and Oct 4
Apr 1, 2 days before Apr 10                   Apr 1 and Apr 8
Mon + 2 days, Fri                             Mon-Tue and Fri
```

A comma between terms starts a new part unless it continues a list inside a clause. A relative operator never reaches beyond its own term, in either direction, so a comma ends the relative expression regardless of whitespace. Before `+` the anchor is the clause written before it, lists included: `Mon,Fri + 1 day` shifts both days, and `Apr 10,Apr 20 + 2 days` is `Apr 10` plus `Apr 20 + 2 days`. After `until`, `before` or `after` the anchor ends at the next comma, so the list rule does not apply there: `2 days before Apr 10,20` and `2 days before Apr 10, 20` are Apr 8 (shifted) and Apr 20 (not shifted), not Apr 8 and Apr 18, and `2 days before Mon,Fri` shifts Monday only. To shift several dates, repeat the form. Each part has its own anchor, zone and arithmetic; a `TZ` applies to the term it ends and never spills over to another part. A trailing comma is an error.

## Grammar

```
interval = part { "," part } ;           (* union of the parts; comma grouping as above *)
part     = term
         | anchor "+" duration
         | duration ( "until" | "before" | "after" ) anchor ;
anchor   = term ;
term     = span | clause ;
span     = dateside "--" dateside [ TZ ] ;   (* a side is one date, never a list *)
dateside = ( ISODATE | [ YEAR ] [ MONTH ] DOM ) [ TIME ] ;
clause   = item { item } [ TZ ] ;
item     = value { "," value } ;          (* values of one kind *)
value    = atom [ "-" atom ] ;            (* no HOUR ranges, no Nm/Nmin ranges *)
duration = NUMBER unit { NUMBER unit } ;
unit     = second | minute | hour | day | week | month | year ;   (* optional plural "s" *)
```

## Time model

* Time is the real instant line with one-second resolution. Every set is a union of **half-open** ranges `[start, end)`, adjacent ranges merge: `08:00-16:00` is active at 08:00:00 and not at 16:00:00.
* A clause is evaluated in its zone: for every local calendar day that satisfies its day-level items and every time range of the clause (default `00:00-24:00`) one range `[day+t1, day+t2)` is produced. If `t2 < t1` the end is on the following day (`t1 = t2` is an error), so day selectors pick the **starting** day.
* A wildcard selects every value of its field, and missing time fields are wildcards in their natural ranges. `*:50-*:10` ends in the next hour just as a time range wraps into the next day.
* Wall clock to instant follows PEP 495 as implemented by `zoneinfo`: a nonexistent local endpoint uses the offset before the transition, an ambiguous one its first occurrence (`fold=0`). Each endpoint is resolved independently, then the half-open UTC range formed; ranges that become empty are dropped. So the spring-gap range `02:00-03:00` in `Europe/Budapest` on 2026-03-29 is empty, and the fall-fold range `02:00-03:00` on 2026-10-25 covers both occurrences of 02:00 and ends at 03:00 standard time (V14).
* Evaluation is **per window**: `eval(spec, lo, hi)` returns exactly `spec ∩ [lo, hi)`.

## Time zones

A **time-zone token** (`TZ`) is accepted in one of these forms, and "is a TZ token" means no more than "the timezone module resolves it":

* an IANA zone ID of the installed tz database, looked up case-insensitively against `zoneinfo.available_timezones()` (`Europe/Budapest`, `America/Argentina/Buenos_Aires`, `UTC`, and legacy IDs such as `CET` or `PST8PDT` when the installation has them);
* a numeric offset `UTC±H`, `UTC±HH`, `UTC±HHMM` or `UTC±HH:MM`, and the same with `GMT`, with the ISO sign convention (`UTC+0300` is three hours east of Greenwich, unlike POSIX `Etc/GMT-3`);
* `Z`, `UTC` and `GMT`, all meaning UTC.

Alphabetic abbreviations that are not zone IDs (`CST`, `CEST`, `IST`, `EDT`, `PST`) are **not** accepted: there is no standard registry mapping them to zones, and the same abbreviation can name different zones or offsets ([IANA tz theory](https://www.iana.org/time-zones/theory)). Kairos neither infers a zone from them nor ships a table; use a zone ID when calendar and DST rules are meant, a numeric offset for a fixed offset. Which IDs exist depends on the installed tz database, and kairos keeps no list of its own. The abbreviations `zoneinfo` returns from `datetime.tzname()` serve only as labels in diagnostics and display.

A `TZ` ending a clause or span applies to the whole of it: its calendar days, times of day and duration arithmetic. Without one the display zone (`--tz`) applies; a relative expression uses the zone of its anchor.
