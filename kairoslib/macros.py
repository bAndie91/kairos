"""Macro definition, scoping, and lazy command resolution.

This is the minimal implementation needed to continue the plan beyond M4 without
picking the parser milestone (M5). It supports the macro rules in SPEC §5 for
name validation, whole-word expansion, and command-backed macro execution.
"""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Mapping

from .errors import IntervalKeeperError

_MACRO_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_MONTHS = {
    "jan", "january", "feb", "february", "mar", "march", "apr", "april",
    "may", "jun", "june", "jul", "july", "aug", "august", "sep", "sept",
    "september", "oct", "october", "nov", "november", "dec", "december",
}
_WEEKDAYS = {
    "mon", "monday", "tue", "tues", "tuesday", "wed", "wednesday", "thu",
    "thur", "thurs", "thursday", "fri", "friday", "sat", "saturday", "sun",
    "sunday",
}
_DURATION_UNITS = {"second", "seconds", "minute", "minutes", "hour", "hours", "day", "days", "week", "weeks", "month", "months", "year", "years"}
_RESERVED_MACRO_NAMES = _MONTHS | _WEEKDAYS | _DURATION_UNITS | {"until", "utc", "gmt", "z"}


@dataclass
class MacroDefinition:
    """A single macro definition in a lexical scope."""

    name: str
    value: str
    command: bool = False
    lineno: int | None = None


def validate_macro_name(name: str) -> None:
    """Reject invalid or reserved macro names before they become visible."""
    if not isinstance(name, str) or not _MACRO_NAME_RE.fullmatch(name):
        raise IntervalKeeperError(None, None, f"invalid macro name {name!r}")
    if name.casefold() in _RESERVED_MACRO_NAMES:
        raise IntervalKeeperError(None, None, f"macro name {name!r} is reserved")


def _normalised_macro_key(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", name).upper()


def expand_macro_text(text: str, values: Mapping[str, str] | Callable[[str], str]) -> str:
    """Expand every whole-word macro name once.

    Values may be provided as a literal mapping or a callable that resolves a
    macro name on demand. This keeps the expansion single-pass while supporting
    lazy command-backed macros.
    """
    if not text:
        return text

    if isinstance(values, Mapping):
        names = sorted(values, key=len, reverse=True)
        if not names:
            return text

        def _resolve(name: str) -> str:
            return values[name]

        pattern = re.compile(r"(?<![A-Za-z0-9_])(?:" + "|".join(re.escape(name) for name in names) + r")(?![A-Za-z0-9_])")

        def replacer(match: re.Match[str]) -> str:
            token = match.group(0)
            return _resolve(token)

        return pattern.sub(replacer, text)

    pattern = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z_][A-Za-z0-9_]*(?![A-Za-z0-9_])")

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
    enclosing scopes, with shadowing rejected when the name is already visible.
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

    def define(self, name: str, value: str, *, command: bool = False, lineno: int | None = None) -> MacroDefinition:
        validate_macro_name(name)
        visible = self.visible()
        if name in visible:
            raise IntervalKeeperError(None, lineno, f"macro name {name!r} is already visible")
        if command:
            value = value.lstrip()
            if value.startswith("!"):
                value = value[1:].lstrip()
        definition = MacroDefinition(name=name, value=value, command=command, lineno=lineno)
        self._definitions[name] = definition
        self._resolved.pop(name, None)
        return definition

    def resolve(self, name: str, *, now: datetime | None = None, env: Mapping[str, str] | None = None, context: list[tuple[int, str, str]] | None = None) -> str:
        visible = self.visible()
        if name not in visible:
            raise KeyError(name)

        definition = visible[name]
        if name in self._resolved:
            return self._resolved[name]
        if name in self._resolving:
            raise IntervalKeeperError(None, definition.lineno, f"recursive macro expansion for {name!r}")

        self._resolving.add(name)
        try:
            if definition.command:
                value = self._run_command_macro(definition.value, now=now, env=env, context=context or [])
            else:
                value = expand_macro_text(definition.value, lambda token: self.resolve(token, now=now, env=env, context=context))
            self._resolved[name] = value
            return value
        finally:
            self._resolving.discard(name)

    def _run_command_macro(
        self,
        command: str,
        *,
        now: datetime | None = None,
        env: Mapping[str, str] | None = None,
        context: list[tuple[int, str, str]],
    ) -> str:
        shell = os.environ.get("SHELL", "/bin/sh")
        process_env = os.environ.copy()
        if env:
            process_env.update(env)

        visible = self.visible()
        for macro_name in visible:
            if macro_name in self._resolving:
                continue
            process_env[f"KAIROS_MACRO_{_normalised_macro_key(macro_name)}"] = self.resolve(macro_name, now=now, env=process_env, context=context)

        when = datetime.now(timezone.utc) if now is None else now
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        process_env["KAIROS_NOW"] = when.isoformat(timespec="seconds")

        for level, interval, state in context:
            process_env[f"KAIROS_INTERVAL_{level}"] = interval
            process_env[f"KAIROS_STATE_{level}"] = state

        completed = subprocess.run(
            [shell, "-c", command],
            check=False,
            env=process_env,
            stdin=subprocess.DEVNULL,
            stderr=None,
            stdout=subprocess.PIPE,
            text=True,
        )
        if completed.returncode != 0:
            raise IntervalKeeperError(None, None, f"macro command failed with exit code {completed.returncode}")

        output = completed.stdout.strip("\n")
        output = output.replace("\n", " ")
        return output


__all__ = [
    "MacroDefinition",
    "MacroScope",
    "expand_macro_text",
    "validate_macro_name",
]
