# kairos — macros

Part of the [kairos specification](../SPEC.md). A macro is a named piece of text that is expanded in INTERVAL text before it is tokenized (§3).

## 1. Definition

```
NAME := STRING            literal string
NAME := ! COMMAND         shell command; its output is the value
```

* NAME: the text before the first `:=`, trimmed (§2).
* STRING: other macros visible at that point are expanded in it (once, §3) and the result is the value, a flat string fixed at the definition. A STRING cannot start with a literal `!` (that always means COMMAND). Empty values are valid.
* COMMAND: §4.
* Macros are not expanded in STATE text (states §2) nor in COMMAND text.

## 2. Names and scope

* NAME is case sensitive and may contain spaces and punctuation (`Mary's birthday`, `Q1 (first quarter)`, `Easter!`). It must not be empty, must not contain `=` (the line would be an interval line, states §1.1), must not start with `!`, and must contain at least one letter (a name made only of digits and punctuation would collide with numbers, times and `*`: `7 := x` is an error).
* A name may start with, end with or contain the name of another macro, as long as the whole name is different: `Mary`, `Mary's birthday` and `birthday` can all be defined together. Only an identical name is a redefinition. Expansion tries longer names first (§3).
* Reserved (case-insensitive) → error: a name that is *entirely* a month name or weekday name of the effective locale (intervals §1.2), a duration unit (intervals §6), `until`, `before` or `after` (`Mon morning` is fine, `Mon` is not).
* **No time-zone word is reserved.** Kairos keeps no list of time-zone names (intervals §8.1). A macro may be named like a zone ID (`Europe/Budapest`, `CET`), like `UTC`, `GMT` or `Z`, like an offset (`UTC+2`), or like an alphabetic abbreviation that is not a zone ID (`CEST`, `CST`, `IST`). Because expansion precedes tokenization (§3), such a macro replaces that word wherever it stands as a whole word. Defining abbreviations as macros is the intended way to use them as a `TZ`: `CEST := Europe/Berlin`, `IST := Asia/Kolkata`; the author decides what an ambiguous abbreviation means.
* A macro defined at indentation 0 is visible to all following lines. A macro defined at deeper indentation, as a child of line P, is visible to the lines that follow it inside P's subtree; leaving the subtree ends the scope.
* Redefining a name that is **visible** at that point (same scope or an enclosing scope) → error. Sibling subtrees may define the same name.

## 3. Expansion

Before an INTERVAL (or a macro STRING) is lexed, every occurrence of a visible macro name that stands as a **whole word** is replaced by its value.

* A name is matched literally and case-sensitively, including inner spaces and punctuation exactly as written in its definition.
* If several visible names match at the same position, the **longest** wins. So `Mary` and `Mary's birthday` can coexist, and `Mary's birthday` is not read as `Mary` followed by `'s birthday`.
* Whole word: when the name starts with a *word character* (a letter, including unicode letters, a digit or `_`), the character before the match must be neither a word character nor `/`; when it ends with one, the character after the match must be neither. So `mary` is not replaced inside `annamary` or `mary_birthday`, and a macro `Budapest` (or `Europe`) leaves the zone ID `Europe/Budapest` alone. Whitespace, other punctuation (including `-` and `,`) and the start or end of the text are boundaries; a name that starts or ends with punctuation needs no boundary on that side.
* Expansion **precedes tokenization** (intervals §1.1): the lexer only ever sees the expanded text, and a macro can stand for any piece of an INTERVAL, including a time-zone word or part of one. Only the `/` rule above shields zone IDs; `-` is a boundary (it is also the range operator), so with macros `au` and `Prince`, `America/Port-au-Prince` is expanded like any other text. Which names to define is the author's business.
* Expansion is a **single pass**: replaced text is not rescanned. (Values are already fully expanded when defined; a string macro that uses a command macro sees the command's output, since the command has already run, §4.3.)

## 4. Command macros

### 4.1 Running

The command is run with `${SHELL:-/bin/sh} -c COMMAND`, stdin from `/dev/null`, stderr passed through. Its stdout is the value: newlines are replaced by spaces (`s/\n/ /g`) and the trailing newline is stripped. A non-zero exit status is an error reported at the macro's file and line, whether or not any line uses the macro (the one exception is a skipped subtree, §4.3).

### 4.2 Environment

* everything inherited from the caller;
* `KAIROS_MACRO_<NAME>` for every macro visible at the definition line, with its resolved value (earlier command macros have already run, so they have values too). NAME is used **as is**, without any transformation: the variable for `Mary's birthday` is named `KAIROS_MACRO_Mary's birthday`. Kairos neither checks nor special-cases it (not `=`, not `\0`): the variable is handed to the operating system / language runtime like any other. If that refuses it, Kairos prints a warning naming the macro to stderr, leaves that variable out and runs the command anyway. The shell may well be unable to read such a variable (`$KAIROS_MACRO_Mary's birthday` is not valid shell); that is not Kairos's concern;
* `KAIROS_NOW`: the evaluation instant (ISO 8601 with offset);
* `KAIROS_INTERVAL_<LEVEL>` and `KAIROS_STATE_<LEVEL>` for each **ancestor** of the definition line, and only for those. LEVEL is the indentation level of the ancestor, from 0. The macro line itself is not included, and a macro at the root level has no ancestor, so none of these variables are set for it.
  * `KAIROS_INTERVAL_<LEVEL>` is the ancestor's INTERVAL text after macro expansion, with a leading `! ` if negated.
  * `KAIROS_STATE_<LEVEL>` is the ancestor's STATE as reported in normal mode: after `~` substitution, escape and `@` processing; it may be empty.

### 4.3 When commands run

Parsing is one pass over the file, top to bottom. A command macro runs **eagerly**: exactly once, when its definition line is reached and before any later line is read, with the environment of that position (§4.2). Its value is then fixed like a string macro's: later lines that use the macro never run the command again, and a macro that no line uses runs all the same.

* **Default mode** (print states): when the parser reaches a subtree whose parent's effective set does **not** contain the evaluation instant, the subtree is *skipped*: command macros inside it do not run (so they cannot fail), and lines that use a command macro defined in a skipped subtree are only structurally validated (indentation, line kind). All other lines are fully parsed and validated.
* **`--next-change`** and **`--check`** never skip, so every command macro of the file runs.

### 4.4 Snapshot limitation

A command macro is a snapshot taken while the config is parsed. `ncal -e`, for example, yields only the *current* year's Easter, so `--next-change` run in December cannot know next year's Easter; commands may read `KAIROS_NOW` to pick a year.

`ncal -e` also prints a locale-dependent, US-style date (`04/05/26`), which the INTERVAL grammar (ISO dates only) rejects, and kairos accepts no `MM/DD/YY` form. So `Easter := ! ncal -e` parses but fails on use; the working form is `Easter := ! date -d "$(ncal -e)" +%F`, which the default config shows (cli §2.3).
