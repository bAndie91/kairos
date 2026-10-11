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
## kairos configuration examples
## =========================================================================
##
## kairos prints active state names; see `man kairos` for the complete
## command-line and configuration reference.
## To try an example, copy it below and remove the leading "# ".
## Validate edits with `kairos --check`; print this file with
## `kairos --print-default-config`.
##
## Conventions: lines starting with "## " are explanations; each example
## starts with "# " followed by the original config line.
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
