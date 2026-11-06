"""Execute a Python 3.14 smoke case with a cross-platform process-tree timeout.

The GUI and ZeroMQ checks spawn child processes. Killing only the test's
top-level Python process leaves inherited stdout/stderr pipes open, which can
make GitHub Actions hang even after subprocess.run(..., timeout=...) raises.
"""

import argparse
import os
from pathlib import Path
import signal
import subprocess
import sys


def kill_tree(process):
    if os.name == "nt":
        # Windows: also terminate the ZeroMQ subprocess spawned by CAMELS.
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        # POSIX: Popen(start_new_session=True) gives this test a private group.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("case", choices=("gui", "zmq", "hdf5", "generated"))
    parser.add_argument("timeout_seconds", type=int)
    arguments = parser.parse_args()
    test_script = Path(__file__).with_name("python314_runtime_smoke.py")
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    process = subprocess.Popen(
        [sys.executable, "-u", str(test_script), arguments.case], **kwargs
    )
    try:
        code = process.wait(timeout=arguments.timeout_seconds)
    except subprocess.TimeoutExpired:
        kill_tree(process)
        process.wait(timeout=10)
        print(
            f"TIMEOUT: Python 3.14 {arguments.case} smoke exceeded "
            f"{arguments.timeout_seconds} seconds",
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(124)
    if code != 0:
        raise SystemExit(code)


if __name__ == "__main__":
    main()
