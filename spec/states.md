# kairos — config syntax, states and hierarchy

Part of the [kairos specification](../SPEC.md). INTERVAL syntax is in [intervals.md](intervals.md), macros in [macros.md](macros.md).

## Config file

UTF-8 text with LF line endings. Every line is one of:

| Kind | Recognised by |
|------|---------------|
| blank | only whitespace; ignored |
| comment | first non-blank character is `#`; ignored. There are **no inline comments**: STATE is free text and may contain `#`. |
| macro definition | `INDENT NAME := VALUE`, where the text before the first `:=` contains no `=` ([macros](macros.md)). If it does contain an `=`, the line is an interval line (`Mon = a := b` has the STATE `a := b`). |
| interval line | everything else: `INDENT [!] INTERVAL [= STATE]` |

### Interval line

* `!` (optionally followed by whitespace) negates the interval ([negation](#negation)).
* The line is split at the **first** `=`; INTERVAL never contains `=`. Both parts are trimmed.
* No `=`: the line has no STATE, so it is not reported, but its INTERVAL still restricts its children.
* `=` followed by an empty STATE, or an empty INTERVAL, is an error.

### Indentation

Indentation works as in Python 3 and kairos follows what the [Python language reference](https://docs.python.org/3/reference/lexical_analysis.html#indentation) prescribes, tabs and spaces included: a line indented deeper than the previous one is its child, a dedent must return to an open level, and indentation that is inconsistent in the reference's sense is an error. An implementation may reimplement the algorithm or reuse a library that does what the reference says. Differences from Python source: blank and comment lines are ignored, the first line must not be indented, and a macro line cannot have children.

## STATE text

Free text; macros are not expanded in it. Escapes: `\~` is a literal `~`, `\@` a literal `@` (meaningful as the first character), `\\` a backslash; any other backslash sequence is an error. Whitespace inside is preserved, leading and trailing whitespace is trimmed.

* `~` is replaced by the **effective name** of the nearest ancestor line that has a STATE (after that line's own `~` substitution, without its leading `@`): the parent if it has one, otherwise the grandparent, and so on. No such ancestor, including a top-level line using `~`, is an error.
* A STATE starting with `@` and optional whitespace is **hidden**: not reported, but its name (without the `@` and the whitespace) is what children see as `~`. A bare `@` is an error.

## Hierarchy

Let `S(L)` be the set of line L's INTERVAL. Its **effective set** is

```
E(L) = E(parent) ∩ S(L)          if L is not negated
E(L) = E(parent) \ S(L)          if L is negated   ("! INTERVAL")
```

with `E(root)` = all time. A child restricts its parent (`Mon-Fri` with a child `Dec` is "weekdays in December"); siblings are independent; a line without STATE contributes only through its children.

Nested lines intersect sets, which is not always what the same words on one line mean:

* `*-*-01` with a child `Fri` is the days that are both a 1st and a Friday. "The first Friday of the month" is `1-7 Fri`.
* On one line day selectors pick the *starting* day: `Fri 22:00-02:00` runs from Friday 22:00 to Saturday 02:00 ([time model](intervals.md#time-model)). The nested form, `Fri` with a child `22:00-02:00`, is a pure intersection: Friday 00:00–02:00 and Friday 22:00–24:00.

### Negation

`! INTERVAL` as a child subtracts from the parent (`! Sun,Sat` under `*-*-01`: the 1st of the month unless it is a weekend). At top level it is the complement of INTERVAL.

## Reported states

* A line is **reported** iff it has a STATE that does not start with `@`.
* The state name is the STATE after `~` substitution and escape processing. Several lines may yield the same name; the state is active when **any** of them is effective: `U(name)` is the union of their effective sets, and the state set at instant `t` is `{ name : t ∈ U(name) }`.
* Output order is the order in which a name's first line appears in the file (depth first, as written).

## Next change

`--next-change` prints the first instant after the base instant at which the set of reported states differs from the set just before it. Every change is a range boundary of some `U(name)`, but not every boundary is a change: a state ending at `T` while another line of the same name starts at `T` is no change, and hidden and STATE-less lines are never change points on their own. A candidate boundary `T` counts only if the complete reported set at `T-1 second` differs from the one at `T`.

Do not sample every second or scan every date. Generate candidate boundaries from the AST:

* A clause yields the local start and end of its matching dates and time ranges, jumping straight to the next matching date; a span yields its endpoints; a relative interval yields the boundaries of its anchor instances moved by its duration. Half-open, second-resolution semantics are kept.
* Merge the candidate streams chronologically and return the first candidate where the set changes.

Termination, with no configurable horizon:

* Explicit-year clauses and spans, and relative intervals over finite anchors only, contribute finitely many boundaries; their complete duration tails count before they are finished. Recurring calendar clauses and spans, and calendar-duration arithmetic, repeat with the 400-year Gregorian cycle (146,097 days); a recurring anchor has no finite tail.
* For each IANA zone in use the future follows the TZif footer: after the last explicit transition either its recurring POSIX rule applies or, with no rule, its final offset ([RFC 9636](https://www.rfc-editor.org/rfc/rfc9636.html)). The recurrence fingerprint includes these rules and offsets, not only Gregorian dates. The implementation may parse the TZif recurrence metadata for this, but wall-clock/instant conversion stays with `zoneinfo`.
* Beyond all finite exceptions and tails, and once the zone fingerprints align, search at most one combined recurrence cycle. If no candidate changes the set in that cycle, no change exists in the representable datetime domain (years 1–9999): print nothing and exit 0.
