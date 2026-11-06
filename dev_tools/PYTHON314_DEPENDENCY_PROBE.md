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

**Important:** This report is a snapshot of the initial run, not a promise that the updated run has passed. The linked Actions pages and uploaded diagnostic artifacts are the source of truth for results.

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
