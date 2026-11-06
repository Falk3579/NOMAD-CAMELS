"""Hardware-free Python 3.14 integration probes.

Run as independent processes:
    python dev_tools/python314_runtime_smoke.py gui
    python dev_tools/python314_runtime_smoke.py zmq
    python dev_tools/python314_runtime_smoke.py hdf5

Each case raises an exception on failure. These are intentionally small CI
smoke tests, not a substitute for the full CAMELS test suite.
"""

from __future__ import annotations

import argparse
import asyncio
import multiprocessing
import os
from pathlib import Path
import queue
import sys
import tempfile
import threading
import time
from unittest.mock import patch


def simulated_run(run_engine, *, subscriber=None):
    """Exercise CAMELS' RunEngine subclass without instrument drivers."""
    from bluesky.plans import count
    from ophyd import Signal

    if subscriber is not None:
        run_engine.subscribe(subscriber)
    detector = Signal(value=42.0, name="camels_python314_sim")
    auxiliary = Signal(value=84.0, name="camels_python314_aux")
    # Bluesky 1.16 sends both readables in a single read message.
    return run_engine(count([detector, auxiliary], num=2, delay=0.01))


def smoke_gui():
    """Exercise the real Qt main window, its proxy, and clean shutdown."""
    import json

    from PySide6.QtWidgets import QApplication

    from nomad_camels.MainApp_v2 import MainWindow
    from nomad_camels.utility import load_save_functions

    # First launch normally asks the user to select a data directory. This
    # is an intentional modal dialog, not a Python 3.14 compatibility error.
    # Seed isolated preferences so unattended CI does not wait for a click.
    preferences_dir = Path(load_save_functions.appdata_path)
    preferences_dir.mkdir(parents=True, exist_ok=True)
    preferences = dict(load_save_functions.standard_pref)
    preferences.update(
        auto_check_updates=False,
        autosave=False,
        password_protection=False,
    )
    (preferences_dir / "preferences.json").write_text(
        json.dumps(preferences), encoding="utf-8"
    )

    app = QApplication.instance() or QApplication([])
    old_stdout, old_stderr = sys.stdout, sys.stderr
    window = None

    def fail_on_unexpected_dialog(*args, **kwargs):
        raise RuntimeError(
            f"Unexpected modal warning during CI GUI smoke: {args!r}, {kwargs!r}"
        )

    try:
        with (
            patch("nomad_camels.utility.update_camels.show_release_notes"),
            patch("nomad_camels.utility.update_camels.auto_update"),
            # check_config_path normally launches a second first-run modal
            # configuration-directory dialog even when preferences exist.
            patch("nomad_camels.utility.load_save_functions.check_config_path"),
            patch(
                "nomad_camels.MainApp_v2.warn_popup.WarnPopup",
                side_effect=fail_on_unexpected_dialog,
            ),
        ):
            window = MainWindow(start_proxy_bool=True)
        window.show()
        app.processEvents()
        assert window.isVisible(), "Main window did not become visible"
        assert "NOMAD CAMELS" in window.windowTitle()
        assert not window.pushButton_pause.icon().isNull()

        # Qt must not destroy a QThread that is still importing modules.
        if hasattr(window, "importer_thread"):
            assert window.importer_thread.wait(15000), "Background imports did not finish"

        window.close()
        app.processEvents()
        assert not window.isVisible(), "GUI close was ignored"
        assert not window.proxy_proc.is_alive(), "GUI left the ZeroMQ proxy running"
        assert not window.dispatcher_thread.is_alive(), "GUI left the dispatcher thread running"
    finally:
        # MainWindow redirects the process streams into its Qt log widget.
        sys.stdout, sys.stderr = old_stdout, old_stderr
        if window is not None and window.isVisible():
            window.close()
    print("PASS: Qt GUI opens, initializes ZMQ, and closes without orphan threads/processes")


def smoke_zmq():
    """RunEngine -> Publisher -> CAMELS proxy -> RemoteDispatcher."""
    from bluesky.callbacks.zmq import Publisher, RemoteDispatcher

    from nomad_camels.bluesky_handling.run_engine_overwrite import RunEngineOverwrite
    from nomad_camels.main_classes.plot_proxy import run_zmq_proxy, run_remote_dispatcher

    context = multiprocessing.get_context()
    port_queue = context.Queue()
    proxy = context.Process(target=run_zmq_proxy, args=(port_queue,), daemon=True)
    publisher = None
    dispatcher = None
    dispatcher_thread = None
    callback_errors = []
    received = []
    stop_seen = threading.Event()

    try:
        proxy.start()
        try:
            in_port, out_port = port_queue.get(timeout=15)
        except queue.Empty as exc:
            raise AssertionError("CAMELS proxy did not return its ports") from exc

        publisher = Publisher(f"127.0.0.1:{in_port}")
        dispatcher = RemoteDispatcher(
            f"127.0.0.1:{out_port}",
            loop=asyncio.SelectorEventLoop() if sys.platform == "win32" else None,
        )

        def collect(name, document):
            received.append((name, document))
            if name == "stop":
                stop_seen.set()

        dispatcher.subscribe(collect)

        def dispatch():
            try:
                run_remote_dispatcher(dispatcher)
            except BaseException as exc:
                callback_errors.append(repr(exc))

        dispatcher_thread = threading.Thread(target=dispatch, daemon=True)
        dispatcher_thread.start()
        # Do not read the dispatcher loop's private running state from the
        # parent thread: the worker may already be polling despite that
        # cross-thread readiness check reading false on CPython 3.14.
        # Validate delivery of actual documents instead.
        assert dispatcher_thread.is_alive(), (
            f"RemoteDispatcher worker exited early: {callback_errors!r}"
        )
        # PUB/SUB has no handshake: permit the subscriber to attach.
        time.sleep(1.0)
        run_engine = RunEngineOverwrite({})
        simulated_run(run_engine, subscriber=publisher)
        if not stop_seen.wait(timeout=15):
            import faulthandler

            faulthandler.dump_traceback(file=sys.stderr)
            raise AssertionError(
                "No stop document received; "
                f"names={[name for name, _ in received]!r}, "
                f"worker_alive={dispatcher_thread.is_alive()}, "
                f"dispatcher_errors={callback_errors!r}"
            )
        names = [name for name, _ in received]
        assert names.count("start") == 1, names
        assert "descriptor" in names, names
        assert names.count("event") == 2, names
        assert names.count("stop") == 1, names
    finally:
        if dispatcher is not None and dispatcher_thread is not None:
            if dispatcher.loop.is_running():
                # Upstream Bluesky's stop() is designed for another thread.
                dispatcher.stop()
            dispatcher_thread.join(timeout=8)
        if publisher is not None:
            publisher.close()
        if proxy.is_alive():
            proxy.terminate()
        proxy.join(timeout=8)
        port_queue.close()
        port_queue.join_thread()

    assert not proxy.is_alive(), "CAMELS proxy process did not exit"
    assert dispatcher_thread is not None and not dispatcher_thread.is_alive(), (
        "RemoteDispatcher thread did not exit"
    )
    assert not callback_errors, f"RemoteDispatcher raised: {callback_errors}"
    print("PASS: Bluesky run documents crossed the CAMELS ZMQ proxy and all workers exited")


def smoke_hdf5(directory: Path):
    """Export simulated Bluesky documents through the CAMELS HDF5 suitcase."""
    import databroker
    import h5py

    from nomad_camels.bluesky_handling.helper_functions import export_function
    from nomad_camels.bluesky_handling.run_engine_overwrite import RunEngineOverwrite

    broker = databroker.temp().v2
    engine = RunEngineOverwrite({})
    engine.subscribe(broker.v1.insert)
    start_uids = []

    def collect_uid(name, document):
        if name == "start":
            start_uids.append(document["uid"])

    simulated_run(engine, subscriber=collect_uid)
    assert len(start_uids) == 1, start_uids
    run = broker[start_uids[0]]
    save_prefix = directory / "python314_roundtrip"
    export_function(
        run,
        str(save_prefix),
        True,
        new_file_each=False,
        do_nexus_output=False,
    )
    outputs = sorted(directory.glob("python314_roundtrip*.h5"))
    assert outputs, "CAMELS suitcase did not produce an HDF5 file"
    datasets = []

    with h5py.File(outputs[0], "r") as h5file:
        def visit(name, value):
            if isinstance(value, h5py.Dataset):
                datasets.append((name, value.shape))

        h5file.visititems(visit)

    assert datasets, "HDF5 output contains no datasets"
    assert len(list(run.documents(fill="yes"))) >= 4, "Simulated run documents unavailable on reopen"
    print(f"PASS: CAMELS HDF5 export/reopen ({outputs[0].name}, {len(datasets)} datasets)")


def smoke_generated():
    """Verify standalone script templates no longer use the removed policy API."""
    from nomad_camels.bluesky_handling import protocol_builder

    text = protocol_builder.standard_start_string
    assert "set_event_loop_policy" not in text
    assert "SelectorEventLoop()" in text
    assert "port_queue.get(timeout=15)" in text
    print("PASS: standalone protocol ZMQ template avoids global asyncio policy")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("case", choices=("gui", "zmq", "hdf5", "generated"))
    args = parser.parse_args()
    # Avoid using a developer's stored presets on CI. Define these before
    # importing CAMELS because path selection happens during module import.
    with tempfile.TemporaryDirectory(prefix="camels-python314-") as root:
        root_path = Path(root)
        for name, child in (
            ("XDG_CONFIG_HOME", "config"),
            ("XDG_DATA_HOME", "data"),
            ("LOCALAPPDATA", "local"),
            ("USERPROFILE", "user"),
        ):
            target = root_path / child
            target.mkdir(parents=True, exist_ok=True)
            os.environ[name] = str(target)
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        if args.case == "gui":
            # If a Qt modal dialog blocks CI, retain a useful Python stack
            # instead of reporting only the outer subprocess timeout.
            import faulthandler

            faulthandler.dump_traceback_later(25, repeat=True)
            try:
                smoke_gui()
            finally:
                faulthandler.cancel_dump_traceback_later()
        elif args.case == "zmq":
            smoke_zmq()
        elif args.case == "hdf5":
            smoke_hdf5(root_path)
        elif args.case == "generated":
            smoke_generated()


if __name__ == "__main__":
    main()
