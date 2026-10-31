"""Generator for evidence/strip_width/EIG_strip_width.json.

The four EIG numbers below were MEASURED in-container by this dispatch
(function-level: d585_modal.build_modal + the new tools/host_ladder.solve_ladder);
they are transcribed literal because the probe container is ephemeral. Everything
else in the JSON (the HJ+KJ reference, d_EIG, d_FDTD at n_strip=2, every leg grade)
is computed here from those numbers plus d585_modal, with asserts that pin the
agreed fourth-decimal values. Run: python3 evidence/strip_width/_make_EIG_strip_width.py
"""
import json, os, sys
sys.path.insert(0, "."); sys.path.insert(0, "tools")
import d585_modal as dm

F_HZ = 10198626214.57275
H = 1.6e-3
K0 = 213.74739982558222
ER = 4.4
DMIN = 0.0734
THREE_DMIN = 0.2202

probe = [
 dict(n_strip=2, W_mm=0.8,
      beta_eig=389.7256713378306, residual=3.2771050989170236e-14,
      eps_eff_eig=3.3244235252556544, curl_ratio=5013.2375568531115,
      lam=151886.09889972274, sigma=152780.5079172678, sigma_mult_used=0.76,
      sigma_retries=0, n_dof=12443, wall_eig_s=34.68, n_converged=16, n_physical=1,
      attempts=[dict(sigma_mult=0.76, sigma=152780.5079172678, n_converged=16,
                     n_physical=1, best_residual=3.2771050989170236e-14, accepted=True)]),
 dict(n_strip=3, W_mm=1.2,
      beta_eig=394.5069378715431, residual=3.134813785874957e-14,
      eps_eff_eig=3.4064938534834055, curl_ratio=5488.979826663936,
      lam=155635.72402878155, sigma=155795.91267879284, sigma_mult_used=0.775,
      sigma_retries=1, n_dof=12505, wall_eig_s=None, n_converged=16, n_physical=1,
      attempts=[dict(sigma_mult=0.76, sigma=None, n_converged=16, n_physical=0,
                     best_residual=0.9559803168921627, accepted=False),
                dict(sigma_mult=0.775, sigma=155795.91267879284, n_converged=16,
                     n_physical=1, best_residual=3.134813785874957e-14, accepted=True)]),
 dict(n_strip=4, W_mm=1.6,
      beta_eig=398.68271603684286, residual=3.3010964892506367e-14,
      eps_eff_eig=3.4789896422012605, curl_ratio=5838.6774934040795,
      lam=158947.90806651386, sigma=158811.31744031786, sigma_mult_used=0.79,
      sigma_retries=2, n_dof=12567, wall_eig_s=None, n_converged=None, n_physical=1,
      attempts=[dict(sigma_mult=0.76, sigma=None, n_converged=None, n_physical=None,
                     best_residual=0.9374781042952944, accepted=False),
                dict(sigma_mult=0.775, sigma=None, n_converged=None, n_physical=None,
                     best_residual=0.9523820823233484, accepted=False),
                dict(sigma_mult=0.79, sigma=158811.31744031786, n_converged=None,
                     n_physical=1, best_residual=3.3010964892506367e-14, accepted=True)]),
 dict(n_strip=5, W_mm=2.0,
      beta_eig=402.37133087951725, residual=2.977090364577061e-14,
      eps_eff_eig=3.543662707789715, curl_ratio=6087.793123935508,
      lam=161902.68791375397, sigma=161826.7222018429, sigma_mult_used=0.805,
      sigma_retries=3, n_dof=12629, wall_eig_s=None, n_converged=None, n_physical=1,
      attempts=[dict(sigma_mult=0.76, sigma=None, n_converged=None, n_physical=None,
                     best_residual=0.9327792913828687, accepted=False),
                dict(sigma_mult=0.775, sigma=None, n_converged=None, n_physical=None,
                     best_residual=0.9650183697692649, accepted=False),
                dict(sigma_mult=0.79, sigma=None, n_converged=None, n_physical=None,
                     best_residual=0.9221065847163377, accepted=False),
                dict(sigma_mult=0.805, sigma=161826.7222018429, n_converged=None,
                     n_physical=1, best_residual=2.977090364577061e-14, accepted=True)]),
]
fdtd_on_disk = {2: 388.21946125247325}          # W08.json rungs[0].beta_fdtd  [M]
fdtd_owner = {3: 0.7020, 4: 0.5040, 5: 0.3330}  # owner-asserted, console only, NOT on disk

for p in probe:
    ref = dm.hammerstad_beta(F_HZ, W=p["W_mm"]*1e-3, H=H, eps_r=ER, verbose=False)["beta"]
    p["beta_hj_kj_ref"] = ref
    p["W_over_cell"] = round(p["W_mm"]/0.4, 1)
    p["d_EIG_pp"] = 100.0*(p["beta_eig"]/ref - 1.0)
    if p["n_strip"] in fdtd_on_disk:
        p["beta_fdtd"] = fdtd_on_disk[p["n_strip"]]
        p["d_FDTD_pp"] = 100.0*(p["beta_fdtd"]/ref - 1.0)
        p["d_FDTD_provenance"] = "measured [M] -- banked in evidence/strip_width/W08.json rungs[0].beta_fdtd"
    else:
        p["beta_fdtd"] = None
        p["d_FDTD_pp"] = fdtd_owner[p["n_strip"]]
        p["d_FDTD_provenance"] = ("OWNER-ASSERTED, console only, NOT ON DISK -- W%d.json carries rungs:[] and no "
                                  "beta_fdtd, so d_FDTD cannot be re-derived from this tree" % (p["n_strip"]*4))
    p["rel_gap_eig_minus_fdtd_pp"] = p["d_EIG_pp"] - p["d_FDTD_pp"]
    assert abs(p["sigma"] - p["sigma_mult_used"]*K0*K0*ER) < 1e-6*abs(p["sigma"]), p["n_strip"]

refs = [p["beta_hj_kj_ref"] for p in probe]
assert abs(refs[0] - 384.74897567707814) < 1e-9, refs[0]
for _got, _want in zip([p["d_EIG_pp"] for p in probe], [1.2935, 1.1434, 0.9976, 0.8735]):
    assert abs(_got - _want) < 1e-3, ("d_EIG", _got, _want)   # pins the agreed 4-dp values
for _got, _want in zip([p["d_FDTD_pp"] for p in probe], [0.9020, 0.7020, 0.5040, 0.3330]):
    assert abs(_got - _want) < 1e-3, ("d_FDTD", _got, _want)

def grade(key):
    d = [p[key] for p in probe]
    steps = [d[i] - d[i+1] for i in range(3)]
    total = d[0] - d[3]
    return dict(
        d_pp=d, steps_pp=steps,
        leg1_strict_falling_by_more_than_delta_min=dict(
            pass_=all(s > DMIN for s in steps), steps_pp=steps, delta_min_pp=DMIN),
        leg2_total_fall_gt_3delta_min=dict(
            pass_=total > THREE_DMIN, total_fall_pp=total, threshold_pp=THREE_DMIN),
        leg3_half_residual_removed=dict(
            pass_=d[3] <= 0.5*d[0], ratio=d[3]/d[0], threshold=0.5, max_allowed_d5_pp=0.5*d[0]))

g_eig = grade("d_EIG_pp")
g_fdtd = grade("d_FDTD_pp")
gaps = [p["rel_gap_eig_minus_fdtd_pp"] for p in probe]
leg4 = all(g > -THREE_DMIN for g in gaps)

guards = dict(
    curl_floor_1e_6=dict(pass_=all(p["curl_ratio"] > 1e-6 for p in probe),
        values=[p["curl_ratio"] for p in probe],
        note="PREREG section 10 curl guard: |curl|/|lam| must exceed 1e-6; all values are 5.0e3..6.1e3"),
    residual_limit_1e_8=dict(pass_=all(p["residual"] < 1e-8 for p in probe),
        values=[p["residual"] for p in probe],
        note="pencil residual < TOL_RESID; the shipped limit is 1e-8 (W08 meta.residual_limit), not 1e-6"),
    eps_eff_below_eps_r=dict(pass_=all(p["eps_eff_eig"] < ER for p in probe),
        values=[p["eps_eff_eig"] for p in probe], eps_r=ER),
    alpha_floor=dict(fired=False,
        note=("alpha_floor_exceeded is true only in W08n.json (lateral box 1x, a different arm) and is a labelled "
              "DIAGNOSTIC (alpha_floor_enforced false, meta.alpha_floor_note); it is NOT a section 10 guard and fires "
              "on no arm here")))

PREREG = ("**CONFIRMED (strip meshing implicated)** -- all of: 1. `|d_W|` falls at **each** of the three consecutive "
 "steps `2 -> 3 -> 4 -> 5`, i.e. each step is a fall of more than `Delta_min`; a step smaller than the floor does not "
 "count as a fall; 2. total fall `|d_W(2)| - |d_W(5)| > 0.2202 pp`; 3. at least half the `n_strip = 2` residual is "
 "removed: `|d_W(5)| <= 0.5 * |d_W(2)|`; 4. the EIG side does not move *against* the FDTD side by more than `0.2202 pp` "
 "(the modal half meshes the same strip and checks `ny_strip == n_strip` against the FDTD half [M, `build_modal` source "
 "~345-360], so it is a second, independent read on the same quantity; a large disagreement means the two halves did not "
 "measure the same change); 5. no guard in section 10 fired. / **REFUTED (meshing is not the explanation)** -- any of: "
 "the sequence is not strictly falling by more than `Delta_min` at each step; total fall `<= 0.2202 pp` (this is what "
 "\"flat\" means, quantified); the half-residual condition (3) fails. Then the residual at `n_strip = 2` survives a strip "
 "`2.5x` wider in cells and is not attributable to how the strip is meshed at this `h`. / **INCONCLUSIVE** -- anything "
 "else: any arm aborted or missing (`meta.abort_reason` not `None`, non-zero exit, no row); any arm tripping the section "
 "5 gate; guard G1/G2/G4/G6 fired; the two solver sides disagreeing per (4). Not a weak confirmation and not a weak "
 "refutation. / Precedence: **guards first**, then the rule.")

arms_out = []
for p in probe:
    q = dict(p)
    q["provenance_EIG"] = "measured [M] in-container by this dispatch (sigma ladder in tools/host_ladder.py)"
    q["n_strip_pinning"] = "strip width pinned to n_strip exactly; build_modal asserts ny_strip == n_strip"
    arms_out.append(q)

out = {
 "file": "evidence/strip_width/EIG_strip_width.json",
 "title": "Strip-width sweep, EIG (modal) side -- companion to W08/W12/W16/W20",
 "status": "companion measurement; supersedes no frozen artefact and changes no verdict by fiat",
 "provenance": {
   "eigenpath": ("tools/host_ladder.py -- build_modal + route_c + pick_mode, driven by the new solve_ladder(). NOT "
                 "emfit/mode2d.py: that module was not imported, not edited, and is not the eigenpath that produced "
                 "these numbers (it keeps its pin b820a3fd4acbfd425e440910685da81c03c8a8ee7b3988e5bdb7a6a7f199c534)"),
   "host_ladder_sha256": "0d7191973fe7babf53463205a1da968befcca205e725027ed83dc0267b190c9b",
   "method": ("function-level, in-container: d585_modal.build_modal(0.4e-3, clearance=3.0, n_strip=N, w_m=W, "
              "k0=213.74739982558222, lateral_mult=8.0, lid_mult=1.0) then solve_ladder(pb, k0, k=16) -- the same "
              "ascending sigma ladder the edited tool now ships"),
   "generator": "evidence/strip_width/_make_EIG_strip_width.py (recomputes everything except the four measured EIG values)",
   "no_fdtd": ("no FDTD was run by this dispatch: in-container FDTD is 30-60x the host cost (~30-50 min per arm). The "
               "FDTD column is therefore quoted from disk (arm n_strip=2) or owner-asserted (arms 3-5)"),
   "container_vs_host": "wall_eig_s 34.68 s at n_strip=2 in-container vs 0.529885 s for the row of record on host (~65x)",
   "f_hz": F_HZ,
   "f_hz_note": ("realised tone of the W08 row of record (meta.tone_f_actual_ghz); the HJ+KJ reference is re-derived per "
                 "width at this tone"),
   "cell_mm": 0.4, "h_mm": 0.4, "clearance_h": 3.0, "box_lateral_mult": 8.0, "box_lid_mult": 1.0, "pml_mm": 4.8,
   "eps_r": ER, "h_substrate_m": H, "k0": K0,
   "reference": "d585_modal.hammerstad_beta(f_hz, W=W, H=1.6e-3, eps_r=4.4)['beta'] (HJ+KJ), recomputed per arm",
   "reference_validation": ("recompute at W=0.8 mm gives 384.74897567707814, equal to W08.json rungs[0].beta_hj_kj_graded "
                            "bit-for-bit, which validates the per-arm re-derivation"),
   "cross_warrant": ("the 0.76-attempt junk residuals measured here (9.559803168921627e-01 / 9.374781042952944e-01 / "
                     "9.327792913828687e-01 at n_strip 3/4/5) are the numbers printed in W12/W16/W20 meta.failure "
                     "('best residual 9.56e-01 / 9.37e-01 / 9.33e-01'), so the in-container modal path reproduces the host "
                     "runs that emitted the frozen artefacts"),
   "sigma_formula_check": "sigma = sigma_mult * k0^2 * ER verified for every accepted arm to 1e-6 relative",
   "delta_min_pp": DMIN, "three_delta_min_pp": THREE_DMIN},
 "d_definition": "d = 100*(beta/ref - 1) in percentage points (pp); Delta_min 0.0734 pp, 3*Delta_min 0.2202 pp (PREREG section 4)",
 "arms": arms_out,
 "grading": {
   "prereg_4_1_verbatim": PREREG,
   "prereg_source": "evidence/strip_width/PREREG.md L118-139 (frozen, read on disk)",
   "EIG_side": dict(g_eig,
     leg4_eig_not_against_fdtd=dict(pass_=leg4, gap_pp=gaps, threshold_pp=-THREE_DMIN),
     leg5_no_section_10_guard=dict(pass_=True, detail=guards),
     note="identical rule set with d_EIG substituted for d_W"),
   "FDTD_side": dict(g_fdtd,
     leg4_eig_not_against_fdtd=dict(pass_=leg4, gap_pp=gaps, threshold_pp=-THREE_DMIN),
     leg5_no_section_10_guard=dict(pass_=True, detail=guards),
     caveat=("d_FDTD(2) is measured and on disk; d_FDTD(3/4/5) are owner-asserted console values, so the FDTD side "
             "cannot be certified from this tree alone")),
   "legs_summary": {
     "leg1": "PASS on both sides",
     "leg2": "PASS on both sides",
     "leg3": ("PASS on FDTD (%.4f <= 0.5) / FAIL on EIG (%.4f > 0.5, i.e. %.4f pp against an allowed %.4f pp)" %
               (g_fdtd["leg3_half_residual_removed"]["ratio"], g_eig["leg3_half_residual_removed"]["ratio"],
                g_eig["d_pp"][3], g_eig["leg3_half_residual_removed"]["max_allowed_d5_pp"])),
     "leg4": ("PASS (EIG above FDTD at every width; gap %.4f -> %.4f pp widens, never reverses)" % (gaps[0], gaps[3])),
     "leg5": "PASS on both sides (no section 10 guard fired on any accepted arm)"},
   "verdict": ("Reading A (letter of section 4.1: the graded quantity d_W is the FDTD one, the EIG side entering only via "
     "leg 4): all five legs pass, so CONFIRMED -- but this reading is NOT certifiable from the tree as frozen, because "
     "arms n_strip 3/4/5 carry rungs:[] (no row, no beta_fdtd) and the INCONCLUSIVE clause makes 'any arm aborted or "
     "missing' decisive; it rests on owner-asserted console numbers. Reading B (EIG graded as an independent quantity, "
     "which is what this file exists to make possible): leg 3 FAILS, so INCONCLUSIVE. Both readings agree it is not "
     "REFUTED: legs 1 and 2 hold on both sides, so the sequence really does fall and the total fall really does exceed "
     "3*Delta_min. This dispatch does not pick between the readings; the owner must rule whether the FDTD side is "
     "authoritative.")},
 "reference_implication_test": {
   "question": ("a falling d_W is consistent both with 'FDTD resolves the strip as cells rise' and with 'the HJ+KJ "
                "reference drifts with W at fixed f'"),
   "why_four_points_cannot_separate": ("both hypotheses predict a monotone falling d_W in n_strip. Four points, four "
     "widths, one solver, one reference: the two explanations are observationally identical in that design"),
   "separator": ("a second independent solver at the SAME W -- the modal EIG value, which meshes the same strip exactly "
     "(build_modal asserts ny_strip == n_strip) and never touches the FDTD grid"),
   "outcome": (("EIG sits " + " / ".join("%.4f" % g for g in gaps) + " pp ABOVE FDTD. The reference is therefore implicated in DIRECTION: ") +
     "two independent solvers both drift away from HJ+KJ as W grows, so the reference is not exact at wider strips. It is "
     "NOT implicated in magnitude: if reference drift were the whole story both sides would fall by the same amount, and "
     "they do not -- the gap widens monotonically. The surviving residual is solver-specific (EIG-side); the 0.902 pp "
     "n_strip=2 residual is NOT removed by wider meshing on the EIG side"),
   "permitted_conclusion": "the strip-meshing explanation is not sufficient on its own; leg 3 fails on the EIG side",
   "forbidden_conclusion": ("that the reference explains the residual away, or that wider meshing fixes it -- neither is "
                            "supported by these numbers")},
 "absent_fdtd_log_finding": {
   "search": "grep -rl 'fit_one' / grep -rl 'BETA  fit_one' / find -name '*.log' '*.txt' '*.out' over the whole workspace",
   "result": ("only evidence/h_refine/h040.log, evidence/h_refine/h0267.log and .scratch/d5811/fit2_h04.log carry FDTD "
              "BETA lines. No log, txt or out file exists for W=1.2/1.6/2.0 anywhere; the only files matching "
              "'strip-width-mm 1.x/2.0' are W12/W16/W20.json themselves. NOTHING WAS HARVESTED"),
   "why_w12_w16_w20_show_fdtd_s_zero": ("meta.timings.fdtd_s is 0.0 only because rows is empty (fdtd_s sums over rows). "
     "wall_total_s of 54.46 / 55.72 / 59.00 s is consistent with the ~54.37 s FDTD of W08 having actually run and then "
     "being discarded by the abort: the FDTD most likely ran but was never banked"),
   "consequence": "d_FDTD for arms 3-5 stays owner-asserted; it is not evidence on disk and is labelled as such here"},
 "caveats": [
   "these EIG rows are NOT the frozen artefacts: W12/W16/W20 remain aborted shells (rungs:[], abort_reason 'ladder_error'). This file is a separate companion and rewrites nothing",
   "the parent arms were preregistered with the single-shift solver (sigma_mult 0.76). The numbers above come from the ascending ladder; at n_strip=2 the ladder's first shift reproduces the single-shift result bit-for-bit, so the EIG column is comparable",
   "sigma_retries > 0 on arms 3/4/5 is a solver-side recovery, not a physics change: only the ARPACK shift moved; the pencil, the guards and the reference are untouched",
   "n_converged is recorded only where it was transcribed; on the failed attempts it was 16 (ARPACK convergence on the inverted operator) while the pencil residual was 0.92-0.97, so n_converged is not evidence of a usable spectrum",
   "the section 5 resource gate is not restated: these are rung-level modal runs (seconds, not minutes) and no FDTD was performed"],
 "written_by": "dispatch: sigma ladder in tools/host_ladder.py + strip-width EIG companion (worker, no commit)",
}
os.makedirs("evidence/strip_width", exist_ok=True)
with open("evidence/strip_width/EIG_strip_width.json", "w") as f:
    json.dump(out, f, indent=1)
    f.write("\n")
json.load(open("evidence/strip_width/EIG_strip_width.json"))
print("refs   ", refs)
print("d_EIG  ", [round(p["d_EIG_pp"], 4) for p in probe])
print("d_FDTD ", [round(p["d_FDTD_pp"], 4) for p in probe])
print("EIG legs  ", [g_eig[k]["pass_"] for k in ("leg1_strict_falling_by_more_than_delta_min","leg2_total_fall_gt_3delta_min","leg3_half_residual_removed")], "ratio", round(g_eig["leg3_half_residual_removed"]["ratio"],4), "steps", [round(s,4) for s in g_eig["steps_pp"]], "total", round(g_eig["leg2_total_fall_gt_3delta_min"]["total_fall_pp"],4))
print("FDTD legs ", [g_fdtd[k]["pass_"] for k in ("leg1_strict_falling_by_more_than_delta_min","leg2_total_fall_gt_3delta_min","leg3_half_residual_removed")], "ratio", round(g_fdtd["leg3_half_residual_removed"]["ratio"],4), "steps", [round(s,4) for s in g_fdtd["steps_pp"]], "total", round(g_fdtd["leg2_total_fall_gt_3delta_min"]["total_fall_pp"],4))
print("gap pp ", [round(g,4) for g in gaps], "leg4", leg4)
print("bytes  ", os.path.getsize("evidence/strip_width/EIG_strip_width.json"))
