"""Summarize opt-in NOMAD-CAMELS startup timing JSON files.

Usage (Windows):
    python dev_tools/summarize_startup_timings.py
    python dev_tools/summarize_startup_timings.py C:\\path\\to\\profiles

Values are medians of per-process durations. Overlapping/nested phases must
not be added together. The first Python module and Qt imports happen before
start_camels() and therefore are not included in launcher elapsed timing.
"""

from __future__ import annotations

from collections import defaultdict
import json
import os
from pathlib import Path
from statistics import median
import sys


def summarize(directory: Path) -> str:
    if not directory.is_dir():
        raise ValueError(f"Timing directory does not exist: {directory}")

    durations: dict[str, list[float]] = defaultdict(list)
    startup_times: list[float] = []
    valid_files = 0
    for path in sorted(directory.glob("startup-*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("format_version") != 1:
                continue
            events = payload["events"]
            phases: dict[str, float] = defaultdict(float)
            marks: dict[str, float] = {}
            for event in events:
                if event["type"] == "phase":
                    phases[event["name"]] += float(event["duration_ms"])
                elif event["type"] == "mark":
                    marks[event["name"]] = float(event["start_ms"])
            # Ignore phases from later user interactions, not startup.
            show_ms = marks.get("launcher.show_called", float("inf"))
            for event in events:
                if event["type"] == "phase" and float(event["start_ms"]) > show_ms:
                    phases[event["name"]] -= float(event["duration_ms"])
            for name, duration_ms in phases.items():
                if duration_ms > 0:
                    durations[name].append(duration_ms)
            if "background.thread_started" in marks and "background.thread_finished" in marks:
                durations["background.import_total"].append(
                    marks["background.thread_finished"] - marks["background.thread_started"]
                )
            if "launcher.show_called" in marks and "launcher.start" in marks:
                startup_times.append(marks["launcher.show_called"] - marks["launcher.start"])
            valid_files += 1
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(f"Skipping {path.name}: {exc}", file=sys.stderr)

    if valid_files == 0:
        return f"No valid startup timing files found in {directory}"

    rows = [f"Read {valid_files} profile(s) from {directory}"]
    if startup_times:
        rows.append(f"Launcher start -> show() median: {median(startup_times):.1f} ms "
                    f"({len(startup_times)} runs; min {min(startup_times):.1f}, "
                    f"max {max(startup_times):.1f})")
    rows.extend(["", "Phase (nested phases overlap)            N  Median ms   Min ms   Max ms",
                 "-" * 74])
    for name, values in sorted(durations.items(), key=lambda pair: median(pair[1]), reverse=True):
        rows.append(f"{name:<38} {len(values):>2} {median(values):>10.1f} "
                    f"{min(values):>8.1f} {max(values):>8.1f}")
    rows.append("\nNote: start_camels() begins after initial Python/PySide6 module imports. ")
    rows.append("Phases are nested or concurrent; do not sum their durations.")
    return "\n".join(rows)


def main() -> int:
    default = Path(os.environ.get("CAMELS_STARTUP_TIMING_DIR") or
                   Path(os.environ.get("LOCALAPPDATA") or Path.home()) /
                   "NOMAD-CAMELS-StartupBench/profiles")
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else default
    try:
        print(summarize(path))
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
