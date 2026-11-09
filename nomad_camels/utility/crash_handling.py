"""Crash traceback setup shared by GUI startup and NOMAD integration.

When Python runs without a console (for example pythonw.exe), write fatal
tracebacks into the user configuration directory. Keep that file open for as
long as faulthandler may write into its descriptor.
"""

from __future__ import annotations

import faulthandler
import logging
import os
from pathlib import Path
import sys
from typing import TextIO

_crash_log_handle: TextIO | None = None


def _crash_log_directory() -> Path:
    """Find the user configuration directory without importing GUI modules."""
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "nomad_camels"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "nomad_camels"
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "nomad_camels"


def configure_fault_handler() -> None:
    """Enable faulthandler without leaving it with a closed file descriptor."""
    global _crash_log_handle

    # Do not replace an existing handler configured by pytest or a host app.
    if faulthandler.is_enabled():
        return

    if sys.__stderr__ is not None:
        try:
            faulthandler.enable(file=sys.__stderr__)
            return
        except (OSError, RuntimeError, ValueError):
            # The original stderr can be unavailable/closed for GUI apps.
            pass

    # pythonw.exe has no original stderr. Avoid importing load_save_functions
    # here: it pulls in Qt/configuration modules before QApplication exists.
    try:
        folder = _crash_log_directory()
        folder.mkdir(parents=True, exist_ok=True)
        if _crash_log_handle is None or _crash_log_handle.closed:
            _crash_log_handle = (folder / "faulthandler.log").open("a", encoding="utf-8")
        faulthandler.enable(file=_crash_log_handle)
    except (OSError, RuntimeError, ValueError) as exc:
        logging.warning("Could not enable NOMAD-CAMELS crash reporting: %s", exc)
        if _crash_log_handle is not None:
            _crash_log_handle.close()
            _crash_log_handle = None
