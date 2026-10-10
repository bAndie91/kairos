"""Helpers shared by Kairos tests."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "kairos"


def run_cli(
    args: Sequence[str],
    config_text: str | None = None,
    env: Mapping[str, str | None] | None = None,
) -> tuple[int, str, str]:
    """Run the source-checkout CLI and return (exit code, stdout, stderr)."""
    child_env = os.environ.copy()
    # Ensure the package works without relying on a caller-provided PYTHONPATH.
    child_env.pop("PYTHONPATH", None)
    locale_vars = ("LC_ALL", "LC_TIME", "LANG", "LANGUAGE")
    if not (env and any(name in env for name in locale_vars)):
        # Month/weekday names follow the locale: pin C so tests do not depend on the developer's.
        for name in locale_vars:
            child_env.pop(name, None)
        child_env["LC_ALL"] = "C"
    if env:
        for name, value in env.items():
            if value is None:
                child_env.pop(name, None)
            else:
                child_env[name] = value
    command = [sys.executable, str(LAUNCHER), *args]
    completed = subprocess.run(
        command,
        input=config_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=child_env,
        cwd=ROOT,
        check=False,
    )
    return completed.returncode, completed.stdout, completed.stderr


def make_ncal_stub(directory: str | Path) -> Path:
    """Create a fake ncal executable that prints a stable Easter-like date."""
    target = Path(directory) / "ncal"
    target.write_text("#!/bin/sh\nprintf '04/05/26\\n'\n", encoding="utf-8")
    target.chmod(0o755)
    return target
