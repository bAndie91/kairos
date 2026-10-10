"""Shared error types and diagnostics for Kairos."""
from __future__ import annotations


class IntervalKeeperError(Exception):
    """A user-facing configuration or evaluation error."""

    def __init__(self, path: str | None, line: int | None, message: str) -> None:
        super().__init__(message)
        self.path = path
        self.line = line
        self.message = message

    def diagnostic(self) -> str:
        if self.path is not None and self.line is not None:
            return f"kairos: {self.path}:{self.line}: error: {self.message}"
        if self.path is not None:
            return f"kairos: {self.path}: error: {self.message}"
        return f"kairos: error: {self.message}"

    def diagnostics(self) -> list[str]:
        """Every diagnostic line this error stands for (one, unless aggregated)."""
        return [self.diagnostic()]


class ErrorList(IntervalKeeperError):
    """Several independent line diagnostics reported together (exit 2 once)."""

    def __init__(self, errors: list[IntervalKeeperError]) -> None:
        if not errors:
            raise ValueError("ErrorList requires at least one diagnostic")
        first = errors[0]
        super().__init__(first.path, first.line, first.message)
        self.errors = tuple(errors)

    def diagnostics(self) -> list[str]:
        lines: list[str] = []
        for error in self.errors:
            lines.extend(error.diagnostics())
        return lines


def located(error: IntervalKeeperError, path: str | None, line: int | None) -> IntervalKeeperError:
    """Return *error* with a missing path/line filled in (lower layers do not know them)."""
    if error.path is not None and error.line is not None:
        return error
    return IntervalKeeperError(
        error.path if error.path is not None else path,
        error.line if error.line is not None else line,
        error.message,
    )
