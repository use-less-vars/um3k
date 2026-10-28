#!/usr/bin/env python3
"""Axis-decomposed R sweep: is the campaign's R hump a diagonal artefact?"""
import os
import sys

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS",
           "THREADPOOLCTL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import gc
import json
import math
import re
import time

import numpy as np

import rung4_routeC_probe as r4
from routeC_mesh_probe import DenseShim

OUT_DIR = os.path.join(HERE, "out_mesh")
OUT_JSON = os.path.join(OUT_DIR, "axis_sweep.json")
OVERLAP_JSON = os.path.join(OUT_DIR, "mode_overlap.json")

SPEC_RE = re.compile(r"^(\d+)/(\d+)/(\d+)-(\d+)-(\d+)$")
TOL = 1e-9

MESHES_Y = ["22/20/34-17-17", "27/22/34-17-17", "35/28/34-17-17",
            "43/34/34-17-17", "44/35/34-17-17"]
MESHES_Z = ["56/43/20-10-10", "56/43/22-11-11", "56/43/28-14-14",
            "56/43/34-17-17", "56/43/35-17-18"]
CORNER = "56/43/34-17-17"


def parse_spec(spec):
    m = SPEC_RE.match(spec.strip())
    if not m:
        raise ValueError("bad spec %r" % (spec,))
    s, a, z0, z1, z2 = (int(x) for x in m.groups())
    return s, a, [z0, z1, z2]


CAMPAIGN_SIGMA = {}


def load_campaign():
    """sigma + R + lambda per campaign mesh, straight from the banked files."""
    out = {}
    for label in ("M5_ctrl_rung4", "M1_fe11888", "M2_fe19665", "M3_fe28980",
                  "M4_fe30672"):
        p = os.path.join(OUT_DIR, label + ".json")
        try:
            with open(p) as fh:
                d = json.load(fh)
            sig = d["sigma"]
            out[label] = {
                "sigma": float(sig["value"]) if isinstance(sig, dict) else float(sig),
                "free_e": int(d["counts"]["free_edges"]) if "counts" in d else None,
            }
        except Exception as exc:                                # noqa: BLE001
            print("  [campaign] %s: %s" % (p, exc), flush=True)
    return out


def load_overlap_diagonal():
    try:
        with open(OVERLAP_JSON) as fh:
            d = json.load(fh)
        return {m["label"]: {"R": m["R"], "lambda": m["lambda"],
                             "free_e": m["n_e"], "spec": m["spec"]}
                for m in d["meshes"] if m.get("error") is None}
    except Exception as exc:                                    # noqa: BLE001
        print("  [diagonal] %s unreadable (%s)" % (OVERLAP_JSON, exc), flush=True)
        return {}


def sigma_for(spec):
    """Per-mesh sigma from the campaign record when this exact mesh was run."""
    s, a, z = parse_spec(spec)
    grid = (s, a, tuple(z))
    known = {
        (36, 22, (20, 10, 10)): "M5_ctrl_rung4",
        (36, 27, (22, 11, 11)): "M1_fe11888",
        (47, 35, (28, 14, 14)): "M2_fe19665",
        (56, 43, (34, 17, 17)): "M3_fe28980",
        (58, 44, (35, 17, 18)): "M4_fe30672",
    }
    label = known.get(grid)
    if label and label in CAMPAIGN_SIGMA:
        return CAMPAIGN_SIGMA[label]["sigma"], "campaign:" + label
    return float(r4.DEFAULT_SIGMA), "r4.DEFAULT_SIGMA"


def fields_on_lattice(mode, ctx, ref):
    nyn, nzn = ctx["NY"] + 1, ctx["NZ"] + 1
    cell = ctx["CELL"]
    yn_node = np.arange(nyn) * cell
    zn_node = np.arange(nzn) * cell
    yc_mid = (np.arange(nyn - 1) + 0.5) * cell
    zc_mid = (np.arange(nzn - 1) + 0.5) * cell
    yy, zz = np.meshgrid(yc_mid, zn_node, indexing="ij")
    iyy, izz = np.meshgrid(yn_node, zc_mid, indexing="ij")
    ey_pts = np.stack([yy.ravel(), zz.ravel()], axis=1)
    ez_pts = np.stack([iyy.ravel(), izz.ravel()], axis=1)
    e_t = mode.e_at(ey_pts).reshape(nyn - 1, nzn, 2)
    e_y = e_t[:, :, 0] * cell
    e_tz = mode.e_at(ez_pts).reshape(nyn, nzn - 1, 2)
    e_z_vv = e_tz[:, :, 1] * cell
    num = float(np.sum(e_z_vv ** 2))
    den = float(np.sum(e_y ** 2))
    return {"e_y": e_y, "e_z_vv": e_z_vv,
            "R": (num / den) if den != 0.0 else float("nan"),
            "corr_ey": r4.corr(ref["e_y"], e_y),
            "corr_ez_vv": r4.corr(ref["e_z"], e_z_vv),
            "sum_e_y2": den, "sum_e_z_vv2": num}


def make_recorder(store, ref):
    def recorder(mode, ctx, _unused=None):
        out = fields_on_lattice(mode, ctx, ref)
        store["e_y"] = out["e_y"]
        store["e_z_vv"] = out["e_z_vv"]
        return {k: out[k] for k in ("R", "corr_ey", "corr_ez_vv",
                                    "sum_e_y2", "sum_e_z_vv2")}
    return recorder


def lattice_masks(ctx):
    nyn, nzn = ctx["NY"] + 1, ctx["NZ"] + 1
    cell = ctx["CELL"]
    cy = np.arange(nyn) * cell
    cz = np.arange(nzn) * cell
    ym = (np.arange(nyn - 1) + 0.5) * cell
    zm = (np.arange(nzn - 1) + 0.5) * cell
    out = {}
    for kind, ya, za in (("e_y", ym, cz), ("e_z_vv", cy, zm)):
        sub = za <= ctx["HSUB"] + TOL
        air = za > ctx["HSUB"] + TOL
        strip = (ya >= ctx["Y0"] - TOL) & (ya <= ctx["Y1"] + TOL)
        assert not np.any(sub & air)
        assert np.count_nonzero(sub) + np.count_nonzero(air) == za.size
        out[kind] = {"substrate": ("col", sub), "air": ("col", air),
                     "strip_footprint": ("row", strip)}
    return out


def ratio(ey, ez, ysel, zsel):
    """e_y lives on (nyn-1, nzn), e_z_vv on (nyn, nzn-1): each needs its own mask."""
    ay, my = ysel
    az, mz = zsel
    a = ey[:, my] if ay == "col" else ey[my, :]
    b = ez[:, mz] if az == "col" else ez[mz, :]
    den = float(np.sum(a ** 2))
    num = float(np.sum(b ** 2))
    return (num / den) if den != 0.0 else float("nan")


def run_one(spec, ctx, ref, masks):
    strip, yair, z = parse_spec(spec)
    sigma, sigma_src = sigma_for(spec)
    label = ("Y_%d_%d" % (strip, yair)) if spec in MESHES_Y else \
            ("Z_%d_%d_%d" % (z[0], z[1], z[2]))
    if spec == CORNER:
        label = "YZ_corner_56_43_34_17_17"
    cfg = {"rung": -1, "role": label, "strip": strip, "yair": yair, "z": list(z)}
    entry = {"label": label, "spec": spec, "strip": strip, "yair": yair,
             "z": list(z), "sigma": sigma, "sigma_source": sigma_src,
             "error": None}
    print("\n=== %-26s spec=%s  sigma=%.12g (%s) ==="
          % (label, spec, sigma, sigma_src), flush=True)
    store = {}
    original = r4.field_scalars
    pb = route_c = shim = None
    t0 = time.perf_counter()
    ladder = [sigma] + [sigma * f for f in (0.996, 0.992, 0.988, 0.984, 0.980)]
    tries = []
    try:
        for attempt, sig in enumerate(ladder):
            store.clear()
            if attempt:
                print("  [retry %d] sigma=%.9g (previous residual >= 1e-6)"
                      % (attempt, sig), flush=True)
            try:
                r4.field_scalars = make_recorder(store, ref)
                with DenseShim(mode="auto") as shim:
                    pb = r4.build_problem(cfg, ctx)
                    route_c = r4.run_route_c(pb, ctx, ref, sig, None)
            except Exception as exc:                            # noqa: BLE001
                entry["error"] = r4.exception_text(exc)
                print("  FAILED: %s" % entry["error"], flush=True)
                break
            tries.append({"sigma": float(sig),
                          "lambda": float(route_c["eigenvalue"]),
                          "R": float(route_c["R"]),
                          "residual": float(route_c["residual"])})
            if float(route_c["residual"]) < 1e-6:
                sigma = float(sig)
                break
    finally:
        r4.field_scalars = original
        entry["wall_s"] = time.perf_counter() - t0
    entry["sigma"] = float(sigma)
    entry["sigma_used"] = float(sigma)
    entry["sigma_retries"] = max(0, len(tries) - 1)
    entry["sigma_ladder"] = tries
    if entry["sigma_retries"]:
        entry["sigma_source"] = entry["sigma_source"] + "+retry"

    if entry["error"] is None:
        ey = np.array(store["e_y"], copy=True)
        ez = np.array(store["e_z_vv"], copy=True)
        entry.update({
            "n_e": int(pb["n_e"]), "n_n": int(pb["n_n"]),
            "free_e": int(len(pb["free_e"])),
            "mesh_checks_ok": bool(pb["mesh_checks_ok"]),
            "lambda": float(route_c["eigenvalue"]),
            "beta_sq": float(route_c["beta_sq"]),
            "R": float(route_c["R"]),
            "residual": float(route_c["residual"]),
            "corr_ey_routec": float(route_c["corr_ey"]),
            "corr_ez_vv_routec": float(route_c["corr_ez_vv"]),
            "corr_vs_ref_ey": r4.corr(ref["e_y"], ey),
            "corr_vs_ref_ez_vv": r4.corr(ref["e_z"], ez),
            "shim_interceptions": ([] if shim is None
                                   else len(shim.interceptions)),
        })
        entry["d_rec_R"] = entry["R"] - (
            float(np.sum(ez ** 2)) / float(np.sum(ey ** 2)))
        entry["d_rec_ey"] = entry["corr_ey_routec"] - entry["corr_vs_ref_ey"]
        entry["d_rec_ez"] = entry["corr_ez_vv_routec"] - entry["corr_vs_ref_ez_vv"]
        entry["R_regions"] = {}
        for name in ("substrate", "air", "strip_footprint"):
            entry["R_regions"][name] = ratio(ey, ez, masks["e_y"][name],
                                             masks["e_z_vv"][name])
        entry["R_regions"]["all"] = entry["R"]
        entry["converged"] = bool(entry["residual"] < 1e-6)
        p = np.abs(ey)
        iy, iz = np.unravel_index(int(np.argmax(p)), p.shape)
        entry["peak_abs_ey"] = float(p[iy, iz])
        entry["peak_y"] = float((iy + 0.5) * ctx["CELL"])
        entry["peak_z"] = float(iz * ctx["CELL"])
        print("  n_e=%d lambda=%.12g R=%.12g Rsub=%.12g Rair=%.12g Rstrip=%.12g"
              " res=%.2e wall=%.1fs d_rec=%+.1e"
              % (entry["n_e"], entry["lambda"], entry["R"],
                 entry["R_regions"]["substrate"], entry["R_regions"]["air"],
                 entry["R_regions"]["strip_footprint"], entry["residual"],
                 entry["wall_s"], entry["d_rec_R"])
              + ("  [sigma retries=%d]" % entry["sigma_retries"]
                 if entry["sigma_retries"] else ""), flush=True)
    del pb, route_c, shim, store
    gc.collect()
    return entry


def mono_line(name, vals):
    if len(vals) < 2:
        return "n/a"
    d = np.diff(np.asarray(vals, dtype=float))
    if np.all(d > 0):
        return "MONOTONE increasing (steps %s)" % " ".join("%+.5f" % v for v in d)
    if np.all(d < 0):
        return "MONOTONE decreasing (steps %s)" % " ".join("%+.5f" % v for v in d)
    return "NOT MONOTONE (steps %s)" % " ".join("%+.5f" % v for v in d)


def main():
    t0 = time.perf_counter()
    global CAMPAIGN_SIGMA
    CAMPAIGN_SIGMA = load_campaign()
    diag = load_overlap_diagonal()
    ctx = r4.load_context()
    ref = r4.analytic_reference(ctx)
    masks = lattice_masks(ctx)

    print("=" * 78)
    print("AXIS-DECOMPOSED R SWEEP")
    print("=" * 78)
    print("lattice-cell=%.1e HSUB=%.4g Y0=%.4g Y1=%.4g  masks e_y sub/air/strip="
          "%d/%d/%d  e_z_vv=%d/%d/%d"
          % (ctx["CELL"], ctx["HSUB"], ctx["Y0"], ctx["Y1"],
             np.count_nonzero(masks["e_y"]["substrate"][1]),
             np.count_nonzero(masks["e_y"]["air"][1]),
             np.count_nonzero(masks["e_y"]["strip_footprint"][1]),
             np.count_nonzero(masks["e_z_vv"]["substrate"][1]),
             np.count_nonzero(masks["e_z_vv"]["air"][1]),
             np.count_nonzero(masks["e_z_vv"]["strip_footprint"][1])))
    print("campaign sigmas found: %s" % {k: v["sigma"] for k, v in
                                         CAMPAIGN_SIGMA.items()})

    cache = {}
    order = []

    def get(spec):
        if spec not in cache:
            cache[spec] = run_one(spec, ctx, ref, masks)
            order.append(spec)
        else:
            print("\n[reuse] %s already solved (%s)" % (spec, cache[spec]["label"]),
                  flush=True)
        return cache[spec]

    for spec in MESHES_Y:
        get(spec)
    for spec in MESHES_Z:
        get(spec)

    ys = [cache[s] for s in MESHES_Y]
    zs = [cache[s] for s in MESHES_Z]

    # ---------------------------------------------------------------- T1
    print("\n" + "=" * 78)
    print("(T1) Y-AXIS SWEEP  (z fixed at 34-17-17)")
    print("=" * 78)
    print("%-16s %-14s %8s %22s %18s %14s %9s"
          % ("strip/yair", "spec", "free_e", "lambda", "R", "dR(prev)",
             "residual"))
    prev = None
    for e in ys:
        if e.get("error"):
            print("%-16s %-14s   FAILED  %s" % (
                "%d/%d" % (e["strip"], e["yair"]), e["spec"], e["error"][:40]))
            continue
        d = "-" if prev is None else "%+.15f" % (e["R"] - prev)
        print("%-16s %-14s %8d %22.15f %18.15f %14s %9.2e%s"
              % ("%d/%d" % (e["strip"], e["yair"]), e["spec"], e["free_e"],
                 e["lambda"], e["R"], d, e["residual"],
                 "  [sigma retried]" if e["sigma_retries"] else ""))
        prev = e["R"]
    yok = [e for e in ys if not e.get("error")]
    yc = [e for e in yok if e["converged"]]
    print("  R along y-axis, ALL SOLVED      : "
          + mono_line("R", [e["R"] for e in yok]))
    print("  R along y-axis, CONVERGED ONLY  : "
          + mono_line("R", [e["R"] for e in yc])
          + "   [%d/%d points]" % (len(yc), len(yok)))
    for e in yok:
        if not e["converged"]:
            print("  !! NOT CONVERGED (excluded from trends): %-14s res=%.3e "
                  "R=%.15f lambda=%.12g"
                  % (e["spec"], e["residual"], e["R"], e["lambda"]))

    # ---------------------------------------------------------------- T2
    print("\n" + "=" * 78)
    print("(T2) Z-AXIS SWEEP  (y fixed at 56/43)")
    print("=" * 78)
    print("%-16s %-14s %8s %22s %18s %14s %9s"
          % ("z0-z1-z2", "spec", "free_e", "lambda", "R", "dR(prev)",
             "residual"))
    prev = None
    for e in zs:
        if e.get("error"):
            print("%-16s %-14s   FAILED  %s" % (
                "%d-%d-%d" % tuple(e["z"]), e["spec"], e["error"][:40]))
            continue
        d = "-" if prev is None else "%+.15f" % (e["R"] - prev)
        print("%-16s %-14s %8d %22.15f %18.15f %14s %9.2e%s"
              % ("%d-%d-%d" % tuple(e["z"]), e["spec"], e["free_e"],
                 e["lambda"], e["R"], d, e["residual"],
                 "  [sigma retried]" if e["sigma_retries"] else ""))
        prev = e["R"]
    zok = [e for e in zs if not e.get("error")]
    zc = [e for e in zok if e["converged"]]
    print("  R along z-axis, ALL SOLVED      : "
          + mono_line("R", [e["R"] for e in zok]))
    print("  R along z-axis, CONVERGED ONLY  : "
          + mono_line("R", [e["R"] for e in zc])
          + "   [%d/%d points]" % (len(zc), len(zok)))
    for e in zok:
        if not e["converged"]:
            print("  !! NOT CONVERGED (excluded from trends): %-14s res=%.3e "
                  "R=%.15f lambda=%.12g"
                  % (e["spec"], e["residual"], e["R"], e["lambda"]))

    # ---------------------------------------------------------------- T3
    print("\n" + "=" * 78)
    print("(T3) REGION DECOMPOSITION OF R  (sum e_z_vv^2 / sum e_y^2 per block)")
    print("=" * 78)
    print("%-27s %-14s %8s %18s %18s %18s %18s"
          % ("label", "spec", "free_e", "R_total", "R_substrate", "R_air",
             "R_strip"))
    for spec in order:
        e = cache[spec]
        if e.get("error"):
            print("%-27s %-14s   FAILED  %s"
                  % (e["label"], e["spec"], e["error"][:40]))
            continue
        rr = e["R_regions"]
        print("%-27s %-14s %8d %18.15f %18.15f %18.15f %18.15f"
              % (e["label"], e["spec"], e["free_e"], rr["all"],
                 rr["substrate"], rr["air"], rr["strip_footprint"]))

    # ---------------------------------------------------------------- T4
    print("\n" + "=" * 78)
    print("(T4) SIDE BY SIDE: campaign diagonal vs the two axis curves")
    print("=" * 78)
    camp_rows = [(lab, d["spec"], d["free_e"], d["R"])
                 for lab, d in sorted(diag.items(), key=lambda kv: kv[1]["free_e"])]
    ymap = {e["free_e"]: e for e in yok}
    zmap = {e["free_e"]: e for e in zok}
    print("%-8s %-18s %8s %18s | %8s %18s | %8s %18s"
          % ("free_e", "campaign", "", "R_campaign", "y-axis", "R_y",
             "z-axis", "R_z"))
    allfe = sorted(set([r[2] for r in camp_rows]) | set(ymap) | set(zmap))
    for fe in allfe:
        c = [r for r in camp_rows if r[2] == fe]
        y = ymap.get(fe)
        z = zmap.get(fe)
        print("%-8d %-18s %8s %18s | %-8s %18s | %-8s %18s"
              % (fe,
                 (c[0][0] if c else "-"), "",
                 ("%.15f" % c[0][3]) if c else "-",
                 (y["label"] if y else "-"), ("%.15f" % y["R"]) if y else "-",
                 (z["label"] if z else "-"), ("%.15f" % z["R"]) if z else "-"))
    campR = [r[3] for r in camp_rows]
    print("\n  campaign diagonal (by free_e): " + mono_line("R", campR))
    print("  campaign n_e vs R: "
          + ", ".join("%d:%.15f" % (r[2], r[3]) for r in camp_rows))

    # ---------------------------------------------------------------- T5
    print("\n" + "=" * 78)
    print("(T5) VERDICT")
    print("=" * 78)

    def pattern(vals):
        d = np.diff(np.asarray(vals, dtype=float))
        if np.all(d > 0):
            return "monotone increasing"
        if np.all(d < 0):
            return "monotone decreasing"
        return "non-monotone (humps)"

    pY = pattern([e["R"] for e in yc]) if len(yc) > 1 else "n/a"
    pZ = pattern([e["R"] for e in zc]) if len(zc) > 1 else "n/a"
    pC = pattern(campR) if len(campR) > 1 else "n/a"
    pYs = pattern([e["R_regions"]["substrate"] for e in yc]) if len(yc) > 1 else "n/a"
    pZs = pattern([e["R_regions"]["substrate"] for e in zc]) if len(zc) > 1 else "n/a"
    pYa = pattern([e["R_regions"]["air"] for e in yc]) if len(yc) > 1 else "n/a"
    pZa = pattern([e["R_regions"]["air"] for e in zc]) if len(zc) > 1 else "n/a"
    excl = ([e["spec"] for e in yok if not e["converged"]]
            + [e["spec"] for e in zok if not e["converged"]])
    print("  convergence-gated: residual < 1e-6; excluded %d mesh(es): %s"
          % (len(excl), excl if excl else "none"))
    print("  R along the y axis alone (%d meshes, z fixed 34-17-17): %s"
          % (len(yc), pY))
    print("  R along the z axis alone (%d meshes, y fixed 56/43):    %s"
          % (len(zc), pZ))
    print("  R along the campaign diagonal:                          %s" % pC)
    print("  R_substrate along y axis: %s ; along z axis: %s" % (pYs, pZs))
    print("  R_air       along y axis: %s ; along z axis: %s" % (pYa, pZa))
    if pY.startswith("non-monotone") or pZ.startswith("non-monotone"):
        owner = []
        if pY.startswith("non-monotone"):
            owner.append("y-axis")
        if pZ.startswith("non-monotone"):
            owner.append("z-axis")
        verdict = ("the hump is NOT purely a diagonal artefact: R already "
                   "humps along the %s alone, so that axis owns (at least part "
                   "of) the hump and R is not a monotone function of any "
                   "single refinement parameter." % " and ".join(owner))
    elif pC.startswith("non-monotone"):
        verdict = ("each axis alone is monotone in R (%s along y, %s along z) "
                   "while the campaign diagonal is %s: the hump is a "
                   "diagonal/mixing artefact of refining five parameters at "
                   "once. R is therefore NOT a function of a single "
                   "refinement parameter h, and a 'convergence in free_e' "
                   "gate is mis-specified." % (pY, pZ, pC))
    else:
        verdict = ("no sweep humps and the diagonal does not hump in this "
                   "sample: no evidence of a diagonal artefact.")
    print("\n  " + verdict)

    payload = {
        "probe": "tools/host/sparse-probe/axis_sweep.py",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "reuses": "rung4_routeC_probe (load_context/analytic_reference/"
                  "build_problem/run_route_c/corr/field_scalars) + "
                  "routeC_mesh_probe.DenseShim(mode='auto'); recorder "
                  "identical to mode_overlap.py",
        "y_sweep_specs": MESHES_Y,
        "z_sweep_specs": MESHES_Z,
        "shared_corner": CORNER,
        "y_axis": [cache[s] for s in MESHES_Y],
        "z_axis": [cache[s] for s in MESHES_Z],
        "solve_order": order,
        "campaign_diagonal": [
            {"label": r[0], "spec": r[1], "free_e": r[2], "R": r[3]}
            for r in camp_rows],
        "residual_gate": 1e-6,
        "nonconverged_specs": excl,
        "n_converged": {"y": len(yc), "z": len(zc)},
        "patterns": {"R_y": pY, "R_z": pZ, "R_campaign": pC,
                     "R_substrate_y": pYs, "R_substrate_z": pZs,
                     "R_air_y": pYa, "R_air_z": pZa},
        "verdict": verdict,
        "wall_s_total": time.perf_counter() - t0,
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_JSON, "w") as fh:
        json.dump(payload, fh, indent=2, sort_keys=False, default=float)
    print("\nwrote %s" % OUT_JSON)
    print("solved %d distinct meshes (%d y + %d z, corner reused); %.1f s"
          % (len(order), len(MESHES_Y), len(MESHES_Z),
             time.perf_counter() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
