"""Post-run analysis for the h-refinement dispatch (evidence/h_refine/PREREG.md).

Reads whichever rung JSONs exist, recomputes the graded reference at each rung's OWN tone,
prints the pre-registered readings, a 3-point order fit when three rungs exist, and the
sizing-gate price for the next rung.  Writes nothing.
"""
import json, math, os, sys

sys.path.insert(0, "tools")
sys.path.insert(0, os.getcwd())
from d585_modal import hammerstad_beta

FROZEN_REF = 384.7489672644
DELTA_MIN = 0.0734
THRESH = 3 * DELTA_MIN
RUNGS = [("A", 0.4, "evidence/h_refine/h040.json"),
         ("B", 0.26667, "evidence/h_refine/h0267.json"),
         ("C", 0.2, "evidence/h_refine/h020.json")]

rows = []
for tag, h, path in RUNGS:
    if not os.path.exists(path):
        rows.append((tag, h, None)); continue
    d = json.load(open(path))
    r = d["rungs"][0]
    ref = hammerstad_beta(r["f_hz"])["beta"]
    rows.append((tag, h, dict(
        raw=r, ref=ref,
        dF=100.0 * (r["beta_fdtd"] / ref - 1.0),
        dE=100.0 * (r["beta_eig"] / ref - 1.0),
        gap=100.0 * (r["beta_eig"] / r["beta_fdtd"] - 1.0),
        ok=abs(ref / FROZEN_REF - 1) < 1e-6)))

for tag, h, x in rows:
    if x is None:
        print("%-2s h=%-8s NOT RUN" % (tag, h)); continue
    r = x["raw"]
    print("%-2s h=%-8s grid=%-12s cells=%-8d ref=%.6f  fdtd=%.7f (%+.5f pp)  eig=%.7f (%+.5f pp)"
          "  gap=%.5f %%  npml=%d nsteps=%d rss=%.1f MB  fdtd=%.1f s eig=%.1f s  meshed_w=%.4f mm  ref_ok=%s"
          % (tag, h, str(tuple(r["grid"])), r["n_cells"], x["ref"], r["beta_fdtd"], x["dF"],
             r["beta_eig"], x["dE"], x["gap"], r["npml"], r["nsteps"], r["peak_rss_mb"],
             r["wall_fdtd_s"], r["t_eigs_s"], r["strip_width_mm"], x["ok"]))

have = [(h, x) for (t, h, x) in rows if x is not None]

def fit(key):
    """least-squares d = d0 + C*h^p, p scanned."""
    best = None
    for i in range(1, 40001):
        p = 0.1 + i * 5.9 / 40000.0
        A = [(1.0, hh ** p) for hh, _ in have]
        y = [x[key] for _, x in have]
        s11 = sum(a * a for a, _ in A)
        s12 = sum(a * b for a, b in A)
        s22 = sum(b * b for _, b in A)
        t1 = sum(a * yy for (a, _), yy in zip(A, y))
        t2 = sum(b * yy for (_, b), yy in zip(A, y))
        det = s11 * s22 - s12 * s12
        if abs(det) < 1e-30:
            continue
        d0 = (t1 * s22 - t2 * s12) / det
        C = (s11 * t2 - s12 * t1) / det
        res = sum((yy - d0 - C * b) ** 2 for (_, b), yy in zip(A, y))
        if best is None or res < best[0]:
            best = (res, p, d0, C)
    return best

if len(have) == 3:
    for key, nm in (("dF", "FDTD"), ("dE", "EIG")):
        res, p, d0, C = fit(key)
        print("3-point fit (%s): d(h) = %.5f + %.5f * h^%.4f   SSR=%.3e  rms=%.5f pp"
              % (nm, d0, C, p, res, math.sqrt(res / 3.0)))
else:
    print("3-point fit: not available (%d rung(s) measured)" % len(have))

if len(have) >= 2:
    fa, la = have[0][1]["dF"], have[-1][1]["dF"]
    fe, le = have[0][1]["dE"], have[-1][1]["dE"]
    monoF = all(have[i + 1][1]["dF"] <= have[i][1]["dF"] for i in range(len(have) - 1))
    monoE = all(have[i + 1][1]["dE"] <= have[i][1]["dE"] for i in range(len(have) - 1))
    print("fall FDTD: %+.5f -> %+.5f pp  = %.5f pp   monotone=%s" % (fa, la, fa - la, monoF))
    print("fall EIG : %+.5f -> %+.5f pp  = %.5f pp   monotone=%s" % (fe, le, fe - le, monoE))
    print("threshold %.5f pp (= 3 x Delta_min %.4f)" % (THRESH, DELTA_MIN))
    h0, h1 = have[0][0], have[-1][0]
    print("end-to-end h ratio %.4f ; apparent pure-power order p_FDTD=%.3f p_EIG=%.3f"
          % (h0 / h1, math.log(fa / la) / math.log(h0 / h1), math.log(fe / le) / math.log(h0 / h1)))

if have:
    h_last, x_last = have[-1]
    r = x_last["raw"]
    for tag, h in (("B", 0.26667), ("C", 0.2)):
        if any(abs(h - hh) < 1e-9 for hh, _ in have):
            continue
        hc = 1.6 / round(1.6 / h)               # grid_for silently re-derives cell = 1.6/n_sub
        s = (h_last / hc) ** 3                   # cells at fixed physical domain
        print("gate price %s: h_eff=%.5f cells~%.0f (x%.2f) fdtd~%.0f s (x%.2f, incl. nsteps) rss~%.0f MB"
              % (tag, hc, r["n_cells"] * s, s, r["wall_fdtd_s"] * s * (h_last / hc),
                 h_last / hc, r["peak_rss_mb"] * s))
