"""Default configuration text (SPEC §3.3).

The text has no active lines. Documentation lines start with ``## ``. In the
EXAMPLES section every example config line is ``# `` followed by the original
line (indentation kept after the ``# ``), so removing those two characters
yields a valid config; ``tests/test_default_config.py`` checks exactly that.
"""
DEFAULT_CONFIG = r"""## ============================================================================
## Kairos configuration
## ============================================================================
##
## Kairos tells which of your named states are active at a given moment
## (`kairos`) and when the set of active states changes next (`kairos -n`).
## You describe states with time INTERVALs in this file. Nothing below is
## enabled yet: copy lines from the EXAMPLES section at the end, remove the
## leading "# " (hash and one space), and edit them.
##
## Run `kairos --check` to validate this file and `kairos --print-default-config`
## to get this text again. See SPEC.md in the source tree for the full details.
##
##
## LINES
## -----
##   blank line        ignored
##   # comment         the first non-blank character is "#"; there are NO inline
##                     comments (a STATE is free text and may contain "#")
##   NAME := VALUE     macro definition (see MACROS)
##   [!] INTERVAL [= STATE]
##                     interval line; split at the FIRST "=": the INTERVAL never
##                     contains "=". Without "= STATE" the line is not reported
##                     but still restricts its children.
##
## The file is UTF-8 text with LF line endings.
##
##
## INDENTATION AND HIERARCHY
## -------------------------
## Indent with spaces or with tabs, never mixed. A line indented deeper than the
## previous line becomes its child; dedent only to a level that is still open
## (like Python). The first line is not indented. Any consistent width works.
##
## A child restricts its parent: the effective set of a line is the parent's
## effective set INTERSECTED with the line's INTERVAL. Siblings are independent.
##     Mon-Fri
##         Dec = weekdays in December
## `! INTERVAL` negates: the line's INTERVAL is SUBTRACTED from its parent's set
## (at top level: from all time).
##
##
## STATE
## -----
## Free text after "=" (leading/trailing blanks trimmed, inner blanks kept).
## Macros are NOT expanded in a STATE. Several lines may use the same name: the
## state is active when any of them is. Output lists each active name once, in
## the order its first line appears in this file.
##   ~          is replaced by the name of the parent line (the nearest ancestor
##              that has a STATE, after its own "~" substitution and without its
##              leading "@"); an error if there is none
##   @name      a leading "@" HIDES the state: it is never reported, but its
##              name (without "@") is what children see as "~"
##   \~  \@  \\ escapes for a literal "~", "@" (as first character) and "\";
##              any other backslash sequence is an error
##
##
## INTERVAL: ONE CLAUSE
## --------------------
## A clause is items separated by blanks; ALL of its items must hold. Each kind
## may appear once per clause (use a comma list inside the item for more).
##
##   kind     forms                          notes
##   YEAR     2026   2026-2028                a number >= 100 is a year (100-9999)
##   MONTH    Dec   Dec-Feb                  full or abbreviated name; ranges wrap
##   DOM      1   1-7   28-3                 day of month 1-31; ranges wrap
##   WEEKDAY  Mon   Mon-Fri   Fri-Mon        full or abbreviated name; ranges wrap
##   TIME     08:00   08:00:30               a point lasts one minute (one second
##            08:00-16:00   23:00-04:00      with seconds); 23:00-04:00 rolls over
##            01:00-24:00                    midnight; 24:00 only ends a range
##   HOUR     8h   8h-12h   22h-2h            8h means 8:*, the whole hour 8
##   MINUTE   30m   30min   50m-10m           30m means *:30, minute 30 of EVERY hour
##   DATE     2026-12-24   *-12-25   *-*-01   ISO date; "*" matches anything; no ranges
##
## Names of months and weekdays follow your locale (LC_ALL, then LC_TIME, then
## LANG), e.g. "March 15" in English and "március 15" in Hungarian: Kairos takes
## the names from the date/time library of your system and has no list of its
## own. An unknown word is an error. The examples below use English names, so
## under another locale write that locale's names instead. Numbers, ISO dates
## and times are the same everywhere.
##
## Lists and commas. "A,B" makes a list when B is of the SAME kind as the item
## just before the comma; otherwise the comma starts a new part (below):
##   Mon-Fri 08:00-12:00,13:00-17:00     weekdays, in both time ranges
##   Apr,Jun 1,15                        the 1st and 15th of April and of June
##   Apr 1, Jun 15                       two separate days (a new part)
##
## A clause with a day selector and a rolling-over time range, on ONE line,
## picks the STARTING day: "Fri 22:00-02:00" is Fri 22:00 to Sat 02:00. On
## nested lines (Fri / 22:00-02:00) the result is a plain intersection instead.
##
##
## INTERVAL: SPANS
## ---------------
## "FROM -- TO" is one continuous period (note the two dashes). A side is
## [YEAR] [MONTH] DAY [TIME] or an ISO date; no lists, ranges or weekdays. The
## last day is INCLUDED. A missing year/month on the right is taken from the left;
## a right side that would fall before the left one moves to the next month/year.
## Without a year the span recurs every year. Times need to be on both sides.
##   Apr 1 -- Jun 15            every year, Apr 1 to Jun 15 inclusive
##   Dec 20 -- Jan 10           over New Year
##   2026 Apr 1 -- 20           same as 2026-04-01 -- 20
##   Apr 1 08:00 -- Apr 3 17:00
##
##
## INTERVAL: RELATIVE PERIODS
## --------------------------
## A duration is "NUMBER unit" pairs: second minute hour day week month year
## (plural allowed), e.g. "5 days" or "4 days 9 hours". Day, week, month and
## year steps follow the calendar (the wall clock); hours, minutes and seconds
## are elapsed time. The ANCHOR is one clause or span.
##   ANCHOR + D          from the start of each anchor instance, D long
##   D until ANCHOR      D long, ending with each anchor instance (the whole last
##                       day included): "40 days until Dec 24" is Nov 15 - Dec 24
##   D before ANCHOR     the anchor itself, moved earlier by D (same length and
##                       time of day): "2 days before Apr 10 12:00" is Apr 8 12:00
##   D after ANCHOR      the anchor itself, moved later by D
## Relative expressions are ordinary parts, so they can be mixed with other parts:
##   2 days before Apr 10, 3 days after Oct 1       Apr 8 and Oct 4
##   Apr 1, 2 days before Apr 10                    Apr 1 and Apr 8
##   Mon + 2 days, Fri                              Mon-Tue and Fri
## A comma ends the anchor: "Apr 10, Apr 20 + 2 days" is Apr 10 plus the two
## days from Apr 20. The result of any of them can be negated or have children.
##
##
## INTERVAL: TIME ZONES
## --------------------
## A zone written at the end of a clause or span applies to that part. Without
## one, the default zone is used: --tz, else $TZ, else the system zone.
##   Europe/Berlin         an IANA zone name
##   UTC   GMT   Z        UTC
##   UTC+0300  UTC-4:30    a numeric offset (no blanks around the sign:
##                         "UTC + 2 hours" is UTC plus a duration)
## Abbreviations such as CEST or CST are not accepted: names are ambiguous.
## Times are wall-clock in the zone: a time skipped by a clock change is read with
## the offset before the change, a repeated one at its first occurrence.
##
##
## MACROS
## ------
##   NAME := TEXT        NAME stands for TEXT in later INTERVALs (and macro values)
##   NAME := ! COMMAND   NAME stands for the output of COMMAND
## NAME is the text before the first ":=": case sensitive, may contain blanks
## and punctuation ("Mary's birthday"), must not contain "=" or be empty. Longer
## names win over shorter ones. Every WHOLE WORD equal to a name is replaced
## once (the replaced text is not searched again). Names of months, weekdays,
## duration units and the words until, before, after, UTC, GMT and Z are
## reserved. A macro defined at the top level is visible to all following lines;
## one defined inside a subtree only inside that subtree. Redefining a visible
## name is an error.
##
## COMMAND runs with ${SHELL:-/bin/sh} -c, stdin from /dev/null, only when a line
## actually uses the macro; its output (newlines become blanks) is the value;
## a non-zero exit status is an error. Macros are not expanded inside COMMAND;
## instead the environment holds KAIROS_NOW (the evaluation time, ISO 8601),
## KAIROS_MACRO_<name> for every visible macro, and for interval lines
## KAIROS_INTERVAL_<n> / KAIROS_STATE_<n> for the line and each ancestor
## (n = indentation level). A command is a snapshot taken at evaluation time:
## "kairos -n" in December cannot know next year's Easter.
##
## SECURITY: macro commands run with YOUR privileges every time Kairos reads
## this file (also for --check and --next-change). Put only commands you trust
## here, keep this file writable by you alone, and never run Kairos on a config
## from an untrusted source. A command's output becomes part of the INTERVAL
## text, so it can change what the interval means.
##
##
## COMMAND LINE
## ------------
##   kairos                   print the active states, one per line
##   kairos --at "2026-10-09 12:00"   as of a given moment (ISO 8601, optional offset)
##   kairos -n                print the next moment the set of states changes
##   kairos -n --format iso   ... as ISO 8601 with offset (or "epoch", or strftime)
##   kairos --tz Europe/Budapest      default zone        kairos -c FILE   other config
## Exit status: 0 on success (even if no state is active), 2 on any error.
## Errors go to stderr as "kairos: PATH:LINE: error: MESSAGE"; stdout stays empty.
##
##
## ============================================================================
## EXAMPLES
## ============================================================================
## Every line starting with "# " below is a config line: remove the "# " (two
## characters) to enable it. Lines starting with "## " are explanations.
## All of them together form one valid config (the macro examples need `date`,
## and `ncal` for Easter).

## Working hours, with a lunch break inside them
# 08:00-16:00 = work
# 12:00-13:00 = lunch

## A time range may roll over midnight; month ranges may wrap around the year end
# 23:00-04:00 = night
# Dec-Feb = winter

## Children restrict their parent: weekdays in December. A negated child
## subtracts: weekdays, except the lunch hour
# Mon-Fri
#     Dec = weekdays in December
#     ! 12:00-13:00 = weekday, outside lunch

## "~" is the parent's name and "@" hides a state while keeping its name for the
## children: the summer Sundays between 20:00 and 23:00 are reported as
## "evening in summer's Sundays"
# Jun,Jul,Aug = summer
#     Sun = @Sunday
#         20:00-23:00 = evening in summer's ~s

## Nested lines intersect: the 1st of the month that is not a weekend day; and
## the first Friday of the month is "days 1-7 that are Fridays"
# *-*-01 = first of the month
#     ! Sun,Sat = first of the month, on a weekday
# 1-7 Fri = first Friday

## ISO dates, with wildcards and lists
# *-12-25 = Christmas
# 2026-12-24,2026-12-25 = Christmas 2026

## Spans: recurring, over New Year, and with an explicit year
# Apr 1 -- Jun 15 = spring season
# Dec 20 -- Jan 10 = holidays
# 2026 Apr 1 -- 20 = project phase
# Mar 29 08:00 -- Mar 29 17:00 = release day, working hours

## Several parts in one INTERVAL: "Mon,Wed" is a list; the comma after the time
## range starts a new part. Monday and Wednesday mornings, plus Friday afternoons
# Mon, Wed 06:00-12:00, Fri 12:00-18:00 = shifts

## Hours and minutes: the whole of 8h (8:*), and every half past (*:30) from 8 to 12
# 8h = hour 8
# 8h-12h 30m = half past, in the morning

## Time zones: a named zone, and a numeric offset
# *-07-* 08:00-09:00 Europe/Berlin = Berlin office, July mornings
# 08:00-09:00 UTC+0300 = stand-up

## Relative periods: the working week starting on the first Monday of the month,
## the 40 days up to Christmas Eve, and 49 days after Easter (see Easter below)
# 1-7 Mon + 5 day = working week of the month
# 40 days until Dec 24 = Christmas run-up
# 40 days before Dec 24 = start of the run-up
# 10 days after Oct 1 = Oct 11, by arithmetic
# 2 days before Apr 10, 3 days after Oct 1 = Apr 8 and Oct 4

## Macros: names may contain blanks and punctuation, longer names win, and the
## value may be anything that is valid in an INTERVAL
# Mary's birthday := Jun 14
# Mary's birthday = Mary is celebrating
# Q1 (first quarter) := Jan-Mar
# Q1 (first quarter) 08:00-12:00 = first quarter mornings
# Workday := Mon-Fri 08:00-16:00
# Workday = at work

## Command macros. `ncal -e` prints Easter in a locale-dependent form that is
## not a date Kairos reads, so `date` converts it to an ISO date. A command
## sees KAIROS_NOW, so it can pick the current year
# Easter := ! date -d "$(ncal -e)" +%F
# Easter = Easter Sunday
# 2 days before Easter = Good Friday
# 1 day after Easter = Easter Monday
# 49 days after Easter = Pentecost
# This year := ! date -d "$KAIROS_NOW" +%Y
# This year Dec = December of the current year
"""
