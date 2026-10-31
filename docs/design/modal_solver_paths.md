# Modal solver paths

Provenance tags, in the form this repository already uses
(`docs/design/session_close_gen5.md:3-9`, quoted): "Provenance tags: **[M]**
measured in this repository in this pass, with the artefact cited beside it;
**[L]** read from the project's own record — claim ledger, decisions, or an
artefact a prior pass banked; **[R]** relayed from the supervisor seat,
unverified; **[UNVERIFIED]** believed here with no means available to check it."

This document is a reading pass: no solver was run for it, and every row below is
a citation rather than a measurement.

Two greps frame the question. The word "production" prefixed to
*route / path / basis / solver / engine / code / modal* occurs in **exactly one
file** in this tree — `tools/host/sparse-probe/sparse_solver_test.py:6` — and in
**none** of the 35 files under `emfit/` [M]. So "the production route" is a
phrase a probe script coined about somebody else's code; the rows below are what
that code actually consists of.

| path | where it is defined | pencil and eigensolver | DOF gate | who reaches it |
|---|---|---|---|---|
| **[M]** **Dense mixed QZ** — `solve_modes_mixed`: the only path any file here calls *"the production route"* | `emfit/mode2d.py`, class `Mode2D`; the dense/sparse dispatch is at `:1940` | mixed `(e_t, e_z)` pencil, reduced to `A - sigma*B` with `B = m1 - c D c^T` and `D = splu(h).solve(I)`; the reduced problem is handed to a **dense QZ** | `_MIXED_DENSE_MAX = 3000` (`mode2d.py:185`). Above it `use_dense` is `False` and the code raises `NotImplementedError("iterative path pending: A - sigma*B is dense through C D C^T; dense QZ only")` (`:1941-1945`) — a refusal, not a fallback | `tools/modal_beta_probe.py:18`, `:165` (`dense=None`, so gated at 3000); `tools/d585_modal.py:340-353` (`max_dof=1400` default, `dense=True`, status `"skipped: {n_fe} free edges exceed --max-dof={max_dof} (dense QZ)"` above the cap); `tools/gates_101_20.py:481-493` refuses the `basis='mixed'` basis outright (window-sensitive at 3.06 % / 2.99 %, span 6.24 %) |
| **[M]** **Sparse ARPACK, transverse pencil** — `solve_modes` | `emfit/mode2d.py:906` (`def solve_modes(`) | the transverse pencil `(K_q - k0^2 M_eps) e = beta^2 M_mu e`, i.e. "no `e_z`", solved by `eigsh(c_free, k=n_k, M=b_free, sigma=sigma, which="LM")` (`:989`) — shift-invert ARPACK on a symmetric-definite pencil, with `n_k = min(int(k), n_dof-1)` (`:986`) | **none** — the function applies no DOF cap | `tools/d585_modal.py:24-30`, `:253-266` (`solve_arpack(..., max_dof=None)`: the cap argument exists on that entry point and is passed `None`). `tools/host_ladder.py:104` imports the module but assembles its own pencil (next row) |
| **[M]** **Route C local block pencil** — `eigs`, assembled inside the tool | `tools/host_ladder.py:16-27` (rationale), `:530-546` (assembly), `:574-575` (call) | `K = [[A, 0], [0, 0]]`, `M = [[m, -c], [-c^T, h]]`, `A = k0^2 m_eps - k_q` symmetrised, `h = k_zz - k0^2 m_zz`. `M` is **indefinite** (the `h` block is negative in the substrate), so it is solved at `sigma` shifted by `eigs`, "never by `eigsh`" — `eigsh` assumes a symmetric-definite pencil and "will silently return junk rather than raise". One explicit `splu` factorisation, reused through `OPinv` | **none** — no DOF cap | nothing else: the pencil never leaves `tools/host_ladder.py`, whose banked metadata records `solver=scipy.sparse.linalg.eigs (NOT eigsh: M is indefinite)` (`:1340-1344`) |
| **[M]** **The harness constructor chain** — how the field solve obtains its mode | `emfit/modal_harness.py:51-53` (imports), `build_mode_plane` at `:67-83` | **no pencil is solved**: `microstrip_mode_profile` -> `modal.plane_mode`, "placed by integer index shift on the 3-D plane (`emfit/modal.py:267-307`)" (`:24-27`), then `modal_station_phasors` (`:41-44`) | not applicable | `emfit/modal_harness.py` itself. It imports `modal`, `mode_profile` and `ports`, and **no** `mode2d`; its docstring adds "There is **no absorbing port** and none is invented here" (`:34-35`) |

The load-bearing result of this reading is in the last column rather than the
third: **no module under `emfit/` imports `emfit.mode2d`.** A grep for `mode2d`
across `emfit/` returns 26 matches, and every one of them is either a
self-reference inside `emfit/mode2d.py` (the `Mode2D` class, `__all__`,
docstrings) or the `ModalPort.from_mode2d` classmethod at
`emfit/modalport.py:194-219` together with its single `ValueError` string [M] —
and `from_mode2d` itself has **no caller**, which `decisions.md:9348` already
records [L]. Every consumer of rows 1 and 2 is a file under `tools/`
(`d585_modal.py:54`, `modal_beta_probe.py:38`, `host_ladder.py:104`,
`destagger_ratio_101_20.py:68`, `corr_ez_101_20.py:60`,
`host/mode_plot/mode_plot.py:209`, plus prose-only mentions in
`host/c1-audit/c1_audit.py` and `spectrum_report.py`), while the package's own
modal route is row 4 — the constructor chain, which touches no eigensolver at
all. What that does **not** establish: nothing here says rows 1-3 return wrong
numbers, that `mode2d` is dead code, or that the 3000-criterion is unnecessary —
the tools call these paths and they answer. It establishes only that an argument
of the form "the production engine is dense, therefore ..." is quoting a probe
script's premise, not a verified statement about `emfit`; and one claim in this
pass's brief did not survive checking — `tools/d585_modal.py` never writes
"production engine" or "production route": its words for row 2 are "the sparse
ARPACK engine" (`:17-22`), and it names row 1 as the dense mixed QZ "that
`tools/modal_beta_probe.py` used" [M].

One correction a reader would otherwise take from row 1: **[M]** `tools/d585_modal.py` is a three-engine driver, not one dense arm — `ENGINES = {"arpack": solve_arpack, "deflated": solve_deflated, "mixed_dense": solve_dense}` (`:366-367`) — with `ENGINE_DEF = "deflated"` as its default (`:369-370`, "The engine used when ``--engine`` is not given"; `--engine` itself defaults to `None` over `choices=sorted(ENGINES)`, `:646-647`), so `max_dof=1400` (`:648-649`, "dense-QZ budget on free edges (mixed_dense only)") scopes the **dense arm alone** and is no ceiling on the tool: the ARPACK and deflated arms accept a `max_dof` keyword (`:253`, `:287`) and never read it.
