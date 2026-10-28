# Dispatch 50 — acceptance criteria, recorded before any work

Frozen before any file in this dispatch is edited. Source: the dispatch 50 brief as given by the supervisor. Where this file and the tree disagree, the tree wins and the disagreement is reported before editing, not after.

Provenance tags: `[USER]` supplied in the brief; `[RELAYED]` carried in from the dispatch 49 record and not re-measured this session; `[VERIFIED]` re-measured in this dispatch by a named command. An untagged number is `[RELAYED]`.

No line numbers are given anywhere in this brief. That is deliberate: the brief is a statement of what must be true, not a patch.

## Fences

- `emfit/` edits are authorised for Task 2 and Task 3 only, and only additively.
- No work at levels 4 or 5.
- No change to the dense-complement cap `_DEFLATED_DENSE_MAX = 6000`.
- No matrix-free work.
- `decisions.md` is append-only.
- **Task 4 ends the dispatch.**

## Task 1 — the erratum and the over-removal finding, in `decisions.md`, no code

One block, recording: (i) that Amendment 3's widened-preservation clause is void as authored, with the reasoning — it is unsatisfiable by seven to ten orders, the measured per-level shrinkage of 4.06x / 4.13x / 4.02x is discretisation and not deflation, and it is internally contradictory with the frozen section 3; (ii) that the clause was authored by the supervisor, and is the eighth supervisory error and the second pre-registration contradiction in two dispatches; (iii) that the nine measurements are diagnostic evidence only, neither a pass nor a fail, and not citable as either; (iv) that the feasibility-argument rule is adopted as a standing rule; (v) that over-removal is recorded as a finding — `residual_eps_mu` eight orders off the round-off prediction, the cause structural, v1's exactness not transferring to v2, and v2 deflation therefore a heuristic whose correctness rests on empirical preservation on the geometries tested; (vi) the `eps_eff ≈ 1.5` cluster hazard and its margin of about 5.25e-2, three times `PAIR_TOL`.

Acceptance: the block exists in `decisions.md` and contains all six items. No code change is part of this task.

## Task 2 — storage fix, so mode purity becomes measurable

`curl_ratio`, and any per-candidate diagnostic that determines mode purity, must be stored per candidate at every level, not merely computed in-run. The change is additive: existing artifacts and existing paths are unchanged.

Acceptance: a test pins that a stored candidate record carries the diagnostic keys. Full suite, with exact pass / skip / xfail counts reported.

## Task 3 — pre-register the preservation gate, frozen and committed before Task 4 runs

`docs/design/preservation_gate_preregistration.md` must contain, at minimum:

1. **Statistic.** Convergence to the analytic root at the observed order, not agreement at a fixed absolute bound. The relative error against the analytic root must be monotone decreasing and the level-to-level ratio must fall inside the order band, at three levels or more.
2. **Feasibility argument.** As the new standing rule requires: what precision is reachable at levels 1 to 3 given the measured second-order rate and the round-off floor, stated as an expectation the gate can meet. If the gate as written cannot be met, that must be said before the run, not after.
3. **The widened set.** The analytic roots in the census window, tested by the convergence statistic and not by a 1e-12 bound.
4. **Over-removal guard.** `residual_eps_mu` reported at every level with its convergence rate stated. Diagnostic, not a pass condition.
5. **What the gate does not test.** Stated explicitly: it does not prove the removed subspace non-physical in general, only on the geometries run.
6. **Verdicts.** PASS, FAIL and FAILED-TO-MEASURE, with FAILED-TO-MEASURE requiring the same diagnostic treatment as the other two.

Acceptance: the file is frozen and committed before Task 4 runs.

## Task 4 — a second geometry against the frozen gate

Choose the cheapest geometry that changes the removed-subspace structure — a different permittivity, a different fill height, or both — and state the choice and why it stresses over-removal specifically. Analytic roots come from the validated reference routine and are frozen before the run. Levels 1 to 3 are run through the frozen Task 3 gate, and the result is reported against the gate and not against intuition.

Readings fixed in advance: if preservation converges at second order, over-removal is structurally harmless for the class tested. If it does not, that is the geometry where the heuristic breaks, which the brief calls the most valuable possible result. **If a physical mode is annihilated, stop and report** — that is the catastrophe Amendment 2 section 1 named.

## Close-out

Commits made; commands run; the gate verdict for each geometry; the `residual_eps_mu` convergence table for both geometries; every disagreement with this brief; and an explicit statement of whether over-removal is now evidenced-harmless, evidenced-harmful, or still open.
