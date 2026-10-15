# kairos — macros

Part of the [kairos specification](../SPEC.md).

## Definition

```
NAME := STRING            literal string
NAME := ! COMMAND         shell command; its stdout is the value
```

A macro line takes part in [indentation](states.md#indentation) but cannot have children. Empty values are valid.

* **String macro.** Visible macros are expanded in STRING once ([expansion](#expansion)); the result is the value, a flat string. A STRING cannot start with a literal `!` (that always means COMMAND).
* **Command macro.** See below.

### Command macros

The command runs with `${SHELL:-/bin/sh} -c COMMAND`, stdin from `/dev/null`, stderr passed through. Its stdout is the value, with a trailing newline stripped and other newlines replaced by spaces. Macros are not expanded in COMMAND text; the environment carries them instead:

* everything inherited from the caller, and `KAIROS_NOW`, the evaluation instant (ISO 8601 with offset);
* `KAIROS_MACRO_<NAME>` for every macro visible at the definition line, with its resolved value (earlier command macros have already run). NAME is used as is: the variable for `Mary's birthday` is `KAIROS_MACRO_Mary's birthday`. Kairos hands it to the operating system like any other; if that refuses it, kairos warns on stderr naming the macro, leaves that variable out and runs the command anyway. A shell may be unable to read such a variable; that is not kairos's concern;
* `KAIROS_INTERVAL_<LEVEL>` and `KAIROS_STATE_<LEVEL>` for each **ancestor** of the definition line, and only those; LEVEL is the ancestor's indentation depth from 0. A macro at the root level has no ancestor, so none are set. The first holds the ancestor's INTERVAL after macro expansion, with a leading `! ` if negated; the second its STATE as reported (after `~`, escape and `@` processing; possibly empty).

## Expansion

Expansion is purely textual and happens **before tokenization**: in every INTERVAL and macro STRING (not in STATE or COMMAND text), each occurrence of a visible macro name that stands as a whole word is replaced by its value. It therefore knows nothing about the INTERVAL grammar, time-zone names included.

* Names match literally and case-sensitively, with inner spaces and punctuation exactly as defined. Where several visible names match at one position the **longest** wins: `Mary` and `Mary's birthday` coexist, and the latter is not read as `Mary` followed by `'s birthday`.
* **Whole word.** If the name starts with a word character (a letter, including Unicode letters, a digit or `_`), the character before the match must be neither a word character nor `/`; if it ends with one, the character after must be neither. So `mary` is not replaced inside `annamary` or `mary_birthday`, and a macro `Budapest` (or `Europe`) leaves the zone ID `Europe/Budapest` alone. Whitespace, other punctuation (`-` and `,` included) and the ends of the text are boundaries; a name that starts or ends with punctuation needs no boundary on that side.
* Expansion is a **single pass**: replaced text is not rescanned. Values are already fully expanded when defined.
* Because `-` is a boundary, a macro named `Prince` or `au` can alter `America/Port-au-Prince`. This is accepted: kairos keeps no list of zone names, and a macro may be named like a time zone (`CEST := Europe/Berlin`). Expansion comes first, so the lexer never sees the name.

## Names and scope

* NAME is the text before the first `:=`, trimmed; case-sensitive; spaces and punctuation are allowed (`Mary's birthday`, `Q1 (first quarter)`, `Easter!`). It must not be empty, must not contain `=`, must not start with `!`, and must contain at least one letter (a name of only digits and punctuation would collide with numbers, times and `*`: `7 := x` is an error).
* A name may start with, end with or contain another macro's name as long as the whole name differs: `Mary`, `Mary's birthday` and `birthday` can all be defined. Only an identical name is a redefinition.
* **Reserved** (case-insensitive) is a name that is *entirely* one of: a month or weekday name of the effective locale ([names](intervals.md#month-and-weekday-names)); a duration unit (`second`, `minute`, `hour`, `day`, `week`, `month`, `year`, singular or plural); `until`, `before`, `after`. `Mon morning` is fine, `Mon` is an error. Nothing else is reserved; in particular there is no list of time-zone names.
* A macro at indentation 0 is visible to all following lines. A macro defined deeper, as a child of line P, is visible to the following lines inside P's subtree; leaving the subtree ends its scope. Redefining a name that is **visible** at that point (same or enclosing scope) is an error; sibling subtrees may reuse a name.

## Evaluation time

Parsing is one pass over the file, top to bottom. A command macro runs **eagerly**: exactly once, when its definition line is reached and before any later line is read. Its value is then fixed like a string macro's; later uses never run it again, and a macro that nothing uses runs all the same. The environment is built from the position of the definition line.

A non-zero exit status is an error reported at the macro's line, whether or not any line uses the macro.

* **Default mode** (print states): when the parser reaches a subtree whose parent's effective set does not contain the evaluation instant, the subtree is *skipped*: its command macros do not run (and so cannot fail), and lines that use a command macro defined there are only structurally validated (indentation, line kind). Everything else is fully parsed and validated.
* `--next-change` and `--check` never skip, so every command macro of the file runs.

### Limitation

A command macro is a snapshot taken while the config is parsed. `ncal -e` prints only the current year's Easter, and in a locale-dependent, US-style format that the ISO-only grammar rejects, so the working example is `Easter := ! date -d "$(ncal -e)" +%F`. Run in December, `--next-change` cannot know next year's Easter; commands may read `KAIROS_NOW` to pick a year.
