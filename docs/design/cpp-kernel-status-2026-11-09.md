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

**Superseded in part by section 6.** The paragraph below describes the kernel as
it stood when this section was written. As of the full-physics dispatch of
2026-11-09 the kernel implements every branch of `step_explicit` -- PML
(as its two multiplier vectors), the lossy Ampere pair, PEC and the source
term -- and the queue of next steps listed at the end of this section has
been overtaken by events. Read section 6 for the current statement order and
for what is actually covered by a test.

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
* **A claim that the parity test covers the kernel.** Narrowed, not lifted. A
  second golden, `tests/data/cpp_golden_step_v2.npz`, now drives every branch
  at once -- PML multiplier vectors, the lossy Ampere pair, a PEC index array
  and a non-zero source `j` -- and `tests/test_cpp_parity.py` asserts
  bit-identity against it at three steps, against a live Python reference, and
  under four single-branch ablations. What is still *not* covered: the OpenMP
  path (the 4x3x2 golden grid, 133 edges and 98 faces, is far too small for the
  loop to split across threads, so parity on it says nothing about
  parallelism), and any grid other than this one.
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

## 6. Full-physics parity: the second golden (2026-11-09)

Dispatch `cpp-full-physics-and-golden-v2-2026-11-09`. The kernel implements the whole
of `emfit.evolve.step_explicit`, and there is now a golden file that exercises all of
it. This section states the operation order the kernel has to reproduce, then the
measurement that shows each branch is covered, then one finding about perturbation
that came out of writing those tests.

### 6.1 The statement order the kernel reproduces

`emfit/evolve.py`, `step_explicit`, in this exact order -- the kernel's single call
site must match it statement for statement, because bit-parity is a claim about
operation order and nothing else:

| # | evolve.py | statement |
|---|-----------|-----------|
| 1 | :114 | `h -= dt * (inv_m_mu * (C @ e))` -- Faraday, over faces |
| 2 | :115-116 | `pml.damp_h(h, dt)`, i.e. `h *= damp_h` |
| 3 | :117 | `ce = C_tilde @ h` |
| 4 | :118-119 | `ce = ce - j` when a source is present |
| 5 | :120-121 | lossless: `e += dt * (inv_m_eps * ce)` |
| 6 | :125-127 | lossy: `e *= loss_num`; `e += ce`; `e *= loss_den` (in place, three statements, not one fused expression) |
| 7 | :128-129 | `pml.damp_e(e, dt)`, i.e. `e *= damp_e` |
| 8 | :130-131 | `e[pec_idx] = 0.0` |
| 9 | :132 | `return e, h` |

Steps 5 and 6 are alternatives selected by `loss_den is None`; the rest are
independent. The PML enters the kernel as its two multiplier vectors (`damp_e`,
`damp_h`) rather than as a layer object, which is arithmetic-identical because
`PML.damp_e` and `PML.damp_h` are exactly one in-place multiply each
(`emfit/pml.py:716-735`).

### 6.2 The golden and the proof that each branch is covered

`tests/data/cpp_golden_step_v2.npz` (19,981 bytes, 45 arrays, `case='v2-full-physics'`)
is a three-step run on the same 4x3x2 grid (133 edges, 98 faces), `dt =
1.715917382577905e-10`, with a one-cell PML on the x axis, a conductance
distribution (`sigma_value = 1e-3` on 16 edges, so `loss_num` / `loss_den` are
genuinely not 1), a PEC set of 34 edges, and a non-zero source `j` (133 non-zeros,
`max|j| = 3.234434104275188`). It is produced by
`evidence/termination/make_cpp_golden.py --v2` from the Python reference; the script
defaults to v1-only so `--v2` cannot silently rewrite the v1 witness, whose md5 is
still `eac28b6dec9e1b2c2be035f260916fdc`.

Coverage is not asserted by inspection. Each branch was dropped on both sides at
once, three steps were re-run, and the resulting state was compared with the
full-physics golden. A non-zero difference is what proves the branch is load-bearing:

| branch dropped | max abs. diff in `e3` | edges differing | max abs. diff in `h3` | faces differing |
|---|---|---|---|---|
| PML (`damp_e`, `damp_h` -> None) | 1.2947920462999032e+03 | 99/133 | 3.4010702140490938 | 98/98 |
| lossy (`loss_num`, `loss_den` -> None) | 3.5726196920463076e+02 | 99/133 | 0.39619102087747837 | 84/98 |
| PEC (`pec_idx` -> None) | 9.6861258517163694e-04 | 133/133 | 2.3844375086380654e-08 | 92/98 |
| source (`j` -> None) | 1.6661651686870448e+03 | 99/133 | 3.0505545991327114 | 86/98 |

Every arm is non-zero on both `e` and `h`, so no branch is passed in and ignored.
The 99/133 rather than 133/133 is itself explained: the 34 PEC entries are reset to
zero at the end of every step, so they carry no information forward.

The full-physics trajectory grows as the lossy scheme predicts --
`max|e|`: 3.0801234367594699, 1.6056005863383207e+03, 1.6507126810249117e+03,
1.9288326149087627e+03 over steps 0..3; `max|h|`: 2.3850086837869382,
2.3839387119470978, 3.6125923885160729, 4.0167676459807176. Consecutive stored steps
are distinct vectors (133/133 and 98/98 entries change between the first two), so
agreement at tolerance zero is a measurement and not a comparison of an array with
itself.

### 6.3 A one-ULP input perturbation is absorbed here (it was not in v1)

The v1 control -- bump `h0[0]` by one ULP and watch the difference grow -- does
**not** work on the full-physics system. Measured: `h0[0] + 1 ULP` (1.1102230246251565e-16)
leaves the three-step output **bit-identical** to the golden; `+2 ULP` moves `h3` by
7.2e-35; `+1024 ULP` still leaves `e3` unchanged. `e0[0] + 1..256 ULP` likewise.

The reason is the rounding floor, not insensitivity: after one lossy step `|e|` is
about `1e3`, so the absolute resolution of the arithmetic is around `1e-13`, and a
1-ULP change to an input of order 1 is three orders of magnitude below it. The v1
finding therefore does not generalise, and quoting it as if it did would be a false
statement about this regime.

The controls in `tests/test_cpp_parity.py` are adjusted rather than dropped:

* the ULP control moved to the **output** side -- bump `e3[0]` by one ULP and assert
  that the comparator raises and localises it as 1/133;
* the input-side liveness control uses a **coarse** perturbation instead (1e-3
  relative on the largest `e0` entry), which does reach the output.

Neither is weaker than the v1 control: one proves the comparator sees a one-bit
change, the other proves the output depends on the input. What is lost is the
single test that did both at once, and it was lost because the physics says so.

### 6.4 Three findings worth carrying forward

1. **Bit-parity is a property of the build line, not of the algorithm.** It holds
   because the compiler emits no FMA contraction and no reassociation for this
   translation unit. The default target `-march=x86-64` has FMA disabled, which is
   why it holds here. `-march=native` or `-mfma` on an FMA-capable host, or
   `-ffast-math` / `-fassociative-math`, would forfeit it -- and would do so
   silently, as a "9 of 98 entries differ" failure that looks like a kernel bug.
   Anyone who changes the build flags and sees the parity test go red should look
   at the flags first.
2. **The GIL is already released around the kernel call.** `src/bindings.cpp` wraps
   the call in `py::gil_scoped_release`, with the argument arrays kept alive for the
   duration. That was on the earlier "next steps" list; it is done, and the list is
   stale on that point.
3. **Any parallel reduction that splits one row's dot product changes the addition
   order, and therefore forfeits bit-parity.** That is a deliberate trade, not an
   oversight: the current kernel reduces each row sequentially in ascending column
   order, in the same order as scipy's CSR mat-vec. No speed figure exists for the
   parallel variant, and none is claimed -- the only measured parallel number is
   that the OpenMP pragmas are about 50x *slower* at this grid size (section 5).

## 7. Full physics stack and environment verification

Section 6 stated the order; this section states what that order now covers, what
still is not covered, and what the build actually was. No table from section 6 or
6.1 is repeated here.

### 7.1 Four branches, one trajectory, all bit-identical

`tests/data/cpp_golden_step_v2.npz` (md5 `ab6061dc6253189562760155b5d9be91`,
19,981 bytes, 45 arrays, `case='v2-full-physics'`) drives the PML multiplier
vectors, the lossy Ampere pair, a 34-entry PEC index array and a non-zero source
`j` in the same three steps, on the same 4x3x2 grid (133 edges, 98 faces). The
kernel and the frozen file agree at tolerance zero on all three stored steps:
`max |e_cpp - e_golden|` = 0.0 with 0 of 133 entries differing, and
`max |h_cpp - h_golden|` = 0.0 with 0 of 98. The same holds against a live
`step_explicit`. The v1 golden is untouched (md5
`eac28b6dec9e1b2c2be035f260916fdc`), so there are now two independent witnesses,
one per physics level.

### 7.2 The ablation proves each branch is exercised, not merely passed in

Dropping one branch on **both** sides and comparing the shared answer against the
frozen golden, three steps:

| branch dropped | change in `e3` (entries) | change in `h3` (entries) |
|---|---|---|
| PML | 1.2947920462999032e+03 (99/133) | 3.4010702140490938 (98/98) |
| lossy | 3.5726196920463076e+02 (99/133) | 0.39619102087747837 (84/98) |
| PEC | 9.6861258517163694e-04 (133/133) | 2.3844375086380654e-08 (92/98) |
| source | 1.6661651686870448e+03 (99/133) | 3.0505545991327114 (86/98) |

Every arm differs on **both** `e` and `h`, so no branch is passed in and ignored.
Agreement alone could not have shown this — a branch that is supplied and never
read still lets the two implementations agree — which is why the test asserts both
agreement (with the branch gone, on both sides) and difference (from the golden).
The 99/133 rather than 133/133 is explained: the 34 PEC entries are zeroed each
step and carry nothing forward.

### 7.3 One ULP is absorbed by the full-physics system

The v1 non-vacuity control was a single-ULP bump of `h0[0]`
(1.1102230246251565e-16), which reached the output as 8.6153306710912148e-14 after
one step. It does **not** generalise. On the v2 golden `|e|` is about 1e3, so the
absolute rounding floor is about 1e-13, and: `h0[0] + 1 ULP` leaves the three-step
output bit-identical to the golden; `+2 ULP` moves `h3` by 7.2e-35; `+1024 ULP`
still leaves `e3` unchanged (`e0[0]` needs `+1024 ULP` for a 2.8e-17 change).

The controls were rebuilt, not weakened. The ULP control moved to the **output**
side — bump `e3[0]` by one ULP and assert the comparator raises and localises it
(1/133) — and the input-side liveness control is a coarse 1e-3 relative
perturbation on the largest `e0` entry, which does reach the output. The test says
in its own comment why each control is the size it is, because a control that
silently stops controlling is worse than none: the run still looks probed.

### 7.4 Bit-parity is a property of the build line

Bit-identity holds because no FMA contraction and no reassociation are emitted:
GCC's default `-ffp-contract=fast` would fuse multiply-adds, and it did not only
because the default `-march=x86-64` target has FMA disabled. `-march=native`,
`-mfma` or `-ffast-math` would forfeit the claim **silently**, with every test
still green at 1e-12. The compiler and flags therefore belong next to any parity
claim: `/usr/bin/g++` 14.2.0, `-O3 -fopenmp -std=c++17 -shared -fPIC -Wall
-Wextra`, pybind11 3.1.0 headers, `Python.h` at `/usr/local/include/python3.12`,
producing `build/cpp/emfit_core.cpython-312-x86_64-linux-gnu.so` with zero
warnings.

### 7.5 What is still open, stated as open

- **The GIL is already released.** `src/bindings.cpp` wraps the kernel call in
  `py::gil_scoped_release`, so "release the GIL" is not a pending step; anyone
  quoting it as one is quoting a stale list.
- **Parallel reduction is a trade, not free work.** Splitting one row's dot
  product across threads changes the order of `row_dot` and forfeits bit-parity.
  That is a legitimate thing to want, and it must be decided explicitly; there is
  no speed figure for it either way.
- **The OpenMP path is untested.** The 4x3x2 golden grid is far too small for the
  loop to split across threads, so a green run here says nothing about parallel
  execution. The only measured parallel number remains that the pragmas are about
  50x *slower* at this grid size (section 5), on a cgroup limited to `cpu.max`
  50000/100000 = 0.5 CPU.
- **Parity is not physics.** It is measured against a Python reference which is
  itself not validated against an external solver for these arrays.

### 7.6 Host result — operator reported, not reproduced here

The operator reports that `pip install -e .` on his host prints
`Successfully installed emfit-0.1.0.dev0`, and that the parity run there reports
`3 passed`.

What this establishes: the build backend, the wheel and the extension build,
install and import on that host, and three parity tests passed there. What it does
**not** establish: anything about this container, where `pip install -e .` cannot
run at all (`scikit-build-core` and `ninja` are absent, no network); anything about
the v2 full-physics golden, which did not exist when those three tests were the
whole suite (the suite is now 20 tests); or anything about physics — parity is
order, not accuracy. The exact command line and the full pip log are still not on
record, and that omission is the reason this block is labelled rather than quoted
as a result.
