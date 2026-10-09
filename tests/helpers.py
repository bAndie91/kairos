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
    env: Mapping[str, str] | None = None,
) -> tuple[int, str, str]:
    """Run the source-checkout CLI and return (exit code, stdout, stderr)."""
    child_env = os.environ.copy()
    # Ensure the package works without relying on a caller-provided PYTHONPATH.
    child_env.pop("PYTHONPATH", None)
    if env:
        child_env.update(env)
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
