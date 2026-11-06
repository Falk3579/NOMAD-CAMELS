# Python 3.14 packaging / dependency discovery log

**Branch:** `feature/python-3-14-support`  
**Scope:** First implementation checkpoint — CPython 3.14 metadata, resolver, import and build.  
**Not covered yet:** full application startup, simulated runs, real plots, API extras, hardware drivers, or installed-wheel resources.

## Changes made

- `pyproject.toml` now declares `requires-python = ">=3.14,<3.15"` and a 3.14 Trove classifier; older interpreters are no longer advertised.
- PySide6's old `<6.9` ceiling is replaced by `>=6.10.1,<6.13`.
- Obsolete version-specific alternatives for Python 3.9–3.13 have been removed.
- Preliminary minimums: `numpy>=2.3.3`, `pyyaml>=6.0.3`, `pyzmq>=27.0.1`, `setuptools>=80.9.0`, and optional `pytest>=9.0.0`.
- The old `requirements.txt`, min-version fixtures and main `ci.yml` **are not migrated yet**. They will be handled after confirming the install baseline; this branch is not release-ready.
- A temporary diagnostic workflow at `.github/workflows/python314-probe.yml` tests core installation on Windows, Linux and macOS and uploads resolver logs.

## Observations from the initial probe

Workflow: https://github.com/Falk3579/NOMAD-CAMELS/actions/runs/42242160099

| Platform | Core wheel-only dependency installation | `pip check` | `import nomad_camels` | Build wheel + sdist | Finding |
| --- | --- | --- | --- | --- | --- |
| Windows | PASS | PASS | PASS | PASS | Core dependency resolution and module import succeeded. |
| Ubuntu | PASS | PASS | FAIL | PASS | Import failed on missing OS Qt library `libEGL.so.1`, not a pip-resolution error. |
| macOS | Not available at time of initial report | — | — | — | Wait for CI job evidence; do not infer a result. |

The Ubuntu runner was then amended to install `libegl1`, `libopengl0`, `libgl1`, `libxkbcommon-x11-0` and `libpulse0` before attempting the import.

Updated workflow: https://github.com/Falk3579/NOMAD-CAMELS/actions/runs/42242433695

### Corrected probe results

The updated workflow (commit `adab6049f2dd5cfb86e8fc5a4daf8e979c4830a3`) completed **successfully on Ubuntu and Windows** for each core diagnostic check: wheel-only install, `pip check`, `import nomad_camels`, and wheel/sdist build. Ubuntu's original failure was fixed by installing Qt system libraries. macOS remained queued when these results were recorded, so it has no verified outcome yet.

**Important:** This establishes a Python 3.14 *installation/import/build baseline*, **not** GUI startup, simulated protocol execution, or HDF5 behavior. The linked Actions runs and diagnostic artifacts are the authoritative evidence.

### Concrete package versions observed on the initial Windows and Ubuntu installs

These versions were selected by pip on Python 3.14 at the time of the initial probe. They are **not** finalized minimum versions.

| Dependency | Resolved version |
| --- | --- |
| PySide6 | 6.12.0 |
| NumPy | 2.5.4 |
| PyYAML | 6.0.3 |
| PyZMQ | 27.3.0 |
| Bluesky | 1.16.0 |
| Ophyd | 1.11.2 |
| Databroker | 1.2.5 |
| suitcase-nomad-camels-hdf5 | 1.3.2 |
| matplotlib | 3.11.2 |
| pyqtgraph | 0.14.0 |
| SciPy | 1.18.1 |
| h5py | 3.16.0 |
| Pandas | 3.1.1 |

Full dependency freezes and exact pip output are attached to the workflow runs. Do not treat successful `pip check` as proof that running Bluesky experiments and reading/writing data work.

## Next tasks

1. Inspect the *updated* Ubuntu/macos/Windows probe results and record failures with full error messages and runner versions.
2. Install the built wheel (not just editable install) into a fresh CPython 3.14 environment and check packaged GUI resources.
3. Verify core GUI + simulated measurement + ZMQ + HDF5 pathways.
4. Consolidate `requirements.txt` and regenerate only tested Python 3.14 minimum requirements.
5. Migrate the main CI, tox configuration, docs and installer metadata from the obsolete Python versions.
6. Keep physical hardware-driver support as **lowest-priority, non-blocking** follow-up work.

## Reproducing locally

On Linux/macOS:

```bash
python3.14 -m venv .venv314
. .venv314/bin/activate
python -m pip install --upgrade pip build
python -m pip install --only-binary=:all: -e .
python -m pip check
python -c "import nomad_camels"
python -m build --wheel --sdist
```

On Windows PowerShell, create and activate the venv using `py -3.14 -m venv .venv314` and `.\.venv314\Scripts\Activate.ps1`; then use the same Python commands.

If `import nomad_camels` fails with a missing Qt shared-library error on Linux, install the corresponding OS runtime packages first; do not attempt to fix it by changing Python package pins.

**Environment limitation:** The inspection environment where these GitHub changes were authored only had Python 3.13 and no direct PyPI/network access. Actual Python 3.14 installation and build observations above come from GitHub-hosted CI runners, not from a local 3.14 installation.

## Runtime milestone observations (2026-11-06)

**Source:** [GitHub Actions run 42247940422](https://github.com/Falk3579/NOMAD-CAMELS/actions/runs/42247940422), Ubuntu CPython 3.14, with runtime smoke scripts under `dev_tools/`.

- **HDF5:** PASS. The CAMELS suitcase exported a simulated two-signal Bluesky measurement, and h5py reopened the file containing 131 datasets. A more detailed fixture verifying data values and dataset shape still needs to be added.
- **GUI:** PASS. With the first-launch configuration dialog disabled in isolated test preferences, the Qt main window initialized its ZeroMQ proxy and closed without orphan threads or processes.
- **Bluesky / ZMQ transport:** Measurement documents were received (start, descriptor, two events, stop), but the test flagged `asyncio.CancelledError` when the dispatcher was stopped. This is a shutdown-handling problem, **not a document-delivery failure**. The wrapper `run_remote_dispatcher` in `main_classes/plot_proxy.py` now treats cancellation after dispatcher cleanup as normal. Verification is pending in [the rerun](https://github.com/Falk3579/NOMAD-CAMELS/actions/runs/42248820919).
- **Bluesky run-engine compatibility:** Original `RunEngineOverwrite._read` passed a dict to the Bluesky 1.16 bundler where the bundler now requires a list of `(object, reading)` pairs; this caused `ValueError: too many values to unpack`. The override now handles multiple readables and preserves error recovery for devices opting in.
- **Databroker / NumPy:** Databroker 1.2.5 can remain; using PIMS 0.7+ fixes a transitive NumPy 2 import break. PIMS 0.7 is currently distributed as a source archive, which is preinstalled before the strict wheel-only CI probe.
- **Windows/macOS:** Windows packaging passed, but final runtime acceptance for Windows and macOS is not documented as complete by this report. The linked CI jobs are the source of truth; macOS runtime jobs have repeatedly been queued.

**Important:** No physical hardware driver validation has been performed. The normal test suite and wheel-installed (rather than editable-installed) GUI remain separate pending tasks.

### Completed two-platform runtime validation

The [2026-11-06 Python 3.14 CI run](https://github.com/Falk3579/NOMAD-CAMELS/actions/runs/42249544430) **passed in full on Ubuntu and Windows**: editable core install from available wheels (with pure-Python PIMS 0.7 preinstalled), `pip check`, import, wheel+sdist build, generated-protocol template, two-signal Bluesky-to-ZMQ document delivery and cleanup, CAMELS suitcase HDF5 export/reopen, and real Qt main-window startup/shutdown in an isolated headless test profile.

The ZMQ shutdown exception was resolved by `nomad_camels.main_classes.plot_proxy.run_remote_dispatcher`, which suppresses the normal `asyncio.CancelledError` after dispatcher cleanup. The Windows test-profile cleanup failure was resolved by closing logging handlers before deleting the temporary profile. These are distinct from untested physical hardware drivers.

**Remaining:** macOS runtime job queued; full existing pytest suite, installed-wheel GUI resources, detailed numeric/metadata HDF5 regression fixtures, graphical plot smoke, API extras, and release CI/tooling migration are not complete.

## Fresh-wheel isolation and resource packaging (2026-11-06)

**Why this matters:** The editable-install smoke tests can import images and UI resources directly from the checkout. They do not establish that a user-installed wheel contains the same files.

- Added `dev_tools/python314_wheel_probe.py`, which builds a fresh CPython 3.14 venv outside the repository, installs the distribution wheel without editable source, runs `pip check`, confirms the imported package resides under the venv, validates graphics files with `importlib.resources`, then executes the HDF5 and GUI smoke cases.
- The **first Ubuntu wheel probe failed** after successfully installing the wheel and passing `pip check`: `CAMELS_Icon.png` and other expected graphics were not packaged into the distribution wheel. [Failed CI run](https://github.com/Falk3579/NOMAD-CAMELS/actions/runs/42251231654).
- The source also referred to `CAMELS_vertical.png` and `CAMELS_horizontal.png`, but the actual filenames are `camels_vertical.png` and `camels_horizontal.png` on case-sensitive filesystems. Fixed the references in `CAMELS_start.py` and `MainApp_v2.py`; the GUI smoke now checks that the main-window logo QPixmap is not null.
- Updated Poetry package includes for `graphics/**/*`, Qt `.ui` and `.qrc`, and API `.yaml` resources in both sdist and wheel.
- The **corrected Ubuntu built-wheel probe passed**: clean venv installation, package-asset inspection, `pip check`, HDF5 round trip and Qt GUI launch/close. [Corrected CI run](https://github.com/Falk3579/NOMAD-CAMELS/actions/runs/42251913059).
- Added numeric data regression assertions: the two simulated signal streams must contain two readings each with the expected values 42.0 and 84.0 in both Databroker and persisted HDF5 datasets. The corrected Ubuntu HDF5 smoke passed.
- Windows/macOS fresh-wheel platform acceptance is not claimed in this snapshot; consult the latest run's per-OS job outcomes. macOS runner assignment was still queued.

The full suite, interactive plotting, real hardware, API extras, and remaining legacy version tooling still require separate work. Do not regard this as a production release declaration.
