# kairos — config lines, hierarchy, state names, matching

Part of the [kairos specification](../SPEC.md). The INTERVAL text itself is in [intervals](intervals.md), macros in [macros](macros.md).

The config file is UTF-8 text with LF line endings.

## 1. Config lines

### 1.1 Line kinds

| Kind | Recognised by |
|------|---------------|
| blank | only whitespace → ignored |
| comment | first non-blank char is `#` → ignored. **No inline comments** (STATE is free text and may contain `#`). |
| macro definition | `INDENT NAME := VALUE`, where NAME is the text before the first `:=` and contains no `=` (macros §1, §2). A line whose text before the first `:=` contains an `=` is an interval line: `Mon = a := b` has the STATE `a := b`. |
| interval line | everything else: `INDENT [!] INTERVAL [= STATE]` |

### 1.2 Interval line

```
INDENT [!] INTERVAL [= STATE]
```

* `INDENT`: spaces and tabs (§1.3).
* `!` (optionally followed by whitespace) negates the interval (§3.1).
* The line is split at the **first** `=`; INTERVAL never contains `=`. Both parts are trimmed.
* No `=` → the line has no STATE: it is **not reported**, but its INTERVAL still restricts its children.
* `=` followed by an empty STATE → error. Empty INTERVAL → error.

### 1.3 Indentation and hierarchy

Indentation is the run of spaces and tabs before the first other character of a line. Its rules (levels, tabs mixed with spaces, a dedent that matches no open level) are those of Python's lexical analysis, <https://docs.python.org/3/reference/lexical_analysis.html#indentation>, which this specification does not restate: kairos does what that reference prescribes, by re-implementing it or by reusing a library where that is practical, and an indentation Python rejects (`TabError`, an unindent to no open level) is an error here too.

Kairos adds only this: the first line must have indentation 0 (else error); a line indented deeper than the previous (non-blank, non-comment) line is its child; blank and comment lines are not measured; a macro line takes part in indentation (the scope of the macro follows it, macros §2) but cannot have children (error).

## 2. State names

The STATE of an interval line is free text; macros are **not** expanded in it. Escapes: `\~` is a literal `~`, `\@` is a literal `@` (only meaningful as the first character), `\\` is a backslash; any other backslash sequence is an error. Whitespace inside STATE is preserved, leading and trailing whitespace is trimmed.

* `~` is replaced by the **effective name** of the nearest ancestor line that has a STATE (after that line's own `~` substitution and without its leading `@`): the parent if it has a STATE, otherwise the grandparent, and so on. A top-level line using `~`, or any line without an ancestor that has a STATE → error.
* A STATE starting with `@\s*` is **hidden**: not reported, but its name (without the `@\s*`) is what children see as `~`. A bare `@` (empty name) is an error.
* The state **name** is the STATE after `~` substitution and escape processing (and, for a hidden state, without the `@`).

## 3. Matching semantics

### 3.1 Effective sets, hierarchy, negation

Let `S(L)` be the set of line L's INTERVAL. Its **effective set** is

```
E(L) = E(parent) ∩ S(L)          if L is not negated
E(L) = E(parent) \ S(L)          if L is negated   ("! INTERVAL")
```

with `E(root)` = all time. A child therefore restricts its parent (`Mon-Fri` with a child `Dec` means "weekdays in December"), and siblings are independent. A line without STATE contributes only through its children. At top level `! INTERVAL` is the complement of INTERVAL; under a parent it subtracts (`! Sun,Sat` under `*-*-01` is the 1st of the month unless it is a weekend).

A child is a plain intersection, nothing more: `*-*-01` with a child `Fri` is the days that are both a 1st and a Friday ("the first Friday of the month" is written `1-7 Fri`). Nesting never spills over midnight: `Fri` with a child `22:00-02:00` is Fri 00:00–02:00 together with Fri 22:00–24:00, whereas `Fri 22:00-02:00` on one line runs from Fri 22:00 to Sat 02:00 (intervals §3.2).

### 3.2 Reported states

* A line is **reported** iff it has a STATE and that STATE does not start with `@`. A line without STATE has no name and is never reported.
* Several lines may yield the same name; the state is active when **any** of them is effective: `U(name)` is the union of their effective sets.
* The state set at instant `t` is `{ name : t ∈ U(name) }`.
* Output order: the order in which a name's first line appears in the file (depth-first, as written).

### 3.3 Changes of the state set

A change at instant `T` means that the complete set of reported names differs immediately before `T` and at `T`. So a state ending at `T` while another line of the **same name** starts at `T` is no change, and hidden (`@`) and STATE-less lines are never change points on their own. Every change point is a range boundary of some `U(name)`. `--next-change` prints the first change after the base instant, nothing if there is none. How it is searched is in implementation §3.
