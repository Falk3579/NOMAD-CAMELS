"""Opt-in, low-overhead startup phase timings saved outside the repository.

Set CAMELS_STARTUP_TIMING=1 before launching NOMAD-CAMELS to record phase
spans in a JSON file. Set CAMELS_STARTUP_TIMING_DIR to override the output
folder. All recordings are in-memory until flush() (or interpreter exit),
so disk writes do not affect the measured startup phases.

Times use a shared monotonic clock and can overlap across threads. The
clock begins when this module is first imported, not at Python process start.
"""

from __future__ import annotations

import atexit
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import tempfile
from threading import RLock, current_thread
from time import perf_counter_ns
from typing import Iterator


ENABLED = os.environ.get("CAMELS_STARTUP_TIMING", "").strip().lower() in {
    "1", "true", "yes", "on",
}
_ORIGIN_NS = perf_counter_ns()
_STARTED_AT_UTC = datetime.now(timezone.utc).isoformat() if ENABLED else None
_EVENTS: list[dict[str, object]] = []
_LOCK = RLock()
_OUTPUT_FILE: Path | None = None


def _milliseconds(ns: int) -> float:
    return round(ns / 1_000_000, 3)


def mark(name: str, **details: object) -> None:
    """Record an instant on the process-wide startup timeline."""
    if not ENABLED:
        return
    now = perf_counter_ns()
    event: dict[str, object] = {
        "type": "mark",
        "name": name,
        "start_ms": _milliseconds(now - _ORIGIN_NS),
        "thread": current_thread().name,
    }
    event.update(details)
    with _LOCK:
        _EVENTS.append(event)


@contextmanager
def phase(name: str) -> Iterator[None]:
    """Measure a block without changing its return value or exceptions."""
    if not ENABLED:
        yield
        return
    begin = perf_counter_ns()
    try:
        yield
    finally:
        end = perf_counter_ns()
        with _LOCK:
            _EVENTS.append({
                "type": "phase",
                "name": name,
                "start_ms": _milliseconds(begin - _ORIGIN_NS),
                "end_ms": _milliseconds(end - _ORIGIN_NS),
                "duration_ms": _milliseconds(end - begin),
                "thread": current_thread().name,
            })


def flush() -> Path | None:
    """Write the latest snapshot atomically; never stop the app on I/O errors."""
    if not ENABLED:
        return None
    global _OUTPUT_FILE
    temporary: str | None = None
    try:
        with _LOCK:
            if not _EVENTS:
                return None
            if _OUTPUT_FILE is None:
                base = os.environ.get("CAMELS_STARTUP_TIMING_DIR")
                if base:
                    directory = Path(base)
                else:
                    directory = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / (
                        "NOMAD-CAMELS-StartupBench/profiles"
                    )
                name = datetime.now(timezone.utc).strftime("startup-%Y%m%d-%H%M%S-%f")
                _OUTPUT_FILE = directory / f"{name}-pid{os.getpid()}.json"
            output = _OUTPUT_FILE
            output.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "format_version": 1,
                "started_at_utc": _STARTED_AT_UTC,
                "pid": os.getpid(),
                "clock_origin": "first import of nomad_camels.utility.startup_timing",
                "events": list(_EVENTS),
            }
            fd, temporary = tempfile.mkstemp(prefix=".startup-", suffix=".tmp", dir=output.parent)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(data, stream, indent=2)
                stream.write("\n")
            os.replace(temporary, output)
            return output
    except OSError as exc:
        logging.getLogger(__name__).warning("Cannot save startup timings: %s", exc)
        return None
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            except OSError:
                pass


if ENABLED:
    atexit.register(flush)
