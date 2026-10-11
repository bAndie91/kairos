# -*- coding: utf8 -*-

"""Default configuration text (SPEC §3.3).

The text is entirely comments, so a freshly created config is inert. Two
conventions make it testable (see ``tests/test_defaults.py``):

* lines starting with ``## `` are prose and are ignored by the test;
* every other comment line is an example config line written as ``# `` followed
  by the original line (indentation preserved after that single space).
  Stripping ``# `` from them must give a config that passes ``kairos --check``.
"""

DEFAULT_CONFIG = r"""## =========================================================================
## kairos configuration
## =========================================================================
##
## kairos is a time-based state registry. This file maps time INTERVALs to
## free-text STATE names. Run `kairos` and it prints the states that are
## active right now, one per line; `kairos --next-change` prints when that
## set of states will next change.
##
## Every line of this file is a comment, so nothing is active yet. To enable
## an example, copy it below the examples section and remove the leading "# ".
## Check your edits with `kairos --check`; try a rule at another moment with
## `kairos --at "2026-10-09 10:00"`. `kairos --print-default-config` prints
## this text again.
##
## Conventions in this file: lines starting with "## " are explanations; every
## other line starting with "#" is an example, written as "# " followed by the
## original config line.
##
## -------------------------------------------------------------------------
## 1. Line format
## -------------------------------------------------------------------------
##
##   blank line             ignored
##   # comment              ignored; there are NO inline comments, because a
##                          STATE is free text and may contain "#"
##   NAME := VALUE          macro definition (section 3)
##   [!] INTERVAL [= STATE] interval line
##
## The file is UTF-8 text. Indentation uses spaces or tabs (never both in one
## line) and works like Python: a line indented deeper than the previous line
## is its child; dedenting must return to an indentation level that is open.
## The first line must not be indented. Macro lines cannot have children.
##
## An interval line is split at the FIRST "=". A leading "!" negates the
## INTERVAL (section 6). Without "= STATE" the line is not reported, but its
## INTERVAL still restricts its children. An empty INTERVAL or an empty STATE
## is an error.
##
## STATE is free text; leading and trailing blanks are trimmed. Macros are NOT
## expanded in it. Escapes: \~ is a literal ~, \@ a literal @, \\ a backslash;
## any other backslash sequence is an error.
##   ~    is replaced by the name of the nearest ancestor line that has a
##        STATE (an error if there is none).
##   @    a STATE starting with "@" is hidden: it is not reported, but the
##        text after the "@" is the name that children see as "~".
##
## -------------------------------------------------------------------------
## 2. INTERVAL syntax
## -------------------------------------------------------------------------
##
## An INTERVAL is built from items. Items of one line are all required at
## once ("and"): `Apr-Jun 1-15` is April to June AND day 1 to 15.
##
##   kind      atoms                                 range a-b
##   YEAR      100-9999 (2026)                       a <= b
##   MONTH     month name, full or short (Oct)       wraps (Dec-Feb)
##   DOM       day of month 1-31                     wraps (28-3)
##   WEEKDAY   weekday name, full or short (Mon)     wraps (Sat-Mon)
##   TIME      H:MM or H:MM:SS ("24:00" only as a    wraps past midnight
##             range end)                            (23:00-04:00)
##   HOUR      8h  = the whole hour 08:00-09:00      inclusive, wraps (22h-2h)
##   MINUTE    30m or 30min = minute :30 of every    inclusive, wraps (50m-10m)
##             hour
##   DATE      Y-m-D, each of Y, m, D may be "*"     (use "--", see below)
##             (2026-10-09, *-12-25, *-*-01)
##
## * A number below 100 is a day of month, 100 or more is a year.
## * Month and weekday names are case-insensitive and follow the LC_TIME
##   locale of the environment (LC_ALL, then LC_TIME, then LANG): in a
##   Hungarian locale write "március", in an English one "March". Nothing
##   else is accepted as a name. A name that is unknown here but valid in
##   another installed locale is reported with a "wrong locale?" hint.
##   Numbers, ISO dates and times do not depend on the locale.
## * At most one group of each kind per line; DATE cannot be combined with
##   YEAR, MONTH or DOM; dates that can never exist (Feb 30, 2026-02-29) are
##   errors, but "Feb 29" is fine.
## * No day-level item (YEAR, MONTH, DOM, WEEKDAY, DATE) means every day; no
##   TIME item means the whole day.
## * Time ranges are half-open: `08:00-16:00` is active at 08:00:00 and not
##   at 16:00:00. A point time lasts one minute (`08:00` is `08:00-08:01`), or
##   one second when written with seconds (`08:00:30`). Day selectors pick the
##   STARTING day of a range that runs past midnight: `Fri 22:00-02:00` ends
##   on Saturday 02:00.
## * DST gaps and folds follow Python's zoneinfo (PEP 495): a time that does
##   not exist uses the offset before the change, an ambiguous one its first
##   occurrence; ranges that become empty vanish.
##
## Commas. `a,b` builds a list of one kind (`Wed,Fri`, `Jun,Jul,Aug`, `1,15`,
## `Mon-Wed,Fri`, `08:00-12:00,13:00-17:00`). A comma continues the list only
## if the next item has the same kind as the item before the comma;
## otherwise it separates TERMs, and the INTERVAL is the union of its terms:
##   `Apr,Jun 1,15`        (Apr or Jun) and (1 or 15): four days
##   `Apr 1, Jun 15`       two terms: Apr 1 and Jun 15
##   `Mon 08:00-09:00, Tue 10:00-11:00`   two terms
## A comma before `NUMBER unit` (`, 2 days before ...`) never continues a
## list; it starts a new part (section 5). A list cannot mix point times and
## time ranges.
##
## Spans. `A -- B` is the span between two dates. A side is an ISO date or
## `[YEAR] [MONTH] DOM`, optionally followed by one TIME. The left side needs
## a month and a day; without a year it recurs every year. The right side may
## omit year and month (they are inherited, and move forward when the result
## would end before the start: `Dec 20 -- Jan 10`). Without times the end day
## is included (`Apr 1 -- Jun 15` ends at the end of Jun 15); with times both
## sides need one and the end is exclusive. `2026 Apr 1 -- 20`,
## `2026 Apr 1-20` and `2026-04-01 -- 20` are the same. In a year where an
## endpoint does not exist (Feb 29) it moves to the end of Feb 28.
##
## Time zones. A clause or span may end with a zone that applies to its days,
## times and arithmetic: an IANA zone ID (`Europe/Budapest`, `Etc/UTC`, any
## case), `UTC`, `GMT` or `Z`, or an offset `UTC+2`, `UTC-0330`, `GMT+01:00`
## (ISO sign: `UTC+0300` is three hours EAST of Greenwich). Bare
## abbreviations such as CEST or CST are rejected: they are not unique, so
## use a zone ID or an offset. Without a zone the default zone is used:
## `--tz`, else $TZ, else the system zone (UTC with a warning if unknown).
## List zone IDs with:
##   python3 -c 'from zoneinfo import available_timezones as a; print(*sorted(a()), sep="\n")'
## Zone data comes from the IANA time zone database (system tzdata).
##
## -------------------------------------------------------------------------
## 3. Macros
## -------------------------------------------------------------------------
##
##   NAME := STRING         literal text
##   NAME := ! COMMAND      the standard output of a shell command
##
## NAME is everything before the first ":=" (trimmed). It may contain spaces
## and punctuation (`Mary's birthday`), may start with, end with or contain
## another macro's name, and is case-sensitive. It must not be empty, contain
## "=", start with "!" or lack a letter, and must not be entirely a month or
## weekday name of the locale, a duration unit, until, before, after, UTC,
## GMT or Z ("Mon morning" is fine, "Mon" is not).
##
## Before an INTERVAL (or a STRING value) is read, every visible macro name
## that stands as a whole word is replaced by its value, once (the result is
## not rescanned). The longest matching name wins. `mary` does not match
## inside `annamary`. Macros are not expanded in STATE or in COMMAND text.
##
## A macro defined at indentation 0 is visible to all following lines; one
## defined as a child of a line is visible in that line's subtree only. A name
## that is already visible cannot be defined again; sibling subtrees may reuse
## names.
##
## COMMAND is run with ${SHELL:-/bin/sh} -c, stdin from /dev/null. Newlines in
## its output become spaces and the trailing newline is dropped. It sees the
## caller's environment plus
##   KAIROS_MACRO_<NAME>        value of each visible macro, NAME as written
##   KAIROS_NOW                 the evaluation instant, ISO 8601 with offset
##   KAIROS_INTERVAL_<LEVEL>    INTERVAL text of the line and each ancestor
##   KAIROS_STATE_<LEVEL>       their STATE (LEVEL counts from 0)
## A command runs lazily: when a line first uses its macro, and never if the
## macro is unused or only used below a line that is not active at the
## evaluation time (default mode); `--check` and `--next-change` never skip.
## A failing command (non-zero exit) is an error reported at the macro's line
## when it is evaluated. The output is a snapshot taken at that moment: a
## command that yields only this year's date cannot predict next year's.
##
## SECURITY: macro commands are arbitrary code run with YOUR privileges and
## are not sandboxed. Only put commands in this file that you trust, and keep
## the file writable by you only.
##
## -------------------------------------------------------------------------
## 4. Hierarchy, negation and reported states
## -------------------------------------------------------------------------
##
## A child restricts its parent: with `Mon-Fri` and a child `Dec`, the child
## means "weekdays in December". Siblings are independent. `*-*-01` with a
## child `Fri` selects days that are both a 1st and a Friday; the first
## Friday of a month is `1-7 Fri`.
##
## A child `! INTERVAL` subtracts from its parent; at top level it is the
## complement. The effective set of a line is its parent's set intersected
## with its INTERVAL (or minus it, when negated).
##
## A line is reported when it has a STATE that does not start with "@" and is
## not empty after "~" substitution. Several lines with the same name form
## one state, active when any of them is. States are printed in the order of
## the first line that names them. A state ending exactly when another line
## of the same name starts is not a change for `--next-change`.
##
## -------------------------------------------------------------------------
## 5. Relative intervals
## -------------------------------------------------------------------------
##
## DURATION is one or more `NUMBER unit` pairs (`5 days`, `4 days 9 hours`);
## units: second, minute, hour, day, week, month, year (singular or plural).
## An ANCHOR is one term (a clause with its lists, or a span). Its instances
## are the maximal contiguous ranges of its set. Day, week, month and year
## arithmetic is calendar arithmetic in the anchor's zone; hours, minutes and
## seconds are elapsed time; calendar units are applied first.
##
##   ANCHOR + DURATION       from the START of each instance, DURATION long
##                           (`1-7 Mon + 5 day`: Monday to Saturday)
##   DURATION until ANCHOR   DURATION long, up to and including the whole
##                           instance (`40 days until Dec 24`)
##   DURATION before ANCHOR  every instance moved back as a whole, its length
##                           kept (`3 days before Dec 24` is Dec 21)
##   DURATION after ANCHOR   every instance moved forward as a whole
##
## An INTERVAL may have several parts separated by commas: plain terms and
## relative expressions in any order; the result is their union. A relative
## operator never reaches beyond its own term, so a comma ends it:
##   `2 days before Apr 10, Apr 20`   Apr 8 and Apr 20
##   `2 days before Apr 10,20`        Apr 8 and Apr 18 (a list in one clause)
##   `Apr 1, 2 days before Apr 10`    Apr 1 and Apr 8
## The result of a relative expression is an ordinary set: it can be negated,
## narrowed by children, or carry a STATE.
##
## -------------------------------------------------------------------------
## 6. Errors and limits
## -------------------------------------------------------------------------
##
## Errors are printed to stderr as `kairos: FILE:LINE: error: MESSAGE`, all of
## them in one run where possible, with exit status 2 and an empty stdout.
## The default config, when called without --config, is created if does not exist.
##
## Non-features: daemon or watch mode, notifications, running actions when a
## state changes, config includes, calendars other than Gregorian, sub-second
## precision, sandboxing command executions. (Combine with other tools to
## achieve them)
##
## -------------------------------------------------------------------------
## Examples
## -------------------------------------------------------------------------
##
## Plain intervals with a state each; overlapping ranges are fine.
# 08:00-16:00 = work
# 12:00-13:00 = lunch
# 23:00-04:00 = night shift
# Dec-Feb = winter
# Sat,Sun = weekend
## 8h-12h is the hours 8 to 12 inclusive; 30m is minute 30 of every hour.
# Mon-Fri 8h-12h 30m = half past, mornings
##
## A child restricts its parent; the parent has no state of its own here.
# Mon-Fri
#   08:00-12:00,13:00-17:00 = office hours
#   Dec = weekdays in December
##
## "@" hides a line; its name is what the children get for "~".
# Jun,Jul,Aug = summer
#   Sun = @Sunday
#     20:00-23:00 = evening in summer's ~s
##
## "!" subtracts from the parent. This is the 1st of the month when it is
## not a weekend. (The first Friday of a month would be `1-7 Fri`.)
# *-*-01 = first of the month
#   ! Sun,Sat = first of the month, on a weekday
##
## Relative intervals.
# 1-7 Mon = first Monday
# 1-7 Mon + 5 day = first working week
# 1-7 Mon + 4 days 9 hours = long run
# 40 days until Dec 24 = christmas run-up
# 3 days before Dec 24 = last order day
# 10 days after Oct 1 = settling in
##
## Spans, with and without years and times.
# Apr 1 -- Jun 15 = season
# Dec 20 -- Jan 10 = holidays
# 2026 Apr 1 -- 20 = project phase
# 2026-05-04 09:00 -- 2026-05-04 17:00 = workshop
##
## Time zones.
# *-12-* 08:00-09:00 Europe/Berlin = berlin call
# 08:00-09:00 UTC+0300 = moscow call
##
## Several parts in one interval.
# Apr 1, 2 days before Apr 10 = day and shift
# Mon + 2 days, Fri = long weekend
# 2 days before Apr 10,20 = two shifted dates
##
## String macros, including names with spaces and punctuation.
# Q1 := Jan-Mar
# Q1 = first quarter
# Mary's birthday := Jun 1
# Mary's birthday = party
##
## Command macros. `ncal -e` prints Easter in a locale-dependent form, so
## `date` turns it into an ISO date (YYYY-MM-DD). The value is only this
## year's Easter (a snapshot, see section 3).
# Easter := ! date -d "$(ncal -e)" +%F
# Easter = Χριστὸς ἀνέστη!
# 2 days before Easter = Holy Friday
# Easter + 1 week = Bright Week
## KAIROS_NOW holds the evaluation instant; `date` reduces it to a day.
# Today := ! date -d "$KAIROS_NOW" +%F
# Today = today
##
## A macro inside a subtree is visible only in that subtree.
# Jun,Jul,Aug = holiday season
#   Break := Jul 1-14
#   Break = summer break
"""
