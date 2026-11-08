# Compiled FIT kernel: where the port actually stands (2026-11-09)

## 1. What is actually done, and what is not

**The C++ compiles and runs, in two independent builds.** The earlier version of
this section said the opposite: that no file under `src/` had ever been through a
compiler. That was true when it was written and is now false, so it is replaced
by what was measured.

* **The operator's build, on his host.** He built `src/` with cmake and the build
  reported `[100%] Built target emfit_core`. That is his build on his host, and it
  is recorded here as his report, not as something re-observed from this
  container. It is the first time the extension has ever compiled.

* **An independent build in this container** — plain g++, no cmake, no network:

  ```
  /usr/bin/g++ -O3 -fopenmp -std=c++17 -shared -fPIC -Wall -Wextra \
    -I/workspace/.venv/lib/python3.12/site-packages/pybind11/include \
    -I/usr/local/include/python3.12 -Isrc \
    src/bindings.cpp src/emfit_core.cpp -o build/cpp/emfit_core<EXT_SUFFIX>
  ```

  `EXT_SUFFIX` is the building interpreter's own suffix; here the artefact is
  `build/cpp/emfit_core.cpython-312-x86_64-linux-gnu.so`. Toolchain:
  `/usr/bin/g++` 14.2.0 with OpenMP, `Python.h` at
  `/usr/local/include/python3.12`, pybind11 3.1.0 headers in
  `/workspace/.venv/lib/python3.12/site-packages/pybind11/include`. **Zero
  warnings** under `-Wall -Wextra`.

* **The parity test executes, and passes at tolerance zero.**

  ```
  PYTHONPATH=build/cpp python3 -m pytest tests/test_cpp_parity.py -v
  -> collected 3 items, 3 passed in 0.53s

  PYTHONPATH=build/cpp python3 -m pytest tests/test_cpp_parity.py tests/test_step_extraction.py
  -> collected 10 items, 10 passed in 0.81s
  ```

  The comparison bodies that previously never ran — `3 skipped in 0.36s` was the
  old, then-correct outcome — now run against the compiled kernel. Kernel against
  the Python reference, all three stored steps: `max|e_cpp - e_py| = 0.0` with
  **0 of 133** entries differing, `max|h_cpp - h_py| = 0.0` with **0 of 98**
  differing, and the same two figures for kernel against the frozen golden arrays.
  The assertion is `assert_array_equal` — tolerance zero, not `allclose`.

What is verified now, on both sides:

* **The extraction.** The FIT update now lives in one place,
  `emfit.evolve.step_explicit`, and `FITStepper.step` is a thin wrapper around
  it. `tests/test_step_extraction.py` checks the two agree bit for bit
  (`assert_array_equal`, not `allclose`) for the lossless scheme, three
  consecutive steps, a current source, a lossy `m_sigma` case and a PEC mask,
  plus the in-place/fixed-buffer contract the C++ has to honour. It is 7 of the 10
  items in the combined run reported above.

* **The golden vectors.** `evidence/termination/make_cpp_golden.py` runs (after
  one fix: it now puts the repository root on `sys.path` so it works as a plain
  script) and writes `tests/data/cpp_golden_step.npz`, **16 551 bytes (16.2
  KiB)**, 4x3x2 cells, `h = 0.1`, seed 20261109, three steps. The 32 stored
  keys, read back with `np.load(...).files` rather than typed from memory:

  ```
  ['e0', 'h0', 'C_data', 'C_indices', 'C_indptr', 'C_shape', 'C_tilde_data',
   'C_tilde_indices', 'C_tilde_indptr', 'C_tilde_shape', 'C_tilde_csr_data',
   'C_tilde_csr_indices', 'C_tilde_csr_indptr', 'inv_m_mu', 'inv_m_eps', 'dt',
   'n_edges', 'n_faces', 'nx', 'ny', 'nz', 'lx', 'ly', 'lz', 'seed',
   'n_steps', 'e1', 'h1', 'e2', 'h2', 'e3', 'h3']
  ```

  (`n_edges = 133`, `n_faces = 98`, `dt = 1.715917382577905e-10`, index arrays
  `int64`, everything else `float64`.)

* **The pass is not vacuous.** Three controls, all measured. (i) Consecutive
  stored steps differ at **133/133** `e` entries and **98/98** `h` entries, so the
  stored arrays are not copies of one another. (ii) A single-ULP perturbation of
  `h0[0]` (delta `1.1102230246251565e-16`) is **not** absorbed: `max|e - golden|`
  becomes `8.6153306710912148e-14` after one step (1 of 133 entries) and
  `5.6843418860808015e-13` after three (15 of 133). (iii) Those perturbed figures
  are identical from the C++ kernel and from the pure-Python reference, so both
  implementations amplify the same perturbation the same way — a kernel that
  never read its input, or a comparison of an object with itself, could not
  produce them.

* **The binding defect is diagnosed, not papered over.** The operator's
  "incompatible function arguments" error came from `C_shape` and `C_tilde_shape`
  being declared `std::vector<long>` **without** `#include <pybind11/stl.h>`:
  those two parameters had no caster at all, so every call raised that error
  whatever arguments were passed, and the caller's dtype was never the issue. The
  operator's diagnosis was correct. The trap, recorded because it nearly hid the
  cause: pybind11 appends the "Did you forget to `#include <pybind11/stl.h>`"
  hint to *any* failed conversion, so the hint alone proves nothing; the proof was
  the old `.so` rendering its own signature with
  `std::vector<long, std::allocator<long> >` in it. The fix adds the include,
  makes both shapes `const std::vector<py::ssize_t>&`, and takes every array
  parameter as `const py::object&` validated by hand — explicit dtype,
  contiguity and writeability checks, with errors naming the parameter and the
  received dtype/contiguity/writeability. The GIL-release block and the kernel
  call are byte-identical to before. One correction to what the old comment
  claimed: it said the binding performed "no silent conversion", which was not
  quite true, because a `py::array_t` requested with `c_style` flags and no
  `forcecast` is strict about dtype but **not** about layout and can still copy
  to satisfy a layout flag. The explicit checks are what make the claim true; the
  flags alone never did.

* **The CSC/CSR premise of section 2 is settled by measurement**, not by argument.
  `scipy`'s `Csc @ h` and `Csr @ h` are bit-identical (0 differing entries); a
  hand CSC-order walk and a hand CSR-order walk are bit-identical; and the kernel
  fed CSR agrees bit-for-bit with the Python reference fed the CSC view, at every
  step. Section 2 should now be read as the premise and the risk it carried, not
  as the current status. The explanation that accompanies the measurement — a CSC
  product visits columns ascending and rows ascending within a column, so each
  output row accumulates in ascending-column order, the same order a CSR row walk
  uses — accompanies it and does not substitute for it.

* **Packaging is written but unexercised.** `pyproject.toml` uses the
  `scikit_build_core.build` backend with `requires = ['scikit-build-core>=0.8']`
  and deliberately does **not** list `pybind11`: CMake finds it with
  `CONFIG QUIET`, and `src/CMakeLists.txt` makes the extension **optional**,
  emitting a `WARNING` and returning early when pybind11 is absent.
  `[tool.scikit-build]` sets `cmake.source-dir = 'src'`,
  `wheel.packages = ['emfit']` and `editable.rebuild = false`. **Not verified:**
  `scikit-build-core`, `ninja` and `scikit-build` are not installed in this
  container, so `pip install -e .` has never been run here; the editable and
  wheel paths are unexercised, and so is `editable.rebuild = false`.

What the measurements above cover is a small grid and a narrow slice of the
branches. Section 5 lists what to distrust, including the parts the numbers above
do *not* cover.

## 2. The CSC finding (settled by measurement on 2026-11-09; kept as the record of the risk)

It is now settled: section 1 records the measurements. The section is retained because it states precisely which premise was at risk and why it could not be argued by inspection, and a future reader changing the kernel's matrix layout needs that reasoning again.

`emfit.operators.CellComplex.curl_dual()` returns
`self.curl().transpose(copy=False)`. That is **not a CSR matrix**: transposing a
CSR matrix without copying gives a **CSC view that shares `C.data`** (the module
says so in a comment, and the generator confirms it at run time:
`scipy.sparse._csc.csc_matrix`, format `csc`). So the Ampere update in the
reference is a CSC product, while the compiled kernel I wrote consumes a CSR row
loop and the golden file accordingly stores a `tocsr()` copy as
`C_tilde_csr_*`.

Consequence, stated plainly: **a CSR row loop cannot be assumed to accumulate in
the same order as the CSC product the reference actually performs**, so the
"bit-identical" claim is solid for the Faraday half (genuine CSR on both sides)
and *unverified* for the Ampere half.

The reasoned expectation — and it is only an expectation — is that they agree: a
CSC product walks column by column and scatters each entry into its output row,
so each output element still receives its contributions in ascending column
order, which is the order a CSR walk of the transposed matrix would use. Plausible,
therefore, but not proof: nothing about that argument has been checked against
floating-point reality. **The test decides, not the argument.** That is also why
the golden file deliberately stores *both* the CSC-as-is arrays and a `tocsr()`
copy, so a parity failure can be attributed to summation order rather than
mistaken for a typo, and why `test_cpp_matches_live_python_kernel_bit_for_bit`
feeds `step_explicit` the CSR copy: if that test passes and the golden one fails,
the blame is the CSC/CSR order, and nothing else.

## 3. What the operator runs on the host

In order, from the repository root, on a machine with a compiler and network:

```bash
python3 -m pip install pybind11 cmake
cmake -S src -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j
PYTHONPATH=build python3 -m pytest tests/test_cpp_parity.py -q
```

`pybind11_add_module` writes into the build directory it belongs to, so the
extension lands as `build/emfit_core.cpython-312-x86_64-linux-gnu.so` (the
suffix follows the host's Python). The test imports `emfit_core`, so `build/`
must be on `PYTHONPATH` — the line above does that; if the `.so` is easier to
find with `find build -name 'emfit_core*.so'`, copy it next to the sources
instead and skip the `PYTHONPATH` prefix. Note that `src/CMakeLists.txt` forces
`-O3` itself, so `-DCMAKE_BUILD_TYPE` is housekeeping rather than the thing that
sets the optimisation level.

First expected failure mode: if the golden comparison reports a last-bit
mismatch on **`h`**, that is the CSC/CSR order question of section 2. It is not
a physics error, and the fix is to make the two summation orders agree (feed the
kernel the CSC arrays and add a CSC kernel, or canonicalise on one layout),
never to loosen the test to `allclose`. If the mismatch is on `e` and the live
Python comparison also fails, the Faraday loop or the elementwise ordering is
wrong and ordinary debugging applies.

## 4. What is in the kernel today, and the order of the next steps

`src/emfit_core.cpp` implements the **lossless core only**: the Faraday
mat-vec (`h -= dt * inv_m_mu * (C e)`) and the Ampere mat-vec
(`e += dt * inv_m_eps * (C_tilde h)`), each as a per-row sequential
accumulation in ascending column order, parallel over independent rows with
`schedule(static)`, no reductions and no atomics. There is **no PML, no PEC
reset, no lossy/conductance branch, no loads**, and the only source support is
the optional `j` vector. Anything that today's `step_explicit` handles beyond
those two lines is simply absent from the C++ and would have to be added before
the compiled path could replace the Python one for any real problem.

Next steps, in this order and for these reasons:

1. **PML multipliers.** Two constant per-edge and per-face vectors, `e *= f`,
   `h *= g`, no auxiliary state, no summation, so exactness is trivial and the
   win is immediate for every absorbing-boundary run. Cheapest real capability.
2. **Lossy / load conductance branch.** `e *= loss_num; e += ce; e *= loss_den`
   — elementwise only, no accumulation order question, and it unlocks board
   runs with loads.
3. **Sources.** Wire the existing optional `j` properly and add whatever driving
   forms the Python side supports.
4. **Stencil optimisation** (writing to `h`/`e` block-wise instead of gathering
   through `indptr`), behind a flag and tested against the mat-vec port to a
   *stated tolerance*, not bit-identically: the moment the summation order
   changes, the bit-identity promise is gone, and pretending otherwise is how a
   test suite stops meaning anything.
5. **Subgridding** last, because it changes the data layout itself.

## 5. What would make me distrust this

* **A parity pass on a grid too small to use more than one OpenMP thread.** Then
  the run says nothing about the parallel path — and the 4x3x2 golden grid
  (98 faces) is *already* such a grid: `schedule(static)` over 98 rows on a
  many-core host still exercises only a few threads, so a green result there
  would not be a green result for a real mesh. Repeat on something with hundreds
  of thousands of rows before believing anything.
* **A golden file regenerated after the C++ was written, or tweaked to match
  it.** The golden data must be a snapshot of the Python reference, taken
  before the kernel was touched; regenerating it to make a red test go green
  destroys the only independent witness.
* **`-ffast-math` anywhere in the build.** It permits reassociation and would
  quietly, invisibly destroy the bit-identity claim while every test still
  "passed" at 1e-12. `src/CMakeLists.txt` deliberately does not set it; if it
  ever appears, the claim is dead.
* **A pass whose reported worst difference is exactly zero on the first run.**
  That is more likely to mean the comparison did nothing — wrong buffer aliased,
  both arrays the same object, a copy where a computation was expected — than to
  mean success. The first thing to check after a suspiciously clean pass is that
  the kernel was actually called on the data that was compared.
* **A green run that nobody can reproduce on a second host**, or one quoted from
  a machine where `emfit_core` came from an older checkout. Record the commit
  and the `.so`'s mtime with the result.
* **A claim that the parity test covers the kernel.** The golden file stores no
  source array `j` at all, so `step_explicit`'s source-term branch has **zero**
  parity coverage; the PML, lossy/load and PEC branches likewise. What passed
  bit-identically is the source-free, lossless, non-PML step — one branch of
  several — and nothing in the numbers above says anything about the others.
* **Bit-parity read as evidence of accuracy.** The golden trajectory is
  oscillatory and large: `max|e|` runs 3.0801234367594699 -> 2218.6970420430825 ->
  1182.5905231289953 -> 1887.1900574751446 while `max|h|` stays near 2.4.
  Bit-parity on a growing trajectory is a strong test of operation *order* — the
  single-ULP control shows a 1.1102230246251565e-16 perturbation amplified to
  5.6843418860808015e-13 in three steps — and it is not evidence of numerical
  accuracy. Do not quote it as either.
* **Any speed figure, and in particular any speedup.** The OpenMP pragmas are
  untested as a speedup and, measured here, about **50x slower** at this grid
  size: 1 thread 5,926 ns/call, 2 threads 49,252, 4 threads 124,111, 8 threads
  353,937, over the 98/133 iterations with 392 nonzeros. `OMP_WAIT_POLICY=passive`,
  `GOMP_SPINCOUNT=0` and `OMP_PROC_BIND=close` do not rescue it. The container's
  cgroup `cpu.max` is 50000/100000 = 0.5 CPU, which inflates the absolute times
  and makes any cpu/wall ratio meaningless as a speedup metric. No speed is
  claimed anywhere in this document, and none should be quoted from it.
* **Parity treated as physics.** Parity is measured against the Python reference,
  which is itself not validated against an external solver for these arrays. It
  establishes that the kernel performs identical operations in identical order;
  it does not establish that those operations give the right answer.
