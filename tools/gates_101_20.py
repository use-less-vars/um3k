#!/usr/bin/env python3
"""gates_101_20 -- station-flux ratio sensitivity (Part A) and two gates T1/T2.

RUNNABLE TODAY (no solve)
------------------------
``--part-a`` writes the E-vs-H sensitivity curve of the station flux ratio
``R = F_phys[8] / F_phys[0]`` on the *cached* capture
``/workspace/.scratch/tol/logs/TOLFLUX_planes.npz``.  It reproduces P0, P8 and
R(1) and asserts agreement with the record in
``/workspace/.scratch/tol/TOLFLUX.tables.txt`` (sections 1 and 3) to 1e-12
relative, then perturbs the captured phasors and re-reads the ratio.

WRITTEN BUT GATED (needs a solve)
---------------------------------
``T1_stab`` and ``T2_agree`` are implemented here in full, but neither can run
without a *fresh* plane capture: they consume blocks that only a solve
produces.  The CLI therefore refuses them unless
``--i-understand-this-needs-a-solve`` is passed, and prints the estimated cost
with the refusal.  Nothing in this module solves anything by itself.

Why the split: everything in Part A is arithmetic on an existing record, so a
typo costs a second; a T1/T2 run costs a full solve, so it must not be
reachable by an accidental flag or an ``import``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

WORKSPACE = "/workspace"
if WORKSPACE not in sys.path:
    sys.path.insert(0, WORKSPACE)

from emfit.plane_phasor import flux_from_phasors  # noqa: E402

#: The cached capture Part A reads (never written to).
PLANES_NPZ = os.path.join(WORKSPACE, ".scratch", "tol", "logs",
                          "TOLFLUX_planes.npz")

#: The four captured phasor blocks, in the order ``flux_from_phasors`` wants.
BLOCK_KEYS = ("plane_Ey", "plane_Ez", "plane_Hy", "plane_Hz")

#: Reference values from ``.scratch/tol/TOLFLUX.tables.txt`` sections 1 and 3.
#: ``F_phys = 4 * f_raw / N**2`` with ``N = plane_n_samples`` (see the
#: ``flux_from_phasors`` docstring: got from ``N**2/4`` on a product of two
#: raw DFT sums).
REF_F_PHYS = (
    24090.371792902824,
    23990.54523353718,
    23877.00685094769,
    23756.31116482864,
    23643.097246971545,
    23551.363576350715,
    23482.83920226148,
    23421.060767968174,
    23336.851094665908,
)
REF_P0 = 24090.371792902824
REF_P8 = 23336.851094665908
REF_R = 0.9687210847256866

#: Reproduction tolerance demanded of Part A.  The reproduction is bit-exact
#: (measured rel dev 0.0 on all eleven reference numbers), so 1e-12 is a
#: detection floor, not a modelling tolerance.
REPRO_RTOL = 1e-12

#: Detection threshold used for the "smallest detectable break" question in
#: Part A.  Given by the task; a *question parameter*, not a gate.
DETECT_THRESHOLD = 1e-5

# ---------------------------------------------------------------------------
# T1_TOL -- tolerance in force for T1_stab (drop-one-station stability of the
# propagation constant beta).
#
# STATUS: **measured, not derived.**  No closed-form stability bound for beta
# exists on this geometry, so what follows is a transcription of what the
# beta-null harness measured, not an error budget integrated from first
# principles.  Source: ``/workspace/.scratch/logs/s10118_beta_null.py``,
# report ``/workspace/.scratch/logs/s10118_beta_null_report.txt``.
#
#   measured input                                      value
#   --------------------------------------------------  ---------------------
#   repeat x2, same process (ana, beta 309.9818636706751)  0.0   (bitwise,
#                                                            beta_a == beta_b)
#   repeat x2, same process (mix, beta 326.9107654423116)  0.0   (bitwise)
#   BLAS threads 1 vs 4 (ana only)                          8.13e-11
#   float32 round-trip of the input fields (ana / mix)      1.10e-10 / 9.87e-11
#   H-destagger toggle                                      0.0  (scalar phase;
#                                                           beta invariant)
#   8-station window 0..7 (station 8 dropped)               0.0700 %
#   8-station window 1..8 (station 0 dropped)               0.2338 %
#   1-wave span over those two windows 0.164 %; 2-wave 0.335 %
#   all 21 contiguous windows, analytic basis, span         2.02 %
#   3-station windows at the ends                           1.93 % / 0.890 %
#   mixed basis: 8-station windows 3.06 % / 2.99 %,
#     span over those 6.24 %, all-window span               31.2 %
#   fit beta vs eigenvalue beta (T2's subject, not this gate)  4.52 %
#
# 0.005 sits ~2x above the worst single-station drop measured on the analytic
# basis (0.2338 %) and ~6x below the mixed-basis 8-station figure (3.06 %) --
# which is exactly why basis='mixed' is refused outright below instead of
# being gated at this tolerance.
# ---------------------------------------------------------------------------
T1_TOL = 0.005

# ---------------------------------------------------------------------------
# T2_TOL -- tolerance in force for T2_agree (two extractions of one field).
#
# STATUS: **measured, not derived.**  As above: transcribed from the beta-null
# harness, not integrated from a model.
#
#   null floor that T2 must simply not trip:
#     repeat x2                            0.0        (bitwise identical)
#     BLAS threads 1 vs 4                  8.13e-11
#     float32 round-trip of input fields   1.10e-10 (ana) / 9.87e-11 (mix)
#     H-destagger toggle                   0.0        (scalar phase)
#   NOT a null -- the real disagreement T2 exists to see:
#     fit beta vs eigenvalue beta on the same field   4.52 %
#
# 1e-3 is ~7 orders above the measured null floor and ~45x *below* the measured
# 4.52 % fit/eigenvalue disagreement.  So a T2 run comparing the fit route with
# the eigenvalue route FAILS on today's record by a factor ~45.  Both numbers
# are recorded as measured; no tolerance recommendation is made here.
# ---------------------------------------------------------------------------
T2_TOL = 1e-3
# WITHDRAWN as a proposed gate value by decisions.md 101.20 (c.2): 1e-3 sits ~45x
# below the 4.52 % fit-vs-eigenvalue disagreement T2 has to clear, so T2 cannot pass
# at this tolerance.  Retained only as the value (c) pre-registered; no replacement
# tolerance is proposed there.  T1_TOL (0.005) is unaffected and still stands.

# ---------------------------------------------------------------------------
# Cost text printed with every refusal of T1/T2.
# ---------------------------------------------------------------------------
COST_TEXT = """\
estimated cost of a T1/T2 run, from the cached record:
  * one board_run_pw solve of the s10118 station-flux geometry:
    wall_s = 4210.484 s = 70.2 min
    (measured, /workspace/.scratch/tol/TOLFLUX.tables.txt line 58)
  * phasor/flux extraction and the beta fit on the result: < 1 s each
  * no cached capture exists at a default path: the solve has to be run first
    and its .npz handed in with --capture
"""

REFUSAL = """\
REFUSED: T1/T2 are written but deliberately unrunnable by accident.
They need a fresh plane capture, which means running a solve.
If that is really what you want, add --i-understand-this-needs-a-solve
(and --capture <npz>):

    python3 tools/gates_101_20.py --t1 --capture CAP.npz \\
        --i-understand-this-needs-a-solve
"""


# ---------------------------------------------------------------------------
# Part A -- sensitivity of the station flux ratio, on the cached capture
# ---------------------------------------------------------------------------
def _phys_flux(plane_Ey, plane_Ez, plane_Hy, plane_Hz, n_samples):
    """``4 * flux_from_phasors(...) / N**2``, per station [W]."""
    raw = flux_from_phasors(plane_Ey, plane_Ez, plane_Hy, plane_Hz)
    return 4.0 * np.asarray(raw, dtype=float) / float(int(n_samples)) ** 2


def _ratio_with_break(blocks, n_samples, b=0.0, which="E", stations=None):
    """``R = F[8] / F[0]`` after scaling one pair of blocks by ``(1+b)``.

    ``which='E'`` scales ``plane_Ey`` and ``plane_Ez``, ``which='H'`` scales
    ``plane_Hy`` and ``plane_Hz``; the other pair is untouched.  ``stations``
    selects which station planes the break applies to (``None`` = all).
    """
    arrs = {k: np.array(blocks[k], dtype=complex, copy=True) for k in BLOCK_KEYS}
    if b != 0.0:
        keys = ("plane_Ey", "plane_Ez") if which == "E" else ("plane_Hy", "plane_Hz")
        sel = slice(None) if stations is None else np.asarray(stations, dtype=int)
        for k in keys:
            arrs[k][sel] *= (1.0 + b)
    flux = _phys_flux(arrs["plane_Ey"], arrs["plane_Ez"],
                      arrs["plane_Hy"], arrs["plane_Hz"], n_samples)
    return float(flux[-1] / flux[0]), flux


def _fit_through_origin(b, y):
    """Least-squares slope through the origin, plus the residuals."""
    b = np.asarray(b, dtype=float)
    y = np.asarray(y, dtype=float)
    slope = float(np.dot(b, y) / np.dot(b, b))
    return slope, y - slope * b


def _report_detectability(w, label, slope, threshold=DETECT_THRESHOLD, b_test=0.01):
    """Smallest ``|b|`` visible at ``threshold``, and the response at ``b_test``."""
    if slope == 0.0:
        w(f"  {label}: slope is 0.0 *exactly* -> |R(b)/R(1)-1| = 0.0 for every b,\n"
          f"    so no break of any size is detectable at {threshold:g}: the response\n"
          f"    at a {100 * b_test:.0f}% break is 0.0, i.e. a factor of 0, not a factor\n"
          f"    below 1 -- the ratio is blind to this break by construction.\n")
        return
    b_min = threshold / abs(slope)
    resp = abs(slope) * b_test
    w(f"  {label}: slope {slope!r} (response per unit relative break)\n"
      f"    arithmetic: |R(b)/R(1)-1| = |slope|*|b|; smallest detectable\n"
      f"      |b| = {threshold:g}/{abs(slope)!r} = {b_min!r} = {100 * b_min:.4g} %\n"
      f"    response at b={b_test}: {abs(slope)!r}*{b_test} = {resp!r},\n"
      f"      i.e. {resp / threshold:.4g}x the {threshold:g} threshold -> "
      f"{'CAUGHT' if resp >= threshold else 'NOT caught'}\n")


def part_a(planes_npz=PLANES_NPZ, out=sys.stdout):
    """The E-vs-H sensitivity curve, plus the reproduction check.  No solve."""
    w = out.write
    d = np.load(planes_npz, allow_pickle=True)
    blocks = {k: d[k] for k in BLOCK_KEYS}
    n_samples = int(np.asarray(d["plane_n_samples"]).ravel()[0])
    n_st = blocks["plane_Ey"].shape[0]

    w("== PART A: E-vs-H sensitivity of the station flux ratio R = F[8]/F[0] ==\n")
    w(f"capture {planes_npz}\n")
    w(f"N={n_samples} ({n_samples ** 2 // 4} = N**2/4) n_stations={n_st}\n")

    flux = _phys_flux(blocks["plane_Ey"], blocks["plane_Ez"],
                      blocks["plane_Hy"], blocks["plane_Hz"], n_samples)
    P0, P8 = float(flux[0]), float(flux[-1])
    R1 = P8 / P0
    w(f"F_phys = {[float(v) for v in flux]}\n")
    w(f"P0 = {P0!r}\nP8 = {P8!r}\nR(1) = {R1!r}\n")

    worst = 0.0
    for i, ref in enumerate(REF_F_PHYS):
        worst = max(worst, abs(float(flux[i]) / ref - 1.0))
    for name, got, ref in (("P0", P0, REF_P0), ("P8", P8, REF_P8),
                           ("R(1)", R1, REF_R)):
        worst = max(worst, abs(got / ref - 1.0))
    w(f"reproduction: worst relative deviation vs the record = {worst!r} "
      f"(demanded < {REPRO_RTOL:g})\n")
    if not worst < REPRO_RTOL:
        raise AssertionError(
            f"Part A does not reproduce the record: worst relative deviation "
            f"{worst!r} >= {REPRO_RTOL:g}")
    w("reproduction OK: bit-exact on P0, P8, R(1) and all nine stations\n")

    B = (0.01, 0.05, 0.10, 0.25, 0.50, 1.00, -0.01, -0.10, -0.50)

    # -- (E-only break, every station) ------------------------------------
    w("\n-- E-only break: plane_Ey and plane_Ez x (1+b), H untouched, "
      "all 9 stations --\n")
    w(f"{'b':>8} | {'R(b)':>22} | {'|R(b)/R(1)-1|':>16}\n")
    R_E = []
    for b in B:
        R, _ = _ratio_with_break(blocks, n_samples, b, "E")
        R_E.append(R)
        w(f"{b:>8.2f} | {R!r:>22} | {abs(R / R1 - 1.0):>16.6e}\n")

    y_E = np.array([R / R1 - 1.0 for R in R_E])
    order = np.argsort(np.asarray(B))
    ys = y_E[order]
    mono = bool(np.all(np.diff(ys) > 0.0) or np.all(np.diff(ys) < 0.0))
    m_E, resid_E = _fit_through_origin(B, y_E)
    w(f"\n(i)   monotone in b: {mono}; max|resid| to the slope-through-origin "
      f"line = {float(np.max(np.abs(resid_E)))!r} "
      f"(= {100 * float(np.max(np.abs(resid_E))):.3g} % of R(1))\n")
    w(f"(ii)  slope = {m_E!r} response per unit relative E break\n")
    _report_detectability(w, "(iii) E-only", m_E)

    # -- companion: the break at a single station (not scale-protected) ----
    # The ratio is a ratio of two products, so a *global* scale break cancels
    # in it exactly; the numbers above are that cancellation, not a small
    # sensitivity.  The same break applied at one station only is what a
    # station-wise calibration error would look like, and is reported beside
    # it so the two are not confused.
    w("\n-- companion (not requested): same E-only break at ONE station, "
      "where the ratio is not scale-protected --\n")
    for j in (0, n_st - 1):
        w(f"   break at station {j} only:\n")
        w(f"{'b':>8} | {'R(b)':>22} | {'|R(b)/R(1)-1|':>16}\n")
        R_j = []
        for b in B:
            R, _ = _ratio_with_break(blocks, n_samples, b, "E", stations=[j])
            R_j.append(R)
            w(f"{b:>8.2f} | {R!r:>22} | {abs(R / R1 - 1.0):>16.6e}\n")
        y_j = np.array([R / R1 - 1.0 for R in R_j])
        m_j, resid_j = _fit_through_origin(B, y_j)
        o = np.argsort(np.asarray(B))
        ysj = y_j[o]
        w(f"   monotone: {bool(np.all(np.diff(ysj) > 0.0) or np.all(np.diff(ysj) < 0.0))}"
          f"; max|resid| = {float(np.max(np.abs(resid_j)))!r}\n")
        _report_detectability(w, f"   E-only at station {j}", m_j)

    # -- (iv) H-only break, the E/H symmetry check ------------------------
    w("\n-- (iv) H-only break: plane_Hy and plane_Hz x (1+b), E untouched --\n")
    w(f"{'b':>8} | {'R(b)':>22} | {'|R(b)/R(1)-1|':>16}\n")
    for b in (0.01, 0.10, 1.00):
        R, _ = _ratio_with_break(blocks, n_samples, b, "H")
        w(f"{b:>8.2f} | {R!r:>22} | {abs(R / R1 - 1.0):>16.6e}\n")
        Rh, _ = _ratio_with_break(blocks, n_samples, b, "E")
        w(f"   E-vs-H at b={b}: |R_E - R_H| = {abs(Rh - R)!r}\n")
    return {"P0": P0, "P8": P8, "R1": R1, "worst_repro_dev": worst,
            "slope_E_global": m_E}


# ---------------------------------------------------------------------------
# Gated gates
# ---------------------------------------------------------------------------
def _load_capture(capture):
    """Accept an ``.npz`` path, an open ``NpzFile``, or a mapping."""
    if isinstance(capture, str):
        return np.load(capture, allow_pickle=True)
    return capture


def _capture_planes(capture):
    """``(blocks, station_x)`` out of a capture; the x key has two spellings."""
    d = _load_capture(capture)
    blocks = {k: d[k] for k in BLOCK_KEYS}
    x = None
    for key in ("plane_station_x", "station_x"):
        try:
            x = d[key]
            break
        except KeyError:
            continue
    if x is None:
        raise ValueError(
            "capture carries neither 'plane_station_x' nor 'station_x': "
            "beta needs the station positions in metres")
    return blocks, np.asarray(x, dtype=float).ravel()


def _beta_from_phase_slope(blocks, x, mask=None):
    """beta from the station-to-station phase slope of the transverse E field.

    The station phasor is taken over the whole transverse plane against
    station 0 as reference, ``z_i = sum_plane conj(E_y[0]) E_y[i]``, so a global
    field level cancels and only the propagation phase accumulates; ``beta`` is
    the magnitude of the least-squares slope of ``unwrap(angle(z))`` against
    ``x``.  The reference stays station 0 even when station 0 is masked out of
    the fit, because the reference phase does not enter the slope.
    """
    ey = np.asarray(blocks["plane_Ey"], dtype=complex)
    z = np.sum(np.conj(ey[0])[None, :, :] * ey, axis=(-2, -1))
    phi = np.unwrap(np.angle(z))
    xx = np.asarray(x, dtype=float)
    if mask is not None:
        phi = phi[mask]
        xx = xx[mask]
    if xx.size < 2:
        raise ValueError(f"a beta fit needs 2 or more stations, got {xx.size}")
    return abs(float(np.polyfit(xx, phi, 1)[0])), phi


def T1_stab(capture, *, drop_station="nearest", basis="analytic", tol=T1_TOL):
    """Drop-one-station stability of beta, on one capture.

    ``beta_a`` is fitted on every station, ``beta_b`` on the same capture with
    ``drop_station`` removed, and the gate is
    ``|beta_b - beta_a| / |beta_a| <= tol``.  ``tol`` defaults to the
    module-level :data:`T1_TOL` (0.005), which records the *measured* window
    sensitivity of beta -- see the comment above it; the value in force is
    returned as ``tolerance_in_force`` so a caller-supplied ``tol`` can never be
    confused with the default.

    ``drop_station='nearest'`` resolves to the station nearest the port.
    For this geometry that is station 0: ``x_port = 0.0087 m`` while the
    stations begin at ``0.0104 m`` and step ``0.0012 m``, so
    ``|0.0104 - 0.0087| = 0.0017 < |0.0116 - 0.0087| = 0.0029``.

    ``basis='mixed'`` raises :class:`NotImplementedError`: the mixed
    (``solve_modes_mixed``) basis is window-sensitive at ~3 % on the two
    8-station windows (3.06 % / 2.99 %, span 6.24 %), six times ``T1_TOL``, so a
    drop-one-station gate on it would be measuring the basis, not the field.
    """
    if basis == "mixed":
        raise NotImplementedError(
            "T1_stab(basis='mixed'): basis='mixed' is not gated. The mixed "
            "(solve_modes_mixed) basis is window-sensitive at ~3 % on the two "
            "8-station windows (measured 3.06 % / 2.99 %, span 6.24 %, 31.2 % "
            "over all 21 windows) -- six times the T1 tolerance of "
            f"{tol!r} -- so a drop-one-station gate on it would measure the "
            "basis, not the field. Use basis='analytic'.")
    if basis != "analytic":
        raise ValueError(f"unknown basis {basis!r}; only 'analytic' is gated "
                         f"('mixed' raises NotImplementedError)")

    blocks, x = _capture_planes(capture)
    d = _load_capture(capture)
    n = x.size
    try:
        x_port = float(np.asarray(d["x_port"]).ravel()[0])
    except (KeyError, IndexError):
        x_port = float("nan")

    if drop_station is None:
        drop = None
    elif isinstance(drop_station, str):
        if drop_station == "nearest":
            drop = int(np.argmin(np.abs(x - x_port)))
        else:
            raise ValueError(
                f"drop_station={drop_station!r}: expected 'nearest', None or "
                f"an int")
    else:
        drop = int(drop_station)
        if not 0 <= drop < n:
            raise ValueError(f"drop_station {drop} outside 0..{n - 1}")

    beta_a, _ = _beta_from_phase_slope(blocks, x)
    if drop is None:
        beta_b = beta_a
    else:
        mask = np.ones(n, dtype=bool)
        mask[drop] = False
        beta_b, _ = _beta_from_phase_slope(blocks, x, mask=mask)
    shift = abs(beta_b - beta_a) / abs(beta_a) if beta_a else float("inf")
    return {
        "gate": "T1_stab",
        "beta_a": beta_a,
        "beta_b": beta_b,
        "relative_shift": shift,
        "pass": bool(shift <= float(tol)),
        "tolerance_in_force": float(tol),
        "basis": basis,
        "drop_station": drop,
        "x_port": x_port,
        "n_stations": int(n),
        "note": ("beta_a = all stations, beta_b = same capture minus the "
                 "dropped station; shift = |beta_b - beta_a| / |beta_a|"),
    }


def T2_agree(capture, *, tol=T2_TOL):
    """Two extractions of the same field must agree: gate on their rel diff.

    Route 1 is the station phase slope (:func:`_beta_from_phase_slope`); route 2
    is the eigenvalue beta the capture carries in ``beta`` (the modal route).
    The gate is ``|beta_fit - beta_eig| / |beta_eig| <= tol`` with ``tol``
    defaulting to the module-level :data:`T2_TOL` (1e-3) -- a *measured* floor,
    see the comment above it: 1e-3 is seven orders above the measured null
    floor and ~45x below the measured 4.52 % fit/eigenvalue disagreement, so
    this comparison fails on today's record.  ``tolerance_in_force`` reports the
    number actually used.

    Raises:
        ValueError: If the capture carries no ``beta`` array (nothing to agree
            with), or the stations/geometry are unusable.
    """
    blocks, x = _capture_planes(capture)
    d = _load_capture(capture)
    try:
        eig = np.asarray(d["beta"], dtype=float).ravel()
    except KeyError:
        eig = np.empty(0)
    if eig.size == 0:
        raise ValueError(
            "T2_agree: the capture carries no 'beta' array, so there is no "
            "second (eigenvalue) extraction of this field to agree with; the "
            "TOLFLUX_planes.npz record has beta of shape (0,)")
    beta_fit, _ = _beta_from_phase_slope(blocks, x)
    beta_eig = float(eig[0])
    if not beta_eig:
        raise ValueError(f"eigenvalue beta is zero: {eig!r}")
    rel = abs(beta_fit - beta_eig) / abs(beta_eig)
    return {
        "gate": "T2_agree",
        "beta_fit": beta_fit,
        "beta_eigenvalue": beta_eig,
        "relative_difference": rel,
        "pass": bool(rel <= float(tol)),
        "tolerance_in_force": float(tol),
        "n_eigenvalue_entries": int(eig.size),
        "note": ("first 'beta' entry used when the array holds several "
                 "stations" if eig.size > 1 else "single eigenvalue beta"),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _build_parser():
    p = argparse.ArgumentParser(
        prog="gates_101_20.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=__doc__,
        epilog=COST_TEXT)
    p.add_argument("--part-a", action="store_true",
                   help="run the Part A E-vs-H sensitivity curve on the cached "
                        "capture (no solve, seconds)")
    p.add_argument("--planes", default=PLANES_NPZ,
                   help=f"cached plane capture for --part-a (default: "
                        f"{PLANES_NPZ})")
    g = p.add_argument_group(
        "gated (need a fresh solve)",
        "T1/T2 need a plane capture that only a solve produces. They are "
        "refused unless --i-understand-this-needs-a-solve is also given, and "
        "the refusal prints the estimated cost.")
    g.add_argument("--t1", action="store_true", help="run T1_stab on --capture")
    g.add_argument("--t2", action="store_true", help="run T2_agree on --capture")
    g.add_argument("--capture", default=None,
                   help=".npz capture for --t1/--t2")
    g.add_argument("--drop-station", default="nearest",
                   help="T1: 'nearest', None or an int (default: nearest)")
    g.add_argument("--basis", default="analytic",
                   help="T1: 'analytic' only; 'mixed' raises "
                        "NotImplementedError")
    g.add_argument("--tol", type=float, default=None,
                   help="override the gate tolerance (T1 default 0.005, T2 "
                        "default 1e-3); reported back as tolerance_in_force")
    g.add_argument("--i-understand-this-needs-a-solve", action="store_true",
                   dest="ack",
                   help="required to reach T1/T2; a T1/T2 run costs a solve "
                        "(see the cost estimate below)")
    return p


def main(argv=None):
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not (args.part_a or args.t1 or args.t2):
        parser.print_help()
        return 0

    if args.part_a:
        result = part_a(args.planes)
        print(f"\nPART A done: {json.dumps({k: float(v) for k, v in result.items()})}")

    if args.t1 or args.t2:
        if not args.ack:
            sys.stderr.write(REFUSAL + "\n" + COST_TEXT)
            return 2
        if not args.capture:
            sys.stderr.write("--t1/--t2 need --capture <npz>\n")
            return 2
        ds = args.drop_station
        if isinstance(ds, str) and ds.isdigit():
            ds = int(ds)
        elif ds == "None":
            ds = None
        if args.t1:
            out = T1_stab(args.capture, drop_station=ds, basis=args.basis,
                          tol=T1_TOL if args.tol is None else args.tol)
            print(json.dumps(out, indent=2, default=float))
        if args.t2:
            out = T2_agree(args.capture,
                           tol=T2_TOL if args.tol is None else args.tol)
            print(json.dumps(out, indent=2, default=float))
    return 0


if __name__ == "__main__":
    sys.exit(main())
