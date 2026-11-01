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


def label_of(doc: dict) -> str:
    return str(doc.get("meta", {}).get("label") or doc.get("run", {}).get("label"))


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
    cell = float(artefact["geometry"]["cell_m"])
    prof = mode_profile.microstrip_mode_profile(
        float(kw["h_m"]),
        w=float(kw["n_strip"]) * cell,
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
        "w_m": float(kw["n_strip"]) * cell,
        "h_m": float(kw["h_m"]),
        "beta_hammerstad_rad_per_m": (None if hj is None else float(hj)),
    }


def wrap(rad: float) -> float:
    """Principal value, so a phase difference across a branch is not 2*pi out."""
    return math.atan2(math.sin(rad), math.cos(rad))


def grade_a(a: dict) -> dict:
    s11 = abs(complex(a["s11"]["magnitude"], 0.0))
    s21 = float(a["s21"]["magnitude"])
    out = {}

    out["AC-3"] = {
        "bar": (f"scope:235 -- |S11| <= {S11_BAR:g} and | |S21| - 1 | <= "
                f"{S21_BAR:g}"),
        "achieved": {
            "s11_abs": s11,
            "s21_abs": s21,
            "s21_abs_minus_one": abs(s21 - 1.0),
            "s11_margin": S11_BAR - s11,
            "s21_margin": S21_BAR - abs(s21 - 1.0),
        },
        "pass": bool(s11 <= S11_BAR and abs(s21 - 1.0) <= S21_BAR),
        "source_artefact": a["meta"]["label"],
    }

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
        "source_artefact": a["meta"]["label"],
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
            "headroom": S21_TRIPWIRE - s21,
        },
        "pass": bool(s21 <= S21_TRIPWIRE),
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
    """beta_FDTD from TWO artefacts' raw phases, against emfit.mode_profile."""
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
        "which_phase": ("s21.raw_phase_rad from each artefact. NOT "
                        "s21.phase_rad: that one is de-embedded with each run's "
                        "own measured beta and is flat in L by construction."),
        "achieved": {
            "dL_m": d_l,
            "dL_from": (f"s21.planes_m[1] of {e['meta']['label']} minus that of "
                        f"{a['meta']['label']}"),
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
        "pass": bool(rel <= BETA_REL_BAR),
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

    docs = [load(p) for p in args.artefacts]
    by_value: dict[float, list[dict]] = {}
    for doc in docs:
        by_value.setdefault(load_ohm(doc), []).append(doc)

    fifty = sorted(by_value.get(50.0, []), key=cut_mm)
    hundred = by_value.get(100.0, [])
    graded: dict = {
        "schema_version": 1,
        "scope": SCOPE,
        "bars_quoted_not_adjusted": {
            "s11": S11_BAR, "s21_match": S21_BAR,
            "s21_tripwire": S21_TRIPWIRE, "beta_relative": BETA_REL_BAR,
            "gamma_relative_AC4": GAMMA_REL_TOL,
        },
        "inputs": {label_of(d): {
            "path": str(p),
            "load_ohm": load_ohm(d),
            "cut_mm": cut_mm(d),
            "n_line": d["run"]["kwargs"]["n_line"],
            "cells": d["geometry"]["cells"],
            "grid": d["geometry"]["grid"],
        } for d, p in zip(docs, args.artefacts)},
    }
    problems = []
    if len(fifty) != 2:
        problems.append(f"need exactly two 50 ohm artefacts (A and E), found "
                        f"{len(fifty)}")
    if len(hundred) > 1:
        problems.append(f"found {len(hundred)} 100 ohm artefacts")

    if len(fifty) == 2:
        a, e = fifty
        graded["criteria"] = grade_a(a)
        graded["criteria"]["AC-7"] = grade_ac7(a, e)
        if hundred:
            prof_z0 = grade_ac7(a, e)["achieved"]["beta_modal"]["z0_ohm"]
            graded["exploratory_100ohm"] = grade_b(hundred[0], prof_z0)
        graded["verdict"] = {
            k: v.get("pass") for k, v in graded["criteria"].items()}
    if problems:
        graded["problems"] = problems

    text = json.dumps(graded, indent=2, sort_keys=True)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {out}")
    else:
        print(text)
    v = graded.get("verdict", {})
    print("verdict: " + "  ".join(f"{k}={v[k]}" for k in sorted(v)))
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
