# kairos — command line and config file location

Part of the [kairos specification](../SPEC.md).

## Command line

```
kairos [OPTIONS]
```

| Option | Meaning |
|--------|---------|
| `-c FILE`, `--config FILE` | Use FILE instead of the [lookup](#config-file-location); `-` reads the config from stdin. |
| `--at DATETIME` | Evaluate at DATETIME instead of now ([evaluation instant](#evaluation-instant)). |
| `-n`, `--next-change` | Print the next instant after now (or after `--at`) at which the set of reported states changes, instead of the states ([next change](states.md#next-change)). |
| `--tz ZONE` | The *display zone*: used for printing and as the default zone of intervals without a `TZ`. Any [time-zone token](intervals.md#time-zones). Default: `$TZ` (same forms; POSIX rule strings are not interpreted), else the system zone via `tzlocal`; if that cannot be found, UTC with a warning on stderr. |
| `--format FMT` | Output format of `--next-change`: a `strftime` string, `iso` (ISO 8601 with offset) or `epoch` (Unix seconds). Default `%Y-%m-%d %H:%M:%S`. |
| `--check` | Parse the whole config without skipping any subtree, so every command macro runs ([evaluation time](macros.md#evaluation-time)); print nothing, exit 0 if valid. |
| `--print-default-config` | Print the [default config](#default-config) text and exit. |
| `-V`, `--version`, `-h`, `--help` | As usual. |

## Output and exit status

* Default mode: one active state per line on stdout, in config order, each name once. No active state: no output, exit 0.
* `--next-change`: one line, the instant in the display zone formatted by `--format`. No future change: empty stdout, exit 0. If the instant falls in a DST fold and the format does not show the UTC offset, a warning goes to stderr.
* The config is parsed completely before anything is printed; on any error stdout stays empty. Diagnostics go to stderr as `kairos: PATH:LINE: error: MESSAGE` (`kairos: error: MESSAGE` when no line applies). Parsing goes on after an error in one line, so a run lists every failing line (for example every unknown word); the exit status is then 2.

| Code | Meaning |
|------|---------|
| 0 | Success, including "no state active". |
| 2 | Error: usage, I/O, parse or semantic error, macro command failure. |

## Evaluation instant

`--at` takes a date and/or a time of day, optionally followed by one [`TZ`](intervals.md#time-zones) token exactly as in an INTERVAL (`12:00Z` and `12:00 Z` are the same). Without `TZ` the value is local time in the display zone, with it local time in that zone. Date and time are separated by whitespace (there is no `T` separator); sub-seconds are truncated; a nonexistent or ambiguous local time follows the [time model](intervals.md#time-model).

| Form | Meaning |
|------|---------|
| `YYYY-MM-DD H:MM[:SS] [TZ]` | that instant |
| `YYYY-MM-DD [TZ]` | the start of that day, 00:00:00 |
| `H:MM[:SS] [TZ]` | a time of day, today or tomorrow (below) |

**Bare time.** "Today" is the current date in the zone of the form. If today's time lies more than 12 hours in the past (exactly 12 hours does not count), the next day is used and a warning names both, e.g. `kairos: warning: --at 06:00 passed 14 hours ago; setting tomorrow, 2026-10-10 06:00:00`. Otherwise it stays today, whether still ahead or up to 12 hours past. So at 20:00 `--at 06:00` means tomorrow (with the warning), while `--at 14:00` at 15:00 and `--at 22:00` at 20:00 mean today. Only the bare time depends on the current time. With `--next-change` the resolved instant is the base like any other `--at`.

## Config file location

The config file is `intervals.conf` in a `kairos` directory. The first file that exists wins; files are not merged:

1. `--config FILE`. If it does not exist this is an error and nothing is created.
2. `$XDG_CONFIG_HOME/kairos/intervals.conf` (default `$HOME/.config`).
3. `DIR/kairos/intervals.conf` for each `DIR` in `$XDG_CONFIG_DIRS` (default `/etc/xdg`), in order.

XDG variables holding relative paths are ignored, as the XDG specification requires.

If no file is found and `--config` was not given, kairos creates `$XDG_CONFIG_HOME/kairos/intervals.conf` (directory mode 0700 if it has to be created, file mode 0644) with the default config, prints `kairos: created default config: PATH` to stderr and uses it.

## Default config

The default config has **no active lines**: a short `## ` header saying where the documentation is (`man kairos`, `kairos --check`, `kairos --print-default-config`), then examples. An example line is `# ` followed by the original line (indentation kept after that single space); explanatory prose uses lines starting with `## `. Stripping the leading `# ` from the example lines must yield a config that parses under `--check` (V11). Together the examples cover every syntax feature of this specification: clauses, lists, ranges, spans, relative forms, zones, nesting, negation, `~` and `@`, string and command macros; `Easter` uses the working wrapper of the [command-macro limitation](macros.md#limitation). The full reference, including the macro-command security note, lives in `man/kairos.1` and is not duplicated in the default config.
