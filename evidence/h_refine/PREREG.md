# Pre-registration: h-refinement of the microstrip beta offset (closes 148(h))

Frozen before any run in this directory. Written 2026-10-31 (UTC), before `h040.json`, `h0267.json`
and `h020.json` existed. The only permitted later edits are append-only errata sections.

## 1. The question, and what is NOT being asked

`evidence/box_sweep/SUMMARY.md` (S7-S8) leaves a residual after the transverse box is opened 8x laterally
and 4x in the lid: beta_FDTD sits **+1.0136 %** and beta_EIG **+1.2506 %** above the graded reference
384.7489672644 rad/m, against +1.1107 % / +2.0152 % at the unit box. The box lever available in that
sweep moves FDTD by at most 0.097 pp. That sweep held **h fixed at 0.4 mm**, so it could not distinguish
"the residual is a discretisation error in h" from "the residual is not a discretisation error at all".
This dispatch varies h at a **fixed physical domain** and nothing else. It does not re-open the box, it
does not test absolute accuracy against truth, and it does not amend 148(h)'s box-loading conclusion.

## 2. Design: the physical domain is pinned, the cell is not

The clearance in `tools/host_ladder.py` is counted in units of H (source 301-312), so at fixed
`--clearance 3.0 --box-lateral-mult 8.0 --box-lid-mult 1.0` the physical box is *identical* at every h
and requires no rescaling. The absorber is pinned in millimetres (`--pml-mm 4.8`), so the *physical*
domain including absorbers is also identical at every h; `npml` then re-derives per rung as
`round(4.8/h)` = 12 / 18 / 24. The strip is pinned in metres (`--strip-width-mm 0.8`, the supported
path), which at these three h gives n_strip = 2 / 3 / 4 and a **meshed** width of exactly 0.8 mm on all
three rungs - a property h = 0.32 mm does NOT have (0.8/0.32 = 2.5 -> n_strip 2, meshed width 0.64 mm,
-20 %), which is one of the reasons 0.32 is not used as the refined rung.

| rung | h (mm) | n_sub | cell (mm) | n_strip | meshed w (mm) | npml | n_clean | n_air |
|---|---|---|---|---|---|---|---|---|
| A | 0.4 | 4 | 0.400 | 2 | 0.800 | 12 | 96 | 12 |
| B | 0.26667 | 6 | 0.26667 | 3 | 0.800 | 18 | 144 | 18 |
| C | 0.2 | 8 | 0.200 | 4 | 0.800 | 24 | 192 | 24 |

`h = 0.3 mm` is **not representable**: `grid_for` computes `n_sub = round(1.6/0.3) = 5` and re-derives
`cell = 0.32 mm`, silently (no validation, source 228-239). A request for 0.3 therefore *is* a request
for 0.32, which is why the middle rung here is the ladder's own second rung, 0.26667, not 0.3.

## 3. The reference, and how it is allowed to move

Graded reference: `tools/d585_modal.hammerstad_beta(f)['beta']` - dispersive Hammerstad-Jensen on
Kirschning-Jansen eps_eff - evaluated at **each run's own DFT-snapped tone** `f_hz` (the tone is
h-dependent; the reference is therefore recomputed per rung and both values are recorded). At
h = 0.4 the tone is 10.19862621457275 GHz and the function returns 384.7489756771, which is the
frozen 384.7489672644 to 8.4e-6 rad/m (2.2e-8 relative) - the tolerance for "the reference is
reproduced" is 1e-6 relative, and it passes. `emfit.microstrip.Microstrip.beta` is **not** used as the
graded basis anywhere in this dispatch: it is quasi-static and gives 373.2885327645, the superseded
basis (decisions.md 146/148(b)).

## 4. Pre-registered readings and the decision rule

For each rung: `d_FDTD = 100*(beta_fdtd/ref - 1)`, `d_EIG = 100*(beta_eig/ref - 1)`,
`rel_gap = 100*(beta_eig/beta_fdtd - 1)` (%), all in percentage points.

Resolution floor carried over from box_sweep: **Delta_min = 0.0734 pp** (the smallest difference that
sweep could resolve). The pre-registered threshold for "the offset moved" is **3*Delta_min = 0.22 pp**.

Pre-registered classification, decided by the h = 0.2 rung against the h = 0.4 rung:

- **DISCRETISATION IMPLICATED** if d falls monotonically across the three rungs and the total fall is
  >= 0.22 pp. Then the residual is (at least partly) an h error and 148(h) must be re-read as
  "box + discretisation", with the h-term quantified by the fitted slope.
- **DISCRETISATION NOT THE EXPLANATION** if the total fall is < 0.22 pp, i.e. the residual is flat in h
  over a 2x refinement of the cell. Then the +1.0 % FDTD / +1.25 % EIG residual is not a discretisation
  error in h, and the surviving candidates are the graded reference's own accuracy, the strip meshing,
  and something in the extraction - none of which this dispatch tests.
- **INCONCLUSIVE** if neither holds (non-monotone, or the run stops on the sizing gate).

Observed order: a three-point fit of `d(h) = d0 + C*h^p` is reported with its residual. If the three
points do not determine p to better than +-30 %, that is reported as "order not determined", not as a
number.

## 5. Sizing gate, declared before the runs

Hard stop, per rung, on either: `peak_rss_mb > 4000` or `wall_fdtd_s > 900`. The gate is applied to the
**measured** value of the previous rung's scaling, re-priced before each launch, not to a guess. If
rung C trips the gate it is **not run**, the table is published with two rungs, and the verdict for
h = 0.2 is "not measured, gate tripped" - never extrapolated.

## 6. Confounds declared in advance

1. **npml grows with refinement** (12 -> 18 -> 24) because the absorber is pinned in mm. Absorption
   quality therefore does not degrade with h; if anything it improves, which biases *toward* seeing a
   converging offset. This is the conservative direction for a "flat in h" verdict.
2. **The h = 0.4 rung here is a bridge run, not the committed row.** The committed lat8-lid1.json and
   lat8-lid4.json were run with the default `--npml 6` (`pml_mm: null`), a 2.4 mm absorber, not 4.8 mm.
   Rung A therefore differs from the committed rows in absorber thickness as well as nothing else, and
   both numbers are reported side by side. Any difference between them is an absorber-thickness effect
   and is *not* attributed to h.
3. **Cell count is not held constant**, so solver wall time and RSS vary with h. That is the independent
   variable, not a confound.
