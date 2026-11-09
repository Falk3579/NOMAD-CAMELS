"""User-owned config pointer and startup-cache locations.

Both files were historically stored in the installed nomad_camels package.
Read those legacy locations only as migration sources; never write there.
This module intentionally uses only the standard library so it is safe to
import before QApplication and during pythonw.exe startup.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
import sys
import tempfile
from collections.abc import Iterable

_logger = logging.getLogger(__name__)


def user_config_root() -> Path:
    """Stable user-owned directory, independent of custom preference locations."""
    home = Path.home()
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        return (Path(base) if base else home / "AppData" / "Local") / "nomad_camels"
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "nomad_camels"
    if sys.platform.startswith("linux"):
        base = os.environ.get("XDG_CONFIG_HOME")
        return (Path(base) if base else home / ".config") / "nomad_camels"
    return home / ".nomad_camels"


def _legacy_package_root() -> Path:
    return Path(__file__).resolve().parents[1]


def config_pointer_file() -> Path:
    """The pointer is *always* in the default user directory, not the target."""
    return user_config_root() / "config_path"


def startup_cache_file() -> Path:
    return user_config_root() / "startup_packages.txt"


def _read_optional(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def _atomic_write(path: Path, content: str) -> None:
    """Replace a user file without truncating a valid previous value."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def write_config_pointer(config_directory: str | os.PathLike[str]) -> None:
    """Persist the chosen directory without modifying installed package files."""
    directory = os.fspath(config_directory)
    if not directory.strip():
        raise ValueError("Configuration directory must not be empty")
    _atomic_write(config_pointer_file(), directory)


def read_config_pointer() -> str | None:
    """Prefer a new pointer; adopt an old package-local pointer if necessary."""
    destination = config_pointer_file()
    new_value = _read_optional(destination)
    if new_value is not None and new_value.strip():
        return new_value.strip()

    legacy = _read_optional(_legacy_package_root() / "config_path")
    if legacy is None or not legacy.strip():
        return None

    selected_directory = legacy.strip()
    # Existing users keep the same configuration folder. If migration fails,
    # use the old pointer for this invocation and retry on the next launch.
    try:
        write_config_pointer(selected_directory)
    except OSError as error:
        _logger.warning("Could not migrate legacy configuration pointer: %s", error)
    return selected_directory


def read_startup_packages() -> list[str]:
    """Read the user cache, adopting a legacy package cache if one exists."""
    destination = startup_cache_file()
    try:
        content = _read_optional(destination)
        if content is None:
            content = _read_optional(_legacy_package_root() / "startup_packages.txt")
            if content is not None:
                try:
                    _atomic_write(destination, content)
                except OSError as error:
                    _logger.warning("Could not migrate startup package cache: %s", error)
    except OSError as error:
        _logger.warning("Could not read startup package cache: %s", error)
        return []
    return content.splitlines() if content is not None else []


def write_startup_packages(names: Iterable[str]) -> None:
    """Best-effort cache write: a read-only user directory must not block GUI."""
    path = startup_cache_file()
    try:
        if path.is_file():
            return
        content = "".join(f"{name}\n" for name in names if name and not name.startswith("_"))
        _atomic_write(path, content)
    except OSError as error:
        _logger.warning("Could not save startup package cache: %s", error)
