#!/usr/bin/env python3
"""Generate the 5.8 GHz microstrip coupon board.

The script is deliberately dependency-free (standard library only) and writes:

  * ``kicad_support_project.kicad_pcb``  -- KiCad 7 board file (format 20221018),
    self-contained: every footprint is embedded, only the three small libraries
    shipped in ``footprints/`` were used.
  * ``kicad_support_project.kicad_pro``  -- project file with the design rules
    (netclass clearance, copper-to-edge clearance, minimum track/via sizes).
  * ``fp-lib-table``                     -- so KiCad picks up ``footprints/``.

Run ``python3 generate_board.py`` and then ``python3 check_board.py``.

Geometry
--------
Everything is a function of the constants below; ``verify()`` re-derives the
pad positions from the connector's own pad table and refuses to write a board
that violates the clearance rule.  The output is deterministic (UUIDs are
derived from fixed names), so regenerating gives a byte-identical file.

Coordinate system: millimetres, board origin at the top-left corner of the
outline, Y increasing downwards (KiCad's own convention).  The line runs along
y = TRACE_Y from the left edge-launch to the right one.
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
import tempfile
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = "kicad_support_project"

# ---------------------------------------------------------------------------
# 1. Board and design-rule parameters
# ---------------------------------------------------------------------------

BOARD_W = 70.0  # mm, outline width
BOARD_H = 20.0  # mm, outline height
BOARD_T = 1.6   # mm, finished thickness (2 layers, 1 oz copper)
TRACE_Y = 10.0  # mm, centre line of the microstrip

W_MAIN = 3.0    # mm, line width in the launch-free middle section
W_NECK = 2.0    # mm, width where the line squeezes between the SMA ground pads
W_PAD = 0.64    # mm, the 0402 land height - the narrow end of the break taper

SMA_PAD_INSET = 4.5  # mm, J1 pad 1 from the left board edge (set by the part)
X_LEFT = SMA_PAD_INSET
X_RIGHT = BOARD_W - SMA_PAD_INSET

NECK_LEN = 2.5          # mm, constant-width neck next to each SMA
SMA_CLR_MARGIN = 0.05   # mm, extra clearance kept to the SMA ground pads
MAX_STAIR = 0.15        # mm, longest staircase step in a width taper

X_BREAK = BOARD_W / 2.0   # mm, centre of the series 0402 break
PAD_PITCH = 0.51          # mm, R_0402_1005Metric land centres at +/-0.51
PAD_HALF_W = 0.27         # mm, land half width (0.54 wide lands)
BREAK_TAPER_LEN = 2.0     # mm, W_MAIN -> W_PAD transition
STUB_OVERLAP = 0.10       # mm, narrow stub reaches this far into the land

# No stitching vias: the top layer carries nothing but the 50 ohm line, so a
# via would land on bare substrate and reach the bottom pour on one layer only --
# DRC says exactly that (``via_dangling``) and it is right.  The connector
# grounds are the four through-hole pads of each SMA, which already reach the
# pour; there is no second layer of copper to stitch to.
VIA_POS: list[tuple[float, float]] = []
VIA_SIZE = 0.8   # kept for the design rules written into the .kicad_pro
VIA_DRILL = 0.4

CLEARANCE = 0.2   # mm, netclass clearance the geometry is validated against
EDGE_CLEAR = 0.25  # mm, copper to board edge
KEEPOUT_OFFSET = 4.8  # mm, "no top copper pour within this of the trace edge"

SUBSTRATE_H = 1.51  # mm, dielectric between F.Cu and B.Cu (1.6 mm overall, 1 oz)
COPPER_T = 0.035    # mm, 1 oz
EPS_R = 4.4
EPS_R_ALT = 4.6     # mm, upper bound used for the tolerance note in the README

# Nets ---------------------------------------------------------------------
NET = {0: "", 1: "GND", 2: "RF_IN", 3: "RF_OUT"}
N_GND, N_IN, N_OUT = 1, 2, 3

# Upper half of the trace plan, left to right; the right half is the mirror
# image about x = BOARD_W/2 (the board is symmetric by construction).
PAD_L_OUTER = X_BREAK - PAD_PITCH - PAD_HALF_W   # 34.22 mm
PAD_R_OUTER = X_BREAK + PAD_PITCH + PAD_HALF_W   # 35.78 mm
X_NECK_END_L = X_LEFT + NECK_LEN                 # 7.00 mm
X_BREAK_TAPER_L = PAD_L_OUTER - BREAK_TAPER_LEN   # 32.22 mm
# The end of the launch taper is not a free parameter: it is where the
# clearance envelope around the SMA ground pads finally admits W_MAIN.  It is
# computed from the footprint pad table by ``env_taper()`` below.

# J1 / J2 placements.  The SMA footprint draws its mating face at local y=0 and
# its board edge at local y=-4.5, so rotating +90 puts the edge on x=0.
J1 = dict(ref="J1", lib="Connector_Coaxial:SMA_Amphenol_901-143_Horizontal",
          value="SMA", x=X_LEFT, y=TRACE_Y, rot=90.0,
          file="Connector_Coaxial.pretty/SMA_Amphenol_901-143_Horizontal.kicad_mod")
J2 = dict(ref="J2", lib="Connector_Coaxial:SMA_Amphenol_901-143_Horizontal",
          value="SMA", x=X_RIGHT, y=TRACE_Y, rot=270.0,
          file="Connector_Coaxial.pretty/SMA_Amphenol_901-143_Horizontal.kicad_mod")
R1 = dict(ref="R1", lib="Resistor_SMD:R_0402_1005Metric",
          value="0R", x=X_BREAK, y=TRACE_Y, rot=0.0,
          file="Resistor_SMD.pretty/R_0402_1005Metric.kicad_mod")

# Pad nets per reference designator.
PAD_NETS = {
    "J1": {"1": (N_IN, "RF_IN"), "2": (N_GND, "GND")},
    "J2": {"1": (N_OUT, "RF_OUT"), "2": (N_GND, "GND")},
    "R1": {"1": (N_IN, "RF_IN"), "2": (N_OUT, "RF_OUT")},
}

# --- the SMA footprint's own pad table (local mm, copied from the library) ---
SMA_SIGNAL_PAD_R = 2.3 / 2.0
SMA_GROUND_PADS = [(-2.54, 2.54), (-2.54, -2.54), (2.54, -2.54), (2.54, 2.54)]
SMA_GROUND_PAD_R = 2.5 / 2.0


# ---------------------------------------------------------------------------
# 2. Small geometry helpers
# ---------------------------------------------------------------------------

def fmt(value: float) -> str:
    """Format a millimetre value the way KiCad does (no trailing zeros)."""
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def place(x0: float, y0: float, deg: float, lx: float, ly: float) -> tuple[float, float]:
    """Footprint-local -> board coordinates.

    Rotation convention verified against pcbnew::

        world = (x0 + lx*cos - ... )  ->  (x0 + lx*cos + ly*sin, y0 - lx*sin + ly*cos)
    """
    t = math.radians(deg)
    c, s = math.cos(t), math.sin(t)
    return (x0 + lx * c + ly * s, y0 - lx * s + ly * c)


def pad_centres(fp: dict) -> list[tuple[float, float]]:
    """World coordinates of an SMA footprint's four ground-pad centres."""
    return [place(fp["x"], fp["y"], fp["rot"], gx, gy) for gx, gy in SMA_GROUND_PADS]


def envelope_width(x: float, pads) -> float:
    """Widest track at *x* that still clears every SMA ground pad.

    KiCad models a track of width ``w`` as a *stadium* -- its centre line
    thickened by ``w/2`` on every side -- so the copper-to-pad gap is exactly

        gap = |P - Q| - pad_r - w/2

    where ``Q`` is the nearest point of the centre line and ``P`` the pad
    centre.  Requiring ``gap >= CLEARANCE + SMA_CLR_MARGIN`` gives the width
    below.  Using this instead of a fixed ramp is what keeps the launch taper
    DRC-clean: a 1.6 mm long linear 2.0 -> 3.0 mm ramp loses ~70 um of gap
    half-way along, which is a real clearance violation.
    """
    limit = float("inf")
    for px, py in pads:
        axis_gap = math.hypot(x - px, TRACE_Y - py)
        limit = min(limit, 2.0 * (axis_gap - SMA_GROUND_PAD_R
                                  - CLEARANCE - SMA_CLR_MARGIN))
    return limit


def point_segment_distance(p, a, b) -> float:
    """Shortest distance from point *p* to segment *a*-*b*."""
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    denom = dx * dx + dy * dy
    if denom == 0.0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / denom))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


# ---------------------------------------------------------------------------
# 3. The trace plan
# ---------------------------------------------------------------------------

def taper(x0: float, w0: float, x1: float, w1: float) -> list[tuple[float, float, float]]:
    """A width taper as a staircase of short, constant-width segments.

    emfit's copper rasteriser only understands ``segment`` and ``zone``
    geometry, so a ``gr_poly`` taper would be invisible to it - and a track
    staircase is also what a hand-drawn board looks like.  Each stair takes the
    mid-point width of the trapezoid slice it replaces, so the copper area
    error is second order.  Steps are at most ~0.15 mm long.
    """
    length = abs(x1 - x0)
    steps = max(2, int(math.ceil(length / MAX_STAIR)))
    dx = (x1 - x0) / steps
    out = []
    for i in range(steps):
        xs = x0 + i * dx
        xe = x0 + (i + 1) * dx
        w = w0 + (w1 - w0) * ((i + 0.5) / steps)
        out.append((xs, xe, w))
    return out


def env_taper(x0: float, w_start: float, w_end: float,
              pads) -> list[tuple[float, float, float]]:
    """Taper from the neck out to *w_end*, never crossing the clearance envelope.

    Stairs are emitted until the width reaches *w_end*; the end point is
    therefore a result of the geometry, not a constant.  A stair's width is the
    tightest value its two ends allow, so the staircase is safe whichever side
    the pads sit on (the right-hand launch is this plan mirrored).

    *w_start* is only the width of the neck this taper leaves behind; when the
    envelope refuses it the taper comes out narrower, which errs on the safe
    side and is reported by ``verify()`` rather than silently corrected.
    """
    out = []
    x = x0
    for _ in range(4096):                 # the envelope grows without bound
        xe = x + MAX_STAIR
        w = min(w_end, envelope_width(x, pads), envelope_width(xe, pads))
        out.append((x, xe, max(w, 0.0)))
        x = xe
        if w >= w_end - 1e-12:
            return out
    raise SystemExit("env_taper did not reach the full width - check the constants")


def trace_plan() -> list[tuple[float, float, float, int]]:
    """(x_start, x_end, width, net) for every track segment, left to right."""
    pads = pad_centres(J1)
    left: list[tuple[float, float, float, int]] = []
    # launch: constant-width neck, then the envelope-following taper
    left.append((X_LEFT, X_NECK_END_L, W_NECK, N_IN))
    left += [(a, b, w, N_IN) for a, b, w in
             env_taper(X_NECK_END_L, W_NECK, W_MAIN, pads)]
    x_launch_end = left[-1][1]
    # straight run to the break taper
    left.append((x_launch_end, X_BREAK_TAPER_L, W_MAIN, N_IN))
    # taper down to the 0402 land height, plus a stub that reaches into the land
    left += [(a, b, w, N_IN) for a, b, w in
             taper(X_BREAK_TAPER_L, W_MAIN, PAD_L_OUTER, W_PAD)]
    left.append((PAD_L_OUTER, PAD_L_OUTER + STUB_OVERLAP, W_PAD, N_IN))
    # right of the break: the mirror image about x = BOARD_W/2
    right = [(BOARD_W - x1, BOARD_W - x0, w, N_OUT)
             for x0, x1, w, _net in reversed(left)]
    return left + right


# ---------------------------------------------------------------------------
# 4. Verification of the geometry before it is written out
# ---------------------------------------------------------------------------

def verify() -> None:
    """Fail loudly rather than emit a board that shorts to the SMA ground pads."""
    problems = []
    segs = trace_plan()

    # 4a. the plan must be continuous and confined to the board
    for (x0, x1, w, _net), nxt in zip(segs, segs[1:]):
        if abs(x1 - nxt[0]) > 1e-9:
            # the only legitimate gap is the 0402 break itself
            if not (abs(x1 - (PAD_L_OUTER + STUB_OVERLAP)) < 1e-9
                    and abs(nxt[0] - (PAD_R_OUTER - STUB_OVERLAP)) < 1e-9):
                problems.append(f"trace plan is discontinuous at x={x1}")
    for x0, x1, w, _net in segs:
        if x0 < -1e-9 or x1 > BOARD_W + 1e-9:
            problems.append(f"segment {x0}..{x1} leaves the board")
        if abs(TRACE_Y - w / 2) < 0.5 or abs(TRACE_Y + w / 2) > BOARD_H - 0.5:
            problems.append(f"segment {x0}..{x1} runs into the board edge")

    # 4b. clearance to the SMA ground pads, using the footprint's own pad table
    worst = (1e9, None)
    for fp in (J1, J2):
        for gx, gy in SMA_GROUND_PADS:
            centre = place(fp["x"], fp["y"], fp["rot"], gx, gy)
            for x0, x1, w, _net in segs:
                d = point_segment_distance(centre, (x0, TRACE_Y), (x1, TRACE_Y))
                gap = d - SMA_GROUND_PAD_R - w / 2.0
                if gap < worst[0]:
                    worst = (gap, (fp["ref"], (round(centre[0], 3), round(centre[1], 3)),
                                   round(x0, 3), round(x1, 3), round(w, 3)))
    if worst[0] < CLEARANCE - 1e-9:
        problems.append(f"copper to SMA ground pad gap {worst[0]:.3f} mm "
                        f"< {CLEARANCE} mm at {worst[1]}")

    # 4c. the signal pads of J1/J2 must land exactly on the trace ends
    for fp, x_expect in ((J1, X_LEFT), (J2, X_RIGHT)):
        px, py = place(fp["x"], fp["y"], fp["rot"], 0.0, 0.0)
        if abs(px - x_expect) > 1e-9 or abs(py - TRACE_Y) > 1e-9:
            problems.append(f"{fp['ref']} pad 1 at {px},{py} is off the line end")

    # 4d. keepout must clear the widest copper it is meant to protect
    ko_top = TRACE_Y - (W_MAIN / 2.0 + KEEPOUT_OFFSET)
    ko_bot = TRACE_Y + (W_MAIN / 2.0 + KEEPOUT_OFFSET)
    if not (0.0 < ko_top < ko_bot < BOARD_H):
        problems.append("the no-top-pour rule area does not fit on the board")

    if problems:
        print("geometry check FAILED:", file=sys.stderr)
        for p in problems:
            print("  -", p, file=sys.stderr)
        raise SystemExit(1)
    print(f"geometry ok: worst copper/pad gap {worst[0]:.3f} mm "
          f"(limit {CLEARANCE} mm) at {worst[1][0]} pad "
          f"{worst[1][1]}, segment {worst[1][2]}..{worst[1][3]} w={worst[1][4]}")


def check_balance(text: str) -> None:
    """Assert that the generated board text is a balanced s-expression.

    Cheap, but it is the one check that would have caught the bug where the
    embedded footprint lost its inner `)` lines: KiCad only says "Failed to
    load board", so the failure is invisible until you bisect by hand.
    """
    depth = 0
    in_string = False
    escaped = False
    for offset, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth < 0:
                raise SystemExit(
                    f"board text closes a paren that was never opened at "
                    f"offset {offset} (line {text.count(chr(10), 0, offset) + 1})")
    if in_string:
        raise SystemExit("board text ends inside a quoted string")
    if depth != 0:
        raise SystemExit(f"board text is unbalanced: final paren depth {depth}"
                         f" (must be 0)")


# ---------------------------------------------------------------------------
# 5. Footprint embedding
# ---------------------------------------------------------------------------

def _uuid(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "thoughtmachine/5g8-coupon/" + name))


def embed_footprint(fp: dict) -> str:
    """Turn one ``.kicad_mod`` file into a placed, net-connected footprint."""
    path = os.path.join(HERE, "footprints", fp["file"])
    with open(path, encoding="utf-8") as handle:
        lines = handle.read().splitlines()

    # Line 0 is the `(footprint ...` head and the very last line is the lone `)`
    # that closes it: both are replaced by the placement header / closer written
    # by this function.  Every other line must be kept verbatim -- KiCad .kicad_mod
    # files close multi-line blocks (fp_text, model, ...) with a single `)` line,
    # so dropping every `)`-only line silently unbalances the file and KiCad then
    # refuses to load the whole board ("Failed to load board").
    kept = [line for line in lines[1:] if line.strip()]
    if kept and kept[-1].strip() == ")":
        kept = kept[:-1]

    body = []
    for line in kept:
        stripped = line.strip()
        if stripped == '(layer "F.Cu")' or stripped.startswith("(tedit"):
            continue                            # replaced by the placement header
        if '(layer "Edge.Cuts")' in stripped:
            # The stock SMA footprint carries a 8.6 mm stub of Edge.Cuts where
            # the connector's flange sits.  The board outline is drawn properly
            # below, and a second, overlapping outline segment is a DRC error.
            continue
        body.append("  " + line)

    text = "\n".join(body)
    text = text.replace('(fp_text reference "REF**"',
                        f'(fp_text reference "{fp["ref"]}"')
    text = text.replace('(fp_text value "R_0402_1005Metric"',
                        f'(fp_text value "{fp["value"]}"')
    text = text.replace('(fp_text value "SMA_Amphenol_901-143_Horizontal"',
                        f'(fp_text value "{fp["value"]}"')
    # lift R1's reference off the tapered copper
    text = text.replace('(fp_text reference "R1" (at 0 -1.17)',
                        '(fp_text reference "R1" (at 0 -3.2)')

    # assign nets to the pads
    nets = PAD_NETS[fp["ref"]]
    out_lines = []
    for line in text.splitlines():
        match = re.match(r'(\s*\(pad "([^"]+)".*?\(layers [^)]*\))(.*)$', line)
        if match:
            number = match.group(2)
            if number in nets:
                code, name = nets[number]
                line = f'{match.group(1)} (net {code} "{name}"){match.group(3)}'
        out_lines.append(line)
    text = "\n".join(out_lines)

    rot = "" if fp["rot"] == 0 else f' {fmt(fp["rot"])}'
    return (f'  (footprint "{fp["lib"]}" (layer "F.Cu")\n'
            f'    (tstamp {_uuid("fp/" + fp["ref"])})\n'
            f'    (at {fmt(fp["x"])} {fmt(fp["y"])}{rot})\n'
            f'{text}\n'
            f'  )\n')


# ---------------------------------------------------------------------------
# 6. Board file assembly
# ---------------------------------------------------------------------------

STACKUP = """    (stackup
      (layer "F.SilkS" (type "Top Silk Screen"))
      (layer "F.Paste" (type "Top Solder Paste"))
      (layer "F.Mask" (type "Top Solder Mask") (thickness 0.01))
      (layer "F.Cu" (type "copper") (thickness %(cu).3f))
      (layer "dielectric 1" (type "core") (thickness %(diel).2f) (material "FR4") (epsilon_r %(eps).1f) (loss_tangent 0.02))
      (layer "B.Cu" (type "copper") (thickness %(cu).3f))
      (layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.01))
      (layer "B.Paste" (type "Bottom Solder Paste"))
      (layer "B.SilkS" (type "Bottom Silk Screen"))
      (copper_finish "None")
      (dielectric_constraints yes)
    )""" % dict(cu=COPPER_T, diel=SUBSTRATE_H, eps=EPS_R)

PLOT_PARAMS = """    (pcbplotparams
      (layerselection 0x00010fc_ffffffff)
      (plot_on_all_layers_selection 0x0000000_00000000)
      (disableapertmacros false)
      (usegerberextensions false)
      (usegerberattributes true)
      (usegerberadvancedattributes true)
      (creategerberjobfile true)
      (dashed_line_dash_ratio 12.000000)
      (dashed_line_gap_ratio 3.000000)
      (svgprecision 4)
      (plotframeref false)
      (viasonmask false)
      (mode 1)
      (useauxorigin false)
      (hpglpennumber 1)
      (hpglpenspeed 20)
      (hpglpendiameter 15.000000)
      (pdf_front_fp_property_popups true)
      (pdf_back_fp_property_popups true)
      (dxfpolygonmode true)
      (dxfimperialunits true)
      (dxfusepcbnewfont true)
      (psnegative false)
      (psa4output false)
      (plotreference true)
      (plotvalue true)
      (plotinvisibletext false)
      (sketchpadsonfab false)
      (subtractmaskfromsilk false)
      (outputformat 1)
      (mirror false)
      (drillshape 1)
      (scaleselection 1)
      (outputdirectory "")
    )"""

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


def silk_text(text: str, x: float, y: float, key: str, size: float = 1.0) -> str:
    return (f'  (gr_text "{text}" (at {fmt(x)} {fmt(y)}) (layer "F.SilkS")\n'
            f'    (tstamp {_uuid(key)})\n'
            f'    (effects (font (size {fmt(size)} {fmt(size)}) (thickness 0.15)))\n'
            f'  )\n')


#: Where the B.Cu pour's ``filled_polygon`` blocks go.  ``fill_gnd_pour()``
#: replaces it; if KiCad's python bindings are missing it is simply dropped and
#: the board is written with an empty (but otherwise correct) pour.
FILL_SLOT = "    @@GND_FILL@@"


def board_text() -> str:
    parts: list[str] = []
    add = parts.append

    add(f'(kicad_pcb (version 20221018) (generator pcbnew)\n\n')
    add(f'  (general\n    (thickness {fmt(BOARD_T)})\n  )\n\n')
    add('  (paper "A4")\n')
    add(LAYERS + "\n\n")
    add('  (title_block\n')
    add('    (title "5.8 GHz microstrip coupon")\n')
    add('    (rev "A")\n')
    add('    (comment 1 "FR4, 1.6 mm, 1 oz, solid B.Cu ground, no top pour")\n')
    add('    (comment 2 "w = 3.00 mm, h = 1.51 mm, er = 4.4 -> Z0 = 48.3 ohm")\n')
    add('  )\n\n')

    add('  (setup\n')
    add(STACKUP + "\n")
    add('    (pad_to_mask_clearance 0.05)\n')
    add('    (allow_soldermask_bridges_in_footprints no)\n')
    add(PLOT_PARAMS + "\n")
    add('  )\n\n')

    for code, name in sorted(NET.items()):
        add(f'  (net {code} "{name}")\n')
    add("\n")

    # --- board outline -----------------------------------------------------
    add('  (gr_line (start 0 0) (end 0 %s) (layer "Edge.Cuts") (width 0.1) '
        '(tstamp %s))\n' % (fmt(BOARD_H), _uuid("edge/left")))
    add('  (gr_line (start %s 0) (end 0 0) (layer "Edge.Cuts") (width 0.1) '
        '(tstamp %s))\n' % (fmt(BOARD_W), _uuid("edge/top")))
    add('  (gr_line (start %s %s) (end %s 0) (layer "Edge.Cuts") (width 0.1) '
        '(tstamp %s))\n' % (fmt(BOARD_W), fmt(BOARD_H), fmt(BOARD_W), _uuid("edge/right")))
    add('  (gr_line (start 0 %s) (end %s %s) (layer "Edge.Cuts") (width 0.1) '
        '(tstamp %s))\n' % (fmt(BOARD_H), fmt(BOARD_W), fmt(BOARD_H), _uuid("edge/bottom")))
    add("\n")

    # --- silkscreen --------------------------------------------------------
    add(silk_text("5.8GHz MICROSTRIP COUPON  50R", BOARD_W / 2.0, 4.0, "silk/title"))
    # y = 2.5: clear of the title above and of R1's reference designator at
    # y = 6.8 below (which sits there to stay off the tapered copper).
    add(silk_text("FR4 1.6mm 1oz  SOLID B.CU GND", BOARD_W / 2.0, 2.5, "silk/title2", 0.8))
    add(silk_text("W 3.00mm   L 61.0mm   REV A", BOARD_W / 2.0, 15.4, "silk/spec", 0.8))
    add(silk_text("0402 SERIES BREAK (0R)", BOARD_W / 2.0, 17.2, "silk/brk", 0.8))
    add("\n")

    # --- footprints --------------------------------------------------------
    for fp in (J1, R1, J2):
        add(embed_footprint(fp))
    add("\n")

    # --- tracks ------------------------------------------------------------
    for index, (x0, x1, w, net) in enumerate(trace_plan()):
        add('  (segment (start %s %s) (end %s %s) (width %s) (layer "F.Cu") '
            '(net %d) (tstamp %s))\n'
            % (fmt(x0), fmt(TRACE_Y), fmt(x1), fmt(TRACE_Y), fmt(w), net,
               _uuid(f"seg/{index}")))
    add("\n")

    # --- stitching / ground vias ------------------------------------------
    for index, (x, y) in enumerate(VIA_POS):
        add('  (via (at %s %s) (size %s) (drill %s) (layers "F.Cu" "B.Cu") (net %d) '
            '(tstamp %s))\n' % (fmt(x), fmt(y), fmt(VIA_SIZE), fmt(VIA_DRILL),
                                N_GND, _uuid(f"via/{index}")))
    add("\n")

    # --- no-top-pour rule area --------------------------------------------
    ko_top = TRACE_Y - (W_MAIN / 2.0 + KEEPOUT_OFFSET)
    ko_bot = TRACE_Y + (W_MAIN / 2.0 + KEEPOUT_OFFSET)
    add('  (zone (net 0) (net_name "") (layers "F.Cu") (name "NO_TOP_POUR") '
        '(tstamp %s) (hatch edge 0.5)\n' % _uuid("zone/keepout"))
    add('    (connect_pads (clearance 0))\n')
    add('    (min_thickness 0.25) (filled_areas_thickness no)\n')
    add('    (keepout (tracks allowed) (vias allowed) (pads allowed) '
        '(footprints allowed) (copperpour not_allowed))\n')
    add('    (fill (thermal_gap 0.5) (thermal_bridge_width 0.5))\n')
    add('    (polygon\n      (pts\n')
    for x, y in ((0, ko_top), (BOARD_W, ko_top), (BOARD_W, ko_bot), (0, ko_bot)):
        add('        (xy %s %s)\n' % (fmt(x), fmt(y)))
    add('      )\n    )\n  )\n\n')

    # --- solid bottom ground ----------------------------------------------
    add('  (zone (net %d) (net_name "GND") (layer "B.Cu") (tstamp %s) (hatch edge 0.5)\n'
        % (N_GND, _uuid("zone/gnd")))
    add('    (connect_pads (clearance %s))\n' % fmt(0.25))
    add('    (min_thickness 0.25) (filled_areas_thickness no)\n')
    add('    (fill yes (thermal_gap 0.5) (thermal_bridge_width 0.5))\n')
    add('    (polygon\n      (pts\n')
    for x, y in ((0, 0), (BOARD_W, 0), (BOARD_W, BOARD_H), (0, BOARD_H)):
        add('        (xy %s %s)\n' % (fmt(x), fmt(y)))
    add('      )\n    )\n')
    add(FILL_SLOT + "\n")
    add('  )\n')
    add(')\n')
    return "".join(parts)


def polygons_as_text(board) -> str:
    """Render a filled board's zone polygons as KiCad 7 ``filled_polygon`` text."""
    import pcbnew  # local import: only this function needs the bindings

    blocks = []
    for zone in board.Zones():
        if zone.GetIsRuleArea():
            continue
        layer = pcbnew.LayerName(zone.GetLayer())
        polys = zone.GetFilledPolysList(zone.GetLayer())
        for index in range(polys.OutlineCount()):
            chain = polys.Outline(index)
            points = []
            for node in range(chain.PointCount()):
                point = chain.CPoint(node)
                points.append((pcbnew.ToMM(point.x), pcbnew.ToMM(point.y)))
            if len(points) > 1 and points[0] == points[-1]:
                points.pop()                     # v7 does not repeat the start
            if len(points) < 3:
                continue
            blocks.append('    (filled_polygon\n      (layer "%s")\n      (pts\n' % layer)
            for start in range(0, len(points), 4):
                row = " ".join("(xy %s %s)" % (fmt(x), fmt(y))
                               for x, y in points[start:start + 4])
                blocks.append("        %s\n" % row)
            blocks.append("      )\n    )\n")
    return "".join(blocks)


def fill_gnd_pour(text: str) -> str:
    """Fill the bottom pour with KiCad's own filler and inline the result.

    KiCad 9 can fill zones from the GUI but not from ``kicad-cli``, and we write
    a KiCad 7 file that we do not want to upgrade to the 9 format.  So we let
    the pcbnew bindings fill a scratch copy and render the resulting polygons
    back into the 7-format text.  Without this the pour is empty on disk, and
    every reader -- ``kicad-cli pcb drc`` included -- sees the ground pads of
    J1/J2 floating, because the only thing joining them is that pour.

    The bindings are optional: if they are not installed the board is written
    unfilled and the user just presses B in KiCad.
    """
    try:
        import pcbnew
    except ImportError:
        print("note: python pcbnew is not available, so the ground pour is "
              "left unfilled; open the board and press B to fill it",
              file=sys.stderr)
        return text.replace(FILL_SLOT, "")

    with tempfile.TemporaryDirectory() as scratch:
        source = os.path.join(scratch, PROJECT + ".kicad_pcb")
        with open(source, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text.replace(FILL_SLOT, ""))
        board = pcbnew.LoadBoard(source)
        if board is None:
            raise SystemExit("pcbnew could not load the freshly generated board")
        if not pcbnew.ZONE_FILLER(board).Fill(board.Zones()):
            raise SystemExit("the zone filler refused to fill the bottom pour")
        blocks = polygons_as_text(board)

    print(f"  ground pour: filled by pcbnew (KiCad {pcbnew.Version()}), "
          f"{blocks.count('(filled_polygon')} polygon(s) inlined")
    return text.replace(FILL_SLOT, blocks.rstrip("\n"))


# ---------------------------------------------------------------------------
# 7. Project file and library table
# ---------------------------------------------------------------------------

def project_json() -> dict:
    default_class = {
        "name": "Default",
        "priority": 2147483647,
        "clearance": CLEARANCE,
        "track_width": W_MAIN,
        "via_diameter": VIA_SIZE,
        "via_drill": VIA_DRILL,
        "microvia_diameter": 0.3,
        "microvia_drill": 0.1,
        "diff_pair_gap": 0.25,
        "diff_pair_via_gap": 0.25,
        "diff_pair_width": 0.2,
        "line_style": 0,
        "wire_width": 6,
        "bus_width": 12,
        "solder_mask_clearance": 0.0,
        "solder_paste_clearance": 0.0,
        "solder_paste_margin_ratio": 0.0,
        "pcb_color": "rgba(0, 0, 0, 0.000)",
        "schematic_color": "rgba(0, 0, 0, 0.000)",
        "tuning_profile": "trapezoid",
    }
    return {
        "board": {
            "design_settings": {
                "defaults": {
                    "board_outline_line_width": 0.1,
                    "copper_line_width": 0.2,
                    "copper_text_size_h": 1.5,
                    "copper_text_size_v": 1.5,
                    "copper_text_thickness": 0.3,
                    "silk_line_width": 0.12,
                    "silk_text_size_h": 1.0,
                    "silk_text_size_v": 1.0,
                    "silk_text_thickness": 0.15,
                },
                "diff_pair_dimensions": [],
                "drc_exclusions": [],
                "rules": {
                    "max_error": 0.005,
                    "min_clearance": CLEARANCE,
                    "min_copper_edge_clearance": EDGE_CLEAR,
                    "min_hole_clearance": 0.25,
                    "min_hole_to_hole": 0.25,
                    "min_microvia_diameter": 0.2,
                    "min_microvia_drill": 0.1,
                    "min_resolved_spokes": 2,
                    "min_silk_clearance": 0.0,
                    "min_text_height": 0.8,
                    "min_text_thickness": 0.08,
                    "min_through_hole_diameter": 0.3,
                    "min_track_width": 0.2,
                    "min_via_annular_width": 0.1,
                    "min_via_diameter": 0.5,
                    "solder_mask_to_copper_clearance": 0.0,
                    "use_height_for_length_calcs": True,
                },
                "track_widths": [0.0, 0.2, 0.64, 1.0, 2.0, 3.0],
                "via_dimensions": [{"diameter": 0.0, "drill": 0.0},
                                   {"diameter": VIA_SIZE, "drill": VIA_DRILL}],
                "zones_allow_external_fillets": False,
            },
            "layer_presets": [],
            "viewports": [],
        },
        "boards": [],
        "cvpcb": {"equivalence_files": []},
        "libraries": {"pinned_footprint_libs": [], "pinned_symbol_libs": []},
        "meta": {"filename": f"{PROJECT}.kicad_pro", "version": 1},
        "net_settings": {
            "classes": [default_class],
            "meta": {"version": 3},
            "net_colors": None,
            "netclass_assignments": None,
            "netclass_patterns": [],
        },
        "pcbnew": {
            "last_paths": {"gencad": "", "idf": "", "netlist": "",
                           "specctra_dsn": "", "step": "", "vrml": ""},
            "page_layout_descr_file": "",
        },
        "schematic": {
            "legacy_lib_dir": "",
            "legacy_lib_list": [],
        },
        "sheets": [["00000000-0000-0000-0000-000000000000", ""]],
        "text_variables": {},
    }


FP_LIB_TABLE = """(fp_lib_table
  (version 7)
  (lib (name "Connector_Coaxial")(type "KiCad")(uri "${KIPRJMOD}/footprints/Connector_Coaxial.pretty")(options "")(descr "Amphenol 901-143 edge-launch SMA, copied from the KiCad library"))
  (lib (name "Resistor_SMD")(type "KiCad")(uri "${KIPRJMOD}/footprints/Resistor_SMD.pretty")(options "")(descr "0402 resistor lands, copied from the KiCad library"))
  (lib (name "Capacitor_SMD")(type "KiCad")(uri "${KIPRJMOD}/footprints/Capacitor_SMD.pretty")(options "")(descr "0402 capacitor lands, for the optional shunt"))
)
"""


def main() -> int:
    verify()

    text = fill_gnd_pour(board_text())
    check_balance(text)

    pcb_path = os.path.join(HERE, f"{PROJECT}.kicad_pcb")
    with open(pcb_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)

    with open(os.path.join(HERE, f"{PROJECT}.kicad_pro"), "w",
              encoding="utf-8", newline="\n") as handle:
        json.dump(project_json(), handle, indent=2)
        handle.write("\n")

    with open(os.path.join(HERE, "fp-lib-table"), "w",
              encoding="utf-8", newline="\n") as handle:
        handle.write(FP_LIB_TABLE)

    segs = trace_plan()
    print(f"wrote {os.path.basename(pcb_path)}: {len(segs)} track segments, "
          f"{len(VIA_POS)} vias, 3 footprints")
    print(f"  line: {X_LEFT} -> {X_RIGHT} mm = {X_RIGHT - X_LEFT:.2f} mm, "
          f"break at x={X_BREAK}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
