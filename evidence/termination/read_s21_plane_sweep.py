#!/usr/bin/env python3
"""Read the Build A s21-plane sweep: one row per extraction column.

Each rung is an artefact of its own (run_s21_plane_sweep.sh passes --out
explicitly, because run_build_A.py names its output only from that flag):

    evidence/termination/build_A_50ohm_p<col>_plane.json

Two reference numbers make the columns comparable to what was already
recorded, and both are quoted, never recomputed here:

  * 0.245108            -- the two-wave fit's |Gamma| at alpha = 11.255 Np/m
                          IMPOSED (docs/design/voltage_integration_and_
                          reflection_2026-11-08.md:82,:90).  |s11| is divided
                          by it.  It is NOT the port -- the record's port
                          value is s11.magnitude = 0.32586326001662264, which
                          is the SAME fit at alpha = 0 (docs/design/upstream-
                          extraction-2026-11-08.md:96-117) -- so a column near
                          1.33x is the port sitting above the attenuation-
                          imposed fit, not a disagreement about |s11|.
  * 0.04390825210124855 -- gamma_plane.abs of the p51 ghost-wave artefact,
                          the same file this sweep writes for col 51.  That
                          documented fit is 5.58x larger, so a rung whose
                          ratio is far from 5.58 is a rung where the recorded
                          plane does not reproduce the documented figure.

Nothing here raises on missing data: an absent file or key prints MISSING.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ARTEFACT = "evidence/termination/build_A_50ohm_p{col}_plane.json"
COLS = (50, 51, 52, 53, 54)

# The denominator of the |s11|/ref column.  It is the two-wave fit with alpha
# imposed, not the port reflection: the two differ by 1.33x on this record and
# the difference is the imposed attenuation, not a defect in either number
# (see the docstring).
REF_S11 = 0.245108                     # two-wave fit |Gamma| (see docstring)
REF_GAMMA_PLANE = 0.04390825210124855  # p51 ghost-wave gamma_plane.abs
MISSING = "MISSING"


def _dig(payload, *path):
    """Walk a key path; None if any hop is absent or the wrong type."""
    node = payload
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node


def _num(value):
    """The value as a float, or None -- bools and strings are not numbers."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _ratio(num, den):
    if num is None or not den:
        return None
    return num / den


def _cell(value, spec="%.6f"):
    return MISSING if value is None else spec % value


def read_row(col):
    """(path, payload) for one rung, or (path, None) when it cannot be read."""
    path = REPO / ARTEFACT.format(col=col)
    try:
        with path.open("r", encoding="utf-8") as handle:
            return path, json.load(handle)
    except (OSError, ValueError):
        return path, None


def row_cells(col, payload):
    if payload is None:
        return [str(col)] + [MISSING] * 6
    gamma = _dig(payload, "gamma_plane")
    gp_abs = _num(_dig(gamma, "abs"))
    gp_arg = _num(_dig(gamma, "arg_deg"))
    s11 = _num(_dig(payload, "s11", "magnitude"))
    s21 = _num(_dig(payload, "s21", "magnitude"))
    plane = _num(_dig(payload, "s21", "s21_plane_index"))
    return [
        str(col),
        _cell(plane, "%d") if plane is not None else MISSING,
        _cell(gp_abs),
        _cell(gp_arg, "%+.3f"),
        _cell(s11),
        _cell(s21),
        _cell(_ratio(s11, REF_S11), "%.2fx"),
        _cell(_ratio(gp_abs, REF_GAMMA_PLANE), "%.2fx"),
    ]


HEADER = ("col", "plane", "|gamma_plane|", "arg_deg", "|s11|", "|s21|",
          "|s11|/ref", "|gp|/ref")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    cols = [int(a) for a in argv] if argv else list(COLS)
    rows = []
    for col in cols:
        path, payload = read_row(col)
        if payload is None:
            print("note: %s %s" % (MISSING, path))
        rows.append(row_cells(col, payload))

    widths = [len(h) for h in HEADER]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    print("  ".join(h.rjust(w) for h, w in zip(HEADER, widths)))
    for row in rows:
        print("  ".join(c.rjust(w) for c, w in zip(row, widths)))
    print("")
    print("plane          = s21.s21_plane_index the run actually extracted on")
    print("|s11|          = s11.magnitude (the TWO-WAVE modulus, not the "
          "one-wave station fit)")
    print("|s11|/ref      = |s11| / %g (two-wave fit, see docstring)" % REF_S11)
    print("|gp|/ref       = |gamma_plane| / %r (p51 recorded plane)"
          % REF_GAMMA_PLANE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
