"""Read config text into a Python-style indentation tree (SPEC §4)."""
from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Iterable, Union

from .errors import ErrorList, IntervalKeeperError

_MACRO_RE = re.compile(r"^([^\W\d]\w*)\s*:=\s*(.*)$")


@dataclass
class Node:
    """An interval line and its child interval lines."""
    lineno: int
    indent: int
    negated: bool
    interval_text: str
    state_raw: str | None
    children: list["Node"] = field(default_factory=list)
    effective_name: str | None = None
    reported: bool = False
    parent: "Node | None" = field(default=None, repr=False)


@dataclass(frozen=True)
class MacroLine:
    """A macro definition retained in source order for the macro pass."""
    lineno: int
    indent: int
    name: str
    value: str


ConfigEntry = Union[Node, MacroLine]


class ReaderErrors(ErrorList):
    """Aggregate independent line diagnostics while remaining CLI-compatible."""


def _error(path: str | None, line: int, message: str) -> IntervalKeeperError:
    return IntervalKeeperError(path, line, message)


def _state_parts(raw: str, path: str | None, lineno: int) -> tuple[str, bool]:
    """Resolve escapes and parent-name substitutions, returning (name, hidden)."""
    # Keep escape provenance so an escaped leading @ is not a hidden marker and
    # escaped tildes are not parent substitutions.
    chars: list[tuple[str, bool]] = []
    i = 0
    while i < len(raw):
        char = raw[i]
        if char == "\\":
            if i + 1 >= len(raw) or raw[i + 1] not in "~@\\":
                bad = raw[i:i + 2]
                raise _error(path, lineno, f"invalid STATE escape {bad!r}")
            chars.append((raw[i + 1], True))
            i += 2
        else:
            chars.append((char, False))
            i += 1

    hidden = False
    if chars and chars[0] == ("@", False):
        j = 1
        while j < len(chars) and chars[j][0].isspace():
            j += 1
        if j == len(chars):
            raise _error(path, lineno, "hidden STATE name after '@' must not be empty")
        hidden = True
        chars = chars[j:]

    parent_name: str | None = None
    # Parent is passed via the temporary attribute set by read_config below.
    # Substitution is performed there, where the nearest named ancestor is known.
    return "".join(ch for ch, _escaped in chars), hidden


def _decode_state(raw: str, parent: Node | None, path: str | None, lineno: int) -> tuple[str, bool]:
    chars: list[tuple[str, bool]] = []
    i = 0
    while i < len(raw):
        if raw[i] == "\\":
            if i + 1 >= len(raw) or raw[i + 1] not in "~@\\":
                raise _error(path, lineno, f"invalid STATE escape {raw[i:i + 2]!r}")
            chars.append((raw[i + 1], True))
            i += 2
        else:
            chars.append((raw[i], False))
            i += 1

    hidden = False
    if chars and chars[0] == ("@", False):
        j = 1
        while j < len(chars) and chars[j][0].isspace():
            j += 1
        if j == len(chars):
            raise _error(path, lineno, "hidden STATE name after '@' must not be empty")
        hidden = True
        chars = chars[j:]

    ancestor = parent
    while ancestor is not None and ancestor.state_raw is None:
        ancestor = ancestor.parent
    parent_name = ancestor.effective_name if ancestor is not None else None
    output: list[str] = []
    for char, escaped in chars:
        if char == "~" and not escaped:
            if parent_name is None:
                raise _error(path, lineno, "'~' requires an ancestor with a STATE")
            output.append(parent_name)
        else:
            output.append(char)
    name = "".join(output)
    if not name:
        raise _error(path, lineno, "STATE must not be empty")
    return name, hidden


def read_config(text: str, path: str | None = None) -> list[ConfigEntry]:
    """Parse indentation and line forms; collect line errors rather than stopping early."""
    roots: list[ConfigEntry] = []
    # Stack contains interval nodes at each currently open indentation level.
    stack: list[tuple[int, Node]] = []
    previous_entry: ConfigEntry | None = None
    errors: list[IntervalKeeperError] = []

    for lineno, physical in enumerate(text.splitlines(), 1):
        if not physical.strip() or physical.lstrip(" \t").startswith("#"):
            continue
        prefix = physical[:len(physical) - len(physical.lstrip(" \t"))]
        if " " in prefix and "\t" in prefix:
            errors.append(_error(path, lineno, "indentation may not mix spaces and tabs"))
            continue
        indent = len(prefix.expandtabs(8))
        body = physical[len(prefix):]
        if not roots and previous_entry is None and indent:
            errors.append(_error(path, lineno, "first line must not be indented"))
            continue

        macro_match = _MACRO_RE.fullmatch(body)
        if macro_match:
            entry: ConfigEntry = MacroLine(lineno, indent, macro_match.group(1), macro_match.group(2).strip())
        else:
            negated = False
            interval_state = body
            if interval_state.startswith("!"):
                negated = True
                interval_state = interval_state[1:].lstrip()
            if "=" in interval_state:
                interval_text, state = interval_state.split("=", 1)
                interval_text, state = interval_text.strip(), state.strip()
                if interval_text.endswith(":"):
                    # `NAME := VALUE` whose NAME is not an identifier; no INTERVAL ends in ':'.
                    bad_name = interval_text[:-1].strip()
                    errors.append(_error(
                        path, lineno,
                        f"invalid macro name {bad_name!r} (use letters, digits and '_', not starting with a digit)",
                    ))
                    previous_entry = None
                    continue
                if not state:
                    errors.append(_error(path, lineno, "STATE must not be empty"))
                    previous_entry = None
                    continue
            else:
                interval_text, state = interval_state.strip(), None
            if not interval_text:
                errors.append(_error(path, lineno, "INTERVAL must not be empty"))
                previous_entry = None
                continue
            entry = Node(lineno, indent, negated, interval_text, state)

        # Resolve dedents before adding the new entry.
        if previous_entry is not None and indent > (
            previous_entry.indent if isinstance(previous_entry, (Node, MacroLine)) else -1
        ):
            if isinstance(previous_entry, MacroLine):
                errors.append(_error(path, lineno, "macro definitions cannot have children"))
                previous_entry = None
                continue
            stack.append((previous_entry.indent, previous_entry))

        previous_indent = previous_entry.indent if previous_entry is not None else 0
        open_levels = {0, *(level for level, _node in stack)}
        if indent < previous_indent and indent not in open_levels:
            errors.append(_error(path, lineno, "dedent does not match an open indentation level"))
            previous_entry = None
            continue
        while stack and indent <= stack[-1][0]:
            stack.pop()

        # If the previous interval was a child and this line dedents to a level
        # that was never opened, the stack-pop check above catches it by comparing
        # against the still-open ancestor levels.
        if stack:
            parent = stack[-1][1]
            if isinstance(entry, Node):
                entry.parent = parent
                parent.children.append(entry)
                if entry.state_raw is not None:
                    try:
                        entry.effective_name, hidden = _decode_state(
                            entry.state_raw, parent, path, lineno
                        )
                        entry.reported = not hidden
                    except IntervalKeeperError as exc:
                        errors.append(exc)
            else:
                # Macro lines are scoped by indentation and still appear as child
                # entries only in the source-order list, not in the interval tree.
                roots.append(entry)
        else:
            roots.append(entry)
            if isinstance(entry, Node) and entry.state_raw is not None:
                try:
                    entry.effective_name, hidden = _decode_state(
                        entry.state_raw, None, path, lineno
                    )
                    entry.reported = not hidden
                except IntervalKeeperError as exc:
                    errors.append(exc)

        previous_entry = entry

    if errors:
        raise ReaderErrors(errors)
    return roots


def iter_nodes(entries: Iterable[ConfigEntry]) -> Iterable[Node]:
    """Yield interval nodes depth-first, preserving file order."""
    for entry in entries:
        if isinstance(entry, Node):
            yield entry
            yield from iter_nodes(entry.children)
