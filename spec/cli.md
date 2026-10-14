# kairos — command line, exit status, config file location

Part of the [kairos specification](../SPEC.md). Other parts: [states](states.md), [macros](macros.md), [intervals](intervals.md), [implementation](implementation.md), [tests](tests.md).

## 1. Command line

```
kairos [OPTIONS]
```

The command is named `kairos` (no `.py`).

| Option | Meaning |
|--------|---------|
| `-c FILE`, `--config FILE` | Use FILE instead of the XDG lookup (§2.1). `-` reads the config from stdin. |
| `--at DATETIME` | Evaluate at DATETIME instead of now (§1.3). |
| `-n`, `--next-change` | Print the next instant (after now, or after DATETIME) at which the set of reported states changes (states §3.3), instead of the states. |
| `--tz ZONE` | Default time zone, any form of intervals §8.1: used for intervals without an explicit zone, for `--at` without a zone, and for printing (intervals §8.2). Default: `$TZ`, else the system zone. |
| `--format FMT` | Output format of `--next-change`: a `strftime` string, or `iso` (ISO 8601 with offset), or `epoch` (Unix seconds). Default `%Y-%m-%d %H:%M:%S`. |
| `--check` | Parse the whole config without skipping any subtree, so every command macro runs (macros §4.3); print nothing, exit 0 if the config is valid. |
| `--print-default-config` | Print the default config text (§2.3) and exit. |
| `-V`, `--version`, `-h`, `--help` | As usual. |

### 1.1 Output

* Default mode: one active state per line on stdout, in config order (states §3.2), each name once. No active state → no output, exit 0.
* `--next-change`: a single line with the datetime in the display zone (intervals §8.2), e.g. `2026-10-09 12:00:00`. If no future change exists: empty stdout, exit 0. Inside a DST fold the default format is ambiguous, so a warning goes to stderr.
* **stdout hygiene:** the config is parsed completely before anything is printed. On any error stdout stays empty. Diagnostics go to stderr.

### 1.2 Exit status and diagnostics

| Code | Meaning |
|------|---------|
| 0 | Success (including "no state active"). |
| 2 | Error: usage, I/O, config syntax or semantics, macro command failure. |

Error message format on stderr: `kairos: PATH:LINE: error: MESSAGE` (or `kairos: error: MESSAGE` when no line applies). After an error in a config line parsing goes on, so that the other failing lines are reported too (every unknown word of an INTERVAL gets its own diagnostic, intervals §1.3); the exit status is 2 at the end and stdout is empty.

What is an error is stated where each rule is: in [states](states.md), [macros](macros.md) and [intervals](intervals.md) for the config, here for usage (unknown option, bad option value, bad `--at`, §1.3) and for a missing `--config` file (§2.2).

### 1.3 `--at` forms

`--at` takes one of three forms. The optional `TZ` is one zone token of intervals §8.1, exactly as in an INTERVAL; whitespace between the time (or date) and the `TZ` is optional (`12:00Z`, `12:00 Z`). A form without `TZ` is local time in the display zone, with a `TZ` it is local time in that zone. A nonexistent or ambiguous local time follows intervals §7. Date and time are separated by whitespace only (there is no `T` separator). Sub-seconds are truncated. `H:MM[:SS]` is the `TIME` token of intervals §1.1.

| Form | Meaning |
|------|---------|
| `YYYY-MM-DD H:MM[:SS] [TZ]` | that instant |
| `YYYY-MM-DD [TZ]` | the start of that day, `YYYY-MM-DD 00:00:00` |
| `H:MM[:SS] [TZ]` | a time of day: today's date, or tomorrow's under the rule below |

**Bare time.** "Today" is the current date in the zone of the form (the `TZ` if given, else the display zone). Let `c` be that date at the given time. If `c` lies **more than 12 hours** in the past, the time is taken on the **next** day instead, and a warning goes to stderr naming both the given time and the date used, e.g. `kairos: warning: --at 06:00 passed 14 hours ago; setting tomorrow, 2026-10-10 06:00:00`. Otherwise `c` stays today, whether it is later today or passed up to 12 hours ago (exactly 12 hours counts as "not more than"). Of the three forms only the bare time depends on the current time. With `--next-change` the resolved instant is the base, like any other `--at`.

## 2. Config file location

### 2.1 Lookup order

1. `--config FILE`.
2. Per the XDG specs:
   1. `$XDG_CONFIG_HOME/kairos/intervals.conf` (default `$HOME/.config/...`).
   2. For each directory in `$XDG_CONFIG_DIRS` (default `/etc/xdg`), in order: `DIR/kairos/intervals.conf`.

The first file that exists wins; files are not merged. XDG variables holding relative paths are ignored, as the XDG spec requires.

### 2.2 Creating the default config

If no file was found and `--config` was **not** given, the tool creates `$XDG_CONFIG_HOME/kairos/intervals.conf` (directory mode 0700 if it has to be created, file mode 0644) with the default examples (§2.3), prints `kairos: created default config: PATH` to stderr, and proceeds using it. If `--config` names a file that does not exist: error, nothing created.

### 2.3 Default config content

The default config has **no active lines**; it consists of examples. It may open with a short `## ` header saying where the documentation is (`man kairos`, `kairos --check`, `kairos --print-default-config`). The complete command-line and configuration reference, including the macro-command security note (implementation §2), lives in `man/kairos.1` and is not repeated in the default config.

Every example line is written as `# ` followed by the original line (indentation preserved after that single space); explanatory prose goes in lines starting with `## `. The examples together cover every syntax feature (clauses, lists, ranges, spans, relative forms, zones, nesting, negation, `~` and `@`, string and command macros), with `Easter` using the wrapper of macros §4.4. Stripping the leading `# ` from the example lines must yield a config that parses (V11).
