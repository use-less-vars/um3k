#!/usr/bin/env python3
"""attribution.py -- is the analytic-internal eps_eff gap estimator bias, or placement?

The number under study is one cell of ``.scratch/s10118_result.txt``: the
``[analytic]`` row's beta, 309.9818636706751 rad/m (:167, eps_eff 3.5648002823688385
at :168), against the converged profile's 300.498268 rad/m (pair A, eps_eff
3.3500085193372118, ``docs/design/zfree_diagnosis.md:163``).  B/A is +3.16 % on
beta and +6.41 % on eps -- one number, not two (:166).

The estimator that produces that cell is named exactly, because the study is
about *that* estimator and no other:

    v = modal_station_phasors(..., PANA, ...)     analytic-basis phasors
    z = D["plane_station_x"]                      the archive's nine stations
    beta = emfit.ports.fit_beta(z, v).beta        n_wave=1, the library default

i.e. ``.scratch/logs/s10118_basis.py:402-414`` (``measure(PANA, "analytic")``) via
``emfit/modal.py:modal_line_quantities`` -> ``emfit/modal.py:575`` ->
``ModalLine.beta`` (``emfit/modal.py:506-508``), with eps_eff = (beta c0 / omega)**2
(``emfit/modal.py:578``).  The eigen-route row the same script writes to
``OUT["mode"]`` (``s10118_basis.py:206-216``, beta = sqrt(best_bs) = 312.7827646323)
is a different number and is *not* the cell attributed here.

Two mechanisms, and only two:

    (a) estimator bias -- the one-wave model is too small for the record it is
        fitted to.  The analytic-basis phasors do carry a backward wave: that
        record's own diagnostics are mode_purity 0.0139, passivity 1.0143 and
        amplitude_mismatch_max 1.49e4 (``.scratch/s10118_result.txt:165, :170-171``), and
        a one-wave fit then reports a beta the data does not have; or
    (b) placement-induced distortion -- the mode is converged on a box of its own
        (431x217, eps_eff 3.35001, ``emfit/mode_profile.py:586-590``) and then
        *placed* on the FDTD lattice by index offset
        (``ModeProfile.plane_window``); a box sized to the plane "would be 4-5 %
        high" (``mode_profile.py:591``).  The beta is then not mis-estimated, it
        belongs to another cross-section.

Branch (a) is *bounded* here, not assumed: phantoms of known beta are fitted four
ways over the archive's own station window with |Gamma| and the interference
phase swept, and the largest beta a one-wave fit can return at |Gamma| = 1 (the
passivity bound) is compared with the gap that has to be explained.  Branch (b)
cannot be bounded from arithmetic: it needs a record whose generating beta is
known, hence ``--phantom`` / ``--archive``.  A phantom whose beta is not its
label is the observable form of (b), not a third mechanism.

Four estimators, in the order ``run.sh:8-9`` names them:

    one-wave      emfit.ports.fit_beta(z, v)                 n_wave=1  <- the cell
    two-wave      emfit.ports.fit_beta(z, v, n_wave=2)
    two-station   phase difference across the two end stations
    phase-slope   least-squares slope of the unwrapped station phase

Only the first is the estimator under test (``emfit/modal.py:575``).  The last
two are not fits at all, so a model that is too small cannot bias them: they are
the control.  A gap that all four show is in the data; a gap that only the
one-wave fit shows is in the model.

Narrow by design: no solver, no solver output, no file written, ``emfit`` only
imported (``fit_beta``, which is the thing under test, and ``C0`` for the
frequency).

Output goes to stdout only (run.sh tees it to out/run.log).  Exit status is 0
for a completed study and 2 for an unusable input record.

CLI:  --quick  --phantom PATH  --archive PATH  --n-phase N  --units {m,mm}
      --label-tol FLOAT
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

import numpy as np

# ---------------------------------------------------------------------------
# repo layout: this file lives at <repo>/tools/host/attribution/attribution.py,
# which is THREE levels below the repository root, and `python3 /path/to/this.py`
# puts only *this* directory on sys.path -- never the root.  run.sh discovers
# the root and exports it as C1_REPO, but the interpreter does not inherit it,
# so the `import emfit` below died with ModuleNotFoundError (out/run.log:3).
# The root is resolved by tools/host/_bootstrap.py -- the one copy the sibling
# host scripts share (c1-audit/c1_audit.py, phaselag-subsets/phaselag_subsets.py,
# c1-audit/pecbox_variant.py) -- and put on sys.path BEFORE any emfit import.
# Never count ".." levels: a fixed count yields <repo>/tools instead of <repo>,
# which is exactly how the import failed.  The remaining traps live in that
# module's docstring.
# ---------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
from _bootstrap import bootstrap  # noqa: E402

#: REPO is primary; C1_REPO is the alias run.sh still exports (see _bootstrap).
REPO = bootstrap(start=HERE)

from emfit.materials import C0  # noqa: E402
from emfit.ports import fit_beta  # noqa: E402

# --- constants: every one is a quoted literal, with its locator -------------
K0 = 164.17940719617263
# rad/m.  `K0 = m2.k0_from_freq(F0)` at .scratch/logs/s10118_basis.py:117.

EPS_A = 3.3500085193372118
# eps_eff of the converged profile box; .scratch/logs/corr_ez_followup.txt:22,
# key `eps_eff`, section "1. ANALYTIC REFERENCE".  Printed as 3.3500085193 at
# docs/design/zfree_diagnosis.md:163 ("pair A").

BETA_A = K0 * math.sqrt(EPS_A)
# rad/m.  Not a measurement: zfree_diagnosis.md:163 prints 300.4980 and the
# exact product is 300.498268 (reports/2026-10-26_23-56-24...:25).  Recomputed
# from K0 and EPS_A so that pair A stays closed under eps = (beta/k0)**2.

BETA_B = 309.9818636706751
EPS_B = 3.5648002823688385
# pair B: `results.analytic` of the s10118 table, .scratch/s10118_result.txt:167
# and :168 (printed as 309.981864 / 3.564800282 at zfree_diagnosis.md:164).  Both
# come from the one fit: eps_eff = (beta c0 / omega)**2, emfit/modal.py:578 --
# NOT beta_sq/K0**2, which is the mixed solver's own mode row (s10118_basis.py:216,
# written to OUT["mode"], beta 312.7827646323, s10118_result.txt:128-135).

BETA_FIT = 326.9107654423116
EPS_FIT = 3.964798
# the fit route's own pair (placed 31x17, post-repair), quizzed only as context:
# docs/design/zfree_diagnosis.md:171.

Z_WINDOW = (0.0104, 0.020)
# m.  "station planes 0.0104..0.020", .scratch/logs/s10118_basis.py:54.

STATION_X = (0.0104, 0.0116, 0.0128, 0.014, 0.0152, 0.0164, 0.0176, 0.0188, 0.02)
# m.  The archive's own nine station planes, quoted from
# .scratch/s10118_result.txt:208-218 (`results.analytic.station_x`, identical to
# `results.mixed.station_x` at :267-277): 0.0104 + 0.0012 k, ref_plane 0.0104,
# ruled plane x_port 0.0087 (:220).  These are the positions the [analytic] beta
# was fitted on, so part 2 samples the phantom where the record was sampled.

N_STATIONS = (9, 10, 11, 12, 13)
# run.sh:13, "9- to 13-station fit_beta calls".  N = 9 is the archive's own count
# (STATION_X); 10-13 fill the same window uniformly, which is a sensitivity
# probe, not something the archive contains.

GAMMA_MAX = 3.0
# search bound for |Gamma| in the inversion, not a claim about anything.

TOL_LABEL = 1.0e-3
# relative beta tolerance that counts as "the label matches the data".

_CALLS = [0]


def _fit(z, v, n_wave):
    """fit_beta with a call counter (the driver advertises ~1000 calls)."""
    _CALLS[0] += 1
    return fit_beta(z, v, n_wave=n_wave)


def fit_one(z, v):
    return _fit(z, v, 1)


def fit_two(z, v):
    return _fit(z, v, 2)


def est_two_station(z, v):
    """beta from the phase difference of the two end stations: no model, no fit."""
    dz = float(z[-1] - z[0])
    b = -float(np.angle(v[-1] * np.conj(v[0]))) / dz
    if b <= 0.0:
        b += 2.0 * math.pi / dz
    return b


def est_phase_slope(z, v):
    """beta from the least-squares slope of the unwrapped station phase."""
    ph = np.unwrap(np.angle(v))
    b = -float(np.polyfit(z, ph, 1)[0])
    if b <= 0.0:
        b += 2.0 * math.pi / float(np.min(np.diff(z)))
    return b


def phantom(beta, z, g_abs, g_phase):
    """Known-beta phantom: one forward and one backward travelling wave."""
    return np.exp(-1j * beta * z) + g_abs * np.exp(1j * g_phase) * np.exp(1j * beta * z)


def stations(n):
    """The archive's own planes when n is 9; a uniform fill of the same window else."""
    if n == len(STATION_X):
        return np.asarray(STATION_X, dtype=float)
    return np.linspace(Z_WINDOW[0], Z_WINDOW[1], n)


def pct(x):
    return "%+.3f %%" % (100.0 * (x - 1.0))


def banner(title):
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


# ---------------------------------------------------------------------------
# 1. the two pairs: one number each, not two
# ---------------------------------------------------------------------------
def audit():
    target = BETA_B / BETA_A
    banner("1. THE TWO ANALYTIC PAIRS ARE ONE NUMBER EACH")
    print("  k0 = %.17g rad/m   ->  f0 = k0 c / 2 pi = %.6f GHz"
          % (K0, K0 * C0 / (2.0 * math.pi) / 1.0e9))
    print("  lambda at beta_A = %.6f m; the station window is %.6f m = %.3f lambda"
          % (2.0 * math.pi / BETA_A, Z_WINDOW[1] - Z_WINDOW[0],
             (Z_WINDOW[1] - Z_WINDOW[0]) / (2.0 * math.pi / BETA_A)))
    print()
    print("  pair  beta [rad/m]       eps            (beta/k0)^2     rel. dev")
    for name, beta, eps in (("A  ", BETA_A, EPS_A), ("B  ", BETA_B, EPS_B),
                            ("fit", BETA_FIT, EPS_FIT)):
        back = (beta / K0) ** 2
        print("  %s  %-17.12g %-14.10g %-15.10g %+.1e"
              % (name, beta, eps, back, back / eps - 1.0))
    print()
    print("  B/A on eps  : %s  (%.10g / %.10g)" % (pct(EPS_B / EPS_A), EPS_B, EPS_A))
    print("  B/A on beta : %s  (sqrt of the line above; %.9f)" % (pct(target), target))
    print("  fit/A, fit/B on beta (context only): %s, %s"
          % (pct(BETA_FIT / BETA_A), pct(BETA_FIT / BETA_B)))
    print()
    print("  The eps gap and the beta gap are one number, so a mechanism that")
    print("  explains 3.16 %% on beta explains 6.41 %% on eps.  Not two findings.")
    print()
    print("  GAP TO ATTRIBUTE (run.sh:5) = B/A on beta = %.9f  ->  %s" % (target, pct(target)))
    print()
    print("  the [analytic] cell is produced by emfit.ports.fit_beta(z, v), n_wave=1,")
    print("  on the analytic-basis station phasors (s10118_basis.py:402-414 ->")
    print("  emfit/modal.py:575), stations .scratch/s10118_result.txt:208-218.")
    return target


# ---------------------------------------------------------------------------
# 2+3. what a passive backward wave can do to the one-wave fit
# ---------------------------------------------------------------------------
def sweep(n_phase, quick):
    phases = np.linspace(0.0, 2.0 * math.pi, n_phase, endpoint=False)
    coarse = ((0.3, 0.5, 0.75, 1.0, 1.5, GAMMA_MAX) if quick else
              (0.0, 0.25, 0.5, 0.75, 1.0, 2.0, GAMMA_MAX))

    banner("2. HOW FAR A BACKWARD WAVE MOVES THE ONE-WAVE FIT -- THE BOUND ON (a)")
    print("  v(z) = exp(-j beta z) + Gamma exp(+j beta z), beta = beta_A = %.9f rad/m" % BETA_A)
    print("  estimator under test: emfit.ports.fit_beta(z, v), n_wave=1 -- exactly the")
    print("  call .scratch/logs/s10118_basis.py:402-414 makes on the analytic-basis")
    print("  phasors (emfit/modal.py:575).  The phantom stands in for those phasors.")
    print("  %d-%d stations over [%.4f, %.4f] m; N = %d is the archive's own grid"
          % (N_STATIONS[0], N_STATIONS[-1], Z_WINDOW[0], Z_WINDOW[1], len(STATION_X)))
    print("  (.scratch/s10118_result.txt:208-218), 10-13 a uniform fill of the same window;")
    print("  %d interference phases over [0, 2pi)" % n_phase)
    print("  |Gamma| grid: %s" % " ".join("%.2f" % g for g in coarse))
    print()
    print("  self-check, |Gamma| = 0: every estimator must return beta_A unchanged")
    worst = 0.0
    for n in N_STATIONS:
        z = stations(n)
        v = phantom(BETA_A, z, 0.0, 0.0)
        rel = (fit_one(z, v).beta / BETA_A - 1.0, fit_two(z, v).beta / BETA_A - 1.0,
               est_two_station(z, v) / BETA_A - 1.0, est_phase_slope(z, v) / BETA_A - 1.0)
        worst = max(worst, max(abs(r) for r in rel))
        print("    N=%-3d one-wave %+.1e  two-wave %+.1e  two-station %+.1e  phase-slope %+.1e"
              % ((n,) + rel))
    print("    largest |relative deviation| seen: %.1e" % worst)
    print()
    print("  one-wave fit, ratio beta_fit / beta_A, worst and best interference phase")
    print("  %-3s %-7s %-12s %-12s %-12s" % ("N", "|Gamma|", "min ratio", "max ratio",
                                             "at phase 0"))
    best = (float("-inf"), None, None)
    bound_passive = float("-inf")
    for n in N_STATIONS:
        z = stations(n)
        for g in coarse:
            lo = hi = at0 = None
            for i, ph in enumerate(phases):
                r = fit_one(z, phantom(BETA_A, z, g, ph)).beta / BETA_A
                if i == 0:
                    at0 = r
                lo = r if lo is None else min(lo, r)
                hi = r if hi is None else max(hi, r)
            print("  %-3d %-7.2f %-12.6f %-12.6f %-12.6f" % (n, g, lo, hi, at0))
            if hi > best[0]:
                best = (hi, n, g)
            if abs(g - 1.0) < 1.0e-12:
                bound_passive = max(bound_passive, hi)
        print()
    print("  most favourable family: N=%d, |Gamma| = %.2f, ratio %.6f" % (best[1], best[2], best[0]))
    print("  PASSIVITY BOUND: at |Gamma| = 1 the one-wave fit can be moved by at most %s"
          % pct(bound_passive))

    # dense scan on that family only: the smallest |Gamma| that reaches the gap
    banner("3. THE SMALLEST BACKWARD WAVE THAT WOULD MANUFACTURE THE GAP")
    n_family = best[1]
    z = stations(n_family)
    dense = np.linspace(0.0, GAMMA_MAX, 7 if quick else 13)
    print("  N = %d stations over [%.4f, %.4f] m; |Gamma| refined to %d nodes"
          % (n_family, Z_WINDOW[0], Z_WINDOW[1], dense.size))
    print("  %-7s %-12s %-12s %s" % ("|Gamma|", "max ratio", "residual", "gap reached?"))
    target = BETA_B / BETA_A
    g_star = None
    resid_star = None
    for g in dense:
        hi = float("-inf")
        hi_fit = None
        for ph in phases:
            f = fit_one(z, phantom(BETA_A, z, g, ph))
            if f.beta / BETA_A > hi:
                hi, hi_fit = f.beta / BETA_A, f
        print("  %-7.3f %-12.6f %-12.6f %s" % (g, hi, hi_fit.residual,
                                               "yes" if hi >= target else "no"))
        if g_star is None and hi >= target:
            g_star, resid_star = float(g), float(hi_fit.residual)
    print()
    if g_star is None:
        print("  No |Gamma| up to %.1f reaches %s on this family." % (GAMMA_MAX, pct(target)))
    else:
        print("  Smallest |Gamma| reaching %s: %.3f (residual there %.4f)."
              % (pct(target), g_star, resid_star))
    print()
    print("  Limits of this bound: noiseless; uniform stations; one backward wave at")
    print("  the same |beta|; one mode.  A reflected dominant-mode wave is exactly")
    print("  this family, so the bound binds on it; it says nothing about a record")
    print("  where a *different* |beta| contributes (a higher-order or evanescent")
    print("  component), which is the two-wave fit's problem, not the one-wave's.")
    return dict(bound_passive=bound_passive, g_star=g_star, resid_star=resid_star,
                n_family=n_family)


# ---------------------------------------------------------------------------
# 4. verdict
# ---------------------------------------------------------------------------
def verdict(target, bound_passive, g_star, resid_star, n_family):
    banner("4. VERDICT")
    print("  gap to attribute: B/A = %s on beta = %s on eps (one number, part 1)"
          % (pct(target), pct(EPS_B / EPS_A)))
    print()
    print("  (a) estimator bias in fit_beta(z, v), n_wave=1 (emfit/ports.py:861)")
    alive = bound_passive >= target
    if alive:
        print("      ALIVE.  A passive backward wave moves the one-wave fit by up to")
        print("      %s on %d stations, which covers the %s gap." % (pct(bound_passive), n_family,
                                                                    pct(target)))
        if g_star is not None:
            print("      Smallest |Gamma| that reaches it: %.3f (worst phase), leaving" % g_star)
            print("      residual %.4f.  A record whose own fit residual is far below" % resid_star)
            print("      that cannot be this phantom -- the residual is the discriminator.")
    elif g_star is not None:
        print("      DEAD for a passive line.  At |Gamma| = 1 the fit moves by at most")
        print("      %s, short of the %s needed.  Reaching it takes |Gamma| = %.3f,"
              % (pct(bound_passive), pct(target), g_star))
        print("      i.e. a reflection coefficient above unity -- no passive section")
        print("      produces that (the phantom's residual there is %.4f)." % resid_star)
    else:
        print("      DEAD across the whole search: no |Gamma| up to %.1f moves the" % GAMMA_MAX)
        print("      one-wave fit as far as %s (most favourable family, %d stations)."
              % (pct(target), n_family))
    print()
    print("  (b) placement-induced distortion")
    print("      The converged box (431x217, eps_eff 3.35001, emfit/mode_profile.py:586-")
    print("      590) is placed on the FDTD lattice by index offset, and a box sized to")
    print("      the plane would be 4-5 % high (:591).  Not decidable from arithmetic:")
    print("      it needs a record whose generating beta is known.  Part 5 decides it")
    print("      for --phantom / --archive and nothing else here does.  A phantom whose")
    print("      beta is not its label is the observable form of this branch, not a")
    print("      third mechanism.")
    print("      Scale to compare: emfit/mode_profile.py:591 quotes 4-5 % on eps for a")
    print("      box sized to the plane, i.e. 2.0-2.5 %% on beta, against the %s on beta"
          % pct(target))
    print("      to explain -- the same order, quoted rather than computed, and the")
    print("      reason (b) is the reading that survives if (a) is excluded.")
    print()
    print("  Consequences")
    if alive:
        print("      (a) is not excluded, so a gap reproduced on a real record with a")
        print("      fitted residual of order %s must be read against the phantom"
              % ("n/a" if resid_star is None else "%.2f" % resid_star))
        print("      before the two constructions are compared.")
    else:
        print("      With (a) excluded on this family, the gap cannot be an artefact of")
        print("      fitting one wave over this window.  If a known-beta record also")
        print("      reproduces its label (part 5), the gap lives in which beta each")
        print("      pair actually is -- the two constructions (converged box versus")
        print("      placed basis, emfit/mode_profile.py:591) -- not in the estimator.")


# ---------------------------------------------------------------------------
# 5. the same cross-check on a real record (--phantom / --archive)
# ---------------------------------------------------------------------------
def load_record(path, units):
    scale = 1.0 if units == "m" else 1.0e-3
    if path.endswith(".npz"):
        with np.load(path, allow_pickle=False) as d:
            keys = set(d.files)
            zk = "z" if "z" in keys else ("station_x" if "station_x" in keys else None)
            if zk is None or "v" not in keys:
                raise SystemExit("record %s: need 'z' (or 'station_x') and 'v'" % path)
            z = np.asarray(d[zk], dtype=float).ravel()
            v = np.asarray(d["v"]).ravel().astype(complex)
            label = float(d["beta_label"]) if "beta_label" in keys else None
    elif path.endswith(".json"):
        with open(path, "r", encoding="utf-8") as fh:
            d = json.load(fh)
        zk = "z" if "z" in d else ("station_x" if "station_x" in d else None)
        if zk is None or "v" not in d:
            raise SystemExit("record %s: need 'z' (or 'station_x') and 'v'" % path)
        z = np.asarray(d[zk], dtype=float).ravel()
        v = np.asarray([complex(x) for x in d["v"]], dtype=complex)
        label = float(d["beta_label"]) if "beta_label" in d else None
    else:
        raise SystemExit("record %s: expected .npz or .json" % path)
    z = z * scale
    span = float(z.max() - z.min())
    if span > 0.5:
        print("  WARNING span %.6g m looks like millimetres -- try --units mm" % span)
    return dict(z=z, v=v, beta_label=label, source=path, span=span)


def cross_check(rec, label_tol):
    z, v = rec["z"], rec["v"]
    if z.size < 4:
        print("  %d stations: too few for the four-way read (needs 4)" % z.size)
        return
    one, two = fit_one(z, v), fit_two(z, v)
    lam = 2.0 * math.pi / one.beta
    print("  %d stations, span %.6g m = %.3f lambda; residual of the one-wave fit %.4f"
          % (z.size, rec["span"], rec["span"] / lam, one.residual))
    print("  %-12s %-18s %-10s" % ("estimator", "beta [rad/m]", "vs one-wave"))
    for name, b in (("one-wave", one.beta), ("two-wave", two.beta),
                    ("two-station", est_two_station(z, v)), ("phase-slope", est_phase_slope(z, v))):
        print("  %-12s %-18.9g %+.3f %%" % (name, b, 100.0 * (b / one.beta - 1.0)))
    print("  two-wave |gamma| = %.4f (read as an order of magnitude: the window is %.2f"
          % (abs(two.gamma), rec["span"] / lam))
    print("  lambda wide, and emfit/ports.py:887-897 warns for that regime)")
    if rec["beta_label"] is None:
        print()
        print("  no beta_label: this record cannot decide branch (b).  It shows whether")
        print("  the four estimators agree, which they cannot on a phantom whose beta")
        print("  differs from its label only if the disagreement is a fit artefact.  Read it")
        print("  this way: agreement across all four is a beta the data carries, and")
        print("  disagreement confined to the two fits is the one-wave model's own shape.")
        return
    label = rec["beta_label"]
    dev = one.beta / label - 1.0
    print()
    print("  label %.9g rad/m; one-wave fit %s against it (tolerance %.1e)"
          % (label, pct(dev), label_tol))
    if abs(dev) <= label_tol:
        print("  DECIDES (b) for this record: the estimator reproduces the known beta,")
        print("  so on this record the estimator is not biased and the gap is not its.")
    else:
        print("  DECIDES (a) for this record: the fit does NOT reproduce the known beta,")
        print("  so the one-wave model is too small here and (a) is real, not hypothetical.")


def section_records(args):
    if not (args.phantom or args.archive):
        return
    banner("5. RECORDS (the only part that can decide branch (b), or falsify (a))")
    for kind, path in (("phantom, known beta", args.phantom),
                       ("archive, no known truth", args.archive)):
        if not path:
            continue
        print()
        print("  --- %s: %s ---" % (kind, path))
        try:
            rec = load_record(path, args.units)
        except SystemExit as exc:
            print("  %s" % exc)
            continue
        cross_check(rec, args.label_tol)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Attribute the 6.41 %% eps_eff gap to (a) bias in "
                    "emfit.ports.fit_beta(z, v) (n_wave=1) or (b) placement of the "
                    "converged profile.  Read-only: no solver, no writes.")
    ap.add_argument("--phantom", metavar="PATH",
                    help="known-beta phantom record (.npz/.json: z, v[, "
                         "beta_label]) -- decides (b) for that record")
    ap.add_argument("--archive", metavar="PATH",
                    help="FDTD station record (.npz/.json: z, v[, i])")
    ap.add_argument("--units", choices=("m", "mm"), default="m",
                    help="units of the loaded positions (default: m, as fit_beta "
                         "expects)")
    ap.add_argument("--label-tol", type=float, default=TOL_LABEL,
                    help="relative beta tolerance that counts as 'the label "
                         "matches the data' (default %.1e)" % TOL_LABEL)
    ap.add_argument("--n-phase", type=int, default=24,
                    help="reflection-phase sweep resolution (default 24)")
    ap.add_argument("--quick", action="store_true",
                    help="coarser sweeps, a fraction of the cost")
    args = ap.parse_args(argv)

    if args.n_phase < 2:
        ap.error("--n-phase must be at least 2")

    target = audit()
    out = sweep(args.n_phase, args.quick)
    verdict(target, out["bound_passive"], out["g_star"], out["resid_star"], out["n_family"])
    section_records(args)

    banner("COST")
    print("  fit_beta calls: %d (n_phase %d, %s)" % (_CALLS[0], args.n_phase,
                                                    "quick" if args.quick else "full"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
