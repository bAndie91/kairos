"""Configuration discovery and default-file creation (SPEC §3)."""
from __future__ import annotations

import os
import stat
import sys
from pathlib import Path
from typing import Mapping, TextIO

from .defaults import DEFAULT_CONFIG
from .errors import IntervalKeeperError

CONFIG_RELATIVE_PATH = Path("kairos") / "intervals.conf"


def _absolute_env_path(value: str | None) -> Path | None:
    """Return an XDG path only when it is absolute, as required by the XDG spec."""
    if not value:
        return None
    path = Path(value).expanduser()
    return path if path.is_absolute() else None


def _config_home(env: Mapping[str, str]) -> Path:
    configured = _absolute_env_path(env.get("XDG_CONFIG_HOME"))
    if configured is not None:
        return configured
    home = env.get("HOME")
    if home:
        return Path(home).expanduser() / ".config"
    return Path.home() / ".config"


def _search_dirs(env: Mapping[str, str]) -> list[Path]:
    raw = env.get("XDG_CONFIG_DIRS")
    if raw is None:
        raw = "/etc/xdg"
    result: list[Path] = []
    for entry in raw.split(os.pathsep):
        path = _absolute_env_path(entry)
        if path is not None:
            result.append(path)
    return result


def _read_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise IntervalKeeperError(str(path), None, f"cannot read config: {exc}") from exc


def load_config(
    config_arg: str | None,
    *,
    stdin: TextIO | None = None,
    env: Mapping[str, str] | None = None,
    stderr: TextIO | None = None,
) -> tuple[str, str]:
    """Return (display path, configuration text).

    An explicit '-' reads stdin. An explicit path is never created. With no
    explicit path, XDG user/system locations are searched before creating the
    default user configuration.
    """
    environ = os.environ if env is None else env
    error_stream = sys.stderr if stderr is None else stderr

    if config_arg == "-":
        source = sys.stdin if stdin is None else stdin
        try:
            return "<stdin>", source.read()
        except OSError as exc:
            raise IntervalKeeperError("<stdin>", None, f"cannot read config: {exc}") from exc

    if config_arg is not None:
        path = Path(config_arg).expanduser()
        if not path.is_file():
            raise IntervalKeeperError(str(path), None, "config file does not exist or is not a regular file")
        return str(path), _read_file(path)

    candidates = [_config_home(environ) / CONFIG_RELATIVE_PATH]
    candidates.extend(directory / CONFIG_RELATIVE_PATH for directory in _search_dirs(environ))
    for path in candidates:
        if path.is_file():
            return str(path), _read_file(path)

    target = _config_home(environ) / CONFIG_RELATIVE_PATH
    try:
        # Create only the leaf hierarchy needed; set the mode explicitly because
        # mkdir's mode is otherwise filtered by the process umask.
        if not target.parent.exists():
            target.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
            target.parent.chmod(0o700)
        target.write_text(DEFAULT_CONFIG, encoding="utf-8")
        target.chmod(0o644)
    except OSError as exc:
        raise IntervalKeeperError(str(target), None, f"cannot create default config: {exc}") from exc
    print(f"kairos: created default config: {target}", file=error_stream)
    return str(target), DEFAULT_CONFIG
