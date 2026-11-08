#!/usr/bin/env python3
"""Read-only split tests on the stored FDTD cut-plane records.

Two hypotheses about the plane-split reflection anomaly (|b|/|f| falling by
about 2x as the extraction plane moves from column 51 to column 54 while
|s11| = 0.325863 is plane-independent):

  A) a half-step leapfrog time offset between the gap voltage v and the
     trace current i makes |b|/|f| plane-dependent;
  B) the single split impedance zc is wrong, and some real zc in 20..80 ohm
     collapses the spread of |b|/|f| across the four extraction planes.

The split reproduced is the engine's own, emfit/studies.py:1294
(_wave_amplitude) with sign = +1 / -1 and gamma_split = 0:

    f = 0.5 * (v + zc * i) * exp(+gamma * x)      forward  (studies.py:1351)
    b = 0.5 * (v - zc * i) * exp(-gamma * x)      backward (studies.py:1375)
    gamma_plane = b / f                           (studies.py:3718)

Reads only evidence/termination/build_A_50ohm_p5{1,2,3,4}_plane.json.  No
FDTD, no writes, no arguments.  ASCII only.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
TERM = ROOT / "evidence" / "termination"
COLUMNS = (51, 52, 53, 54)
C_LIGHT = 299792458.0
F_HZ_FALLBACK = 2.4e9
CELL_M_FALLBACK = 0.0004
ZC_SWEEP = tuple(20.0 + 0.5 * k for k in range(121))


def pair(node):
    """A stored complex phasor {"re": ..., "im": ...} as a Python complex."""
    return complex(float(node["re"]), float(node["im"]))


def load_column(col):
    """The stored cut-plane record for one extraction column."""
    path = TERM / ("build_A_50ohm_p%d_plane.json" % col)
    with path.open() as handle:
        rec = json.load(handle)
    plane = rec["s21_plane"]
    fit = rec["run"]["station_fit"]
    geo = rec.get("geometry") or {}
    return {
        "col": col,
        "path": path,
        "v": pair(plane["v"]),
        "i": pair(plane["i"]),
        "a_stored": pair(plane["a"]),
        "b_stored": pair(plane["b"]),
        "x_m": float(plane["x_m"]),
        "gamma_plane_stored": float(rec["gamma_plane"]["abs"]),
        "zc": complex(float(fit["z0_re"]), float(fit["z0_im"])),
        "f_hz": geo.get("f_hz"),
        "dt_s": geo.get("dt_s"),
        "cell_m": geo.get("cell_m"),
        "reference": rec["run"].get("reference"),
    }


def split(v, i, zc):
    """The engine's two travelling-wave amplitudes on one plane."""
    forward = 0.5 * (v + zc * i)
    backward = 0.5 * (v - zc * i)
    return forward, backward


def ratio(v, i, zc):
    forward, backward = split(v, i, zc)
    return abs(backward) / abs(forward)


def spread(values):
    lo = min(values)
    hi = max(values)
    if lo <= 0.0:
        return float("inf")
    return hi / lo


def main():
    parser = argparse.ArgumentParser(
        description="Read-only split tests on the stored cut-plane records.")
    parser.parse_args()

    recs = [load_column(col) for col in COLUMNS]

    print("=" * 72)
    print("SOURCE INVENTORY")
    print("=" * 72)
    have = [r["col"] for r in recs
            if (TERM / ("build_A_50ohm_p%d_ghostwave_fields.npz"
                        % r["col"])).is_file()]
    absent = [c for c in COLUMNS if c not in have]
    print("npz field dumps present for column(s): %s"
          % (", ".join(str(c) for c in have) if have else "none"))
    print("npz field dumps ABSENT for column(s): %s"
          % (", ".join(str(c) for c in absent) if absent else "none"))
    print("v, i taken from the s21_plane phasors stored in each plane JSON")
    print("(the same record the engine split consumed; emfit/studies.py:3407-")
    print("3408: v_cut = cut_spec[0], i_cut = -cut_spec[1])")
    print("zc = run.station_fit.z0 of the same record (emfit/studies.py:3664;")
    print("run.reference is %r on every column, so studies.py:3666-3707 takes"
          % recs[0]["reference"])
    print("the no-reference branch with gamma_split = 0)")
    print("")

    print("=" * 72)
    print("(a) STORED SPLIT, zc = station_fit.z0, gamma_split = 0")
    print("=" * 72)
    base = []
    repro = 0.0
    for r in recs:
        forward, backward = split(r["v"], r["i"], r["zc"])
        # the same split the engine ran, to prove v/i and zc are the right ones
        repro = max(repro, abs(forward - r["a_stored"]),
                    abs(backward - r["b_stored"]))
        rat = abs(backward) / abs(forward)
        base.append(rat)
        print("col %d  |f| = %.6f  |b| = %.6f  |b|/|f| = %.6f  "
              "zc = (%.6f%+.6fj)  x = %.6f m"
              % (r["col"], abs(forward), abs(backward), rat,
                 r["zc"].real, r["zc"].imag, r["x_m"]))
    print("stored |gamma_plane| per column: %s"
          % ", ".join("%.6f" % r["gamma_plane_stored"] for r in recs))
    print("SPLIT_REPRO_CHECK: max |stored - recomputed| over a, b = %.6e"
          % repro)
    spread_uncorrected = spread(base)
    print("spread over columns %s: %.6f"
          % (", ".join(str(c) for c in COLUMNS), spread_uncorrected))
    print("")

    print("=" * 72)
    print("(b) HALF-STEP CORRECTION OF THE CURRENT-LIKE PHASOR")
    print("=" * 72)
    f_hz = recs[0]["f_hz"]
    if f_hz is None:
        f_hz = F_HZ_FALLBACK
        print("f_hz: FALLBACK %.6e Hz (no geometry.f_hz in the record)"
              % f_hz)
    else:
        print("f_hz: %.6f Hz  source: geometry.f_hz of %s"
              % (float(f_hz), recs[0]["path"].name))
        print("      provenance: written by evidence/termination/run_build_A.py"
              ":772 as float(res.geometry['f']); no f_hz literal exists in that"
              " script")
    dt = recs[0]["dt_s"]
    if dt is None:
        cell = CELL_M_FALLBACK
        dt = 0.99 * cell / (C_LIGHT * np.sqrt(3.0))
        print("dt: FALLBACK %.12e s = 0.99 * cell_m / (c * sqrt(3)), "
              "cell_m = %.6e m (labelled fallback)"
              % (dt, cell))
    else:
        print("dt: %.12e s  source: geometry.dt_s of %s"
              % (float(dt), recs[0]["path"].name))
        print("      provenance: written by evidence/termination/run_build_A.py"
              ":1066/:1843 as geom.get('dt'); no dt or Courant literal exists in"
              " that script")
    omega = 2.0 * np.pi * float(f_hz)
    half = 0.5 * omega * float(dt)
    print("omega = 2*pi*f_hz = %.6f rad/s, half-step phase = %.6f rad "
          "(%.6f deg)" % (omega, half, np.degrees(half)))
    print("A_plus : i -> i * exp(+j*omega*dt/2); A_minus : i -> i * "
          "exp(-j*omega*dt/2)")
    print("")
    print("col   A_plus |b|/|f|      A_minus |b|/|f|")
    plus = []
    minus = []
    for r in recs:
        i_plus = r["i"] * complex(np.exp(1j * half))
        i_minus = r["i"] * complex(np.exp(-1j * half))
        plus.append(ratio(r["v"], i_plus, r["zc"]))
        minus.append(ratio(r["v"], i_minus, r["zc"]))
        print("%3d   %18.6f   %18.6f" % (r["col"], plus[-1], minus[-1]))
    spread_plus = spread(plus)
    spread_minus = spread(minus)
    print("spread A_plus  = %.6f  (min %.6f, max %.6f)"
          % (spread_plus, min(plus), max(plus)))
    print("spread A_minus = %.6f  (min %.6f, max %.6f)"
          % (spread_minus, min(minus), max(minus)))
    print("")

    print("=" * 72)
    print("(c) ZC SWEEP 20.0 .. 80.0 ohm, step 0.5 (121 values)")
    print("=" * 72)
    if spread_plus <= spread_minus:
        sign_name = "A_plus"
        corrected = plus
    else:
        sign_name = "A_minus"
        corrected = minus
    print("sign used: %s (smaller half-step spread of the two)" % sign_name)
    sweep = []
    for zc_value in ZC_SWEEP:
        values = [ratio(r["v"], r["i"] * complex(np.exp(
            1j * half if sign_name == "A_plus" else -1j * half)), zc_value)
            for r in recs]
        sweep.append((spread(values), zc_value))
    ranked = sorted(sweep, key=lambda item: item[0])
    print("ten smallest spreads:")
    for sp, zc_value in ranked[:10]:
        print("  zc = %6.1f ohm  spread = %.6f" % (zc_value, sp))
    best_spread, best_zc = ranked[0]
    print("BEST: spread = %.6f at zc = %.1f ohm" % (best_spread, best_zc))
    at_50 = [sp for sp, zc_value in sweep if abs(zc_value - 50.0) < 1e-9][0]
    print("spread at zc = 50.0 ohm: %.6f" % at_50)
    print("")

    print("=" * 72)
    print("SUMMARY")
    print("=" * 72)
    print("COLUMNS_USED: %s" % ", ".join(str(c) for c in COLUMNS))
    print("SPREAD_UNCORRECTED: %.6f" % spread_uncorrected)
    print("SPREAD_A_PLUS: %.6f" % spread_plus)
    print("SPREAD_A_MINUS: %.6f" % spread_minus)
    print("SPREAD_BEST_ZC: %.6f at ZC_BEST: %s" % (best_spread, _fmt(best_zc)))
    return 0


def _fmt(value):
    return ("%.1f" % value) if abs(value - round(value, 1)) < 1e-9 else repr(value)


if __name__ == "__main__":
    sys.exit(main())
