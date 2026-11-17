# emfit — a Finite Integral Technique solver for computational electromagnetics

`emfit` integrates the time-domain Maxwell equations on a structured, non-uniform
grid using FIT/FDTD operator pairs (curl matrices, a dual grid, material matrices),
in pure Python plus NumPy/SciPy, with an optional C++ kernel for the update step.
It is a research instrument: every number it produces is traceable to a recorded
artefact, and the project's own conventions about what may be claimed are written
down rather than assumed.

## Start here

| read this | it tells you |
|---|---|
| [`docs/design/EM_SOLVER_LEDGER.md`](docs/design/EM_SOLVER_LEDGER.md) | The open work: twelve items, each with a status label and the artefact that decides it. Read before planning anything. |
| [`docs/design/lessons_learned_emfit.md`](docs/design/lessons_learned_emfit.md) | Six mistakes this project made and the rules that would have prevented them. Read before trusting a number. |
| [`docs/design/cpp-kernel-status-2026-11-09.md`](docs/design/cpp-kernel-status-2026-11-09.md) | The C++ kernel: what it implements, how parity is measured, what would make the claim wrong. |

## Build

### Container (verified)

The only build recipe exercised in this repository's development container is the
explicit compiler invocation — no cmake, no network, pybind11 3.1.0 headers already
present in `.venv`:

```
/usr/bin/g++ -O3 -fopenmp -std=c++17 -shared -fPIC -Wall -Wextra \
  -I/workspace/.venv/lib/python3.12/site-packages/pybind11/include \
  -I/usr/local/include/python3.12 -Isrc \
  src/bindings.cpp src/emfit_core.cpp -o build/cpp/emfit_core<EXT_SUFFIX>
```

`<EXT_SUFFIX>` is the building interpreter's own suffix; here the artefact is
`build/cpp/emfit_core.cpython-312-x86_64-linux-gnu.so`, built by `/usr/bin/g++`
14.2.0 with zero warnings under `-Wall -Wextra`.

`pip install -e .` is **not available** in the container: `pyproject.toml` uses
`scikit-build-core`, and neither it nor `ninja` is installed. `emfit` itself is
importable from the repository root without installing anything.

### Operator host (reported)

On a host with a compiler and network, the operator built the package with
`pip install -e .` and reported:

```
Successfully installed emfit-0.1.0.dev0
```

and, from the parity tests, `3 passed`.

**This is OPERATOR-REPORTED and not reproduced here.** It establishes that the
build backend, the wheel and the extension work on that host. The three tests are
the three v1 parity tests — the goldens predate the second, full-physics golden, so
"3 passed" is what the suite reported then, not now: the tree holds **784 collected
tests across 65 test files** (`tests/test_*.py`), and the two-file command under
Test below collects 20 of them.
The exact command line and the full pip log are still not on record.

## Test

```
PYTHONPATH=build/cpp python3 -m pytest tests/test_cpp_parity.py tests/test_step_extraction.py -q
```

That command collects **20** tests today — 13 in `tests/test_cpp_parity.py` and 7 in
`tests/test_step_extraction.py`. It is a two-file gate, not the suite.

The whole tree is **784 collected tests across 65 test files** (`tests/test_*.py`).
The collection has to be run with the kernel's `site-packages` on `PYTHONPATH`:
from a bare interpreter 30 files die on `RuntimeError: emfit_core exists on disk but
could not be imported` and `--collect-only` ends `Interrupted: 30 errors during
collection`, so no count comes out at all.

```
PYTHONPATH=.venv/lib/python3.12/site-packages python3 -m pytest --collect-only -q
```

<!-- Trace, verbatim tail of the per-file-summing run that produced 783: it prints
     one line per file and no total line, 783 being the sum of the 64 per-file
     lines. Re-measured on 2026-11-12 with `tests/test_dr43_pulse_writer.py` added
     - one test, `slow` - the same collection is 784 over 65 files (per-file lines
     summed: 784), and the tail below is unchanged. No total line appears there
     because `pyproject.toml` sets `addopts="-q"`, so the command above runs as
     `-qq` and the `N tests collected in ...` line is suppressed; a single `-q`
     (`--collect-only -o addopts="" -q`) prints `784 tests collected in 1.12s`.
tests/test_step_extraction.py: 7
tests/test_studies.py: 62
tests/test_terminations.py: 11
tests/test_webapp.py: 11
tests/test_writer_station_phasors.py: 13
-->

The **fast gate** is 23 tests over three files: 13 parity (`tests/test_cpp_parity.py`
— 3 on the v1 golden and 10 on the v2 full-physics golden, the 10 being 7 functions
one of which is parametrised over four single-branch ablations) + 3
`tests/test_extraction_plane_default.py` (the DR-43 residual 1 plane default) + 7
`tests/test_engine_provenance.py`. Measured with `--collect-only`, not added up on
paper:

```
PYTHONPATH=.venv/lib/python3.12/site-packages python3 -m pytest --collect-only -q \
  tests/test_cpp_parity.py tests/test_extraction_plane_default.py tests/test_engine_provenance.py
```

The one file this tree does **not** put in that gate is the new DR-43 pulse test:
`tests/test_dr43_pulse_writer.py` (1 test, marked `slow`) drives
`evidence/termination/run_build_A.py` through a real 2400-step 3-D solve — ~42 s
here, 378 MB peak — and reads the record it writes, so it is the one test that
fails if the plane-less pulse path ever publishes an |S21| again. `-m 'not slow'`
deselects it, and the fast gate stays at **23**.

For the whole suite, one file per process — the canonical per-file invocation, as
`docs/design/GEN12_HANDOFF_TRAPS.md:104-106` gives it:

```sh
for f in tests/test_*.py; do
  echo "=== $f"; timeout 400 python3 -m pytest "$f" -o addopts="" -q 2>&1 | tail -20
done
```

`scripts/test_all.sh` is the full-suite runner and does exactly that loop: one
process per test file, `-o addopts=""` on every call so the `addopts = "-q"` in
`pyproject.toml` cannot make the quiet flag double, a per-file `timeout`
(`TEST_TIMEOUT`, default 300 s) and exit 124 reported as STALLED rather than
FAILED. It also passes `-o timeout=0`, because `pyproject.toml`'s `timeout = 300`
arms pytest-timeout's own `SIGALRM` clock, which cannot interrupt a blocked C or
sparse-matvec call (DR-39): with it off, the per-file `timeout` is the only clock
in the run and a stall has exactly one way to be reported.

The parity tests compare the C++ kernel against the pure-Python reference at
tolerance **zero** (`assert_array_equal`, not `allclose`), and the goldens are
frozen snapshots of the Python reference taken before the kernel was written.
Bit-identity is a property of the build line as much as of the code: no FMA
contraction and no reassociation are emitted, which `-ffast-math`, `-mfma` or
`-march=native` would silently destroy.

## Web UI

```
PYTHONPATH=. python3 server/poc_app.py        # from the repo root; serves http://127.0.0.1:8080/
```
Flags, the `--list-keys` preflight, the headless caveat, dependencies and known-broken items: `docs/kb/WORK/run.md` is the single maintained source.

## Status and conventions

These are the rules the project holds itself to. They exist because each one was
broken at least once.

- **No claim of physical correctness without an independent anchor.** The port
  extraction still marks itself as not yet checked against its anchor in its own
  output record (`evidence/termination/build_A_50ohm.json`). The anchor it was
  first measured against, `0.34465 = 50/(2*47.53662+50)`, turned out to be the
  twin run's own fitted impedance rather than an independent one, so that
  comparison is retracted. Against the independent quasistatic value for the
  same strip width (`Z0 = 48.0237405` ohm at `w = 3.2` mm) the residual is
  `-3.10` to `-6.52` percent (`-6.52` on the fine mesh, two-wave; `-4.90` on the
  coarse mesh, two-wave, superseded by the fine mesh), not sub-percent. The
  **active verification** of it is the openEMS referee in E12: a second solver
  runs the same build A and its `|S11|` is compared against `0.326` (artefact)
  and `0.342` (anchor). See E1, E10 and E11 in
  [`docs/design/EM_SOLVER_LEDGER.md`](docs/design/EM_SOLVER_LEDGER.md) and
  `evidence/termination/build_A_50ohm.superseded.json`.
- **No speed claim without a measurement.** The OpenMP pragmas measured about 50x
  *slower* at the golden grid size, so no speed figure appears anywhere here, and
  none should be quoted from the code.
- **The passivity question is open, not closed.** Records whose
  `|S11|^2 + |S21|^2` exceeds 1 still exist and are still explained only by an
  inference. Do not describe the matter as settled. See E2 in the ledger.
- **Label the evidence on every claim**: repository-observed, operator-reported,
  or unverified. The ledger's status vocabulary is used across these documents.
- **Commit explicit file lists.** A dispatch is authorised by an entry in
  [`docs/design/dispatch_log.md`](docs/design/dispatch_log.md), and a dispatch that
  is not on that list is not authorised.

## Documentation

Design documents live in `docs/design/`; the current-session roadmap is
`docs/design/roadmap-next-2026-11-08.md`, and the dispatch history is
`docs/design/dispatch_log.md` (with `dispatch_log_archive_2026-Q4.md` behind it).

## License

See `Intro.txt` and `evidence/logs/attribution.log` for provenance and terms.
