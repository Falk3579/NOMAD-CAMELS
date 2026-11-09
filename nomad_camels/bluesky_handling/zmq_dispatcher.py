"""Construct a Bluesky RemoteDispatcher with an explicit Windows event loop.

Python 3.14 deprecates the process-wide asyncio policy API. PyZMQ's asyncio
integration needs a selector loop on Windows, so pass that loop to Bluesky
rather than changing the policy for unrelated application components.
"""

from __future__ import annotations

import asyncio
import sys

from bluesky.callbacks.zmq import RemoteDispatcher


def create_remote_dispatcher(address: str) -> RemoteDispatcher:
    """Return a dispatcher using the appropriate loop for ZMQ on this OS."""
    if sys.platform == "win32":
        return RemoteDispatcher(address, loop=asyncio.SelectorEventLoop())
    return RemoteDispatcher(address)
