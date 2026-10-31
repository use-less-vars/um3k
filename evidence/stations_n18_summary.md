# 18-station arm: 9 vs 18 stations at fixed box, span and h

**Provenance.** `evidence/strip_width/W08.json` (9 stations) vs `evidence/stations_n18.json`
(18 stations, `--stations 18`). Written 2026-10-31. **Marks.** `[M]` measured this session on the
two JSONs (parsed, not read); `[L]` located and read in the tree; `[R]` relayed from the
dispatching agent's `git` output -- **no git binary is available in this container, so every
git-level claim below is `[R]`, not reproduced by me.**

## 1. Result
At identical box, span, mesh and h, going 9 -> 18 stations does not move the graded quantity.
`beta_FDTD` 388.21946125247325 -> 388.0930631070381, delta **-0.1263981454** [M];
`d_W` 0.9020129473477568 -> 0.8691608402790642 pp, delta **-0.0328521070686926 pp** [M].

## 2. Controlled: one configuration field differs, and it is the station count
Bit-identical between the two JSONs: `grid` [68,218,28], `n_cells` 415072, `nsteps` 2400,
`dt_s` 7.626299478123987e-13, `pml_mm` 4.8, `npml` 12, `box_lateral_mult` 8.0, `box_lid_mult`
1.0, `clearance_h` 3.0, `h_mm` 0.4, `cell_m` 0.0004, `n_dof` 12443 (`free_e` 9326 + `free_n`
3117) [M]. Inert diffs: `max_rungs` 1 vs 3 (the rung list is one element in both, `rungs_mm`
[0.4]); `--strip-width-mm 0.8` passed explicitly in W08 only, `strip_width_mm` 0.8 in both [M].

## 3. Residual confound: two `git_rev`s
W08 `1bfd47d75065928ba403efe8333fbe172905969c`, n18 `02017d1e5015baa331b010212f2794afccdee8bc` [M].
`1bfd47d7` is an ancestor of `02017d1e`; the `tools/host_ladder.py` delta is 4 hunks / +11-3 / 1395 -> 1403 lines,
all station plumbing (`--stations` L1183-1189; `n_stations: int = studies.MS_N_STATIONS` L427-429; consumed L480;
called L814), inert at the default of 9 [R, dispatching agent's `git show` / `merge_base`]. What `1bfd47d7` was is
not findable without git: 9 hits, all "which arms carry it" [L, `evidence/strip_width/ERRATA_003.md:183-184`,
`decisions.md:9729-9732`, `evidence/strip_width/SUMMARY.md:256-262`]. Mitigation: W08's (`beta_eig`, `beta_fdtd`)
pair is bit-identical to `evidence/h_refine/h040.json:94-95` [L, `evidence/strip_width/SUMMARY.md:260-262`],
and every eigen-side output is bit-identical across the arms [M] (item 8).

## 4. `Delta_min` is a resolution floor; the decision rule is `3*Delta_min`
`Delta_min = 0.0734 pp` is the RESOLUTION FLOOR, not a grading limit [L,
`evidence/h_refine/PREREG.md:53`; `evidence/strip_width/PREREG.md:115`; code constant
`evidence/h_refine/analyse.py:14`]. The pre-registered threshold on a change is
`3*Delta_min = 0.2202 pp` [L, `evidence/strip_width/PREREG.md:115-116`, rule at `:165-166`
"MOVES iff |d_wide - d_narrow| > 0.2202 pp"; written "0.22 pp" at
`evidence/h_refine/PREREG.md:54`]. Observed |delta d| = 0.0328521070686926 pp is **6.70x below
the decision threshold** and 2.23x below the floor [M, arithmetic].

## 5. Disclosed circularity in the floor
`evidence/strip_width/PREREG.md:224-226`: "`0.0734 pp` is, operationally, *the largest
arm-induced change `box_sweep` retained as null*. Using it as the floor is mildly
self-fulfilling: a lever that moved `0.08 pp` would have been graded as a move under a floor of
`0.0734` and as noise under `0.0735`." [L] The DOES-NOT-MOVE verdict inherits this weakness; it
is not established by the 6.70x margin alone.

## 6. Reading: below threshold; the "12x closer to envelope-limited" figure is not reproducible
Consistent with envelope/termination-limited error, but "12x" does not follow from the stated inputs: from fit-noise
0.26 pp, envelope 0.0 and observed 0.03285 pp the candidate arithmetics give 7.90x (0.26/0.03285), 6.9x
(0.03285/0.22715), 6.70x (0.2202/0.03285), and 11.47x only via 0.377 pp, a different quantity (item 9b). **"12x" is
[UNVERIFIED] and is not written as a finding here.** The 1/sqrt(N) prediction of a 0.26 pp shrink assumes independent
station samples; the stations sit on a standing-wave pattern and N=9 vs N=18 differ in two-wave fit conditioning, so
it is a heuristic [UNVERIFIED]. The conclusion that the fix is termination or a longer span, NOT more stations,
survives on item 7 alone and does not depend on the 12x.

## 7. Cost: 18 stations are near-free; the eigen timer is noisy
`wall_fdtd_s` 54.37167117698118 -> 54.35445575299673 = **-0.017215 s (-0.032 %)** [M]. The march is fixed-cost
(2400 steps on 68x218x28), so stations are near-free probes. Caveat: `wall_eig_s` on the same h=0.4 problem ranges
0.5298851800616831 (W08) to 2.590875502093695 (W20), with W12 1.7930572900222614 and W16 1.9174219991546124 [M] --
a 4.89x spread on bit-identical work, so "the eigen solve is 2.7 % of the run" (1.524485116940923 /
55.942991410032846 = 2.725 %) is arithmetic on a noisy timer, not a performance measurement. The 14.49 s / 9 stations
figure from `/tmp/smoke_pre_9st.json` is a DIFFERENT configuration (`n_dof` 1691 vs 12443), preserved only in captured
stdout [L, `evidence/rung_c_errata/ERRATA_005.md` sec. D.4], and is not a comparator here.

## 8. `beta_EIG` bit-identical is correct behaviour, not an omission
`beta_eig` 389.7256713378306 in both files [M], with `residual` 3.2771050989170236e-14,
`n_converged` 16, `n_physical` 1, `opinv_calls` 133, `sigma` 152780.50791726782, `k0`
213.74739982558222, `eps_eff_eig` 3.3244235252556544, `beta_hj_kj_graded` 384.74897567707814 [M].
The eigensolve is a 2D cross-section problem with no station dependence, so identical output is
the expected result.

## 9. Two further readings, both disclosed as weak
(a) `rel_gap_pct` (gap to `beta_eig`, ungraded) moved the OTHER way: +0.0326953908202046 pp against `d_W`
-0.0328521070686926 pp [M]. They are not independent: `beta_eig - beta_hj_kj_graded` is 1.2934915946155559 pp,
bit-identical in both files, so all movement is in `beta_fdtd`. `d_W` is the pre-registered graded metric
[L, `evidence/h_refine/PREREG.md:50`; `evidence/strip_width/PREREG.md:112`]; `rel_gap_pct` is printed but never
gated [L, `tools/host_ladder.py:1275-1281`, `:1398`; grep finds no rel-gap limit option anywhere].
(b) The `0.377 pp` `2*b_over_a/d_probe` bias attributed to `decisions.md` section 143 is [R]: not read this session;
nothing here rests on it; item 6 uses it only to show what the "12x" would require.

## 10. `beta_two_station` -265.67472947179476 is a known aliased field -- never quotable
Bit-identical in both arms, so it carries no station information [M]. The aliasing is documented
and quotable at `docs/design/component_map.md:49` ("it aliases once the phase across the span
passes pi, and the station spacing exceeds lambda/2, so the number is aliased, unsigned and not a
wavenumber ... it must never be quoted as beta") [L]; `decisions.md:9311`
("`beta_two_station` is **not a beta** ... a sign-flipped, folded phase. It must never be quoted
as a wavenumber") [L]; `evidence/rung_c/SUMMARY.md:239` (aliased by a full `2*pi` wrap) [L];
`decisions.md:9301` ("garbage") [L]. The two provenance labels offered for this field do not
exist in the tree: literal `D-beta-ts` occurs only in transcript copies of the claim itself, and
no `*handoff*` document exists tree-wide (only `.scratch/handoff_done.txt`, 5 B, `done`) [L].

## Disagreements and open questions

- **The `12x` multiplier is not reproducible and needs a stated pairing.** Three candidate
  pairings of the owner's own inputs give 7.90x, 6.9x and 6.70x; only `0.377/0.03285 = 11.47x`
  approaches 12, and it substitutes a different quantity for the stated fit-noise figure. Until the
  pairing is named this figure is `[UNVERIFIED]` and carries no weight in the reading.
- **The two provenance labels offered for `beta_two_station` are not sources.** No `D-beta-ts` entry
  and no `handoff` document exist anywhere in the tree (section 10). The aliasing claim itself is sound
  and is cited there to `docs/design/component_map.md:49` and `decisions.md:9311`; those two labels
  should not be reused.
- **No independent repeatability estimate exists at fixed station count.** `Delta_min = 0.0734 pp` is
  inherited from `box_sweep` and is, on its own disclosure, the largest arm-induced change that sweep
  chose to retain as null (section 5). So "below the floor" means "below a floor set by what `box_sweep`
  called noise", not "below a measured run-to-run scatter". A same-configuration repeat at 9 stations, or at
  18, would supply that and has not been run. This is the one measurement that would let a future dispatch
  price the station lever honestly.
