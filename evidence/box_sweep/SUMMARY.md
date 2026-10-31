# Box sweep at h = 0.4 mm — results (lateral walls and lid, scaled independently)

**Graded against `docs/design/box_sweep_preregistration.md`**, frozen at 2026-10-31T00:52Z *before* the
first graded run [M, md5 `0b52326c52ef41365cdeda7f27a0a319`, 241 lines]. Clause numbers below (§1–§12)
are that file's. Nothing in the preregistration was edited after the freeze; this file is the results
record it pointed at.

Tags: **[M]** measured in this dispatch, artefact named beside it · **[L]** read from the project's own
record · **[R]** relayed from the owner · **[UNVERIFIED]** believed, no means to check here.

---

## 1. What was run

Six graded arms, one at a time, in the committed order, from `/workspace` in container `boxsweep`
(uid 1000, Python 3.12.15, numpy 2.5.4, scipy 1.18.1, cgroup `memory.max` = 6442450944 B [M]):

    python3 tools/host_ladder.py --h 0.4 --clearance 3.0 \
        --box-lateral-mult L --box-lid-mult M \
        --json evidence/box_sweep/<slug>.json --mem-ceiling-mb 3000

| # | slug | lateral mult | lid mult | exit | `meta.status` | wall (s, external) | peak RSS (MB) |
|---|---|---|---|---|---|---|---|
| 1 | `lat1-lid1` | 1.0 | 1.0 | 0 | ok | 7.98 | 150.9 |
| 2 | `lat2-lid1` | 2.0 | 1.0 | 0 | ok | 13.44 | 170.4 |
| 3 | `lat4-lid1` | 4.0 | 1.0 | 0 | ok | 23.17 | 210.1 |
| 4 | `lat8-lid1` | 8.0 | 1.0 | 0 | ok | 55.66 | 295.0 |
| 5 | `lat1-lid2` | 1.0 | 2.0 | 0 | ok | 11.80 | 167.3 |
| 6 | `lat1-lid4` | 1.0 | 4.0 | 0 | ok | 21.92 | 201.6 |
| — | `lat8-lid4` *(advisory, §7)* | 8.0 | 4.0 | 0 | ok | 135.97 | 665.6 |

All seven wrote a complete JSON with both `beta_fdtd` and `beta_eig` [M, `evidence/box_sweep/*.json`].

**The parameter set actually run is the committed one**: clearance 3.0 H with one axis scaled at a
time. The brief's clearance-8.0 whole-box arm and its (1.5, 1) / (2, 2) arms were **not** run; that
divergence, with its three reasons, is prereg §1 and is not re-argued here. The advisory joint arm in
§7 is the closest available stand-in for the whole-box question and is labelled ungraded throughout.

Priced versus measured wall: 10.82 / 17.65 / 31.31 / 58.64 / 16.72 / 28.52 s priced (163.65 s total,
prereg §1) against 7.98 / 13.44 / 23.17 / 55.66 / 11.80 / 21.92 s measured (133.97 s total) [M] — the
estimate was conservative by 18 %.

## 2. The six graded rows

Grading reference **384.7489672644 rad/m** (dispersive Hammerstad–Jansen + Kirschning–Jansen at the
run tone [M, prereg §3]). `d(s, c) = 100 · (β_s(c) − 384.7489672644) / 384.7489672644` [%], one number
per solver side per config, never averaged across sides (prereg §4).

| slug | lat | lid | grid (nx,ny,nz) | cells | β_FDTD (rad/m) | β_EIG (rad/m) | b/a | α (dB/mm) | d_FDTD % | d_EIG % | rel_gap % |
|---|---|---|---|---|---|---|---|---|---|---|---|
| lat1-lid1 | 1 | 1 | (62, 38, 22) | 51 832 | 389.0223223929 | 392.5024902740 | 0.009078 | 0.04281 | **+1.11069** | **+2.01522** | 0.89459 |
| lat2-lid1 | 2 | 1 | (62, 62, 22) | 84 568 | 388.8287021489 | 389.8023401588 | 0.010419 | 0.02410 | +1.06036 | +1.31342 | 0.25040 |
| lat4-lid1 | 4 | 1 | (62, 110, 22) | 150 040 | 388.8565104165 | 389.7257195760 | 0.010628 | 0.02322 | +1.06759 | +1.29351 | 0.22353 |
| lat8-lid1 | 8 | 1 | (62, 206, 22) | 280 984 | 388.8591004998 | 389.7256713378 | 0.010625 | 0.02322 | +1.06826 | +1.29349 | 0.22285 |
| lat1-lid2 | 1 | 2 | (62, 38, 34) | 80 104 | 388.7620208389 | 392.5432197911 | 0.009436 | 0.04342 | +1.04303 | +2.02580 | 0.97263 |
| lat1-lid4 | 1 | 4 | (62, 38, 58) | 136 648 | 388.7397670494 | 392.5467009469 | 0.009476 | 0.04342 | +1.03725 | +2.02671 | 0.97930 |

Invariant across all six [M]: `nsteps` = 2400, `dt_s` = 7.6263e-13, `cell_m` = 4e-4, `k0` = 213.747,
`n_converged` = 16, `n_stations` = 9, `alpha_floor_db_per_mm` = 0.0139 (`alpha_floor_exceeded` true in
every row). So the time window, the CFL step and the station geometry are identical and cannot explain
a difference between rows.

## 3. Offset trend, both axes

**Lateral axis (lid held at 1), |d| in %:**

| mult | 1 | 2 | 4 | 8 |
|---|---|---|---|---|
| FDTD | 1.11069 | 1.06036 | 1.06759 | 1.06826 |
| EIG | 2.01522 | 1.31342 | 1.29351 | 1.29349 |

**Lid axis (lateral held at 1), |d| in %:**

| mult | 1 | 2 | 4 |
|---|---|---|---|
| FDTD | 1.11069 | 1.04303 | 1.03725 |
| EIG | 2.01522 | 2.02580 | 2.02671 |

Reading the two tables:

- **EIG is laterally loaded and saturates fast.** Widening the lateral box once (2×) removes
  0.7018 pp of the +2.015 % EIG offset (−34.8 %); 4× and 8× add nothing (−0.0199, −0.00002 pp). The
  lateral loading is therefore *fully converged at 4× at the 0.1 pp level* and worth −0.722 pp in total.
- **The lid does nothing to EIG, and moves it the wrong way.** 2× and 4× lid raise |d_EIG| by
  0.0106 and 0.0115 pp — below Δ_min, so INVARIANT, but the sign is consistent and it is not a
  convergence toward the reference.
- **FDTD is nearly insensitive to both axes.** The whole lateral sequence spans 0.0503 pp and the lid
  sequence 0.0734 pp, against a base offset of 1.11069 pp: the box accounts for at most **6.6 %** of
  the FDTD offset.
- FDTD-lateral is strictly **non-monotone**: 1.11069 → 1.06036 → 1.06759 → 1.06826 (minimum at 2×,
  then +0.0072 pp, +0.0007 pp). The violation is 14× below Δ_min = 0.10 pp and 2.3× below the measured
  estimator spread (0.0164 %), so it is not resolvable by this instrument, but it *is* a strict
  violation and is reported as one (prereg §8, A4).
- The **FDTD-vs-EIG gap** (descriptive column only) collapses from 0.8946 % at the base box to
  0.2229 % at 4×/8× lateral: most of the two-solver discrepancy was the modal side's own lateral box,
  not a disagreement about physics.

## 4. Guards (prereg §10) — all five pass

| guard | rule | measurement | result |
|---|---|---|---|
| **G1** tone identity | all six `f_hz` within 1e-9 relative | 10198626214.572733 … 10198626214.572750; absolute spread 1.717e-05 Hz = **1.683e-15 relative** | **PASS** |
| **G2** completeness | exit 0 and `meta.status == ok` for every graded row; no partial row graded | 6/6 exit 0, 6/6 `ok`, 6/6 carry both β keys; EIG residuals 3.28e-14 … 3.82e-14 (tool limit 1e-8) | **PASS** |
| **G3** base reproduction | post-freeze base row equals both pre-freeze runs bit-for-bit | `lat1-lid1` `beta_fdtd` = 389.0223223928527 and `beta_eig` = 392.50249027403123, **identical floats** to `.scratch/rep_base_1.json` and `_2.json` | **PASS** |
| **G4** mode identity | `b_over_a` and `alpha_fdtd_db_per_mm` each within a factor [1/3, 3] of base | b/a ratios 1.0000 / 1.1477 / 1.1707 / 1.1704 / 1.0395 / 1.0438; α ratios 1.0000 / 0.5630 / 0.5425 / 0.5425 / 1.0143 / 1.0142 — no MODE-SUSPECT row | **PASS** |
| **G5** resources | `--mem-ceiling-mb 3000`, one run at a time, cgroup verified before the first run | max graded peak RSS **295.0 MB** (280 984 cells) = 9.8 % of the ceiling, 4.6 % of the 6144 MB cgroup | **PASS** |

G4's closest approach is α at the lateral arms: ratio **0.5425**, still 1.6× clear of the 1/3 bound.
It is a real physical change (the side walls load the line lossily at the base box), not a mode
change, and the b/a direction (1.17) is consistent with the same loading — but it is the guard nearest
to firing and is flagged as such.

No guard fired ⇒ the verdict is not forced to INCONCLUSIVE by §10 precedence; it is decided by the
cell pattern of §8.

## 5. Verdict, applied mechanically to the frozen §8 table

Δ_min = 0.10 % = 0.38475 rad/m (prereg §7). d0 = `lat1-lid1`, dL = `lat8-lid1`, dD = `lat1-lid4`.

| cell (arm × side) | \|d_arm\| | \|d0\| | change | frozen rule | classification |
|---|---|---|---|---|---|
| lateral 8× × **FDTD** | 1.06826 | 1.11069 | **−0.04242 pp** | < Δ_min ⇒ INVARIANT | **INVARIANT** |
| lid 4× × **FDTD** | 1.03725 | 1.11069 | **−0.07344 pp** | < Δ_min ⇒ INVARIANT | **INVARIANT** |
| lateral 8× × **EIG** | 1.29349 | 2.01522 | **−0.72172 pp** | ≥ Δ_min, \|d\| shrinks ⇒ IMPROVES | **IMPROVES** |
| lid 4× × **EIG** | 2.02671 | 2.01522 | **+0.01149 pp** | < Δ_min ⇒ INVARIANT | **INVARIANT** |

- **CONFIRMED requires all four cells IMPROVES.** One cell (EIG-lid) is INVARIANT and two FDTD cells are
  INVARIANT ⇒ **CONFIRMED not met.**
- **REFUTED requires all four cells INVARIANT-or-WORSENS with at least two WORSENS.** One cell is
  IMPROVES and there are **zero** WORSENS ⇒ **REFUTED not met.**
- Monotonicity (a necessary condition of CONFIRMED): EIG-lateral monotone non-increasing **yes**;
  FDTD-lateral **no** (strictly violated by 0.0072 pp); FDTD-lid yes; EIG-lid no.

### Verdict: **INCONCLUSIVE**

Per prereg §8, anything that is not CONFIRMED or REFUTED is INCONCLUSIVE, and §8 is explicit that the
measurement then "does not settle §148(h); it must be reported as unresolved, not as a weak
confirmation." **`decisions.md` §148(h) remains open.** That is the honest outcome and no post-hoc
reclassification is applied below: the descriptive content in §3 and §8 is what the six runs measured,
and it is not a verdict.

## 6. Why it came out INCONCLUSIVE, in one line

The four-cell gate is an AND across two axes × two solver sides. **The EIG side responds to the lateral
axis far above threshold (−0.722 pp, 35 % of its offset) and the FDTD side does not respond to either
axis above threshold (−0.042, −0.073 pp).** A protocol that demands agreement of both axes on both
sides cannot convert that split reading into a verdict — correctly, because the two sides are
disagreeing about the physics, not because the instrument is blunt.

Sensitivity of this conclusion to Δ_min (checked, not assumed): because EIG-lid moves the wrong way by
+0.0115 pp, the EIG-lid cell is INVARIANT for every Δ_min > 0.0115 pp and a WORSENS (never IMPROVES)
below it. **No value of Δ_min makes the EIG-lid cell IMPROVES, so CONFIRMED is unreachable at any
threshold**, and the INCONCLUSIVE is not an artefact of the 0.10 % choice.

## 7. Advisory arm, post-freeze and ungraded: lateral 8× and lid 4× together

Not part of the committed six, does not enter §5, and cannot change the verdict. Run afterwards to
answer the one question §5 leaves unanswered — *does the box account for the offset at all when both
axes are opened?* [M, `evidence/box_sweep/lat8-lid4.json`, exit 0, `meta.status` ok, 740 776 cells,
peak RSS 665.6 MB, wall 135.97 s]

| arm | β_FDTD | β_EIG | d_FDTD % | d_EIG % | rel_gap % |
|---|---|---|---|---|---|
| lat8-lid4 | 388.6487434231 | 389.5607821859 | **+1.01359** | **+1.25064** | 0.23467 |

Against the base row: FDTD **−0.09710 pp (8.7 % of its offset removed)**, EIG **−0.76458 pp (37.9 %
removed)**. Opening the lateral walls 8× *and* the lid 4× moves the FDTD offset by **less than
Δ_min** — 0.0029 pp short of the IMPROVES threshold — and leaves ~+1.01 % standing. The joint arm also
confirms that lateral and lid do not interact on either side (8×+4× gives FDTD 1.0136 against 1.0683
lateral-only, and EIG 1.2506 against 1.2935 lateral-only: the lid adds a further −0.055 pp on FDTD,
−0.043 pp on EIG, both below Δ_min).

## 8. What this measurement does establish (descriptive; not a verdict)

1. **The lateral walls were loading the EIG mode badly at the base box, and 2× fixes it.** The EIG
   offset drops 2.015 % → 1.313 % and is flat thereafter (1.2935 % at 4×, 1.2935 % at 8×). The modal
   box at clearance 3.0 H laterally was under-resolved for this mode; **any EIG number taken at the
   base box carries ≈ +0.72 pp of transverse-box error** [M].
2. **The lid is not loading the line, in the tested direction.** 2× and 4× lid move |d| by at most
   0.073 pp on either side; the EIG side moves *away* from the reference.
3. **The FDTD offset is not transverse-box loading.** The entire box lever available here (lateral
   8×, lid 4×, and both together) moves FDTD by ≤ 0.097 pp of 1.111 pp. Note the direction of that
   claim: it rules the box *in this range and these two directions* out as the explanation of the FDTD
   offset; it does not rule out a box effect from *shrinking* the clearance below 3 H, which was not
   tested (prereg §11).
4. **The two-solver gap was mostly a box artefact.** rel_gap 0.8946 % → 0.2229 % (lat 8×) → 0.2347 %
   (joint). The residual 0.22 % gap and the residual +1.01 % (FDTD) / +1.25 % (EIG) offsets are
   co-located in the same place and are *not* lateral or lid loading.
5. The base-box EIG row of the d585 ladder was therefore pessimistic by ~0.72 pp relative to a
   laterally converged modal box [M, by direct comparison within this sweep]. Any older EIG conclusion
   drawn at clearance 3.0 H laterally should be read with that offset in mind. **This is not a re-run
   of any earlier conclusion and none is amended here** — flagging it is all this file does.

## 9. A protocol limitation found after the freeze (disclosed, not repaired)

The §8 three-outcome table has an asymmetry the A1–A10 adversarial pass did not catch: **REFUTED is
unreachable by construction for a sweep made only of enlargements.** WORSENS requires the offset to
*grow*, and moving walls or lid outward cannot grow the offset on the FDTD side in any run measured
here (it shrinks it, by ≤ 0.073 pp) — so at most one cell could ever read WORSENS and the ≥ 2 WORSENS
requirement is unsatisfiable. In practice the only reachable non-INCONCLUSIVE verdict was CONFIRMED,
and it failed. Combined with §6, this means the frozen protocol could not have returned a non-trivial
answer for **this** pattern of results: the informative outcome (a strong, saturated lateral effect on
one side and none on the other) sits outside the vocabulary the freeze allowed. This is recorded as a
criticism of the criterion, not used to upgrade the verdict; a future dispatch that wants this
question answered must freeze a criterion that grades the *per-axis, per-side* changes and reports the
two sides separately, rather than an AND across both.

## 10. Next hypothesis, and what it costs

Since the box does not account for the residual ≈ +1.01 % (FDTD) / +1.25 % (EIG) offset, the next
candidate is the one term that is common-mode here and therefore invisible to this sweep (§5 of the
prereg): **the h = 0.4 mm discretisation**, where the 0.8 mm strip is only **2 cells wide** [M,
`strip_width_mm` 0.8, `cell_m` 4e-4 in every row]. The d585 ladder's own record has the FDTD gap
falling with h (1.012 / 0.638 / 0.450 %) and extrapolating to ≈ +0.07 % at h→0 [L, prereg §5] — i.e.
the h-term is of exactly the right order to account for ~1 pp at h = 0.4 mm.

Test: re-run `lat8-lid4` (now known to be the box-free geometry) at **h = 0.2 mm** and **h = 0.3 mm**,
graded as a two-point h-line against the same 384.7489672644 reference.

Cost, projected from measured scaling [UNVERIFIED as a projection; the ladder's own measured points are
in §1]: cells 51832 → 280984 (5.42×) cost 6.8 → 34.4 s of FDTD wall, so wall ≈ cells^1.06; h = 0.2 mm
is 8× the cells of h = 0.4 mm ⇒ ≈ 414 656 cells ⇒ ≈ 60–70 s FDTD, n_dof 1691 → ≈ 13 500 ⇒ ≈ 20–30 s
EIG, ≈ 100 s per rung, peak RSS ≈ 400–600 MB (measured 150.9 MB at 51 832 and 295.0 MB at 280 984,
sublinear). h = 0.3 mm ≈ 2.4× cells ⇒ ≈ 25 s. **Total ≈ 2–3 minutes**, inside the same 3000 MB ceiling.
The confound to declare in advance: refining h refines the strip *and* the box together, so an h-term
result will not separate "strip sampled by 2 cells" from "box sampled by 22 cells" — that separation
needs a strip-width sweep at fixed h, which is a separate and more expensive dispatch.

## 11. Reproducibility

Seven JSONs (`evidence/box_sweep/*.json`, ≈5.0 kB each), one per command, no post-processing written
back into them; every number above is read from the JSON that the corresponding command produced.
Code under test, sha256 [M, prereg §12, unchanged during the sweep]:
`tools/host_ladder.py` `1cd1a3eee4e76cd8e3672decafc35145eaf761c3cde1a900feca87f8087abeb9` (1106 lines),
`tools/d585_modal.py` `8ba8e2a86294418b7e91fa324a00dd246eaaf0e9e41bd2051156e0858e4d53a6`,
`emfit/microstrip.py` `808079b5921f2117c5ce7a18b3d35b2c7725d5b28ff9e2b249278d5c3e13d169`.
The runner (`/tmp/run_sweep.py`, not committed — it only builds the command line and reads back the
JSON, and every command it issued is printed verbatim in §1) ran one arm at a time against the same
container.

Every criterion in prereg §8 and §10 is a rule over the numbers in §2 and §7, so a reader can re-apply
the verdict table without trusting any prose in this file.
