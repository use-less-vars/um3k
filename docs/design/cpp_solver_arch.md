# A C++ architecture for the emfit 2D eigenproblem

## Status

**New document.** Authored at Dispatch 42. There was no `docs/design/cpp_solver_arch.md` in the tree before this pass and none in history; this is not a revision of anything, and it supersedes nothing.

**Design only.** There is no C++ source, no header, no CMake file, and nothing in `emfit/` or `tools/` that knows this document exists. No benchmark in this document was run by it.

**Every component and licence choice is an OPEN RULING.** Section 4 lists the options and the cost of each; section 8 collects them; section 9 lists what is deliberately not decided. This document recommends and does not decide, for the reason given in 4.0: a docs dispatch is not the place to create a legal position that an append-only log will then carry.

---

## 1. Purpose and scope

**1.1 The question this document answers.** Given that the adopted 2D eigenproblem path is a Python shift-invert Lanczos solve that has been measured to 259,760 degrees of freedom and measured to return nothing at `k = 6` on that same matrix, what would a C++ implementation of that same solve have to look like, and how would anyone know it was right before trusting it?

**1.2 The question it does not answer.** It does not ratify a library, a licence, a Python/C++ binding, a threading model, or a matrix storage format. Section 4 presents each as an option with its cost and its ratification requirement. Nothing in section 4 is a decision.

**1.3 It does not author a second C++ contract.** `docs/design/core_contract.md:166` opens `### C++ FIT production port`, and that subsection already fixes the interface shape: inputs are "the same contract, plus a thread count and a dt policy" (`:168` to `:170`), returns are `e`/`h` samples at declared probes and planes plus "the `dt` actually used, the three-valued status (item 5), and the required provenance core" (`:172` to `:173`), and two things it "cannot be asked for" are fixed at `:179` to `:185` (in-memory mutation as a variation mechanism, and source exposure for `inspect.getsource`). This document supplies the *engineering* content that section leaves open, namely which factoriser, which storage, which threads, which binding, and how the port is accepted. It does not restate the interface shape, and where the two ever appear to disagree, `core_contract.md` wins.

**1.4 Scope note on which core.** `core_contract.md:166` names the FIT time-domain port. This document is about the 2D eigenproblem member (`emfit/mode2d.py:795`, `:935`, identified as Core A at `core_contract.md:300` to `:301`). The two share the contract; they do not share a cost model, because one is a shift-invert factorisation and the other is a leapfrog march. Nothing here should be read as a statement about the time-domain core.

**1.5 Why the acceptance criterion gets half the document.** A C++ port that is faster and slightly wrong is the failure mode this whole exercise risks, and it is not detectable by inspection. Section 5 is therefore written as a pre-registration in the style of `docs/design/t4b_t4c_preregistration.md`: the statistic, the thresholds, the meshes, the environment pinning and the verdict vocabulary are fixed here, before any C++ exists, so that the port cannot later be judged against whatever it happens to produce.

---

## 2. The incumbent being replaced, stated as measurement

**2.1 The adopted solve.** `decisions.md:6112` to `:6116`: "The solve is shift-invert Lanczos: `eigsh(C, k=nk, M=B, sigma=sigma, which="LM")` (`/tmp/c3.py:96-97`), which factorises `C - sigma B` sparsely and returns the `k` eigenvalues nearest `sigma`. Nothing is densified at any size used here, including 259760 degrees of freedom."

**2.2 The pencil actually run.** The mass-side enlarged pencil of `docs/design/sparse_eigenmode.md:550` to `:584`:

| object | shape | content |
|---|---|---|
| `K_C` | `(free_e+free_n) x (free_e+free_n)` | `[[A, 0], [0, 0]]` |
| `M_C` | same | `[[m1_f, -c], [-c^T, h]]` |
| factorised matrix | same | `K_C - sigma*M_C`, one `splu` |
| `sigma` | scalar | `0.999 * beta_sq`, pre-registered in the result |

**2.3 The `LinearOperator` form is mandatory, not stylistic.** `M_C` is symmetric **indefinite**, so it cannot be passed as the `M` argument of `eigsh`. The driver must be handed `(K_C - sigma*M_C)^{-1} M_C` as an operator and must never see `M_C` as an `M`. Evidence, MEASURED at `free_e = 1444` with `M_C` of order 1927 (`sparse_eigenmode.md:529` to `:533`, with the dimension triple at `:336`):

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

**2.7 The dense path stays dead.** `decisions.md:6398` to `:6402` records the rejection: `todense()` at `emfit/eigen.py:186`, `sla.eigh` at `:196` and `:198`, and a guard that raises above `max_dense = 3000` at `:176` to `:182`. "It cannot reach 115232 or 259760 degrees of freedom, and it must not be refactored to try; 315.64 MiB and 155 s is the measured alternative." Any C++ proposal that reaches for a dense solve on these meshes is contradicting a recorded ruling, not proposing an optimisation.

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

## 4. Component selection: OPEN RULINGS

**4.0 The framing, stated once.** Nothing below is decided, and this document does not draft the decision. Two reasons. First, a licence ruling made inside a documentation dispatch becomes a legal position the project never actually took, and append-only logs then carry it forward. Second, three of the five choices are downstream of the factoriser, and the factoriser choice is itself not settled, so deciding them now would be deciding the wrong order.

Where a licence appears below, it is **asserted from general knowledge and not verified against any vendor file in this tree; verify before ratification.** No licence text ships with this repository and none was consulted.

### 4.1 Sparse direct factorisation

| option | what it is | cost | what ratification must establish |
|---|---|---|---|
| SuperLU | unsymmetric LU with pivoting, ships inside SciPy's `splu` which the incumbent already calls | uses no symmetry; doubles index storage for a symmetric matrix | that an unsymmetric path is acceptable, and which licence applies |
| SuiteSparse/UMFPACK | unsymmetric multifrontal LU; the same SuiteSparse tree also carries the symmetric-indefinite multifrontal paths | external build dependency; multifrontal memory is supernode dependent | licence class, and whether the GPL branch is acceptable (4.6) |
| Eigen | header-only C++ templates; `SparseLU` unsymmetric, `SimplicialLDLT`/`LLT` symmetric positive definite | `SimplicialLDLT` is excluded by 2.4; `SparseLU` is the surviving member | licence class for a header-only vendored dependency |
| LAPACK + BLAS only | the incumbent's language, banded or dense blocked | `dpotrf` excluded by 2.4; `dsytrf` (Bunch-Kaufman) survives but is not sparse | whether a non-sparse indefinite path is admissible at all (it is not, per 2.7) |

**Why not decided here.** The surviving set is determined by 2.4, which is a linear-algebra fact; picking among the survivors is determined by licence and by build-portability, which are principal decisions. The recommendation, if a recommendation is wanted: an unsymmetric LU with pivoting is the conservative choice because it needs nothing from the matrix, and a symmetric-indefinite multifrontal path is the efficient choice because the matrix is symmetric and the inertia is already being computed as a check (2.4).

### 4.2 Eigen's role and scope

Eigen is named separately because it can enter at four different depths and the choice is not one choice:

1. **dense small blocks only** (the `2x2` and `3x3` per-cell work),
2. **sparse assembly only** (triplet lists, no solve),
3. **the factorisation itself** (`SparseLU`),
4. **the eigensolver** (not proposed; the driver stays the same algorithm as 2.1, in C++ or in Python).

**Why not decided here.** Whether Eigen is permitted to touch the factorisation at all is constrained by 2.4 (its SPD members are excluded, its `SparseLU` is not), and by the licence question in 4.6. Depth 1 or 2 is a low-risk vendoring decision; depth 3 is the factoriser decision wearing a different name.

### 4.3 Matrix storage

CSC against CSR, and the ordering point: **the storage choice is downstream of the factoriser.** A factoriser that wants column access wants CSC; one that assembles row-wise prefers CSR and a transpose. There is also the question this project actually faces, which is whether the `(free_e+free_n)` block structure of 2.2 is stored as one assembled matrix with the zero block written explicitly, or as two stacked matrices with the zero block implied. The former is simpler and wastes three quarters of the index space at the ratio 3:1 that `free_n/free_e = 483/1444` (`sparse_eigenmode.md:336`) implies; the latter is faster to build and harder to hand to a third-party factoriser.

**Why not decided here.** It cannot be decided before 4.1, because the right answer is whatever the chosen factoriser wants.

### 4.4 Threading

OpenMP against TBB against `std::thread`. This is a component choice **and** part of the acceptance criterion, not a performance detail, for the reason in 5.8: thread count alone moves the answer by more than the primary target. The measured figure is `decisions.md:7192`: "The smallest non-zero null obtainable without a re-solve is **8.13e-11** relative, from BLAS thread count 1 against 4 on the same capture."

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

The two licence facts that bear on it are **asserted from general knowledge and not verified against any vendor file in this tree; verify before ratification**: SuperLU is BSD-3-Clause, and UMFPACK is GPL-2.0-or-later. If the distribution boundary for this project is a Python package that a user installs, then a GPL factoriser is a different proposition from a GPL tool used in-house, and the answer changes which of the survivors in 4.1 is even a candidate. That is the principal's call, and it is the reason 4.1 is not decided here.

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

### 5.3 Primary target

**`|rel| <= 1e-11`, the registered primary target, carrying a PASS or FAIL verdict.**

**The caveat belongs in the same paragraph, not in an appendix.** This target sits at or below the measured round-off floor of the reference itself, and below the post-processing noise bound. `decisions.md:6133` to `:6135` records a relative error of **9.79e-12** at 9560 degrees of freedom and says in the next breath that "the error grows with refinement ... and it licenses no convergence rate". The smallest non-zero null obtainable without a re-solve is **8.13e-11** (`decisions.md:7192`, 5.8), from BLAS thread count 1 against 4 on the same capture, and it is *above* this target.

The caveat and the verdict coexist, and neither cancels the other. The threshold is registered as a falsifiable target in the sense of 5.0: a result at or outside `1e-11` is scored **FAIL** and a result inside it is scored **PASS**. What the caveat fixes is the *interpretation* of that verdict, not its existence. **A FAIL at `1e-11` is not by itself evidence that the port is wrong, because the instrument's own floor sits at or above this threshold; and a PASS at `1e-11` is a stronger result than the threshold implies.** Both readings are registered here, before any C++ exists, so that no later reader can call a 1.4e-11 disagreement a surprise or a 9.8e-12 agreement a validation.

### 5.4 Second statistic: the achievable diagnostic

**`|rel| <= 1e-8` on the same eigenpair, same mesh, same run.** This is achievable above the measured noise floors recorded in 5.3, and tight enough to catch a wrong pencil, a wrong `sigma`, or a silent densification that changes rounding. It is the *second* statistic: a gate that is expected to pass, so a failure here is diagnostic of a real port defect rather than of instrument noise. It carries a PASS or FAIL verdict of its own. The `1e-11` row in 5.3 is the registered primary target and is scored on its own terms, with the caveat above attached to it.

### 5.5 Third statistic: Python-side self-agreement

The Python solver run against itself on the same mesh, thread count pinned to 1, must reproduce **bit-for-bit**. What it actually does is reported. This calibrates the harness before the port is judged by it: if the Python solver does not agree with itself under the pinning of 5.8, no cross-language comparison on that machine is meaningful, and the run is abandoned rather than scored.

### 5.6 Meshes, both required

| mesh | free edges | spec | source |
|---|---|---|---|
| M4 | **30,672** | `58/44/35-17-18` | `tools/host/sparse-probe/out_mesh/mode_overlap.json:285` to `:286`, with `n_e = 30672`, `n_n = 10231`, `free_e = 30672` at `:299` to `:301` and `sigma = 96335.2458966532` at `:294` |
| target class | **30,000** | extrapolated target architecture | `docs/design/sparse_eigenmode.md:355` |

M4 is a measured mesh and is the mesh on which the port is judged. The 30,000 class mesh is an extrapolated target (`sparse_eigenmode.md:357` to `:360`) and is run to show that the port scales past the measured rungs; per `:359`, "Nothing here was measured at the target mesh", so a result there is reported as a first data point and not as a confirmation of the extrapolation.

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

This block exists because of `decisions.md:7192`, quoted: "The smallest non-zero null obtainable without a re-solve is **8.13e-11** relative, from BLAS thread count 1 against 4 on the same capture." A thread-count change alone moves the answer by 8.13e-11, which is 8 times the primary target in 5.3. Without pinning, the primary target is not measurable and the secondary target is not attributable.

One honest qualification, recorded so the block is not over-read: `decisions.md:7365` states that "the `8.13e-11` null demonstrates **determinism** ... not **repeatability** across the configuration changes a gate has to survive." This is exactly why 5.8 pins the configuration rather than treating the number as a repeatability bound. The number bounds what configuration drift does, which is the thing being pinned.

### 5.9 Verdict vocabulary

**PASS** and **FAIL**, and only those two. "Close" is not a verdict. "Within tolerance except for one pair" is a FAIL with a note.

| statistic | threshold | verdict if exceeded |
|---|---|---|
| `|rel|` on `beta^2`, registered primary target, both meshes | `1e-11` | FAIL (see the caveat in 5.3) |
| `|rel|` on `beta^2`, second achievable diagnostic, same run | `1e-8` | FAIL (diagnostic of a port defect) |
| Python self-agreement, 5.5 | bitwise | FAIL (harness invalid) |
| residual, either side | `1e-6` | not a result |
| environment block, 5.8 | as registered | comparison void |

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

**7.5 Configuration drift.** Covered by 5.8 and by `7.3`'s logic: a change of machine, BLAS, or thread count moves the answer by more than the primary target, so the comparison is void rather than FAIL. Void is not a soft verdict; it means the run did not test anything.

---

## 8. Open rulings, collected

Principal-only. Nothing below is decided by this document.

1. **Licence, and specifically GPL in the factorisation path.** Whether a GPL component is admissible in a library this project ships (4.6). This gates 4.1 and therefore 4.2 and 4.3.
2. **Factoriser.** Which of the survivors in 4.1, given 2.4. Recommendation if one is wanted: unsymmetric LU with pivoting is conservative, symmetric-indefinite multifrontal is efficient.
3. **Eigen's scope.** Depth 1 or 2 (small blocks, assembly) against depth 3 (the factorisation) against not at all (4.2).
4. **Storage.** CSC against CSR, and whether the zero block of `K_C` is stored or implied (4.3). Cannot be settled before item 2.
5. **Threading model.** OpenMP against TBB against `std::thread` (4.4). Free choice, with mandatory pinning under 5.8.
6. **Binding.** pybind11 against `ctypes` against a C ABI with numpy handoff (4.5).
7. **CUDA.** Not proposed (6.1), and the proof obligation in 6.2 is unmeetable from the current record (6.3).
8. **When the port starts.** Not a design question. On the evidence of 3.1 the trigger would be the next `k = 6` run at the target mesh hitting the 300 s cap, which is already the recorded outcome at 259,760 dof.

---

## 9. What this document does not decide

- It does not ratify a library, a licence, a binding, a threading model, or a storage format. Every one of those is in section 8.
- It does not author a C++ contract, and it does not amend `docs/design/core_contract.md:166` to `:185`. That section owns the interface; this one supplies engineering content.
- It does not assert that a C++ port will be faster. 3.3 leaves the estimate explicitly unfilled, because no measurement exists from which to fill it.
- It does not assert any licence fact as a repository finding. Every licence statement in 4.1, 4.2 and 4.6 is marked as asserted from general knowledge and unverified against any vendor file in this tree.
- It does not propose CUDA, and it does not add CUDA to any shortlist.
- It does not move any existing verdict. `T4_amp` remains the recorded FAIL, `T4b` and `T4c` remain as recorded in `docs/design/t4b_t4c_preregistration.md`, and the two errata recorded there in section 8 are not reopened here.
- It does not decide the `mode2d` normalisation defect (`decisions.md:7008`). Section 5.2 excludes field scale from the comparison for exactly that reason, following `core_contract.md:327` to `:331`.
- It does not authorise a run. No benchmark, no prototype, and no build is implied by this document having been written.
