# Python 3.14 compatibility ledger

**Branch:** `feature/python-3-14-support`  
**Target:** standard CPython 3.14 (not free-threaded)  
**Scope:** verified observations from historical and branch CI. This is a **diagnostic ledger**, not a release declaration.  
**Hardware-device drivers:** lowest-priority, non-blocking for the core release.

## Evidence and failure classes

The key is **fixed/tested** (supported by a passing job), **fixed/partial** (the fix has limited platform or feature evidence), **open**, or **not in scope**. A successful resolver or `pip check` does not prove runtime compatibility.

| Category | Component / path | Observed issue or finding | Status and actual evidence |
| --- | --- | --- | --- |
| Requires-Python / solver | `pyproject.toml` | Original `>=3.9,<3.13` prevented installation on CPython 3.14. Version-specific markers and `pyside6<6.9` precluded a supported Qt release. | **Fixed/tested (installation):** declared `>=3.14,<3.15`, PySide6 `>=6.10.1,<6.13`, modern NumPy and PyZMQ floors. Windows, Ubuntu and macOS installed core dependencies, passed `pip check`, imported CAMELS and built wheel/sdist: [three-OS CI](https://github.com/Falk3579/NOMAD-CAMELS/actions/runs/42242433695). |
| No cp314 wheel / source build | `pims>=0.7` transitive via Databroker | The required NumPy-compatible PIMS 0.7 is distributed as a pure-Python source archive in the observed resolver. | **Fixed/partial:** install PIMS 0.7 from source before the diagnostic's wheel-only project install. A strictly all-wheel dependency installation is **not** established. See [runtime CI](https://github.com/Falk3579/NOMAD-CAMELS/actions/runs/42251913059). |
| OS shared library | Linux Qt graphics | First Ubuntu run installed Python packages and passed `pip check` but `import nomad_camels` raised `ImportError: libEGL.so.1`. | **Fixed/tested (Ubuntu CI):** runner now installs `libegl1`, `libopengl0`, `libgl1`, `libxkbcommon-x11-0`, `libpulse0`. Compare [original failure](https://github.com/Falk3579/NOMAD-CAMELS/actions/runs/42242160099) and [passing rerun](https://github.com/Falk3579/NOMAD-CAMELS/actions/runs/42242433695). |
| Python / NumPy runtime API | Databroker 1.x -> PIMS | PIMS 0.6.1 imported `numpy.lib.arraypad`, removed in NumPy 2, breaking Databroker import during a Python 3.14 run. | **Fixed/tested (Windows/Ubuntu smokes):** require `pims>=0.7`; Databroker 1.2.5 is retained without a premature Tiled migration: [compatibility run](https://github.com/Falk3579/NOMAD-CAMELS/actions/runs/42246769233) and [two-OS smokes](https://github.com/Falk3579/NOMAD-CAMELS/actions/runs/42249544430). |
| Library API change | `RunEngineOverwrite._read` | In Bluesky 1.16, the bundler requires `(object, reading)` pairs; CAMELS previously passed a dict, causing `ValueError` in simulated measurements. | **Fixed/tested (Windows/Ubuntu smokes):** override now passes the required read pairs and the two-signal run reaches HDF5 export. Bluesky currently constrained to the 1.16 line: [two-OS smokes](https://github.com/Falk3579/NOMAD-CAMELS/actions/runs/42249544430). |
| Thread/event loop | Windows selector and ZeroMQ dispatcher | Global `WindowsSelectorEventLoopPolicy` is deprecated; dispatcher shutdown initially propagated an expected `asyncio.CancelledError`. | **Fixed/partial:** remove the global policy; use a thread-owned selector loop on Windows for the dispatcher and a wrapper that suppresses cancellation after successful closure. Windows and Ubuntu delivery and shutdown tests pass; full cancellation/failure-path and macOS checks still open: [smokes](https://github.com/Falk3579/NOMAD-CAMELS/actions/runs/42251913059). |
| Core data output | Databroker / suitcase HDF5 | Potential NumPy 2 and serializer errors when reading a run and writing HDF5. | **Fixed/tested (Windows/Ubuntu):** simulated Bluesky run with two channels `42.0` and `84.0`, two readings each, survived Databroker and persisted datasets; HDF5 could be reopened: [two-OS CI](https://github.com/Falk3579/NOMAD-CAMELS/actions/runs/42251913059). Historical formats and broader metadata remain unverified. |
| Built-wheel package resources | `pyproject.toml`, `graphics/`, startup GUI | A clean wheel install passed `pip check` but was missing non-Python GUI resources. Qt logo paths also used incorrect case on case-sensitive platforms. | **Fixed/tested (Windows/Ubuntu):** Poetry now includes graphics, `.ui`, `.qrc` and `.yaml`; PNG paths use actual filenames. Fresh isolated venv wheel installs found resources and passed GUI/HDF5 smokes: [initial failure](https://github.com/Falk3579/NOMAD-CAMELS/actions/runs/42251231654), [fixed rerun](https://github.com/Falk3579/NOMAD-CAMELS/actions/runs/42251913059). |
| Optional extra | API, material, dash, VISA, dev | Core-install success does not establish all extras can resolve and run on Python 3.14. | **Open:** test each extra separately. No driver-specific failures should block the core migration. |
| Full test suite | `nomad_camels/tests` | The Python 3.14 branch has only focused integration smokes, not the full pytest regression suite. | **Open:** broader existing unit/integration tests, plots, generated standalone scripts, exception cleanup and optional features remain separate gates. |
| Hardware-only | Third-party drivers / physical devices | External binary or instrument-specific dependencies may lack Python 3.14 support. | **Not in core scope:** track separately after core functionality is validated. |

## Verified dependency-resolution sample

The installed Python 3.14 environment in [the original package probe](https://github.com/Falk3579/NOMAD-CAMELS/actions/runs/42242160099) resolved PySide6 6.12.0, NumPy 2.5.4, Bluesky 1.16.0, PyZMQ 27.3.0, Ophyd 1.11.2, Databroker 1.2.5, SciPy 1.18.1, h5py 3.16.0, and suitcase-nomad-camels-hdf5 1.3.2. These are **observed working install versions**, not necessarily the earliest compatible versions or finalized minimums. Per-run `pip-freeze.txt` artifacts contain the full resolver outputs.

## Platform evidence

| Platform | Package/install baseline | Hardware-free Qt + Bluesky/ZMQ + HDF5 | Fresh built-wheel / packaged resources |
| --- | --- | --- | --- |
| Ubuntu | Passed | Passed | Passed |
| Windows | Passed | Passed | Passed |
| macOS | Passed | **Not verified** (job previously queued/cancelled) | **Not verified** |

References: [three-OS install](https://github.com/Falk3579/NOMAD-CAMELS/actions/runs/42242433695), [two-OS runtime and wheel](https://github.com/Falk3579/NOMAD-CAMELS/actions/runs/42251913059).

## Remaining decisions

1. Test modern scientific/plotting code and existing unit tests against NumPy 2.x, not just two static measurement channels.
2. Resolve and test optional `api`, `material`, `dash`, `visa`, and `dev` extras in **independent** environments.
3. Establish macOS runtime evidence and test Linux `forkserver` / macOS `spawn` explicitly.
4. Update the original full CI and release tooling, legacy requirements and docs to Python 3.14 only.
5. Defer actual hardware drivers until core release gates are satisfied.
