"""Python 3.14 multiprocessing startup and failure-path regression tests."""

from __future__ import annotations

import multiprocessing
from queue import Empty
import sys
import time

import pytest

from nomad_camels.main_classes.plot_proxy import start_zmq_proxy
from nomad_camels.utility.process_handling import (
    terminate_process,
    wait_for_process_event,
)


class _FakeQueue:
    def __init__(self, response=None):
        self.response = response
        self.closed = False

    def get(self, timeout):
        if self.response is None:
            time.sleep(timeout)
            raise Empty
        return self.response

    def close(self):
        self.closed = True

    def join_thread(self):
        pass


class _FakeProcess:
    def __init__(self, *, alive=True, exitcode=None, **kwargs):
        self.alive = alive
        self.exitcode = exitcode
        self.terminated = False
        self.started = False

    def start(self):
        self.started = True

    def is_alive(self):
        return self.alive

    def terminate(self):
        self.terminated = True
        self.alive = False
        self.exitcode = -15

    def join(self, timeout=None):
        pass

    def kill(self):
        self.terminate()


class _FakeContext:
    def __init__(self, *, alive, exitcode=None, response=None):
        self.queue = _FakeQueue(response)
        self.process = _FakeProcess(alive=alive, exitcode=exitcode)

    def Queue(self):
        return self.queue

    def Process(self, **kwargs):
        return self.process


def test_zmq_proxy_exits_before_reporting_ports():
    context = _FakeContext(alive=False, exitcode=42)
    with pytest.raises(RuntimeError, match="exit code 42"):
        start_zmq_proxy(context=context, timeout=0.1)
    assert context.queue.closed


def test_zmq_proxy_never_reports_ports():
    context = _FakeContext(alive=True)
    with pytest.raises(TimeoutError, match="did not report listening ports"):
        start_zmq_proxy(context=context, timeout=0.03)
    assert context.process.terminated
    assert context.queue.closed


def test_zmq_proxy_rejects_invalid_ports():
    context = _FakeContext(alive=True, response=(0, 70000))
    with pytest.raises(RuntimeError, match="invalid listening ports"):
        start_zmq_proxy(context=context, timeout=0.1)
    assert context.process.terminated
    assert context.queue.closed


def test_wait_for_process_event_detects_crash():
    process = _FakeProcess(alive=False, exitcode=17)
    event = type("NoSignal", (), {"wait": lambda self, timeout: False})()
    with pytest.raises(RuntimeError, match="exit code 17"):
        wait_for_process_event(process, event, timeout=0.1, name="Dash plot")


def test_wait_for_process_event_times_out():
    process = _FakeProcess(alive=True)
    event = type("NoSignal", (), {"wait": lambda self, timeout: False})()
    with pytest.raises(TimeoutError, match="Dash plot did not signal"):
        wait_for_process_event(process, event, timeout=0.01, name="Dash plot")


def test_zmq_proxy_starts_with_python314_process_context():
    """Actually launch a proxy using Linux forkserver or Windows/macOS spawn."""
    method = "forkserver" if sys.platform.startswith("linux") else "spawn"
    if method not in multiprocessing.get_all_start_methods():
        pytest.skip(f"Multiprocessing method {method} unavailable")
    ctx = multiprocessing.get_context(method)
    process, in_port, out_port = start_zmq_proxy(context=ctx, timeout=20)
    try:
        assert 0 < in_port <= 65535
        assert 0 < out_port <= 65535
        assert in_port != out_port
        assert process.is_alive()
    finally:
        terminate_process(process)
    assert not process.is_alive()


def test_generated_protocol_waits_for_proxy_ports_safely():
    from nomad_camels.bluesky_handling.protocol_builder import standard_start_string

    assert "proxy_proc, in_port, out_port = start_zmq_proxy()" in standard_start_string
    assert "port_queue.get()" not in standard_start_string
