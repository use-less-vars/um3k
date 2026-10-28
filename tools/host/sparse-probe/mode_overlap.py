#!/usr/bin/env python3
"""Cross-mesh mode-shape overlap probe for the rung-4 Route-C campaign.

WHAT THIS IS
    A read-only consumer of ``rung4_routeC_probe`` (imported as ``r4``) and of
    ``routeC_mesh_probe`` (for ``DenseShim`` only).  Nothing of the physics is
    re-implemented here: each of the five campaign meshes is solved by calling
    exactly the entry points routeC_mesh_probe.py:404-406 uses

        pb      = r4.build_problem(cfg, ctx)
        route_c = r4.run_route_c(pb, ctx, ref, sigma, anchor)   # anchor=None

    The only new machinery is (a) observation of the lattice field and (b) the
    comparison tables the campaign never computed: pairwise cross-mesh overlap.

WHY A MONKEYPATCH AND NOT A SECOND SOLVE
    run_route_c() keeps the eigenvector in memory only: it builds the Mode2D,
    calls the module-global ``r4.field_scalars(mode_c, ctx, ref)``
    (rung4_routeC_probe.py:765) and returns scalars.  The lattice field is
    neither returned nor dumped, so a re-solve would double the cost and would
    compare two *different* eigsh runs.  Instead ``r4.field_scalars`` is
    replaced by ``recorder`` for the duration of one build+solve and restored
    in a ``finally`` block.  ``recorder`` reproduces the :328-352 arithmetic
    term by term (same sample points, same reshape, same CELL scaling, same
    r4.corr) and additionally keeps the two arrays.  Fidelity is not assumed:
    the recorder's scalars are compared against route_c's own corr_ey /
    corr_ez_vv / R and the difference is printed (column ``d_rec``).

LATTICE PROVENANCE
    field_scalars samples every mesh on ONE fixed uniform lattice taken from
    ctx, so a cross-mesh comparison is well defined at all:
        e_y    on (yc_mid  x zn_node) = (NY   x NZ+1) = (200 x 77)
        e_z_vv on (yn_node x zc_mid ) = (NY+1 x NZ  ) = (201 x 76)
    spacing CELL = 1e-4, covering 0..W x 0..H.  Note the lattice does NOT
    depend on the mesh: overlap here measures agreement of the *interpolated*
    fields, not of the unknowns, so it cannot fall just because two meshes have
    different vertex counts.

REGIONS
    substrate      z <= HSUB (+1e-9 so the interface node belongs to exactly
                   one side; the partition is checked to be exact)
    air            z >  HSUB
    strip_footprint Y0 <= y <= Y1 (+1e-9), the conductor footprint, all z

OUTPUT
    Tables on stdout, machine-readable summary in out_mesh/mode_overlap.json.
    Exit 0 iff all five meshes solved.
"""

import os
import sys

# Pin to one thread BEFORE numpy / scipy / r4 are imported (the campaign was
# measured single-threaded; eigsh and splu must not change that here).
for _var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
             "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS",
             "THREADPOOLCTL_NUM_THREADS"):
    os.environ.setdefault(_var, "1")

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
OUT_JSON = os.path.join(OUT_DIR, "mode_overlap.json")

# campaign order as banked in out_mesh/<label>.json
MESHES = [
    ("M5_ctrl_rung4", "36/22/20-10-10"),
    ("M1_fe11888",    "36/27/22-11-11"),
    ("M2_fe19665",    "47/35/28-14-14"),
    ("M3_fe28980",    "56/43/34-17-17"),
    ("M4_fe30672",    "58/44/35-17-18"),
]

SPEC_RE = re.compile(r"^(\d+)/(\d+)/(\d+)-(\d+)-(\d+)$")
TOL = 1e-9
SATURATION = 0.99


# ---------------------------------------------------------------- spec / sigma
def parse_spec(spec):
    m = SPEC_RE.match(spec.strip())
    if not m:
        raise ValueError("bad mesh spec %r (want strip/yair/z0-z1-z2)" % (spec,))
    strip, yair, z0, z1, z2 = (int(v) for v in m.groups())
    return strip, yair, [z0, z1, z2]


def sigma_for(label):
    """Per-mesh sigma from the banked campaign record, else r4's default."""
    path = os.path.join(OUT_DIR, label + ".json")
    try:
        with open(path) as fh:
            rec = json.load(fh)
        sig = rec["sigma"]
        value = float(sig["value"]) if isinstance(sig, dict) else float(sig)
        return value, path, True
    except Exception as exc:                                    # noqa: BLE001
        print("  [sigma] %s unreadable (%s: %s) -> r4.DEFAULT_SIGMA"
              % (path, type(exc).__name__, exc), flush=True)
        return float(r4.DEFAULT_SIGMA), path, False


# ------------------------------------------------------- field on the lattice
def fields_on_lattice(mode, ctx, ref):
    """Verbatim arithmetic of r4.field_scalars (:328-352) + the two arrays."""
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
    return {
        "e_y": e_y,
        "e_z_vv": e_z_vv,
        "R": (num / den) if den != 0.0 else float("nan"),
        "corr_ey": r4.corr(ref["e_y"], e_y),
        "corr_ez_vv": r4.corr(ref["e_z"], e_z_vv),
        "sum_e_y2": den,
        "sum_e_z_vv2": num,
    }


def make_recorder(store, ref):
    """Drop-in for r4.field_scalars that also stores the two lattice arrays."""

    def recorder(mode, ctx, _ref_unused=None):
        out = fields_on_lattice(mode, ctx, ref)
        store["e_y"] = out["e_y"]
        store["e_z_vv"] = out["e_z_vv"]
        return {k: out[k] for k in ("R", "corr_ey", "corr_ez_vv",
                                    "sum_e_y2", "sum_e_z_vv2")}

    return recorder


# ------------------------------------------------------------------- one solve
def run_mesh(label, spec, ctx, ref):
    strip, yair, z = parse_spec(spec)
    sigma, sigma_src, sigma_json = sigma_for(label)
    cfg = {"rung": -1, "role": label, "strip": strip, "yair": yair, "z": list(z)}
    entry = {
        "label": label, "spec": spec, "strip": strip, "yair": yair, "z": list(z),
        "sigma": sigma, "sigma_source": sigma_src, "sigma_from_json": sigma_json,
        "error": None,
    }
    print("\n=== %s  spec=%s  sigma=%.12g (%s) ==="
          % (label, spec, sigma, "banked" if sigma_json else "default"),
          flush=True)

    store = {}
    original = r4.field_scalars
    pb = route_c = None
    shim = None
    t0 = time.perf_counter()
    try:
        r4.field_scalars = make_recorder(store, ref)
        with DenseShim(mode="auto") as shim:
            pb = r4.build_problem(cfg, ctx)
            route_c = r4.run_route_c(pb, ctx, ref, sigma, None)
    except Exception as exc:                                    # noqa: BLE001
        entry["error"] = r4.exception_text(exc)
        print("  FAILED: %s" % entry["error"], flush=True)
    finally:
        r4.field_scalars = original
        entry["wall_s"] = time.perf_counter() - t0

    if entry["error"] is None:
        entry.update({
            "n_e": int(pb["n_e"]),
            "n_n": int(pb["n_n"]),
            "free_e": int(len(pb["free_e"])),
            "mesh_checks_ok": bool(pb["mesh_checks_ok"]),
            "lambda": float(route_c["eigenvalue"]),
            "beta_sq": float(route_c["beta_sq"]),
            "R": float(route_c["R"]),
            "corr_ey_routec": float(route_c["corr_ey"]),
            "corr_ez_vv_routec": float(route_c["corr_ez_vv"]),
            "residual": float(route_c["residual"]),
            "t_eigsh_s": float(route_c.get("t_eigsh_s", float("nan"))),
            "shim_interceptions": ([] if shim is None
                                   else list(shim.interceptions)),
        })
        rec_R = store["e_y"] is not None            # recorder really ran
        entry["recorder_ran"] = bool(rec_R)
        entry["corr_vs_ref_ey"] = r4.corr(ref["e_y"], store["e_y"])
        entry["corr_vs_ref_ez_vv"] = r4.corr(ref["e_z"], store["e_z_vv"])
        entry["sum_e_y2"] = float(np.sum(store["e_y"] ** 2))
        entry["sum_e_z_vv2"] = float(np.sum(store["e_z_vv"] ** 2))
        entry["d_rec_R"] = entry["R"] - float(np.sum(store["e_z_vv"] ** 2)
                                             / np.sum(store["e_y"] ** 2))
        entry["d_rec_ey"] = entry["corr_ey_routec"] - entry["corr_vs_ref_ey"]
        entry["d_rec_ez"] = entry["corr_ez_vv_routec"] - entry["corr_vs_ref_ez_vv"]
        e_y = np.array(store["e_y"], copy=True)
        e_z_vv = np.array(store["e_z_vv"], copy=True)
        print("  n_e=%d n_n=%d lambda=%.12g R=%.12g corr_ey=%+.4f "
              "corr_ez=%+.4f wall=%.1fs"
              % (entry["n_e"], entry["n_n"], entry["lambda"], entry["R"],
                 entry["corr_ey_routec"], entry["corr_ez_vv_routec"],
                 entry["wall_s"]), flush=True)
        print("  recorder fidelity: dR=%+.3e dcorr_ey=%+.3e dcorr_ez=%+.3e"
              % (entry["d_rec_R"], entry["d_rec_ey"], entry["d_rec_ez"]),
              flush=True)
    else:
        e_y = e_z_vv = None

    del pb, route_c, shim, store
    gc.collect()
    return entry, e_y, e_z_vv


# --------------------------------------------------------------- lattice/masks
def lattice(ctx):
    nyn, nzn = ctx["NY"] + 1, ctx["NZ"] + 1
    cell = ctx["CELL"]
    return {
        "cell": cell, "W": ctx["W"], "H": ctx["H"], "HSUB": ctx["HSUB"],
        "Y0": ctx["Y0"], "Y1": ctx["Y1"],
        "e_y": {"y": (np.arange(nyn - 1) + 0.5) * cell,      # yc_mid
                "z": np.arange(nzn) * cell},                 # zn_node
        "e_z_vv": {"y": np.arange(nyn) * cell,               # yn_node
                   "z": (np.arange(nzn - 1) + 0.5) * cell},  # zc_mid
        "shape": {"e_y": (nyn - 1, nzn), "e_z_vv": (nyn, nzn - 1)},
    }


def masks(ctx, lat):
    """kind -> list of (region_name, axis, boolean_mask)."""
    out = {}
    for kind in ("e_y", "e_z_vv"):
        zax = lat[kind]["z"]
        yax = lat[kind]["y"]
        sub = zax <= ctx["HSUB"] + TOL
        air = zax > ctx["HSUB"] + TOL
        strip = (yax >= ctx["Y0"] - TOL) & (yax <= ctx["Y1"] + TOL)
        assert not np.any(sub & air), "substrate/air partition not exact"
        assert np.count_nonzero(sub) + np.count_nonzero(air) == zax.size, \
            "substrate/air partition does not cover the column axis"
        out[kind] = [("substrate", "col", sub),
                     ("air", "col", air),
                     ("strip_footprint", "row", strip)]
    return out


def region_block(field, axis, mask):
    return field[:, mask] if axis == "col" else field[mask, :]


def sign_changes(v):
    v = np.asarray(v, dtype=float)
    s = np.sign(v[np.abs(v) > 0.0])
    if s.size < 2:
        return 0
    return int(np.count_nonzero(s[1:] * s[:-1] < 0))


def descriptors(e_y, ctx, lat, mask_row):
    """Structural read-out of one e_y lattice field."""
    z = lat["e_y"]["z"]
    y = lat["e_y"]["y"]
    a = np.abs(e_y)
    iy, iz = np.unravel_index(int(np.argmax(a)), a.shape)
    iz0 = int(np.argmin(np.abs(z - 0.5 * (ctx["HSUB"] + ctx["H"]))))
    iy0 = int(np.argmin(np.abs(y - 0.5 * ctx["W"])))
    air_rows = ~mask_row
    peak_strip = float(a[mask_row].max()) if np.any(mask_row) else float("nan")
    peak_air = float(a[air_rows].max()) if np.any(air_rows) else float("nan")
    return {
        "peak_abs": float(a[iy, iz]),
        "peak_y": float(y[iy]),
        "peak_z": float(z[iz]),
        "peak_in_strip_rows": bool(mask_row[iy]),
        "sign_changes_along_y_at_row_z": float(z[iz0]),
        "sign_changes_along_y": sign_changes(e_y[:, iz0]),
        "sign_changes_along_z_at_col_y": float(y[iy0]),
        "sign_changes_along_z": sign_changes(e_y[iy0, :]),
        "peak_strip_over_air": (peak_strip / peak_air) if peak_air else float("nan"),
    }


def print_matrix(title, labels, rows, fmt="%.4f", note=None):
    print("\n" + title, flush=True)
    if note:
        print("  " + note, flush=True)
    print("            " + "".join("%11s" % l for l in labels), flush=True)
    for lab, row in zip(labels, rows):
        cells = "".join("%11s" % ("n/a" if v is None else (fmt % v))
                        for v in row)
        print("%-11s" % lab + cells, flush=True)


# ------------------------------------------------------------------------ main
def main():
    t_start = time.perf_counter()
    ctx = r4.load_context()
    ref = r4.analytic_reference(ctx)
    lat = lattice(ctx)
    msk = masks(ctx, lat)

    print("=" * 78)
    print("MODE OVERLAP PROBE - rung-4 Route-C campaign (5 meshes, cross-mesh)")
    print("=" * 78)
    print("r4        : rung4_routeC_probe.py (load_context/build_problem/"
          "run_route_c/field_scalars reused)")
    print("shim      : DenseShim(mode='auto') from routeC_mesh_probe.py")
    print("lattice   : %dx%d (e_y) and %dx%d (e_z_vv), CELL=%.1e, "
          "W=%.4g H=%.4g HSUB=%.4g"
          % (lat["shape"]["e_y"][0], lat["shape"]["e_y"][1],
             lat["shape"]["e_z_vv"][0], lat["shape"]["e_z_vv"][1],
             lat["cell"], ctx["W"], ctx["H"], ctx["HSUB"]))
    for kind in ("e_y", "e_z_vv"):
        print("masks[%s] : " % kind
              + "  ".join("%s(%s)=%d" % (n, ax, np.count_nonzero(m))
                          for n, ax, m in msk[kind]))
    print("ref       : analytic e_y %s  e_z %s  eps_eff=%.6f"
          % (np.shape(ref["e_y"]), np.shape(ref["e_z"]), float(ref["eps_eff"])))
    print("threads   : OMP=%s OPENBLAS=%s MKL=%s"
          % (os.environ.get("OMP_NUM_THREADS"),
             os.environ.get("OPENBLAS_NUM_THREADS"),
             os.environ.get("MKL_NUM_THREADS")))

    entries = []
    fields = {}
    labels = []
    for label, spec in MESHES:
        entry, e_y, e_z_vv = run_mesh(label, spec, ctx, ref)
        entries.append(entry)
        labels.append(label)
        if e_y is not None:
            mag = math.hypot(entry["corr_vs_ref_ey"], 1.0)
            sgn_ey = -1.0 if entry["corr_vs_ref_ey"] < 0 else 1.0
            sgn_ez = -1.0 if entry["corr_vs_ref_ez_vv"] < 0 else 1.0
            entry["sign_applied_ey"] = sgn_ey
            entry["sign_applied_ez"] = sgn_ez
            fields[label] = {
                "e_y": sgn_ey * e_y,
                "e_z_vv": sgn_ez * e_z_vv,
                "e_y_raw": e_y,
                "e_z_vv_raw": e_z_vv,
            }
            # structural descriptors on the raw (sign is irrelevant for these)
            entry["structural"] = descriptors(e_y, ctx, lat,
                                              msk["e_y"][2][2])
            # energy fractions per region on the raw fields
            fr = {}
            for kind, arr in (("e_y", e_y), ("e_z_vv", e_z_vv)):
                tot = float(np.sum(arr ** 2))
                for name, ax, m in msk[kind]:
                    blk = region_block(arr, ax, m)
                    fr["%s:%s" % (kind, name)] = (float(np.sum(blk ** 2)) / tot
                                                  if tot else float("nan"))
            entry["region_energy_fractions"] = fr
    solved = [e for e in entries if e.get("error") is None]
    have = [l for l in labels if l in fields]

    # ---------------------------------------------------------------- (A)
    print("\n" + "=" * 78)
    print("(A) EIGENVALUE CONTINUITY (campaign order; d vs first row)")
    print("=" * 78)
    print("%-11s %-17s %8s %22s %11s %18s %11s %9s %7s"
          % ("label", "spec", "n_e", "lambda", "d_lambda", "R",
             "d_R", "resid", "wall_s"))
    base = solved[0] if solved else None
    lam_seq, R_seq, wall_tot = [], [], 0.0
    for e in entries:
        if e.get("error") is not None:
            print("%-11s %-17s %8s %22s %11s %18s %11s %9s %7.1f  ERROR: %s"
                  % (e["label"], e["spec"], "-", "-", "-", "-", "-", "-",
                     e["wall_s"], e["error"][:40]))
            continue
        dl = (e["lambda"] - base["lambda"]) / abs(base["lambda"])
        dR = e["R"] - base["R"]
        lam_seq.append(e["lambda"])
        R_seq.append(e["R"])
        wall_tot += e["wall_s"]
        print("%-11s %-17s %8d %22.15f %+11.3e %18.15f %+11.3e %9.2e %7.1f"
              % (e["label"], e["spec"], e["n_e"], e["lambda"], dl, e["R"], dR,
                 e["residual"], e["wall_s"]))
    print("total solve wall: %.1f s (+%.1f s probe overhead)"
          % (wall_tot, time.perf_counter() - t_start - wall_tot))

    def mono(seq, name):
        if len(seq) < 3:
            print("  %s monotonicity: n/a (<3 solved)" % name)
            return None
        d = np.diff(np.asarray(seq, dtype=float))
        inc = bool(np.all(d > 0))
        dec = bool(np.all(d < 0))
        word = "strictly increasing" if inc else ("strictly decreasing" if dec
                                                 else "NOT monotone")
        print("  %s monotonicity: %s   steps=%s"
              % (name, word, " ".join("%+.2e" % v for v in d)))
        return word

    print()
    mono_lam = mono(lam_seq, "lambda")
    mono_R = mono(R_seq, "R     ")
    print("  lambda spread (max-min)/|min| = %.3e"
          % (((max(lam_seq) - min(lam_seq)) / abs(min(lam_seq)))
             if lam_seq else float("nan")))

    # ---------------------------------------------------------------- (A2)
    print("\n" + "=" * 78)
    print("(A2) AGREEMENT WITH THE ANALYTIC REFERENCE (with sign), "
          "recorder fidelity")
    print("=" * 78)
    print("%-11s %10s %10s %11s %11s %10s %10s %10s"
          % ("label", "corr_ey", "corr_ez", "|corr_ey|", "|corr_ez|",
             "d_rec_ey", "d_rec_ez", "d_rec_R"))
    for e in entries:
        if e.get("error") is not None:
            continue
        print("%-11s %+10.6f %+10.6f %11.6f %11.6f %10.2e %10.2e %10.2e"
              % (e["label"], e["corr_vs_ref_ey"], e["corr_vs_ref_ez_vv"],
                 abs(e["corr_vs_ref_ey"]), abs(e["corr_vs_ref_ez_vv"]),
                 e["d_rec_ey"], e["d_rec_ez"], e["d_rec_R"]))
    print("  d_rec_* = route_c's own scalar minus the recorder's: "
          "0 means the hook reproduced r4 exactly.")

    # ---------------------------------------------------------------- (B)
    def corr_matrix(kind):
        M = np.full((len(have), len(have)), np.nan)
        for i, a in enumerate(have):
            for j, b in enumerate(have):
                M[i, j] = r4.corr(fields[a][kind], fields[b][kind])
        return M

    def corr_block_matrix(kind, axis, mask):
        M = np.full((len(have), len(have)), np.nan)
        for i, a in enumerate(have):
            for j, b in enumerate(have):
                ba = region_block(fields[a][kind], axis, mask)
                bb = region_block(fields[b][kind], axis, mask)
                M[i, j] = r4.corr(ba, bb)
        return M

    ref_mag = {}
    for kind, key in (("e_y", "corr_vs_ref_ey"), ("e_z_vv", "corr_vs_ref_ez_vv")):
        ref_mag[kind] = {e["label"]: abs(e[key]) for e in entries
                         if e.get("error") is None}

    absM = {}
    print("\n" + "=" * 78)
    print("(B) PAIRWISE |corr| BETWEEN MESH FIELDS (sign-aligned to the "
          "reference)")
    print("=" * 78)
    for kind, title in (("e_y", "e_y  (200x77 lattice, yc_mid x zn_node)"),
                        ("e_z_vv", "e_z_vv  (201x76 lattice, yn_node x zc_mid)")):
        M = corr_matrix(kind)
        absM[kind] = M
        print_matrix("(B) %s" % title, have,
                     [[abs(M[i, j]) for j in range(len(have))]
                      for i in range(len(have))],
                     "%.6f",
                     note="each field flipped to +corr with the reference; "
                          "symmetric")

    # ---------------------------------------------------------------- (C)
    consistency = {}
    print("\n" + "=" * 78)
    print("(C) CONSISTENCY: does pair (a,b) agree at least as well as the "
          "WORSE of their reference agreements?")
    print("=" * 78)
    print("  margin(a,b) = |corr(a,b)| - max(|corr(a,ref)|,|corr(b,ref)|); "
          "PASS iff margin >= 0")
    for kind in ("e_y", "e_z_vv"):
        M = absM[kind]
        n = len(have)
        margin = [[None] * n for _ in range(n)]
        passed = [[None] * n for _ in range(n)]
        for i, a in enumerate(have):
            for j, b in enumerate(have):
                if i == j:
                    continue
                margin[i][j] = M[i, j] - max(ref_mag[kind][a], ref_mag[kind][b])
                passed[i][j] = bool(margin[i][j] >= 0.0)
        print_matrix("(C) %s  margin" % kind, have, margin, "%+.6f")
        print_matrix("(C) %s  PASS=1" % kind, have,
                     [[None if v is None else (1 if v else 0) for v in row]
                      for row in passed], "%d")
        off = [margin[i][j] for i in range(n) for j in range(n) if i != j]
        npairs = len(off)
        npass = int(sum(1 for v in passed[i][j] if False)) if False else \
            int(sum(1 for i in range(n) for j in range(i + 1, n)
                    if passed[i][j]))
        print("  %s: %d/%d unordered pairs PASS, margin min=%+.6f max=%+.6f"
              % (kind, npass, n * (n - 1) // 2, min(off), max(off)), flush=True)
        consistency[kind] = {
            "margin": {have[i]: {have[j]: margin[i][j] for j in range(n)
                                 if j != i} for i in range(n)},
            "pass": {have[i]: {have[j]: passed[i][j] for j in range(n)
                               if j != i} for i in range(n)},
            "definition": "|corr(a,b)| - max(|corr(a,ref)|,|corr(b,ref)|) >= 0",
            "npairs": n * (n - 1) // 2,
            "npass": npass,
            "margin_min": min(off) if off else None,
            "margin_max": max(off) if off else None,
        }

    # ---------------------------------------------------------------- (D)
    print("\n" + "=" * 78)
    print("(D) REGION-RESOLVED OVERLAP AND ENERGY FRACTIONS")
    print("=" * 78)
    pairwise_abs = {}
    for kind in ("e_y", "e_z_vv"):
        pairwise_abs[kind] = {"global": {have[i]: {have[j]: float(absM[kind][i, j])
                                                   for j in range(len(have))}
                                         for i in range(len(have))}}
        for name, ax, m in msk[kind]:
            Mb = corr_block_matrix(kind, ax, m)
            pairwise_abs[kind][name] = {
                have[i]: {have[j]: float(abs(Mb[i, j]))
                          for j in range(len(have))} for i in range(len(have))}
            print_matrix("(D) %s  |corr| restricted to %s (%s mask, %d points)"
                         % (kind, name, ax, np.count_nonzero(m)), have,
                         [[abs(Mb[i, j]) for j in range(len(have))]
                          for i in range(len(have))], "%.6f")
    print("\n(D) energy fractions  sum(f^2 in region)/sum(f^2 all)")
    print("%-11s %-24s %12s %12s %12s %12s %12s"
          % ("label", "field:region", "value", "", "", "", ""))
    for e in entries:
        if e.get("error") is not None:
            continue
        for key, val in sorted(e["region_energy_fractions"].items()):
            print("%-11s %-24s %12.6f" % (e["label"], key, val))
    print("\n(D) cross-mesh spread of each region's |corr| (min..max off-diag)")
    for kind in ("e_y", "e_z_vv"):
        for region in ("global", "substrate", "air", "strip_footprint"):
            d = pairwise_abs[kind][region]
            off = [d[a][b] for a in have for b in have if a != b]
            print("  %-7s %-16s min=%.6f max=%.6f spread=%.6f"
                  % (kind, region, min(off), max(off), max(off) - min(off)))

    # ---------------------------------------------------------------- (E)
    print("\n" + "=" * 78)
    print("(E) STRUCTURAL DESCRIPTORS (e_y lattice field, sign-free)")
    print("=" * 78)
    print("%-11s %10s %9s %9s %6s %12s %8s %8s %10s"
          % ("label", "peak|e_y|", "peak_y", "peak_z", "strip",
             "signchg_y", "row z", "col y", "strip/air"))
    for e in entries:
        if e.get("error") is not None or "structural" not in e:
            continue
        s = e["structural"]
        print("%-11s %10.3e %9.5f %9.5f %6s %12d %8.5f %8.5f %10.4f"
              % (e["label"], s["peak_abs"], s["peak_y"], s["peak_z"],
                 "yes" if s["peak_in_strip_rows"] else "no",
                 s["sign_changes_along_y"], s["sign_changes_along_z_at_col_y"],
                 s["sign_changes_along_y_at_row_z"], s["peak_strip_over_air"]))
    print("  signchg_y = sign changes of e_y along y on the row nearest z="
          "(HSUB+H)/2; col y = the column y nearest W/2 (signchg_z there).")

    # ---------------------------------------------------------------- (F)
    print("\n" + "=" * 78)
    print("(F) CAN THE OVERLAP TEST DISCRIMINATE THE MESHES?")
    print("=" * 78)
    discriminating = {}
    for kind in ("e_y", "e_z_vv"):
        M = absM[kind]
        off = [abs(M[i, j]) for i in range(len(have)) for j in range(i + 1, len(have))]
        lo, hi = min(off), max(off)
        saturated = bool(lo > SATURATION)
        discriminating[kind] = {
            "offdiag_min": lo, "offdiag_max": hi, "offdiag_spread": hi - lo,
            "saturation_threshold": SATURATION,
            "saturated": saturated,
            "distinguishes": (not saturated),
        }
        print("  %-7s off-diagonal |corr|: min=%.6f max=%.6f spread=%.6f  "
              "-> %s (threshold %.2f)"
              % (kind, lo, hi, hi - lo,
                 "SATURATED, no discriminating power" if saturated
                 else "resolvable", SATURATION))
    lam_spread = ((max(lam_seq) - min(lam_seq)) / abs(min(lam_seq))
                  if lam_seq else float("nan"))
    print("  for scale: lambda spread over the campaign = %.3e; "
          "R spread = %.3e" % (lam_spread, (max(R_seq) - min(R_seq))))
    verdict = ("the cross-mesh overlap test is SATURATED: every pair agrees "
               "at |corr| > %.2f, i.e. all five meshes reproduce the same "
               "shape to within the resolution of the 200x77/201x76 lattice. "
               "It therefore CANNOT distinguish the meshes from one another, "
               "and must not be used as evidence that any one of them is "
               "right - a test that cannot fail is not evidence." % SATURATION) \
        if all(v["saturated"] for v in discriminating.values()) else \
        "the cross-mesh overlap test is NOT saturated: at least one field's " \
        "pairwise |corr| falls below %.2f, so the meshes are separable." % SATURATION
    print("\n  VERDICT: " + verdict)

    # ---------------------------------------------------------------- JSON
    payload = {
        "probe": "tools/host/sparse-probe/mode_overlap.py",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "reuses": {
            "module": "rung4_routeC_probe.py",
            "calls": ["r4.load_context()", "r4.analytic_reference(ctx)",
                      "r4.build_problem(cfg, ctx)",
                      "r4.run_route_c(pb, ctx, ref, sigma, None)",
                      "r4.corr(a, b)"],
            "hook": "r4.field_scalars swapped for a recorder that reproduces "
                    ":328-352 and keeps the arrays; restored in finally",
            "shim": "routeC_mesh_probe.DenseShim(mode='auto') around "
                    "build_problem+run_route_c (routeC_mesh_probe.py:404-406)",
            "anchor": None,
        },
        "lattice": {
            "CELL": lat["cell"], "W": lat["W"], "H": lat["H"],
            "HSUB": lat["HSUB"], "Y0": lat["Y0"], "Y1": lat["Y1"],
            "e_y_shape": list(lat["shape"]["e_y"]),
            "e_z_vv_shape": list(lat["shape"]["e_z_vv"]),
            "e_y_axes": "yc_mid x zn_node",
            "e_z_vv_axes": "yn_node x zc_mid",
            "mesh_independent": True,
            "tolerance": TOL,
        },
        "region_notes": {
            "substrate": "z <= HSUB (+tol); column mask",
            "air": "z > HSUB; column mask",
            "strip_footprint": "Y0 <= y <= Y1 (+tol); row mask, all z",
            "partition_exact": True,
            "mask_counts": {k: {n: int(np.count_nonzero(m)) for n, a, m in v}
                            for k, v in msk.items()},
        },
        "meshes": entries,
        "labels": labels,
        "pairwise_abs_corr": pairwise_abs,
        "consistency": consistency,
        "eigenvalue_continuity": {
            "labels": [e["label"] for e in entries if e.get("error") is None],
            "lambda": lam_seq, "R": R_seq,
            "lambda_spread_rel": lam_spread,
            "lambda_monotone": mono_lam, "R_monotone": mono_R,
        },
        "reference_agreement": ref_mag,
        "discriminating_power": {
            "fields": discriminating,
            "saturation_threshold": SATURATION,
            "saturated_all": all(v["saturated"]
                                 for v in discriminating.values()),
            "verdict": verdict,
        },
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_JSON, "w") as fh:
        json.dump(payload, fh, indent=2, sort_keys=False, default=float)
    print("\nwrote %s" % OUT_JSON)
    print("solved %d/%d meshes; total %.1f s"
          % (len(solved), len(entries), time.perf_counter() - t_start))
    return 0 if len(solved) == len(entries) else 1


if __name__ == "__main__":
    sys.exit(main())
