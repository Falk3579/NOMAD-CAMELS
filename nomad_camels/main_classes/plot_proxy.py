"""Run the ZMQ forwarding proxy in a separate, monitored process."""

from __future__ import annotations

import multiprocessing
from multiprocessing.context import BaseContext
from queue import Empty
import time

import zmq

from nomad_camels.utility.process_handling import terminate_process


def run_zmq_proxy(queue: multiprocessing.Queue) -> None:
    """Bind two random TCP ports, publish them, then forward ZMQ traffic."""
    # Use a dedicated context in the child, including under the forkserver
    # default used by Python 3.14 on Linux.
    context = zmq.Context()
    frontend = context.socket(zmq.SUB)
    backend = context.socket(zmq.PUB)
    try:
        in_port = frontend.bind_to_random_port("tcp://*")
        out_port = backend.bind_to_random_port("tcp://*")
        frontend.setsockopt_string(zmq.SUBSCRIBE, "")
        queue.put((in_port, out_port))
        zmq.proxy(frontend, backend)
    finally:
        frontend.close(linger=0)
        backend.close(linger=0)
        context.term()


def start_zmq_proxy(
    *, timeout: float = 30.0, context: BaseContext | None = None
) -> tuple[multiprocessing.Process, int, int]:
    """Start a proxy and await its ports, with crash/timeout detection.

    The default multiprocessing context is intentionally not overridden:
    Python 3.14 uses forkserver on Linux and spawn on Windows/macOS.
    The caller owns the returned process and must terminate it on shutdown.
    """
    if timeout <= 0:
        raise ValueError("ZMQ proxy startup timeout must be positive")

    mp_context = context if context is not None else multiprocessing.get_context()
    port_queue = mp_context.Queue()
    process = mp_context.Process(target=run_zmq_proxy, args=(port_queue,), daemon=True)
    try:
        process.start()
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(
                    f"ZMQ proxy did not report listening ports within {timeout:g}s"
                )
            try:
                ports = port_queue.get(timeout=min(0.2, remaining))
            except Empty:
                if not process.is_alive():
                    raise RuntimeError(
                        "ZMQ proxy exited before reporting listening ports "
                        f"(exit code {process.exitcode})"
                    ) from None
                continue

            if (
                not isinstance(ports, tuple)
                or len(ports) != 2
                or any(type(port) is not int or not 1 <= port <= 65535 for port in ports)
            ):
                raise RuntimeError(f"ZMQ proxy reported invalid listening ports: {ports!r}")
            if not process.is_alive():
                raise RuntimeError(
                    f"ZMQ proxy exited during startup (exit code {process.exitcode})"
                )
            return process, ports[0], ports[1]
    except BaseException:
        terminate_process(process)
        raise
    finally:
        port_queue.close()
        port_queue.join_thread()
