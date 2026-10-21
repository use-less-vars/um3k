#!/usr/bin/env python3
"""Generate ``reference_box.kicad_pcb``: the published reference mesh, as a board.

The microstrip study is quoted on a box of ``66 x 52 x 26`` cells of ``0.400 mm``
-- ``26.4 x 20.8 x 10.4 mm`` of mesh -- carrying a ``h = 1.6 mm`` substrate of
``eps_r = 4.4``, a ``3.20 mm`` strip and a ten-cell matched layer against every
absorbing face.  Those integers *are* the mesh, and this script writes them into
a KiCad board so that they sit in a file instead of in a paragraph::

    nx = n_pml + n_ref + n_line        = 10 +  2 + 54 = 66
    ny = 2*n_pml + n_strip + 2*n_clean = 20 +  8 + 24 = 52
    nz = n_sub + n_air + n_top         =  4 + 12 + 10 = 26
    cell = h / n_sub                   = 1.6 mm / 4    = 0.400 mm

so the outline is ``66 * 0.4 = 26.4 mm`` along the line by ``52 * 0.4 = 20.8 mm``
across it, the strip is ``8 * 0.4 = 3.20 mm`` wide and centred on ``y = 10.4 mm``,
and the port plane sits ``(10 + 2) * 0.4 = 4.8 mm`` in from the ``xmin`` edge with
``54`` cells of line between it and the far wall at ``26.4 mm``, where the strip
runs out into the far absorber.

The board is deliberately bare: one ``RF_IN`` track, four ``Edge.Cuts`` lines and
a stackup that declares the dielectric.  No pads, no footprints, no zones --
there is nothing here to launch from or solder to, because the file states the
mesh and is not a coupon.  :meth:`emfit.board.MicrostripBoard.from_kicad` reads
it with no number supplied by the caller: ``h`` is the stackup total and
``eps_r`` is the core's own ``epsilon_r``, so nothing in the spec is a default in
disguise.  For that same reason the stackup declares the core and no copper or
mask thickness: what it sums to is the ``1.6 mm`` that fixes the cell size, and
KiCad's usual ``0.035 mm`` foils would make it ``1.67 mm``.

Run ``python3 generate_reference_box.py``; the output is deterministic (UUIDs are
derived from fixed names), so regenerating gives a byte-identical file.
``tests/test_reference_box.py`` holds the file to the arithmetic above.
"""

from __future__ import annotations

import os
import sys
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
PCB_NAME = "reference_box.kicad_pcb"

# ---------------------------------------------------------------------------
# 1. The published mesh, in cells
# ---------------------------------------------------------------------------

N_SUB = 4       # substrate cells across h -- this is what fixes the cell size
N_PML = 10      # matched-layer cells against every absorbing face
N_AIR = 12      # air cells above the strip
N_TOP = N_PML   # one PML carries one thickness: the lid shares the lateral one
N_STRIP = 8     # strip cells
N_CLEAN = 12    # metal-free cells between a strip edge and the lateral absorber
N_REF = 2       # cells from the port plane back to the absorber behind it
N_LINE = 54     # cells from the port plane to the far wall

NX = N_PML + N_REF + N_LINE                # 66
NY = 2 * N_PML + N_STRIP + 2 * N_CLEAN     # 52
NZ = N_SUB + N_AIR + N_TOP                 # 26

# ---------------------------------------------------------------------------
# 2. The same numbers in millimetres
# ---------------------------------------------------------------------------

CELL_MM = 0.4        # one cell, in mm
H_MM = N_SUB * CELL_MM   # 1.6 -- the substrate, and hence the cell size
EPS_R = 4.4

LENGTH_MM = NX * CELL_MM                 # 26.4, outline along the line
WIDTH_MM = NY * CELL_MM                  # 20.8, outline across it
W_MM = N_STRIP * CELL_MM                 # 3.2, strip width
X_PORT_MM = (N_PML + N_REF) * CELL_MM    # 4.8, the port plane from xmin
X_FAR_MM = LENGTH_MM                     # the strip ends in the far absorber
Y_CENTRE_MM = 0.5 * WIDTH_MM             # 10.4, the strip's centre line

NET = "RF_IN"
NET_CODE = 1

LAYERS = """  (layers
    (0 "F.Cu" signal)
    (31 "B.Cu" signal)
    (32 "B.Adhes" user "B.Adhesive")
    (33 "F.Adhes" user "F.Adhesive")
    (34 "B.Paste" user)
    (35 "F.Paste" user)
    (36 "B.SilkS" user "B.Silkscreen")
    (37 "F.SilkS" user "F.Silkscreen")
    (38 "B.Mask" user)
    (39 "F.Mask" user)
    (40 "Dwgs.User" user "User.Drawings")
    (41 "Cmts.User" user "User.Comments")
    (42 "Eco1.User" user "User.Eco1")
    (43 "Eco2.User" user "User.Eco2")
    (44 "Edge.Cuts" user)
    (45 "Margin" user)
    (46 "B.CrtYd" user "B.Courtyard")
    (47 "F.CrtYd" user "F.Courtyard")
    (48 "B.Fab" user)
    (49 "F.Fab" user)
    (50 "User.1" user)
    (51 "User.2" user)
    (52 "User.3" user)
    (53 "User.4" user)
    (54 "User.5" user)
    (55 "User.6" user)
    (56 "User.7" user)
    (57 "User.8" user)
    (58 "User.9" user)
  )"""

STACKUP = """    (stackup
      (layer "F.Cu" (type "copper"))
      (layer "dielectric 1" (type "core") (thickness %(diel).1f) (material "FR4") (epsilon_r %(eps).1f))
      (layer "B.Cu" (type "copper"))
      (copper_finish "None")
      (dielectric_constraints yes)
    )""" % dict(diel=H_MM, eps=EPS_R)


# ---------------------------------------------------------------------------
# 3. The board file
# ---------------------------------------------------------------------------

def fmt(value: float) -> str:
    """Format a millimetre value the way KiCad does (no trailing zeros)."""
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def _uuid(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "thoughtmachine/reference-box/" + name))


def verify() -> None:
    """Refuse to write a board whose arithmetic does not close."""
    if abs(CELL_MM - H_MM / N_SUB) > 1e-12:
        raise ValueError(
            f"cell = {CELL_MM} mm but h / n_sub = {H_MM} / {N_SUB} = "
            f"{H_MM / N_SUB} mm: the mesh would not be the one published")
    if (NX, NY, NZ) != (66, 52, 26):
        raise ValueError(
            f"the cell counts work out to {NX} x {NY} x {NZ}, not the published "
            f"66 x 52 x 26")
    if N_TOP != N_PML:
        raise ValueError(
            f"n_top = {N_TOP} does not match n_pml = {N_PML}: a PML carries one "
            f"thickness for every wall it opens, and nz counts the lid")
    if X_FAR_MM != LENGTH_MM:
        raise ValueError(
            f"the strip ends at {X_FAR_MM} mm but the outline is {LENGTH_MM} mm "
            f"long: the study terminates the line in the far absorber at the x "
            f"wall, so the two have to be the same plane")
    if not 0.0 < X_PORT_MM < X_FAR_MM:
        raise ValueError(
            f"the port plane at {X_PORT_MM} mm has to lie inside the line, "
            f"which runs to {X_FAR_MM} mm")
    if not W_MM < WIDTH_MM:
        raise ValueError(
            f"a {W_MM} mm strip does not fit a {WIDTH_MM} mm outline")


def board_text() -> str:
    """The ``reference_box.kicad_pcb`` file, as text."""
    parts: list[str] = []
    add = parts.append

    add('(kicad_pcb (version 20221018) (generator pcbnew)\n\n')
    add('  (general\n    (thickness %s)\n  )\n\n' % fmt(H_MM))
    add('  (paper "A4")\n')
    add(LAYERS + "\n\n")
    add('  (title_block\n')
    add('    (title "66 x 52 x 26 reference box at 0.400 mm")\n')
    add('    (rev "A")\n')
    add('    (comment 1 "h = %s mm, cell = %s mm, w = %s mm, er = %s")\n'
        % (fmt(H_MM), fmt(CELL_MM), fmt(W_MM), fmt(EPS_R)))
    add('    (comment 2 "nx %d = %d + %d + %d, ny %d = %d + %d + %d, '
        'nz %d = %d + %d + %d")\n'
        % (NX, N_PML, N_REF, N_LINE, NY, 2 * N_PML, N_STRIP, 2 * N_CLEAN,
           NZ, N_SUB, N_AIR, N_TOP))
    add('  )\n\n')

    add('  (setup\n')
    add(STACKUP + "\n")
    add('    (pad_to_mask_clearance 0.05)\n')
    add('  )\n\n')

    add('  (net 0 "")\n')
    add('  (net %d "%s")\n\n' % (NET_CODE, NET))

    # --- the strip: one straight run on the centre line --------------------
    add('  (segment (start %s %s) (end %s %s) (width %s) (layer "F.Cu") '
        '(net %d) (tstamp %s))\n\n'
        % (fmt(X_PORT_MM), fmt(Y_CENTRE_MM), fmt(X_FAR_MM), fmt(Y_CENTRE_MM),
           fmt(W_MM), NET_CODE, _uuid("strip")))

    # --- the outline: length x width, the box the counts are made of -------
    add('  (gr_line (start 0 0) (end %s 0) (layer "Edge.Cuts") (width 0.1) '
        '(tstamp %s))\n' % (fmt(LENGTH_MM), _uuid("edge/bottom")))
    add('  (gr_line (start %s 0) (end %s %s) (layer "Edge.Cuts") (width 0.1) '
        '(tstamp %s))\n' % (fmt(LENGTH_MM), fmt(LENGTH_MM), fmt(WIDTH_MM),
                            _uuid("edge/right")))
    add('  (gr_line (start %s %s) (end 0 %s) (layer "Edge.Cuts") (width 0.1) '
        '(tstamp %s))\n' % (fmt(LENGTH_MM), fmt(WIDTH_MM), fmt(WIDTH_MM),
                            _uuid("edge/top")))
    add('  (gr_line (start 0 %s) (end 0 0) (layer "Edge.Cuts") (width 0.1) '
        '(tstamp %s))\n' % (fmt(WIDTH_MM), _uuid("edge/left")))
    add(')\n')

    return "".join(parts)


def write(path: str | None = None) -> str:
    """Write the board -- next to this script unless ``path`` says otherwise."""
    target = path or os.path.join(HERE, PCB_NAME)
    with open(target, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(board_text())
    return target


def spec(path: str | None = None):
    """The spec the board encodes, read back through :mod:`emfit.board`.

    The route is the one a test takes -- ``MicrostripBoard.from_kicad`` on the
    file -- so what comes back is what the file says and not what the constants
    above say.  ``emfit`` is imported here rather than at module level to keep
    this script runnable with the standard library alone, like
    ``generate_board.py``.
    """
    from emfit.board import MicrostripBoard
    from emfit.kicad import load_board

    target = path or os.path.join(HERE, PCB_NAME)
    return MicrostripBoard.from_kicad(load_board(target), net=NET)


def main(argv: list[str] | None = None) -> int:
    """Write the board file; an optional argument overrides where it goes."""
    args = list(sys.argv[1:] if argv is None else argv)
    verify()
    print(f"wrote {write(args[0] if args else None)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
