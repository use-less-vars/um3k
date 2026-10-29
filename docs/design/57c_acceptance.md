# 57c — `Q` diagnosis: acceptance criteria

**Dispatch:** 57c (replaces 57b Task 2 / T3b).
**Author:** Agent A, single writer for this file.
**Status:** FROZEN at write time, before any code was read for this dispatch.
**Amendment rule:** later additions go in a dated Amendment section at the end. Nothing above is edited. A criterion may be tightened or withdrawn only by an amendment that names the criterion and the reason, dated before the evidence that bears on it.

## §0 Standing rules

R1 **Artifact wins.** Every claim about what the code does is quoted verbatim from a file at HEAD, with path and symbol. A claim supported only by this dispatch, a brief, a previous agent's summary, or a `decisions.md` narrative is not evidence.

R2 **No line numbers as locators.** Investigation proceeds by symbol name and by searching for the actual text. Line numbers rot; the artifact does not. A source line was reported for the station-fit warning in an earlier run; that number is deliberately not used as a locator here, the symbol name is.

R3 **Provenance on every number.** `[ARTIFACT]` = read from a file at HEAD. `[MEASURED]` = produced by a recorded invocation. `[RELAYED]` = carried from a dispatch, brief or prior agent, unverified. `[INFERRED]` = argument from tagged numbers, and the argument must be shown.

R4 **Fences.** No edits under `emfit/`. No Route C landing. `docs/design/decisions.md` remains single-writer Agent A. No writes to `viz/`, `component_map.md`, `d58_*`.

R5 **A close that repeats this document is a false close.** Nothing here is evidence.

### Numbers carried in, all `[RELAYED]`, all unverified

- `Q` = 1.272 against a bar of 0.10, at rung 4.
- Rungs 0 and 1 also fail: `Q` = 0.441 and 0.345.
- Route C residual 2.3e-18.
- Station fit refused: `sigma_beta` 65.80604052737668 against `beta` 1.7098484335215227e-15, `station_fit_ok` False.

Each must acquire `[ARTIFACT]` or `[MEASURED]` before it appears in a verdict.

### Premise P1 `[MEASURED]` — the constraint this diagnosis starts from

The full suite is green at HEAD: `502 passed, 1 skipped, 1 xfailed` in 1069.48 s, uncapped, via `python3 -m pytest -o addopts="" -q --tb=line -rfE --durations=15`. That suite includes `tests/test_mode2d.py::test_sparse_dense_agree`. Therefore, at the configuration that test exercises, the sparse path and the dense path agree to the test's tolerance.

Consequence, which binds every hypothesis in §3: **the sparse solve is not producing a wildly different mode from the dense solve at the tested configuration.** Any explanation offered must be common-mode — the pencil, the shift, the metric, or an input shared by both routes — unless the rung configurations used for `Q` differ materially from the tested one, and that difference must then be shown.

## §1 Task 1 — define `Q` before judging it

Acceptance requires all of the following.

T1.1 The expression that computes `Q`, verbatim, plus its numerator, its denominator, and what each of the three is a function of.

T1.2 Every argument `Q` consumes, named at the call site, with the producing symbol for each.

T1.3 A transitive dependency list, one row per edge, each row carrying path and symbol. Trace until each branch terminates in exactly one of: a field read from a solve; a fitted parameter; a literal constant. An undocumented edge is a failure, not a gap.

T1.4 **The break point.** An explicit statement of where the chain stops being trustworthy, or "no break found" together with the argument for why each edge carries.

T1.5 Denominator failure modes: can it be zero; can it change sign; is it a function of a quantity that is itself unvalidated; does it carry a dimension that makes the ratio meaningless.

T1.6 **Disposition of the station-fit lead** — exactly one of ON PATH / NOT ON PATH / UNDETERMINED, with the deciding artifact. The question that decides it: did the Route C rung runs supply an explicit `reference=`, i.e. does `Q` in those runs consume an impedance that came from the station fit at all. This is cheap and it is decisive for the lead's status.

T1.7 `Q` defined **per rung**. If the ladder changes `Q`'s inputs — mesh, window, mode basis, reference — say so rung by rung. A single definition asserted across rungs without checking is a failure of T1.7.

Refuse and record: a definition assembled from prose. If the prose and the code disagree, the code is right and the disagreement is a required deliverable.

## §2 Task 2 — the `beta` anomaly

T2.1 **What `beta` is.** Propagation constant, or fitted coefficient? Decide from the code, not from the name. The refusal text's own wording — that the trial at `beta` minus `sigma_beta` would go negative — is `[ARTIFACT]` and has the shape of a positivity constraint on an estimated parameter, not of a dispersion relation. Both readings must be tested; the code decides.

T2.2 **Where the value comes from at rung 0**: which field, produced by which call, on which mesh.

T2.3 **`beta` and `sigma_beta` at every rung**, `[MEASURED]`, with the recorded invocation.

T2.4 **Is the mode propagating?** Compare the observed `beta` against an independent value for the same configuration — dense route, analytic relation, or reference solution. State the comparison, not the conclusion alone.

T2.5 **Is `sigma_beta < beta` well posed?** Under reading (a) it compares a spread to a propagation constant; under reading (b) it is a lower bound on a positive fitted parameter. State which, and whether the constraint can hold for physically admissible inputs.

T2.6 **Invariance.** Is `beta` approximately 1e-15 at every rung? If it does not move with mesh, it is structural rather than discretisation error, and its cause must be structural too.

## §3 Task 3 — decision rule, frozen now

### Discriminators

D1 **Dense control.** Compute `Q` from the dense route at the same rung and configuration whose answer is established independently. If `Q` from the dense route also exceeds the bar, `Q` is not measuring the quality it claims to certify. If `Q` from the dense route is inside the bar while `Q` from the sparse route is outside, then `Q` discriminates and the sparse path is implicated. Note P1: sparse and dense agree at the tested configuration, so the expected outcome of D1 is that `Q` fails on both — but the control must be run, not assumed. D1 is a measurement at a known-good configuration, not a re-run to a kinder tolerance: it changes no tolerance, no band, and no rung.

D2 **Input-correctness test** (for outcome C). For each input on `Q`'s path, is there an independent check that it equals the value physics requires? If no such check exists for an input, C cannot be asserted for that input — only UNDETERMINED.

D3 **Ruler test** (for outcome A). Either a structural argument from the code that `Q`'s denominator vanishes or that `Q` is not monotone in the quantity it certifies, or D1 showing failure on a known-correct field.

### Outcomes

**A — `Q` structurally flawed** (a bent ruler). Holds iff D3 holds. Consequence: retire `Q` and specify a replacement quality measure; Route C remains unvalidated and the gate, not the route, was the failure. The `T4_amp` precedent.

**B — `Q` well formed and the route fails.** Holds iff D1 shows `Q` discriminates (sparse outside, dense inside), and D2 shows `Q`'s inputs correct, and `Q` exceeds its bar. Consequence: excellent eigenpairs of the wrong operator — a pencil or shift problem — and this is the serious case.

**C — `Q` well formed and its input is broken.** Holds iff D1 does not implicate `Q`, and T1.6 returns ON PATH or T2 shows a wrong or non-propagating `beta` or a wrongly formed impedance, and D2 identifies at least one such input as wrong. Consequence: the physics may be intact and the measurement upstream-broken; Route C stays unvalidated until the input is repaired and `Q` re-measured, which is a new dispatch and not this one.

**UNDETERMINED** is a legitimate and recordable result, and is required whenever a discriminator could not be run inside the fences.

### Hierarchy

A dominates B and C: if the ruler is bent, neither B nor C is answerable, and any claim that the route failed or that an input broke is suspended.

B and C are distinguished only by D2, never by plausibility.

A finding that `beta` is a fitted coefficient rather than a propagation constant does not by itself make C true; it removes the null-mode explanation and leaves C contingent on D2.

### Authorisation to run

Only D1 may be run under this dispatch, and only if T1 and T2 have not already determined the outcome. No new tolerance, no wider band, no relabelled rung, no re-registration. If D1 cannot be run inside the fences, write UNDETERMINED and say why.

## §4 Close-out

Must contain, in this order: (a) `Q`'s definition, per T1.1 to T1.7, with quotes; (b) the dependency chain and the break point; (c) `beta` and `sigma_beta` per rung with provenance; (d) whether the station-fit failure is on `Q`'s path, per T1.6; (e) **every disagreement with the dispatch**, stated as dispatch-said versus artifact-says; (f) which of A, B, C or UNDETERMINED holds, with the discriminator that decided it; (g) one sentence on Route C's status — unvalidated, and why — and one on whether the sparse route is a candidate for landing, expected answer no.

## §5 False closes, stated in advance

- Asserting A from the refusal warning alone. The warning is an input event; A is a claim about `Q`'s structure.
- Asserting C without T1.6. If the rung runs passed an explicit `reference=`, the station fit was never on `Q`'s path and the lead is dead.
- Asserting B from the 2.3e-18 residual. A small residual says the solve converged to an eigenpair; it says nothing about whether `Q` reads it correctly.
- Quoting any `[RELAYED]` number as `[MEASURED]` because a prior summary already said it.
- Declaring UNDETERMINED without naming the discriminator that could not be run and why the fences forbade it.
- Any close that does not state in one sentence that Route C remains unvalidated.

## Amendments

None at freeze time.
