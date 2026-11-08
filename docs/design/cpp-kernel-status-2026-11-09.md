# Compiled FIT kernel: where the port actually stands (2026-11-09)

## 1. What is actually done, and what is not

**The C++ has never been compiled.** Not once, not even a syntax-only parse. The
authoring container has no `g++`, no `cmake`, no `pybind11` and no network, so
`src/emfit_core.h`, `src/emfit_core.cpp`, `src/bindings.cpp` and
`src/CMakeLists.txt` are *source that has never been through a compiler*. They
may not even parse. Treat them as a proposal expressed in C++, not as a working
kernel, and do not let anyone quote them as evidence that the port is fast,
correct or close.

What *is* verified, all of it on the Python side:

* **The extraction.** The FIT update now lives in one place,
  `emfit.evolve.step_explicit`, and `FITStepper.step` is a thin wrapper around
  it. `tests/test_step_extraction.py` checks the two agree bit for bit
  (`assert_array_equal`, not `allclose`) for the lossless scheme, three
  consecutive steps, a current source, a lossy `m_sigma` case and a PEC mask,
  plus the in-place/fixed-buffer contract the C++ will have to honour. Its
  literal result:

  ```
  7 passed in 0.43s
  ```

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

* **The parity test exists and skips.** `tests/test_cpp_parity.py` has three
  tests: golden comparison, comparison against a live `step_explicit`, and a
  bookkeeping check that the golden `n_edges`/`n_faces` match the shapes handed
  to the kernel. Observed result here:

  ```
  3 skipped in 0.36s
  ```

  with the skip reason naming the build commands, as it should. A skip is the
  correct outcome. The tests have never executed their comparison bodies, so
  their correctness as tests is itself unverified.

## 2. The CSC finding (the bit-identity premise for Ampere is unproven)

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
