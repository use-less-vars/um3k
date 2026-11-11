#!/usr/bin/env python3
"""Multifrequency station-fit beta test: A-arm geometry, one tone per DFT bin.

Dispatch: multifreq-beta-test-2026-11-07.

Hypothesis under test
---------------------
The station-fit beta used by the A arm (231.55331672912826 rad/m at
5.827786408 GHz, see docs/design/beta_refit_test_2026-11-05.md:24) sits 3.67 %
above the Hammerstad-Jensen model value (line.beta_model = 223.35306683909533
rad/m, same file :26).  If that offset is model error the extraction absorbs,
then a *frequency sweep of the same fit* must show the offset moving.  If it is
a stable bias of the estimator, it will not.

What this script is NOT
-----------------------
It does not touch ``emfit/``.  It calls the library's public entry point
``emfit.studies.microstrip_wave`` exactly as the A arm does, changing ONE
argument: ``f_target``.  It does not run on the operator's behalf: the operator
runs it (no FDTD is executed at authoring time).

The frequency knob, and why there is no broadband shortcut
----------------------------------------------------------
``microstrip_wave`` takes ``f_target`` as a plain float parameter
(emfit/studies.py:2495) and snaps it onto a DFT bin of the accumulated record:

    n_warm = nsteps // 4; n_acc = nsteps - n_warm      # studies.py:2969-2977
    span   = n_acc * dt                                # studies.py:2981
    f0     = max(1, round(f_target * span)) / span     # studies.py:2982

so the reachable frequencies are ``k / (n_acc * dt)``, k an integer, and the
only honest way to ask for a bin is to pass ``f_target`` INSIDE that bin (this
script passes ``k / span`` exactly).

The library also carries a broadband mode, ``excite="pulse"``
(emfit/studies.py:1206-1214, band 2..12 GHz over ``n_bins``), which would give
every bin from one solve.  It cannot be used here: a pulse run REFUSES
``s21_plane`` outright --

    if excite == "pulse":
        raise ValueError("s21_plane is a single-tone extraction, ...")
                                                    # studies.py:2930-2934

-- and the A arm is precisely a ``s21_plane="cut"`` run (run_build_A.py builds
``s21_plane="cut"`` into its kwargs, and every A artefact records
``s21_plane: "cut"``).  So the pulse route cannot emit the A arm's
``s21.magnitude``, and per-bin pulse metrics come from ``_bin_metrics``
(studies.py:1947), which is off the build_A artefact path.  Five single-tone
solves it is: same mesh, same stations, same load, one frequency each.

Outputs (all under evidence/termination/, named from the arm's
``artefact_prefix`` -- A: build_A_50ohm_multifreq, B: build_B_100ohm_multifreq)
-------------------------------------------------------------------------------
{artefact_prefix}_k{K}_{f:.4f}GHz.json   one per frequency, each carrying
                                        its own top-level ``dossier`` run label
{artefact_prefix}_summary.json
{artefact_prefix}_summary.md

Exit codes: 0 = all five frequencies extracted; 5 = BLOCKED (the F4 falsifier
fired: more than half the bins failed to yield a station fit or a beta).
"""
from __future__ import annotations

import argparse
import inspect
import json
import math
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
# HERE is evidence/termination, so HERE.parents[1] is the repo root holding emfit/:
# put it on the path so a plain `python3 evidence/termination/run_multifreq.py` resolves the package.
_ROOT = str(HERE.parents[1])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
ARTEFACT_PREFIX = "build_A_50ohm_multifreq"

#: The A arm's reference artefact: source of the mesh cross-check.
REFERENCE = HERE / "build_A_50ohm_p51_phasors.json"

#: The A arm's call, mirrored from run_build_A.py's ``build_kwargs``
#: (run_build_A.py:314-453) and NOT from its argparse flags: three of those
#: flags never reach the library.  ``--load-at-mm`` / ``--load-ohm`` are folded
#: into ONE ``emfit.board.Load`` and passed as ``loads`` (run_build_A.py:392,
#: :402), and ``--s21-plane-index`` is folded into ``s21_plane`` as an int
#: (run_build_A.py:408-409, and :435 for the default policy) -- neither is a
#: parameter of ``microstrip_wave`` (signature emfit/studies.py:2467-2533), so
#: a dict that carries them as keys is a TypeError, not a call.
#:
#: The values are the reference artefact's own: build_A_50ohm_p51_phasors.json
#: records meta.argv ``--n-line 64 --load-at-mm 20 --load-ohm 50
#: --s21-plane-index 51``, geometry.grid [72, 212, 22], geometry.n_sub 4,
#: n_air 12, n_top 6, n_clean 96, n_strip 8, and run.kwargs.s21_plane 51.
#: ``f_target`` is the ONLY argument this script varies; cross_check() refuses
#: if any of the mesh keys below drift from that artefact.
AARM_KWARGS = dict(
    h=1.6e-3,          # substrate thickness [m]; geometry.h 0.0016
    w=3.2e-3,          # strip width [m]; MS_W, geometry.w 0.0032
    eps_r=4.4,         # MS_EPS_R, geometry.eps_r 4.4
    n_sub=4,           # h / n_sub = 0.4 mm cell (studies.py:2586-2588)
    n_air=12,
    n_top=6,           # equals n_pml: one PML thickness (studies.py:2544)
    n_clean=96,        # ny = 2*6 + 8 + 2*96 = 212
    n_strip=8,
    n_pml=6,
    n_line=64,         # nx = 6 + 2 + 64 = 72  (p51; the older A run is 54)
    n_stations=9,
    nsteps=2400,
    dt_scale=1.0,
    keep_slice=False,
    audit=False,
    excite="cw",
    s21_plane=51,      # int: load column 50 + 1, passed explicitly (not "cut")
    reference=None,
    flux_projection=False,
)

#: The two driver-side numbers that become the ``loads`` entry in main().
#: run_build_A.py:392: Load(load_at_mm * 1e-3, "series_r", load_ohm).
LOAD_AT_MM = 20.0
LOAD_OHM = 50.0
LOAD_KIND = "series_r"


#: The B arm's dossier: the run label every B artefact carries.  ONE definition --
#: resolve_structure() hands this same string to the summary and to each per-bin
#: record, so a lone per-k file says which run it belongs to and the two can never
#: drift apart.  Pinned to the dispatch date rather than date-stamped per run: the
#: label names the sweep the evidence belongs to, so regenerating that evidence
#: reproduces the same label instead of stamping today's date on it.
DOSSIER = "multifreq-B-test-2026-11-11"


def _script_name() -> str:
    """Name of the file the operator invoked, not the module that defines main().

    A wrapper (run_multifreq_B.py) must be recorded as itself: the provenance
    record has to name the entry point the user actually ran. argv[0] is empty,
    '-c' or '-' under -c/-m invocation, where __file__ is the honest answer.
    """
    argv0 = Path(sys.argv[0]).name if sys.argv and sys.argv[0] else ""
    if argv0 in ("", "-", "-c"):
        argv0 = Path(__file__).name
    return argv0


#: Per-arm provenance, resolved ONCE per run by resolve_structure() and then
#: threaded through every place an output name, a load or a dossier is built.
#: The A entry repeats the module constants above by value -- they stay this
#: file's documented default -- and the B entry is the 100 ohm twin.
#:
#: It is a table because the alternative was tried and it lied: the arm-B sweep
#: was produced by patching ARTEFACT_PREFIX / LOAD_OHM from outside, so its
#: artefacts came out headed "A-arm", carrying the A arm's dossier, with no
#: load recorded anywhere and ``meta.argv`` naming a call that passed no load at
#: all.  A name, a load and a dossier are ONE decision; they are resolved here,
#: together, from one string.
STRUCTURES = {
    "A": {
        "load_ohm": LOAD_OHM,
        "artefact_prefix": ARTEFACT_PREFIX,
        "arm_title": "A-arm",
        "dossier_default": "multifreq-beta-test-2026-11-07",
    },
    "B": {
        "load_ohm": 100.0,
        "artefact_prefix": "build_B_100ohm_multifreq",
        "arm_title": "B-arm",
        "dossier_default": DOSSIER,
    },
}

#: k values chosen in the dispatch: 3.5 / 5.0 / 5.83 / 7.5 / 9.0 GHz asked,
#: each snapped to the nearest bin of the one record.  k = 8 is the existing
#: single-frequency point (5.827786408 GHz), kept as the harness check.
K_VALUES = (5, 7, 8, 10, 12)

FIELDS = (
    "s11.magnitude",
    "s11.magnitude_one_wave_station_fit",
    "s11.phase_deg",
    "s21.magnitude",
    "s21.phase_deg",
    "station_fit.beta",
    "station_fit.z0_re",
    "station_fit.z0_im",
    "line.beta",
    "line.beta_model",
    "line.eps_eff_model",
)


def _finite(value, what, errors):
    """``float(value)``, or ``None`` with ``what`` appended to ``errors``.

    JSON has no NaN: ``json.dumps`` writes the bare token ``NaN``, which
    ``json.loads`` reads back but no comparison can then touch.  A gap is
    therefore written as ``null`` AND named in ``errors``, so that a row with a
    hole in it can never be read as a row with a value.
    """
    if value is None:
        errors.append(f"{what}: absent from the result")
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        errors.append(f"{what}: not a real number ({value!r})")
        return None
    if not math.isfinite(out):
        errors.append(f"{what}: not finite ({value!r})")
        return None
    return out


def _complex_field(value, what, errors):
    """``complex(value)``, or ``None`` with ``what`` appended to ``errors``."""
    try:
        return complex(value)
    except (TypeError, ValueError):
        errors.append(f"{what}: not a complex number ({value!r})")
        return None


def _deg(value):
    """``arg(value)`` in degrees, by hand: there is no numpy on this path."""
    return math.degrees(math.atan2(value.imag, value.real))


def resolve_reference(path):
    """The path ``--reference`` should actually be read from.

    A bare filename is what an operator types from the repo root, but the
    artefact lives beside this script, so a bare name that is not in the
    working directory resolves to ``HERE / name``.  Anything that already
    resolves -- including a CWD-relative path with a directory component -- is
    returned untouched; anything else is returned as given, so the caller's
    own absent-file handling decides what to do with it.
    """
    path = Path(path)
    if path.exists():
        return path
    if path.parent == Path(".") and (HERE / path.name).exists():
        return HERE / path.name
    return path


def filter_kwargs(kwargs, func):
    """Split ``kwargs`` into what ``func`` accepts and what it does not.

    A key that is missing from ``inspect.signature(func).parameters`` is a
    driver-side knob some other file folds in before the call (see
    AARM_KWARGS above).  Dropping it with a printed note turns a TypeError at
    the call into a warning at the call site, which is the difference between
    "the sweep ran" and "the sweep never started".

    Returns:
        ``(kept, dropped)`` -- two new dicts; ``kwargs`` is not modified.
    """
    accepted = set(inspect.signature(func).parameters)
    kept, dropped = {}, {}
    for key, value in kwargs.items():
        (kept if key in accepted else dropped)[key] = value
    if dropped:
        print(f"NOTE: dropping {sorted(dropped)} -- not parameters of "
              f"{getattr(func, '__name__', func)}; they are folded in by the "
              f"caller (run_build_A.py:392-435), not passed to the library",
              file=sys.stderr)
    return kept, dropped


def unloaded_kwargs(kwargs):
    """Turn ``kwargs`` into the load-free arm: no element, no cut plane.

    The two are one decision, because the library ties them: a record with no
    load has no cut plane to name, so ``s21_plane`` must be ``None`` there.
    ``emfit/studies.py:2920``-``:2925`` is the guard that says so -- asked for
    a plane on a load-free record it raises ``ValueError`` ("s21_plane was
    asked for on a load-free record: there is no cut for it to name.  Leave it
    None, which measures the station span a load-free run wants.") -- and
    ``None`` is also the value a load-free run wants: the station span, not
    the loaded arm's column 51.

    Returns:
        ``kwargs`` itself, modified: ``loads`` dropped if present,
        ``s21_plane`` set to ``None``.
    """
    kwargs.pop("loads", None)
    kwargs["s21_plane"] = None
    return kwargs


def cross_check(kwargs, reference=None):
    """Assert this script's mesh is the reference artefact's mesh.

    Cheap, and it is the only thing standing between "a sweep of the A arm"
    and "a sweep of some other microstrip".  Missing reference file is a
    warning, not a failure: the operator may run this on a machine where the
    artefact was not copied over.  ``reference`` is ``--reference``: left
    empty it is the module constant above, so a run without the flag reads
    exactly the file it always read.
    """
    ref_path = REFERENCE if reference is None else resolve_reference(reference)
    if not ref_path.exists():
        print(f"WARNING: {ref_path.name} absent, mesh cross-check skipped",
              file=sys.stderr)
        return {"checked": False, "reason": "reference artefact absent"}
    ref = json.loads(ref_path.read_text())
    geom = ref.get("geometry", {})
    dt = float(geom.get("dt", 0.0))
    diffs = {}
    for key in ("h", "w", "eps_r", "n_sub", "n_air", "n_top", "n_clean",
                "n_strip", "n_pml", "n_line"):
        want = geom.get(key)
        got = kwargs.get(key)
        if want is not None and got is not None and abs(float(want) - float(got)) > 0:
            diffs[key] = {"reference": want, "this_script": got}

    # The station count is stored under no key called ``n_stations``: the
    # fitted count is ``s11.station_phasors.n`` (9 on the reference) and
    # ``geometry.station_fit_n`` is that count minus every station dropped for
    # sitting on a load column (8 there, one load).  The loop above used to
    # compare ``n_stations``, got ``None``, and skipped in silence -- the guard
    # was one key short on every artefact ever written.  Absent under BOTH
    # names is an error now, not a pass.
    got_n = kwargs.get("n_stations")
    phasors_n = ref.get("s11", {}).get("station_phasors", {})
    if "n" in phasors_n:
        want_n = int(phasors_n["n"])
        basis = "s11.station_phasors.n"
    elif "station_fit_n" in geom:
        want_n = int(geom["station_fit_n"]) + 1
        basis = "geometry.station_fit_n + 1 (the load-column station)"
    else:
        raise SystemExit(
            f"REFUSED: {ref_path.name} records no station count under "
            "s11.station_phasors.n or geometry.station_fit_n; the station "
            "count cannot be confirmed and is not skipped in silence")
    if got_n is None:
        raise SystemExit(
            f"REFUSED: this script passes no n_stations, so its station count "
            f"cannot be compared against {ref_path.name}'s {want_n} ({basis})")
    if want_n != int(got_n):
        diffs["n_stations"] = {"reference": want_n, "this_script": int(got_n),
                               "basis": basis}
    if diffs:
        raise SystemExit(f"REFUSED: mesh does not match {ref_path.name}: {diffs}")
    n_acc = int(geom.get("n_acc", 0)) or None
    return {"checked": True, "reference": ref_path.name, "dt_s": dt,
            "n_acc": n_acc, "n_warm": geom.get("n_warm"),
            "nsteps": geom.get("nsteps"), "cell_m": geom.get("cell"),
            "n_stations": want_n, "n_stations_basis": basis}

def extract(result):
    """Per-frequency row out of one MicrostripWave result.

    Every field is Optional by design: a bin where the station fit did not
    close must be recorded as a gap, not patched, because a patched row is how
    an F4 falsifier gets laundered into an F1.  Each gap is NAMED in
    ``row["errors"]``, and a row carrying any error is not a complete row.

    The mapping is the A arm's own, read off the returned object rather than
    off a serialised dict: ``microstrip_wave`` returns a ``MicrostripWave``
    dataclass (emfit/studies.py:1585-1651), so there is no ``result.s11`` block
    (the reflection is the complex ``result.gamma_port`` / ``result.gamma``),
    ``result.s21`` is a complex number and not a dict with a ``magnitude`` key,
    and the ``line`` / ``run`` blocks below are what run_build_A.py writes into
    the artefact, not fields of the result.  Every source index is
    run_build_A.py's: :1518-1530 for the wave quantities, :1655-1722 for
    ``s21``, :1723-1730 for ``s11``, :1769-1801 for ``line``.
    """
    geom = dict(getattr(result, "geometry", {}) or {})
    errors = []

    # --- the complex numbers every field below is derived from --------------
    # run_build_A.py:1518-1527.
    gamma = _complex_field(getattr(result, "gamma", None), "gamma", errors)
    gamma_port = _complex_field(getattr(result, "gamma_port", None),
                                "gamma_port", errors)
    s21 = _complex_field(getattr(result, "s21", None), "s21", errors)
    station_fit = getattr(result, "station_fit", None)

    row = {
        "f_hz_used": _finite(geom.get("f"), "geometry.f", errors),
        "f_hz_asked": _finite(geom.get("f_target"), "geometry.f_target", errors),
        "beta_ambiguous": geom.get("beta_ambiguous"),
        "n_acc": _finite(geom.get("n_acc"), "geometry.n_acc", errors),
        "dt_s": _finite(geom.get("dt"), "geometry.dt", errors),
    }

    # --- s11: two estimators, and they are not the same number --------------
    # magnitude is the TWO-WAVE fit (run_build_A.py:1527, ``abs(res.gamma)``);
    # magnitude_one_wave_station_fit and phase_deg are the ONE-WAVE reflection
    # referred to the port plane (run_build_A.py:1525-1526, ``res.gamma_port``,
    # declared emfit/studies.py:1608).  Conflating them is the classic way a
    # reflection gets quoted twice as if it were a cross-check.
    row["s11.magnitude"] = (None if gamma is None else
                            _finite(abs(gamma), "s11.magnitude", errors))
    row["s11.magnitude_one_wave_station_fit"] = (
        None if gamma_port is None else
        _finite(abs(gamma_port), "s11.magnitude_one_wave_station_fit", errors))
    row["s11.phase_deg"] = (None if gamma_port is None else
                            _finite(_deg(gamma_port), "s11.phase_deg", errors))

    # --- station fit: the beta it was handed, and its impedance -------------
    if station_fit is None:
        # A record with no station fit has no beta_used and no z0: both are
        # gaps, and the row must say so (the F4 falsifier counts on it).
        errors.append("station_fit: the fit did not run (result.station_fit "
                      "is None)")
        row["station_fit.beta"] = None
        row["station_fit.beta_two"] = None
        row["station_fit.z0_re"] = None
        row["station_fit.z0_im"] = None
    else:
        # beta_used: StationFit.beta, falling back to res.beta when the fit was
        # skipped (run_build_A.py:675-678).  On this HEAD it equals
        # beta_two_wave, because emfit/studies.py:3387 repoints ``beta`` to the
        # two-wave fit before the station fit is called -- the artefact's
        # s11.station_phasors.beta_used, i.e. 231.55331672912826 on p51.
        beta_used = _finite(getattr(station_fit, "beta", None),
                            "station_fit.beta", errors)
        if beta_used is None:
            beta_used = _finite(getattr(result, "beta", None),
                                "station_fit.beta (fallback res.beta)", errors)
        row["station_fit.beta"] = beta_used
        row["station_fit.beta_two"] = _finite(
            getattr(result, "beta_two_wave", None),
            "station_fit.beta_two", errors)
        # A fit that did not close carries ``z0 = complex(nan, nan)``
        # (studies.py:1843 _blank_station_fit), which is a missing number and
        # not a zero: run_build_A.py:1573-1579 emits it as null on that test.
        z0 = _complex_field(getattr(station_fit, "z0", None),
                            "station_fit.z0", errors)
        if z0 is None:
            row["station_fit.z0_re"] = None
            row["station_fit.z0_im"] = None
        else:
            row["station_fit.z0_re"] = _finite(z0.real, "station_fit.z0_re",
                                               errors)
            row["station_fit.z0_im"] = _finite(z0.imag, "station_fit.z0_im",
                                               errors)

    # --- s21: the transmission as came out of the extraction plane ----------
    # run_build_A.py:1655-1722: ``complex(res.s21)``, magnitude and phase.
    row["s21.magnitude"] = (None if s21 is None else
                            _finite(abs(s21), "s21.magnitude", errors))
    row["s21.phase_deg"] = (None if s21 is None else
                            _finite(_deg(s21), "s21.phase_deg", errors))

    # --- line: the phase constant and the closed forms ----------------------
    # run_build_A.py:1769-1801.  eps_eff_model is MicrostripWave.eps_eff_model
    # (emfit/studies.py:1619, filled at :3965 from
    # emfit.microstrip.Microstrip.eps_eff, the same Hammerstad-Jensen closed
    # form that gives beta_model): a top-level attribute, NOT a member of any
    # ``line`` block -- that dict is this script's construction, not the
    # library's.
    row["line.beta"] = _finite(getattr(result, "beta", None), "line.beta",
                               errors)
    row["line.beta_model"] = _finite(getattr(result, "beta_model", None),
                                     "line.beta_model", errors)
    row["line.eps_eff_model"] = _finite(getattr(result, "eps_eff_model", None),
                                        "line.eps_eff_model", errors)

    # The one-line human summary, straight off the record (run_build_A.py:1804).
    try:
        row["summary_line"] = result.summary()
    except Exception as exc:                          # noqa: BLE001
        errors.append(f"summary_line: {type(exc).__name__}: {exc}")
        row["summary_line"] = None

    # beta_model is the closed form this sweep is measured against.  Its own
    # falsifier: a missing model value makes the comparison undefined.
    bm = row["line.beta_model"]
    if bm:
        row["beta_model_over_omega"] = None  # beta_model already rad/m
    bb = row["station_fit.beta"]
    if bb is not None and bm:
        row["delta_beta_rad_m"] = float(bb) - float(bm)
        row["delta_beta_frac"] = (float(bb) - float(bm)) / float(bm)
    else:
        row["delta_beta_rad_m"] = None
        row["delta_beta_frac"] = None
    row["errors"] = errors
    return row


def resolve_structure(structure_id, load_ohm=None, artefact_prefix=None,
                      dossier=None):
    """Resolve one run's provenance: the STRUCTURES row, then the flags.

    A ``None`` flag means "unset, take the arm's default", so ``--structure B``
    alone is a complete, self-describing B run.  Returns a plain dict; nothing
    here mutates a module global, and nothing downstream reads one back.
    """
    spec = STRUCTURES[structure_id]
    return {
        "structure_id": structure_id,
        "load_ohm": float(spec["load_ohm"] if load_ohm is None else load_ohm),
        "artefact_prefix": (spec["artefact_prefix"]
                            if artefact_prefix is None else artefact_prefix),
        "arm_title": spec["arm_title"],
        "dossier": spec["dossier_default"] if dossier is None else dossier,
        "title": f"{spec['arm_title']} multifrequency beta sweep",
    }


def load_provenance(prov, unloaded):
    """The load numbers as they belong in a kwargs record.

    ``loads`` is an object, not a library keyword (see the comment in main()),
    so the numbers that built it are written into the kwargs record by hand: a
    meta that cannot say which load a record came from is exactly how an arm-B
    run passed for arm A.  A load-free run records none of them.
    """
    if unloaded:
        return {"load_ohm": None, "load_kind": None, "load_at_mm": None}
    return {"load_ohm": float(prov["load_ohm"]), "load_kind": LOAD_KIND,
            "load_at_mm": LOAD_AT_MM}


def row_status(row):
    """One word for a bin: failed > incomplete > ambiguous > ok.

    ``failed`` is a raise, ``incomplete`` a record with named gaps, and
    ``ambiguous`` a station fit whose beta wrapped (``beta_ambiguous``): three
    different failures, and a report must not merge them.
    """
    if row.get("error"):
        return "failed"
    if row.get("errors"):
        return "incomplete"
    if row.get("beta_ambiguous"):
        return "ambiguous"
    return "ok"


def write_summary(rows, summary):
    load_txt = ("none" if summary.get("load_ohm") is None
                else f"{summary['load_ohm']:g} ohm")
    md = [
        f"# {summary['title']}",
        "",
        "Generated by `evidence/termination/run_multifreq.py`.",
        "",
        f"Structure {summary['structure_id']} ({summary['arm']}): "
        f"load {load_txt}, dossier `{summary['dossier']}`, "
        f"generated {summary['generated_utc']}.",
        "",
        f"Record length: nsteps={summary['cross_check'].get('nsteps')}, "
        f"n_acc={summary['cross_check'].get('n_acc')}, "
        f"dt={summary['cross_check'].get('dt_s')} s -> "
        f"bin spacing {summary['bin_spacing_mhz']:.4f} MHz",
        "",
        "| k | asked (GHz) | used (GHz) | beta_fit (rad/m) | beta_model | "
        "d_beta/beta | \\|S11\\| | \\|S21\\| | status |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        # The status column is the row's OWN status (row_status(), stored on the
        # row): the .md and the .json must never disagree about a bin.
        status = r.get("status") or row_status(r)
        if status == "failed":
            md.append(f"| {r['k']} | {r['f_ghz_asked']:.4f} | - | - | - | - "
                      f"| - | - | FAILED: {r['error']} |")
            continue
        db = r.get("delta_beta_frac")
        # A row with named gaps is never "ok": the status column is what a
        # reader skims, so it carries the gaps rather than hiding them.
        if status == "incomplete":
            status = "INCOMPLETE: " + "; ".join(r.get("errors") or [])
        md.append(
            f"| {r['k']} | {r['f_ghz_asked']:.4f} | {r['f_ghz_used']:.6f} | "
            f"{_f(r.get('station_fit.beta'), 4)} | "
            f"{_f(r.get('line.beta_model'), 4)} | "
            f"{'n/a' if db is None else format(100 * db, '+.3f') + ' %'} | "
            f"{_f(r.get('s11.magnitude'), 6)} | "
            f"{_f(r.get('s21.magnitude'), 6)} | {status} |")
    (HERE / f"{summary['artefact_prefix']}_summary.md").write_text(
        "\n".join(md) + "\n")
    (HERE / f"{summary['artefact_prefix']}_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return "\n".join(md)


def _f(value, nd):
    return "n/a" if value is None else f"{float(value):.{nd}f}"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--k", type=int, nargs="*", default=list(K_VALUES),
                    help="DFT-bin indices to run (default 5 7 8 10 12)")
    ap.add_argument("--mem-ceiling-mb", type=float, default=3000.0,
                    help="pre-flight only: refuse to start a batch whose "
                         "single-run high-water mark would not fit (the trip "
                         "itself lives in run_build_A.py, not here)")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the five planned calls and exit: no FDTD")
    ap.add_argument("--structure", choices=sorted(STRUCTURES), default="A",
                    help="arm this run IS: its load, output prefix, .md "
                         "heading and default dossier (default A)")
    ap.add_argument("--load-ohm", type=float, default=None,
                    help="series-R load in ohm (default: the --structure's "
                         "own value -- 50 for A, 100 for B)")
    ap.add_argument("--artefact-prefix", default=None,
                    help="output filename prefix (default: the --structure's "
                         "own -- build_A_50ohm_multifreq / "
                         "build_B_100ohm_multifreq)")
    ap.add_argument("--dossier", default=None,
                    help="dossier string recorded in the summary (default: "
                         "the --structure's own)")
    ap.add_argument("--reference", type=Path, default=REFERENCE,
                    help="artefact the mesh cross-check compares against "
                         "(default: build_A_50ohm_p51_phasors.json beside "
                         "this script; not microstrip_wave's ``reference`` "
                         "kwarg)")
    ap.add_argument("--no-cross-check", action="store_true",
                    help="skip the mesh cross-check: for a twin arm whose "
                         "reference geometry is not the loaded arm's, which "
                         "is the condition the guard exists to refuse.  dt "
                         "and n_acc still come from --reference, so the bin "
                         "grid does not move")
    ap.add_argument("--unloaded", action="store_true",
                    help="omit the ``loads`` entry, i.e. run the arm with no "
                         "series-R load.  --load-ohm sets that load's value "
                         "instead of removing it, so when both are given "
                         "--unloaded wins and the run records no load")
    args = ap.parse_args(argv)
    # One provenance record for the whole run: --structure fills the load, the
    # output prefix, the .md heading and the dossier, and an explicit flag
    # overrides its own field only.  Nothing below patches a module global.
    prov = resolve_structure(args.structure, args.load_ohm,
                             args.artefact_prefix, args.dossier)
    prefix = prov["artefact_prefix"]

    import json as _json
    if args.no_cross_check:
        # The guard is skipped, not the numbers: the bin grid is defined by the
        # artefact's own dt and n_acc, and skipping a guard must not move a bin.
        # With the guard off there is nothing left to raise: a --reference that
        # does not exist falls back to the module constant for dt and n_acc
        # (and, if that is absent too, leaves dt unset so the ``if not dt``
        # refusal below still decides, rather than a traceback here).
        grid_path = resolve_reference(args.reference)
        if not grid_path.exists():
            print(f"WARNING: {grid_path.name} absent, bin grid falling back "
                  f"to {REFERENCE.name}", file=sys.stderr)
            grid_path = REFERENCE
        geom = (_json.loads(grid_path.read_text()).get("geometry", {})
                if grid_path.exists() else {})
        cross = {"checked": False,
                 "reason": "cross-check skipped by --no-cross-check",
                 "reference": args.reference.name,
                 "dt_nacc_source": grid_path.name,
                 "dt_s": float(geom.get("dt", 0.0)),
                 "n_acc": int(geom.get("n_acc", 0)) or None}
    else:
        cross = cross_check(AARM_KWARGS, args.reference)
    dt = cross.get("dt_s")
    if not dt:
        raise SystemExit("REFUSED: no dt available to define the bin grid; "
                         "pass the reference artefact beside this script")

    import emfit.studies as studies
    from emfit.board import Load

    # Drop anything the library does not take (nothing here, today: the three
    # driver-only keys left AARM_KWARGS when it was corrected to the p51 call)
    # and say so rather than raising TypeError five times inside the loop.
    kwargs_base, dropped = filter_kwargs(AARM_KWARGS, studies.microstrip_wave)
    n_acc = cross.get("n_acc") or AARM_KWARGS["nsteps"] - AARM_KWARGS["nsteps"] // 4
    span = n_acc * float(dt)
    bin_hz = 1.0 / span
    start_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # The plan is built from the same kwargs the loop will pass below, so a
    # flag that changes the call cannot leave the printed plan saying
    # something else.  With no flag this is AARM_KWARGS by value, unchanged.
    plan_kwargs = dict(AARM_KWARGS)
    if args.unloaded:
        plan_kwargs = unloaded_kwargs(plan_kwargs)
    plan_kwargs.update(load_provenance(prov, args.unloaded))

    if args.dry_run:
        print(_json.dumps({
            "cross_check": cross,
            "bin_spacing_hz": bin_hz,
            "resolved": dict(
                prov,
                script=_script_name(),
                artefacts=[f"{prefix}_k{k}_{k / span / 1e9:.4f}GHz.json"
                           for k in args.k]
                + [f"{prefix}_summary.json", f"{prefix}_summary.md"]),
            "calls": [{"k": k, "f_hz": k / span, "kwargs_hint": plan_kwargs}
                      for k in args.k], }, indent=2, sort_keys=True))
        return 0

    rows = []
    for k in args.k:
        f_target = k / span                     # ON the bin, not near it
        kwargs = dict(kwargs_base)
        kwargs["f_target"] = f_target
        # ``loads`` is the one place a driver flag became an object rather than
        # a keyword: run_build_A.py:392 builds Load(load_at_mm*1e-3,
        # "series_r", load_ohm) and passes it under this name
        # (studies.py:2503).  A list of tuples is not a Load and would not run.
        # --unloaded drops the element AND the cut plane the loaded arm measures
        # across: one decision, not two (unloaded_kwargs(); and
        # emfit/studies.py:2920-:2925 for the library's own reason -- a
        # load-free record has no cut to name, and ``None`` measures the
        # station span a load-free run wants).  The same driver, a bare line.
        # --load-ohm changes the value HERE rather than removing the entry, and
        # the value used is the RESOLVED one (--structure B -> 100 ohm), never
        # the module constant read back at this line: patching LOAD_OHM from
        # outside is what left the arm-B artefacts with no load on record.
        if args.unloaded:
            kwargs = unloaded_kwargs(kwargs)
        else:
            kwargs["loads"] = [Load(LOAD_AT_MM * 1e-3, LOAD_KIND,
                                    prov["load_ohm"])]
        row = {"k": k, "f_hz_asked": f_target,
               "f_ghz_asked": f_target / 1e9}
        started = time.monotonic()
        try:
            result = studies.microstrip_wave(**kwargs)
            row.update(extract(result))
            row["f_ghz_used"] = (row["f_hz_used"] or f_target) / 1e9
            out = HERE / (f"{prefix}_k{k}_"
                          f"{row['f_ghz_used']:.4f}GHz.json")
            # ``argv`` is the PROCESS command line (the wrapper's, when one is
            # used) and ``main_argv`` what main() was actually handed; the load
            # numbers go INTO ``kwargs`` because they are not a library kwarg
            # and would otherwise be recorded nowhere at all.
            meta_kwargs = {kk: vv for kk, vv in kwargs.items()
                           if kk not in ("loads", "reference")}
            meta_kwargs.update(load_provenance(prov, args.unloaded))
            # ``dossier`` is a TOP-level key, not another entry in ``meta``: a
            # single per-bin file handed to a reader has to say which sweep it
            # belongs to, and it is prov["dossier"] -- the very string the
            # summary is stamped with -- so the two cannot disagree.  The dump
            # sorts its keys, so on disk it lands after "artefact_keys".
            out.write_text(_json.dumps(
                {"meta": {"script": _script_name(), "k": k,
                          "started_utc": start_utc,
                          "structure_id": prov["structure_id"],
                          "arm": prov["arm_title"],
                          "load_ohm": meta_kwargs["load_ohm"],
                          "argv": list(sys.argv[1:]),
                          "main_argv": (list(sys.argv[1:]) if argv is None
                                        else list(argv)),
                          "kwargs": meta_kwargs},
                 "dossier": prov["dossier"],
                 "row": row,
                 "artefact_keys": sorted(k2 for k2 in dir(result)
                                         if not k2.startswith("_"))},
                indent=2, sort_keys=True, default=str) + "\n")
            row["artefact"] = out.name
        except Exception as exc:                      # noqa: BLE001
            row["error"] = f"{type(exc).__name__}: {exc}"
            row["traceback"] = traceback.format_exc(limit=4)
        row["status"] = row_status(row)
        row["wall_s"] = round(time.monotonic() - started, 2)
        rows.append(row)
        gaps = row.get("errors") or []
        print(f"k={k} f={row.get('f_ghz_used', row['f_ghz_asked']):.6f} GHz "
              f"beta={_f(row.get('station_fit.beta'), 4)} "
              f"model={_f(row.get('line.beta_model'), 4)}"
              + ("" if not row.get("error") else f"  FAILED {row['error']}")
              + ("" if not gaps else f"  INCOMPLETE {gaps}"),
              file=sys.stderr)

    summary = {
        "dossier": prov["dossier"],
        "title": prov["title"],
        "structure_id": prov["structure_id"],
        "arm": prov["arm_title"],
        "load_ohm": (None if args.unloaded else float(prov["load_ohm"])),
        "artefact_prefix": prefix,
        "started_utc": start_utc,
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cross_check": cross,
        "bin_spacing_hz": bin_hz,
        "bin_spacing_mhz": bin_hz / 1e6,
        "k_values": list(args.k),
        "rows": rows,
        # A bin that RAISED and a bin that returned a record with a hole in it
        # are both bins without a station fit: the F4 count takes either.  The
        # split is kept beside it so a report can tell the two apart.
        "failures": sum(1 for r in rows if r.get("error") or r.get("errors")),
        "raised": sum(1 for r in rows if r.get("error")),
        "incomplete": sum(1 for r in rows if r.get("errors")),
    }
    # "ok" is a claim about the RUN, so it is only made when all three counters
    # are zero; otherwise the status names the counters that fired.
    summary["status"] = "ok"
    if summary["failures"] or summary["incomplete"] or summary["raised"]:
        summary["status"] = "not_ok: " + ", ".join(
            f"{name}={summary[name]}" for name in
            ("failures", "incomplete", "raised") if summary[name])
    write_summary(rows, summary)
    if summary["failures"] * 2 > len(rows):
        print("BLOCKED: the F4 falsifier fired -- more than half the bins did "
              "not yield a station fit. No bracket is scored from this run.",
              file=sys.stderr)
        return 5
    return 0


if __name__ == "__main__":
    sys.exit(main())
