# Dispatch 43b Task B: extraction-layer audit of `emfit/mode2d.py`

Read-only audit. Contract artifact written after the reads, before any other edit.

## 0. Fences held, and what this file is

- Nothing under `emfit/` was edited. `emfit/mode2d.py` at the end of this work still hashes
  `9b74d83d7b2c6b0df5b362a391df39dd8940378195b5faef1efe14d84febe032`, 1390 lines, 58509 bytes.
- No existing design document was edited. `docs/design/d43b_acceptance.md` is untouched.
- This file is new. Nothing was committed; the supervisor commits.
- Task C and Task D were not started.
- Every line number below was resolved by content search in this session, not copied from a
  brief. Where a brief's number is wrong the brief is corrected in place in section 5.

File under audit:

| fact | value |
|---|---|
| path | `emfit/mode2d.py` |
| lines | 1390 |
| bytes | 58509 |
| sha256 | `9b74d83d7b2c6b0df5b362a391df39dd8940378195b5faef1efe14d84febe032` |
| module `__all__` | 12 names, `:91` to `:104`, including `Mode2D`, `solve_modes`, `solve_modes_mixed` |

Method note, recorded because it bounds what the evidence is worth: `host_bash` is banned in
this session (`host_bash:banned`), so all shell evidence was produced through `DockerCodeRunner`
against `/workspace`, which is this workspace. The `mode2d.py` inside that container hashes to
the same digest as the host file, so the container reads are reads of the file under audit. A
second tool limitation is worth recording: neither `FileSearchTool` nor the `FileEditor` grep
honours a `^` anchor (a pattern like `^def \w+` returns zero matches on a file that plainly
contains `def` at column 0), and `FileEditor` grep treats `|` as a literal. Regex work was
therefore done with plain patterns in the container, where `grep -nE` behaves normally.

## 1. Findings summary

1. **Two solvers, one dense, one sparse, and they solve different pencils.** `solve_modes`
   (`:795`) is transitive (`e_z := 0`), sparse, uncapped, ARPACK shift-invert at `:868`.
   `solve_modes_mixed` (`:935`) carries the transverse plus longitudinal pair, is dense-only, and
   raises `NotImplementedError` above 3000 free edges (`:1094` to `:1099`).
2. **The mixed solver's densification is unconditional and sits downstream of an explicit dense
   inverse.** `d_dense = lu_h.solve(np.eye(n_n))` at `:1114` forms `D = inv(k_zz - k0^2 m_zz)` as
   an `n_n x n_n` dense array, the two pencil blocks are materialised with `.toarray()` at
   `:1115` and `:1116`, and the pencil goes to a dense QZ at `:1120`.
3. **The module's only shipped consumer of a `Mode2D` is dead code.**
   `ModalPort.from_mode2d` (`emfit/modalport.py:194`) has zero call sites: a repo-wide search for
   the name returns the definition, its own error string at `:217`, and one scratch note that
   already records the zero (`.scratch/logs/s10118_basis.py:12`).
4. **Neither solver has a production caller inside `emfit/`.** Every call site of
   `solve_modes(` or `solve_modes_mixed(` is in `tests/`, `.scratch/` or `tools/host/`.
5. **The measured M4 record was not produced by the module solver.** At 30672 free edges the
   module would raise at `:1096`; the M4 numbers come from harness route C, which builds its own
   `LinearOperator` and hands `OPinv=` to `eigsh` (`tools/host/sparse-probe/rung4_routeC_probe.py:694`
   to `:696`).
6. **The operator-inverse form that `cpp_solver_arch.md` 2.3 calls mandatory exists only in
   harness code.** `OPinv` occurs 0 times in `emfit/mode2d.py` and 4 times in
   `tools/host/sparse-probe/sparse_solver_test.py` (`:493`, `:595`, `:714`, `:867`).
7. **The extraction layer proper (`emfit/modal.py`, `emfit/ports.py`) never sees a mode from
   `mode2d`.** It consumes 3-D FIT plane captures. The bridge that would carry a 2-D mode into it
   is the dead `from_mode2d`, so today the basis is assembled at each call site in harness code.
8. **The dense path the module uses is ruled dead by `cpp_solver_arch.md` 2.7, but 2.7 is written
   about a different module.** 2.7 cites `emfit/eigen.py:176` to `:182`, `:186`, `:196`, `:198`,
   all of which verify; it does not cite `emfit/mode2d.py`. The number 3000 appears in both
   modules as two different guards on two different solves.

## 2. The five questions

**Provenance, stated before the answers.** `docs/design/d43b_acceptance.md` (section "Task B's
five questions") records verbatim: "NOT TRANSMITTED. This brief (Dispatch 43b, Task A-close) does
not contain Task B or its five questions, and no earlier message in this session contains them."
The five questions therefore do not exist as an artifact in this tree. What the dispatch to this
worker did carry is five verification claims about `emfit/mode2d.py`. Those five propositions are
the only surviving record of what the five questions were about, so the five sections below audit
the five propositions and give each a verdict. This is a disagreement with the acceptance artifact
and is entered in section 5, item 1. The propositions are not guessed: they are reproduced in the
wording they arrived in, and each is checked against the file.

### Q1. `solve_modes` uses sparse shift-invert `eigsh(c_free, k=n_k, M=b_free, sigma=sigma, which="LM")` at `:868`

**VERDICT: TRUE.**

```
868:    vals, vecs = eigsh(c_free, k=n_k, M=b_free, sigma=sigma, which="LM")
```

Content check, not just the line: `solve_modes` is defined at `:795`, returns `Mode2D` (`:804`,
`:917`), and its `eigsh` call passes a pre-factorised shift through `sigma`, so ARPACK factorises
`c_free - sigma*b_free` sparsely. No `todense()`, no `toarray()`, no `_MIXED_DENSE_MAX` and no
`NotImplementedError` occurs anywhere between `:795` and `:934`. `solve_modes` is uncapped.

### Q2. `OPinv` appears 0 times in `mode2d.py`, so there is no custom operator inverse anywhere

**VERDICT: TRUE as written about the module, FALSE as a statement about the tree.**

```
$ grep -c OPinv emfit/mode2d.py
0
```

The module contains no `OPinv=` and no `LinearOperator`. The second clause, "no custom operator
inverse anywhere", does not survive a repo-wide check:

```
tools/host/sparse-probe/sparse_solver_test.py:493:                OPinv=op.operator(), maxiter=5000,
tools/host/sparse-probe/sparse_solver_test.py:595:                OPinv=op_B.operator(), maxiter=5000,
tools/host/sparse-probe/sparse_solver_test.py:714:                   OPinv=op_B2.operator(), maxiter=5000,
tools/host/sparse-probe/sparse_solver_test.py:867:            OPinv=op_C.operator(), maxiter=5000,
tools/host/sparse-probe/rung4_routeC_probe.py:696:            OPinv=op_C.operator(), maxiter=5000,
```

with `LinearOperator` constructed at `rung4_routeC_probe.py:258` to `:259`. This is the
load-bearing distinction for a C++ port: the form `cpp_solver_arch.md` 2.3 calls "mandatory, not
stylistic" is implemented, but only in probes under `tools/host/sparse-probe/`, never in the
shipped package.

### Q3. Densification exists in `solve_modes_mixed`

**VERDICT: TRUE. Q3 = YES.** See section 3, which is the required contradiction paragraph.

```
1114:    d_dense = lu_h.solve(np.eye(n_n))              # D = inv(k_zz - k0^2 m_zz)
1115:    a_dense = k0 * k0 * m_eps_f.toarray() - k_q_f.toarray()
1116:    b_dense = m1_f.toarray() - (c_f @ d_dense) @ c_f.toarray().T
1117:    a_dense = 0.5 * (a_dense + a_dense.T)
1118:    b_dense = 0.5 * (b_dense + b_dense.T)
1120:    lam, vecs = _dense_eig(a_dense, b_dense)
```

### Q4. `lu_h = splu(h)` at `:1107`

**VERDICT: TRUE.**

```
1105:    h = (k_zz[free_n][:, free_n] - k0 * k0 * m_zz[free_n][:, free_n]).tocsc()
1106:    try:
1107:        lu_h = splu(h)
1108:    except RuntimeError as exc:
1109:        raise ValueError(
1110:            f"the longitudinal block k_zz - k0^2 m_zz is singular at "
1111:            f"k0 = {k0!r} ({exc}); nudge k0 off the nodal Dirichlet eigenvalue"
1112:        ) from exc
```

Note what `lu_h` is and is not: it is a sparse factorisation, and it is used twice. Once as a
solve inside the field reconstruction (`e_z[free_n] = 1j*beta*lu_h.solve(c_f.T @ x)`, `:1175`),
and once, at `:1114`, as the generator of an explicit dense inverse. The factorisation is not the
densification; `np.eye(n_n)` is.

### Q5. `raise NotImplementedError("iterative path pending: A - sigma*B is dense through C D C^T; dense QZ only")` at `:1096` (brief said `:1095-1099`)

**VERDICT: TRUE. The line number is exact and the brief's range is too wide by one at each end.**

```
1094:    use_dense = (n_e <= _MIXED_DENSE_MAX) if dense is None else bool(dense)
1095:    if not use_dense:
1096:        raise NotImplementedError(
1097:            "iterative path pending: A - sigma*B is dense through C D C^T; "
1098:            "dense QZ only"
1099:        )
```

`:1094` to `:1099` is the guard; `:1096` is the raise. Both citations are usable. The docstring
at `:1038` to `:1042` states the same reasoning and is the sentence a reviewer should read: "an
iterative path. `A - sigma*B` is **dense** through `c D c^T`, so the ARPACK shift-invert route
used by `solve_modes` is not available here as it stands".

## 3. The contradiction paragraph (Q3 = YES)

Q3 is YES, and taken alone the answer is misleading, which is why this paragraph is required.
Densification exists in `solve_modes_mixed` and it is unconditional: the `.toarray()` calls at
`:1115` and `:1116`, the explicit `lu_h.solve(np.eye(n_n))` at `:1114` and the dense QZ at `:1120`
have no sparse alternative, no size-dependent switch and no fallback. But that densification is
not reachable at the mesh the campaign judges the port on. `use_dense` at `:1094` compares the
free-edge count against `_MIXED_DENSE_MAX = 3000` (`:151`), so the dense block runs only when
`n_e <= 3000`, and the largest measured mesh, `M4_fe30672`, has `free_e = 30672`
(`.scratch/dispatch40_facts.md:146`, and `n_e: 30672` in
`tools/host/sparse-probe/out_mesh/mode_overlap.json:299` to `:301`), which is 10.2 times the cap.
A default `solve_modes_mixed(mesh, k0, dense=None)` call on M4 does not densify anything: it
raises `NotImplementedError` at `:1096` before a single matrix is formed. The M4 record on disk
was produced by something else entirely, harness route C in
`tools/host/sparse-probe/rung4_routeC_probe.py`, which assembles the corrected enlarged pencil,
factors it with `splu(S_C)` at `:674` and calls `eigsh(KC, k=1, M=MC, sigma=sigma, which="LM",
OPinv=op_C.operator(), maxiter=5000)` at `:694` to `:696`, constructing the `Mode2D` result object
itself at `:316`. No module solver is invoked anywhere on that path. So the accurate statement is
three-part and each part matters: the module densifies when it runs, the module refuses to run on
every mesh above 3000 free edges, and the record the port is judged on was produced by code that
does not run the module at all. `docs/design/cpp_solver_arch.md` 2.7 independently rules the dense
path dead ("Any C++ proposal that reaches for a dense solve on these meshes is contradicting a
recorded ruling, not proposing an optimisation"), and 2.7's citations verify against
`emfit/eigen.py`, which is the resonance solve, not this one; the ruling therefore does not name
`emfit/mode2d.py`, but the conclusion transfers without needing it to. A reader who takes "the
dense path stays dead" as covering `mode2d` is right about the outcome and wrong about the
mechanism: at M4 the mixed solver is dead by its own 3000-edge guard, not by the 2.7 ruling.

## 4. The extraction layer, mapped as far as this audit went

The term "extraction layer" resolves, on this tree, to two modules that do not touch `mode2d`:

- `emfit/modal.py` (about 39 KB): `PlaneMode` `:197`, `plane_mode` `:267`, `StationPhasors`
  `:319`, `modal_station_phasors` `:372`, `ModalLine` `:472`, `modal_line_quantities` `:538`,
  `ModalSparams` `:596`, `modal_sparams` `:685`, `ResidualGate` `:763`, `ResidualReport` `:872`.
- `emfit/ports.py` (about 82 KB): `Probe` `:134`, `LumpedPort` `:180`, `DftAccumulator` `:564`,
  `BetaFit` `:772`, `fit_beta` `:861`, `LineFit` `:980`, `StationFit` `:1290`,
  `fit_station_impedance` `:1429`.
- `emfit/modalport.py` (about 17 KB): `ModalPort` `:128`, `from_profile` `:189`,
  `from_mode2d` `:194`, `amplitude` `:299`, `inject` `:316`, `forward_backward` `:335`,
  `s11` `:363`.

The input to that layer is a 3-D FIT plane capture (an npz of `plane_Ey` / `plane_Ez` blocks), not
a cross-section eigenvector. The single function written to connect the two is
`ModalPort.from_mode2d` (`:194`), which requires `mode.mesh.grid_axes` (`:214` to `:220`) and
therefore accepts only meshes from `mode2d.structured_mesh`, `mesh_from_grid` or `box_mesh`. Its
call-site count is zero:

```
$ grep -rn --include='*.py' 'from_mode2d' . | grep -v '^\./\.git/'
./.scratch/logs/s10118_basis.py:12:``ModalPort.from_mode2d`` (emfit/modalport.py:194) has **zero call sites**; the
./emfit/modalport.py:194:    def from_mode2d(cls, mode, cc, axis, index):
./emfit/modalport.py:217:                "from_mode2d needs a 2-D mesh that came from a structured "
```

This is not a new finding: `decisions.md:6829` already records it ("That method
(`emfit/modalport.py:194`, its error string at `:217`) has **zero call sites**"), and
`docs/design/modalport_ownership.md` and the pass-1 report at
`reports/2026-10-26_13-52-03_Design_pass_1__modal_port_pipeline_ownership__and_.md` stage it as
stage 2 of a seven-stage pipeline. What this audit adds is only the confirmation that the tree has
not moved: the count is still zero.

The consequence for extraction is that the effective extraction layer includes undocumented
harness copies. `.scratch/logs/s10118_basis.py` drives `solve_modes_mixed` at `:172` and then
re-implements the solver's own internal reconstruction: mode selection at `:181` to `:217`,
`z_free = lu.solve(c_f.T @ x_t)` at `:223` (the same solve the module performs at `:1175`),
`e_z_node[free_n] = np.abs(beta * z_free)` at `:225`, sign fixing at `:370`, one common scale at
`:371` to `:373`, and `PlaneMode` assembly at `:381`. `s10118_mesh_study.py:355` to `:391` is a
transcription of the same block. A port that is a drop-in replacement for `solve_modes_mixed`
therefore has to be a drop-in replacement for the harness's copy of its internals too, or the
harness keeps the old kernel and the comparison measures the harness.

Call-site inventory, complete as of this audit:

| entry point | call sites |
|---|---|
| `solve_modes_mixed` | `tests/test_mode2d.py:168,207,276,277`; `.scratch/logs/s10118_basis.py:172`; `.scratch/logs/s10118_mesh_study.py:184`; `.scratch/mode2d/c2_slab2.py:91`; `.scratch/mode2d/c2_ident.py:245`; `tools/host/c1-audit/c1_audit.py:545`; `tools/host/c1-audit/pecbox_variant.py:636` |
| `solve_modes` | `tests/test_mode2d.py:208`; `.scratch/mode2d/c2_slab.py:207`; `.scratch/mode2d/c2_oldunits.py:233` |
| `ModalPort.from_mode2d` | none |

`.scratch/mode2d/c2_power.py:431` records the string `"emfit.mode2d.solve_modes_mixed"` as a
provenance label rather than calling it, and `.scratch/mode2d/c2_slab_finish.py:4` names the
function in its docstring. Neither is a call.

`emfit/`-wide, the only mentions of `mode2d` or `Mode2D` outside `mode2d.py` itself are docstring
cross-references in `modalport.py` (`:195`, `:198`, `:199`, `:217`, `:218`). No shipped module
imports either solver.

The M4 ladder agrees with this reading from the other side:
`tools/host/sparse-probe/*.py` imports `emfit.mode2d as m2` but uses only `m2.k0_from_freq`,
`m2.structured_mesh`, `m2.assemble`, `m2.assemble_mixed`, `m2.pec_edge_mask`, `m2.pec_node_mask`
and constructs `m2.Mode2D(...)` by hand (`rung4_routeC_probe.py:316`,
`sparse_solver_test.py:276`). `high_res_run.py:129` copies the guard as a constant with its own
comment, "`MIXED_DENSE_MAX = 3000                 # emfit/mode2d.py:151, guard default`".

## 5. Disagreements

1. **The five questions versus the acceptance artifact.** `docs/design/d43b_acceptance.md`
   records "NOT TRANSMITTED" under "Task B's five questions". The dispatch to this worker carried
   five verification propositions. Section 2 answers the propositions and says so at the top
   rather than claiming to answer questions it cannot read. If the five questions exist as text
   elsewhere, section 2 needs re-aiming against them; the evidence in section 6 does not change.
2. **Q5's brief citation `:1095-1099` versus the tree's `:1096`.** The raise is at `:1096`; the
   guard spans `:1094` to `:1099`. Small, and recorded because the standing rule in
   `d43b_acceptance.md` is content citations with the worker resolving the lines.
3. **"No custom operator inverse anywhere" is false at tree level.** True of `emfit/mode2d.py`
   (0 occurrences), false of the repository (5 occurrences, plus `LinearOperator` construction).
   A C++ port scoped from the module alone will not know that route C exists and works.
4. **`cpp_solver_arch.md` 2.7 versus `emfit/mode2d.py`.** 2.7's citations verify exactly
   (`emfit/eigen.py:176` to `:182` guard, `:186` `todense()`, `:196` and `:198` `sla.eigh`), and
   all of them are about the resonance solve. `emfit/mode2d.py` has a second, independent dense
   path with the same numeric cap (3000) under a different name (`_MIXED_DENSE_MAX`, `:151`
   versus `max_dense`, `eigen.py:122`). The ruling's conclusion covers both; its evidence covers
   one. This is the same shape as the defect class `d43b_acceptance.md` item 9 was written to
   catch, one document over.
5. **The residual tolerance versus 2.1's "nothing is densified".** `cpp_solver_arch.md` 2.1 quotes
   `decisions.md:6112` to `:6116`: "Nothing is densified at any size used here, including 259760
   degrees of freedom." That sentence is true of the route it describes and false if read as a
   statement about the package: `emfit/mode2d.py` densifies, `emfit/eigen.py` densifies up to
   3000, and the mixed solver's own residual metric at `:1029` to `:1036` exists precisely because
   `B = m1 - C D C^T` cannot be treated as an ordinary mass matrix. The two statements are
   reconcilable only if 2.1 is read as scoped to the C++ port's target route, which is how 2.7
   reads, and that scope is not written into the sentence.
6. **`.scratch/logs/sweep3.py:19` to `:22` versus the main tree.** That harness appends
   `.scratch/wt-m3b-diag/emfit` to `emfit.__path__` with the comment "`emfit.modal` lives only in
   the m3b worktree". The main tree has `emfit/modal.py` with `plane_mode` `:267`,
   `modal_station_phasors` `:372`, `modal_line_quantities` `:538` and `modal_sparams` `:685`, so
   the comment is stale or was true of a different checkout. Recorded, not resolved: which copy a
   given scratch run imported is not recoverable from the file.

## 6. Not examined

Stated so the audit is not read as complete:

- No analytic or reference S-parameter comparison was checked. `tests/test_scatter.py`,
  `tests/test_ports.py`, `docs/design/t4b_t4c_preregistration.md` and the `basis='analytic'`
  branch of `tools/gates_101_20.py` T1_stab were not read for that purpose.
- `emfit/modal.py` and `emfit/ports.py` were mapped structurally (classes, entry points, line
  numbers). Their bodies, their tolerances and their error handling were not audited.
- `emfit/scatter.py` is a 2-D FDTD PEC-cylinder scattering demonstration (`ScatterSetup` `:221`,
  `ScatterRun` `:341`, `ScatterResult` `:423`), not an S-parameter extraction path for the modal
  pipeline. Noted so a later reader does not mistake it for one.
- `tools/gates_101_20.py:482` to `:493` was read only as far as the `basis='mixed'` refusal, which
  cites a measured window sensitivity of 3.06 percent and 2.99 percent. The measurement behind it
  was not re-run.

## 7. Evidence appendix

All commands were run in the `DockerCodeRunner` container, working directory `/workspace`, which
is this workspace. Outputs are reproduced as returned, abridged only where marked.

**E1. Identity of the file under audit.**

```
$ pwd; sha256sum emfit/mode2d.py; wc -l < emfit/mode2d.py; wc -c < emfit/mode2d.py; grep -c OPinv emfit/mode2d.py
/workspace
9b74d83d7b2c6b0df5b362a391df39dd8940378195b5faef1efe14d84febe032  emfit/mode2d.py
1390
58509
0
```

**E2. Solver primitives and guards.**

```
$ grep -n 'eigsh(\|splu(\|toarray()\|todense()\|NotImplementedError\|_MIXED_DENSE_MAX\|_MIXED_RESIDUAL_TOL\|OPinv\|LinearOperator' emfit/mode2d.py
150:_MIXED_RESIDUAL_TOL = 1.0e-3
151:_MIXED_DENSE_MAX = 3000
868:    vals, vecs = eigsh(c_free, k=n_k, M=b_free, sigma=sigma, which="LM")
969:        is at most ``_MIXED_DENSE_MAX``.  ``dense=False`` raises
970:        ``NotImplementedError`` -- see the Notes.
1031:    against ``_MIXED_RESIDUAL_TOL``, then takes the largest positive
1041:    than ``_MIXED_DENSE_MAX`` free edges, raises ``NotImplementedError``
1094:    use_dense = (n_e <= _MIXED_DENSE_MAX) if dense is None else bool(dense)
1096:        raise NotImplementedError(
1107:        lu_h = splu(h)
1115:    a_dense = k0 * k0 * m_eps_f.toarray() - k_q_f.toarray()
1116:    b_dense = m1_f.toarray() - (c_f @ d_dense) @ c_f.toarray().T
1159:        & (residuals < _MIXED_RESIDUAL_TOL)
1164:            f"below {_MIXED_RESIDUAL_TOL:g}: beta^2 = {beta_sq.tolist()}, "
```

**E3. Module structure of `mode2d.py`.**

```
$ grep -nE '^(def|class) ' emfit/mode2d.py
157:def _quadrature_lambda()
166:class Mesh2D
229:def _as_mesh(nodes, tris, grid_axes=())
287:def structured_mesh(xs, ys) -> Mesh2D
323:def _transverse_axes(grid)
341:def mesh_from_grid(grid) -> Mesh2D
354:def box_mesh(lx, ly, nx, ny) -> Mesh2D
378:def _per_triangle(value, mesh, name)
397:def assemble(mesh, eps_r=1.0, mu_r=1.0)
469:def assemble_mixed(mesh, eps_r=1.0, mu_r=1.0)
539:def pec_edge_mask(mesh, boundaries=())
571:def pec_node_mask(mesh, boundaries=())
605:class Mode2D
787:def k0_from_freq(freq) -> float
795:def solve_modes(
935:def solve_modes_mixed(
1212:def _p1_stiffness(mesh, eps_t)
1222:def _laplace_phi(k, v1, v0)
1236:def _dirichlet_groups(mesh, boundaries=(), groups=None)
1298:def eps_eff_laplace(mesh, eps_t, *, boundaries=(), groups=None)
```

**E4. Call-site inventory.**

```
$ grep -rn --include='*.py' -E 'solve_modes_mixed\(|solve_modes\(' . | grep -v '^\./\.git/'
./.scratch/logs/s10118_mesh_study.py:184:    mode = m2.solve_modes_mixed(mesh, K0, sigma=1.0, eps_r=eps_of,
./.scratch/logs/s10118_basis.py:172:        mode = m2.solve_modes_mixed(mesh, K0, sigma=1.0, eps_r=eps_of,
./.scratch/mode2d/c2_oldunits.py:233:            mode = solve_modes(mesh, k0, sigma=s, eps_r=eps_t,
./.scratch/mode2d/c2_slab2.py:91:        m = solve_modes_mixed(mesh, k0, sigma=an_eps, eps_r=eps_of,
./.scratch/mode2d/c2_ident.py:245:        mode = solve_modes_mixed(mesh, k0, boundaries=boundaries, eps_r=eps_t)
./.scratch/mode2d/c2_slab.py:207:            m = solve_modes(b["mesh"], k0, sigma=sig, eps_r=eps_of,
./tools/host/c1-audit/c1_audit.py:545:    mode = m2.solve_modes_mixed(mesh, K0, sigma=1.0, eps_r=eps_of,
./tools/host/c1-audit/pecbox_variant.py:636:        m2.solve_modes_mixed(mesh_v, k0v, sigma=1.0,
./tests/test_mode2d.py:168:    res = m2.solve_modes_mixed(mesh, k0, eps_r=1.0, boundaries=_pec_walls())
./tests/test_mode2d.py:207:    dense = m2.solve_modes_mixed(mesh, k0, eps_r=1.0, boundaries=_pec_walls())
./tests/test_mode2d.py:208:    sparse = m2.solve_modes(
./tests/test_mode2d.py:276:    closed = m2.solve_modes_mixed(mesh, k0, eps_r=1.0, boundaries=_pec_walls())
./tests/test_mode2d.py:277:    open_ = m2.solve_modes_mixed(mesh, k0, eps_r=1.0, boundaries=())
./emfit/mode2d.py:795:def solve_modes(
./emfit/mode2d.py:935:def solve_modes_mixed(
```

**E5. `from_mode2d` call sites.** Reproduced in section 4. Three hits: one scratch note, one
definition, one error string.

**E6. `emfit/`-wide reach.**

```
$ grep -rn -E 'mode2d|solve_modes|Mode2D' emfit/
emfit/mode2d.py: ... (30 hits, all inside the module itself: docstring, __all__, class and def lines)
emfit/modalport.py:194:    def from_mode2d(cls, mode, cc, axis, index):
emfit/modalport.py:195:        """A port from a :class:`emfit.mode2d.Mode2D`'s ``e_t``.
emfit/modalport.py:198:        the 3-D port plane: built by :func:`emfit.mode2d.structured_mesh`,
emfit/modalport.py:199:        :func:`emfit.mode2d.mesh_from_grid` or :func:`emfit.mode2d.box_mesh`, so
emfit/modalport.py:217:                "from_mode2d needs a 2-D mesh that came from a structured "
emfit/modalport.py:218:                "rectangle (mode2d.structured_mesh / mesh_from_grid / "
```

**E7. The route that actually produced M4.**

```
$ sed -n '660,700p' tools/host/sparse-probe/rung4_routeC_probe.py
    try:
        lu_C, t_lu_C = timed(lambda: splu(S_C))
    ...
    op_C = CountedSolve(lu_C, S_C.shape)
    ...
        (w_c, v_c), route_c["t_eigsh_s"] = timed(lambda: eigsh(
            KC, k=1, M=MC, sigma=float(sigma), which="LM",
            OPinv=op_C.operator(), maxiter=5000,
            v0=deterministic_v0(KC.shape[0])))
```

with `LinearOperator` built at `:258` to `:259`, and the result object constructed by hand at
`:316` (`mode = m2.Mode2D(`). The M4 numbers, for the contrast with the module's 3000 cap:

```
$ grep -n '30672' .scratch/dispatch40_facts.md
146:### Largest campaign mesh --- `out_mesh/M4_fe30672.json`
      spec `58/44/35-17-18`, nx=147, nz=71, free_e=30672, n_dof=40903, nodes 10437,
      edges 30876, n_pec 204; wall_s 0.6908, peak_rss_mib 288.785, t_splu 0.3106,
      t_eigsh 0.2347, factor_nnz 6327066, fill/row 154.68, R=3.430414, residual 6.06e-11
```

**E8. `emfit/eigen.py`, the module `cpp_solver_arch.md` 2.7 actually cites.**

```
$ grep -n 'max_dense\|todense()\|sla.eigh' emfit/eigen.py
122:               max_dense=3000, res_tol=1.5) -> ResonanceResult:
176:    if n_free > int(max_dense):
178:            f"n_free={n_free} exceeds the dense limit max_dense={int(max_dense)}; "
186:    a_free = np.asarray(a[free][:, free].todense(), dtype=float)
196:        vals, vecs = sla.eigh(a_free, b_free, subset_by_index=[0, m - 1])
198:        vals, vecs = sla.eigh(a_free, b_free)
```

All four citations in 2.7 (`:176` to `:182`, `:186`, `:196`, `:198`) verify.

**E9. `cpp_solver_arch.md` section boundaries.**

```
$ grep -n '^\*\*2\.' docs/design/cpp_solver_arch.md
29:**2.1 The adopted solve.** ...
31:**2.2 The pencil actually run.** ...
40:**2.3 The `LinearOperator` form is mandatory, not stylistic.** ...
51:**2.4 Derived requirement: the factorisation must handle a symmetric indefinite matrix.**
61:**2.5 Measured costs to carry into any design.**
72:**2.6 Extrapolations are labelled as extrapolations.**
74:**2.7 The dense path stays dead.** ...
```

**E10. The mixed solver's body, `:1101` to `:1130`, verbatim.**

```
    m1_f = m1[free_e][:, free_e].tocsc()
    m_eps_f = m_eps[free_e][:, free_e].tocsc()
    k_q_f = k_q[free_e][:, free_e].tocsc()
    c_f = c[free_e][:, free_n].tocsc()
    h = (k_zz[free_n][:, free_n] - k0 * k0 * m_zz[free_n][:, free_n]).tocsc()
    try:
        lu_h = splu(h)
    except RuntimeError as exc:
        raise ValueError(
            f"the longitudinal block k_zz - k0^2 m_zz is singular at "
            f"k0 = {k0!r} ({exc}); nudge k0 off the nodal Dirichlet eigenvalue"
        ) from exc

    d_dense = lu_h.solve(np.eye(n_n))              # D = inv(k_zz - k0^2 m_zz)
    a_dense = k0 * k0 * m_eps_f.toarray() - k_q_f.toarray()
    b_dense = m1_f.toarray() - (c_f @ d_dense) @ c_f.toarray().T
    a_dense = 0.5 * (a_dense + a_dense.T)
    b_dense = 0.5 * (b_dense + b_dense.T)

    lam, vecs = _dense_eig(a_dense, b_dense)
    lam = np.asarray(lam)
    n_cand = int(lam.size)
    lam_real = np.real(lam)
    real_enough = np.abs(np.imag(lam)) <= 1e-6 * np.maximum(1.0, np.abs(lam))

    # --- per-candidate normalisation, pencil residual and curl ratio --------
    normalised = np.real(vecs)
    norms = np.linalg.norm(normalised, axis=0)
    norms[norms == 0.0] = 1.0
    normalised = normalised / norms
```

**E11. Extraction-layer structure.** Line numbers from
`grep -n 'class '` / `grep -n 'def '` on `emfit/modal.py`, `emfit/ports.py`,
`emfit/modalport.py`, plus `FileSearchTool` for the module-level functions
(`plane_mode` `:267`, `modal_station_phasors` `:372`, `modal_line_quantities` `:538`,
`modal_sparams` `:685`, `fit_beta` `:861`, `fit_station_impedance` `:1429`).

**E12. Prior art already on the tree.** `decisions.md:6829` records the zero call sites of
`ModalPort.from_mode2d`; `docs/design/modalport_ownership.md` and the pass-1 report stage the
seven-stage pipeline; `.scratch/logs/s10118_basis.py:12` records the zero independently. This
audit's finding 3 confirms them rather than discovering them.

---

Audit ends. No code, no test, no harness, no design document other than this new file was written
or edited; nothing was committed.

---

## 8. Question map: what was issued, where it was answered, what the answer was

Appended at the supervisor's instruction as Dispatch 43b sections 8 and 9. The closing statement
above applies to sections 0 to 7; nothing above this line was changed to make room for these two
sections.

Two plain facts fix the shape of the map. First, only Q5 exists verbatim on the record: it is
quoted in the heading of section 2 Q5 because it arrived in the dispatch. Q1 to Q4 do not exist
verbatim anywhere in this tree, which section 2 states at `:67` to `:75` before answering anything,
and which section 5 item 1 records as a disagreement with `docs/design/d43b_acceptance.md`. Second,
section 2 Q5 and section 9 Q5 are different questions and both are answered: section 2 Q5 asks
whether the `NotImplementedError` raise sits at `:1096` (it does, and the brief's `:1095-1099` is
the guard), and Q5 as issued as part of the analytic-reference question asks whether the `mode2d`
solver has an analytic S-parameter reference to be scored against. The map below therefore maps
propositions to answers, and says so, rather than pretending to map questions to answers.

| question | what is on the record for it | answered at | verdict |
|---|---|---|---|
| Q1 | `solve_modes` uses sparse shift-invert `eigsh(c_free, k=n_k, M=b_free, sigma=sigma, which="LM")` at `:868` | section 2 Q1 | ANSWERED, TRUE |
| Q2 | `OPinv` appears 0 times in `mode2d.py`, so there is no custom operator inverse anywhere | section 2 Q2 | ANSWERED, TRUE of the module, FALSE of the repository (section 5 item 3) |
| Q3 | densification exists in `solve_modes_mixed` | section 2 Q3 and section 3 | ANSWERED, TRUE, and misleading without section 3: the densification is unconditional and sits downstream of an explicit dense cap |
| Q4 | `lu_h = splu(h)` at `:1107` | section 2 Q4 | ANSWERED, TRUE |
| Q5 | the `NotImplementedError` at `:1096`; and, as issued, whether an analytic S-parameter reference exists for this solver | section 2 Q5 for the line claim, section 9 for the reference question | ANSWERED, both. The line claim is TRUE. The reference question is answered NO for S-parameters and YES for eigenvalues, with one three-orders-of-magnitude caveat |

## 9. Analytic references: what exists, what they bind, and what they cannot detect

Section 6 recorded that no analytic or reference S-parameter comparison was checked, and named
`tests/test_scatter.py`, `tests/test_ports.py`, `docs/design/t4b_t4c_preregistration.md` and the
`basis='analytic'` branch of `tools/gates_101_20.py` as the places it had not read for that purpose.
This section closes that gap. Every line number below was read in this session through
`DockerCodeRunner` against `/workspace`.

### 9.1 (a) The references that exist

**The four closed-form S-parameter references.** All four are on the FDTD path. Both test files
import from `emfit.evolve` (`tests/test_port_parallel_plate.py:79`,
`tests/test_evolve_loads.py:71`) and neither imports `emfit.mode2d`.

1. `tests/test_port_parallel_plate.py:334` to `:368`, `test_dielectric_step_gives_the_fresnel_amplitudes`.
   Two semi-infinite lines meeting at a plane give `S11 = (Z2-Z1)/(Z2+Z1) = -1/3` and
   `S21 = 2 Z2/(Z2+Z1) = 2/3` for `Z1/Z2 = 2` (`:338` to `:339`). Both magnitudes are asserted at
   3 percent (`:358` to `:361`). No phase is asserted, and the docstring says why: "that would need
   the discontinuity de-embedded from a reference plane" (`:353` to `:354`).
2. `tests/test_port_parallel_plate.py:366` to `:368`. The naive power sum `|S11|^2 + |S21|^2` is
   asserted against the exact `5/9` at `1e-2`, because a port that quietly renormalised would push
   it to 1 (`:350` to `:352`).
3. `tests/test_evolve_loads.py:240` to `:258`, series resistor across a cut in the top plate.
   `S11 = R/(2 Zc + R)` and `S21 = 2 Zc/(2 Zc + R)` (`:243`), asserted at `rel=0.01` for S21 and
   `rel=0.02` for S11 (`:256` to `:258`).
4. `tests/test_evolve_loads.py:264` to `:288`, shunt capacitor. `S21 = 2/(2 + j w C Zc)` (`:267`),
   asserted at `rel=0.01`/`rel=0.02` (`:286` to `:287`).

Items 1 and 2 together are a true closed form for the device under test. Items 3 and 4 are closed
forms of a lumped circuit the grid is asked to realise, which is a weaker claim: the device is
manufactured by the test, so what the test checks is that the solver realises the circuit it was
told to build, not that the physics of a real discontinuity is right.

**The reference on the `mode2d` path, which is eigenvalue-only.** `.scratch/mode2d/c2_slab.py:52`
to `:62` holds eight stored `(k0, analytic beta^2/k0^2)` pairs under the comment "stored project
values, verbatim". `.scratch/mode2d/c2_slab.json` records `entry_point` as
`emfit.mode2d.solve_modes_mixed (mixed e_t/e_z, dense QZ)` and seven comparison rows (`n_cases: 7`,
`n_ok: 7`), so one stored value, `k0 = 1.5`, is absent from the result file:

```
k0        abs_rel
0.05      2.48261602337134e-09
0.1       4.182635595200968e-08
0.2       7.316789324593976e-07
0.5       3.141044838746482e-05     <- at_k0, the design point
1.0       2.234808050673558e-05
2.095845021952   3.3048607526243745e-06
3.0       6.69683971926247e-07
all_rel_negative: true    max_abs_rel_dev: 3.141044838746482e-05
```

Read the column with care. The largest deviation is at the design point, `3.14e-05`, which is three
and a half orders of magnitude looser than the `1e-8` gate discussed in 9.3. The two rows below
`1e-8` are `k0 h = 0.0025` and `0.005`, and the file carries the normalised column that explains
them: `abs_rel_over_k0h2` is `3.97e-04` and `1.67e-03` there against `5.03e-02` at `k0 = 0.5`, so the
small numbers at low `k0` are the scaling of the error with `(k0 h)^2`, not evidence of a converging
solver. The `all_rel_negative` flag matters too: every deviation has the same sign, so this is a
systematic offset, not a convergence rate.

**Three analytic references that are not S-parameters.**

- `docs/design/t4b_t4c_preregistration.md:256` registers `r_analytic = 2.8101021387524523`, and
  `:328` to `:334` scores `R_extracted` against it. `decisions.md:8279` records the outcome in the
  register's own words: `3.184188500254623` / `3.2242746409436047` / `3.153215686647681` against
  `2.8101021387524523` is `+13.312 %` / `+14.739 %` / `+12.210 %` high, "flat and non-monotone".
  This is a reference the solver visibly fails.
- `tools/host/sparse-probe/out_mesh/mode_overlap.json` `reference_agreement.e_z_vv` spans `0.9665`
  to `0.9771` over five meshes, produced by `tools/host/sparse-probe/mode_overlap.py:459` to `:461`
  and written at `:655`. A mode-shape correlation of 0.97 is an agreement figure, not a tolerance
  that anything is gated against.
- `tests/test_scatter.py:55` to `:56` compares the PEC edge count with `pi a^2/h^2` at 10 percent.

**Two traps in the citations.** `tools/gates_101_20.py:465` has a keyword named `basis` whose
default is the string `"analytic"`; it is a basis selector, not an analytic reference, and
`basis="mixed"` raises `NotImplementedError` (`:486` to `:493`) while any other value raises
`ValueError` (`:494` to `:496`). `tests/test_modalport.py:591` computes
`expect = -np.exp(-2j*beta*L_GUIDE)` and `:596` to `:597` prints the expected phase with the words
"(reported, not asserted)"; the only assertion at `:598` is on the magnitude. That test is also
skipped (`:538` to `:554`), so the printed phase is not evidence of anything.

### 9.2 (b) What each comparison can and cannot detect

| class | count | what it compares | can it detect a wrong S-parameter convention |
|---|---|---|---|
| A. closed-form S-parameters of the device under test | 4 | solver against algebra | yes, at 1 to 3 percent |
| B. analytic references that are not S-parameters | 4 | eigenvalue, R, mode shape, edge count | no, and one of them (the prereg `R`) fails outright |
| C. cross-implementation or cross-formula | 4 | one code route against another | only if the two routes do not share the convention |
| D. self-consistency | 12 | the code against itself | no |
| E. manufactured inputs or exact by construction | 6 | imposed answers, or a boundary condition | no |

Class A, 4 items: `tests/test_port_parallel_plate.py:358` to `:361` and `:366` to `:368`;
`tests/test_evolve_loads.py:256` to `:258` and `:286` to `:288`.

Class B, 4 items: `.scratch/mode2d/c2_slab.py:52` to `:62` with `c2_slab.json`;
`docs/design/t4b_t4c_preregistration.md:256` and `:328` to `:334` with `decisions.md:8279`;
`tools/host/sparse-probe/out_mesh/mode_overlap.json` `reference_agreement`; `tests/test_scatter.py:55`
to `:56`.

Class C, 4 items: `tools/gates_101_20.py:544` to `:555` `T2_agree`, the station-phase beta against the
eigenvalue beta, tolerance `0.005`, measured gap 4.52 percent (`beta_fit 326.9107654423116` against
`beta_eigen 312.7827646322591`), which the docstring states is a FAIL "on today's record -- expected
and correct". `.scratch/logs/s10118_basis.py:436` to `:448`, the analytic and mixed bases measured on
the same mesh and differenced. `tests/test_bin_power.py:43` to `:52`, the single-`zc` formula
asserted to sit within `1e-2` of 1.0. `docs/design/cpp_solver_arch.md:164` to `:178` with `:245`,
`rel = (beta2_cpp - beta2_py)/beta2_py` at `1e-8`.

Class D, 12 items: `tests/test_ports.py:201` (round trip), `:307` to `:370` (Touchstone write and
read), `:373` to `:395` (primitives used as a run uses them, power `<= 1` and `= 1`),
`:609` to `:629` (de-embedding out and back), `:632` to `:655` (de-embedded magnitude moves only
through absorption); `tests/test_port_parallel_plate.py:294` to `:295` and `:363` to `:365` (lossless
energy identities); `tests/test_evolve_loads.py:288` (absorbed fraction vanishes);
`tests/test_bin_power.py:33` to `:40` (`p_first == p_last` and `s21_power == 1.0` exactly);
`tools/gates_101_20.py:465` (`T1_stab`, drop-one-station stability of the same estimator);
`docs/design/cpp_solver_arch.md:203` (Python against itself, bit for bit); `tests/test_modalport.py:455`
to `:497`, whose own docstring states the case: the amplitude ratio is "beta-INDEPENDENT ... Nothing
here tests the dispersion relation, and the t1 number cannot be moved by changing beta".

Class E, 6 items: `tests/test_ports.py:223` to `:233`, `:236` to `:248`, `:284` to `:299`, all of
which impose the probe fields and read back the answer they imposed; `tests/test_modalport.py:500` to
`:535`, where `|Gamma_short| = 1` follows from the PEC boundary condition alone and is asserted at
`1e-3`; `tests/test_modalport.py:555` to `:598`, skipped, and the one phase it knows is printed
rather than asserted; `tests/test_port_parallel_plate.py:270` to `:295`, a uniform air line whose
zero reflection is exact by construction and is asserted as a `-40` dB floor rather than as a value.

The consequence in one sentence: eighteen of the thirty comparisons listed here cannot distinguish a
right answer from a wrong one, and of the eight that can, only one runs on the `mode2d` solver at all
(the eigenvalue table in class B), and none of the eight is an S-parameter comparison on that path.

### 9.3 (c) The binding 1e-8 gate is not an S-parameter gate

`docs/design/cpp_solver_arch.md:245` makes `|rel| <= 1e-8` on `beta^2`, same mesh, same run, the
binding gate, with `PASS` or `FAIL` and no other verdict (`:238` to `:240`). Three things follow and
all three are in the document rather than inferred here.

First, it certifies the port, not the physics. What it constrains is that the C++ reproduces the
Python number. Nothing in the gate constrains either number against an external answer, so a shared
error passes it exactly. `:174` fixes the denominator as the Python value "precisely so it cannot be
chosen post hoc", which also means the gate is silent about whether that denominator is right.

Second, it is three to five orders of magnitude tighter than the best analytic agreement available
for this kind of device. The strongest references found here sit at 1 to 3 percent (class A) and at
`3.14e-05` on the design point of the eigenvalue table (9.1). A gate at `1e-8` therefore cannot be
read as validation of the extraction physics; it is four orders finer than any physics check in the
tree.

Third, shared errors cancel exactly. `rel` is a ratio of two values produced by two implementations
of the same pencil under the same conventions (section 4). A wrong sign convention, a wrong port
normalisation, a wrong `de-embedding`, all survive `1e-8` untouched, because both sides carry them.
This is why the four class A tests matter more to a physics claim than the binding gate does, and why
their 1 to 3 percent tolerances are not the weakness in the record.

### 9.4 (d) What the s10118 harness agreement proves

The analytic-versus-mixed harness at `.scratch/logs/s10118_basis.py:436` to `:448` measures the same
mesh twice and reports the difference, so its agreement is a statement about porting fidelity and
about nothing else: it cannot rank the two bases, because no external answer enters it. That is the
same limitation as 9.3, one level down the pipeline, and it is the reason `T2_agree` at
`tools/gates_101_20.py:544` is recorded there as a FAIL rather than a tolerance.

```
.scratch/s10118_result.txt
results.analytic  beta 309.9818636706751  eps_eff 3.5648002823688385  passivity 1.0142899588259895
                  z0_power 49.55894085929383  mode_purity 0.013875360260712512  s11 (absent)  s21 (absent)
results.mixed     beta 326.9107654423116  eps_eff 3.964798117952359  passivity 2.0013807961296104
                  z0_power 0.001988518234666638  mode_purity 0.20682682511194114  s11 (absent)  s21 (absent)
verdict           "mode_purity > 0.95: NO"
```

Neither branch carries `s11` or `s21`, so no S-parameter was compared in that run, and the beta pair
`309.9818636706751` and `326.9107654423116` is the same 4.52 percent gap that `T2_agree` scores as a
FAIL. The harness agreement is real and it proves that the reproduction is faithful. It does not
prove that either number is right.

Sections 8 and 9 were appended to this file only. No file under `emfit/` was edited and nothing was
committed.

## Dispatch 57 addendum (2026-10-29): the line numbers above have shifted

The citations in this audit were exact for the revision it audited and they are left standing as
written: this is a record of what was in the file then, and rewriting them would forge that record.
`emfit/mode2d.py` has since grown to 2129 lines, so every citation above now points at different
code. Verified mapping for the four constructs dispatch 57 AC-1.4 names, re-derived by symbol
against the current file (not by arithmetic on the old numbers):

| construct | cited in this audit | current |
| --- | --- | --- |
| `def solve_modes_mixed` | `:935` | `:1674` |
| `use_dense = (n_e <= _MIXED_DENSE_MAX) ...` | `:1094` | `:1833` |
| `if not use_dense:` | `:1095` | `:1834` |
| `raise NotImplementedError(` | `:1096` | `:1835` |
| the raise's closing paren (end of guard) | `:1099` | `:1838` |
| `_MIXED_DENSE_MAX = 3000` | `:151` (per `sparse_eigenmode.md`) | `:157` |
| `_MIXED_RESIDUAL_TOL = 1.0e-3` | `:150` (per `sparse_eigenmode.md`) | `:156` |

The audit's **other** `mode2d.py` citations (`:795`, `:868`, `:1114`, `:1150-1167`, the
`:1038`-`:1042` docstring and the rest) were not re-derived in this pass and are reported as
outstanding, not silently renumbered.
