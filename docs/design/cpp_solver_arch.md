# A C++ architecture for the emfit 2D eigenproblem

## Status

**New document.** Authored at Dispatch 42. There was no `docs/design/cpp_solver_arch.md` in the tree before this pass and none in history; this is not a revision of anything, and it supersedes nothing.

**Design only.** There is no C++ source, no header, no CMake file, and nothing in `emfit/` or `tools/` that knows this document exists. No benchmark in this document was run by it.

**The factoriser is ruled and the licence is not.** Port v1 uses SuperLU (4.1, R4a) for attribution reasons and not for speed; the symmetric-indefinite upgrade is deferred to its own pre-registration (4.1, R4b); Eigen is excluded from v1 (4.2, R4c). The licence question stays open (4.6, R4d), and so do the binding, the threading model and the storage format. R4a is an engineering call and not a licence clearance. Section 8 collects all of them; section 9 lists what is deliberately not decided.

---

## 1. Purpose and scope

**1.1 The question this document answers.** Given that the adopted 2D eigenproblem path is a Python shift-invert Lanczos solve that has been measured to 259,760 degrees of freedom and measured to return nothing at `k = 6` on that same matrix, what would a C++ implementation of that same solve have to look like, and how would anyone know it was right before trusting it?

**1.2 The question it does not answer.** It does not clear a licence, a Python/C++ binding, a threading model, or a matrix storage format. It records one component ruling (4.1, R4a), one deferral (R4b), one scope ruling (4.2, R4c) and one open question (4.6, R4d). The licence, the binding, the threading model and the storage format remain open, and R4a is an engineering call rather than a clearance.

**1.3 It does not author a second C++ contract.** `docs/design/core_contract.md:166` opens `### C++ FIT production port`, and that subsection already fixes the interface shape: inputs are "the same contract, plus a thread count and a dt policy" (`:168` to `:170`), returns are `e`/`h` samples at declared probes and planes plus "the `dt` actually used, the three-valued status (item 5), and the required provenance core" (`:172` to `:173`), and two things it "cannot be asked for" are fixed at `:179` to `:185` (in-memory mutation as a variation mechanism, and source exposure for `inspect.getsource`). This document supplies the *engineering* content that section leaves open, namely which factoriser, which storage, which threads, which binding, and how the port is accepted. It does not restate the interface shape, and where the two ever appear to disagree, `core_contract.md` wins.

**1.4 Scope note on which core.** `core_contract.md:166` names the FIT time-domain port. This document is about the 2D eigenproblem member (`emfit/mode2d.py:795`, `:935`, identified as Core A at `core_contract.md:300` to `:301`). The two share the contract; they do not share a cost model, because one is a shift-invert factorisation and the other is a leapfrog march. Nothing here should be read as a statement about the time-domain core.

**1.5 Why the acceptance criterion gets half the document.** A C++ port that is faster and slightly wrong is the failure mode this whole exercise risks, and it is not detectable by inspection. Section 5 is therefore written as a pre-registration in the style of `docs/design/t4b_t4c_preregistration.md`: the statistic, the thresholds, the meshes, the environment pinning and the verdict vocabulary are fixed here, before any C++ exists, so that the port cannot later be judged against whatever it happens to produce.

---

## 2. The incumbent being replaced, stated as measurement

**2.1 The adopted solve, and the second entry point it hides.** `emfit/mode2d.py:795` `solve_modes` is the adopted solve: `c = (k0*k0*m_eps - k_q).tocsr()` at `:860`, `b = m_mu.tocsr()` at `:861`, free-degree slices `c_free` and `b_free` at `:862` to `:863`, then `eigsh(c_free, k=n_k, M=b_free, sigma=sigma, which="LM")` at `:868`, with `sigma` a scalar (`float` annotation at `:798`, `float(sigma)` at `:847`, finite check at `:850` to `:851`) and with no `OPinv`, no `LinearOperator`, no `todense` and no `toarray` anywhere in `:795` to `:934`. `decisions.md:6112` to `:6116` records the same solve against `/tmp/c3.py:96-97`, a file that is not in this tree; the citation that can be reopened is the one just given. The same file carries a second solve, `solve_modes_mixed` at `:935`, and it is dense by construction: `_MIXED_DENSE_MAX = 3000` at `:151`, `use_dense` at `:1094`, a `NotImplementedError` above that cap at `:1096` to `:1099`, and below it `splu(h)` at `:1107`, `toarray()` at `:1115` and `_dense_eig` at `:1120`. The sentence "nothing is densified at any size used here" is true of the first and false of the second. See 9.1.

**2.2 The pencil actually run.** The mass-side enlarged pencil of `docs/design/sparse_eigenmode.md:550` to `:584`:

| object | shape | content |
|---|---|---|
| `K_C` | `(free_e+free_n) x (free_e+free_n)` | `[[A, 0], [0, 0]]` |
| `M_C` | same | `[[m1_f, -c], [-c^T, h]]` |
| factorised matrix | same | `K_C - sigma*M_C`, one `splu` |
| `sigma` | scalar | `0.999 * beta_sq`, pre-registered in the result |

**2.3 The `LinearOperator` form is mandatory for the port, and absent from the incumbent.** `M_C` is symmetric **indefinite**, so it cannot be passed as the `M` argument of `eigsh`. A driver that has to exceed the incumbent's cap must be handed `(K_C - sigma*M_C)^{-1} M_C` as an operator and must never see `M_C` as an `M`. That is a requirement on the port and not a description of anything in `emfit/`: `solve_modes` passes the positive definite `M=b_free` at `:868` and lets the ARPACK layer factorise `C - sigma B` internally, and `solve_modes_mixed` never forms the operator at all, building the dense pair at `:1115` to `:1116` and calling `_dense_eig` at `:1120` (9.1). Evidence, MEASURED at `free_e = 1444` with `M_C` of order 1927 (`sparse_eigenmode.md:529` to `:533`, with the dimension triple at `:336`):

| quantity | value |
|---|---|
| positive / negative / zero eigenvalues of `M_C` | 1444 / 483 / 0 |
| `lambda_min` | `-1.856672362588098e-02` |
| `lambda_max` | `21.777039052800774` |
| smallest `abs(lambda)` | `1.0293555296331769e-04` |
| `numpy.linalg.cond` | `211559.9365417365` |
| condition ratio of `abs(eig)` | `1172.9069431746586` |

**2.4 Derived requirement: the factorisation must handle a symmetric indefinite matrix.** This is a consequence of 2.3 and it is not negotiable by taste.

`K_C - sigma*M_C` is symmetric indefinite. Any factorisation that assumes positive definiteness is therefore excluded by measurement, before any licence question is asked. That eliminates, at minimum: CHOLMOD, Eigen `SimplicialLLT`, Eigen `SimplicialLDLT` (unpivoted `LDL^T` has no mechanism to survive a zero or ill-conditioned pivot on an indefinite matrix), and any `dpotrf` or `spotrf` path in LAPACK/BLAS. What survives is a symmetric-indefinite path (multifrontal `LDL^T` with numerical pivoting, or a Bunch-Kaufman style pivoted indefinite factorisation) or an unsymmetric LU that does not exploit symmetry at all.

Three consequences follow, and each of them changes section 4:

1. A large part of the obvious library shortlist is eliminated by linear algebra, not by licensing. The licence discussion in 4.1 applies only to the surviving candidates.
2. An unsymmetric LU on a symmetric matrix doubles the index storage and discards a symmetry the problem actually has. It is admissible but it is a worse answer, and any ratification that picks it should say why.
3. The inertia is also the correctness check on the factorisation itself. A factoriser that reports a different inertia for the same `M_C` has taken a different path through the pivots, and the discrepancy is a finding about the factoriser, not about the physics. Section 7.4 uses this.

**2.5 Measured costs to carry into any design.** From the rung table at `sparse_eigenmode.md:334` to `:349`, rung1 column (`sc = 16`, `s16_a12_z10-5-5`):

| quantity | rung1 (MEASURED) |
|---|---|
| `free_e / free_n / n` | 2404 / 803 / 3207 |
| `nnz(M_C) = nnz(S_C)` | 35,351 (`0.00344 n^2`) |
| `splu(K_C - sigma M_C)` | 0.00756 s |
| `nnz(L+U)` / fill per row | 214,641 / 66.9 |
| factor memory | `2.58e-3 GB` |
| `eigsh` wall time / `OPinv` calls | 0.00901 s / 21 |

**2.6 Extrapolations are labelled as extrapolations.** `sparse_eigenmode.md:357` to `:360` states the terms: "Everything in this subsection is **EXTRAPOLATED**: a two-point power law fitted through the two measured rungs ... Nothing here was measured at the target mesh, and nothing here was measured at ladder rung 4." At `free_e = 30000` (`:362` to `:365`) that gives route A (`nnz(L+U)` `8.99e8`, 10.8 GB, 343 s) against route C (`n = 40021`, `nnz(L+U)` `7.03e6`, 0.0843 GB, 0.156 s). The 0.0843 GB and 0.156 s figures are **EXTRAPOLATED**. They are quoted here because they set the scale of what a port is being asked to beat, and for no other reason.

**2.7 The dense path stays dead in `emfit/eigen.py` and is alive in `emfit/mode2d.py`.** `decisions.md:6398` to `:6402` records the rejection of the `emfit/eigen.py` path: `todense()` at `emfit/eigen.py:186`, `sla.eigh` at `:196` and `:198`, and a guard that raises above `max_dense = 3000` at `:176` to `:182`. "It cannot reach 115232 or 259760 degrees of freedom, and it must not be refactored to try; 315.64 MiB and 155 s is the measured alternative." That ruling names one dense path and the tree contains two. `solve_modes_mixed` in `emfit/mode2d.py` is itself a dense path: `splu` at `:1107`, `np.eye` at `:1114`, `toarray()` at `:1115`, `_dense_eig` at `:1120`, and the same 3000 threshold at `:151` enforced by the raise at `:1096`. A port that excludes only the `emfit/eigen.py` path has not excluded the dense path the incumbent actually reaches (9.1).

---

## 3. Why a C++ port at all, and the honest negative

**3.1 Three measured facts, and nothing else.** The case for a port rests on these and not on an intuition that C++ is faster:

| fact | source |
|---|---|
| at 259,760 dof, `k = 4` took 21.0 s at 682 MiB, while `k = 6` on the same matrix **exceeded the 300 s cap and returned no data** | `decisions.md:6121` to `:6123` |
| at up to 115,232 dof the nine-point matrix took 155 s wall (148.18 s in process) at a peak resident set of 315.64 MiB | `decisions.md:6119` to `:6120` |
| fill per row rises from 55.1 at rung0 to 66.9 at rung1, and the target-mesh factor is `7.03e6` nonzeros by extrapolation | `sparse_eigenmode.md:345`, `:365` |

Read together: cost is governed by `k`, not by assembly (`decisions.md:6121`), and the wall that stops the current path is a budget cap hit by a second eigenpair, not a memory wall. `decisions.md:6123` to `:6124` is explicit that this "is recorded as a budget outcome in (k)(5), not as a limit of the solver", which is the reason a port is worth discussing at all: the solver did not fail, the run did.

**3.2 The discipline any speed claim must adopt.** `decisions.md:5635` to `:5643` sets the house form: "**4600 s is an ESTIMATE, not a budget, and it is now falsifiable.** ... A price with no void condition is a licence to run indefinitely, so the falsifier is registered with the estimate rather than after the wall is known", with the 2x falsifier at `:5639` to `:5643`: "A run whose wall exceeds twice the estimate, 9200 s, without a documented cause **VOIDS** the run and requires a **new** pre-registration before any re-run. The void is recorded whether or not the diagnostics look good. That is the point of a falsifier: it is not a warning threshold."

**3.3 No measured speedup exists.** This document makes no speedup claim, because there is no measurement in the record from which one could be derived. The target is a falsifiable estimate of the form:

> A threaded C++ shift-invert solve on the `free_e = 30000` class mesh will complete the `k = 6` case in **X** seconds of wall time on machine **M**, falsified if the first correct run on that mesh exceeds **Y** seconds without a documented cause, in which case the run is VOID and requires a new pre-registration.

**X and Y are unfilled.** Filling them requires either a C++ prototype or a measured threaded CPU run of the incumbent, and neither exists. Anyone who writes a number into that sentence before a run has invented it. The only honest present-tense statement is that the 300 s cap was hit on a Python `k = 6` at 259,760 dof (`decisions.md:6122`) and that the port is motivated by that, with no claim about how much of the 300 s a compiled factorisation would recover.

---

## 4. Component selection: RULED, DEFERRED AND OPEN

**4.0 The framing, as amended at Dispatch 43.** This section was written at Dispatch 42 as five open rulings, on the reasoning that a licence position taken inside a documentation dispatch becomes a position the project never actually took, and that three of the five choices sit downstream of the factoriser. The first reason stands, and it is why 4.6 is still open. The second no longer applies: the factoriser question is answered by an engineering call that assumes nothing about licensing, and Eigen's scope is answered by not needing it. Both are ruled below, and the order they were taken in is stated because the other three questions were waiting on the factoriser.

Where a licence appears below it is marked either as **verified against a file in this tree** or as **asserted from general knowledge and not verified**. One fact is now verified, and it is not the comfortable one: the SuperLU code path ships inside the installed SciPy as compiled machinery, and no SuperLU licence text ships beside it. The audit and its evidence are in 4.6.

### 4.1 Sparse direct factorisation

| option | what it is | cost | what ratification must establish |
|---|---|---|---|
| SuperLU | unsymmetric LU with pivoting, ships inside SciPy's `splu` which the incumbent already calls; **VERIFIED** at Dispatch 43, `_superlu` compiles `gstrf` (`scipy/sparse/linalg/_dsolve/linsolve.py:13`, `:444`, `:54`) | uses no symmetry; doubles index storage for a symmetric matrix | asserted BSD-3-Clause, not verifiable from this tree; notice not shipped in dist-info; obtaining and shipping the upstream notice is a prerequisite to ratification. **RULED** as R4a, below |
| SuiteSparse/UMFPACK | unsymmetric multifrontal LU; the same SuiteSparse tree also carries the symmetric-indefinite multifrontal paths | external build dependency; multifrontal memory is supernode dependent | licence class, and whether the GPL branch is acceptable (4.6) |
| Eigen | header-only C++ templates; `SparseLU` unsymmetric, `SimplicialLDLT`/`LLT` symmetric positive definite; not installed in this tree | `SimplicialLDLT` is excluded by 2.4; `SparseLU` is the surviving member | asserted MPL2, unverified - Eigen absent from environment. **RULED** out of v1 as R4c, in 4.2 |
| LAPACK + BLAS only | the incumbent's language, banded or dense blocked | `dpotrf` excluded by 2.4; `dsytrf` (Bunch-Kaufman) survives but is not sparse | whether a non-sparse indefinite path is admissible at all (it is not, per 2.7) |

**The ruling (R4a), and why it is attribution rather than performance.** SuperLU is the port's factoriser. It is a general sparse LU, it is unsymmetric, and it exploits no symmetry of `K_C - sigma*M_C`. It survives 2.4 for the only reason that matters here: it assumes nothing about definiteness, so the indefinite pencil cannot break it. That is admissibility and not fitness, and 2.4 said so in advance: an unsymmetric LU on a symmetric matrix "discards a symmetry the problem actually has. It is admissible but it is a worse answer". SuperLU is chosen because the comparison it makes possible is attributable, the Python side already calling the same factorisation through `splu`, and not because it is fast. No speed claim is made for it (3.3). **The deferral (R4b).** The efficient answer is a symmetric-indefinite multifrontal path: MUMPS, or a paid HSL code (MA57, MA97) under a licence this project would have to buy. It is **DEFERRED**, not refused, and it is deferred to its own pre-registration. It must be judged against the port's measured SuperLU result on the same mesh and the same pencil, and not against the Python timing, because the Python timing is a script and the port is not.

### 4.2 Eigen's role and scope

Eigen is named separately because it can enter at four different depths and the choice is not one choice:

1. **dense small blocks only** (the `2x2` and `3x3` per-cell work),
2. **sparse assembly only** (triplet lists, no solve),
3. **the factorisation itself** (`SparseLU`),
4. **the eigensolver** (not proposed; the driver stays the same algorithm as 2.1, in C++ or in Python).

**The ruling (R4c).** Eigen enters v1 at no depth. Depth 1, the per-cell `2x2` and `3x3` work, is a handful of closed-form operations per cell and does not justify a vendored header library. Depths 2 and 3 are excluded by the same argument as R4b: they would put a second factoriser in the tree, with a licence to attribute and a scope to defend, and R4a has already answered the factoriser question. Every dependency is a thing to attribute, and this document will not add one for convenience. Eigen is not installed in this tree, so its licence is not verified here either; its licence is asserted MPL2, unverified - Eigen absent from environment, and that is recorded as an assertion and not as a finding.

### 4.3 Matrix storage

CSC against CSR, and the ordering point: **the storage choice is downstream of the factoriser.** A factoriser that wants column access wants CSC; one that assembles row-wise prefers CSR and a transpose. There is also the question this project actually faces, which is whether the `(free_e+free_n)` block structure of 2.2 is stored as one assembled matrix with the zero block written explicitly, or as two stacked matrices with the zero block implied. The former is simpler and wastes three quarters of the index space at the ratio 3:1 that `free_n/free_e = 483/1444` (`sparse_eigenmode.md:336`) implies; the latter is faster to build and harder to hand to a third-party factoriser.

**Why not decided here.** It cannot be decided before 4.1, because the right answer is whatever the chosen factoriser wants.

### 4.4 Threading

OpenMP against TBB against `std::thread`. This is a component choice **and** part of the acceptance criterion, not a performance detail, for the reason in 5.8: thread count alone moves the answer by 8.13e-11, which is eight times the 1e-11 figure reported in 5.3. The measured figure is `decisions.md:7192`: "The smallest non-zero null obtainable without a re-solve is 8.13e-11 relative, from BLAS thread count 1 against 4 on the same capture."

**Why not decided here.** The threading model is a build and deployment decision, and 5.8 makes its *reporting* mandatory regardless of which model is chosen. Pinning thread count to 1 for the comparison run (5.8) means the choice does not affect the verdict, which is the right relationship: the model may be chosen freely, the pinning may not be skipped.

### 4.5 Python/C++ binding

pybind11 against `ctypes` against a plain C ABI with a numpy buffer handoff. The relevant constraint is already in the contract: the port "cannot be asked to expose source for `inspect.getsource`" (`core_contract.md:184` to `:185`, citing `.scratch/lever/run_real.py:50-53`), so no binding technology recovers that capability and the variation point must move into the contract instead (`core_contract.md:183` to `:184`).

| option | cost |
|---|---|
| pybind11 | header-only, C++-type-aware, adds a build-time dependency and a compiler-version floor |
| ctypes | no build dependency on the Python side, hand-written struct marshalling, no exception translation |
| C ABI + numpy handoff | smallest surface, no C++ ABI stability question, most manual code |

**Why not decided here.** Binding choice interacts with how the result is reported (the provenance core of `core_contract.md:172` to `:173`), which is a schema question that section 3 of `core_contract.md` already owns.

### 4.6 The decision rule the principal needs

The rule is not "is a GPL library good". It is: **is a GPL component admissible anywhere in the factorisation path of a project that ships a Python package?**

**The verified fact, and the ruling that is not a clearance (R4d).** What is verified in this tree is a shipping fact and not a licence fact: the SuperLU code path ships inside the installed SciPy as compiled machinery, `_superlu` compiling `gstrf` (`scipy/sparse/linalg/_dsolve/linsolve.py:13`, `:444`, `:54`), and nothing in the wheel's licence field says so. `scipy-1.18.1.dist-info/LICENSE.txt` is SciPy's BSD-3-Clause text and contains zero occurrences of `superlu`; `METADATA:46` names OpenBLAS and the GCC runtime in its bundled list and does not name SuperLU. That citation was written `:43` in the supervisor's brief for Dispatch 43a and corrected to `:44` in the brief for 43b, and neither is right: line 43 of that file is the phrase "(depending on the build):", lines 44 and 45 are blank, and the first bundled name, OpenBLAS, is on line 46, so the reference is corrected here to `:46`; the auditwheel SBOM carries zero SuperLU entries. What is asserted and not verified against any vendor file in this tree is this: SuperLU is asserted BSD-3-Clause, not verifiable from this tree; notice not shipped in dist-info; obtaining and shipping the upstream notice is a prerequisite to ratification. UMFPACK is asserted GPL-2.0-or-later, unverified here. R4d stays **OPEN**, and R4a is an engineering call and not a clearance: it says the factoriser is SuperLU and it does not say a licence question is settled, because on this evidence nobody has established where the SuperLU notice lives in a wheel that ships the compiled library without it. If the distribution boundary for this project is a Python package that a user installs, that question is the principal's, and it no longer changes which factoriser v1 uses.

---

## 5. The acceptance criterion, pre-registered

**5.0 Pre-registration.** Everything in this section is fixed before any C++ exists. It is written in the form of `docs/design/t4b_t4c_preregistration.md`: registered first, with an explicit failure verdict available, so the port cannot be judged against whatever it later produces.

### 5.1 The comparison convention

> **Compare `beta^2`, not `beta`.** `beta^2` is what the code computes and it carries no sign or branch ambiguity, so it is the quantity compared.
>
> **Compare as a relative difference with the Python value as the fixed denominator:**
>
> ```
> rel = (beta2_cpp - beta2_py) / beta2_py
> ```
>
> **The denominator is fixed before the run** and may not be changed after the result is seen. It is the Python value on the same mesh, from the same pencil, under the environment block of 5.8; it is fixed precisely so it cannot be chosen post hoc to move a verdict.
>
> **The statistic is dimensionless**, which is what `core_contract.md:283` to `:284` requires of a core comparison: "compared as a **dimensionless ratio** at the anchor's own tolerance". A relative difference of two `beta^2` values is exactly that shape.
>
> **Sign convention:** `rel` is signed and is reported with its sign. The gates in 5.3 and 5.4 are on `|rel|`.

### 5.2 What is not compared, and why

| excluded | reason | source |
|---|---|---|
| eigenvector amplitude and normalisation | the `mode2d` normalisation defect is open (`decisions.md:7008`); `core_contract.md:325` to `:331` puts field scale out of scope by construction | `core_contract.md:327` to `:331` |
| field arrays, bitwise | determinism across machine, thread count and BLAS is not supported by anything in the tree | `decisions.md:7065`, quoted at `core_contract.md:169` to `:170` and `:332` to `:333` |
| provenance key sets | a 2D eigenproblem solve and a 3D time-domain solve do not describe themselves with the same terms | `core_contract.md:334` to `:336`, citing `decisions.md:7091` |
| wall time | "reported but never compared" | `core_contract.md:338` to `:341` |

Wall time is reported for every run under 5.8 and it never enters a verdict. `core_contract.md:340` to `:341` gives the reason and it applies verbatim here: "a wall-time comparison would fail the test precisely when the test succeeded."

### 5.3 The 1e-11 figure: reported, and not citable

**`|rel| <= 1e-11` on the same eigenpair is reported for every scored run and carries no verdict.** It is not citable as a pass or as a fail, for the reason in the next paragraph: the instrument cannot hold it still.

**The caveat belongs in the same paragraph, not in an appendix.** This figure sits at or below the measured round-off floor of the reference itself, and below the post-processing noise bound. `decisions.md:6133` to `:6135` records a relative error of **9.79e-12** at 9560 degrees of freedom and says in the next breath that "the error grows with refinement ... and it licenses no convergence rate". The smallest non-zero null obtainable without a re-solve is **8.13e-11** (`decisions.md:7192`, 5.8), from BLAS thread count 1 against 4 on the same capture, and it is eight times this figure, which means it is above it. A number the instrument moves by eight times its own size cannot carry a verdict.

**This is a relabel, and the threshold does not move.** Dispatch 42 called `1e-11` the primary criterion and scored it PASS or FAIL. The number stays exactly where it was and the verdict comes off it, for the reason stated above and for no other: a FAIL at `1e-11` would not be evidence that the port is wrong, because the instrument's own floor sits at or above the threshold, and a PASS at `1e-11` would be an artefact of a quiet machine rather than a validation of the port. A number that cannot fail is not a gate, and keeping a verdict on it invites a later reader to treat either outcome as information. The result is still reported for every run, with its sign, and it is reported as a figure and not as a score. The binding gate is 5.4.

### 5.4 The second statistic, and the binding gate: `1e-8`

**`|rel| <= 1e-8` on the same eigenpair, same mesh, same run, and this one carries the PASS or FAIL verdict.** It is achievable above the measured noise floors recorded in 5.3, and tight enough to catch a wrong pencil, a wrong `sigma`, or a silent densification that changes rounding. It remains the *second* statistic in the order of the two, because it is the larger number and is read after the first, and it is the only one of the two that binds. A failure here is a FAIL of the port, not a diagnostic footnote, and it is attributable: the noise floor of 5.3 is two orders of magnitude below it.

### 5.5 Third statistic: Python-side self-agreement

The Python solver run against itself on the same mesh, thread count pinned to 1, must reproduce **bit-for-bit**. What it actually does is reported. This calibrates the harness before the port is judged by it: if the Python solver does not agree with itself under the pinning of 5.8, no cross-language comparison on that machine is meaningful, and the run is abandoned rather than scored.

### 5.6 Meshes, both required

| mesh | free edges | spec | source |
|---|---|---|---|
| M4 | **30,672** | `58/44/35-17-18` | `tools/host/sparse-probe/out_mesh/mode_overlap.json:285` to `:286`, with `n_e = 30672`, `n_n = 10231`, `free_e = 30672` at `:299` to `:301` and `sigma = 96335.2458966532` at `:294` |
| M3 | **28,980** | `56/43/34-17-17` | `tools/host/sparse-probe/out_mesh/mode_overlap.json:228` to `:229`, with `n_e = 28980`, `n_n = 9667`, `free_e = 28980` at `:242` to `:244`, `mesh_checks_ok = true` at `:245`, `sigma = 96404.93625838071` at `:237`, `lambda = 96431.67757422743` at `:246` and `R = 3.473702068959308` at `:248` |

M4 at 30,672 free edges and M3 at 28,980 free edges are both measured meshes, and the port is judged on both. Dispatch 42 carried a third row here, a 30,000 free-edge class mesh taken from `sparse_eigenmode.md:355`, and it has been removed: a criterion row that names a mesh no probe in this tree can execute is not a criterion, it is a placeholder, and it is the same class of defect as a line that no longer matches its own measurement. The observation the row carried is not lost and is weaker than it was written. `sparse_eigenmode.md:357` to `:360` marks that whole subsection EXTRAPOLATED and says "Nothing here was measured at the target mesh, and nothing here was measured at ladder rung 4", so any figure at 30,000 free edges remains an EXTRAPOLATED first data point, is labelled as one there (`:357`), and is not a confirmation of the extrapolation.

### 5.7 Residual gate

**No comparison may be scored without a recorded residual on both sides, `<= 1e-6`.** The rule is `docs/design/t4b_t4c_preregistration.md:452` to `:456`: "Any solve reporting residual `> 1e-6` is **INVALID** and must be retried down the descending ladder `sigma x {1, .996, .992, .988, .984, .980}` until a solve reports residual `<= 1e-6`. **A result carries its residual as part of the result.** A result without a recorded residual, or with residual `> 1e-6`, **may not be banked, scored, or cited**."

If the C++ side's residual exceeds `1e-6`, the row is **not a result**. It is not a FAIL, and it is not a pass with a footnote.

### 5.8 Pinned environment block

Every run reports, and any deviation from the registered values **voids the comparison**:

| field | registered value |
|---|---|
| machine | (to be filled at run time; must be identical for both sides) |
| BLAS vendor and version | (to be filled; must be identical for both sides) |
| thread count | **1** for the scored run |
| compiler and optimisation flags | (to be filled for the C++ side) |
| Python, numpy, scipy versions | (to be filled) |

This block exists because of `decisions.md:7192`, quoted: "The smallest non-zero null obtainable without a re-solve is 8.13e-11 relative, from BLAS thread count 1 against 4 on the same capture." A thread-count change alone moves the answer by 8.13e-11, which is eight times the 1e-11 figure of 5.3 and 0.8 percent of the 1e-8 threshold of 5.4. Without pinning, the 1e-11 figure is not measurable at all, and the binding gate carries an unattributed contribution it cannot separate from a port defect.

One honest qualification, recorded so the block is not over-read: `decisions.md:7365` states that "the `8.13e-11` null demonstrates **determinism** ... not **repeatability** across the configuration changes a gate has to survive." This is exactly why 5.8 pins the configuration rather than treating the number as a repeatability bound. The number bounds what configuration drift does, which is the thing being pinned.

### 5.9 Verdict vocabulary

**PASS** and **FAIL**, and only those two. "Close" is not a verdict. "Within tolerance except for one pair" is a FAIL with a note.

| statistic | threshold | verdict if exceeded | citable for |
|---|---|---|---|
| `|rel|` on `beta^2`, both meshes | `1e-11` | PASS or FAIL, reported only | nothing: not validation, not port defect (5.3) |
| `|rel|` on `beta^2`, same run | `1e-8` | PASS or FAIL, binding | fidelity of the port to the Python on the same pencil, and nothing beyond it (5.4, 9.1) |
| analytic anchor (9.1) | not set here | reference only, no verdict | whether the Python itself is right. UNMEASURED (9.1) |
| physics invariants (9.1) | not set here | reference only, no verdict | passivity, mode purity and `beta` against an analytic value. UNMEASURED (9.1) |
The thresholds do not move: `1e-6` on the residual on either side is still not a result, self-agreement in 5.5 is still bitwise and its failure still invalidates the harness rather than the port, and the environment block of 5.8 still voids any comparison when it differs. What changes is the fourth column, which now says what each row is allowed to certify, and the last two rows are commitments recorded in 9.1 rather than measurements. Those three are retained and were not dropped: they sit outside the criterion table because they are not accuracy criteria and not wrongness criteria.

---

## 6. What would justify CUDA, as a proof obligation

**6.1 No CUDA is required, and none is proposed.** CUDA does not appear on any shortlist in section 4 and is not a candidate for ratification in section 8. It is mentioned here only to state where the burden of proof sits.

**6.2 The burden is on the proposer, and it is a measurement.** Any proposal for a GPU path must exhibit, on the `free_e = 30000` class mesh:

1. a threaded CPU implementation of the same algorithm, already accepted under section 5;
2. a measured profile of that implementation showing the **factorisation** still dominating wall time, with numbers, not with an estimate;
3. the specific fraction of wall time that a device factorisation would have to recover to matter, and that fraction compared against the data-transfer cost of the pencil at that size.

**6.3 No such measurement exists in the record today.** There is no measured CPU profile at the target mesh, because there is no C++ implementation. The record contains `21.0 s` at `k = 4` and a `300 s` cap hit at `k = 6` on 259,760 dof in Python (`decisions.md:6121` to `:6123`), and it contains an EXTRAPOLATED 0.156 s `splu` at 30,000 free edges (`sparse_eigenmode.md:365`). Neither is a CPU profile of a threaded compiled implementation. The proof obligation in 6.2 is therefore unmeetable today, by the record's own contents.

---

## 7. Failure modes and falsifiers

**7.1 The `eigsh` spurious-eigenpair trap.** Shift-invert Lanczos can return a converged pair that is not a solution of the pencil. This is a solver-reliability rule, not a mesh issue, and it is why 5.7 exists: residual `> 1e-6` means INVALID and the retry ladder is `sigma x {1, .996, .992, .988, .984, .980}` (`t4b_t4c_preregistration.md:452` to `:454`). A C++ port inherits the trap and must therefore inherit the ladder, not just the solve.

**7.2 The 2x falsifier.** Any run whose wall exceeds twice its pre-registered estimate without a documented cause is VOID and requires a new pre-registration before any re-run, "whether or not the diagnostics look good" (`decisions.md:5639` to `:5643`). The same shape applies to 3.3's estimate once X is filled.

**7.3 The indefinite-pencil hazard: a variant off by a percent is more dangerous than one obviously wrong.** `sparse_eigenmode.md:588` to `:596` measures the stiffness-side enlargement: `lambda = 26953.0` against a reference `97833.1` at `sigma = 1`, and with the shift moved onto the target, `98360.7 / 98375.3` (`+0.54 % / +1.08 %` off) at `abs(corr_ey) = 0.55` against `0.92`. The document's own conclusion at `:595` to `:596`: "A variant that is within a percent is **more** dangerous here than one is nowhere near, because it looks like a convergence tolerance". A port that gets the pencil slightly wrong will produce numbers that look converged. This is the failure mode 5.4 is sized to catch, and it is the reason the second diagnostic is sized at `1e-8` and not `1e-2`.

**7.4 Silent densification.** The specific hazard of a C++ port: a factoriser that decides a matrix is small enough to fill in, or a binding that marshals a sparse matrix through a dense intermediate, converts the incumbent's 2.58e-3 GB factor (`sparse_eigenmode.md:346`) into something else without failing. Two detectors. First, the factor's reported `nnz(L+U)` and fill per row are recorded per run and compared against the measured rung values `214,641` and `66.9` (`:345`) at the corresponding size; a factoriser reporting zero fill has densified. Second, the inertia check of 2.4: a factoriser that reports a different positive/negative split for the same `M_C` has taken a different path, and at 1444 free edges the expected split is 1444/483/0 (`:530`).

**7.5 Configuration drift.** Covered by 5.8 and by `7.3`'s logic: a change of machine, BLAS, or thread count moves the answer by more than the 1e-11 figure reported in 5.3, so the comparison is void rather than scored. Void is not a soft verdict; it means the run did not test anything.

---

## 8. Open rulings, collected

Principal-only, except for the two rulings recorded in 4.1 and 4.2. Nothing below is decided by this document unless it is marked as ruled.

1. **Licence, and specifically GPL in the factorisation path.** Whether a GPL component is admissible in a library this project ships (4.6). **OPEN (R4d).** R4a is an engineering call and not a clearance, and it no longer depends on this answer. It gates any future factoriser upgrade and not the v1 choice.
2. **Factoriser.** **RULED (R4a): SuperLU**, general sparse LU, unsymmetric, no symmetry exploited, admissible under 2.4 because it assumes nothing about definiteness, and chosen for attribution rather than for speed. The efficient symmetric-indefinite path (MUMPS, MA57, MA97) is **DEFERRED (R4b)** to its own pre-registration, judged against the port's SuperLU result on the same mesh.
3. **Eigen's scope.** **RULED (R4c): none in v1.** The per-cell `2x2` and `3x3` work does not need a vendored header library, and every dependency is a thing to attribute (4.2).
4. **Storage.** CSC against CSR, and whether the zero block of `K_C` is stored or implied (4.3). Cannot be settled before item 2.
5. **Threading model.** OpenMP against TBB against `std::thread` (4.4). Free choice, with mandatory pinning under 5.8.
6. **Binding.** pybind11 against `ctypes` against a C ABI with numpy handoff (4.5).
7. **CUDA.** Not proposed (6.1), and the proof obligation in 6.2 is unmeetable from the current record (6.3).
8. **When the port starts.** Not a design question. On the evidence of 3.1 the trigger would be the next `k = 6` run at the target mesh hitting the 300 s cap, which is already the recorded outcome at 259,760 dof.

---

## 9. What this document does not decide

- It does not clear a licence, a binding, a threading model, or a storage format, and it does not ratify SuperLU as a licence decision. It rules one component (R4a) as an engineering call and records that the call is not a clearance (R4d); the binding, the threading model and the storage format stay open in section 8.
- It does not author a C++ contract, and it does not amend `docs/design/core_contract.md:166` to `:185`. That section owns the interface; this one supplies engineering content.
- It does not assert that a C++ port will be faster. 3.3 leaves the estimate explicitly unfilled, because no measurement exists from which to fill it.
- It does not assert any licence fact as a repository finding, with the one exception recorded at 4.6: that SuperLU ships compiled inside the installed SciPy and that no SuperLU notice accompanies it in that tree is verified. Every other licence statement in 4.1, 4.2 and 4.6 is marked as asserted from general knowledge and unverified against any vendor file in this tree.
- It does not propose CUDA, and it does not add CUDA to any shortlist.
- It does not move any existing verdict. `T4_amp` remains the recorded FAIL, `T4b` and `T4c` remain as recorded in `docs/design/t4b_t4c_preregistration.md`, and the two errata recorded there in section 8 are not reopened here.
- It does not decide the `mode2d` normalisation defect (`decisions.md:7008`). Section 5.2 excludes field scale from the comparison for exactly that reason, following `core_contract.md:327` to `:331`.
- It does not authorise a run. No benchmark, no prototype, and no build is implied by this document having been written.
### 9.1 Corrigenda, appended below the last line so that nothing above it moves

Four statements above did not match the code they describe, and they are corrected here rather than in place because eleven citations point into lines 110 to 272 of this file and a line inserted above them would drift every one of them. The corrections were applied line for line, one line in and one line out, and the 5.9 table was replaced seven lines for seven, so `:244` is still the `1e-11` row and `:245` is still the `1e-8` row.

- **2.1.** There are two solves in `emfit/mode2d.py`, not one. `solve_modes` at `:795` is a sparse shift-invert Lanczos on a standard symmetric pencil with a positive definite mass side: `eigsh(c_free, k=n_k, M=b_free, sigma=sigma, which="LM")` at `:868`, a scalar `sigma`, no `OPinv` and no `LinearOperator` in `:795` to `:934`. `solve_modes_mixed` at `:935` is dense by construction: capped at `_MIXED_DENSE_MAX = 3000` at `:151`, raising at `:1096` to `:1099` above the cap, and below it building `toarray()` pairs at `:1115` to `:1116` for `_dense_eig` at `:1120`. The quoted decisions entry at `:6112` to `:6116` cites `/tmp/c3.py:96-97`, which is not in this tree.
- **2.3.** The `LinearOperator` requirement is a condition the port must meet to pass the cap. It is not a description of the incumbent, which never forms that operator: the standard pencil is handed to ARPACK with `M=b_free`, and the mixed path builds a dense pair instead.
- **2.7.** The dense path is dead in `emfit/eigen.py` (`:176` to `:182`, `:186`, `:196`, `:198`) and alive in `emfit/mode2d.py` (`:1107`, `:1114` to `:1115`, `:1120`). A port that excludes one and not the other has not applied the ruling.
- **5.9.** The table now has four rows and a column stating what each row may certify. `1e-11` certifies nothing. `1e-8` certifies fidelity to the Python on the same pencil and nothing beyond it, because both sides share the arithmetic and therefore share its cancellation: `b_dense = m1_f.toarray() - (c_f @ d_dense) @ c_f.toarray().T` at `:1116` and `e_z[free_n] = 1j * beta * lu_h.solve(c_f.T @ x)` at `:1175` both combine terms that are not scaled to their difference. The two added rows, an analytic anchor and the physics invariants, carry no threshold and no verdict, and they are commitments rather than measurements.

**Consequence for the port, stated once.** A port has to name its reference entry point. A port of `solve_modes` is a port of the path measured to return nothing at `k = 6` at 259,760 degrees of freedom, and a port of `solve_modes_mixed` cannot reach the meshes in 5.6 at all, because M3 at 28,980 and M4 at 30,672 free edges are ten times its cap. The full argument, together with the one adverse analytic cross-check that prompted these rows and the harness defect that prevents it being promoted to a measurement of the incumbent, is in `docs/design/d44_acceptance.md`.
