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



def test_http_health_check_waits_for_actual_response(monkeypatch):
    from nomad_camels.utility.process_handling import wait_for_http_service
    import requests

    seen_urls = []

    def get(url, **kwargs):
        seen_urls.append(url)
        return type("Ok", (), {"status_code": 200})()

    monkeypatch.setattr(requests, "get", get)
    wait_for_http_service(
        _FakeProcess(alive=True), "http://127.0.0.1:12345/status", timeout=0.1
    )
    assert seen_urls == ["http://127.0.0.1:12345/status"]


def test_http_health_check_notices_child_exit():
    from nomad_camels.utility.process_handling import wait_for_http_service

    with pytest.raises(RuntimeError, match="exit code 7"):
        wait_for_http_service(
            _FakeProcess(alive=False, exitcode=7),
            "http://127.0.0.1:12345/status",
            timeout=0.1,
        )


def test_http_health_check_times_out(monkeypatch):
    from nomad_camels.utility.process_handling import wait_for_http_service
    import requests

    def offline(*args, **kwargs):
        raise requests.ConnectionError("server not ready")

    monkeypatch.setattr(requests, "get", offline)
    with pytest.raises(TimeoutError, match="did not respond"):
        wait_for_http_service(
            _FakeProcess(alive=True),
            "http://127.0.0.1:12345/status",
            timeout=0.03,
            name="Dash test",
        )


def test_dash_startup_checks_http_after_process_event(monkeypatch):
    """The child sends its event before Dash binds its HTTP socket."""
    from nomad_camels.main_classes import plot_plotly

    calls = []
    monkeypatch.setattr(
        plot_plotly,
        "wait_for_process_event",
        lambda *args, **kwargs: calls.append("event"),
    )
    monkeypatch.setattr(
        plot_plotly,
        "wait_for_http_service",
        lambda *args, **kwargs: calls.append(("http", args[1])),
    )
    plot_plotly._wait_for_dash_startup(
        _FakeProcess(alive=True), object(), 45678, timeout=1.0
    )
    assert calls == ["event", ("http", "http://127.0.0.1:45678/status")]
