"""Hierarchy semantics and reported-state unions (SPEC §5.4, §7.2-§7.4).

Two steps:

1. :func:`build_lines` walks the config in file order, keeps the macro scopes
   (SPEC §5.3), expands and parses every INTERVAL, and returns the interval
   lines depth-first as :class:`Line` objects. With a *window* it also computes
   each line's effective set as it goes and prunes subtrees whose parent is not
   active in that window (default mode, SPEC §5.4): commands inside a pruned
   subtree do not run, and a line that needs such a command is only
   structurally validated (the reader already did that).
2. :func:`effective_sets` / :func:`reported_sets` apply the hierarchy rules
   (``E(L) = E(parent) ∩ S(L)``, or ``\\`` for a negated line) over any window
   and group the reported lines by state name (``U(name)``).

Calendar and zone logic stays in ``evaluate.py``; this module only combines
the resulting :class:`~kairoslib.ranges.RangeSet` values.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, tzinfo
from typing import Dict, List, Optional, Sequence, Tuple

from .errors import ErrorList, IntervalKeeperError, located
from .evaluate import evaluate
from .macros import CommandNotRun, MacroScope
from .parser import Expr, parse_interval
from .ranges import EMPTY, RangeSet
from .reader import ConfigEntry, MacroLine, Node, iter_nodes


@dataclass(eq=False)
class Line:
    """One interval line with its macro scope and (when available) its AST."""

    node: Node
    parent: Optional["Line"]
    depth: int  # 0 for a top-level line (the LEVEL of SPEC §5.1)
    scope: MacroScope
    expanded: Optional[str] = None  # INTERVAL text after macro expansion
    expr: Optional[Expr] = None  # None: not fully parsed (pruned or failed)
    eff: RangeSet = EMPTY  # E(L) over the build window (default mode only)
    evaluated: bool = False  # ``eff`` is meaningful

    @property
    def negated(self) -> bool:
        return self.node.negated

    @property
    def name(self) -> Optional[str]:
        """The reported state name, or None for a hidden / STATE-less line."""
        return self.node.effective_name if self.node.reported else None


def _context(line: Line) -> List[Tuple[int, str, str]]:
    """``(LEVEL, INTERVAL, STATE)`` for each ancestor and the line itself (SPEC §5.1).

    The line's own INTERVAL is still being expanded, so its raw text is given.
    """
    chain: List[Line] = []
    cursor: Optional[Line] = line
    while cursor is not None:
        chain.append(cursor)
        cursor = cursor.parent
    chain.reverse()
    result: List[Tuple[int, str, str]] = []
    for level, item in enumerate(chain):
        text = item.expanded if item.expanded is not None else item.node.interval_text
        if item.node.negated:
            text = "! " + text
        result.append((level, text, item.node.effective_name or ""))
    return result


def build_lines(
    entries: Sequence[ConfigEntry],
    *,
    path: Optional[str],
    tz: tzinfo,
    now: datetime,
    window: Optional[Tuple[int, int]] = None,
    run_all_commands: bool = False,
) -> List[Line]:
    """Expand macros and parse every INTERVAL; raise :class:`ErrorList` on any error.

    *now* is the evaluation instant exposed to commands as ``KAIROS_NOW``.
    *window* ``(lo, hi)`` (POSIX seconds) switches on default-mode pruning: a
    line's parent must be active somewhere in the window for commands below it
    to run. Without a window nothing is skipped (``--check``, ``--next-change``).
    Commands otherwise run lazily, on first use (D4); *run_all_commands*
    (``--check``) also runs the ones nothing uses, so a broken command is found.
    """
    # The reader keeps top-level nodes (children nested) and every macro line in
    # one list; merging by line number restores file order for the scope walk.
    flat: List[object] = [*iter_nodes(entries), *(e for e in entries if isinstance(e, MacroLine))]
    flat.sort(key=lambda entry: entry.lineno)  # type: ignore[attr-defined]

    errors: List[IntervalKeeperError] = []
    lines: List[Line] = []
    stack: List[Line] = []
    global_scope = MacroScope()
    command_macros: List[Tuple[MacroScope, MacroLine, Optional[Line]]] = []

    def parent_active(line: Line) -> bool:
        """May the subtree below *line* run commands? (SPEC §5.4)"""
        if window is None:
            return True
        return line.evaluated and bool(line.eff)

    for entry in flat:
        while stack and stack[-1].node.indent >= entry.indent:  # type: ignore[attr-defined]
            stack.pop()
        parent = stack[-1] if stack else None
        scope = parent.scope if parent is not None else global_scope

        if isinstance(entry, MacroLine):
            is_command = entry.value.startswith("!")
            try:
                scope.define(entry.name, entry.value, command=is_command, lineno=entry.lineno)
            except IntervalKeeperError as exc:
                errors.append(located(exc, path, entry.lineno))
            else:
                if is_command:
                    command_macros.append((scope, entry, parent))
            continue

        node: Node = entry  # type: ignore[assignment]
        line = Line(node, parent, len(stack), MacroScope(parent=scope))
        stack.append(line)
        lines.append(line)

        allow_run = parent is None or parent_active(parent)
        try:
            line.expanded = line.scope.expand(
                node.interval_text, now=now, context=_context(line), allow_run=allow_run,
            )
        except CommandNotRun:
            continue  # depends on a command that must not run here: structure only
        except IntervalKeeperError as exc:
            errors.append(located(exc, path, node.lineno))
            continue
        try:
            line.expr = parse_interval(line.expanded, path=path, lineno=node.lineno)
        except IntervalKeeperError as exc:
            errors.append(located(exc, path, node.lineno))
            continue

        if window is None:
            continue
        lo, hi = window
        if parent is None:
            base: Optional[RangeSet] = RangeSet([(lo, hi)])
        else:
            base = parent.eff if parent.evaluated else None
        if base is None:
            continue
        if base:
            try:
                spec = evaluate(line.expr, lo, hi, tz)
            except IntervalKeeperError as exc:
                errors.append(located(exc, path, node.lineno))
                continue
            line.eff = base.subtract(spec) if node.negated else base.intersect(spec)
        line.evaluated = True

    if run_all_commands:
        for scope, macro, owner_line in command_macros:
            try:
                # A macro some line already used keeps its first-use value; an
                # unused one sees the lines above its definition as context.
                scope.resolve(
                    macro.name, now=now, allow_run=True,
                    context=_context(owner_line) if owner_line is not None else [],
                )
            except IntervalKeeperError as exc:
                errors.append(located(exc, path, macro.lineno))

    if errors:
        # A failing command is reported once per macro, however often it was used.
        unique = list({(e.path, e.line, e.message): e for e in errors}.values())
        unique.sort(key=lambda error: (error.line is None, error.line or 0))
        raise ErrorList(unique)
    return lines


def active_states(lines: Sequence[Line], at: int) -> List[str]:
    """Names of the reported states active at *at*, in config order (SPEC §7.4).

    *lines* must come from :func:`build_lines` with a window containing *at*.
    """
    active: Dict[str, bool] = {}
    for line in lines:
        name = line.name
        if not name:
            continue
        on = line.evaluated and line.eff.contains(at)
        active[name] = active.get(name, False) or on
    return [name for name, on in active.items() if on]


def effective_sets(lines: Sequence[Line], lo: int, hi: int, tz: tzinfo) -> Dict[Line, RangeSet]:
    """``E(L)`` for every line over the window ``[lo, hi)`` (SPEC §7.2, §7.3)."""
    result: Dict[Line, RangeSet] = {}
    for line in lines:
        if line.expr is None:
            raise ValueError(f"line {line.node.lineno} was not fully parsed (pruned build)")
        base = RangeSet([(lo, hi)]) if line.parent is None else result[line.parent]
        if not base:
            result[line] = EMPTY
            continue
        spec = evaluate(line.expr, lo, hi, tz)
        result[line] = base.subtract(spec) if line.negated else base.intersect(spec)
    return result


def reported_sets(lines: Sequence[Line], lo: int, hi: int, tz: tzinfo) -> Dict[str, RangeSet]:
    """``U(name)`` over ``[lo, hi)`` for each reported name, in order of first appearance."""
    effective = effective_sets(lines, lo, hi, tz)
    union: Dict[str, RangeSet] = {}
    for line in lines:
        name = line.name
        if not name:
            continue
        union[name] = union.get(name, EMPTY).union(effective[line])
    return union


def states_at(sets: Dict[str, RangeSet], t: int) -> List[str]:
    """The reported state names whose union contains the instant *t*."""
    return [name for name, ranges in sets.items() if ranges.contains(t)]


__all__ = [
    "Line",
    "active_states",
    "build_lines",
    "effective_sets",
    "reported_sets",
    "states_at",
]
