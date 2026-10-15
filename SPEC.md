# kairos — specification

Status: **DRAFT 0.1.** Implemented except for the items in [`PLAN.md`](PLAN.md), which is the work plan; this specification is the source of truth for behaviour.

`kairos` is a modular Python 3 command-line tool for Linux: a **time-based arbitrary state registry**. A config file maps time intervals to free-text *state* names. Run the tool and it prints the states that are active now; with `--next-change` it prints when that set of active states will next change.

## Parts

| Part | Covers |
|------|--------|
| [spec/cli.md](spec/cli.md) | command usage, options, output and exit status, the `--at` instant, config file location, the default config |
| [spec/states.md](spec/states.md) | config line syntax, indentation, STATE text and `~`/`@`, hierarchy and negation, reported states, `--next-change` |
| [spec/macros.md](spec/macros.md) | string and command macros, expansion, names and scope, when commands run |
| [spec/intervals.md](spec/intervals.md) | INTERVAL syntax: tokens, locale names, items, ranges, lists, spans, durations and relative forms, the time model, time zones |
| [spec/other.md](spec/other.md) | implementation architecture and constraints, test instructions, conformance vectors V1–V22 |

## Scope

In scope: parsing the config, computing the active states at a given instant, and the next instant at which that set changes.

Out of scope for v1: daemon or watch mode, notifications, running actions on change, config includes, calendars other than Gregorian, sub-second precision, sandboxing of macro commands. Possible later: weekday spans (`Mon 08:00 -- Fri 17:00`), an n-th weekday syntax, config includes.

## Conventions

* An **error** is reported on stderr with file and line, parsing goes on to find the other errors, stdout stays empty and the exit status is 2 ([cli.md](spec/cli.md#output-and-exit-status)). The rules say where something is an error; there is no separate list.
* Where this specification names a standard (the Python language reference for indentation, PEP 495 and `zoneinfo` for wall-clock times, RFC 9636 for TZif), kairos does what that standard prescribes and does not restate it.
