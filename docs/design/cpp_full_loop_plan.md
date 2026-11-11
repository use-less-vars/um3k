# Moving the FIT time loop into C++: the boundary as it stands (E3 preparation)

**Status.** Planning document, proposal only. No code is changed by this dispatch, no
new kernel is built, and no speedup is claimed anywhere. Everything asserted in the
present tense about existing code carries a `file:line` citation that was resolved
against the working tree; everything in the future or imperative mood is a proposal
and is marked as one. The single exception is a set of timings measured in the
development container while writing this, reported in section 5 with the grid size
attached, because a number without a grid size is a rumour.

The ledger's E3 row is `UNVERIFIED` with no speed figure and an explicit instruction
that none may be claimed before a large-mesh measurement (`docs/design/EM_SOLVER_LEDGER.md:28`).
This document is the preparation that row is missing: it establishes what the boundary
actually is today, so that the measurement in section 5 can be designed before any
work is commissioned.

---

## 1. Premise correction

Two things that are widely believed about this repository are false. Both are load
bearing, and both change what E3 is.

**(i) `build/cpp/emfit_core.cpp` does not exist.** `build/cpp/` contains exactly one
file, the compiled `emfit_core.cpython-312-x86_64-linux-gnu.so`. The C++ sources live
in `src/`: the build names its two translation units explicitly, `bindings.cpp` and
`emfit_core.cpp` (`src/CMakeLists.txt:43-46`), with the include directory set to the
source directory rather than to any build directory (`src/CMakeLists.txt:47`). The
`build/cpp` path in the documentation is the *output* directory of the standalone
build (`src/CMakeLists.txt:4-6`), and the parity test's hand-written compile line
writes its output there as well (`tests/test_cpp_parity.py:83-84`). So `build/cpp` is
an artefact directory, not a source directory; there is nothing in it to "extend".

This matters because "extend the C++ path" reads like a change confined to a file
under `build/`, i.e. to generated output. Every change this plan proposes is a change
to `src/` and to `emfit/`, and lands in review like any other code.

**(ii) There is no production Python -> C++ boundary.** `pyproject.toml:55-56` states
it directly: "`emfit/` never imports emfit_core, so the pure-Python package is
unaffected either way." That is not a comment about a partially wired backend; it is
the current state. `emfit/evolve.py:48-50` imports numpy and `C0` from
`emfit.materials`, nothing else, and the time step is executed by the Python function
at `emfit/evolve.py:248-251`. The only importer of `emfit_core` in tracked code is the
parity test (`tests/test_cpp_parity.py:91`), and it is written to *skip* rather than
fail when the module is absent (`tests/test_cpp_parity.py:96-103`). The package is
declared to be shippable without the extension at all (`pyproject.toml:5`,
`pyproject.toml:41-57`).

Consequently the compiled kernel is, today, a **test-only parity oracle**. It has no
numpy fallback because there is nothing for it to fall back *from*: the Python kernel
is not the fallback path, it is the only path.

**Therefore E3 is not "extend the C++ path".** It is two deliverables in sequence:
create the call path that does not exist, then move work across it, one item at a
time, with the Python path remaining the reference and the fallback throughout. A plan
that starts by moving the loop has nothing to move it into.

---

## 2. What C++ does today

One function is exported. Not a class, not a loop, not a stepper.

| Item | Declared at | What it is |
|---|---|---|
| `emfit_core.step_explicit` | `src/bindings.cpp:302` | the module's only `m.def` |
| its argument list | `src/bindings.cpp:167-180` | 19 parameters, all positional except the six trailing optionals |
| its defaults | `src/bindings.cpp:309-311` | the six optionals default to `py::none()` |
| the numerical function | `src/emfit_core.h:53-66` | `void`, raw `double*`, mutates `e` and `h` |
| `Csr` | `src/emfit_core.h:15-21` | three raw pointers plus `n_rows`, `n_cols`; no ownership, no destructor |
| module docstring | `src/bindings.cpp:290-301` | states the statement order and the parity status |
| GIL | `src/bindings.cpp:279-285` | released around the kernel call |

The header is deliberately Python-free (`src/emfit_core.h:3-5`), so a future unit test
of the numerics would not need CPython headers; the binding is a separate translation
unit (`src/CMakeLists.txt:43-46`). The kernel body is one pass over the faces and one
pass over the edges — Faraday (`src/emfit_core.cpp:80-87`), PML damping of `h`
(`src/emfit_core.cpp:89-96`), Ampere in one of two branches with the source folded in
(`src/emfit_core.cpp:98-124`), PML damping of `e` (`src/emfit_core.cpp:126-134`), and
the PEC reset last (`src/emfit_core.cpp:136-142`).

**What is not in C++**, in full, because the omission defines the size of the job:

| Not in C++ | Lives today at |
|---|---|
| Grid and operator assembly (`C`, `C_tilde`, material diagonals) | `emfit/evolve.py:178-179`, `emfit/evolve.py:190-191` |
| PML coefficient construction | `emfit/pml.py:402` (class), `emfit/pml.py:662` (`multipliers`) |
| Source waveform and injection | `emfit/evolve.py:59`, `emfit/evolve.py:321`, called at `emfit/evolve.py:310` |
| Ports / terminal functionals | `emfit/terminations.py:26`, `emfit/terminations.py:91`, `emfit/terminations.py:111` |
| RLC state and its coupled solve | `emfit/terminations.py:232`, `emfit/terminations.py:291` |
| DFT / probe accumulation | `emfit/ports.py:564`, per-step sampling at `emfit/evolve.py:313-314` |
| S-parameters and de-embedding | not in this module; see the coupling document named in section 6 |
| Energy accounting | `emfit/evolve.py:259`, `emfit/evolve.py:269` |
| The time loop itself | `emfit/evolve.py:283-317` |
| The `FITSystem` adapter and its `dt` validation | `emfit/evolve.py:353-372` |
| `Leapfrog`'s source-vector reuse | `emfit/evolve.py:374-375` |

Stated as a ratio: the kernel that exists is one statement sequence of six operations;
everything that decides *which* arrays it gets, *when* it is called, and what is done
with the result is Python.

One housekeeping fact worth recording, because it will confuse the next reader:
the status text inside the C++ still says the PML, lossy, PEC and source branches have
no committed parity test (`src/emfit_core.cpp:4-8`, `src/bindings.cpp:48-55`,
`src/bindings.cpp:295-301`), while `tests/test_cpp_parity.py:416` and
`tests/test_cpp_parity.py:494` now exercise exactly those branches against
`tests/data/cpp_golden_step_v2.npz` (`tests/test_cpp_parity.py:74`). The **code** is
stale, the *test* is current: 13 tests pass against the current `.so`. Two sources of
truth for status is a hazard in its own right (section 9).

---

## 3. What Python does today

`emfit/evolve.py` is 375 lines and has one public entry point per concept. The surface
a C++ loop would have to displace:

| Symbol | Line | Role |
|---|---|---|
| `__all__` | `emfit/evolve.py:52-53` | five names: `ricker`, `cfl_dt`, `step_explicit`, `FITStepper`, `RickerSource`, `Leapfrog` |
| `ricker` | `emfit/evolve.py:59` | waveform, scalar in, scalar out |
| `cfl_dt` | `emfit/evolve.py:69` | stability limit from the grid; scalar, called once |
| `step_explicit` | `emfit/evolve.py:84` | the kernel; mutates `e`, `h`; returns them |
| `FITStepper` | `emfit/evolve.py:136` | glass box around `(e, h, time, n)` |
| `FITStepper.__init__` | `emfit/evolve.py:175` | derives `inv_m_eps`, `inv_m_mu`, `dt`, `loss_num`/`loss_den`, `pec_idx` |
| `FITStepper._index_array` | `emfit/evolve.py:227` | mask -> index array conversion, once |
| `FITStepper.step` | `emfit/evolve.py:239` | one call through to `step_explicit`, then `time += dt`, `n += 1` |
| `FITStepper.energy` | `emfit/evolve.py:259` | the mixed-state invariant |
| `FITStepper.energy_components` | `emfit/evolve.py:269` | the same, split into three named terms |
| `FITStepper.run` | `emfit/evolve.py:283` | the loop: source -> step -> probe -> callback |
| `RickerSource` | `emfit/evolve.py:321` | callable returning a full `j` vector for a time |
| `Leapfrog` | `emfit/evolve.py:353` | adapter over a pre-assembled `FITSystem` |

The kernel's statement order is frozen. It is written out in the docstring
(`emfit/evolve.py:88-97`), restated as a numbered list in the C++ header
(`src/emfit_core.h:26-35`), and implemented once in Python
(`emfit/evolve.py:114-131`). The correspondence, statement by statement:

1. **Faraday** — `h -= dt * (inv_m_mu * (C @ e))`, one expression, `emfit/evolve.py:114`.
2. **PML damping of `h`**, before the dual curl — `emfit/evolve.py:115-116`.
3. **Dual curl minus the source** — `ce = C_tilde @ h`, then `ce = ce - j` if `j` is
   given: `emfit/evolve.py:117-119`.
4. **Ampere**, lossless branch `e += dt * (inv_m_eps * ce)` (`emfit/evolve.py:121`) or
   lossy branch as three separate in-place statements (`emfit/evolve.py:125-127`),
   chosen on `loss_den is None` (`emfit/evolve.py:120`).
5. **PML damping of `e`**, after Ampere and before PEC — `emfit/evolve.py:128-129`.
6. **PEC reset** — `e[pec_idx] = 0.0`, last — `emfit/evolve.py:130-131`.

**This order is the parity contract, not a style preference.** A fused kernel — `h -=
dt * inv_m_mu * ce` with the multiply reassociated, or the lossy branch collapsed into
`e = (e*loss_num + ce)*loss_den` as a single expression — computes a different sequence
of roundings, hence a different double. The C++ file says so in its own comments
(`src/emfit_core.cpp:10-22`, `src/emfit_core.cpp:24-35`), and the build refuses
`-ffast-math` for the same reason (`src/CMakeLists.txt:19-21`). Once the trajectories
differ, parity stops being `assert_array_equal` and becomes `allclose(tol)`, at which
point two things happen: the tolerance has to be justified (and will be re-tuned
whenever the grid changes), and every committed evidence artefact produced before the
change is no longer comparable to one produced after it, because nobody can say whether
a 1e-9 difference is the reordering or a physics bug. Bit-identity is not a fetish
here; it is what makes an evidence file re-checkable.

---

## 4. The boundary as it is

**Allocation and ownership.** Nobody in C++ allocates. `e` and `h` are allocated by
`FITStepper.__init__` (`emfit/evolve.py:221-222`), handed across as writable arrays
(`src/bindings.cpp:195-196`), and mutated in place through `mutable_data()`
(`src/bindings.cpp:281`). The kernel's signature says the same thing in C++ terms:
`double*` for the two it writes, `const double*` for every coefficient and for `j`
(`src/emfit_core.h:53-66`). The binding holds each array as a named local so that no
pointer can outlive the object owning its memory across the released-GIL section
(`src/bindings.cpp:226-231`). There is no scratch buffer on either side; the kernel
fuses the scaling into the update precisely so it needs no temporary
(`src/emfit_core.cpp:50-52`).

**What may arrive.** The binding is strict on purpose and does its own checks against
`py::object` rather than relying on overload resolution (`src/bindings.cpp:3-25`). The
rules, all enforced before anything numeric runs:

- dtype exactly float64 (`src/bindings.cpp:103-105`), index arrays exactly int64
  (`src/bindings.cpp:123-125`);
- C-contiguous, with the error text naming the remedy (`src/bindings.cpp:106-108`);
- writeable when the kernel writes through it (`src/bindings.cpp:109-111`), where the
  message names the function that updates in place;
- length checks against `n_edges` / `n_faces` derived from the CSR shape
  (`src/bindings.cpp:206-209`);
- CSR consistency: `data` and `indices` the same length, `indptr` of `n_rows + 1`
  (`src/bindings.cpp:148-155`). Column indices are **not** range-checked or
  sort-checked — the kernel trusts scipy's invariant, which the header states
  (`src/emfit_core.h:13-14`).

There is no forcecast (`src/bindings.cpp:5-9`), so a float32 or non-contiguous array is
refused rather than silently copied. That is the difference between a parity test that
means something and one that passes because both sides were quietly converted: an
`ascontiguousarray` copy would double peak memory and a float32 cast would change every
digit.

**Absent branches.** `dt` crosses by value (`src/bindings.cpp:175`). The six optional
arrays arrive as `py::none()` (`src/bindings.cpp:215-224`), which the kernel sees as
`nullptr` and treats as a no-op, matching Python's `if pml is not None` /
`if j is not None` guards (`emfit/evolve.py:115`, `emfit/evolve.py:118`,
`emfit/evolve.py:128`, `emfit/evolve.py:130`). One asymmetry is refused rather than
inherited: `loss_den` without `loss_num` raises, because Python's branch selection
reads both and the kernel would dereference a null (`src/bindings.cpp:242-250`).

**Exception safety.** Every validation happens before `py::gil_scoped_release`
(`src/bindings.cpp:279`), so a rejected call cannot have mutated `e` or `h` — a
half-applied step is not a reachable state. Inside the release block the kernel
allocates nothing, throws nothing, and calls nothing that can do either
(`src/emfit_core.cpp:63-143`), so the released-GIL section cannot unwind. That is a
property of the *current body*, not a guarantee the boundary provides: a future C++ loop
that allocates or calls into Python would have to catch inside the release block, before
the unwinding reaches Python where the GIL is being re-acquired.

**`j` semantics.** `j` is read, never written (`src/emfit_core.h:66`). Python computes
`ce = C_tilde @ h` into a fresh array and then subtracts (`emfit/evolve.py:117-119`);
C++ folds the subtraction into the row accumulation, before the scaling
(`src/emfit_core.cpp:106-108`, `src/emfit_core.cpp:117-119`). Same operations, same
order, one fewer temporary — which the v2 golden with a live source branch confirms is
bit-identical (`tests/test_cpp_parity.py:416`).

**Aliasing is decided nowhere.** Nothing in the binding checks whether `e` and `j` are
the same array, or overlap, or whether `h` aliases a coefficient vector. Today that
contract exists only in usage: the parity test builds each array separately from the
`.npz` (`tests/test_cpp_parity.py:169-184`). It is not in a loader, not in a dataclass,
not in a docstring that a caller would read. Any wrapper introduced in Phase 0 has to
state it explicitly — *the two field arrays, the source, and every coefficient array are
distinct, non-overlapping, correctly-shaped buffers* — and preferably assert it for one
release, because the failure mode (a source view into `e` with a non-zero offset) is
silent and small.

---

## 5. Why this is not yet a speed path

`step_explicit` is 100% array-level. There is no per-cell Python loop anywhere in
`emfit/evolve.py:114-131`: two `scipy.sparse` mat-vecs and a handful of elementwise
passes. Everything expensive already runs in compiled code — scipy's CSR kernel and
numpy's ufunc loops. What a C++ loop can therefore save is **only** the per-step Python
dispatch, the interpretation of six statements, and the temporaries those statements
allocate. That is a small and grid-size-dependent share, and it is the thing to
measure before spending anything.

Measured here, in this container, on the golden grid (4x3x2, 133 edges, 98 faces, 392
non-zeros per operator), lossless branch, best of five batches of 2000:

| Operation | Per call |
|---|---|
| Python `step_explicit` (whole step) | 8.84 us |
| `scipy` `C @ e` | 2.46 us |
| `scipy` `C_tilde @ h` | 2.53 us |
| the two mat-vecs together | 4.99 us = 56% of the step |
| residual: dispatch, elementwise passes, allocation | 3.85 us = 44% of the step |
| the compiled kernel, same grid, same arguments, `OMP_NUM_THREADS=1` | 3.71 us per call |
| the same kernel, thread team left at its default | 291 us per call |

Thread count, not grid size, sets the kernel's cost, so both kernel rows are quoted. An
earlier revision of this table carried a single kernel figure of 1,755.69 us per call;
that number is **retracted** — it did not reproduce here under any thread count, and the
worst reading obtained with the thread team left at its default is 291 us. The whole-step
timer is the unstable one as well: repeated batches alternate between about 8.8 us and
about 33 us as the cgroup throttles a 0.5-CPU slice, so the two mat-vec times, which do
not move, are the figures to trust, and the 44% is a best-batch ratio.

Two readings, both of which have to be stated together or neither is honest:

1. **44% is an upper bound that exists only at toy size.** The mat-vec term grows with
   the non-zero count; dispatch does not. On a mesh with 10^5 edges the mat-vec terms
   dominate and the saveable share falls. Quoting 44% as the opportunity at production
   size would be exactly the kind of extrapolation this ledger refuses
   (`docs/design/EM_SOLVER_LEDGER.md:28`).
2. **The compiled kernel's cost is set by its thread count, not by its arithmetic.**
   At one thread it is the *faster* of the two paths at this size; left at its default
   thread count it is about 33x the Python step, and the cause is visible in the source:
   five `#pragma omp parallel for` regions per call (`src/emfit_core.cpp:83`, `:92`,
   `:103`, `:114`, `:130`), each paying a thread-team launch for 392 multiply-adds, on a
   cgroup that allows 0.5 CPU. This is the same effect the ledger already records as
   thread-count scaling from 5,926 ns at one thread to 353,937 ns at eight
   (`docs/design/EM_SOLVER_LEDGER.md:28`); re-measured here the ladder reproduces in
   shape and runs about 2.4x faster in absolute terms — 3,770 ns, 19,620, 54,290,
   145,590 at 1/2/4/8 threads and 351,450 at twelve. It says nothing about 10^5 edges,
   where the arithmetic finally dwarfs the launch — but it does say that a plan whose
   first act is to put a call across the boundary will make small and medium cases
   *slower* unless that call is single-threaded, and that the thread count has to be
   settled before any size scaling is measured.

**The threshold, stated as a number so it can be argued with (proposal).** E3 should
proceed past the measurement only if, on a grid with at least 10^5 edges:

- the non-mat-vec share of the per-step wall time exceeds **20%**, i.e.
  `t_step - (t_C + t_C_tilde) > 0.20 * t_step`; **and**
- the absolute saving implied by that share over a representative study exceeds **10%**
  of that study's wall time; **and**
- the per-call fixed cost of the compiled path is below the Python step time it
  replaces — at one thread that now holds at toy size (3.71 us against 8.84 us), so
  this gate has to be taken at target size with the thread count pinned, not read off
  this grid.

If those fail, the correct output of E3 is a recorded negative result, not a port.

**Packaging cost.** There is no fallback to keep, so Phase 0 has to *create* one, and
the honest shape of it is a dispatch on a strategy flag with the Python path as the
default. That is cheap in code and expensive in test time: every physics test that
matters has to run twice. And memory is not free: the container's cgroup cap is 512 MB
(`/sys/fs/cgroup/memory.max`), so a second copy of the field arrays held across a loop,
or a CSR copy held on both sides of the boundary, is a real budget line on a large mesh,
not a rounding error.

---

## 6. The target boundary, in dependency order

Ordered by what can be moved without changing anything else. Each item states what
would cross, what it replaces, what breaks if it is done out of order, and the risk.
The order is not negotiable in one respect: (a) before (b) before (c) before (d)/(e),
because each later item needs the loop that the earlier one establishes.

**(a) The time loop.** What crosses: `nsteps`, the probe index array, and the ordering
of four operations. What it replaces: the `for` at `emfit/evolve.py:309`, whose body is
`j = source(self.time)` -> `self.step(j)` -> probe sample -> `callback(self)`, in that
order and documented as that order (`emfit/evolve.py:286-287`). If this is done after
(b), the source cannot be called at all; if after (c), the RLC state has no loop to live
in. Risk: the loop owns the definition of "one step" (`self.time += self.dt`,
`self.n += 1`, `emfit/evolve.py:254-255`), so a C++ loop must either return those or
take a step count and own them; both are defensible, and one must be chosen before any
code is written.

**(b) Source injection.** What crosses: an edge-index array, an amplitude, a waveform
identifier, `t0`, `fmax` — or, for arbitrary callables, nothing crosses and the loop
cannot move. What it replaces: `j = source(self.time) if callable(source) else None`
(`emfit/evolve.py:310`) and the `RickerSource.__call__` body that zeroes a reused buffer
and fills the chosen edges (`emfit/evolve.py:341-345`). Breaks if out of order: there is
no loop to inject into. Risk: `source` is duck-typed as *any* callable
(`emfit/evolve.py:294-295`), and studies pass closures. A C++ loop can absorb the
Ricker case; it cannot absorb an arbitrary Python callable without a per-step callback,
which section 7 forbids.

**(c) Loads and ports — the hard one.** What crosses: the port's edge bundle, the
per-edge capacitances, `R`, `L`, `C`, and the state triple `(i, v_c, v)`. What it
replaces: `step_rlc` (`emfit/terminations.py:291`) and the state object
(`emfit/terminations.py:232`). Two properties make this different in kind from (a) and
(b):

- the state contract is **immutable**: "A step never mutates a state; `step_rlc`
  returns a new one" (`emfit/terminations.py:259-261`), and the field update is supplied
  as a keyword-only callable `advance=(e, h, dt) -> (e*, h*)` that the caller composes
  (`emfit/terminations.py:245-252`, stored at `emfit/terminations.py:285`);
- each coupled step assembles and solves a **dense n_t x n_t** terminal block
  (`emfit/terminations.py:294-297`).

So a C++ loop has two choices, and only two. Either it calls back into Python once per
step to obtain `(e*, h*)` from `advance` — which reintroduces exactly the crossing the
loop was built to remove, and adds an object round-trip to a step whose arithmetic is a
handful of terminals — or it moves the RLC state machine too, keeping the immutability
as a return-by-value in C++. **Proposal: move it.** The reasons are concrete rather than
aesthetic: the immutable contract translates to a returned struct with no semantic
loss; the per-step arithmetic on the circuit side is small (n_t is a port's terminal
count, not the mesh), so its cost cannot justify a Python hop; and both port functionals
are plain linear algebra over an index bundle (`emfit/terminations.py:91`,
`emfit/terminations.py:111`), with no Python object semantics to preserve. The port/RLC
derivation, the sign convention and the three impedance names are not re-derived here —
they are covered in `docs/design/spice_adapter_scope.md:1`, which is the document to
read with this one.

What breaks if (c) is attempted before (a): the composition `advance` currently *is* the
Python step, so without a loop there is nothing to compose inside. Risk: the coupling
test surface is the densest in the repository (`tests/test_terminations.py`, 11 tests
over 605 lines), and a C++ state machine that returns a struct will not be
signature-compatible with it; the tests would have to keep testing the Python path
while a parallel C++ path is checked against it.

**(d) DFT and probe accumulation.** What crosses: the probe index array and the
frequency list; in a full move, the complex accumulator too. What it replaces: the
per-step sampling at `emfit/evolve.py:313-314` and, for the study path, the accumulator
at `emfit/ports.py:564` whose phase is taken from the step index rather than from an
accumulated clock (`emfit/ports.py:571-573`). Breaks if before (a): there is no loop to
sample from. Risk: the index-not-clock decision is a numerical guarantee; a C++ loop
that accumulates `t += dt` and computes the phase from it reproduces the bug the Python
code documents and avoids. If a loop reports `n` and lets Python accumulate, this item
is cheap; if it absorbs accumulation, it must reproduce the index convention exactly.

**(e) Energy accounting.** What crosses: nothing but the field arrays and the material
diagonals. What it replaces: `energy` (`emfit/evolve.py:259`) and `energy_components`
(`emfit/evolve.py:269`). Breaks if before (a): nothing to hook. Risk: low numerically,
but the cross term couples `C @ e` to `h`, so a C++ implementation needs one more
mat-vec per call or must run only at recording points; and the audit path
(`emfit/evolve.py:213-215`) expects to be told about energy events, which a
silent C++ reduction would skip.

**(f) PML coefficient construction — and why it may legitimately stay in Python.**
What is built: a layer object (`emfit/pml.py:402`) whose multipliers are an exact
per-step decay (`emfit/pml.py:663-680`), computed for a given `dt` and cached. What is
consumed: two elementwise multiplier arrays, one multiply each
(`emfit/pml.py:716-725`, `emfit/pml.py:727-735`), which is exactly what the kernel takes
(`src/emfit_core.h:43-48`). Construction happens once per run, is O(n) with a handful of
exponentials, and depends on grid geometry that Python already owns. Moving it buys
nothing measurable and costs the ability to inspect the layer in Python at run time.
**Proposal: leave PML construction in Python at every phase of this plan; move only the
consumption, which has already moved.** One trap: consuming the multipliers directly in
C++ bypasses `PML.damp_e`/`damp_h`'s audit hook (`emfit/pml.py:720-721`,
`emfit/pml.py:731-732`), so any C++ loop that applies factors directly must reproduce
the audit record or state that the audit is disabled on that path.

---

## 7. The per-step boundary-crossing budget

The tension is structural and easy to state: **everything that makes a step a step has
to be available inside the loop, and everything that is only available in Python has to
be fetched across the boundary.** A loop that fetches per step is a loop with a Python
call in its inner body, and at the sizes where the fixed cost matters that is where the
time goes — the measurement in section 5 shows a single crossing costing 1.7 ms against
a whole Python step of 8.5 us.

**The rule (proposal):** *a step must not call into Python. Anything needed per step is
either precomputed before the loop starts or moved into it.* "Precomputed" means
computed once and passed as an array or a scalar; "moved" means implemented in C++; there
is no third category, and a callback is not one.

Applied to section 6:

| Item | Needs Python per step today? | Under the rule |
|---|---|---|
| (a) time loop | no — `step` is pure array work (`emfit/evolve.py:248-251`) | moves cleanly; the loop owns `time`/`n` |
| (b) source | yes if arbitrary callable; no if Ricker | precompute the Ricker parameters; arbitrary callables stay on the Python path |
| (c) ports/RLC | yes — `advance` is the Python step (`emfit/terminations.py:245-252`) | state machine moves, or the item does not happen |
| (d) DFT/probe | only the accumulation is per step (`emfit/evolve.py:313-314`) | probe indices precomputed; accumulation moved or reported per step as `n` |
| (e) energy | no, at recording points only | precompute materials; evaluate on demand, not every step |
| (f) PML | no — multipliers computed once (`emfit/pml.py:662`) | stays in Python, arrays crossed once |

The corollary that has to be accepted up front: under this rule, **any feature that
genuinely requires a per-step Python decision cannot be in the fast path**, and the
product has to say so rather than silently degrade. An arbitrary `callback` argument
(`emfit/evolve.py:315-316`) is the canonical example: it is a Python call by
construction, so a C++ loop can support it only by being a Python loop.

---

## 8. Staging

Each phase is independently shippable, has an exit criterion that can fail, and leaves
the Python path authoritative. Nothing here authorises work; the phases exist so that a
partial outcome is still a useful one.

**Phase 0 — wire the existing `.so` as an opt-in backend, Python default.** No new C++.
Add a backend selector and route `FITStepper.step` through it when the flag is set,
falling back to `emfit/evolve.py:84` on `ImportError`. Files touched (proposal):
`emfit/evolve.py`, a new `emfit/_kernel.py` selector, `pyproject.toml` (nothing to
change — the extension is already optional, `pyproject.toml:41-57`). Tests added: a
dispatch test that the flag actually selects each path, and a fallback test that the
selector survives a missing module. Exit criterion: the full suite green in both modes
and `tests/test_cpp_parity.py` no longer skipping in the default CI configuration — a
skip is not evidence (section 10). What could regress: nothing numerically, if the
selector is a pure dispatch; the real risk is import-time work creeping into
`emfit/__init__.py`, which currently does exactly one thing, pinning threads
(`emfit/__init__.py:33-39`), and must stay cheap.

**Phase 1 — move the statement order into a C++ loop; sources stay in Python.** The
loop takes `nsteps`, the coefficient arrays, and the two field buffers, and returns `e`,
`h`, `time`, `n`. Sources, ports and probes stay outside, which limits the loop to the
lossless/PML/PEC case. Exit criterion: bit-identical (`assert_array_equal`, not
`allclose`) agreement with the Python loop over N steps on the committed ghostwave case,
or a toleranced criterion agreed in writing *before* the code exists. What could
regress: the audit hook (section 6f), the `time`/`n` bookkeeping (`emfit/evolve.py:254-255`),
and the fact that `FITStepper.step` currently returns `self`, which callers chain.

**Phase 2 — source injection into the loop.** Ricker parameters cross as scalars;
arbitrary callables are refused with a documented reason rather than silently demoted.
Exit criterion: parity on the v2 golden with `j` active, which already exists as a
fixture (`tests/test_cpp_parity.py:416`), plus a parity run whose source is time-varying
across steps rather than constant.

**Phase 3 — RLC / terminal coupling.** Per section 6c the state machine moves; the
Python path keeps its immutable `step_rlc` untouched so the existing 11 tests still test
something. Exit criterion: for a fixed excitation, the port voltage and the branch
current match the Python path over N steps at the same tolerance as Phase 1; the
back-reaction current density agrees too, not just the scalar observables.

**Phase 4 — DFT and energy accounting.** Exit criterion: the same accumulator output
for the same probe record, and `energy` matching to the last bit at every recorded step
(it is a sum of three scalars, so there is no excuse for drift).

**Evidence comparability, all phases (proposal).** Every artefact produced by a
C++-backed run must record which backend produced it and, for a toleranced phase, the
tolerance. The committed ghostwave artefact
(`evidence/termination/build_A_50ohm_p51_ghostwave.json:337`,
`evidence/termination/build_A_50ohm_p51_ghostwave.json:448`) is the reference: a rerun
under a new backend must land on the same numbers within the stated tolerance or the
backend is wrong, and if it cannot, the phase has changed physics rather than speed and
must be re-scoped.

---

## 9. Build and packaging

**The build.** `src/CMakeLists.txt` (2399 bytes) is the whole build: C++17, `-O3
-fopenmp`, no fast-math (`src/CMakeLists.txt:19-27`), pybind11 found via `CONFIG` and, if
missing, a loud warning followed by `return()` so a machine without pybind11 still gets
a pure-Python install (`src/CMakeLists.txt:29-39`). The extension is `emfit_core`, and
the `install()` rule exists only to place it at the wheel root
(`src/CMakeLists.txt:51-54`).

**Two build paths, two artefacts, three copies.** The documented standalone path puts
the module in `build/cpp` (`src/CMakeLists.txt:4-6`, `tests/test_cpp_parity.py:84`); the
packaging path puts it in the wheel and, under an editable install, into
`site-packages` (`pyproject.toml:35-39`). On disk that is:

- `build/cpp/emfit_core.cpython-312-x86_64-linux-gnu.so` — 258,720 bytes, the one the
  test and the documentation both load (`tests/test_cpp_parity.py:86`);
- `build/emfit_core.cpython-312-x86_64-linux-gnu.so` — 200,872 bytes, left by the
  operator's cmake run whose binary directory is the repository `build/`
  (`build/CMakeCache.txt:224`);
- `.venv/lib/python3.12/site-packages/emfit_core.cpython-312-x86_64-linux-gnu.so` —
  258,720 bytes, the installed copy.

**`build/cpp` is authoritative**, because that is where both the documented command
(`src/CMakeLists.txt:6`) and the test's `PYTHONPATH` (`tests/test_cpp_parity.py:86`)
look. **Two copies in-tree is a hazard** for three reasons: which one loads is decided
by `PYTHONPATH` alone, so two runs of the same test can exercise different binaries; the
smaller, older `build/` copy predates the binding fix recorded in the dispatch log
(`docs/design/dispatch_log.md:53`), so it is a *stale ABI* sitting one directory away
from the current one; and `build/` is git-ignored (`.gitignore:11`), so nothing about
either copy appears in a diff for a reviewer to notice.

**ABI and Python pinning.** The artefact's tag is `cpython-312`, derived at build time
from `sysconfig` (`tests/test_cpp_parity.py:84`); the test also hardcodes the include
path `/usr/local/include/python3.12` (`tests/test_cpp_parity.py:83`). A Python upgrade
therefore breaks the build line first and the import second, and the second failure is
`ImportError` — which the parity test converts into `pytest.mark.skipif`
(`tests/test_cpp_parity.py:96-103`). The consequence deserves to be spelled out: after a
Python upgrade, the project would show *green* while its only C++ evidence had silently
stopped being collected.

**Should the module be optional at import time?** It already is, by construction:
nothing in `emfit/` imports it (`pyproject.toml:55-56`). Any Phase 0 selector must keep
it that way — import inside the selector on demand, catch `ImportError`, and record the
reason once — rather than importing at package import and turning a missing compiler into
a broken `import emfit`.

---

## 10. How we would know it worked

Numbered, so each can be marked done or not done.

1. **Parity, at zero tolerance, on committed data.** For N steps (N to be fixed in the
   plan for that phase, and to exceed the three steps of the golden fixtures), the
   C++-backed run reproduces the Python path with `assert_array_equal` on `e` and `h`,
   on the frozen fixtures (`tests/data/cpp_golden_step.npz`,
   `tests/data/cpp_golden_step_v2.npz`) and on the live reference. If bit-identity is
   abandoned, the substitute criterion is named and justified before the code lands, not
   after.
2. **Parity on the committed ghostwave case.** The end-to-end artefact
   `evidence/termination/build_A_50ohm_p51_ghostwave.json` has `s11` magnitude
   `0.32586326001662264` (`evidence/termination/build_A_50ohm_p51_ghostwave.json:337`)
   and an `s21` magnitude (`evidence/termination/build_A_50ohm_p51_ghostwave.json:448`)
   with `validation_status` recorded (`evidence/termination/build_A_50ohm_p51_ghostwave.json:437`).
   A backend change either reproduces those numbers or states, in writing, why and by how
   much it cannot.
3. **Determinism.** Same inputs, same output bytes, on repeat runs and across process
   restarts. This is not a formality: the kernel parallelises over independent rows with
   a static schedule specifically so that the result is a function of the input bytes
   regardless of thread count (`src/emfit_core.cpp:37-42`), and any new parallel region
   must preserve that property or be serial.
4. **A performance criterion that is a measurement, not a wish.** The reported number
   must come from the section 5 protocol on a grid of at least 10^5 edges, with the
   dispatch share stated separately from the mat-vec share, and it must be compared
   against the same study on the Python path in the same container. No factor is
   promised by this document and none should be quoted from it.
5. **The fallback is not removed.** The Python path stays reachable and stays the
   default until the evidence above exists, and the selector's fallback is covered by a
   test that runs with the module deliberately unimportable.
6. **`tests/test_poc_playback.py` stays green — all 26 tests.** Those 26 test functions
   cover the vis trigger and its controller wiring, which depends on state shapes that a
   loop rewrite can change.
7. **`tests/test_cpp_parity.py` stays green, 13 tests, no skips.** A skip is not
   evidence: the file is written to skip when the module is missing
   (`tests/test_cpp_parity.py:96-103`), and it reports a passing run with a warning-free
   skip if the module is not built correctly. Any "parity verified" claim must be
   accompanied by the pass count.
8. **The stale-status problem is closed.** The comments asserting that PML, lossy, PEC
   and source branches are unverified (`src/emfit_core.cpp:4-8`,
   `src/bindings.cpp:48-55`, `src/bindings.cpp:295-301`) either become true again or are
   updated; a status claim in three places that contradicts the test file
   (`tests/test_cpp_parity.py:416`) is a hazard for whoever reads the C++ next.

---

## 11. Open questions and non-goals

Undecided, and deliberately left undecided here because each one changes the shape of
the code rather than the wording of the plan:

- **Who owns the field arrays across the loop.** Today `FITStepper` allocates them
  (`emfit/evolve.py:221-222`) and passes them down. A C++ loop can either borrow them
  (no copy, lifetime guaranteed by the caller) or own them (cleaner invariants, one copy
  and an ownership question at the boundary, against a 512 MB cap).
- **Expose a C++ loop, or a C++ `run`.** A loop is a smaller surface and keeps probes
  and callbacks in Python, at the cost of one crossing per *run* rather than per step —
  which is all the crossing budget needs. A whole `run` moves more and takes on the
  callback problem (section 7). The smaller surface is the safer default; the larger one
  is the only way to remove the last per-step Python work.
- **RLC immutability at a C++ boundary.** Returning a state struct by value is the
  natural translation of "a step never mutates a state"
  (`emfit/terminations.py:259-261`), but it changes the call signature that
  `tests/test_terminations.py` pins, and it must be decided before Phase 3 starts.
- **Whether bit-identity survives a different sparse mat-vec order.** The current
  guarantee rests on visiting each row's non-zeros in ascending column order with one
  accumulator (`src/emfit_core.cpp:10-22`), which forbids tree reductions and parallel
  row splitting. Whether a faster traversal exists that still produces identical bits is
  open, and the ledger records the same tension as the narrower E3 decision
  (`docs/design/EM_SOLVER_LEDGER.md:28`).
- **Scratch buffers within 512 MB.** A loop that needs temporaries, or a boundary that
  holds a CSR copy on both sides, has to fit a cgroup cap of 512 MB
  (`/sys/fs/cgroup/memory.max`) alongside whatever the study already holds.
- **What "N steps" is** for criterion 1 — three (the fixture length), a study's full
  length, or a number chosen to make drift visible.

Non-goals, stated so they do not creep in:

- **No GPU.** No CUDA, no OpenCL, no device-side mat-vec.
- **No threading work.** Thread counts are pinned at import
  (`emfit/__init__.py:33-39`) and the OpenMP regions are already the reason the small
  grid is slow; tuning them is a separate dispatch, and rescinding bit-parity to buy
  parallelism is a ledger decision, not a side effect of this plan.
- **No new physics.** No dispersive materials, no non-linear loads, no new boundary
  conditions, no change to any discretisation.
- **No change to results.** A phase that alters a number has failed, whatever it did to
  the wall clock.
- **No removal of the Python path.** It is the reference, the fallback, and the only
  implementation that a machine without a compiler can run.
