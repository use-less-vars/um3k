# Negative control: dated addendum, written before the run

Dated 2026-10-28. Written and committed before the run whose readings it governs.

## What this file is, and what it is not

`docs/design/anchor_preregistration.md` section 6 defines the negative control. Geometry B is geometry A with the slab thickness halved, from t = b/4 = 0.001953125 to t = b/8 = 0.0009765625, everything else byte-identical: b = 0.0078125, a = 0.0009765625, eps_r = 2, k0 = 1407.4335088082273. Section 6 names four conditions and says the control passes if and only if all four hold. It quantifies condition 4 and only condition 4. Conditions 1, 2 and 3 are phrased in words - "to within a few percent", "without permuting", "no fourth physical mode" - from which no numeric test can be written. The existing implementation, `run_control()` in `tools/host/anchor/ladder.py`, prints those quantities and asserts none of them.

This file does not amend section 6. The four conditions stand exactly as written. This file fixes, in advance of the run, the arithmetic that section 6 leaves open, together with the input paths and the pairing rule a runnable harness needs. It replaces no criterion and relaxes no threshold. It supplies the numbers the document omitted, and it does so here, before the run, so that they cannot be chosen after the numbers are seen.

## 1. Source of the geometry A side

Geometry A solver betas are read from `tools/host/anchor/records/levelN.json`, the committed records. They are not read from `out/level1.json`, which does not exist: `tools/host/anchor/out/` is empty and the records live in `records/`. This is a path correction and not a criterion change.

## 2. Pairing rule: by value, not by position

The pairing is by value. Each analytic beta is paired with the nearest retained solver candidate within a pairing distance of 2 per cent relative in beta. The rule is applied separately to geometry A and to geometry B, using each geometry's own analytic betas, and the two are then paired to each other through the shared analytic mode index. Only candidates retained by the frozen eps_eff filter are eligible; a candidate the filter drops is not a solver beta for this purpose.

The reason is a measurement, not a preference. At level 1 the committed geometry A record retains five candidates, and its `matched_by_order` triple is 1736.2570207158685, 1636.5986739978343, 1296.9723776897456. The first is spurious: the analytic census for geometry A has exactly three modes below the endpoint beta = sqrt(eps_r) k0 = 1990.411556294948, and 1736.2570207158685 is not one of them. Positional matching therefore pairs order 1 with an artifact and displaces the fundamental to order 2. Condition 1 speaks of "every solver beta", and a solver beta is a physical mode, so the pairing has to be the correspondence between solver candidates and analytic modes, not the rank order of the candidate list.

The 2 per cent distance is set by the solver's own error, not chosen for convenience. The worst geometry A pairing residual at level 1 is 8.88014985603658e-03 relative, on mode 3, where the candidate 952.9911948312771 sits against the analytic 944.6029788248537. A pairing distance must exceed the error of the solver it is pairing or it would refuse to pair with the very modes it is meant to be measuring. The distance is twice that residual. It is a pairing distance and not a pass criterion: no quantity in condition 1 depends on its size.

If a pairing finds no candidate inside the distance, that mode is recorded as not measured and condition 1 is not testable for it. The control is then not a PASS.

## 3. Condition 1: the band

Section 6 requires the movement to match "to within a few percent". Declared reading: let r be the measured relative movement (beta_B - beta_A) / beta_A for a mode, and let p be the analytic prediction from the table in section 6, which is -0.1635263486659064 for mode 1, -0.05849076597000279 for mode 2 and -0.08052370136888307 for mode 3. Condition 1 holds for that mode if and only if

    |r - p| <= 0.02

that is, if the measured percentage movement agrees with the predicted percentage movement to within two percentage points. "A few percent" is read as a few percentage points of movement, not as a few per cent of a movement.

## 4. Condition 2: the tolerance

Section 6 gives the fingerprints to four decimal places. Declared test: each measured geometry B eps_eff must lie within 0.02 absolute of its analytic value, these being 0.9477107208249235, 0.7519759548015799 and 0.3808236629763696 for modes 1, 2 and 3, and the measured triple must be strictly decreasing in mode index, so that the correspondence does not permute. The 0.02 is sized to the solver's own geometry A eps_eff error, which reaches 0.0081 absolute on mode 3, where it measures 0.4584816966495742 against the analytic 0.4504. A tolerance tighter than the solver's own error would fail a correct solver.

## 5. Condition 3: the census

The census is analytic and is not re-derived from the solver. Both geometries have exactly three physical modes below the endpoint beta = sqrt(eps_r) k0 = 1990.411556294948. Declared test: neither geometry may show a retained candidate that pairs, within the distance of section 2, to a fourth analytic mode, and each geometry must show all three. A candidate at the endpoint is not below the endpoint and is not counted. A candidate with negative beta squared is not a physical mode and is not counted.

## 6. Condition 4: as written

No interpretation is needed and none is offered. The control is void if |beta_B - beta_A| / beta_A < 1e-6 for any paired mode. A void control is reported as void and the harness exits non-zero. Section 6 already states that a void control voids any pass from section 4.

## 7. Level coverage, stated rather than narrowed

The control is run at mesh level 1. That is the level the committed geometry A record supports: it holds physical candidates for all three modes, at 1636.5986739978343, 1296.9723776897456 and 952.9911948312771, with pairing residuals 8.54637681914113e-04, 5.19245631694501e-04 and 8.88014985603658e-03.

At level 2 the committed geometry A record retains only 1296.4632008496378 and 946.6516295409791. It has no fundamental candidate at all, so "every solver beta moves" cannot be tested there from those records. Level 3 is the same. Section 6 does not state how many levels the control is run at, so this is a coverage statement and not a narrowing: nothing in section 6 says five levels, and a control whose purpose is to show connectivity does not become more connected by repetition. The level 2 and level 3 shortfall is recorded as a limitation of the available geometry A census and as the reason the control is level 1 only. It is not a pass.

## 8. Scope: which solver

Geometry B is solved with the same solver the committed geometry A records were produced with, which is the undeflated route. Section 6 predates deflation and says nothing about it. A deflated variant of the control is out of scope for this entry and is not reported under it.

## 9. Verdict vocabulary

PASS: all four conditions hold, on all three modes, at the level run.
FAIL: a condition fails on a mode that was measured.
NOT MEASURED: a condition could not be evaluated because a pairing found no candidate inside the distance of section 2, or because the geometry A census at the level run does not supply the mode.

The vocabulary is not ordered. NOT MEASURED is not a weak pass and it is not a fail; it is the record of a question that could not be put.
