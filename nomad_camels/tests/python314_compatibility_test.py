"""Regression tests for import-side effects and fault-reporting lifetime."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


def test_import_plot_placement_does_not_construct_qapplication() -> None:
    """Importing helper modules should not create an implicit Qt application."""
    script = (
        "from PySide6.QtCore import QCoreApplication\n"
        "assert QCoreApplication.instance() is None\n"
        "from nomad_camels.utility import plot_placement\n"
        "assert QCoreApplication.instance() is None\n"
    )
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env=env,
        timeout=45,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_plot_placement_discovers_screens_lazily(qtbot) -> None:
    from nomad_camels.utility import plot_placement

    plot_placement.reset_variables()
    assert plot_placement.screens

    from PySide6.QtWidgets import QWidget

    widget = QWidget()
    qtbot.addWidget(widget)
    plot_placement.place_widget(widget)
    assert widget.isVisible()


def test_crash_log_file_stays_open(monkeypatch, tmp_path: Path) -> None:
    """faulthandler must hold a live descriptor when console stderr is absent."""
    from nomad_camels.utility import crash_handling

    seen_files = []
    monkeypatch.setattr(crash_handling.sys, "__stderr__", None)
    monkeypatch.setattr(crash_handling.faulthandler, "is_enabled", lambda: False)
    monkeypatch.setattr(
        crash_handling.faulthandler,
        "enable",
        lambda *, file: seen_files.append(file),
    )
    monkeypatch.setattr(crash_handling, "_crash_log_directory", lambda: tmp_path)

    try:
        crash_handling.configure_fault_handler()
        handle = crash_handling._crash_log_handle
        assert handle is not None
        assert not handle.closed
        assert seen_files == [handle]
        assert Path(handle.name) == tmp_path / "faulthandler.log"
    finally:
        if crash_handling._crash_log_handle is not None:
            crash_handling._crash_log_handle.close()
            crash_handling._crash_log_handle = None


def test_crash_handler_does_not_override_existing_handler(monkeypatch) -> None:
    from nomad_camels.utility import crash_handling

    monkeypatch.setattr(crash_handling.faulthandler, "is_enabled", lambda: True)

    def should_not_be_called(**kwargs):
        raise AssertionError("Existing faulthandler must not be replaced")

    monkeypatch.setattr(crash_handling.faulthandler, "enable", should_not_be_called)
    crash_handling.configure_fault_handler()



def test_windows_zmq_dispatcher_uses_selector_loop(monkeypatch) -> None:
    """Windows requires a selector event loop, without a global policy change."""
    import asyncio

    from nomad_camels.bluesky_handling import zmq_dispatcher

    class DispatcherStub:
        def __init__(self, address, *, loop=None):
            self.address = address
            self.loop = loop

    monkeypatch.setattr(zmq_dispatcher, "RemoteDispatcher", DispatcherStub)
    monkeypatch.setattr(zmq_dispatcher.sys, "platform", "win32")

    dispatcher = zmq_dispatcher.create_remote_dispatcher("localhost:12345")
    try:
        assert dispatcher.address == "localhost:12345"
        assert isinstance(dispatcher.loop, asyncio.SelectorEventLoop)
    finally:
        dispatcher.loop.close()


def test_non_windows_zmq_dispatcher_keeps_default_loop(monkeypatch) -> None:
    """Other platforms leave loop selection to Bluesky as before."""
    from nomad_camels.bluesky_handling import zmq_dispatcher

    kwargs_received = []

    def fake_remote_dispatcher(address, **kwargs):
        kwargs_received.append(kwargs)
        return address

    monkeypatch.setattr(zmq_dispatcher, "RemoteDispatcher", fake_remote_dispatcher)
    monkeypatch.setattr(zmq_dispatcher.sys, "platform", "linux")
    assert zmq_dispatcher.create_remote_dispatcher("localhost:12345") == "localhost:12345"
    assert kwargs_received == [{}]


def test_generated_protocol_does_not_set_global_asyncio_policy() -> None:
    from nomad_camels.bluesky_handling.protocol_builder import standard_start_string

    assert "create_remote_dispatcher" in standard_start_string
    assert "set_event_loop_policy" not in standard_start_string
