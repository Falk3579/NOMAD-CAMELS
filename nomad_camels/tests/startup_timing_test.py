"""Pure-stdlib startup timing unit tests (no Qt dependency)."""

import json
from pathlib import Path
from threading import Thread
from time import sleep

import pytest

from nomad_camels.utility import startup_timing


@pytest.fixture
def timing(monkeypatch, tmp_path):
    monkeypatch.setattr(startup_timing, "ENABLED", True)
    monkeypatch.setattr(startup_timing, "_EVENTS", [])
    monkeypatch.setattr(startup_timing, "_OUTPUT_FILE", None)
    monkeypatch.setenv("CAMELS_STARTUP_TIMING_DIR", str(tmp_path))
    return tmp_path


def test_records_nested_phases_and_milestones(timing):
    startup_timing.mark("launcher.start", proxy_enabled=False)
    with startup_timing.phase("main_window"):
        with startup_timing.phase("preferences"):
            sleep(0.003)
    path = startup_timing.flush()
    assert path is not None and path.parent == timing
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["format_version"] == 1
    events = payload["events"]
    assert {event["name"] for event in events} == {
        "launcher.start", "main_window", "preferences",
    }
    by_name = {event["name"]: event for event in events}
    assert by_name["launcher.start"]["proxy_enabled"] is False
    assert by_name["preferences"]["duration_ms"] >= 2
    assert by_name["main_window"]["duration_ms"] >= by_name["preferences"]["duration_ms"]
    assert by_name["preferences"]["start_ms"] >= by_name["main_window"]["start_ms"]
    assert by_name["preferences"]["end_ms"] <= by_name["main_window"]["end_ms"]


def test_flush_updates_one_file_with_background_events(timing):
    startup_timing.mark("main_window.shown")
    first = startup_timing.flush()

    def background():
        with startup_timing.phase("background.imports"):
            startup_timing.mark("background.thread_started")
        startup_timing.flush()

    worker = Thread(target=background)
    worker.start()
    worker.join(timeout=3)
    assert not worker.is_alive()
    assert startup_timing.flush() == first
    assert len(list(timing.glob("*.json"))) == 1
    payload = json.loads(first.read_text(encoding="utf-8"))
    assert {event["name"] for event in payload["events"]} == {
        "main_window.shown", "background.imports", "background.thread_started",
    }


def test_phase_rethrows_original_exception_and_still_records(timing):
    with pytest.raises(ValueError, match="sentinel"):
        with startup_timing.phase("failing.phase"):
            raise ValueError("sentinel")
    events = json.loads(startup_timing.flush().read_text(encoding="utf-8"))["events"]
    assert events[0]["name"] == "failing.phase"


def test_disabled_mode_writes_nothing(monkeypatch, tmp_path):
    monkeypatch.setattr(startup_timing, "ENABLED", False)
    monkeypatch.setenv("CAMELS_STARTUP_TIMING_DIR", str(tmp_path))
    startup_timing.mark("ignored")
    with startup_timing.phase("ignored.block"):
        pass
    assert startup_timing.flush() is None
    assert not list(tmp_path.iterdir())


def test_unwritable_timing_directory_does_not_interrupt_startup(timing):
    obstacle = timing / "not-a-directory"
    obstacle.write_text("occupied", encoding="utf-8")
    startup_timing._OUTPUT_FILE = obstacle / "data.json"
    startup_timing.mark("startup.continues")
    assert startup_timing.flush() is None


def test_timing_file_is_local_and_includes_no_configuration_details(timing):
    startup_timing.mark("launcher.start")
    output = startup_timing.flush()
    data = output.read_text(encoding="utf-8")
    assert str(Path.home()) not in data
    assert "CAMELS_STARTUP_TIMING_DIR" not in data
