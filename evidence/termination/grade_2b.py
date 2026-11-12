#!/usr/bin/env python3
"""Grade the termination-build artefacts against the pre-registered scope.

Nothing here runs FDTD: the inputs are the JSON artefacts written by
``evidence/termination/run_build_A.py`` and the output is a verdict per
acceptance criterion, each with the ACHIEVED value beside its pass/fail.

    python3 evidence/termination/grade_2b.py \
        evidence/termination/build_A_50ohm.json \
        evidence/termination/build_E_50ohm.json \
        evidence/termination/build_B_100ohm.json

The artefacts identify themselves (``meta.label``, ``run.kwargs.loads[0]``);
they are not identified by argument order, and no length or load value is typed
in here.  ``dL`` in AC-7 is the difference of the two artefacts' own
``s21.planes_m[1]``.

What this grader does NOT do
----------------------------
It never substitutes a proxy for a criterion the batch cannot close.  AC-4 and
the seam half of AC-5 need runs that are not in this batch (two unmatched loads;
an open control against a PML-terminated reference run in the same batch), so
they are emitted with ``achieved: None`` and ``closable_in_run_a: False``.

Bars are quoted from ``docs/design/absorbing_termination_scope.md`` and are not
adjusted here (AC-2, and the falsifier at ``:272-275``).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

# --- bars, quoted (scope section 5) ------------------------------------------
S11_BAR = 1.0e-3        # scope:235  AC-3
S21_BAR = 1.0e-3        # scope:235  AC-3
S21_TRIPWIRE = 1.0 + 1e-5   # scope:251  AC-5
BETA_REL_BAR = 1.0e-3   # scope:266-268  AC-7
GAMMA_REL_TOL = 0.03    # scope:246  AC-4

SCOPE = "docs/design/absorbing_termination_scope.md"


def load(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


_MISSING = object()


def dig(doc, path: str):
    """Fetch a dotted path (``a.b[0].c``), or ``_MISSING`` if it is absent."""
    cur = doc
    for part in path.split("."):
        index = None
        if part.endswith("]") and "[" in part:
            part, _, rest = part.partition("[")
            try:
                index = int(rest[:-1])
            except ValueError:
                return _MISSING
        if not isinstance(cur, dict) or part not in cur:
            return _MISSING
        cur = cur[part]
        if index is not None:
            if not isinstance(cur, list) or index >= len(cur):
                return _MISSING
            cur = cur[index]
    return cur


def finite_number(value):
    """``float(value)`` when it is a finite number, else ``None``.

    A NaN or an inf in an artefact is not a value to grade against: it would
    score a criterion silently.  It is reported as a problem instead.
    """
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def json_safe(value):
    return None if value is _MISSING else value


def label_of(doc: dict) -> str:
    return str(doc.get("meta", {}).get("label") or doc.get("run", {}).get("label"))


#: What an artefact written before engine provenance existed says about its step
#: engine.  NEVER ``"python"``: a document banked before
#: ``emfit.evolve.engine_report()`` was added carries no ``meta.step_engine``, and
#: a missing key means nobody recorded which path ran -- it does not mean the
#: Python path ran.  Those are different claims and only one is readable off the
#: file, so the grader reports the fact it has.
STEP_ENGINE_UNKNOWN = "unknown (pre-6cbb89d)"


def step_engine_of(doc: dict) -> str:
    """``meta.step_engine`` as written by the artefact, else the unknown marker.

    Absence is REPORTED, never inferred.  A falsy-but-present value is treated
    as absence too (\"\" or None is not a claim about the arithmetic); anything
    else is passed through verbatim, because the reader's job here is to carry
    the writer's word into the graded document, not to second-guess it.
    """
    meta = doc.get("meta")
    if not isinstance(meta, dict):
        return STEP_ENGINE_UNKNOWN
    value = meta.get("step_engine")
    if not isinstance(value, str) or not value.strip():
        return STEP_ENGINE_UNKNOWN
    return value


REQUIRED_NUMERIC = (
    "run.kwargs.h_m",
    "run.kwargs.n_strip",
    "run.kwargs.n_sub",
    "run.kwargs.n_clean",
    "run.kwargs.n_air",
    "run.kwargs.n_line",
    "geometry.cell_m",
    "geometry.f_hz",
    "s21.magnitude",
    "s21.phase_rad",
    "s21.raw_phase_rad",
    "s11.magnitude",
)


def validate(doc: dict, src: str, problems: list, warnings: list) -> bool:
    """Check every key and number this grader reads.  No exception escapes.

    Missing keys and non-finite numbers become entries in ``problems`` naming
    the artefact and the path, so the run reports what is wrong with the input
    instead of dying in a traceback (and instead of scoring a NaN silently).
    """
    ok = True
    if not label_of(doc).strip():
        problems.append(f"{src}: missing required key `meta.label` "
                        f"(or `run.label`) -- the artefact cannot be "
                        f"identified")
        ok = False

    loads = dig(doc, "run.kwargs.loads")
    if not isinstance(loads, list) or len(loads) != 1:
        if loads is _MISSING:
            found = "nothing (key absent)"
        elif isinstance(loads, list):
            found = f"{len(loads)} loads"
        else:
            found = type(loads).__name__
        problems.append(f"{src}: `run.kwargs.loads` must hold exactly one "
                        f"load; found {found}")
        ok = False
    else:
        value = dig(doc, "run.kwargs.loads[0].value")
        if value is _MISSING:
            problems.append(f"{src}: missing required key "
                            f"`run.kwargs.loads[0].value`")
            ok = False
        elif finite_number(value) is None:
            problems.append(f"{src}: `run.kwargs.loads[0].value` is not a "
                            f"finite number ({value!r})")
            ok = False

    # DR-43: an artefact whose |S21| was never measured (no cut plane -- a
    # station-span record) publishes None on every s21 numeric key rather than
    # a number nobody may publish.  The KEY must still be there; the value is
    # allowed to be null exactly when the artefact says so, and the shortfall
    # is reported as a WARNING naming the reason rather than as a problem.
    unmeasured = (dig(doc, "s21.measured") is False)
    unmeasured_reason = json_safe(dig(doc, "s21.unmeasured_reason"))
    for path in REQUIRED_NUMERIC:
        value = dig(doc, path)
        if value is _MISSING:
            problems.append(f"{src}: missing required key `{path}`")
            ok = False
        elif value is None and unmeasured and path.startswith("s21."):
            warnings.append(f"{src}: `{path}` is null because |S21| was not "
                            f"measured (s21.measured=False; "
                            f"s21.unmeasured_reason={unmeasured_reason!r}) "
                            f"-- nothing may score it (DR-43)")
        elif finite_number(value) is None:
            problems.append(f"{src}: `{path}` is not a finite number "
                            f"({value!r})")
            ok = False

    planes = dig(doc, "s21.planes_m")
    if planes is _MISSING:
        problems.append(f"{src}: missing required key `s21.planes_m`")
        ok = False
    elif not isinstance(planes, list) or len(planes) < 2:
        problems.append(f"{src}: `s21.planes_m` must list at least two cut "
                        f"positions (got {planes!r})")
        ok = False
    else:
        for i, value in enumerate(planes[:2]):
            if finite_number(value) is None:
                problems.append(f"{src}: `s21.planes_m[{i}]` is not a finite "
                                f"number ({value!r})")
                ok = False

    ac6 = dig(doc, "ac.AC-6.achieved")
    if ac6 is _MISSING:
        problems.append(f"{src}: missing required key `ac.AC-6.achieved`")
        ok = False
    elif not isinstance(ac6, dict):
        problems.append(f"{src}: `ac.AC-6.achieved` must be an object (got "
                        f"{type(ac6).__name__})")
        ok = False

    hj = dig(doc, "line.beta_model")
    if hj is _MISSING:
        warnings.append(f"{src}: optional key `line.beta_model` absent -- the "
                        f"Hammerstad comparison is reported as null")
    elif finite_number(hj) is None:
        problems.append(f"{src}: `line.beta_model` is not a finite number "
                        f"({hj!r})")
        ok = False
    return ok


def load_ohm(doc: dict) -> float:
    loads = doc["run"]["kwargs"]["loads"]
    if len(loads) != 1:
        raise SystemExit(f"{label_of(doc)}: expected exactly one load, "
                         f"found {len(loads)}")
    return float(loads[0]["value"])


def cut_mm(doc: dict) -> float:
    return float(doc["s21"]["planes_m"][1]) * 1e3


def beta_modal(artefact: dict) -> dict:
    """The AC-7 reference, computed HERE from the artefact's own geometry.

    Scope :266-268 names ``emfit.mode_profile`` explicitly, so that is what is
    called -- on the cross-section the artefact records, not on one retyped.
    The Hammerstad-Jensen number the run itself stores (``line.beta_model``) is
    reported beside it because the two closed forms do NOT agree; see
    ``reference_spread`` in the output.
    """
    import emfit.materials as materials
    import emfit.mode_profile as mode_profile
    import emfit.studies as studies

    kw = artefact["run"]["kwargs"]
    # The AC-7 reference width is the geometry the artefact RECORDS, not a
    # width re-derived from the mesh layout. ``n_strip * cell`` was circular:
    # the mesh cannot define the physical strip it is supposed to resolve, and
    # the reference moved every time the mesh was widened.
    w_m = float(artefact["geometry"]["w"])
    prof = mode_profile.microstrip_mode_profile(
        float(kw["h_m"]),
        w=w_m,
        eps_r=float(studies.MS_EPS_R),
        n_sub=int(kw["n_sub"]),
        n_clean=int(kw["n_clean"]),
        n_air=int(kw["n_air"]),
    )
    f = float(artefact["geometry"]["f_hz"])
    beta = 2.0 * math.pi * f * math.sqrt(float(prof.eps_eff)) / float(materials.C0)
    hj = artefact.get("line", {}).get("beta_model")
    return {
        "source": "emfit.mode_profile.microstrip_mode_profile (scope:266-268)",
        "beta_modal_rad_per_m": beta,
        "eps_eff": float(prof.eps_eff),
        "z0_ohm": float(prof.z0),
        "f_hz": f,
        "c0_m_per_s": float(materials.C0),
        "ms_eps_r": float(studies.MS_EPS_R),
        "w_m": w_m,
        "h_m": float(kw["h_m"]),
        "beta_hammerstad_rad_per_m": (None if hj is None else float(hj)),
    }


def wrap(rad: float) -> float:
    """Principal value, so a phase difference across a branch is not 2*pi out."""
    return math.atan2(math.sin(rad), math.cos(rad))


def grade_a(a: dict) -> dict:
    s11 = abs(complex(a["s11"]["magnitude"], 0.0))
    # DR-43: |S21| is published only when the run had a single extraction
    # plane to form it on (a cut plane).  A station-span record publishes
    # magnitude=None and says why in s21.unmeasured_reason, because that ratio
    # is a de-embedding residual and not a transmission -- grading it as
    # |S21| is the defect DR-43 records.  None is therefore READ, not
    # substituted: an unmeasured |S21| fails the bars that need it instead of
    # passing on a number nobody may publish.
    _s21_mag = a["s21"].get("magnitude")
    s21 = None if _s21_mag is None else float(_s21_mag)
    out = {}

    out["AC-3"] = {
        "bar": (f"scope:235 -- |S11| <= {S11_BAR:g} and | |S21| - 1 | <= "
                f"{S21_BAR:g}"),
        "achieved": {
            "s11_abs": s11,
            "s21_abs": s21,
            "s21_abs_minus_one": (None if s21 is None
                                  else abs(s21 - 1.0)),
            "s11_margin": S11_BAR - s11,
            "s21_margin": (None if s21 is None
                           else S21_BAR - abs(s21 - 1.0)),
        },
        "pass": bool(s11 <= S11_BAR and s21 is not None
                     and abs(s21 - 1.0) <= S21_BAR),
        "source_artefact": label_of(a),
    }
    if s21 is None:
        # Stated on the criterion, not left to be inferred from a null.
        out["AC-3"]["note"] = (
            "unmeasured: no cut plane -- the artefact publishes "
            "s21.magnitude=None with s21.unmeasured_reason set (DR-43), so "
            "the | |S21| - 1 | half of this bar has no number to score and "
            "the criterion fails rather than being skipped")

    ac6 = a["ac"]["AC-6"]
    got = ac6["achieved"]
    loaded_plane = got.get("load_plane_index")
    s21_plane = got.get("s21_plane_index")
    keys = ("load_value", "load_units", "load_kind", "load_position_mm",
            "load_plane_index", "s21_plane_index")
    out["AC-6"] = {
        "bar": ("scope:260-261 -- the run JSON carries the load specification "
                "(value, units, plane index) and the index of the plane the "
                "S-parameters were extracted from"),
        "achieved": {
            "keys_present": {k: (k in got) for k in keys},
            "load_value": got.get("load_value"),
            "load_units": got.get("load_units"),
            "load_kind": got.get("load_kind"),
            "load_position_mm": got.get("load_position_mm"),
            "load_plane_index": loaded_plane,
            "s21_plane_index": s21_plane,
            "indices_agree": bool(loaded_plane is not None
                                  and s21_plane is not None
                                  and int(loaded_plane) == int(s21_plane)),
            "s11_magnitude_present": "magnitude" in a.get("s11", {}),
        },
        "pass": bool(all(k in got and got[k] is not None for k in keys)
                     and loaded_plane is not None and s21_plane is not None
                     and int(loaded_plane) == int(s21_plane)),
        "source_artefact": label_of(a),
        "note": ("re-derived here from the artefact, not copied from the "
                 "artefact's own AC-6 verdict"),
    }

    out["AC-5"] = {
        "bar": (f"scope:251 -- no |s21| above {S21_TRIPWIRE:g} anywhere in the "
                f"batch; and the beta standard error on the open control at "
                f"least 3x smaller than the 57 on record, against a "
                f"PML-terminated reference run"),
        "achieved": {
            "s21_abs": s21,
            "tripwire": S21_TRIPWIRE,
            "headroom": (None if s21 is None else S21_TRIPWIRE - s21),
        },
        "pass": bool(s21 is not None and s21 <= S21_TRIPWIRE),
        "pass_scope": "magnitude half only",
        "closable_in_run_a": False,
        "status": ("magnitude half scored; `pass` must NOT be read as AC-5 "
                   "closed"),
    }

    out["AC-4"] = {
        "bar": ("**AC-4. The load value has to matter.** For at least two "
                "unmatched loads, `|Gamma|` within 3 % of `|R - Zc| / (R + Zc)`. "
                "The 3 % is the tolerance already recorded for the Fresnel case "
                "at `:337-339`; it is borrowed, not invented, and if it is the "
                "wrong tolerance for this quantity then that is a legitimate "
                "objection to it rather than a reason to pick another."),
        "bar_source": f"{SCOPE}:246-250",
        "achieved": None,
        "pass": None,
        "closable_in_run_a": False,
        "status": ("not closable in this batch: AC-4 needs at least two "
                   "UNMATCHED loads, and the batch carries one matched load "
                   "(50 ohm) plus one exploratory 100 ohm arm. No proxy is "
                   "substituted -- deferred to dispatch 2c."),
    }

    out["AC-5b"] = {
        "bar": ("And the `beta` standard error on the open control is reported "
                "against a PML-terminated reference run in the same batch: if it "
                "is not at least 3 times smaller than the `57` on record, the "
                "seam is not fixed, whatever `S11` says."),
        "bar_source": f"{SCOPE}:256-258",
        "achieved": None,
        "pass": None,
        "closable_in_run_a": False,
        "status": ("not closable in this batch: needs an open control AND a "
                   "PML-terminated reference run in the same batch; both runs "
                   "here are loaded and carry reference=None. Deferred to 2c."),
    }
    return out


def grade_ac7(a: dict, e: dict) -> dict:
    """beta_FDTD from TWO artefacts' raw phases, against emfit.mode_profile.

    ``beta_fdtd`` is the CROSS-RUN raw-phase slope:
    ``-wrap(raw_phase_rad[E] - raw_phase_rad[A]) / dL`` with
    ``dL = planes_m[1] of E - planes_m[1] of A``.

    ``deembedded_slope_rad_per_m`` is the same slope taken on
    ``s21.phase_rad`` instead, which is de-embedded with each run's OWN
    measured beta: ``arg(s21) = arg(t) + (beta_meas - beta_true) * d``, so it
    is flat in L only when ``beta_meas == beta_true``. Its non-zero value is
    therefore a real measured residual, not a construction artefact, and it is
    NOT the AC-7 quantity. ``deembedded_slope_expected_rad_per_m: 0.0`` is the
    conditional expectation under ``beta_meas == beta_true``, not a value the
    runs are guaranteed to meet.

    Not to be confused with an artefact's own
    ``AC-7.phase_degeneracy.deembedded_slope_rad_per_m``: that one is a
    WITHIN-RUN slope over that run's ``s21.planes_m[0..1]``, a different (also
    degenerate) number.
    """
    # DR-43: an artefact with no measured |S21| publishes null on the phases
    # too -- there is no single-plane phasor pair to take an angle of.  The
    # cross-run slope needs two of them, so this is reported as unscored
    # instead of crashing on float(None).
    if any(dig(x, "s21." + k) is None for x in (a, e)
           for k in ("phase_rad", "raw_phase_rad")):
        return {
            "bar": (f"scope:266-268 -- `beta_FDTD = -d(arg S21)/dL` from two "
                    f"line lengths; compare against `beta_modal`; "
                    f"|beta_FDTD - beta_modal| / beta_modal <= {BETA_REL_BAR:g}"),
            "achieved": None,
            "pass": None,
            "source_artefact": f"{label_of(a)} vs {label_of(e)}",
            "status": ("unscored: at least one artefact has no measured "
                       "|S21| (s21.phase_rad / s21.raw_phase_rad is null, "
                       "DR-43), so there is no phase to difference across "
                       "the two runs"),
        }
    d_l = float(e["s21"]["planes_m"][1]) - float(a["s21"]["planes_m"][1])
    raw_a = float(a["s21"]["raw_phase_rad"])
    raw_e = float(e["s21"]["raw_phase_rad"])
    de_a = float(a["s21"]["phase_rad"])
    de_e = float(e["s21"]["phase_rad"])
    d_raw = wrap(raw_e - raw_a)
    d_de = wrap(de_e - de_a)
    beta_fdtd = -d_raw / d_l
    beta_de = -d_de / d_l

    ref = beta_modal(a)
    bm = ref["beta_modal_rad_per_m"]
    rel = abs(beta_fdtd - bm) / bm
    hj = ref["beta_hammerstad_rad_per_m"]
    rel_hj = None if hj is None else abs(beta_fdtd - hj) / hj

    lam_g = 2.0 * math.pi / bm
    branch_ok = bool(d_l < 0.5 * lam_g)
    if branch_ok:
        verdict = bool(rel <= BETA_REL_BAR)
        status = ("scored" if verdict else "scored: outside the "
                  f"{BETA_REL_BAR:g} bar")
    else:
        # The raw phase difference is only known modulo 2*pi/dL; a wrapped
        # beta_FDTD must not be scored as if it were a measurement.
        verdict = None
        status = ("unscored: the raw phase difference aliases (dL >= "
                  "lambda_g/2), so beta_FDTD is only determined modulo "
                  "2*pi/dL and |beta_FDTD - beta_modal| is meaningless")

    sig = {}
    for deg in (0.1, 1.0):
        s_beta = math.radians(deg) / d_l
        sig[f"{deg:g}_deg"] = {
            "sigma_beta_rad_per_m": s_beta,
            "relative_to_bar": (s_beta / bm) / BETA_REL_BAR,
        }
    standing = 5.0e-4
    quad = math.sqrt((math.radians(0.1) / d_l / bm) ** 2 + standing ** 2)
    phase_error_that_consumes_bar_deg = math.degrees(d_l * bm * BETA_REL_BAR)

    return {
        "bar": (f"scope:266-268 -- `beta_FDTD = -d(arg S21)/dL` from two line "
                f"lengths; compare against `beta_modal` from "
                f"`emfit.mode_profile` on the same geometry; "
                f"|beta_FDTD - beta_modal| / beta_modal <= {BETA_REL_BAR:g}"),
        "which_phase": ("s21.raw_phase_rad from both artefacts: beta_FDTD = "
                        "-wrap(raw_phase_rad of E minus that of A) / dL, with "
                        "dL = s21.planes_m[1] of E minus that of A -- the "
                        "CROSS-RUN slope. NOT s21.phase_rad: that phase is "
                        "de-embedded with each run's own measured beta, so its "
                        "cross-run slope (deembedded_slope_rad_per_m below) "
                        "vanishes only if beta_meas == beta_true; a non-zero "
                        "value there is a measured residual, not a "
                        "construction artefact. The artefact's own "
                        "phase_degeneracy.deembedded_slope_rad_per_m is a "
                        "WITHIN-run slope over that run's s21.planes_m[0..1] "
                        "and is a different number."),
        "achieved": {
            "dL_m": d_l,
            "dL_from": (f"s21.planes_m[1] of {label_of(e)} minus that of "
                        f"{label_of(a)}"),
            "raw_phase_deg": [math.degrees(raw_a), math.degrees(raw_e)],
            "delta_raw_phase_rad": d_raw,
            "delta_raw_phase_deg": math.degrees(d_raw),
            "beta_fdtd_rad_per_m": beta_fdtd,
            "beta_modal_rad_per_m": bm,
            "rel_error": rel,
            "beta_modal": ref,
            "rel_error_vs_hammerstad": rel_hj,
            "deembedded_slope_rad_per_m": beta_de,
            "deembedded_slope_expected_rad_per_m": 0.0,
            "lambda_g_m": lam_g,
            "branch_unambiguous": branch_ok,
            "branch_note": ("dL must be below lambda_g/2 for the raw phase "
                            "difference to pick out one branch; lambda_g/2 = "
                            f"{0.5 * lam_g * 1e3:.4f} mm against dL = "
                            f"{d_l * 1e3:.4f} mm."),
        },
        "pass": verdict,
        "status": status,
        "reference_spread": {
            "beta_mode_profile": bm,
            "beta_hammerstad": hj,
            "relative_difference": (None if hj is None
                                    else abs(bm - hj) / hj),
            "note": ("The two closed forms do not agree at the bar's own scale. "
                     "AC-7 names emfit.mode_profile (scope:266-268), so that is "
                     "the graded reference; the Hammerstad-Jensen number is "
                     "reported beside it because a verdict that moved by more "
                     "than the bar between two admissible references is a "
                     "property of the reference, not of the phase."),
        },
        "error_budget": {
            "sigma_beta_from_phase": sig,
            "standing_wave_systematic_L": standing,
            "quadrature_total_at_0p1_deg_as_fraction_of_bar": quad,
            "phase_error_that_alone_consumes_the_bar_deg":
                phase_error_that_consumes_bar_deg,
            "statement": ("sigma_beta = radians(sigma_phase)/dL, so the budget "
                          "is comparable to the 1.0e-3 bar: at 0.1 deg the pure "
                          "phase term is 0.76 of the bar and the quadrature "
                          f"total is {quad:.3f} of it; at 1.0 deg it is 7.6x "
                          "the bar, i.e. the run cannot pass on 1 deg phase "
                          "noise. This is stated, not repaired: the bar is not "
                          "moved."),
        },
    }


def grade_b(b: dict, zc: float) -> dict:
    """The 100 ohm arm: scope:520 Ruling 3 -- exploratory, not an AC."""
    s11 = float(b["s11"]["magnitude"])
    gamma_model = abs(100.0 - zc) / (100.0 + zc)
    lo, hi = 0.30, 0.37
    return {
        "ruling": ("**Ruling 3 - 25 and 50 Ohm are graded against AC-3; 100 Ohm "
                   "is exploratory.**"),
        "bar_source": f"{SCOPE}:520",
        "exploratory": True,
        "acceptance_criterion": False,
        "achieved": {
            "s11_abs": s11,
            "gamma_model": gamma_model,
            "gamma_model_basis": f"|R - Zc| / (R + Zc) with Zc = {zc:.6f} ohm",
            "band": [lo, hi],
            "inside_band": bool(lo <= s11 <= hi),
        },
        "pass": None,
        "note": ("A band check, not a verdict: this arm may not be reported as "
                 "an AC passed or failed."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Grade the termination-build artefacts (no FDTD).")
    ap.add_argument("artefacts", nargs="+", help="artefact JSON paths")
    ap.add_argument("--out", default=None,
                    help="write the graded JSON here (default: stdout only)")
    args = ap.parse_args(argv)

    problems: list[str] = []
    warnings: list[str] = []
    docs: list[tuple[str, dict]] = []
    for path in args.artefacts:
        try:
            doc = load(path)
        except OSError as exc:
            problems.append(f"{path}: cannot read artefact "
                            f"({exc.strerror or exc.__class__.__name__})")
            continue
        except json.JSONDecodeError as exc:
            problems.append(f"{path}: not valid JSON ({exc.msg} at line "
                            f"{exc.lineno} column {exc.colno})")
            continue
        if not isinstance(doc, dict):
            problems.append(f"{path}: artefact must be a JSON object, got "
                            f"{type(doc).__name__}")
            continue
        validate(doc, path, problems, warnings)
        docs.append((path, doc))

    inputs = {}
    for path, doc in docs:
        cut = finite_number(dig(doc, "s21.planes_m[1]"))
        inputs[label_of(doc) or Path(path).name] = {
            "path": path,
            # Which arithmetic produced the graded numbers.  Absent on every
            # artefact banked before 6cbb89d -> "unknown (pre-6cbb89d)", which a
            # reader must not read as "python".
            "step_engine": step_engine_of(doc),
            "load_ohm": finite_number(dig(doc, "run.kwargs.loads[0].value")),
            "cut_mm": None if cut is None else cut * 1e3,
            "n_line": json_safe(dig(doc, "run.kwargs.n_line")),
            "cells": json_safe(dig(doc, "geometry.cells")),
            "grid": json_safe(dig(doc, "geometry.grid")),
        }

    graded: dict = {
        "schema_version": 1,
        "scope": SCOPE,
        "bars_quoted_not_adjusted": {
            "s11": S11_BAR, "s21_match": S21_BAR,
            "s21_tripwire": S21_TRIPWIRE, "beta_relative": BETA_REL_BAR,
            "gamma_relative_AC4": GAMMA_REL_TOL,
        },
        "inputs": inputs,
    }

    fifty: list[dict] = []
    hundred: list[dict] = []
    if not problems:
        by_value: dict[float, list[dict]] = {}
        for _path, doc in docs:
            by_value.setdefault(load_ohm(doc), []).append(doc)
        fifty = sorted(by_value.get(50.0, []), key=cut_mm)
        hundred = by_value.get(100.0, [])
        if len(fifty) != 2:
            problems.append(f"need exactly two 50 ohm artefacts (A and E), "
                            f"found {len(fifty)}")
        if len(hundred) > 1:
            problems.append(f"found {len(hundred)} 100 ohm artefacts")

    if not problems:
        a, e = fifty
        criteria = grade_a(a)
        ac7 = grade_ac7(a, e)
        criteria["AC-7"] = ac7
        graded["criteria"] = criteria
        if ac7.get("achieved") is None:
            # DR-43: one of the two runs has no measured |S21|, so there is no
            # cross-run phase to difference.  Reported as a problem rather
            # than crashing on a missing `achieved` block.
            problems.append("AC-7: " + str(ac7.get("status")))
        elif not ac7["achieved"]["branch_unambiguous"]:
            problems.append(
                "AC-7: dL = "
                f"{ac7['achieved']['dL_m'] * 1e3:.4f} mm is not below "
                f"lambda_g/2 = "
                f"{0.5 * ac7['achieved']['lambda_g_m'] * 1e3:.4f} mm, so the "
                "raw phase difference aliases and beta_FDTD is only known "
                "modulo 2*pi/dL; AC-7 is left unscored (pass: null) instead "
                "of being scored against a wrapped beta")
            graded["status"] = ("scored except AC-7, which is unscored: see "
                                "`problems`")
        if hundred and ac7.get("achieved") is not None:
            graded["exploratory_100ohm"] = grade_b(
                hundred[0], ac7["achieved"]["beta_modal"]["z0_ohm"])
        graded["verdict"] = {
            k: v.get("pass") for k, v in criteria.items()}

    if problems:
        graded["problems"] = problems
        graded.setdefault("status", f"unscored: {len(problems)} problem(s) in "
                                    f"the input artefacts")
    if warnings:
        graded["warnings"] = warnings

    text = json.dumps(graded, indent=2, sort_keys=True)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {out}")
    else:
        print(text)
    for msg in problems:
        print(f"problem: {msg}", file=sys.stderr)
    for msg in warnings:
        print(f"warning: {msg}", file=sys.stderr)
    v = graded.get("verdict", {})
    if v:
        print("verdict: " + "  ".join(f"{k}={v[k]}" for k in sorted(v)))
    else:
        print("verdict: unscored -- " + "; ".join(problems))
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
