# Dispatch 57 — acceptance criteria

**Frozen before execution.** Recorded from the dispatch as issued. No criterion may be edited once
work begins; a criterion found unsatisfiable is reported as a DISAGREEMENT, never amended in place.

Standing rule: **the artifact wins over the brief.** Where a claim in the brief and the content of
the repository disagree, the repository governs, and the disagreement is reported *before* any edit
is made.

## Rulings carried into this dispatch

- **R1.** This dispatch has the structure proposed in the dispatch-56 report.
- **R2.** The `emfit/` fences are lifted for landing Route C only, behind `use_dense`.
- **R3.** Evidence defects are fixed first. Nothing downstream (Task 2 onward) quotes the evidence
  until Task 1 is complete.
- **R4.** The order-p target is the existing strip ladder (five rungs), **not** the 2B slab; the slab
  harness is deleted and §101.17(l).7 governs — its provenance is prose.
- **R5.** §101.18(d.3) is retracted with the ancestry argument plus the rung-4 measurement, **not**
  with a design note.

## Fences

- **F1.** `emfit/` edits are authorised for Task 3 only: additive, behind `use_dense`.
- **F2.** `assemble_mixed` mathematics unchanged.
- **F3.** `decisions.md` is **append-only**. No existing line is edited or deleted; the retraction is
  an appended errata.
- **F4.** `[RELAYED]` numbers are re-measured, never cited. A relayed number that is not re-measured
  must be marked `UNRE-MEASURED` wherever it appears.
- **F5.** No line number in this dispatch is authoritative. Every line reference introduced by a fix
  is re-derived from the current file, never copied from the brief.

## Task 1 — evidence defects

Nothing downstream quotes the evidence until these are fixed.

- **AC-1.1 (a)** `verdict.overall.note` states that no dense reference exists at rung 4 and that no
  `reproduces_reference` claim is made anywhere in the report, while `agreement.status` is
  `REPRODUCES_REFERENCE` and `dense_anchor_present` is `true` in the same file. The contradiction is
  removed at its generator and in both recorded copies. No measured value changes.
- **AC-1.2 (b)** The report records `exit_code: 0`; the preserved logs end in `KeyError: 'n'` inside
  `print_summary` with a child return code of 1. The discrepancy is recorded against the file; the
  fact that the code has since been fixed is stated, and the standing "recorded, not fixed" note in
  `docs/design/t4_amp_ratio.md` is marked stale.
- **AC-1.3 (c)** The probe docstring asserts no dense anchor and no `c1_spectrum.npz` at rung 4, while
  a 738 560 423-byte `c1_spectrum.npz` exists and was written four minutes before the probe ran. The
  docstring states the measured fact.
- **AC-1.4** Stale line references are swept and corrected across `docs/design/sparse_eigenmode.md`,
  `docs/design/d43b_extraction_audit.md` and `tests/test_mode2d.py` (`_MIXED_RESIDUAL_TOL`,
  `use_dense`, `solve_modes_mixed`, the `NotImplementedError` stub). Every reference is re-derived
  from the current file; an unresolvable reference is reported, not guessed.
- **AC-1.5** Two copies of the report exist — `evidence/t4/rung4_routeC_report.json` (10 151 B) and
  `tools/host/sparse-probe/out_rung4/rung4_routeC_report.json` (10 158 B) — differing only in 11
  timing leaves, verified, not assumed.

## Task 2 — order-p pre-registration

`docs/design/order_p_preregistration.md`, frozen before the run.

- **AC-2.1** Target is the existing strip ladder: at least three resolutions spanning 9604 free edges.
- **AC-2.2** The band **[1.7, 2.3]** is pre-registered. A measured order outside the band is the
  finding, not a failure to be explained away.
- **AC-2.3** The residual question is pre-registered as a *flag hypothesis*: is the enlarged-pencil
  residual (2.33e-18) computable **without forming dense B**, and does it certify the Schur-complement
  eigenpair? The test is stated. If it certifies, no E3 item is raised. If it does not, E3 is
  pre-registered with a measured memory bound.
- **AC-2.4** A feasibility argument is mandatory: attainable precision at these resolutions versus
  the width of the band.
- **AC-2.5** The document states what one strip geometry cannot prove.

## Task 3 — land Route C in `emfit`

- **AC-3.1** Additive: a branch behind `use_dense`, or a new public entry point alongside
  `solve_modes_mixed`. The dense path's behaviour is unchanged.
- **AC-3.2** One `splu` per shift; shift-invert via `LinearOperator`; **no silent fallback** to a
  dense factorisation on failure.
- **AC-3.3** The full test suite is run and exact pass/skip/xfail counts are reported.
- **AC-3.4** The `NotImplementedError` message is removed or narrowed. It may not survive unchanged
  above `_MIXED_DENSE_MAX`.

## Task 4 — run the order-p ladder

Against Task 2's frozen criteria. Per rung: free edges, factor time, factor nnz, memory, β, analytic
β, relative error, observed order, gradient-state count, residuals on both pencils, wall time.

- **AC-4.1** No such "gradient-state count" metric exists in the codebase at the time of writing. If
  it is still absent, that is reported as absent — it is not invented, approximated or renamed into
  existence.

## Task 5 — the record

- **AC-5.1** Retraction text for §101.18(d.3), ready for a separate commit, resting on the ancestry
  argument and the rung-4 measurement.
- **AC-5.2** An account of what the deflated v2 path is now worth: it produced the diagnosis and
  characterised the fallback with a measured scope. Said plainly, so it is not read as a wrong turn.
- **AC-5.3** What remains unproven: general geometry, extraction composition, certified-bound
  machinery.
- **AC-5.4** Close-out: commits, the order-p table, the residual verdict, any disagreements, and an
  explicit statement whether the module now implements the route it once refused.

## Execution

Tasks are executed in order. Only the orchestrator commits; no task stages or commits its own work.
