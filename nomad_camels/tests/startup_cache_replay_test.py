"""Regression test: startup does not replay the legacy imported-module cache."""

import sys
from unittest.mock import patch

from PySide6.QtWidgets import QWidget

from nomad_camels import MainApp_v2
from nomad_camels.CAMELS_start import start_camels
from nomad_camels.utility import user_paths


def test_startup_does_not_touch_cached_modules(qtbot, monkeypatch, tmp_path):
    """An old cache must not import extra packages or be overwritten on launch."""
    cache_file = tmp_path / "startup_packages.txt"
    cache_file.write_text("not_an_installed_package\n", encoding="utf-8")
    monkeypatch.setattr(user_paths, "startup_cache_file", lambda: cache_file)
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)

    class BareWindow(QWidget):
        def __init__(self, start_proxy_bool):
            super().__init__()
            assert start_proxy_bool is False

    with (
        patch.object(MainApp_v2, "MainWindow", BareWindow),
        patch.object(user_paths, "read_startup_packages", side_effect=AssertionError("unexpected cache read")),
        patch.object(user_paths, "write_startup_packages", side_effect=AssertionError("unexpected cache write")),
    ):
        window = start_camels(start_proxy_bool=False, actually_exec=False)
        try:
            assert isinstance(window, BareWindow)
            assert window.isVisible()
            assert cache_file.read_text(encoding="utf-8") == "not_an_installed_package\n"
        finally:
            window.close()
