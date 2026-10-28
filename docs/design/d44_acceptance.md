# Acceptance addendum: what the `1e-8` comparison can and cannot certify

## Status

**New document.** Authored at Dispatch 44, Task 1, and written before any other file was touched in that dispatch. It is the artefact the Dispatch 44 corrigendum entry in `decisions.md` declares, and it is cited from the corrigenda subsection at the end of section 9 of `docs/design/cpp_solver_arch.md`.

**Design and record only.** There is no C++ source, no header and no build. No benchmark in this document was run by it. No threshold is set here for the two rows it adds, and no run is authorised by anything below.

**What it corrects.** Four statements in `docs/design/cpp_solver_arch.md` do not match the code they describe: 2.1, 2.3, 2.7, and the verdict table in 5.9. The corrections are stated here in full and applied in place at the end of section 9 of that file, because eleven citations elsewhere in the tree point into its lines 110 to 272 and moving those lines would drift every one of them.

## 1. Two entry points, and only one of them is "the same solve"

`emfit/mode2d.py` contains two solves, not one, and the design document presented them as one.

`solve_modes` at `:795` builds `c = (k0*k0*m_eps - k_q).tocsr()` at `:860` and `b = m_mu.tocsr()` at `:861`, slices the free degrees of freedom into `c_free` and `b_free` at `:862` to `:863`, and calls `eigsh(c_free, k=n_k, M=b_free, sigma=sigma, which="LM")` at `:868`. `sigma` is a scalar: annotated `float` at `:798`, coerced with `float(sigma)` at `:847` and finite-checked at `:850` to `:851`. There is no `OPinv`, no `LinearOperator`, no `todense`, no `toarray` and no reference to `_MIXED_DENSE_MAX` anywhere in `:795` to `:934`. That is a sparse shift-invert Lanczos on a standard symmetric pencil whose mass side is positive definite, and it densifies nothing at any size.

`solve_modes_mixed` at `:935` takes `dense: bool | None = None` at `:944`, counts `n_e = int(free_e.size)` at `:1087`, and sets `use_dense = (n_e <= _MIXED_DENSE_MAX) if dense is None else bool(dense)` at `:1094` against `_MIXED_DENSE_MAX = 3000` at `:151`. Above that cap it raises, at `:1096` to `:1099`, `NotImplementedError("iterative path pending: A - sigma*B is dense through C D C^T; dense QZ only")`. Below it, it factorises `h` with `splu(h)` at `:1107`, forms `d_dense = lu_h.solve(np.eye(n_n))` at `:1114`, `a_dense = k0*k0*m_eps_f.toarray() - k_q_f.toarray()` at `:1115` and `b_dense = m1_f.toarray() - (c_f @ d_dense) @ c_f.toarray().T` at `:1116`, symmetrises both at `:1117` to `:1118`, and calls `_dense_eig` at `:1120`. That path is dense by construction, regardless of what the caller asks for, because the branch above the cap does not exist.

The sentence quoted at `cpp_solver_arch.md:29`, "Nothing is densified at any size used here, including 259760 degrees of freedom", is therefore true of `solve_modes` and false of `solve_modes_mixed`. Both statements are in the record, and 2.1 and 2.7 of the design document read as though the tree contained only the first.

**Consequence for acceptance.** A port has to name its reference entry point before any comparison is meaningful, and neither choice is free.

- A port of `solve_modes` is a port of the path that has been measured to return nothing at `k = 6` at 259,760 degrees of freedom. Its comparison target is a solver that has also been measured to return nothing there, so a `1e-8` agreement on the acceptance meshes says nothing about whether either would work at the target mesh.
- A port of `solve_modes_mixed` is a port of a dense QZ path that stops at 3000 free edges. The meshes named in 5.6 are M3 at 28,980 and M4 at 30,672 free edges, which are outside that path's domain by a factor of ten, so it cannot be the reference for them either.

The remaining option, and the only one this addendum can recommend, is to port `solve_modes` and to say in the pre-registration that the port is accepted as a faithful reproduction of an incumbent whose behaviour at the target mesh is itself unresolved.

## 2. The `LinearOperator` requirement is a requirement on the port, not a description

The linear algebra in 2.3 is right: `M_C` is symmetric indefinite, it cannot be passed as the `M` argument of `eigsh`, and a driver that has to exceed the incumbent's cap must be handed `(K_C - sigma*M_C)^{-1} M_C` as an operator.

What 2.3 does not say is that nothing in `emfit/` forms that operator. `solve_modes` passes `M=b_free`, a positive definite mass matrix, and lets ARPACK build and factorise `C - sigma B` internally. `solve_modes_mixed` never builds the operator at all: it builds the dense pair at `:1115` to `:1116` and calls `_dense_eig` at `:1120`, which is why it stops at 3000. The word "mandatory" in 2.3 is therefore correct about what a port needs and misleading about what exists. Read it as the condition a port must meet in order to pass the cap, and note that meeting it is exactly the work the incumbent never did.

## 3. The verdict table, as it now stands

Four rows, one of which is citable. This is the table at `docs/design/cpp_solver_arch.md:242` to `:248`, repeated here so that the re-scoping is legible without reading the other file.

| statistic | threshold | verdict if exceeded | citable for |
|---|---|---|---|
| `|rel|` on `beta^2`, both meshes | `1e-11` | PASS or FAIL, reported only | nothing: not validation, not port defect (5.3) |
| `|rel|` on `beta^2`, same run | `1e-8` | PASS or FAIL, binding | fidelity of the port to the Python on the same pencil, and nothing beyond it (5.4) |
| analytic anchor (section 4 below) | not set here | reference only, no verdict | whether the Python itself is right. UNMEASURED |
| physics invariants (section 4 below) | not set here | reference only, no verdict | passivity, mode purity and `beta` against an analytic value. UNMEASURED |

The thresholds do not move. `1e-11` is still reported and still carries no verdict weight. `1e-8` is still binding and still PASS or FAIL. `1e-6` on the residual on either side is still not a result, self-agreement in 5.5 is still bitwise and its failure still invalidates the harness rather than the port, and the environment block of 5.8 still voids any comparison when it differs. What changes is the fourth column: `1e-8` is now scoped to fidelity and to nothing else, and the two rows below it are added as commitments. Those three are retained and were not dropped: they sit outside the criterion table because they are not accuracy criteria and not wrongness criteria.

## 4. The port-fidelity limitation, stated as cancellation

A `1e-8` agreement between the port and the Python on the same pencil is not evidence that either is correct. Both sides run the same arithmetic on the same matrices. Where the incumbent loses accuracy through cancellation, the port loses it identically, the difference stays small, and the statistic reports PASS. The comparison is structurally blind to the error it looks most like it would catch.

The cancellation is nameable in the source. `b_dense = m1_f.toarray() - (c_f @ d_dense) @ c_f.toarray().T` at `:1116` subtracts a dense product from a mass matrix, and `e_z[free_n] = 1j * beta * lu_h.solve(c_f.T @ x)` at `:1175` forms the same `C D C^T` product again to recover the field. The terms being combined are not scaled to their difference, so the relative accuracy of the result is not bounded by the relative accuracy of its terms. No measurement of that cancellation exists in this tree, and none is claimed here: this is recorded as an unmeasured risk and as the reason the `1e-8` row is scoped to fidelity.

The practical consequence is that the acceptance gate can certify a port that reproduces the incumbent faithfully and inherits its error. The gate is worth keeping, because a port that is faster and slightly different is the failure mode the pre-registration was written to catch. It is not worth keeping alone, which is what the two added rows are for.

## 5. The one experiment that pointed at an analytic anchor, and what it showed

An analytic cross-check was run at one mesh and the result is adverse to the incumbent. The figures below are read from `.scratch/s10118_result.txt` and from the run log at `.scratch/logs/s10118_basis.py`.

- The mesh has `free_edges = 1444`, `free_nodes = 483`, `n_dof = 1927`, and `mixed_dense_max = 3000` in the logged `dof` line, so the mixed path ran in its dense branch.
- `beta` analytic is `309.9818636706751` and `beta` mixed is `326.9107654423116`, a difference of `16.928901771636447`, or `+5.46` per cent.
- Passivity is `1.0142899588259895` analytic and `2.0013807961296104` mixed.
- The verdict line reads `VERDICT: mode_purity > 0.95: NO (mixed 0.206827 vs analytic 0.013875; amp_mismatch mixed 2.366e+04 vs analytical 1.491e+04)`.
- The overlap between the analytic and mixed fields is `corr_e_z = 0.11916043239134175` and `corr_e_y = 0.9207707848111418`.
- The mode residual is `4.849473685711963e-18`, so the modes themselves are converged and the disagreement is not a convergence artefact.

A `beta` that is high by 5.46 per cent, a passivity figure that doubles and a mode purity that fails by a factor of fourteen are not a `1e-8` problem. They are the shape of an error that a same-pencil comparison cannot see, and they are the reason the third and fourth rows exist in the table above.

The passivity figure is recorded with a caveat. There are no `s11` or `s21` keys anywhere in the result file, so the S-matrix element from which a passivity number would be computed is not in the artefact, and the derivation of `1.0142899588259895` and `2.0013807961296104` cannot be reconstructed from what was written down. The number is reported here because it was produced by the run, and it is not citable as a measurement of passivity until the key it came from is named.

## 6. The harness defect in that experiment

The comparison is not the comparison it appears to be. At `.scratch/logs/s10118_basis.py:218` the harness calls `m2.assemble_mixed(...)` and then rebuilds the pencil's Schur complement by hand:

- `:219` `h_blk = (k_zz[free_n][:, free_n] - K0*K0*m_zz[free_n][:, free_n]).tocsc()`
- `:221` `lu = splu(h_blk)`
- `:222` `z_free = lu.solve(np.asarray(c_f.T @ x_t).ravel())`
- `:223` to `:224` `e_z_node[free_n] = np.abs(beta * z_free)`

The solver already performs exactly this recovery, at `emfit/mode2d.py:1175`, as `e_z[free_n] = 1j * beta * lu_h.solve(c_f.T @ x)`. The harness did not call it. It re-derived the same formula independently and then took the modulus, which drops the `1j` phase that `:1175` keeps. So the quantity compared against the analytic field was a second, hand-written implementation of the incumbent's own expression, not the incumbent's output. A disagreement between the two would have been a bug in the harness. The disagreement that was found is therefore attributable to the formula, and the harness is the wrong instrument for deciding which side of it is wrong.

This is a harness defect and not a solver finding. It also means the experiment has to be rerun through `mode2d.py:1175` before any of the figures in section 5 are promoted from adverse indication to measurement of the incumbent, and the passivity caveat in that section stands until it is.

## 7. The marker that is withdrawn

The Dispatch 43b entry at `decisions.md:8429` refused a superseded marker on the ground that `docs/design/sparse_eigenmode.md`, 43,278 bytes, contains no "superseded", no `6.06`, no `1e-12` figure of the kind named in that brief, no "validat" and no "span". Dispatch 44 withdraws the marker question rather than re-deciding it, and the premise is now explained rather than merely refused.

`docs/design/sparse_eigenmode.md` does carry notes of its own: an erratum pointer at `:6`, the statement at `:12` that section 4.2 supersedes section 4 as an implementation recipe, the statement at `:13` that section 4 is left standing as the record of the defect, and a primary-recommended-path line at `:15`. Those are the file's own errata and they are not the marker that was in question.

The two errata that the marker was about are in `docs/design/t4b_t4c_preregistration.md`: errata E1 at `:688` and errata E2 at `:716`, both inside section 8, which opens at `:546`, with the append-only note for that section at `:732` to `:736`. They are recorded there and they were never missing. The citation in the brief was a cross-file transposition between two design documents of similar length, not a miscount inside one of them. No marker is applied to `docs/design/sparse_eigenmode.md` now or later on this ground, and no edit to that file is authorised by this addendum.

## 8. Why the corrections sit at the end of section 9

Eleven citations in the tree point into `docs/design/cpp_solver_arch.md` above line 304, and every one of them would drift if a line were inserted above it:

- `decisions.md:8376` cites `:166` and `:171`; `:8380` cites `:193`, `:197`, `:201` and `:244` to `:247`; `:8404` cites `:272`; `:8419` cites `:212` and `:214`; `:8421` cites `:244` and `:193`; `:8423` cites `:112`; `:8425` cites `:110`.
- `docs/design/d43b_extraction_audit.md:644` cites `:164` to `:178` with `:245`; `:654` cites `:203`; `:671` cites `:245`.

The rewrite of 2.1, 2.3 and 2.7 was therefore done line for line, one line in and one line out, and the replacement of the 5.9 table was done at seven lines in and seven lines out so that the `1e-11` row stays at `:244` and the `1e-8` row stays at `:245`. The substantive corrections, with their reasoning, are appended after `:304` as a corrigenda subsection, where they displace nothing.

## 9. What this document does not decide

- It does not set a threshold for the analytic anchor or for the physics invariants. Neither is measured, and fixing a bar before the instrument that produces the number has been repaired would repeat the error the `T4_amp` post-mortem records.
- It does not decide which analytic anchor to use, at which mesh, or with which normalisation. The `mode2d` normalisation defect at `decisions.md:7008` is still open, and section 5.2 of `cpp_solver_arch.md` excludes field scale from the comparison for that reason.
- It does not promote the section 5 figures to measurements of the incumbent. They are an adverse indication produced by a harness that does not call the code under test.
- It does not choose the reference entry point for the port. Section 1 states the constraint and the cost of each option; the choice is a ruling this document is not authorised to make.
- It does not reopen `T4b`, `T4c`, `T4_amp`, or the errata in `docs/design/t4b_t4c_preregistration.md` section 8.
- It does not authorise a run. No benchmark, no prototype and no build is implied by this document having been written.

## Provenance

`[VERIFIED]` means read directly from the named file during this session. `[RELAYED]` means carried from another document without independent reading, and untagged statements are `[RELAYED]`.

- `[VERIFIED]` every line reference into `emfit/mode2d.py`, `emfit/eigen.py`, `.scratch/logs/s10118_basis.py`, `decisions.md`, `docs/design/cpp_solver_arch.md`, `docs/design/sparse_eigenmode.md` and `docs/design/t4b_t4c_preregistration.md` in sections 1, 2, 3, 6, 7 and 8, and every figure in section 5, which was read from `.scratch/s10118_result.txt`.
- `[VERIFIED]` `docs/design/sparse_eigenmode.md` is 777 lines and 43,278 bytes.
- The inertia triple `1444 / 483 / 0` and the conditioning figures quoted in `cpp_solver_arch.md` 2.3 are attributed there to `docs/design/sparse_eigenmode.md:529` to `:533` with the dimension triple at `:336`; those lines were not opened in this session, so the tables are `[RELAYED]`.
- The `259,760` degrees of freedom, the `k = 6` outcome and the `300 s` cap are the design document's own figures and are `[RELAYED]` here.
- The claim that `emfit/eigen.py` is dead code at the sizes in question, and the `315.64 MiB` and `155 s` measured alternative quoted in 2.7 of the design document, are `[RELAYED]` from `decisions.md:6398` to `:6402`.
