"""Bounded checks and cleanup for child processes launched by CAMELS."""

from __future__ import annotations

import time
from multiprocessing.process import BaseProcess


def terminate_process(process: BaseProcess, *, timeout: float = 2.0) -> None:
    """Reap a child even if it ignores a graceful terminate request."""
    if process.is_alive():
        process.terminate()
        process.join(timeout=timeout)
        if process.is_alive():
            process.kill()
            process.join(timeout=timeout)


def wait_for_process_event(
    process: BaseProcess,
    event,
    *,
    timeout: float = 30.0,
    name: str = "Background process",
) -> None:
    """Wait for a child readiness event without hanging when it exits."""
    if timeout <= 0:
        raise ValueError("Process startup timeout must be positive")

    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"{name} did not signal startup within {timeout:g}s")
        if event.wait(timeout=min(0.2, remaining)):
            if not process.is_alive():
                raise RuntimeError(
                    f"{name} exited during startup (exit code {process.exitcode})"
                )
            return
        if not process.is_alive():
            raise RuntimeError(
                f"{name} exited before signaling startup (exit code {process.exitcode})"
            )
