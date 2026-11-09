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
| [`docs/design/EM_SOLVER_LEDGER.md`](docs/design/EM_SOLVER_LEDGER.md) | The open work: nine items, each with a status label and the artefact that decides it. Read before planning anything. |
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
"3 passed" is what the suite reported then, not now; the current suite is 20 tests.
The exact command line and the full pip log are still not on record.

## Test

```
PYTHONPATH=build/cpp python3 -m pytest tests/test_cpp_parity.py tests/test_step_extraction.py -q
```

Expected, at the time of writing: 20 tests, all passing (13 parity — 3 on the v1
golden and 10 on the v2 full-physics golden, the 10 being 7 functions one of which
is parametrised over four single-branch ablations — plus 7 extraction tests).

The parity tests compare the C++ kernel against the pure-Python reference at
tolerance **zero** (`assert_array_equal`, not `allclose`), and the goldens are
frozen snapshots of the Python reference taken before the kernel was written.
Bit-identity is a property of the build line as much as of the code: no FMA
contraction and no reassociation are emitted, which `-ffast-math`, `-mfma` or
`-march=native` would silently destroy.

## Web UI

```
python3 server/poc_app.py                    # serve the browser view
python3 server/poc_app.py --list-keys        # print the dump's keys; numpy only
python3 server/poc_app.py --station 4        # choose the station to show
```

`server/poc_app.py` starts a Trame/pyvista view of a field dump; `--input` selects
the dump, `--station` the station (default 4), `--host` and `--port` the bind
address. The browser view itself is **unverified here**: the Trame/pyvista/VTK
stack is absent from the container and there is no network, so only the numpy-only
`--list-keys` path has been exercised. `requirements-web.txt` names the six
packages that stack needs and pins no versions.

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
  coarse mesh, two-wave, superseded by the fine mesh), not sub-percent. See E1,
  E10 and E11 in
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

See `Intro.txt` and `attribution.log` for provenance and terms.
