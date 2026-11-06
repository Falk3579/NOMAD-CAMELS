# Historical Python 3.11 comparison (not a support target)

**Purpose:** Preserve observable behavior from the original NOMAD-CAMELS 1.11.0 source as a comparison with the Python 3.14 migration. This does **not** reinstate support for Python <3.14. All workflow and documentation changes are made on `feature/python-3-14-support`; the pinned historical revision is checked out read-only.

**Reference code:** `f07bb422d30d4da689ab396ed023a8ec2e5d3027` (pre-migration `main`).  
**Runner:** Ubuntu, CPython 3.11.18, Qt offscreen.  
**Reproducer:** [`.github/workflows/python311-baseline.yml`](../.github/workflows/python311-baseline.yml).  
**Artifacts:** each run uploads `pip-freeze.txt`, installation and `pip check` logs, focused Qt-test output, and first-failure full-suite output.

## Observed results

| Run | Installed optional extras / constraints | pip check and import | Existing loading-screen tests | Original test suite |
| --- | --- | --- | --- | --- |
| [First attempt](https://github.com/Falk3579/NOMAD-CAMELS/actions/runs/42290650081) | `dev`, NumPy <2 preinstalled | Passed | 2 passed | Collection stopped: `api_test.py` requires optional FastAPI, which the diagnostic had not installed |
| [API-enabled run](https://github.com/Falk3579/NOMAD-CAMELS/actions/runs/42290880286) | `dev,api`, otherwise latest compatible releases | Passed | 2 passed | **6 passed, 1 skipped, 1 failed**, stopped on `test_run_subprotocol`: `ValueError: too many values to unpack (expected 2)` |
| [Historically bounded rerun](https://github.com/Falk3579/NOMAD-CAMELS/actions/runs/42291476443) | `dev,api`, `bluesky>=1.15,<1.16`, `numpy>=1.26,<2` | Awaiting verified run result | Awaiting verified run result | Awaiting verified run result |

The API-enabled run resolved **Bluesky 1.16.0** and **NumPy 2.4.6** despite initially preinstalling NumPy 1.26.4. This is why preinstallation alone must not be mistaken for a pin. The original code has `bluesky>=1.9.0` with no upper bound.

### Identified preexisting failure (not Python 3.14-specific)

The unmodified source's `nomad_camels/bluesky_handling/run_engine_overwrite.py`, line 77, calls the Bluesky bundler with a read-result mapping. Bluesky 1.16 expects iterable `(object, reading)` pairs and rejects the mapping with `ValueError: too many values to unpack (expected 2)`. The **same issue reproduces on Python 3.11** in `nomad_camels/tests/protocol_test.py::test_run_subprotocol`; it is a Bluesky API-version incompatibility, not evidence that Python 3.14 itself caused the error. The migration branch's `RunEngineOverwrite._read` fix addresses this new bundler API.

The API-enabled run also produced a pending-task warning on dispatcher teardown: the original test's `RemoteDispatcher.start` thread was stopped without full coroutine cleanup. The migration branch already has a thread-owned dispatcher wrapper and dedicated shutdown smoke test. See [Python 3.14 compatibility ledger](PYTHON314_COMPATIBILITY_LEDGER.md).

## Scope and limitations

- The isolated tests are representative comparison checks, **not** an assertion that the historical full suite was green.
- Full-suite diagnosis is run with `--maxfail=1`, making the **first failure** a useful baseline without attempting potentially hardware-dependent long-running tests.
- No physical instrument drivers were installed or exercised.
- Python 3.11 is tested only against an immutable historical code checkout; the migration branch's packaging continues to require `>=3.14,<3.15`.

**No release-support claim is implied by these diagnostics.**
