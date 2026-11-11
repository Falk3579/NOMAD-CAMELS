import pytest
from unittest.mock import patch, Mock
import tempfile
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication
import sys
import os
import subprocess
from nomad_camels.MainApp_v2 import MainWindow
from nomad_camels.CAMELS_start import start_camels, LoadingScreen


class MockDialog:
    def __init__(self, *args, **kwargs):
        # Create a temporary directory for the test
        self.path = tempfile.mkdtemp()

    def exec(self):
        return True


@pytest.mark.order(1)
@pytest.mark.skipif(
    not sys.platform.startswith("win"), reason="pythonw test only runs on Windows"
)
def test_start_camels_with_pythonw():
    import shutil

    pythonw = shutil.which("pythonw")
    assert pythonw, "pythonw not found in PATH on Windows"

    # pythonw has no visible stderr. Record a traceback for failed startup
    # so CI can diagnose Python GUI-launcher failures rather than an exit code.
    with tempfile.TemporaryDirectory(prefix="nomad-camels-pythonw-") as directory:
        error_path = os.path.join(directory, "startup-error.txt")
        cmd = (
            "import traceback\n"
            "try:\n"
            "    from nomad_camels.CAMELS_start import start_camels\n"
            "    start_camels(start_proxy_bool=False, actually_exec=False)\n"
            "except BaseException:\n"
            f"    with open({error_path!r}, 'w', encoding='utf-8') as log:\n"
            "        log.write(traceback.format_exc())\n"
            "    raise\n"
        )
        proc = subprocess.run([pythonw, "-c", cmd], timeout=50, check=False)
        error_message = ""
        if os.path.isfile(error_path):
            with open(error_path, encoding="utf-8") as log:
                error_message = log.read()
        assert proc.returncode in [0, 3221226505], (
            f"pythonw startup exited with {proc.returncode}:\n{error_message}"
        )
    # if proc.returncode != 0:
    #     # assert proc.returncode == 0

    #     # If the return code is nonzero because of missing optional drivers,
    #     # skip the test instead of failing.
    #     driver_errors = [
    #         "could not load package",
    #         "Could not find module",
    #         "No module named",
    #         "It seems you have not installed",
    #         "Make sure it is installed",
    #         "warnings.warn(",
    #     ]
    #     # Split stdout and stderr into individual lines.
    #     err_lines = proc.stderr.splitlines()
    #     # Filter out lines that are expected driver errors.
    #     unexpected_lines = []
    #     for line in err_lines:
    #         if not any(driver_msg in line for driver_msg in driver_errors):
    #             unexpected_lines.append(line)
    #     if unexpected_lines:
    #         # check if all unexpected_lines are empty strings
    #         unexpected_lines = [line for line in unexpected_lines if line.strip()]
    #     if unexpected_lines:
    #         failure_text = "\n".join(unexpected_lines)
    #         pytest.fail(f"pythonw run failed with unexpected errors:\n{failure_text}")
    #     # If all error lines match expected driver errors, the test passes.


@pytest.mark.order(0)
def test_start_camels(qtbot, capfd):
    """Test the startup of the CAMELS application."""

    def close_save_message():
        """ """
        main_window.close()
        out, err = capfd.readouterr()
        app = QApplication.instance()
        app.processEvents()
        assert "current state saved!" in out

    with patch(
        "nomad_camels.ui_widgets.path_button_edit.Path_Button_Dialog", new=MockDialog
    ):
        with patch("nomad_camels.CAMELS_start.QApplication.exec", return_value=None):
            with patch(
                "nomad_camels.utility.update_camels.show_release_notes",
                return_value=None,
            ):

                # Start the CAMELS application
                app = QCoreApplication.instance()
                if app is not None:
                    app.quit()
                    del app
                start_camels(start_proxy_bool=False)
                app = QApplication.instance()

                # Check if the main window is displayed
                app.processEvents()
                main_window = None
                widgets = app.topLevelWidgets()
                for widget in widgets:
                    if isinstance(widget, MainWindow):
                        main_window = widget
                        break
                assert main_window is not None
                assert (
                    main_window.windowTitle()
                    == "NOMAD CAMELS - Configurable Application for Measurements, Experiments and Laboratory-Systems"
                )
                try:
                    qtbot.waitUntil(close_save_message)
                except TimeoutError:
                    pass

                # Ensure the main window is closed properly
                main_window.close()
                app.processEvents()
                qtbot.waitUntil(lambda: not main_window.isVisible())


@pytest.mark.order(1)
def test_start_camels_second_start():
    """Test the startup of the CAMELS application a second time."""
    window = start_camels(start_proxy_bool=False, actually_exec=False)
    assert isinstance(window, MainWindow)


@pytest.fixture(scope="module")
def app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
    if app is not None:
        app.quit()


@pytest.fixture
def instance(app):
    return LoadingScreen()


@pytest.mark.order(0)
def test_set_progress(instance):
    # LoadingScreen defaults to an indeterminate bar during application startup.
    instance.progress_bar.setRange(0, 100)
    instance.set_progress(50)
    assert instance.progress_bar.value() == 50


def test_startup_progress_is_indeterminate(instance):
    assert instance.progress_bar.minimum() == 0
    assert instance.progress_bar.maximum() == 0


@pytest.mark.order(0)
def test_set_text(instance):
    test_text = "Test text"
    instance.set_text(test_text)
    assert instance.label.text() == test_text


@pytest.mark.order(0)
def test_import_thread(qtbot):
    """Test the ImportThread class."""
    from CAMELS_start import ImportThread

    # Mock the package list and other dependencies
    package_list = ["os", "sys", "nonexistent_package", "sys.bad_test_attribute"]
    loading_screen = Mock()
    loading_screen.set_progress = Mock()
    loading_screen.set_text = Mock()

    # Create an instance of ImportThread
    thread = ImportThread(package_list=package_list)

    # Connect signals to slots
    thread.update_progress.connect(loading_screen.set_progress)
    thread.update_text.connect(loading_screen.set_text)

    # Start the thread
    thread.run()

    # Wait for the thread to finish
    qtbot.waitUntil(lambda: not thread.isRunning(), timeout=5000)

    # Check if the signals were emitted correctly
    loading_screen.set_progress.assert_called()
    loading_screen.set_text.assert_called()

    # Ensure the thread has finished
    assert not thread.isRunning()
    thread.quit()
    thread.wait()
    thread.deleteLater()
