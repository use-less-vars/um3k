> **STATUS: SUPERSEDED (2026-10-28).** This draft is retained for provenance only. It has been
> replaced by **section 13** of `docs/design/t4_amp_ratio.md`, which carries the same material
> against the completed five-rung ladder and the rung-4 sparse (Route C) cross-check. Nothing
> below was ever applied as a rule: the draft records rung 4 as pending and proposes thresholds
> rather than applying them. Its own mtime (`2026-10-28 01:52:01.035717862`) is 43.5 s after the
> rung-4 `DONE` line, so it is **not** a timestamped pre-registration; the only block carrying
> that warrant is `(d1)`/`(d2)` in `tools/host/sparse-probe/evidence/ladder/summary_HIGHRES.txt`.
>
> Do not cite this file for any number. Cite section 13.

---

# §13 convergence — DRAFT, not yet part of the frozen note

**Status.** Draft section for `docs/design/t4_amp_ratio.md`, which is FROZEN (547 lines,
sha256 `f1077f80…`) and was **not** edited by this draft. This file is a proposal for the
maintainer to fold in, rewrite, or reject. Every number below is either read from a run
(`tools/host/sparse-probe/out/rung*/`) or is arithmetic on those numbers; nothing is
estimated except where a line says "model" or "proposed".

**Machine-readable companion.** `evidence/t4/ladder_convergence.json` (`schema:
t4.ladder_convergence/v1`) carries the same table plus every derived quantity and their
definitions, so the arithmetic here is reproducible without re-reading this prose.

**Provenance of `R_extracted`.** `tools/host/c1-audit/c1_audit.py`: per-column energies are
appended at `:705` as `(sum(e_y**2), sum(e_z_vv**2))`, reduced at `:746-747` to
`R_by_col = ez/ey`, and the banked value is `R_extracted = float(R_by_col[banked_idx])` at
`:766`. So `R_extracted = Σe_z_vv² / Σe_y²` on the single banked column, with
`e_y = E_t[:,:,0]*CELL` (200×77) and `e_z_vv = E_tz[:,:,1]*CELL` (201×76). `Q` is not a
separate measurement: §9.1 defines `Q = R_extracted / R_analytic`, so every `Q` below is
that division by `2.8101021387524523` and is derived here for the first time at rungs 1–3.

## 13.1 What was run, and what it is not

Four rungs completed; the fifth did not. The control rung is unchanged from the banked
capture: the fresh run reads `4.0489791163950715` against the banked
`4.0489791163982565`, agreeing to `1.96e-13` — inside the registered gate
(`|ΔR|/R ≤ 1e-6`, `n_eligible = 1`, `summary_HIGHRES.txt:39-46`), so the ladder is scorable.
Rung 0 also passes the `e_y` / `e_z` reproduction check (`1.956e-13`, `2.755e-11`).

Rungs 1–3 all carry `C1_ALLOW_REMESH=1` (and rungs 2–3 `C1_ALLOW_DENSE_ABOVE_MAX=1`), so
the rebuilt mesh is not the banked one, `banked_idx` resolves to `-1`, and the reproduction
check is **expected to fail** — the logs say so verbatim
(`run.log:17` / `:29`, "EXPECTED to fail"). Those FAILs are a statement about mesh identity,
not about the validity of `R_extracted`: each run selected exactly one propagating column
(`modes_kept=1 ok=1`) and each reports the `REPRO R` line from which the table below is read.
Rung 2 is tabulated here for the first time; §12.2 of the frozen note stops at rung 1.

Rung 4 (`rung4_s36_a22_z20-10-10`, 9604 free edges) left only `env.json` and a 29-line
`run.log` that ends at the DENSE ABOVE MAX banner: no `c1_spectrum.npz`, no `c1_table.txt`,
no `REPRO R` line. It is **pending**, and no number is attributed to it anywhere below.

## 13.2 The data

| rung | strip / y_air / z | free_e | R_extracted | Q | error vs R_analytic | excess over band hi | wall |
|---|---|---|---|---|---|---|---|
| 0 | 12 / 9 / 8\|4\|4 | 1444 | 4.0489791163982565 | 1.440865461991999 | 44.086546199199894 % | 30.9877692719998 % | 19.2 s |
| 1 | 16 / 12 / 10\|5\|5 | 2404 | 3.7803319900157453 | 1.3452649773413672 | 34.52649773413672 % | 22.296816121942385 % | 105.8 s |
| 2 | 20 / 15 / 12\|6\|6 | 3604 | 3.5673083405263886 | 1.2694586048427758 | 26.945860484277585 % | 15.405327712979533 % | 404.8 s |
| 3 | 24 / 18 / 14\|7\|7 | 5044 | 3.6127170292894397 | 1.2856176932036034 | 28.56176932036034 % | 16.874335745782034 % | 1277.2 s |
| 4 | 36 / 22 / 20\|10\|10 | (9604) | — pending — | — | — | — | — |

`R_analytic = 2.8101021387524523`; band `|Q − 1| ≤ 0.10` ⇔
`R_extracted ∈ [2.52909192487721, 3.09111235262770]` (§12.2, §12.5). Error is
`100·(R/R_analytic − 1)`; the "excess" column is `100·(R/3.09111235262770 − 1)`, i.e. how
far above the band's upper edge each rung sits — every completed rung is above it.

Row checks against §12.2: rung 1 `R`, `Q` and error reproduce the frozen note's roundings
(`3.780331990015745`, `1.345264977341367`, `34.5264977341367 %`); rung 0's `Q` reproduces
the banked `1.440865461991999` exactly, which is the consistency check that the `Q` column
is the note's own quantity. Rung 3 agrees with the anchors already in `decisions.md`
(`3.6127170293`, `beta_sq 96873.8886804`, `eps_eff 3.59392796`, `free_e 5044`).

## 13.3 What the four rungs say about order — and where it breaks

Using §12.3's convention (`h ∝ free_e^{-1/2}`, `p = ln(e_i/e_j)/ln(h_i/h_j)` with
`e = |R_extracted − R_analytic|`):

| interval | h ratio | e before → after | p |
|---|---|---|---|
| 0 → 1 | 0.775026165625604 | 1.2388769776458042 → 0.970229851263293 | 0.959071771078014 |
| 1 → 2 | 0.8167231023860799 | 0.970229851263293 → 0.7572062017739363 | 1.224455785196871 |
| 2 → 3 | 0.8452882891841571 | 0.7572062017739363 → 0.8026148905369874 | **−0.3465031741550254** |

Least squares in log-log over rungs 0–2 gives `p = 1.0715786518800754`
(rms 0.0141 in log); over rungs 0–3, `p = 0.7681098321351343` (rms 0.0694). The 0→1 value
reproduces §12.3 exactly, which is the anchor that this arithmetic is the note's arithmetic.

The decay of `|R − R_analytic|` **stops at rung 3**: rung 2 is the minimum of `R`
(3.5673083405263886) and rung 3 is `+0.0454086887630511` above it, i.e. `|R − R_analytic|`
goes 0.7572062017739363 → 0.8026148905369874, an increase of 6.0 %. The ordered sequence
`p = 0.96, 1.22` is broken by a negative interval. A single reversal is not yet a trend —
but it is not scatter either: within-run agreement is at the `1e-13` level, so the reversal
is a property of the mesh family, not of numerics.

## 13.4 The two scenarios the four rungs distinguish

**Scenario A — monotone decay at p ≈ 1.** This is what rungs 0–2 gave: `p = 1.07`
(0.96 at 0→1). Carried forward, Scenario A **predicted rung 3 at 3.4901516117794618**
(from `p = 0.959071771078014`) or `3.44197630945449` (from `p = 1.076558672005238`).
Rung 3 read `3.6127170292894397`, i.e. `0.122565417510` / `0.170740719835` **above**
those predictions. The ladder did not follow its own order.

Even if it had: under Scenario A, `R` reaches the band edge `3.09111235262770` only at
`free_e ≈ 22726.92343771089` (from `p = 1.076558672005238`) or
`≈ 31854.490070597025` (from `p = 0.959071771078014`) — i.e. peak ≈ 22.7 GB / 44.6 GB and
≈ 49 h / 134 h by the note's cost model (`5.5·8·free_e²` bytes, `45 s·(free_e/1444)³`).
**Scenario A is therefore not a route to a passing run either**: it converts the discrepancy
into "discretisation, at a resolution 4.5–6.3× the current rung in `free_e`", which the
plateau of §9.7/§9.8 and the present reversal both argue against funding on this evidence.

**Scenario B — a plateau.** Under Scenario B the mesh family brackets a floor of `R` near
rung 2 and rung 3 (`3.5673083405263886` … `3.6127170292894397`, `|R − R_analytic|` ≈
0.76–0.80, `Q` ≈ 1.27–1.29) and no refinement in this family moves it into the band. The
straight-line fits say the same thing from a different direction:

| fit | intercept (= R as free_e → ∞) | excess over band hi | rms | R² | predicts R at 9604 |
|---|---|---|---|---|---|
| `R` vs `1/free_e`, rungs 0–3 | 3.36584109881959 | +8.887698499808593 % | 0.04410886472597009 | 0.945391 | 3.4674505912339324 |
| `R` vs `1/√free_e`, rungs 0–3 | 2.990608605836237 | −3.251377993621818 % | 0.05366950140373725 | 0.919152 | 3.392045140566151 |
| `R` vs `1/free_e`, rungs 0–2 | 3.2751781525410877 | +5.954678410731873 % | 0.024206845681575665 | 0.984913 | 3.3932090457010746 |
| `R` vs `1/√free_e`, rungs 0–2 | 2.7540770632321094 | −10.903365874394133 % | 0.012436861843007583 | 0.996018 | 3.258799252188066 |
| `R` vs `1/free_e`, rungs 0–1 | 3.3762419374153847 | +9.224174092064352 % | 0 | 1.000000 | 3.4773906761129343 |
| `R` vs `1/√free_e`, rungs 0–1 | 2.854853021114504 | −7.64318163046892 % | 0 | 1.000000 | 3.3178815070408567 |

Two readings, both honest, and they differ:

- On **`1/free_e`** — the variable the registered rule names — every fit puts the
  `free_e → ∞` intercept **above** the band (`3.28`–`3.38`), and since the slope is positive
  the band is approached from above and is **never** reached at any finite resolution.
- On **`1/√free_e`** (= `1/h`, the variable §12.3 orders in) the intercept is **inside** the
  band (`2.75`–`2.99`), with crossing at `free_e ≈ 21538.040774610025` for the 0–2 fit
  (≈ 20.4 GB peak, ≈ 41.5 h model) and `≈ 153222.10918130612` for the 0–3 fit (≈ 1.0 TB peak;
  not runnable).

So the extrapolant half of the decision rule is **variable-dependent**, and the registered
text binds to `1/n_free`. That is a genuine ambiguity in the pre-registration, not a result:
it should be named, not resolved post hoc.

## 13.5 The registered rule applied to rungs 0–3

Verbatim (`tools/host/sparse-probe/evidence/ladder/summary_HIGHRES.txt:34-39`, quoted in
§12.6): "(d1) |R_extracted - R_analytic| falls monotonically and the 1/n_free extrapolant
lands inside the band -> the discrepancy is discretisation, and the bar can be met by a run
at the fitted resolution; (d2) it is flat or non-monotone, or the extrapolant stays above
3.09111235262770 -> the mesh is NOT the mechanism, and the ladder has eliminated it."

- Monotonicity half: **fails** at rung 3.
- `1/n_free` extrapolant half: **fails** — `3.36584109881959` is `8.887698499808593 %`
  above `3.09111235262770`.

⇒ **(d2) fires on the completed rungs.** Both halves of (d1) are violated. The ladder, as
it stands, has eliminated the mesh as the mechanism and the bar is untouched
(`summary_HIGHRES.txt:50`: "POST-HOC USE OF A NUMBER FROM THIS LADDER TO MOVE THE BAR IS A
BREACH"). Rung 4 cannot rescue (d1) without reading `≤ 2.9906114587635453` under the
`1/n_free` fit — a drop of `0.62` (4.3× the entire rung 2→3 reversal, in the opposite
direction), which no extrapolation above predicts. Under the `1/√free_e` fit the value that
would pull the five-point intercept to the band edge is `3.4880845400862164` — plausible as
a reading, but it does not change what `1/n_free` says, and the rule binds to `1/n_free`.

## 13.6 Thresholds for the pending rung 4 (PROPOSED — not registered)

Registrable as written, ahead of the run. Let `W = 3.6127170292894397 − 3.5673083405263886
= 0.0454086887630511`, the only reversal observed so far.

- **A (decay resumed):** `R₄ ≤ 3.5673083405263886` (`ΔR₄ ≤ −W`). Then refit rungs 0–4 and
  require the `1/n_free` extrapolant `≤ 3.09111235262770` before any pass is claimed.
- **B (plateau confirmed):** `3.5673083405263886 < R₄ < 3.6127170292894397`
  (`|ΔR₄| < W`). The ladder is flat at `Q ≈ 1.27–1.29`; (d2) stands.
- **C (rising / order still broken):** `R₄ ≥ 3.6127170292894397`. (d2) stands without
  argument; the family is not converging.

For calibration: all six extrapolations above predict `R₄ ∈ [3.258799252188066,
3.4773906761129343]` — the whole predicted range is above the band edge by 5.4 %–12.5 %, so
**no extrapolation predicts a passing rung 4**. A rung 4 inside that range confirms the
plateau reading and discriminates nothing between the fits; a rung 4 *below* it (branch A)
would be the only outcome that revives (d1), and a rung 4 above it (branch C) closes the
question against the mesh.

Cost of rung 4, for the record: `free_e = 9604` ⇒ one dense matrix `0.738 GB`, QZ peak
≈ `4.058419904 GB` (the log's own banner says `3.78 GB`); wall ≈ `3.68 h` at the note's
cubic model, ≈ `3.08 h` if extrapolated at the exponent the rungs actually show
(`ln(1277.2/19.2)/ln(5044/1444) = 3.355`). It is affordable; it is also, on present evidence,
not decisive for the pass/fail question.

## 13.7 What this does and does not overturn

- It does **not** change `R_extracted` at the banked resolution, `R_analytic`, the band, or
  the audit's conclusion (§10) that the extraction is correct. `Q = 1.440865461991999` at
  rung 0 stands.
- It **adds** rungs 2 and 3 and a derived `Q` for every rung: the sequence is
  `1.440865, 1.345265, 1.269459, 1.285618` — the non-monotonicity is visible in `Q` itself,
  not only in `R`.
- It **trims** the reading of §12.3. The two-rung order (`p = 0.959`) was labelled "an
  indication"; with four rungs the indication is that the order holds to rung 2 and fails at
  rung 3, so §12.3's number should not be used for extrapolation without this caveat.
- It says nothing new about the `e_y` denominator being the sensitivity site (§10); the
  ladder varied only the mesh and the discrepancy did not follow it down.

## 13.8 What is still open

1. **Rung 4 is unmeasured.** Its `run.log` has no `REPRO R`; nothing may be quoted for it.
2. **Which extrapolation variable is registered.** (d1)/(d2) say `1/n_free`; §12.3 orders in
   `1/h = free_e^{-1/2}`. The verdict differs between them (out-of-band vs in-band). This
   should be fixed by the maintainer before any rung-4 reading is scored, or the rule will be
   read two ways after the fact.
3. **Whether a single reversal is a plateau.** Two rungs at `3.567` and `3.613` establish a
   floor only if rung 4 does not fall below `3.5673083405263886`; branch B above is exactly
   that test.
4. **The measured wall exponent (`3.355`) is above the note's model (`3`).** If a larger run
   is ever funded, the note's cost table should be corrected upward (rung 3: model 1917.9 s,
   measured 1277.2 s; rung 4 projected 3.1–3.7 h).
5. **Mesh-family independence.** Every rung moves strip, `y_air` and `z` together; no rung
   isolates which of the three controls the size of the discrepancy, so (d2) eliminates *this
   family*, not "the mesh" in every possible parameterisation. Stated as scope, not as a
   hope: the note's §9.7/§9.8 sweeps are the only evidence that the strip and air bands are
   individually flat.
