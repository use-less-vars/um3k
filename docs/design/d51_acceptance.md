# Dispatch 51 — acceptance criteria

Frozen before any edit. If the tree contradicts this brief, the artifact wins;
report before editing. Every number carries `[VERIFIED this session]`,
`[RELAYED]` or `[USER]`; untagged is `RELAYED`.

## Scope

- **Task 1** — pre-register geometry A-3.5 (`eps_r = 3.5`, `t = T = B/4`,
  contrast 2.5) in `docs/design/preservation_gate_preregistration_a35.md`,
  committed before any run.
- **Task 2** — run A-3.5 at levels 1-3 against the Task 1 gate, via a new
  additive script `tools/host/anchor/preservation_gate_a35.py`.
- **Task 3** — backfill `docs/design/preservation_gate_results_a15.md`; retro-gate
  geometry A through the same frozen gate, or report the limitation.
- **Task 4** — assemble the three-contrast residual table and issue one verdict.
  Task 4 ends the dispatch.

## Fences

- `emfit/` untouched.
- No levels 4 or 5.
- No dense-cap change. No matrix-free work. No ARPACK budget increase.
- No patch to the frozen A-1.5 module `tools/host/anchor/preservation_gate.py`
  (sha256 `7a0c04b2efbe9fefd2e5a2f7ccbfba3ca8500cb9506cda40e789201396dd2d1b`).
  It is a registered hash.
- `decisions.md` append-only.

## Task 1 acceptance

1. `residual_eps_mu` defined **from the code**, with its normalisation, quoted
   with `file:line`. Not paraphrased from the d49 record.
2. States explicitly that two contrasts cannot test a power law and that A-3.5 is
   the first point with discriminating power.
3. Prediction stated as a **band**, plus falsification conditions, one of which
   is an L1 residual at or above `0.1`.
4. Feasibility argument present **before** the run: what precision is reachable
   at levels 1-3 at `eps_r = 3.5`, the expected conditioning penalty, and the
   criterion that must still be met. If the gate as written cannot be met at
   this contrast, that is said before the run.
5. Budget rule: iteration cap a fixed multiple of the deflated dimension; if the
   cap binds, the level is `FAILED-TO-MEASURE` and no second budget is taken.
6. Cluster-safety rule: the `eps_eff` cluster distance **must be printed** at
   every level (a blocking reporting item after it failed to appear last run);
   a cluster converging below `PAIR_TOL` stops the run and reports.
7. Gate criteria inherited unchanged: strict monotone decrease, observed order in
   the `1.7-2.3` band, supporting bound `5e-3`, route-3 threshold `0.04`,
   monotonicity flag true, unpaired list empty at every level. Widened set = the
   analytic roots in the census window at `eps_r = 3.5`, frozen.
8. Non-claims restated: the gate does not establish over-removal absent, only
   that it did not disrupt pairing on this geometry.

## Task 2 acceptance

- `sys.path` bootstrap present, so the script runs as documented.
- Per level: the ordered roots with analytic references, residuals, observed
  orders, route-3 figure, candidate counts and surplus, paired `curl_ratio`, and
  the cluster distance required by Task 1 item 6.
- Reported **against the gate**. A PASS that required the fit to be reinterpreted
  is a FAIL of the pre-registration and must be reported as such.

## Task 3 acceptance

- The A-1.5 PASS recorded with its numbers in
  `docs/design/preservation_gate_results_a15.md`, so the record does not live
  only in a scratch directory.
- Geometry A retro-gated through the same frozen gate, or the limitation reported
  without touching the frozen script; a sibling-script result is labelled
  *non-gate evidence, instrument not the registered artefact*.
- States whether A's `curl_ratio` purity context is available under current
  storage.

## Task 4 acceptance

- `residual_eps_mu` table across all three contrasts at levels 1-3, per-level
  ratios, fitted exponent and its residuals.
- Exactly one verdict: `STRUCTURAL`, `BREAKING` (naming the falsifier that fired)
  or `STILL-OPEN` (naming what remains untested and what would close it).
- Candidate population recorded as **observation only**, hypothesis space in one
  paragraph, no gate and no verdict.
