# kairos — specification

Status: **DRAFT 0.1.** Implemented except for the items listed in `PLAN.md`, which is the work plan; this specification is the source of truth for behaviour.

`kairos` is a modular Python 3 command-line tool for Linux: a **time-based arbitrary state registry**. A config file maps time intervals to free-text *state* names. Run the tool and it prints the states that are active right now; with `--next-change` it prints when that set of active states will next change.

In scope: parsing the config, computing the active states at a given instant, computing the next instant at which the set of active states changes. Out of scope for v1: daemon/watch mode, notifications, running actions on change, config includes, calendars other than Gregorian, sub-second precision, sandboxing of macro commands. Possible future work: weekday spans (`Mon 08:00 -- Fri 17:00`), n-th weekday syntax, config includes.

## Parts

| Part | Contents |
|------|----------|
| [spec/cli.md](spec/cli.md) | command usage, options, `--at`, output, exit status, config file location, default config |
| [spec/states.md](spec/states.md) | config lines, indentation and hierarchy, state names (`~`, `@`), matching semantics, what counts as a change |
| [spec/macros.md](spec/macros.md) | string and command macros: names, scope, expansion, environment, when commands run |
| [spec/intervals.md](spec/intervals.md) | INTERVAL syntax: tokens, items, clauses, lists, spans, durations and relative forms, time model, time zones, grammar |
| [spec/implementation.md](spec/implementation.md) | architecture, implementation constraints, the `--next-change` search |
| [spec/tests.md](spec/tests.md) | test instructions and the conformance vectors V1–V22 |

References between parts read `file §N` (`intervals §6.1`); inside a part just `§N`. Each rule is stated in one place only; other places refer to it. `V<n>` names a vector in `spec/tests.md`.
