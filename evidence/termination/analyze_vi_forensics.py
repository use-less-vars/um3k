#!/usr/bin/env python3
"""Forensic read of the complex wave impedance Z = v/i carried by the fields.

No reference impedance is assumed anywhere in the measurement: v and i are the
line integrals of the simulated fields that the termination artefacts already
store, and Z = v/i is whatever ratio those numbers give.  Everything printed
below is either read out of the artefacts or computed from them; anything the
artefacts do not contain is reported as the literal ABSENT rather than guessed.

Read-only: opens five JSON artefacts, runs no FDTD, writes nothing.

Run from the repo root:
    python3 evidence/termination/analyze_vi_forensics.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EVIDENCE_DIR = REPO_ROOT / "evidence" / "termination"

# p50 .. p54: the same run, five different extraction planes.
FILES = tuple("build_A_50ohm_p5%d_plane.json" % k for k in (0, 1, 2, 3, 4))

F_HZ = 5827786408.327286
C_M_S = 299792458.0
DX_M = 4.0e-4

EPS_EFF_LIST = (1.0, 2.0, 3.0)
GAMMA_LIST = (0.245, 0.326)
Z0_LIST = (39.5, 47.305815, 50.0, 55.0)

# Two x values closer than this are treated as the same plane, and two spacings
# closer than this as the same spacing.
SPACING_TOL = 1.0e-9

ABSENT = "ABSENT"


# --------------------------------------------------------------------------
# artefact reading
# --------------------------------------------------------------------------
def _cplx(rec):
    """Complex from a {"re": ..., "im": ...} record, or None."""
    if not isinstance(rec, dict):
        return None
    if "re" not in rec or "im" not in rec:
        return None
    return complex(float(rec["re"]), float(rec["im"]))


def _list_of(rec, key):
    value = rec.get(key) if isinstance(rec, dict) else None
    return list(value) if isinstance(value, list) else []


def load_columns(path: Path):
    """Every (column, x, v, i) the artefact carries.  None if unreadable."""
    if not path.exists():
        return None
    doc = json.loads(path.read_text(encoding="utf-8"))

    station = {}
    s11 = doc.get("s11")
    if isinstance(s11, dict) and isinstance(s11.get("station_phasors"), dict):
        station = s11["station_phasors"]

    xs = _list_of(station, "x_m")
    v_re = _list_of(station, "v_re")
    v_im = _list_of(station, "v_im")
    i_re = _list_of(station, "i_re")
    i_im = _list_of(station, "i_im")
    selected = _list_of(station, "fit_selected")
    js = _list_of(station, "js")

    columns = []
    count = min(len(xs), len(v_re), len(v_im), len(i_re), len(i_im))
    for k in range(count):
        v = complex(float(v_re[k]), float(v_im[k]))
        i = complex(float(i_re[k]), float(i_im[k]))
        columns.append(
            {
                "col": "st%d" % k,
                "x_m": float(xs[k]),
                "v": v,
                "i": i,
                "js": int(js[k]) if k < len(js) else ABSENT,
                "selected": bool(selected[k]) if k < len(selected) else None,
            }
        )

    plane = doc.get("s21_plane")
    if isinstance(plane, dict):
        v = _cplx(plane.get("v"))
        i = _cplx(plane.get("i"))
        x = plane.get("x_m")
        if v is not None and i is not None and x is not None:
            columns.append(
                {
                    "col": "s21plane",
                    "x_m": float(x),
                    "v": v,
                    "i": i,
                    "js": ABSENT,
                    "selected": None,
                }
            )

    extract = ABSENT
    geom = doc.get("geometry")
    if isinstance(geom, dict) and geom.get("s21_plane_index") is not None:
        extract = geom.get("s21_plane_index")

    return {"columns": columns, "extract_col": extract, "doc": doc}


def with_impedance(columns):
    """Add z = v/i and argz in degrees; drop (and flag) zero-current rows."""
    out = []
    skipped = []
    for col in columns:
        if col["i"] == 0:
            skipped.append(col["col"])
            continue
        z = col["v"] / col["i"]
        row = dict(col)
        row["z"] = z
        row["argz"] = float(np.degrees(np.angle(z)))
        row["zmag"] = float(abs(z))
        out.append(row)
    return out, skipped


# --------------------------------------------------------------------------
# span selection
# --------------------------------------------------------------------------
def uniform_spans(columns):
    """Contiguous equal-spacing runs over increasing x, longest first."""
    cols = sorted(columns, key=lambda c: c["x_m"])
    spans = []
    for i in range(len(cols) - 1):
        step = cols[i + 1]["x_m"] - cols[i]["x_m"]
        if step <= SPACING_TOL:
            continue
        j = i + 1
        while (
            j + 1 < len(cols)
            and abs((cols[j + 1]["x_m"] - cols[j]["x_m"]) - step) <= SPACING_TOL
        ):
            j += 1
        spans.append(cols[i : j + 1])
    spans.sort(key=lambda s: (-len(s), s[0]["x_m"]))
    return spans


def wrapped_increments_deg(values):
    """Successive differences of a degree array, wrapped into (-180, 180]."""
    values = np.asarray(values, dtype=float)
    if values.size < 2:
        return np.zeros(0)
    return np.degrees(np.angle(np.exp(1j * np.radians(np.diff(values)))))


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="analyze_vi_forensics.py",
        description=(
            "Read v and i out of the termination artefacts and report Z = v/i, "
            "its phase increment and the reflection bracket it implies. "
            "Read-only; no FDTD, no reference impedance assumed."
        ),
    )
    ap.add_argument(
        "--evidence-dir",
        default=str(DEFAULT_EVIDENCE_DIR),
        help="directory holding the build_A_50ohm_p5*_plane.json artefacts",
    )
    args = ap.parse_args(argv)
    ev_dir = Path(args.evidence_dir)

    runs = {}
    for name in FILES:
        loaded = load_columns(ev_dir / name)
        if loaded is None:
            runs[name] = None
            continue
        columns, skipped = with_impedance(loaded["columns"])
        runs[name] = {
            "columns": columns,
            "skipped": skipped,
            "extract_col": loaded["extract_col"],
        }

    # ---------------------------------------------------------------- (a)
    print("== (a) Z = v/i for every stored (file, column) pair ==")
    print(
        "%-38s %-9s %9s %12s %11s %12s"
        % ("file", "col", "x_mm", "|Z|_ohm", "argZ_deg", "dArgZ_deg")
    )
    for name in FILES:
        run = runs[name]
        if run is None:
            print("%-38s %s" % (name, ABSENT + " (file not found)"))
            continue
        print("-" * 95)
        print("%s" % name)
        prev_arg = None
        for col in sorted(run["columns"], key=lambda c: c["x_m"]):
            if prev_arg is None:
                incr = ABSENT
            else:
                incr = "%.6f" % wrapped_increments_deg([prev_arg, col["argz"]])[0]
            print(
                "%-38s %-9s %9.4f %12.6f %11.6f %12s"
                % (
                    "",
                    col["col"],
                    col["x_m"] * 1000.0,
                    col["zmag"],
                    col["argz"],
                    incr,
                )
            )
            prev_arg = col["argz"]
        if run["skipped"]:
            print("   zero-current columns skipped: %s"
                  % ", ".join(run["skipped"]))
        else:
            print("   v/i pairs available: %d (no column skipped for i = 0)"
                  % len(run["columns"]))

    # ---------------------------------------------------------------- (b)
    print()
    print("== (b) x-range available, and the span used ==")
    station_pairs = {}
    for name in FILES:
        run = runs[name]
        if run is None:
            print("  %-38s %s" % (name, ABSENT))
            continue
        stations = [c for c in run["columns"] if c["col"].startswith("st")]
        plane = [c for c in run["columns"] if c["col"] == "s21plane"]
        print("  %s" % name)
        print("    extraction column (geometry.s21_plane_index) : %s"
              % (run["extract_col"],))
        if plane:
            print("    s21_plane.x_m                              : %.6f  (%.4f mm)"
                  % (plane[0]["x_m"], plane[0]["x_m"] * 1000.0))
        else:
            print("    s21_plane.x_m                              : %s" % ABSENT)
        if stations:
            xs = ", ".join("%.4f" % (c["x_m"] * 1000.0) for c in stations)
            print("    nine station x (mm)                        : %s" % xs)
            print("    station columns with a v/i pair            : %d"
                  % len(stations))
            sel = [c["col"] for c in stations if c["selected"] is False]
            print("    station columns dropped by the impedance fit: %s"
                  % (", ".join(sel) if sel else "none"))
        else:
            print("    nine station x (mm)                        : %s" % ABSENT)
        print("    s21_plane column with a v/i pair           : %s"
              % ("YES" if plane else ABSENT))
        station_pairs[name] = stations

    # Are the station phasors the same run in every file?
    ref = None
    same = True
    for name in FILES:
        cols = station_pairs.get(name) or []
        sig = [(c["x_m"], c["v"], c["i"]) for c in cols]
        if ref is None:
            ref = sig
        elif sig != ref:
            same = False
    print("  station phasors identical across the five files : %s"
          % ("YES (single run, station extraction is plane-independent)"
             if same else "NO"))
    plane_xs = []
    for name in FILES:
        run = runs[name]
        if run is None:
            continue
        for col in run["columns"]:
            if col["col"] == "s21plane":
                plane_xs.append("%s=%.4f mm" % (name.split("_")[3],
                                                 col["x_m"] * 1000.0))
    print("  s21_plane columns (one per file): %s"
          % (", ".join(plane_xs) if plane_xs else ABSENT))

    chosen_name = None
    chosen = None
    for name in FILES:
        run = runs[name]
        if run is None:
            continue
        # Only the station grid is a span: the s21_plane column of a given file
        # sits on a different grid and is reported in (a) but never merged in.
        station_only = [c for c in run["columns"] if c["col"].startswith("st")]
        spans = uniform_spans(station_only)
        if not spans:
            continue
        if chosen is None or len(spans[0]) > len(chosen):
            chosen_name = name
            chosen = spans[0]

    if chosen is None:
        print("  CHOSEN SPAN: %s - no column with a v/i pair in any file" % ABSENT)
    else:
        step = chosen[1]["x_m"] - chosen[0]["x_m"] if len(chosen) > 1 else 0.0
        print("  CHOSEN SPAN (longest single-run, equal-spacing span):")
        print("    file          : %s" % chosen_name)
        print("    columns       : %s"
              % ", ".join(c["col"] for c in chosen))
        print("    x range (mm)  : %.4f .. %.4f"
              % (chosen[0]["x_m"] * 1000.0, chosen[-1]["x_m"] * 1000.0))
        print("    span spacing  : %.6f mm" % (step * 1000.0))
        print("    phase increments available: %d" % (len(chosen) - 1))
        print("    note: st8 sits on the load column and the impedance fit drops"
              " it; a load-free sensitivity block follows section (c).")

    span_cols = chosen if chosen is not None else []
    span_argz = np.array([c["argz"] for c in span_cols], dtype=float)
    increments = wrapped_increments_deg(span_argz)

    # ---------------------------------------------------------------- (c)
    print()
    print("== (c) phase rotation of arg(Z) along the chosen span ==")
    if increments.size == 0:
        print("  %s - no successive pair in the chosen span" % ABSENT)
    else:
        for k, inc in enumerate(increments):
            print("    arg(Z) increment %d (%s -> %s): %+10.6f deg"
                  % (k, span_cols[k]["col"], span_cols[k + 1]["col"], inc))
        mean_incr = float(increments.mean())
        spread = float(increments.max() - increments.min())
        print("    mean increment      : %+10.6f deg   (|mean| = %.6f deg)"
              % (mean_incr, abs(mean_incr)))
        print("    increment spread    : %10.6f deg   (max - min)" % spread)
    print("    reference values for eps_eff, beta = 2*pi*f/c*sqrt(eps_eff),"
          " dx = %.1e m:" % DX_M)
    for eps in EPS_EFF_LIST:
        beta = 2.0 * np.pi * F_HZ / C_M_S * float(np.sqrt(eps))
        two_beta_dx = float(np.degrees(2.0 * beta * DX_M))
        beta_dx = float(np.degrees(beta * DX_M))
        print("      eps_eff = %.1f :  2*beta*dx = %8.6f deg   beta*dx = %8.6f deg"
              % (eps, two_beta_dx, beta_dx))
    if increments.size:
        print("    closeness of |mean increment| to each reference"
              " (single number = absolute difference, then ratio):")
        for eps in EPS_EFF_LIST:
            beta = 2.0 * np.pi * F_HZ / C_M_S * float(np.sqrt(eps))
            for label, ref in (
                ("2*beta*dx", float(np.degrees(2.0 * beta * DX_M))),
                ("beta*dx", float(np.degrees(beta * DX_M))),
            ):
                diff = abs(abs(mean_incr) - ref)
                ratio = abs(mean_incr) / ref if ref else float("nan")
                print("      eps_eff = %.1f %-9s : |diff| = %8.6f deg   ratio = %8.6f"
                      % (eps, label, diff, ratio))

    if len(span_cols) > 1:
        no_load = [c for c in span_cols if c.get("selected") is not False]
        if len(no_load) > 1 and len(no_load) != len(span_cols):
            sens = wrapped_increments_deg([c["argz"] for c in no_load])
            print("    SENSITIVITY (load column dropped, %d columns, %d increments):"
                  " mean %+10.6f deg, spread %10.6f deg, |Z| max/min %.6f"
                  % (
                      len(no_load),
                      len(no_load) - 1,
                      float(sens.mean()),
                      float(sens.max() - sens.min()),
                      max(c["zmag"] for c in no_load)
                      / min(c["zmag"] for c in no_load),
                  ))

    # ---------------------------------------------------------------- (d)
    print()
    print("== (d) |Z| brackets on the chosen span, and the ripple a reflection"
          " would need ==")
    if not span_cols:
        print("  %s" % ABSENT)
        zmag_mean = zmag_min = zmag_max = ripple = None
    else:
        zmags = np.array([c["zmag"] for c in span_cols], dtype=float)
        zmag_mean = float(zmags.mean())
        zmag_min = float(zmags.min())
        zmag_max = float(zmags.max())
        ripple = zmag_max / zmag_min if zmag_min else float("inf")
        print("    |Z| mean        : %12.6f ohm" % zmag_mean)
        print("    |Z| min         : %12.6f ohm   (%s at %.4f mm)"
              % (zmag_min, span_cols[int(np.argmin(zmags))]["col"],
                 span_cols[int(np.argmin(zmags))]["x_m"] * 1000.0))
        print("    |Z| max         : %12.6f ohm   (%s at %.4f mm)"
              % (zmag_max, span_cols[int(np.argmax(zmags))]["col"],
                 span_cols[int(np.argmax(zmags))]["x_m"] * 1000.0))
        print("    |Z| max/min     : %12.6f" % ripple)
        print("    prediction: on a line of impedance Z0 with reflection |Gamma|,"
              " |Z| oscillates between")
        print("      Z0*(1-|Gamma|)/(1+|Gamma|) and Z0*(1+|Gamma|)/(1-|Gamma|),"
              " a peak-to-peak ratio of ((1+|Gamma|)/(1-|Gamma|))^2.")
        for g in GAMMA_LIST:
            pred = ((1.0 + g) / (1.0 - g)) ** 2
            verdict = "YES" if ripple >= pred else "NO"
            print("      |Gamma| = %.3f -> predicted |Z| max/min = %9.6f ;"
                  " measured %9.6f ; ripple large enough to host it: %s"
                  % (g, pred, ripple, verdict))
        print("    measured ripple vs predicted: %s"
              % ("measured ripple EXCEEDS the |Gamma| = 0.245 requirement and is"
                 " just below the |Gamma| = 0.326 requirement"
                 if ripple >= ((1.0 + 0.245) / (1.0 - 0.245)) ** 2
                 else "measured ripple is BELOW the |Gamma| = 0.245 requirement"))

    # ---------------------------------------------------------------- (e)
    print()
    print("== (e) Gamma implied by the measured Z, per assumed Z0 ==")
    print("    |Gamma| = |(Z - Z0)/(Z + Z0)|, arg(Gamma) in degrees;"
          " the spread across Z0 is the part of the answer that is a choice"
          " of reference, not a measurement.")
    if not span_cols:
        print("  %s" % ABSENT)
    else:
        for z0 in Z0_LIST:
            print("  Z0 = %9.6f ohm" % z0)
            print("    %-9s %9s %12s %14s"
                  % ("col", "x_mm", "|Gamma|", "argGamma_deg"))
            mags = []
            for col in span_cols:
                g = (col["z"] - z0) / (col["z"] + z0)
                mags.append(abs(g))
                print("    %-9s %9.4f %12.6f %14.6f"
                      % (col["col"], col["x_m"] * 1000.0, abs(g),
                         float(np.degrees(np.angle(g)))))
            gm = float(np.mean(mags))
            print("    mean |Gamma| over the span : %12.6f" % gm)
            print("    spread of |Gamma|          : %12.6f"
                  % (float(np.max(mags)) - float(np.min(mags))))

    # ---------------------------------------------------------------- (f)
    print()
    mean_arg_z = float(np.mean(np.abs(span_argz))) if span_argz.size else None
    spread_val = float(increments.max() - increments.min()) if increments.size else None
    print("== (f) bracket test inputs and labelled result block ==")
    print("  C1 tests: |Z| max/min < 1.10 (measured %s), mean |arg(Z)| < 10 deg"
          " (measured %s), increment spread < 3 deg (measured %s)"
          % (
              "%.6f" % ripple if ripple is not None else ABSENT,
              "%.6f" % mean_arg_z if mean_arg_z is not None else ABSENT,
              "%.6f" % spread_val if spread_val is not None else ABSENT,
          ))
    print("  C2 tests: |Z| max/min > 1.5 (measured %s) OR increment spread > 10 deg"
          " (measured %s)"
          % (
              "%.6f" % ripple if ripple is not None else ABSENT,
              "%.6f" % spread_val if spread_val is not None else ABSENT,
          ))
    if chosen is None:
        print("SPAN_FILE: %s" % ABSENT)
    else:
        print("SPAN_FILE: %s" % (ev_dir / chosen_name))
    print("SPAN_COLUMNS: %s"
          % (", ".join(c["col"] for c in span_cols) if span_cols else ABSENT))
    print("N_PHASE_INCREMENT: %d" % int(increments.size))
    print("ZMAG_MEAN_OHM: %s" % ("%.6f" % zmag_mean if zmag_mean is not None else ABSENT))
    print("ZMAG_MIN_OHM: %s" % ("%.6f" % zmag_min if zmag_min is not None else ABSENT))
    print("ZMAG_MAX_OHM: %s" % ("%.6f" % zmag_max if zmag_max is not None else ABSENT))
    print("ZMAG_RIPPLE_RATIO: %s" % ("%.6f" % ripple if ripple is not None else ABSENT))
    print("PRED_RIPPLE_GAMMA0245: %.6f" % (((1.0 + 0.245) / (1.0 - 0.245)) ** 2))
    print("PRED_RIPPLE_GAMMA0326: %.6f" % (((1.0 + 0.326) / (1.0 - 0.326)) ** 2))
    if increments.size:
        print("ARGZ_MEAN_INCR_DEG: %+.6f" % float(increments.mean()))
        print("ARGZ_INCR_SPREAD_DEG: %.6f"
              % float(increments.max() - increments.min()))
    else:
        print("ARGZ_MEAN_INCR_DEG: %s" % ABSENT)
        print("ARGZ_INCR_SPREAD_DEG: %s" % ABSENT)
    for eps in EPS_EFF_LIST:
        beta = 2.0 * np.pi * F_HZ / C_M_S * float(np.sqrt(eps))
        print("ARGZ_INCR_2BETADX_EPS%d: %.6f"
              % (int(eps), float(np.degrees(2.0 * beta * DX_M))))

    c1 = (
        ripple is not None
        and mean_arg_z is not None
        and spread_val is not None
        and ripple < 1.10
        and mean_arg_z < 10.0
        and spread_val < 3.0
    )
    c2 = (
        (ripple is not None and ripple > 1.5)
        or (spread_val is not None and spread_val > 10.0)
    )
    print("BRACKET_C1_MATCHED: %s" % ("YES" if c1 else "NO"))
    print("BRACKET_C2_REFLECTION: %s" % ("YES" if c2 else "NO"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
