# NOMAD-CAMELS: Python 3.14 migration plan

**Status:** Planning document, not a statement of implemented compatibility  
**Prepared:** 2026-11-06  
**Working branch:** `feature/python-3-14-support`  
**Starting revision:** `main`, commit `f07bb422d30d4da689ab396ed023a8ec2e5d3027`  
**Target:** standard, GIL-enabled CPython 3.14 on Windows, Linux, and macOS  
**Priority:** core desktop application and simulated measurements first; hardware drivers last

**Completed/verified checkpoints:** The [Python 3.14 core and runtime CI run](https://github.com/Falk3579/NOMAD-CAMELS/actions/runs/42249544430) is **green on both Ubuntu and Windows**. Both platform jobs passed core dependency installation, `pip check`, package import, wheel/sdist build, generated-protocol checks, Bluesky RunEngine/ZeroMQ simulated document delivery and shutdown, HDF5 export/reopen, and headless Qt GUI startup/shutdown. macOS runtime validation remains queued. The existing full pytest suite, built-wheel GUI installation, graphical plotting, and physical drivers are still separate unfinished tasks.

**Windows evidence:** [Windows Python 3.14 job](https://github.com/Falk3579/NOMAD-CAMELS/actions/runs/42249544430) passed all core/runtime smoke checks, including the Windows-specific selector loop and clean Qt/ZeroMQ shutdown. The earlier file-lock error was in the smoke fixture's teardown, and is fixed via `logging.shutdown()`. macOS runtime jobs are still queued.

## 1. Decisions and definition of done

### Explicit support decisions

- **Drop support for every Python release below 3.14.** Remove Python 3.9, 3.10, 3.11, 3.12, and 3.13 from supported-version claims, test matrices, minimum-version files, and installation instructions.
- **For this migration, declare only Python 3.14:** use `requires-python = ">=3.14,<3.15"` until Python 3.15 has been separately tested. The lower bound satisfies the new minimum; the upper bound avoids silently promising untested versions.
- **Do not support the free-threaded Python 3.14 build in this milestone.** It requires independent validation of Qt, C extensions, callbacks, and thread safety.
- **Hardware/device drivers have the lowest priority.** A driver that does not support 3.14 must not prevent the core application from being released. Document incompatible external drivers separately and allow users to select/install them at their own risk.
- **Keep the existing file formats and core measurement behavior intact.** Do not combine this work with a wholesale Databroker-to-Tiled migration, a framework rewrite, or unrelated feature development.
- **No automatic dependency-version guesswork.** Proposed version floors must be verified against real Python 3.14 installs and tests before finalizing.

### Definition of done

Python 3.14 support is complete when:

1. On each claimed OS, `pip install nomad-camels` (from the built artifact) and `pip check` pass in a clean standard CPython 3.14 environment.
2. The GUI starts, loads settings, creates and runs a simulated-device protocol, plots measurement data, stops cleanly, and can restart without hanging.
3. The Bluesky RunEngine and the CAMELS ZeroMQ publisher/dispatcher deliver run documents reliably; the subprocess and dispatcher shut down without orphan processes.
4. Core HDF5/NeXus output, metadata, catalog access used by CAMELS, and reading existing representative files pass round-trip tests.
5. Critical automated tests run on Python 3.14 in Windows, Ubuntu, and macOS CI; known OS-specific exceptions are documented with owner and follow-up, not disguised by retries.
6. The optional API can be installed separately and its startup, authentication, and protocol-status tests pass where the API extra is claimed supported.
7. Published metadata, dependency files, CI, installation docs, and release notes consistently say **Python 3.14** and no longer advertise 3.9–3.13.
8. Unsupported hardware drivers are clearly documented as deferred; they are **not a core Python 3.14 release gate**.

## 2. Repository findings (verified against the starting revision)

| Path | Finding | Planned response |
| --- | --- | --- |
| `pyproject.toml` | `requires-python = ">=3.9,<3.13"` | Change to `>=3.14,<3.15`; update Python classifiers. |
| `pyproject.toml` | `pyside6 = ">=6.6.0,<6.9"` | Replace with a Qt for Python release supporting CPython 3.14 (6.10.1+); test selected release and retain a defensible upper bound. |
| `pyproject.toml` | NumPy minimum `>=1.26.0` on Python >=3.12; complex legacy version markers for YAML, PyZMQ, setuptools, NumPy, httpx, uvicorn, and pytest | Remove obsolete <3.14 marker alternatives; establish compatible modern floors using a tested resolver. |
| `pyproject.toml` | `bluesky >=1.9.0` and `databroker >=1.2.5,<2.0.0` | Validate a new Bluesky baseline and legacy Databroker/Intake integration on 3.14 before choosing constraints. |
| `pyproject.toml` | `suitcase-nomad-camels-hdf5 >=1.3.2` | Validate version, transitive dependencies, and HDF5 output. |
| `requirements.txt` | Long second dependency list with versions differing from `pyproject.toml`; e.g. `databroker==1.2.5` | Decide whether to remove, narrow, or generate this file. Keep one authoritative dependency specification. |
| `dev_tools/min_versions_from_toml.py` | Python list ends at 3.13; minimum finder reads textual version floors but does not check actual 3.14 wheel/Requires-Python compatibility | Refactor for 3.14-only requirement generation and verify generated pins by installation. |
| `dev_tools/req_min_3.9.txt` … `req_min_3.13.txt` | Obsolete or stale minimum dependency fixtures | Remove legacy fixtures; introduce validated `req_min_3.14.txt` only after version discovery. |
| `tox.ini` | Test environments cover 3.9–3.13; default list ends at 3.12 | Replace with `py314` and `py314_min`, or simplify and delegate matrix control to CI. |
| `.github/workflows/ci.yml` | Main OS jobs hard-code Python 3.11; high/low test matrices target 3.9–3.12 | Migrate to 3.14 across Windows, Linux, macOS; remove obsolete matrices and clean up retries. |
| `.github/workflows/release_pages.yml` | Documentation workflow hard-codes 3.11 | Change to 3.14, verify Sphinx and dependencies. |
| `.github/workflows/publish.yml` | Builds with `python-version: '3.x'` | Use an explicit, reproducible 3.14 interpreter for publishing the 3.14-only package. |
| `nomad_camels/MainApp_v2.py` | Calls `asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())`; starts ZeroMQ proxy process and RemoteDispatcher thread | Remove global policy mutation; validate thread-owned event loops, ZMQ lifecycle, startup and cleanup. |
| `nomad_camels/bluesky_handling/protocol_builder.py` | Embeds the same deprecated asyncio policy call into generated protocols | Fix the **generated code template**, not just the GUI startup. Add generated-protocol regression tests. |
| `nomad_camels/tests/protocol_test.py` | Has the same Windows asyncio policy call | Refactor tests to avoid deprecated global policy manipulation. |
| `nomad_camels/main_classes/plot_proxy.py` | Top-level `run_zmq_proxy` uses a multiprocessing Queue to send chosen ports; proxy loops on `zmq.proxy` | Verify with 3.14 POSIX `forkserver` and Windows/macOS `spawn`, including proper termination. |
| `nomad_camels/api/api.py` | Qt `QThread` API integration explicitly creates/sets an asyncio loop | Exercise API thread startup, shutdown, request handling and event-loop ownership on 3.14. |
| `nomad_camels/main_classes/plot_pyqtgraph.py` and `nomad_camels/main_classes/plot_2D.py` | Qt, NumPy, SciPy, PyQtGraph, Bluesky callback integration | Test GUI and live plotting against new scientific/Qt dependencies. |
| `nomad_camels/bluesky_handling/make_catalog.py` and `nomad_camels/utility/databroker_export.py` | DataBroker catalog setup and HDF5 export | Test catalog configuration and persisted data against actual dependencies. |
| `nomad_camels/CAMELS_start.py` | Qt app loading/import thread and package resources | Test clean startup, wheel-installed resources, and clean exit. |
| `nomad_camels/tests/` | Startup, main app, protocol, plots, API, manual controls, devices | Extend to cover 3.14 behavior with simulated drivers; isolate tests that assume physical hardware. |

### External compatibility notes

- Qt for Python release notes list Python 3.14 support starting in PySide6 6.10.1. See https://doc.qt.io/qtforpython-6.10/release_notes/pyside6_release_notes.html
- The upstream Bluesky `main` CI includes Python 3.14 Linux tests; the Windows 3.14 combination was excluded due to a Tiled/duckdb dependency in its expanded test environment. This **does not** mean CAMELS itself is validated: https://github.com/bluesky/bluesky/blob/main/.github/workflows/ci.yml
- Python 3.14 deprecates the global asyncio policy API, including `WindowsSelectorEventLoopPolicy`: https://docs.python.org/3.14/library/asyncio-policy.html
- Python 3.14 changes the default POSIX multiprocessing method to `forkserver` (except macOS, where `spawn` remains the default): https://docs.python.org/3.14/library/multiprocessing.html#contexts-and-start-methods
- Validate Python 3.14-compatible NumPy, SciPy, h5py, PyTables, numexpr, PyZMQ, and Qt wheels instead of copying old minimum pins.

## 3. Prioritized work packages

### Phase 0 — baseline and failure inventory (P0)

**Objective:** identify the first real blockers before making broad upgrades.

- [ ] Run `python -m pip check` and the current tests under a known-good **existing** CAMELS environment, if available; record current behavior for comparison. This is a historical baseline, **not** a continued support promise for <3.14.
- [x] Record the commit, OS/architecture, Python build, and full `pip freeze` or `poetry show --tree` for baseline and migration environments. Preserve logs as CI artifacts, not committed binary files.
- [ ] Probe fresh Python 3.14 virtual environments on Windows, Ubuntu, and macOS. Initially attempt installing the project with a **temporary local metadata relaxation** to expose dependency incompatibilities. Do not publish that metadata change yet.
- [ ] Separate failures into: (a) Requires-Python/solver, (b) no cp314 wheel/source build, (c) package import, (d) app/runtime, (e) optional extra, (f) hardware-only.
- [ ] Create a concise compatibility ledger listing dependency, required feature, resolved 3.14 version, platform, status, and evidence.
- [ ] Verify target architectures (for example x86_64/AMD64 and macOS arm64); do not infer support for untested architectures.

**Exit criterion:** a reproducible install log and a ranked list of specific Python 3.14 blockers exist.

### Phase 1 — metadata and dependency resolution (P0)

**Primary files:** `pyproject.toml`, `requirements.txt`, packaging/build configuration.

- [x] Change `[project].requires-python` to `>=3.14,<3.15` and add the `Programming Language :: Python :: 3.14` classifier. Remove obsolete compatibility claims.
- [x] Select a Python 3.14-capable PySide6 version (at least 6.10.1); consider pairing with a matching PySide6 Addons/Essentials release via dependency resolver. Do not retain `<6.9`.
- [x] Replace all Python-version-specific dependency branches targeting 3.9–3.13 with a single 3.14 baseline, except any markers still required for OS distinctions.
- [ ] Set NumPy and compiled scientific dependencies using versions with verified Python 3.14 builds. Explicitly test NumPy 2.x compatibility; avoid assuming an existing 1.26 minimum works.
- [x] Resolve `bluesky`, `ophyd`, `pyzmq`, `event-model` and `msgpack(-numpy)` together. Prefer a supported current Bluesky version; preserve the CAMELS RunEngine/ZMQ interfaces and avoid an unnecessary Bluesky API rewrite.
- [x] Require `pims>=0.7` because Databroker 1.x otherwise installs PIMS 0.6.1, which imports removed `numpy.lib.arraypad`. The corrected Python 3.14 CI imports and executes the Databroker-backed simulated run without that error. Evidence: [diagnostic run](https://github.com/Falk3579/NOMAD-CAMELS/actions/runs/42246769233).
- [x] Try to retain Databroker 1.x first. If it or its transitive dependencies cannot resolve/run on 3.14, document the exact blocker and choose the **smallest possible** adaptation or compatibility shim. A full Tiled migration is a separate decision.
- [x] Validate `suitcase-nomad-camels-hdf5` and transitive HDF5 packages for Python 3.14 wheels and actual export behavior.
- [ ] Resolve **core first**. Then install each extra independently: `api`, `material`, `visa`, `dash`, `dev`. An optional extra should not force unsupported dependencies on core users.
- [ ] Decide whether to generate `requirements.txt` from authoritative metadata, reduce it to a documented constraint set, or remove it; eliminate incompatible old pins.
- [ ] Test an sdist and wheel build (`python -m build`); install the resulting wheel into a fresh 3.14 environment and run `pip check`.

**Exit criterion:** clean Python 3.14 core install and wheel build succeed on the target OSes; each unsupported optional extra has an explicit ticket and does not break core installation.

### Phase 2 — core runtime, asyncio and ZeroMQ (P0)

**Primary files:** `nomad_camels/MainApp_v2.py`, `nomad_camels/bluesky_handling/protocol_builder.py`, `nomad_camels/main_classes/plot_proxy.py`, `nomad_camels/tests/protocol_test.py`.

- [x] Remove deprecated calls to `asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())` from the main window, generated protocol template, and test setup.
- [ ] Determine which component actually owns and starts each event loop. Where a selector loop is needed, create it **locally in the correct thread** (e.g. an explicit `loop_factory` via `asyncio.Runner`/`asyncio.run` for owned async entry points); do **not** blindly wrap a synchronous Qt event loop in `asyncio.run`.
- [x] Check how the chosen Bluesky `RemoteDispatcher` and PyZMQ versions create/consume event loops and which thread invokes `dispatcher.start()`. Prefer documented upstream APIs.
- [x] Update CAMELS' `RunEngineOverwrite._read` to Bluesky 1.16's multi-object `(object, reading)` bundler contract; the previous `ValueError` disappeared and the simulated run reached HDF5 output. Evidence: [diagnostic run](https://github.com/Falk3579/NOMAD-CAMELS/actions/runs/42246769233).
- [ ] Test cancellation, unsubscribing, dispatcher closure, ZMQ socket/context closure, and application restart, especially after exceptions.
- [x] Run hardware-free Python 3.14 integration smokes on Windows and Ubuntu: GUI startup/shutdown, two-signal Bluesky run, ZeroMQ publish/dispatch and shutdown, and HDF5 export/reopen. [Both jobs passed](https://github.com/Falk3579/NOMAD-CAMELS/actions/runs/42249544430); macOS and built-wheel tests remain pending.
- [ ] Exercise Python 3.14 default `forkserver` on Linux and `spawn` on Windows/macOS. Make subprocess targets/imports picklable; ensure process/Queue/port handoff is robust without relying on inherited Qt state.
- [x] Replace any unbounded startup wait (for example `port_queue.get()` without a timeout) with bounded waits and useful diagnostics; ensure the child can be terminated on failure.
- [ ] Verify generated standalone protocol scripts use the same corrected startup/cleanup logic. Avoid duplicated divergent setup code if a shared helper can be introduced safely.
- [x] Add a subprocess integration test: RunEngine -> Publisher -> proxy -> RemoteDispatcher receives `start`, `descriptor`, `event`, and `stop` (or relevant stream documents), and all processes/threads exit cleanly.
- [x] Test on actual Windows as the Windows selector/proactor difference is not reproduced on Linux.

**Exit criterion:** simulated run documents flow reliably through the proxy and no orphaned process, hanging thread, or policy deprecation warning remains.

### Phase 3 — GUI, scientific calculations, plots, and data output (P0/P1)

**Primary files:** `nomad_camels/CAMELS_start.py`, `nomad_camels/MainApp_v2.py`, `nomad_camels/main_classes/`, `nomad_camels/gui/`, `nomad_camels/frontpanels/`, `nomad_camels/utility/databroker_export.py`, `nomad_camels/bluesky_handling/make_catalog.py`.

- [ ] Start the wheel-installed GUI and use the main controls with the new PySide6 version; test app shutdown/relaunch.
- [ ] Audit enum namespaces, `exec()/exec_()`, signals/slots, Qt thread affinity, blocking calls, and event-loop interactions. Replace deprecated patterns only where needed; distinguish warnings from actual failures.
- [ ] Exercise protocol editing, channel selection, device configuration for simulated devices, queueing, aborting, status indicators, manual controls without hardware, and standard preferences persistence.
- [ ] Verify NumPy 2.x behavior in evaluation helpers, plotting, fitting, xarray/pandas conversion, and generated protocol code. Audit removed NumPy aliases and older SciPy APIs used by CAMELS or loaded plugins.
- [ ] Run headless plotting tests and at least one **real graphical** smoke test on every supported OS; Xvfb/offscreen is useful but is not a substitute for interactive GUI validation.
- [x] Verify a simulated Python 3.14 measurement writes HDF5 data through the existing suitcase and can reopen the file. The Linux smoke run found 131 HDF5 datasets (as recorded in [CI log](https://github.com/Falk3579/NOMAD-CAMELS/actions/runs/42247940422)); value/shape regression fixtures and all-platform coverage remain separate unchecked tasks.
- [ ] Validate serialized data: create a simulated run, export with the suitcase, inspect metadata and datasets, reopen the output, and compare expected values and shapes.
- [ ] Verify an existing representative file (preferably a non-sensitive fixture) can still be read and exported without silent schema changes.
- [ ] If Databroker integration fails, isolate whether the issue is installation, catalog configuration, storage adapter, or data access; do not prematurely redesign the storage stack.
- [x] Add regression tests for discovered incompatibilities, keeping fixtures independent of physical instruments.

**Exit criterion:** GUI + simulated measurement + plots + saved/reopened data pass on Python 3.14; core storage format remains compatible.

### Phase 4 — optional API and extensions (P1)

**Primary files:** `nomad_camels/api/api.py`, `nomad_camels/api/api_schema_validation.py`, `nomad_camels/tests/api_test.py`, `nomad_camels/extensions/`, `nomad_camels/nomad_integration/`.

- [ ] Verify `api` extra resolves FastAPI, Pydantic, Uvicorn, and HTTPX versions on Python 3.14.
- [ ] Check `FastapiThread` startup/shutdown and ownership of the explicitly created asyncio event loop. Confirm clean closure when the main Qt app exits.
- [ ] Test API key creation/validation, health/status/protocol requests, cancellation, and error responses using automated API tests or an in-process test client where possible.
- [ ] Smoke-test NOMAD integration paths that require no external credentials; stub remote calls and document live-service checks separately.
- [ ] Check extension discovery/import paths and ensure **unavailable third-party plugins/drivers fail gracefully without crashing the core GUI**.
- [ ] Keep optional `dash` and `material` functionality in separate test jobs if their dependencies add major platform constraints.

**Exit criterion:** documented non-hardware extras can be installed and tested without destabilizing core.

### Phase 5 — CI, packaging, release, and docs (P0/P1)

**Primary files:** `.github/workflows/ci.yml`, `.github/workflows/publish.yml`, `.github/workflows/release_pages.yml`, `tox.ini`, `dev_tools/min_versions_from_toml.py`, `dev_tools/req_min_*.txt`, `README.md`.

- [ ] Change main CI to Python **3.14 only**, with Windows, Ubuntu, and macOS jobs. Do not retain obsolete 3.9–3.13 matrix rows.
- [ ] Split jobs into: build/install/`pip check`; lint/static checks; unit tests; Qt smoke; simulated measurement/ZMQ integration; HDF5 round trip; API extra; optional extra checks.
- [ ] Update or simplify tox environments to `py314` and `py314_min`. Do not silently run `poetry lock` in each job and call that a reproducible version baseline: record the resolved dependency set and pin workflow tooling appropriately.
- [ ] Refactor minimum-version generator for 3.14 only. Distinguish a syntactic minimum from the **earliest installable and tested** release for 3.14; reject unsupported candidates by wheel/metadata/resolver test before committing a minimum requirements file.
- [ ] Remove obsolete `dev_tools/req_min_3.9.txt` through `req_min_3.13.txt` and commit a genuinely installable `dev_tools/req_min_3.14.txt` only after validation.
- [ ] Change docs and release build workflows to use explicit Python 3.14. Validate Sphinx requirements and build packaging.
- [ ] Ensure CI triggers on pull requests involving this feature branch or a PR into `main`; do not make it dependent solely on the old Python 3.11 jobs.
- [ ] Make logs and test artifacts available for failures; do not use "retry then pass" to hide known deterministic compatibility errors. Track genuinely flaky tests separately.
- [ ] Update installation commands, minimum Python requirements, platform-specific installation notes, release notes, and `README.md`. State that Python <=3.13 is unsupported in the new version; advise users of the last older-Python-compatible release without claiming it will receive updates.
- [ ] Install and launch the **built wheel**, not only `pip install -e .`, to catch missing non-Python GUI and data resources.
- [ ] Review launchers, packaging metadata, and third-party installers (if distributed) for embedded Python 3.11; migrate them to CPython 3.14 or document as separate distributables.

**Exit criterion:** reproducible green Python 3.14 CI for the claimed core feature set and matching user-facing release documentation.

### Phase 6 — hardware/device drivers: lowest priority, non-blocking (P3)

**Only after Phases 0–5 succeed:**

- [ ] Inventory real drivers and installations, separating maintained drivers from outdated third-party components.
- [ ] Record driver-specific Python 3.14 support, binary dependencies, VISA/EPICS/native libraries, installation failures, and device test outcomes.
- [ ] Provide clear compatibility warnings or preflight diagnostics when adding a driver on Python 3.14.
- [ ] Prioritize drivers by actual usage and maintenance ownership, not by a blanket requirement to support everything.
- [ ] Test connected instruments only where hardware is available; document unverified combinations.
- [ ] Track incompatible drivers in independent issues, without blocking the Python 3.14 **core** release.

**Exit criterion:** a driver compatibility table and follow-up tickets. All hardware-drivers-green is **not required** for core release.

## 4. Execution order, ownership and issue breakdown

| Order | Issue / work item | Priority | Key dependencies | Deliverable |
| --- | --- | --- | --- | --- |
| 0 | Produce 3.14 dependency/install failure inventory | P0 | Python 3.14 runners | Resolver logs + compatibility ledger |
| 1 | Modernize metadata and core dependency floors | P0 | Issue 0 | 3.14 core install with `pip check` |
| 2 | Fix asyncio policy and ZMQ process lifecycle | P0 | Issue 1 | Tested startup/shutdown helper and integration tests |
| 3 | GUI + simulated device/protocol regression fixes | P0 | Issues 1–2 | End-to-end simulated run |
| 4 | NumPy, plotting and HDF5/Databroker compatibility | P0 | Issues 1–3 | Data round-trip/plot tests |
| 5 | Modernize CI/tox/min-version tooling and wheel build | P0 | Issues 1–4 | Green 3.14 platform matrix |
| 6 | Validate optional API + extension/NOMAD integration | P1 | Issues 1–4 | API-extra and extension tests |
| 7 | Update release/docs/installers and prepare PR | P1 | Issues 1–6 | Reviewable migration PR and release notes |
| 8 | Review physical hardware drivers | P3 | None for core release | Compatibility list and later tickets |

**Suggested PR strategy:** implement work in small, reviewable commits on `feature/python-3-14-support`; prefer separate focused PRs if the changes become large, with the final release/support declaration only after the acceptance gates pass. Do not merge before those gates are satisfied.

## 5. Concrete installation and smoke-test commands

Examples below are intended for **after** dependency metadata is updated. Use standard CPython 3.14.

### Linux / macOS

```bash
python3.14 -m venv .venv314
. .venv314/bin/activate
python -m pip install --upgrade pip build
python -m pip install -e .
python -m pip check
python -c "from nomad_camels import start_camels; print('import OK')"
python -m pytest -q nomad_camels/tests
python -m build
```

### Windows PowerShell

```powershell
py -3.14 -m venv .venv314
.\.venv314\Scripts\Activate.ps1
python -m pip install --upgrade pip build
python -m pip install -e .
python -m pip check
python -m pytest -q nomad_camels/tests
python -m build
```

### Optional extras

```bash
python -m pip install -e ".[api,dev]"
python -m pip check
python -m pytest -q nomad_camels/tests/api_test.py
```

### Built-wheel verification

```bash
python -m build
python -m pip install --force-reinstall dist/*.whl
python -m pip check
nomad-camels
```

On Linux CI, configure actual Qt system libraries and Xvfb/offscreen environment explicitly; running a GUI binary may require a graphical smoke-test job separate from headless unit tests. The current tests may need code changes before they run on Python 3.14. Record failing and skipped tests rather than treating these commands as a guarantee of success.

## 6. Acceptance matrix

| Check | Windows 3.14 | Ubuntu 3.14 | macOS 3.14 | Blocking? |
| --- | --- | --- | --- | --- |
| Clean core install + `pip check` | Required | Required | Required | Yes |
| Import and application startup/exit | Required | Required | Required | Yes |
| Simulated protocol through Bluesky | Required | Required | Required | Yes |
| ZMQ callback stream + process cleanup | Required | Required | Required | Yes |
| Live/recorded plotting smoke test | Required | Required | Required | Yes |
| HDF5 export + reopen | Required | Required | Required | Yes |
| Package wheel and sdist build | Required (wheel install) | Required | Required (wheel install) | Yes |
| API extra and representative requests | Required if API supported | Required if API supported | Required if API supported | Yes for API claim |
| NOMAD live-server credentialed integration | Manual/deferred | Manual/deferred | Manual/deferred | No, but mock path required |
| Physical VISA/EPICS/external device drivers | Deferred | Deferred | Deferred | **No** |
| Python 3.15, free-threaded 3.14 | Not targeted | Not targeted | Not targeted | No |

## 7. Risks and fallback/rollback

1. **No compatible native wheel or hard transitive pin (high):** isolate package and platform from resolver output; look for a supported package version, replace only the smallest incompatible component, or make genuinely optional functionality non-blocking. Do not force source builds as the default installation path for all users without evidence.
2. **Databroker 1.x incompatibility (high):** retain its external API if possible using a narrow adaptation; do not start a cross-project storage migration without separately approving that scope. Test real file round trips.
3. **PySide6 API/behavior differences (high):** prioritize only failing GUI interactions, Qt thread-affinity issues, and enums; keep visual and behavioral changes minimal.
4. **ZMQ startup/shutdown hangs (high):** bounded waits, explicit loop/process ownership, integration tests for failure paths, and process cleanup.
5. **NumPy 2.x semantic changes (medium/high):** use regression fixtures for numerical values, plots, metadata dtypes, and serialization.
6. **Optional dependency failures (medium):** independently test and isolate extras; report unverified functions explicitly.
7. **Hardware drivers (lowest priority):** accept unsupported individual drivers in the initial Python 3.14 core release, provided failures are visible and non-catastrophic.

**Rollback:** preserve the last working release as-is for users staying on older Python. Do not retroactively edit that release; if this migration fails, do not publish the new 3.14-only package. The migration branch can be revised or reverted without changing `main`.

## 8. First implementation checkpoint

The first code commit after this plan should be a small **packaging/dependency discovery** change, not a sweeping rewrite:

1. Make the metadata Python-3.14-only and allow a Python-3.14-capable PySide6 version.
2. Remove obsolete Python <3.14 marker branches.
3. Run clean install attempts on the 3 main OSes, collect solver/build failures, and document exact viable pins.
4. Verify `python -m pip check` and build an installable wheel.
5. Only then tackle async/ZMQ, GUI, data and API regressions in the order above.

**This file is the plan, not proof of Python 3.14 compatibility.** Implementation, test results, and driver qualifications must be recorded in subsequent commits.
