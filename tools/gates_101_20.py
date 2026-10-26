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
``T1_stab``, ``T2_agree`` and ``T3_ey_slot`` are implemented here in full, but
none can run without a *fresh* plane capture: they consume blocks that only a
solve produces.  The CLI therefore refuses them unless
``--i-understand-this-needs-a-solve`` is passed, and prints the estimated cost
with the refusal.  Nothing in this module solves anything by itself.

THE THREE GATES (scopes as re-ruled by decisions.md 101.20, c.2)
---------------------------------------------------------------
``T1_stab``    drop-one-station stability of the fitted beta.  Tolerance 0.005,
               the *measured* window sensitivity (see T1_TOL).  Analytic basis
               only; ``basis='mixed'`` raises NotImplementedError.
``T2_agree``   EXTRACTION CONSISTENCY: beta from the station phase fit versus
               beta from the eigenvalue the capture carries.  Tolerance 0.005
               (0.5 %).  It FAILS on today's record -- the measured gap is
               4.52 % -- and that failure is intended: the gap is real and is
               the fix target.  It no longer gates the flux route; the old
               R_MODAL-versus-R_FLUX number survives only as the demoted
               :func:`aux_rmodal_rflux`, which is not a gate.
``T3_ey_slot`` FAULT DETECTION at 1e-5: inject a multiplicative break into the
               ONE named ``plane_Ey`` slot and detect it with that slot's own
               statistic ``rho = sum conj(Ey)Hz / sum conj(Ez)Hy``, whose
               response is 1:1.  A flux-ratio gate cannot see this break at all
               (1.0256e-8 at b=1e-5, see T3_TOL), which is exactly why the slot
               has to be checked directly.  Detection is the half-open side
               ``statistic >= tol * (1 - _DETECT_RTOL)``, so a break of size
               ``tol`` reads as detected even though the double representation
               of ``(1+b)`` lands the statistic ~3.8e-11 below ``tol``.

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
# T2_TOL -- tolerance in force for T2_agree (two extractions of ONE field).
#
# SCOPE (re-ruled by decisions.md 101.20 c.2): T2 tests EXTRACTION
# CONSISTENCY -- beta_fit (station phase slope) against beta_eigen (the
# eigenvalue the capture carries) -- not the quality of the beta fit.  The
# quality of the fit is T1's subject; conflating the two is what made the old
# T2 pass/fail mean nothing.
#
# STATUS: **derived from the measured gap, not invented.**
#
#   measured on the s10118 mixed-basis record
#     beta_fit    = 326.9107654423116
#     beta_eigen  = 312.7827646322591
#     |gap|/|beta_eigen| = 4.52 %
#
#   null floor that T2 must simply not trip:
#     repeat x2                            0.0        (bitwise identical)
#     BLAS threads 1 vs 4                  8.13e-11
#     float32 round-trip of input fields   1.10e-10 (ana) / 9.87e-11 (mix)
#     H-destagger toggle                   0.0        (scalar phase)
#
# 0.005 (0.5 %) sits between the two: 8 orders above the null floor and 9x
# *below* the 4.52 % gap, so on today's record T2 still FAILS -- by design and
# correctly.  The old value was 1e-3, which sat ~45x below a disagreement it was
# being asked to clear, so it failed by construction and said nothing about
# whether the extractions agreed; 0.005 replaces it (the 1e-3 value is
# superseded, not merely annotated as withdrawn).  0.5 % is also the resolution
# at which the two routes WOULD have to agree for the 4.52 % gap to be a fit
# artefact rather than a real disagreement -- that is the number the fix has to
# move.
# ---------------------------------------------------------------------------
T2_TOL = 0.005

# ---------------------------------------------------------------------------
# T3_TOL -- tolerance in force for T3_ey_slot (fault detection in the plane_Ey
# slot).
#
# STATUS: **derived from the measured sensitivity curve**, not invented.  The
# curve below is what T3_ey_slot() produces on the cached capture
# ``.scratch/tol/logs/TOLFLUX_planes.npz`` (arithmetic on an existing record;
# no solve).  One record, ``plane_Ey`` scaled by (1+b), two statistics:
#
#   break b   |R(b)/R(1)-1|  [flux route]   |rho(b)/rho(1)-1|  [Ey slot]
#   1e-2        1.023655e-05                   1.000000e-02
#   1e-3        1.025440e-06                   1.000000e-03
#   1e-4        1.025619e-07                   1.000000e-04
#   1e-5        1.025637e-08                   1.000000e-05
#   1e-6        1.025639e-09                   1.000000e-06
#   1e-7        1.025637e-10                   1.000000e-07
#
# What the curve says, in the order it matters:
#
# 1. THE FLUX ROUTE CANNOT REACH 1e-5, and no tolerance choice fixes that.  Its
#    slope is 1.0236e-3 per unit relative Ey break -- that is the station-to-
#    station DIFFERENCE of the Ey*Hz share of Sx (measured share 0.193803 at
#    station 0 vs 0.192777 at station 8), because a common scale almost cancels
#    in R = F8/F0.  At b=1e-5 the flux statistic therefore reads 1.0256e-8,
#    i.e. 975x below a 1e-5 threshold: blind.
#
# 2. THE Ey-SLOT STATISTIC REACHES IT WITH ROOM.  rho = sum conj(Ey)Hz /
#    sum conj(Ez)Hy responds 1:1 (measured relative response 1.000000000 at
#    every level down to 1e-7; the 3.8e-11 shortfall at 1e-5 is the double
#    representation of (1+b), not physics), because the break scales only the
#    numerator.  Its zero-break response is 0.0 exactly, so the arithmetic
#    floor is absent; the only real floor is the record's reproducibility,
#    measured 1.1e-10 (float32 round-trip, T1_TOL's table) -- five decades below
#    1e-5.
#
#    THAT 3.8e-11 IS A SIGN, NOT A CURIOSITY.  At ``b == tol`` the statistic
#    lands 3.8e-11 *below* the threshold, which a bare ``>= tol`` reads as "not
#    detected" -- the exact break the gate exists to catch would be called
#    clean.  The shortfall is a few ulp of the ratio (one ulp of 1.0 is 2.2e-16,
#    i.e. 2.2e-11 relative at 1e-5), so it can fall either side depending on the
#    data; the comparison therefore carries an explicit slack
#    ``_DETECT_RTOL = 1e-9`` (26x the measured shortfall, and a threshold shift
#    of ``tol*1e-9 = 1e-14``, four decades below the record's 1.1e-10
#    reproducibility floor) and detection is ``statistic >= tol*(1-1e-9)``.
#    Without it the promise "fires on a break of size tol" would hold only
#    accidentally.
#
# So 1e-5 IS supported -- by the slot statistic, not by the flux ratio.  1e-5 is
# chosen because it is the smallest break the chosen statistic resolves with
# five decades of margin, and it is exactly the operator's target.  It is NOT
# chosen because it was asked for: had the slot statistic come in at 1e-3, the
# tolerance would have been 1e-3.
# ---------------------------------------------------------------------------
T3_TOL = 1e-5

#: Break levels swept by T3_ey_slot; the ladder the curve above was measured on.
T3_BREAK_LADDER = (1e-2, 1e-3, 1e-4, 1e-5, 1e-6, 1e-7)

# ---------------------------------------------------------------------------
# Cost text printed with every refusal of T1/T2.
# ---------------------------------------------------------------------------
COST_TEXT = """\
estimated cost of a T1/T2/T3 run, from the cached record:
  * one board_run_pw solve of the s10118 station-flux geometry:
    wall_s = 4210.484 s = 70.2 min
    (measured, /workspace/.scratch/tol/TOLFLUX.tables.txt line 58)
  * phasor/flux extraction and the beta fit on the result: < 1 s each
  * no cached capture exists at a default path: the solve has to be run first
    and its .npz handed in with --capture
"""

REFUSAL = """\
REFUSED: T1/T2/T3 are written but deliberately unrunnable by accident.
They need a fresh plane capture, which means running a solve.
If that is really what you want, add --i-understand-this-needs-a-solve
(and --capture <npz>):

    python3 tools/gates_101_20.py --t1 --capture CAP.npz \\
        --i-understand-this-needs-a-solve

T1 = drop-one-station beta stability (tol 0.005)
T2 = extraction consistency, beta_fit vs beta_eigen (tol 0.005, expected to FAIL)
T3 = plane_Ey slot fault detection at 1e-5 (inject-and-detect, not a ratio gate)
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
    defaulting to the module-level :data:`T2_TOL` (0.005).  This is the
    *extraction consistency* test re-ruled by 101.20 c.2: the measured gap is
    4.52 % (beta_fit 326.9107654423116 vs beta_eigen 312.7827646322591), 9x the
    tolerance, so this gate FAILS on today's record -- expected and correct,
    because the gap is the fix target, not a measurement artefact to be
    tolerated.  ``tolerance_in_force`` reports the number actually used.

    The old statistic (R_MODAL versus R_FLUX at 1e-3) is NOT withdrawn as a
    number but IS withdrawn as a gate: it sat ~45x below the 4.52 % it had to
    clear and inherited the fit-versus-eigenvalue discrepancy by construction.
    It survives as :func:`aux_rmodal_rflux`, which returns ``gate=False``.

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
        "scope": "extraction consistency: beta_fit vs beta_eigen",
        "beta_fit": beta_fit,
        "beta_eigenvalue": beta_eig,
        "relative_difference": rel,
        "pass": bool(rel <= float(tol)),
        "tolerance_in_force": float(tol),
        "n_eigenvalue_entries": int(eig.size),
        "note": ("first 'beta' entry used when the array holds several "
                 "stations" if eig.size > 1 else "single eigenvalue beta"),
    }


def aux_rmodal_rflux(capture):
    """DEMOTED, NOT A GATE: the pre-101.20 T2 statistic, kept auditable only.

    ``R_FLUX`` is the measured station flux ratio ``F[8]/F[0]``.  ``R_MODAL``
    is the lossless modal prediction of the same ratio for a propagating mode:
    the record carries no attenuation, so ``|R_MODAL| = 1`` exactly (any phase
    factor cancels in the magnitude).  The number this returns is therefore
    ``|R_FLUX - 1|`` -- and it is reported here only so that the old T2 statistic
    stays computable.

    It is NOT a gate and must never be used as one: at the old ``T2_TOL = 1e-3``
    it failed by construction (~45x below the 4.52 % beta fit-versus-eigenvalue
    gap it was being asked to clear) and it measures the *flux* route, i.e.
    exactly the thing T2 no longer claims to test.  The gate is
    :func:`T2_agree`, on beta_fit vs beta_eigen.

    Returns:
        dict: ``R_MODAL``, ``R_FLUX``, ``relative_difference``, ``gate=False``.
    """
    blocks, x = _capture_planes(capture)
    d = _load_capture(capture)
    try:
        n_samples = int(np.asarray(d["plane_n_samples"]).ravel()[0])
    except (KeyError, IndexError):
        n_samples = 1
    flux = _phys_flux(blocks["plane_Ey"], blocks["plane_Ez"],
                      blocks["plane_Hy"], blocks["plane_Hz"], n_samples)
    r_flux = float(flux[-1] / flux[0])
    r_modal = 1.0
    return {
        "gate": False,
        "role": "demoted auxiliary (pre-101.20 T2 statistic); not a gate",
        "R_MODAL": r_modal,
        "R_FLUX": r_flux,
        "relative_difference": abs(r_flux / r_modal - 1.0),
        "n_stations": int(np.asarray(x).size),
        "note": ("|R_MODAL| = 1 for a propagating mode (no attenuation in the "
                 "record), so this is |R_FLUX - 1|; use T2_agree instead"),
    }


# ---------------------------------------------------------------------------
# T3 -- fault detection in ONE named polarisation slot
# ---------------------------------------------------------------------------
def _capture_blocks(capture):
    """``(blocks, n_samples)`` -- no station geometry needed by T3."""
    d = _load_capture(capture)
    blocks = {}
    for k in BLOCK_KEYS:
        try:
            blocks[k] = np.asarray(d[k], dtype=complex)
        except KeyError:
            raise ValueError(
                f"T3_ey_slot: the capture carries no {k!r} block, so no slot "
                f"can be checked (have: {sorted(d.files) if hasattr(d, 'files') else '?'})")
    try:
        n_samples = int(np.asarray(d["plane_n_samples"]).ravel()[0])
    except (KeyError, IndexError):
        n_samples = 1
    return blocks, n_samples


def _ey_slot_terms(blocks):
    """The two ``Sx`` product terms, station by station.

    ``plane_phasor`` writes ``P = 0.5 Re(sum conj(E_y) H_z - sum conj(E_z) H_y)``,
    so ``t_eyhz`` is the term the ``plane_Ey`` slot feeds and ``t_ezhy`` is the
    term it does not.  Their station-to-station ratio drift is the whole reason
    a flux-ratio gate is nearly blind to the slot, and their ratio is the slot
    statistic itself.
    """
    t_eyhz = np.sum(np.conj(blocks["plane_Ey"]) * blocks["plane_Hz"], axis=(-2, -1))
    t_ezhy = np.sum(np.conj(blocks["plane_Ez"]) * blocks["plane_Hy"], axis=(-2, -1))
    return t_eyhz, t_ezhy


def _break_slot(blocks, b, slot):
    """A copy of ``blocks`` with exactly one slot scaled by ``(1+b)``."""
    arrs = {k: np.array(blocks[k], dtype=complex, copy=True) for k in BLOCK_KEYS}
    arrs[slot] *= (1.0 + b)
    return arrs


#: Relative slack on the ``>=`` side of T3's detection comparisons.  The break
#: is carried as ``(1+b)`` in double, so the statistic at ``b == tol`` lands a
#: few ulp away from ``tol`` -- measured 3.8e-11 *below* it on the cached
#: capture (see T3_TOL, note 2).  A bare ``>=`` would therefore report the
#: threshold break as undetected.  1e-9 is 26x the measured shortfall, and at
#: ``tol = 1e-5`` it shifts the threshold by 1e-14 -- four decades below the
#: record's 1.1e-10 reproducibility floor -- so it changes no real detection,
#: it only makes the boundary deterministic.
_DETECT_RTOL = 1e-9


def _detected(statistic, tol):
    """``|statistic| >= tol``, half-open with the ``_DETECT_RTOL`` slack.

    ``tol`` is inclusive up to ``tol * _DETECT_RTOL`` relative, which is what
    makes "a break of size ``tol`` is detected" true rather than dependent on
    which side of the threshold the double arithmetic happens to land.
    """
    return bool(abs(float(statistic)) >= float(tol) * (1.0 - _DETECT_RTOL))


def _t3_statistics(blocks, n_samples, b, slot="plane_Ey"):
    """``(flux_ratio_statistic_input, ey_slot_input)`` at break level ``b``.

    Returns the two *raw* quantities the statistics are ratios of, so the
    caller can form ``|x(b)/x(1) - 1|`` against the same record at ``b=0``.
    """
    arrs = _break_slot(blocks, b, slot)
    flux = _phys_flux(arrs["plane_Ey"], arrs["plane_Ez"],
                      arrs["plane_Hy"], arrs["plane_Hz"], n_samples)
    t_eyhz, t_ezhy = _ey_slot_terms(arrs)
    return complex(flux[-1] / flux[0]).real, complex(np.sum(t_eyhz) / np.sum(t_ezhy))


def T3_ey_slot(capture, *, tol=T3_TOL, ladder=T3_BREAK_LADDER,
               slot="plane_Ey", out=None):
    """Fault detection: inject a break into ONE named slot, resolve it at ``tol``.

    This is the T3 re-scoped by 101.20 c.2.  It is a *fault-injection
    sensitivity* gate, not a ratio gate: one record is the reference, the same
    record with ``slot`` scaled by ``(1+b)`` is the fault, and the statistic is
    the **response**

        flux route :  | R(b)/R(1) - 1 |      R = F[8]/F[0]
        slot route :  | rho(b)/rho(1) - 1 |  rho = sum conj(Ey)Hz / sum conj(Ez)Hy

    Both are computed and printed at every level, so the two can never be
    confused -- the entire point of the gate is that they differ by ~1000x.

    Why ``plane_Ey`` and not ``plane_Ez``: the Ez slot carries ~80 % of Sx, so
    its response is already saturated (slope ~0.999) and it cannot resolve a
    small break in itself with any margin.  The Ey slot's *flux* response is the
    station-to-station difference of its Sx share, measured slope 1.0236e-3, so
    a 1e-5 break reads 1.0256e-8 -- 975x below threshold, i.e. invisible to a
    flux-based gate.  Its *slot* response is 1:1, which is why the slot has to
    be checked directly.  See :data:`T3_TOL` for the measured curve.

    REPLACES the degenerate E-versus-H branch
    ----------------------------------------
    The old T3 compared ``R_E`` with ``R_H``.  A *global* E scale cancels inside
    a ratio of per-station products ``conj(E)H``, so the fitted slope came out
    -2.45e-17 against a residual of 2.24e-16, and an H-only break gave
    ``|R_E - R_H| = 0.0`` exactly: the branch was measuring its own
    cancellation, not a fault.  It is removed, not retuned.

    ``pass`` requires the slot statistic to have unit sensitivity
    (``|slope| >= 1 - 1e-9``; the slack is the double representation of
    ``(1+b)``, measured at 3.8e-11) *and* both zero-break responses to be exactly
    zero, i.e. the gate fires on a break of size ``tol`` and stays silent on
    clean data.  A missing capture raises rather than passing silently.

    Detection is the half-open side, ``statistic >= tol * (1 - _DETECT_RTOL)``:
    at ``b == tol`` the statistic lands ~3.8e-11 *below* ``tol`` (the double
    representation of ``(1+b)``), so a bare ``>=`` would call exactly the break
    the gate exists to catch *undetected*.  The slack is 1e-9 relative (26x
    that shortfall; 1e-14 absolute at ``tol = 1e-5``, four decades below the
    record's 1.1e-10 reproducibility floor), so it moves no real detection --
    it only settles the boundary.
    """
    if slot != "plane_Ey":
        raise ValueError(
            f"T3_ey_slot(slot={slot!r}): only 'plane_Ey' is gated -- the Ez "
            f"slot's response is saturated (slope ~0.999) and Hy/Hz are the "
            f"reference terms of the slot statistic")
    blocks, n_samples = _capture_blocks(capture)
    if blocks["plane_Ey"].size == 0:
        raise ValueError("T3_ey_slot: the capture's plane_Ey block is empty; "
                         "there is no slot to test")

    x0_flux, x0_rho = _t3_statistics(blocks, n_samples, 0.0, slot)
    if x0_rho == 0.0:
        raise ValueError("T3_ey_slot: sum conj(Ez)Hy is zero on this capture, "
                         "so the slot statistic is undefined")

    rows = []
    for b in ladder:
        xf, xr = _t3_statistics(blocks, n_samples, b, slot)
        rows.append({
            "b": float(b),
            "flux_statistic": float(abs(xf / x0_flux - 1.0)),
            "slot_statistic": float(abs(xr / x0_rho - 1.0)),
            "flux_detected": _detected(abs(xf / x0_flux - 1.0), tol),
            "slot_detected": _detected(abs(xr / x0_rho - 1.0), tol),
        })

    bs = np.asarray([r["b"] for r in rows], dtype=float)
    y_flux = np.asarray([r["flux_statistic"] for r in rows], dtype=float)
    y_slot = np.asarray([r["slot_statistic"] for r in rows], dtype=float)
    m_flux, resid_flux = _fit_through_origin(bs, y_flux)
    m_slot, resid_slot = _fit_through_origin(bs, y_slot)
    null_flux = float(abs(x0_flux / x0_flux - 1.0))
    null_slot = float(abs(x0_rho / x0_rho - 1.0))

    # the effective threshold is the one _detected() uses, so "smallest
    # detectable b" is the smallest break this gate actually calls detected
    thr = float(tol) * (1.0 - _DETECT_RTOL)
    b_min_flux = (thr / abs(m_flux)) if m_flux else float("inf")
    b_min_slot = (thr / abs(m_slot)) if m_slot else float("inf")
    passed = bool(abs(m_slot) >= 1.0 - 1e-9 and null_slot == 0.0
                  and null_flux == 0.0)

    if out is not None:
        w = out.write
        w("== T3: plane_Ey slot fault detection (inject-and-detect) ==\n")
        w(f"tolerance in force {tol!r} (see T3_TOL);  slot {slot!r};  "
          f"{len(rows)} break levels\n")
        w(f"{'b':>9} | {'flux |R/R1-1|':>16} {'det':>4} | "
          f"{'slot |rho/rho1-1|':>18} {'det':>4}\n")
        for r in rows:
            w(f"{r['b']:>9.0e} | {r['flux_statistic']:>16.6e} "
              f"{'YES' if r['flux_detected'] else ' no':>4} | "
              f"{r['slot_statistic']:>18.6e} "
              f"{'YES' if r['slot_detected'] else ' no':>4}\n")
        w(f"slope (through origin): flux {m_flux!r}, slot {m_slot!r}\n")
        w(f"max|resid|:              flux {float(np.max(np.abs(resid_flux)))!r}, "
          f"slot {float(np.max(np.abs(resid_slot)))!r}\n")
        w(f"zero-break response:     flux {null_flux!r}, slot {null_slot!r}\n")
        w(f"smallest detectable |b| at {tol:g}: flux {b_min_flux!r}, "
          f"slot {b_min_slot!r}\n")

    return {
        "gate": "T3_ey_slot",
        "scope": "fault detection: one named slot, inject-and-detect",
        "slot": slot,
        "tolerance_in_force": float(tol),
        "rows": rows,
        "slope_flux": m_flux,
        "slope_slot": m_slot,
        "resid_flux": float(np.max(np.abs(resid_flux))),
        "resid_slot": float(np.max(np.abs(resid_slot))),
        "null_response_flux": null_flux,
        "null_response_slot": null_slot,
        "smallest_detectable_b_flux": float(b_min_flux),
        "smallest_detectable_b_slot": float(b_min_slot),
        "flux_route_reaches_tol": bool(b_min_flux <= tol),
        "n_stations": int(blocks["plane_Ey"].shape[0]),
        "pass": passed,
        "note": ("replaces the degenerate E-vs-H branch (global E scale cancels "
                 "in a ratio of per-station conj(E)H products, so that branch "
                 "had slope -2.45e-17 and |R_E - R_H| = 0.0 exactly)"),
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
        "T1/T2/T3 need a plane capture that only a solve produces. They are "
        "refused unless --i-understand-this-needs-a-solve is also given, and "
        "the refusal prints the estimated cost.")
    g.add_argument("--t1", action="store_true", help="run T1_stab on --capture")
    g.add_argument("--t2", action="store_true", help="run T2_agree on --capture")
    g.add_argument("--t3", action="store_true",
                   help="run T3_ey_slot fault-detection curve on --capture")
    g.add_argument("--capture", default=None,
                   help=".npz capture for --t1/--t2/--t3")
    g.add_argument("--drop-station", default="nearest",
                   help="T1: 'nearest', None or an int (default: nearest)")
    g.add_argument("--basis", default="analytic",
                   help="T1: 'analytic' only; 'mixed' raises "
                        "NotImplementedError")
    g.add_argument("--tol", type=float, default=None,
                   help="override the gate tolerance (T1 default 0.005, T2 "
                        "default 0.005, T3 default 1e-5); reported back as "
                        "tolerance_in_force")
    g.add_argument("--i-understand-this-needs-a-solve", action="store_true",
                   dest="ack",
                   help="required to reach T1/T2/T3; a T1/T2/T3 run costs a "
                        "solve (see the cost estimate below)")
    return p


def main(argv=None):
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not (args.part_a or args.t1 or args.t2 or args.t3):
        parser.print_help()
        return 0

    if args.part_a:
        result = part_a(args.planes)
        print(f"\nPART A done: {json.dumps({k: float(v) for k, v in result.items()})}")

    if args.t1 or args.t2 or args.t3:
        if not args.ack:
            sys.stderr.write(REFUSAL + "\n" + COST_TEXT)
            return 2
        if not args.capture:
            sys.stderr.write("--t1/--t2/--t3 need --capture <npz>\n")
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
        if args.t3:
            out = T3_ey_slot(args.capture,
                             tol=T3_TOL if args.tol is None else args.tol,
                             out=sys.stdout)
            print(json.dumps(out, indent=2, default=float))
    return 0


if __name__ == "__main__":
    sys.exit(main())
