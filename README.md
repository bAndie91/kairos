# kairos

A time-based, arbitrary **state registry** for Linux. A config file maps time
intervals to free-text state names; `kairos` prints the states that are active
right now, or (with `--next-change`) when that set will next change.

```
$ cat ~/.config/kairos/intervals.conf
08:00-16:00 = work
12:00-13:00 = lunch
Mon-Fri
  Dec = weekdays in December

$ kairos --at "2026-10-09 12:05" --tz Europe/Budapest
work
lunch
$ kairos --at "2026-10-09 12:05" --tz Europe/Budapest --next-change
2026-10-09 13:00:00
```

Intervals can be times, weekdays, dates, ranges, lists, spans
(`Dec 20 -- Jan 10`), relative expressions (`40 days until Dec 24`,
`3 days before Dec 24`, `1-7 Mon + 5 days`), with time zones, nesting,
negation and macros (including shell-command macros such as
`Easter := ! date -d "$(ncal -e)" +%F`).

## Install

Requirements: Python >= 3.9, [`python-dateutil`](https://pypi.org/project/python-dateutil/),
[`tzlocal`](https://pypi.org/project/tzlocal/) and the system time zone database.

Debian/Ubuntu:

```sh
sudo apt install python3 python3-dateutil python3-tzlocal tzdata
```

`kairos` runs straight from a checkout (`./kairos`). To install it:

```sh
sudo make install            # PREFIX=/usr/local by default
make install PREFIX=$HOME/.local
make uninstall
```

## Usage

```
kairos [-c FILE] [--at DATETIME] [-n] [--tz ZONE] [--format FMT] [--check]
       [--print-default-config] [-V] [-h]
```

| Option | Meaning |
|--------|---------|
| `-c`, `--config FILE` | use FILE instead of the XDG lookup (`-` reads stdin) |
| `--at DATETIME` | evaluate at `YYYY-MM-DD[ T]HH:MM[:SS][offset]` instead of now |
| `-n`, `--next-change` | print when the set of states next changes (nothing if it never will) |
| `--tz ZONE` | default zone: an IANA ID or `UTC+2`-style offset (default `$TZ`, then the system zone) |
| `--format FMT` | format of `--next-change`: a `strftime` string, `iso` or `epoch` |
| `--check` | validate the whole config, print nothing |
| `--print-default-config` | print the documented default config |

The config is read from `$XDG_CONFIG_HOME/kairos/intervals.conf`
(`~/.config/...`), then `$XDG_CONFIG_DIRS`. If none exists and `--config` was
not given, a fully commented default is created there; it contains the
complete format description and many examples. A missing `--config FILE` is an
error and is never created.

On a config error, `kairos` prints `kairos: FILE:LINE: error: MESSAGE` for each
problem it finds, nothing on stdout, and exits with status 2.

Month and weekday names follow the `LC_TIME` locale (`LC_ALL`, `LC_TIME`,
`LANG`): `március` in a Hungarian locale, `March` in an English one.

## Security

Macro commands (`NAME := ! COMMAND`) are arbitrary shell code run with your
privileges. They are not sandboxed. Only use commands you trust and keep the
config writable by you alone.

## Not provided

A daemon or watch mode, notifications, running actions when a state changes,
config includes, calendars other than Gregorian, sub-second precision and
sandboxing of macro commands.

## Development

```sh
make test        # python3 -m unittest discover -s tests -v
```

`SPEC.md` is the source of truth for behaviour (including the conformance
vectors in section 13); `PLAN.md` records the milestones and design decisions.
The command is a thin launcher (`kairos`) around the `kairoslib/` package.
