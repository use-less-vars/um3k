"""phaselag_subsets.py -- is the phase-slope beta a property of the line, or of
the station window it was read from?

READ-ONLY, NO SOLVE.  Every number comes from the already-banked capture
``.scratch/tol/logs/TOLFLUX_planes.npz`` (the 9 station planes and their ``x``).
Nothing is written outside ``tools/host/phaselag-subsets/out/``; ``emfit`` is
imported for one thing only, the ANCHOR ROUTE below (a Laplace profile and a
9-station least-squares fit -- no eigenproblem, seconds).

THE ESTIMATOR UNDER TEST, copied from ``tools/gates_101_20.py:426-445``
(``_beta_from_phase_slope``), not imported from it::

    ey   = blocks["plane_Ey"]                        # (n_st, ny, nzn)
    z    = sum_plane conj(ey[0]) * ey                # station phasor vs station 0
    phi  = np.unwrap(np.angle(z))
    beta = abs(float(np.polyfit(x, phi, 1)[0]))

The reference station stays station 0 even when station 0 is dropped from the
fit, because a reference phase does not enter a slope.  So every subset below is
fitted on the SAME ``z`` vector, merely masked -- exactly what
``_beta_from_phase_slope(blocks, x, mask)`` does.

WHAT IS PRINTED
  (a) the station table: idx, x, wrapped phase, unwrapped phase, residual from
      the all-9 line, and the unwrap step between neighbours
  (b) the all-9 fit as slope AND beta, against the banked anchor 309.981864
  (c) the same fit over station subsets -- drop one end, drop both, drop the
      station nearest the port, every contiguous triple, every contiguous pair,
      the widest pair -- as beta and as relative spread against the all-9 value
  (d) the RMS residual of the phase about each subset's own fitted line [rad]
  (e) SPREAD = the largest of those spreads, and a verdict at 0.2 % / 0.5 %
  (f) a subset with fewer than two finite stations is skipped with a printed
      note, and NaN is never allowed to become a verdict

THE ANCHOR IS A DIFFERENT ESTIMATOR -- read this before believing a mismatch.
``tools/gates_101_20.py:110`` quotes ``beta 309.9818636706751`` from
``.scratch/logs/s10118_beta_null.py`` STEP 2, and that number is
``fit_beta(x, v, n_wave=1).beta`` (``emfit/ports.py:861``: a 2048-point scan, a
bounded Brent refinement and a Newton polish on the complex one-wave model
``v(z) = A exp(-j beta z)``) applied to the ANALYTIC-basis modal station
voltages -- ``microstrip_mode_profile`` -> ``plane_mode`` ->
``modal_station_phasors`` -- over all 9 stations.  It is *not* a polyfit of an
unwrapped phase.  So (b)'s 1e-4 gate can fail with the banked data perfectly
intact, and the ANCHOR ROUTE block is what separates "the capture moved" from
"a different estimator was quoted".
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np

#: the anchor as ``tools/gates_101_20.py:110`` quotes it, in full and rounded.
ANCHOR_FULL = 309.9818636706751
ANCHOR_ROUND = 309.981864
#: relative tolerance of the (b) reconstruction gate.
RECON_TOL = 1.0e-4
#: verdict thresholds on SPREAD, in percent.
STABLE = 0.2
MARGINAL = 0.5

HERE = os.path.dirname(os.path.abspath(__file__))


def say(*a):
    print(" ".join(str(x) for x in a), flush=True)


# ---------------------------------------------------------------------------
# repo discovery -- one answer, from tools/host/_bootstrap.py, shared with the
# sibling host scripts (c1-audit/c1_audit.py, c1-audit/pecbox_variant.py,
# attribution/attribution.py).  Never count ".." levels -- this file sits three
# levels below the root; a root that holds no emfit/ is not accepted; both
# C1_REPO and REPO name the root.  The traps live in that module's docstring.
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
from _bootstrap import bootstrap  # noqa: E402

REPO = bootstrap(start=HERE)
EMFIT_DIR = os.path.join(REPO, "emfit")     # presence validated in find_repo()

PLANES = os.path.join(REPO, ".scratch", "tol", "logs", "TOLFLUX_planes.npz")
GEOJSON = os.path.join(REPO, ".scratch", "tol", "logs", "TOLFLUX.json")


def _ls_fit(idx, phi, xs):
    """``abs(polyfit(x, phi, 1))`` over station set *idx*, and its residual.

    Returns ``(fit, n_dropped)``; ``fit`` is ``None`` when fewer than two of the
    requested stations carry a finite phase.
    """
    idx = np.atleast_1d(np.asarray(idx, dtype=int))
    xx = np.asarray(xs[idx], dtype=float)
    ph = np.asarray(phi[idx], dtype=float)
    ok = np.isfinite(xx) & np.isfinite(ph)
    n_dropped = int(ok.size - int(ok.sum()))
    if int(ok.sum()) < 2:
        return None, n_dropped
    xx, ph = xx[ok], ph[ok]
    co = np.polyfit(xx, ph, 1)
    resid = ph - np.polyval(co, xx)
    return {
        "slope": float(co[0]),
        "beta": abs(float(co[0])),
        "co": co,
        "rms": float(np.sqrt(float(np.mean(resid ** 2)))),
        "n": int(xx.size),
    }, n_dropped


def _fmt_set(idx):
    """``0-2`` for a contiguous run, ``0,1,8`` otherwise."""
    idx = list(idx)
    if len(idx) == idx[-1] - idx[0] + 1:
        return f"{idx[0]}-{idx[-1]}"
    return ",".join(str(i) for i in idx)


def _x_port(D):
    """The port plane [m], as ``tools/gates_101_20.py:485-493`` reads it."""
    try:
        return float(np.asarray(D["x_port"]).ravel()[0])
    except (KeyError, ValueError, IndexError):
        return float("nan")


def _anchor_route(D, xs):
    """Recompute the anchor the way ``.scratch/logs/s10118_beta_null.py`` did.

    Returns ``(beta, note)``; ``beta`` is NaN when the route cannot run and
    *note* says why.  The caller prints either and moves on -- no verdict
    depends on this block.
    """
    try:
        from emfit import modal as M                            # noqa: PLC0415
        from emfit.mode_profile import microstrip_mode_profile   # noqa: PLC0415

        with open(GEOJSON) as fh:
            g = json.load(fh)["geometry"]
        nyn, nzn = int(g["ny"]) + 1, int(g["nz"]) + 1
        ey_shape = tuple(np.asarray(D["plane_Ey"]).shape[1:])
        ez_shape = tuple(np.asarray(D["plane_Ez"]).shape[1:])
        if ey_shape != (nyn - 1, nzn) or ez_shape != (nyn, nzn - 1):
            return float("nan"), (
                f"lattice mismatch: plane_Ey{ey_shape} plane_Ez{ez_shape} vs this "
                f"geometry's {(nyn - 1, nzn)}/{(nyn, nzn - 1)}")
        prof = microstrip_mode_profile(float(g["h"]), float(g["w"]),
                                       float(g["eps_r"]), n_sub=int(g["n_sub"]))
        pm = M.plane_mode(prof, nyn=nyn, nzn=nzn, k_strip=int(g["k_strip"]),
                          iy_strip_centre=int(g["j_centre"]), cell=float(g["cell"]))
        f0, dt = float(D["plane_f"]), float(D["plane_dt"])
        sp = M.modal_station_phasors(D, pm, np.arange(xs.size), f0=f0, dt=dt)
        line = M.modal_line_quantities(sp.v, sp.i, xs, f0=f0)
        return float(line.beta), "fit_beta n_wave=1 on analytic-basis modal v, all stations"
    except Exception as exc:                                  # noqa: BLE001
        return float("nan"), f"{type(exc).__name__}: {exc}"


def main() -> int:
    say("=" * 78)
    say("PHASE-SLOPE BETA: SUBSET SENSITIVITY  (banked capture, read-only, no solve)")
    say("=" * 78)
    say(f"repo     : {REPO}")
    say(f"emfit    : {EMFIT_DIR}")
    say(f"capture  : {PLANES}")
    if not os.path.exists(PLANES):
        say(f"FATAL: the banked capture is missing: {PLANES}")
        return 3

    D = np.load(PLANES, allow_pickle=False)
    ey = np.asarray(D["plane_Ey"], dtype=complex)
    xs = None
    for key in ("plane_station_x", "station_x"):
        if key in D.files:
            xs = np.asarray(D[key], dtype=float).ravel()
            say(f"stations : key {key!r}")
            break
    if xs is None:
        say("FATAL: the capture carries no station positions "
            "(plane_station_x / station_x)")
        return 3
    n = int(xs.size)
    if ey.shape[0] != n:
        say(f"FATAL: plane_Ey holds {ey.shape[0]} stations, the x record {n}")
        return 3
    if n < 2:
        say(f"FATAL: a phase-slope fit needs 2 or more stations, got {n}")
        return 3
    say(f"blocks   : plane_Ey {ey.shape}  plane_Ez {np.shape(D['plane_Ez'])}")
    say(f"tone     : f = {float(D['plane_f']):.9g} Hz  dt = {float(D['plane_dt']):.9g} s"
        f"  n_samples = {int(D['plane_n_samples'])}")
    say(f"stations : n = {n}  x = {1e3 * xs[0]:.4f} .. {1e3 * xs[-1]:.4f} mm  "
        f"dx = {1e3 * np.min(np.diff(xs)):.4f} .. {1e3 * np.max(np.diff(xs)):.4f} mm")
    x_port = _x_port(D)
    if np.isfinite(x_port):
        nearest = int(np.argmin(np.abs(xs - x_port)))
        say(f"port     : x_port = {1e3 * x_port:.4f} mm -> nearest station is idx {nearest} "
            f"(x = {1e3 * xs[nearest]:.4f} mm, {1e3 * abs(xs[nearest] - x_port):.4f} mm away)")
    else:
        nearest = int(np.argmin(np.abs(xs - xs[0])))
        say("port     : the capture carries no x_port -> 'nearest the port' falls back to "
            f"idx {nearest} (the first station); state this before reading the row")

    # --- the phasor, exactly as gates_101_20.py:436-438 forms it -------------
    z = np.sum(np.conj(ey[0])[None, :, :] * ey, axis=(-2, -1))
    raw = np.angle(z)
    phi = np.unwrap(raw)
    dphi = np.diff(phi)
    ref, _ = _ls_fit(range(n), phi, xs)
    if ref is None:
        say("FATAL: the all-9 fit has fewer than two finite stations")
        return 3
    resid_all = phi - np.polyval(ref["co"], xs)

    say("-" * 78)
    say("(a) STATION TABLE   z_i = sum_plane conj(E_y[0]) E_y[i], reference = station 0")
    say(f"    {'idx':>3} {'x [mm]':>9} {'angle(z) [rad]':>15} {'unwrap [rad]':>13} "
        f"{'dphi [rad]':>11} {'resid(all-9) [rad]':>19}")
    for i in range(n):
        step = "" if i == 0 else f"{dphi[i - 1]:+11.6f}"
        say(f"    {i:>3} {1e3 * xs[i]:>9.4f} {raw[i]:>15.9f} {phi[i]:>13.6f} "
            f"{step:>11} {resid_all[i]:>19.3e}")
    say(f"    unwrap steps span {dphi.min():+.6f} .. {dphi.max():+.6f} rad; np.unwrap uses the")
    say("    default 2*pi period and is only safe while |dphi| < pi between neighbours")

    # --- (b) the all-9 fit against the anchor -------------------------------
    say("-" * 78)
    say("(b) ALL-9 LEAST-SQUARES PHASE SLOPE, against the banked anchor")
    say(f"    slope  (signed, d phi / d x) : {ref['slope']!r} rad/m")
    say(f"    beta   (abs of the slope)    : {ref['beta']!r} rad/m")
    say(f"    anchor : {ANCHOR_ROUND!r}  (tools/gates_101_20.py:110, full "
        f"{ANCHOR_FULL!r})")
    rel = abs(ref["beta"] - ANCHOR_FULL) / abs(ANCHOR_FULL)
    say(f"    rel diff vs the anchor       : {rel:.6e}  ({100.0 * rel:.6f} %)   "
        f"gate {RECON_TOL:.0e}")
    if rel <= RECON_TOL:
        say("    RECON OK: this polyfit reproduces the quoted beta to better than 1e-4")
    else:
        say("    RECON MISMATCH: the polyfit beta differs from the quoted beta by more "
            f"than {RECON_TOL:.0e} relative")
        say("      NOT necessarily damaged data: the quote is fit_beta(x, v, 1) on the "
            "ANALYTIC-basis")
        say("      modal voltages (.scratch/logs/s10118_beta_null.py STEP 2), a different "
            "estimator from")
        say("      this polyfit on the raw plane_Ey phasor. Read the ANCHOR ROUTE block, "
            "which recomputes")
        say("      the quote as it was produced, before concluding anything about the "
            "capture.")
    b_anchor, note = _anchor_route(D, xs)
    if not np.isfinite(b_anchor):
        say(f"    ANCHOR ROUTE skipped: {note}")
    else:
        rel_a = abs(b_anchor - ANCHOR_FULL) / abs(ANCHOR_FULL)
        say(f"    ANCHOR ROUTE beta = {b_anchor!r} rad/m  ({note})")
        say(f"    ANCHOR ROUTE rel diff vs {ANCHOR_FULL!r} = {rel_a:.3e}")
        if rel_a == 0.0:
            say("    ANCHOR REPRODUCED bitwise: the capture is the one the quote came from")
        elif rel_a <= RECON_TOL:
            say(f"    ANCHOR REPRODUCED within {RECON_TOL:.0e} relative")
        else:
            say(f"    ANCHOR DRIFT: {100.0 * rel_a:.6f} % off the quote -- the banked "
                "capture or the geometry moved")

    # --- the subset list ----------------------------------------------------
    first, last = 0, n - 1
    subsets = []

    def add(label, idx):
        subsets.append((label, tuple(int(i) for i in idx)))

    add(f"all {n} stations (REFERENCE)", range(n))
    add(f"drop nearest-port (idx {nearest})", [i for i in range(n) if i != nearest])
    add(f"drop first (idx {first})", range(first + 1, n))
    add(f"drop last (idx {last})", range(0, last))
    add("drop first+last", range(first + 1, last))
    add(f"drop nearest-port (idx {nearest}) + last (idx {last})",
        [i for i in range(0, last) if i != nearest])
    for lo in range(0, n - 2):
        add(f"triple {lo}-{lo + 2}", range(lo, lo + 3))
    for lo in range(0, n - 1):
        add(f"pair {lo}-{lo + 1}", range(lo, lo + 2))
    add(f"pair widest {first}-{last}", (first, last))

    # --- (c) + (d) the subset table ----------------------------------------
    say("-" * 78)
    say("(c) SUBSET SENSITIVITY, with (d) the RMS residual about each subset's own line")
    say(f"    same z, same np.polyfit degree 1, stations masked; reference beta = "
        f"{ref['beta']!r} rad/m")
    say(f"    {'stations':>15} {'n':>2} {'beta [rad/m]':>16} {'|dbeta|/beta [%]':>17} "
        f"{'rms resid [rad]':>16}  note")
    seen = {}
    rows = []
    for label, idx in subsets:
        fit, n_dropped = _ls_fit(idx, phi, xs)
        dup_of = seen.get(idx)
        seen.setdefault(idx, label)
        notes = []
        if dup_of is not None:
            notes.append(f"same station set as '{dup_of}'")
        if fit is None:
            notes.append(f"SKIPPED: {len(idx) - n_dropped} finite station(s) < 2")
            say(f"    {_fmt_set(idx):>15} {len(idx):>2} {'-':>16} {'-':>17} {'-':>16}  "
                f"{label}  [{'; '.join(notes)}]")
            continue
        if n_dropped:
            notes.append(f"{n_dropped} non-finite station(s) dropped")
        if fit["n"] == 2:
            notes.append("2 points: the line is exact, so the residual is 0 by construction")
        spread = (100.0 * abs(fit["beta"] - ref["beta"]) / abs(ref["beta"])
                  if ref["beta"] else float("nan"))
        rows.append((label, idx, fit, spread, dup_of is not None))
        say(f"    {_fmt_set(idx):>15} {fit['n']:>2} {fit['beta']:>16.9f} {spread:>17.4f} "
            f"{fit['rms']:>16.4e}  {label}"
            + (f"  [{'; '.join(notes)}]" if notes else ""))

    # --- (e) the verdict ----------------------------------------------------
    spreads = [r[3] for r in rows
               if not r[4] and r[1] != tuple(range(n)) and np.isfinite(r[3])]
    spread = max(spreads) if spreads else float("nan")
    say("=" * 78)
    say("(e) VERDICT")
    say(f"    reference  : beta_all = {ref['beta']!r} rad/m over {n} stations")
    say(f"    compared   : {len(spreads)} distinct station sets (the all-{n} reference and "
        "any repeat excluded)")
    say(f"    spread     : max over those sets of |beta_set - beta_all| / beta_all")
    say(f"    thresholds : <= {STABLE:.1f} % FALSIFIED (estimator stable) | "
        f"{STABLE:.1f}-{MARGINAL:.1f} % MARGINAL | > {MARGINAL:.1f} % ALIVE")
    if not np.isfinite(spread):
        say("    SPREAD = nan  (no subset produced a finite beta; see the SKIP notes)")
        say("    VERDICT: UNDETERMINED (nothing comparable was fitted, so no claim is made)")
        say("=" * 78)
        return 4
    say(f"    SPREAD = {spread:.3f} %")
    if spread <= STABLE:
        say(f"    VERDICT: FALSIFIED (estimator stable, spread <= {STABLE:.1f}%)")
    elif spread <= MARGINAL:
        say(f"    VERDICT: MARGINAL (spread {spread:.3f}% is above {STABLE:.1f}% but not "
            f"beyond {MARGINAL:.1f}%)")
    else:
        say(f"    VERDICT: ALIVE (spread {spread:.3f}% >> {STABLE:.1f}%)")
    say("=" * 78)
    say(f"DONE phaselag_subsets.py  n_stations={n}  beta_all={ref['beta']!r}  "
        f"spread={spread:.3f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
