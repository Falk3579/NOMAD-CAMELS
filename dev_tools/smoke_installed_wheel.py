"""Smoke-test the installed Hatchling wheel, isolated from the source checkout.

Usage:
    uv build --wheel
    python dev_tools/smoke_installed_wheel.py

The script creates a temporary Python environment, installs the wheel with its
runtime dependencies, and runs the GUI checks from outside the repository.
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


REPOSITORY = Path(__file__).resolve().parents[1]

# Executed by the new environment's Python with -I (isolated mode) and a
# working directory outside the repository. Never import from the checkout.
INSTALLED_PROBE = """
from importlib import metadata, resources
from pathlib import Path
import sys

import nomad_camels
from PySide6.QtCore import QFile
from PySide6.QtGui import QFontDatabase, QPixmap
from PySide6.QtWidgets import QApplication, QDialog, QMainWindow

# Some imported GUI modules initialize Qt themselves. Create the application
# before importing the application's modules, and always reuse any instance.
app = QApplication.instance()
if app is None:
    app = QApplication([])

installed_root = Path(sys.prefix).resolve()
module_file = Path(nomad_camels.__file__).resolve()
assert module_file.is_relative_to(installed_root), (
    f'Package came from {module_file}, not the isolated environment {installed_root}'
)

distribution = metadata.distribution('nomad-camels')
assert any(
    entry.name == 'nomad-camels'
    and entry.group == 'gui_scripts'
    and entry.value == 'nomad_camels:start_camels'
    for entry in distribution.entry_points
), 'Hatchling wheel is missing the GUI entry point'

gui = resources.files('nomad_camels.gui')
graphics = resources.files('nomad_camels.graphics')
for filename in ('mainWindow_v2.ui', 'settings_window.ui',
                 'settings_window_resource_rc.py', 'dynamicuploadcombobox.py'):
    assert (gui / filename).is_file(), f'Missing packaged Qt asset: {filename}'
for filename in ('CAMELS_Icon.png', 'dark.qss', 'copy_to_clipboard.svg'):
    assert (graphics / filename).is_file(), f'Missing packaged graphic: {filename}'

from nomad_camels import start_camels
from nomad_camels.MainApp_v2 import MainWindow
from nomad_camels.gui.mainWindow_v2 import Ui_MainWindow
from nomad_camels.gui.settings_window import Ui_settings_window

assert callable(start_camels) and issubclass(MainWindow, QMainWindow)

assert QFontDatabase.families(), 'Qt could not find any system fonts'
assert not QPixmap(str(graphics / 'CAMELS_Icon.png')).isNull(), (
    'Qt could not load the packaged application icon'
)
window = QMainWindow()
Ui_MainWindow().setupUi(window)
dialog = QDialog()
Ui_settings_window().setupUi(dialog)
assert QFile(':/images/graphics/copy_to_clipboard.svg').exists(), (
    'Compiled Qt resource for settings window was not registered'
)
app.processEvents()
dialog.close()
window.close()
print(f'Installed wheel smoke test passed: {distribution.version} ({module_file})')
"""

# A separate subprocess exercises a first GUI launch with the installed
# nomad_camels directory read-only. The custom configuration directory and
# startup cache must be created outside site-packages.
READ_ONLY_CONFIG_PROBE = """
from pathlib import Path
import os
import stat

import nomad_camels
from nomad_camels.utility import user_paths

package = Path(nomad_camels.__file__).resolve().parent
expected_root = Path(os.environ['NOMAD_CAMELS_SMOKE_CONFIG_ROOT'])
selected = Path(os.environ['NOMAD_CAMELS_SMOKE_CUSTOM_CONFIG'])
assert user_paths.user_config_root() == expected_root
assert not expected_root.exists()
assert not selected.exists()

# Preserve the original permissions for temporary-environment cleanup.
permissions = []
for target in sorted(package.rglob('*'), key=lambda p: len(p.parts), reverse=True):
    if not target.is_symlink():
        mode = stat.S_IMODE(target.stat().st_mode)
        permissions.append((target, mode))
        target.chmod(mode & ~0o222)
mode = stat.S_IMODE(package.stat().st_mode)
permissions.append((package, mode))
package.chmod(mode & ~0o222)

try:
    from nomad_camels.ui_widgets import path_button_edit
    from nomad_camels.utility import update_camels

    class AutoChoosePath:
        def __init__(self, *, title='', path='', **kwargs):
            if title == 'Select path for configuration files':
                self.path = str(selected)
            else:
                self.path = str(expected_root / 'measurements')

        def exec(self):
            return True

    path_button_edit.Path_Button_Dialog = AutoChoosePath
    update_camels.show_release_notes = lambda: None

    from nomad_camels.CAMELS_start import start_camels

    window = start_camels(start_proxy_bool=False, actually_exec=False)
    try:
        assert window.isVisible(), 'Full first-run GUI did not open'
        assert (expected_root / 'config_path').read_text(encoding='utf-8') == str(selected)
        assert (expected_root / 'startup_packages.txt').is_file()
        assert (selected / 'preferences.json').is_file()
        assert not (package / 'config_path').exists(), 'Config pointer written inside package'
        assert not (package / 'startup_packages.txt').exists(), 'Startup cache written inside package'
        print('Read-only installed-wheel first-launch smoke test passed')
    finally:
        window.close()
finally:
    # Restore parent directories before their children, including on Windows.
    for target, mode in reversed(permissions):
        target.chmod(mode)
"""



def run(command: list[str], cwd: Path, *, environment: dict[str, str] | None = None) -> None:
    """Run a checked command outside the repository, with visible output."""
    print("+", " ".join(command), flush=True)
    subprocess.run(
        command,
        check=True,
        cwd=cwd,
        env=environment,
        timeout=600,
    )


def main() -> None:
    """Install the built wheel into a fresh environment and test its GUI imports."""
    wheels = sorted((REPOSITORY / "dist").glob("nomad_camels-*.whl"))
    if len(wheels) != 1:
        raise SystemExit(
            f"Expected exactly one built wheel in dist/, found {len(wheels)}. "
            "Run 'uv build --wheel' in a clean dist/ directory."
        )
    uv = shutil.which("uv")
    if uv is None:
        raise SystemExit("uv must be installed and available on PATH.")

    with tempfile.TemporaryDirectory(prefix="nomad-camels-wheel-") as directory:
        outside = Path(directory).resolve()
        venv = outside / "venv"
        run([uv, "venv", "--python", sys.executable, str(venv)], outside)
        interpreter = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        assert interpreter.is_file(), f"Python executable missing: {interpreter}"

        # No --no-deps and no editable installation: this checks real wheel
        # metadata and whether a new user can resolve all runtime dependencies.
        run([uv, "pip", "install", "--python", str(interpreter), str(wheels[0].resolve())], outside)

        # A GUI script is generated by the installer, but must not be executed
        # here: it would start the interactive application event loop.
        entrypoint = interpreter.parent / ("nomad-camels.exe" if os.name == "nt" else "nomad-camels")
        assert entrypoint.is_file(), f"Installed GUI entry point missing: {entrypoint}"

        environment = os.environ.copy()
        environment.pop("PYTHONPATH", None)
        # Windows' native Qt platform plugin uses the Windows font system.
        # Forcing the offscreen plugin on Windows makes Qt search for
        # PySide6/lib/fonts (a directory no longer shipped by Qt).
        # Linux CI uses the offscreen plugin with system fontconfig.
        environment["QT_QPA_PLATFORM"] = "windows" if os.name == "nt" else "offscreen"
        environment["PYTHONNOUSERSITE"] = "1"
        run([str(interpreter), "-I", "-c", INSTALLED_PROBE], outside, environment=environment)

        # Test the actual first GUI launch (including config-path initialization)
        # from a non-editable wheel without touching the real user's settings.
        if os.name == "nt":
            config_root = outside / "LocalAppData" / "nomad_camels"
            environment["LOCALAPPDATA"] = str(config_root.parent)
        else:
            config_root = outside / "xdg-config" / "nomad_camels"
            environment["XDG_CONFIG_HOME"] = str(config_root.parent)
        environment["NOMAD_CAMELS_SMOKE_CONFIG_ROOT"] = str(config_root)
        environment["NOMAD_CAMELS_SMOKE_CUSTOM_CONFIG"] = str(outside / "custom-config")
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        run(
            [str(interpreter), "-I", "-c", READ_ONLY_CONFIG_PROBE],
            outside,
            environment=environment,
        )


if __name__ == "__main__":
    main()
