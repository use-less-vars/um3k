# h-refinement of the microstrip beta offset — SUMMARY

Closes the open item of `decisions.md` 148(h). Protocol frozen in `PREREG.md` (this directory) before
any run. Rungs: `h040.json`, `h0267.json`; `h020.json` deliberately **does not exist** (§4 below).
Reference throughout: `tools/d585_modal.hammerstad_beta(f)['beta']` evaluated at each run's **own**
tone → **384.7489756771** rad/m (frozen value 384.7489672644; deviation 2.2e-8 relative, reproduced
by this agent, tolerance 1e-6 → PASS).

## 1. Measured rungs (both solvers, fixed physical domain)

Box: `--clearance 3.0 --box-lateral-mult 8.0 --box-lid-mult 1.0` (same box as committed
`box_sweep/lat8-lid1`). Strip pinned in metres at **0.8 mm**; both rungs mesh it at exactly 0.8000 mm.
Absorber pinned at **4.8 mm**, so `npml` re-derives (12, 18, 24).

| rung | h (mm) | grid | n_cells | npml | nsteps | beta_FDTD | d_FDTD (pp) | beta_EIG | d_EIG (pp) | rel_gap (%) |
|---|---|---|---|---|---|---|---|---|---|---|
| A | 0.4 | (68, 218, 28) | 415 072 | 12 | 2400 | 388.2194613 | **+0.90201** | 389.7256713 | **+1.29349** | 0.38798 |
| B | 0.26667 | (101, 327, 42) | 1 387 134 | 18 | 3600 | 386.8664667 | **+0.55036** | 388.3447897 | **+0.93459** | 0.38213 |
| C | 0.2 | (not run) | ~3.27 M | 24 | 4800 | — | **not run, gate tripped** | — | — | — |

`d = 100*(beta/ref - 1)`, pp.

Cost (measured, `[M]`): A 388.4 MB / FDTD 232.0 s / EIG 22.3 s; B 1069.7 MB / FDTD 595.5 s /
EIG 39.5 s. Absorber diagnostic `alpha` 0.0107 (A) and 0.0129 (B) dB/mm, both **below** the 0.0139
floor → no spurious radiation from the box at either rung. `eps_eff`: HJ+KJ 3.240062, A
3.298777 / 3.324424, B 3.275823 / 3.300907 (FDTD / EIG) — both solvers walk **down** toward 3.240 as
h refines, consistent with a discretisation term that vanishes.

## 2. Pre-registered verdict (§4/§5 of PREREG) — **INCONCLUSIVE**

`PREREG.md` §4 makes the classification depend on the h = 0.2 rung against h = 0.4, and §5 says: *"If
rung C trips the gate it is not run, the table is published with two rungs, and the verdict for
h = 0.2 is 'not measured, gate tripped' — never extrapolated."* §4's third bullet is explicit:
**INCONCLUSIVE** *"if neither holds (non-monotone, or the run stops on the sizing gate)"*.

Rung C **trips the gate** (§4 below) → **the pre-registered verdict is INCONCLUSIVE**, and that is
what this dispatch reports. The protocol bound; it is not overridden here.

## 3. Post-hoc reading of the two measured rungs (labelled post-hoc; NOT the pre-registered verdict)

Both readings below are computed from A and B only, which §5 permits as *description*, not as a
substitute verdict.

- **d falls monotonically and the fall is well over threshold.** FDTD **+0.90201 → +0.55036 pp**,
  fall **0.35166 pp**; EIG **+1.29349 → +0.93459 pp**, fall **0.35890 pp**. Pre-registered threshold
  `3*Delta_min = 0.22020 pp`. The fall over a mere **1.5x** refinement is **1.6x the threshold**, on
  *both* solvers. So the residual is **not flat in h**: the direction that `box_sweep` could not test
  is established, even though the pre-registered three-rung verdict could not be issued.
- **The h-fall is common to both solvers.** 0.35166 vs 0.35890 pp — they agree to 0.007 pp, i.e. 1/10
  of `Delta_min`. Consequently the FDTD–EIG gap is essentially **h-invariant**: 0.38798 → 0.38213 %
  (change 0.00585 pp << Delta_min). The two solvers share the same grid, so a shared h-error is the
  expected signature; the ~0.382 % gap that survives a saturated absorber and 1.5x refinement is a
  *solver-basis* difference, not a discretisation artifact (see §6.2 for what it is not).
- **Order is NOT determined.** With two points, any `d = d0 + C*h^p` fits exactly; a pure power law
  with no `d0` gives apparent exponents p_FDTD = 1.22, p_EIG = 0.80 — these are *brackets, not an
  order*, and `PREREG.md` §4 requires three points (and +-30 %) before any p is quoted. **No number is
  claimed for p.** For orientation only (and explicitly `[UNVERIFIED]`): a straight line through the
  two points extrapolates to `d(0) = -0.153 pp` (FDTD) and `+0.217 pp` (EIG), which would move the
  FDTD residual to ~0 while leaving the solver gap intact. **This is an extrapolation and CARRIES NO
  WEIGHT** — §5 forbids trusting even the *h = 0.2* extent of it, let alone h = 0.

## 4. Sizing gate — why rung C was not run (declared before the runs, applied to measurement)

Measured A→B scaling (h ratio 1.5, cells x3.342, FDTD-time x2.567, RSS x2.754):

| quantity | measured exponent (h^-p) | C priced from B (h ratio 1.333) | gate |
|---|---|---|---|
| cells | p = 2.976 (a priori 3) | 3.27 M | — |
| FDTD wall | p = 2.325 | **1 163 s** | **> 900 s → TRIP** |
| peak RSS | p = 2.499 | 2 195 MB | < 4000 MB → pass |

The naive `h^-4` pricing (cells x nsteps) gives 1 882 s from B. **Both pricings trip the 900 s wall
gate**, none trips the memory gate. Per §5: not run, not extrapolated. (`box_sweep`-era estimates
costed 6.9 M cells for this rung from a linear-in-cells model; the measured exponents — cells
~ h^-2.98, wall ~ h^-2.33, RSS ~ h^-2.50 — are what the gate is priced on here. Note FDTD wall time
scales **softer** than cells, and much softer than a `cells^1.06` generalisation.)

**Deviation declared:** rung B was launched concurrently with A, before A's measurement existed, so
its gate could not be applied prospectively; it came in at 595.5 s (< 900 s) and needed no decision.
Rung C's gate *was* applied prospectively and the run was withheld.

## 5. Confounds: declared, and (mostly) shown to be inactive

1. **npml grows with refinement** (12 → 18 → 24). PREREG §6.1 called this as biasing toward a
   converging offset; it is stronger than that — the absorber is **saturated** over this range, so the
   ladder is *clean* on this axis, on evidence:
   - prior unit-box depth sweep at h = 0.4, `.scratch/d589/npml{3,6,8,12,16}.json` `[M]`, same box and
     cell, only `--npml` differs: d_FDTD = +1.67779 (3), +1.11068 (6), +0.98914 (8), +0.83925 (12),
     **+0.85006 (16)** pp. 6 → 12 moves 0.271 pp; 12 → 16 moves **0.0108 pp** (< `Delta_min`):
     saturated by npml 12.
   - same conclusion in this dispatch's box: committed `lat8-lid1` (npml 6) 388.8591005 → rung A
     (npml 12) 388.2194613 = **0.16625 pp**. Both ladder rungs sit at npml ≥ 12, i.e. in the plateau.
   - **beta_EIG is exactly PML-transparent**: `lat8-lid1` (npml 6) and rung A (npml 12) return
     **389.7256713378306, identical to 13 digits**, with identical `n_dof` = 12 443 (= 3117 n + 9326 e).
     So the EIG arm of the ladder has **zero** absorber confound, and the EIG fall of 0.35890 pp is
     purely cell size at a fixed box.
2. **The committed rows are not this dispatch's h = 0.4 rung.** Both are reported side by side; the
   difference is absorber thickness (4.8 mm vs the committed `npml 6` = 2.4 mm) and is **not**
   attributed to h. Measured: 0.16625 pp on FDTD, 0 on EIG (§5.1).
3. **Strip meshing** — exact on both rungs (0.8000 mm meshed), so it cannot drive the fall.
4. **Cell count not held constant** — that is the independent variable.

## 6. Cross-checks

### 6.1 A prior three-rung h-ladder exists at the UNIT box (`.scratch/host_ladder.json`) `[M]`

`argv: --max-rungs 3`, `--clearance 3.0`, `npml 6`, no box multipliers (= 1.0), status "incomplete"
(`abort_reason: memory_ceiling`), **all three rungs completed**:

| h (mm) | grid | n_cells | d_FDTD (pp) | d_EIG (pp) | rel_gap (%) |
|---|---|---|---|---|---|
| 0.4 | (62, 38, 22) | 51 832 | +1.11068 | +2.01521 | 0.89459 |
| 0.26667 | (89, 51, 30) | 136 170 | +0.88374 | +1.63558 | 0.74525 |
| 0.2 | (116, 64, 38) | 282 112 | +0.77335 | +1.44580 | 0.66729 |

Falls over 2x: **0.33734 pp** (FDTD) and **0.56941 pp** (EIG) — same sign and similar size to this
dispatch's 0.35166 / 0.35890 pp over 1.5x, so **the two ladders agree that the offset is h-dependent**.
That ladder is *not* decision-grade and is not used as such: it is the unit box (its EIG rows carry
the ≈ +0.72 pp transverse-box error that `box_sweep` S8.1 quantifies — cite
`evidence/box_sweep/SUMMARY.md` §8, do not re-derive it), `npml` fixed at the **under-resolved** 6 (so
its falls mix h with absorber deepening: up to 0.271 pp of its FDTD fall of 0.337 pp could be
absorber alone), and its grids (89, 51, 30) do not match a strip pinned in metres, i.e. it predates
the 0.8 mm pinning. It is cited only as independent corroboration of the *sign* of the h-term.

### 6.2 What the h = 0.4 numbers look like decomposed

Committed `lat8-lid1` (npml 6), FDTD: **+1.0683 pp** = 0.1663 (absorber depth, §5.1) + **+0.9020**
(rung A), then 0.3517 (h, to rung B) → **+0.5504**. Note the absorber term (0.166 pp) is *larger than
the entire lid lever* of `box_sweep` (≤ 0.097 pp for the whole box lever there) — i.e. at the
committed `npml 6` the FDTD offset was never absorber-converged, and `box_sweep`'s "box lever" bound
did not include absorber depth (it held npml at 6 throughout). This is a *new* qualifier on how the
committed FDTD rows should be read; it does not amend `box_sweep`'s box conclusion, which is about
lateral/lid extent at fixed npml.

### 6.3 h = 0.3 mm is not representable `[M]`

`tools/host_ladder.py:228-235` `grid_for(0.3)` returns **(n_sub 5, cell 0.00032 m)** — it silently
re-derives the cell as `H_SUB/round(H_SUB/h)`. A request for 0.3 mm therefore *is* a request for
0.32 mm, at which `round(0.8/0.32) = 2` cells gives a meshed strip of **0.64 mm (-20 %)**. That is why
the middle rung here is 0.26667 (n_sub 6, meshed 0.800 mm), not 0.3. No validation raises on this; it
is silent.

## 7. What this does NOT establish

- **It does not measure the h term at h = 0.2** (gated), so the *magnitude* of the residual at the
  refinement level a future run would use is unknown, and no extrapolation is endorsed (§3, §5 note).
- **It does not determine the order p** (two points), and therefore says nothing about whether the
  h-error is first or second order.
- **It does not identify the source of the ~0.382 % solver gap that survives refinement.** That gap is
  now demonstrably *not* lateral/lid loading (`box_sweep`) and demonstrably *not* cell size over
  0.4 → 0.26667 mm (0.00585 pp change). Candidates that remain untested here: the graded reference's
  own accuracy, the wide-strip edge discretisation common to both solvers but *not* shared with the
  quasi-static reference, and the extraction.
- **It does not test the box below 3 H clearance**, nor the lid in the shrinking direction.
- **It does not establish absolute accuracy.** "d falls with h" is a statement about a difference from
  a *reference*, not about truth; if the reference were itself off by ~0.4 %, a converged pair sitting
  0.4 % above it would look exactly like this.
- **It does not amend `decisions.md` 148(h)**, `box_sweep`'s verdicts, or any committed ladder row.
  It supplies the missing axis those files flagged as untested.

## 8. Reproduction

```
python3 tools/host_ladder.py --h 0.4     --clearance 3.0 --box-lateral-mult 8.0 --box-lid-mult 1.0 \
        --pml-mm 4.8 --json evidence/h_refine/h040.json  --mem-ceiling-mb 4000   # 388 MB, 254.6 s
python3 tools/host_ladder.py --h 0.26667 --clearance 3.0 --box-lateral-mult 8.0 --box-lid-mult 1.0 \
        --pml-mm 4.8 --json evidence/h_refine/h0267.json --mem-ceiling-mb 4000   # 1070 MB, 640.9 s
python3 evidence/h_refine/analyse.py    # recomputes every number in this file
```
The two rungs ran concurrently and neither hit the 4000 MB ceiling (container cgroup 6144 MB).
