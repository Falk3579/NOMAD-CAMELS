"""Verify a built NOMAD-CAMELS wheel in a clean CPython 3.14 virtualenv.

This deliberately starts from a new venv and runs in a directory outside the
checkout, so importing from the source tree (or an editable install) cannot
silently satisfy the check. Only hardware-free GUI and HDF5 tests are run.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import venv


def run(command: list[str], *, cwd: Path, environment: dict[str, str], timeout=300):
    print("RUN:", " ".join(command), flush=True)
    subprocess.run(
        command,
        check=True,
        cwd=str(cwd),
        env=environment,
        timeout=timeout,
    )


def main():
    if sys.version_info[:2] != (3, 14):
        raise RuntimeError(f"Requires CPython 3.14, got {sys.version}")

    checkout = Path(__file__).resolve().parent.parent
    wheels = sorted((checkout / "dist").glob("nomad_camels-*.whl"))
    if len(wheels) != 1:
        raise RuntimeError(f"Expected exactly one built NOMAD-CAMELS wheel: {wheels}")

    with tempfile.TemporaryDirectory(prefix="camels-314-wheel-") as tmp:
        root = Path(tmp).resolve()
        venv_path = root / "environment"
        print(f"Creating isolated virtual environment: {venv_path}", flush=True)
        venv.EnvBuilder(with_pip=True).create(venv_path)

        py = (
            venv_path / "Scripts" / "python.exe"
            if os.name == "nt"
            else venv_path / "bin" / "python"
        )
        if not py.is_file():
            raise AssertionError(f"Cannot find venv interpreter: {py}")

        environment = os.environ.copy()
        environment.pop("PYTHONPATH", None)
        environment["PYTHONNOUSERSITE"] = "1"
        environment["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
        environment.setdefault("QT_QPA_PLATFORM", "offscreen")
        external_cwd = root / "outside-checkout"
        external_cwd.mkdir()

        # Some Databroker transitive dependencies ship sdists only (PIMS 0.7).
        # Install from our built wheel and allow those dependencies to build;
        # avoid implicitly installing CAMELS in editable mode.
        run(
            [str(py), "-m", "pip", "install", str(wheels[0])],
            cwd=external_cwd,
            environment=environment,
            timeout=600,
        )
        run(
            [str(py), "-m", "pip", "check"],
            cwd=external_cwd,
            environment=environment,
        )

        # -I and cwd outside checkout prevent importing a local source copy.
        code = (
            "from pathlib import Path; import sys; import nomad_camels; "
            "from nomad_camels import graphics; "
            "from importlib.resources import files; "
            "package = Path(nomad_camels.__file__).resolve(); "
            "prefix = Path(sys.prefix).resolve(); "
            "assert prefix in package.parents, (prefix, package); "
            "assets = ['CAMELS_Icon.png', 'CAMELS_vertical.png', 'CAMELS_horizontal.png']; "
            "assert all((files(graphics) / name).is_file() for name in assets), assets; "
            "print('PASS: wheel installed in isolated venv with GUI resources:', package)"
        )
        run(
            [str(py), "-I", "-c", code],
            cwd=external_cwd,
            environment=environment,
        )
        runner = checkout / "dev_tools" / "run_python314_smoke.py"
        for smoke in ("hdf5", "gui"):
            run(
                [str(py), "-u", str(runner), smoke, "120"],
                cwd=external_cwd,
                environment=environment,
                timeout=150,
            )

    print("PASS: clean wheel install, resources, HDF5 export, and Qt startup/close", flush=True)


if __name__ == "__main__":
    main()
