"""Macro definition, scoping, and lazy command resolution (SPEC §5).

Names are validated, expansion is whole-word and single-pass, and command
macros (``NAME := ! COMMAND``) are run lazily, on first use, with the context
described in SPEC §5.1. A resolved value is cached on the scope that *defines*
the macro, so a command runs at most once however many scopes use it.

Two properties support the default-mode pruning of SPEC §5.4 (implemented in
``states.py``):

* ``allow_run=False`` makes resolution raise :class:`CommandNotRun` instead of
  running a command that has no cached value;
* a string macro expands only names that were visible where it was defined
  ("values are already fully expanded when defined"), even though the work is
  done lazily.
"""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Mapping, Sequence

from .errors import IntervalKeeperError
from .lexer import is_reserved_word

_MACRO_NAME_RE = re.compile(r"^[^\W\d]\w*$")  # unicode letters/digits/underscore (SPEC §5.2)

class CommandNotRun(Exception):
    """A command macro had to run but commands are suppressed (``allow_run=False``)."""

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.name = name


@dataclass
class MacroDefinition:
    """A single macro definition in a lexical scope."""

    name: str
    value: str
    command: bool = False
    lineno: int | None = None
    # Names visible where the macro was defined (SPEC §5.1/§5.2).
    visible_names: frozenset = field(default_factory=frozenset)


def validate_macro_name(name: str) -> None:
    """Reject invalid or reserved macro names before they become visible."""
    if not isinstance(name, str) or not _MACRO_NAME_RE.fullmatch(name):
        raise IntervalKeeperError(None, None, f"invalid macro name {name!r}")
    if is_reserved_word(name):
        raise IntervalKeeperError(None, None, f"macro name {name!r} is reserved")


def expand_macro_text(text: str, values: Mapping[str, str] | Callable[[str], str]) -> str:
    """Expand every whole-word macro name once.

    Values may be provided as a literal mapping or a callable that resolves a
    macro name on demand (raising ``KeyError`` for a word that is not a macro).
    This keeps the expansion single-pass while supporting lazy command-backed
    macros.
    """
    if not text:
        return text

    if isinstance(values, Mapping):
        names = sorted(values, key=len, reverse=True)
        if not names:
            return text

        pattern = re.compile(r"(?<!\w)(?:" + "|".join(re.escape(name) for name in names) + r")(?!\w)")
        return pattern.sub(lambda match: values[match.group(0)], text)

    pattern = re.compile(r"(?<!\w)[^\W\d]\w*(?!\w)")

    def replacer(match: re.Match[str]) -> str:
        token = match.group(0)
        try:
            return values(token)
        except KeyError:
            return token

    return pattern.sub(replacer, text)


class MacroScope:
    """Scoped macro registry with lazy command evaluation.

    The lexically visible macro set is the union of the current scope and any
    enclosing scopes; redefining a visible name is rejected (SPEC §5.3, D8).
    """

    def __init__(self, parent: "MacroScope | None" = None) -> None:
        self.parent = parent
        self._definitions: dict[str, MacroDefinition] = {}
        self._resolved: dict[str, str] = {}
        self._resolving: set[str] = set()

    def visible(self) -> dict[str, MacroDefinition]:
        values: dict[str, MacroDefinition] = {}
        if self.parent is not None:
            values.update(self.parent.visible())
        values.update(self._definitions)
        return values

    def _owner(self, name: str) -> "MacroScope | None":
        scope: MacroScope | None = self
        while scope is not None:
            if name in scope._definitions:
                return scope
            scope = scope.parent
        return None

    def define(self, name: str, value: str, *, command: bool = False, lineno: int | None = None) -> MacroDefinition:
        validate_macro_name(name)
        visible = self.visible()
        if name in visible:
            raise IntervalKeeperError(None, lineno, f"macro name {name!r} is already visible")
        if command:
            value = value.lstrip()
            if value.startswith("!"):
                value = value[1:].lstrip()
        definition = MacroDefinition(
            name=name, value=value, command=command, lineno=lineno,
            visible_names=frozenset(visible),
        )
        self._definitions[name] = definition
        self._resolved.pop(name, None)
        return definition

    def expand(
        self,
        text: str,
        *,
        now: datetime | None = None,
        context: Sequence[tuple[int, str, str]] | None = None,
        allow_run: bool = True,
    ) -> str:
        """Expand the macros visible from this scope in *text* (one pass)."""
        return expand_macro_text(
            text,
            lambda token: self.resolve(token, now=now, context=context, allow_run=allow_run),
        )

    def resolve(
        self,
        name: str,
        *,
        now: datetime | None = None,
        env: Mapping[str, str] | None = None,
        context: Sequence[tuple[int, str, str]] | None = None,
        allow_run: bool = True,
    ) -> str:
        """Return the value of the visible macro *name*.

        Raises ``KeyError`` when no such macro is visible and
        :class:`CommandNotRun` when a command would have to run but
        *allow_run* is false and no value is cached.
        """
        owner = self._owner(name)
        if owner is None:
            raise KeyError(name)
        definition = owner._definitions[name]
        if name in owner._resolved:
            return owner._resolved[name]
        if name in owner._resolving:
            raise IntervalKeeperError(None, definition.lineno, f"recursive macro expansion for {name!r}")
        if definition.command and not allow_run:
            raise CommandNotRun(name)

        owner._resolving.add(name)
        try:
            if definition.command:
                value = owner._run_command_macro(
                    definition, now=now, env=env, context=context or (), allow_run=allow_run,
                )
            else:
                def lookup(token: str) -> str:
                    if token not in definition.visible_names:
                        raise KeyError(token)
                    return owner.resolve(token, now=now, env=env, context=context, allow_run=allow_run)

                value = expand_macro_text(definition.value, lookup)
            owner._resolved[name] = value
            return value
        finally:
            owner._resolving.discard(name)

    def _run_command_macro(
        self,
        definition: MacroDefinition,
        *,
        now: datetime | None,
        env: Mapping[str, str] | None,
        context: Sequence[tuple[int, str, str]],
        allow_run: bool,
    ) -> str:
        shell = os.environ.get("SHELL") or "/bin/sh"
        process_env = os.environ.copy()
        if env:
            process_env.update(env)

        # KAIROS_MACRO_<NAME> for every macro visible where this one was defined.
        for macro_name in sorted(definition.visible_names):
            if macro_name in self._resolving:
                continue
            process_env[f"KAIROS_MACRO_{macro_name}"] = self.resolve(
                macro_name, now=now, context=context, allow_run=allow_run,
            )

        when = datetime.now(timezone.utc) if now is None else now
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        process_env["KAIROS_NOW"] = when.isoformat(timespec="seconds")

        for level, interval, state in context:
            process_env[f"KAIROS_INTERVAL_{level}"] = interval
            process_env[f"KAIROS_STATE_{level}"] = state

        completed = subprocess.run(
            [shell, "-c", definition.value],
            check=False,
            env=process_env,
            stdin=subprocess.DEVNULL,
            stderr=None,
            stdout=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if completed.returncode != 0:
            raise IntervalKeeperError(
                None, definition.lineno,
                f"macro command for {definition.name!r} failed with exit status {completed.returncode}",
            )

        return completed.stdout.rstrip("\n").replace("\n", " ")


__all__ = [
    "CommandNotRun",
    "MacroDefinition",
    "MacroScope",
    "expand_macro_text",
    "validate_macro_name",
]
