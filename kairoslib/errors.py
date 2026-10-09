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
