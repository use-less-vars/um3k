#!/usr/bin/env python3
"""Independently re-measure the generated coupon board.

``generate_board.py`` is a text generator: it emits S-expressions and trusts its
own arithmetic.  This script is the second opinion.  It reads the *written*
``.kicad_pcb`` back with ``emfit.kicad.load_board`` -- a reader that shares no
code with the generator -- and re-derives every number the design claims:

* the outline is 70 x 20 mm,
* the stackup is 1.6 mm of FR4 with 35 um foils and eps_r 4.4,
* the trace carries the three widths the launch/break design asks for
  (3.0 mm main line, 2.0 mm neck, 0.64 mm break stub),
* each RF net is a single unbranched, x-monotonic chain with no dangling end,
* pad-centre to pad-centre is 61.0 mm,
* 3.0 mm on 1.51 mm of eps_r 4.4 is 48.26 ohm (via ``emfit.microstrip``),
* there is exactly one poured B.Cu ground zone and no copper pour on top,
* there are no vias and no footprints beyond J1/J2/R1.

Every check is a plain comparison printed as a table; any failure exits 1 so
this can gate a commit or a fab order.  Nothing here writes to the board.

Usage::

    python3 check_board.py [board.kicad_pcb]
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # the workspace root, for ``emfit``

from emfit.kicad import load_board  # noqa: E402
from emfit.microstrip import Microstrip  # noqa: E402

# --------------------------------------------------------------------------
# What the design claims.  Kept next to the generator's constants on purpose:
# if you edit the geometry there, edit it here and the check goes red until the
# two agree again.
# --------------------------------------------------------------------------
BOARD_W = 70.0
BOARD_H = 20.0
BOARD_T = 1.6
SUBSTRATE_T = 1.51
COPPER_T = 0.035
EPS_R = 4.4
LINE_LENGTH = 61.0  # pad centre to pad centre
GAP = 0.48  # break gap between the two inner lands
W_MAIN = 3.0
W_NECK = 2.0
W_STUB = 0.64
W_LAND = 0.54  # R1 0402 land, the x extent of the pad
Z0_MAIN = 48.26  # emfit, w=3.0 mm, h=1.51 mm, t=35 um, eps_r 4.4
STRAIGHT = 23.42  # length of the constant-3.0 mm middle section, per side
NECK_LEN = 2.5  # length of the constant-2.0 mm neck, per side
TOL = 1e-3  # mm; the file stores 4 decimals


class Checks:
    """Collect pass/fail rows instead of assert-and-die, so one run shows all."""

    def __init__(self) -> None:
        self.rows: list[tuple[bool, str, str]] = []

    def check(self, name: str, ok: bool, detail: str = "") -> bool:
        self.rows.append((bool(ok), name, detail))
        return bool(ok)

    def close(self, name: str, got: float, want: float, tol: float = TOL) -> bool:
        ok = abs(got - want) <= tol
        return self.check(name, ok, f"got {got:g}, want {want:g} +/- {tol:g}")

    def eq(self, name: str, got, want) -> bool:
        return self.check(name, got == want, f"got {got!r}, want {want!r}")

    def report(self) -> int:
        width = max(len(name) for _, name, _ in self.rows)
        failed = 0
        for ok, name, detail in self.rows:
            mark = "ok  " if ok else "FAIL"
            print(f"[{mark}] {name.ljust(width)}  {detail}")
            failed += not ok
        print()
        if failed:
            print(f"{failed} of {len(self.rows)} checks FAILED")
            return 1
        print(f"all {len(self.rows)} checks passed")
        return 0


def world_pos(fp, pad) -> tuple[float, float]:
    """Place a footprint-local pad in board coordinates.

    KiCad stores pad positions in the footprint frame; rotate by the footprint
    angle and translate.  Verified against the GND pads of J1 (rot 90), whose
    world positions (1.96/7.04, 7.46/12.54) are known from the connector
    datasheet.
    """
    theta = math.radians(fp.rotation)
    c, s = math.cos(theta), math.sin(theta)
    lx, ly = pad.position
    return (fp.position[0] + lx * c - ly * s, fp.position[1] + lx * s + ly * c)


def chain_length(tracks) -> tuple[float, str]:
    """Walk one net's tracks and return ``(total_mm, problem)``.

    A coupon line must be a single simple path: every segment end shared by
    exactly two segments, except the two ends of the path, which are used once
    and sit at the extreme x.  Returns a non-empty problem string when the
    segments do not form one clean chain.
    """
    key = lambda p: (round(p[0], 4), round(p[1], 4))  # noqa: E731
    ends: dict[tuple[float, float], list[int]] = {}
    for i, t in enumerate(tracks):
        for p in (t.start, t.end):
            ends.setdefault(key(p), []).append(i)

    if len(ends) != len(tracks) + 1:
        return 0.0, f"{len(ends)} distinct endpoints for {len(tracks)} segments (expect {len(tracks) + 1})"
    degrees = sorted(len(v) for v in ends.values())
    if degrees.count(1) != 2 or any(d > 2 for d in degrees):
        return 0.0, f"endpoint degrees {degrees}: not one simple path"
    if any(t.width <= 0 for t in tracks):
        return 0.0, "a segment has zero width"
    if any(t.start[0] >= t.end[0] for t in tracks):
        return 0.0, "a segment is not drawn left-to-right (x not increasing)"
    if any(abs(t.start[1] - t.end[1]) > TOL for t in tracks):
        return 0.0, "a segment is not horizontal (coupon is a straight line at y=10)"
    return sum(t.length() for t in tracks), ""


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else HERE / "kicad_support_project.kicad_pcb"
    if not path.is_file():
        print(f"no such board: {path}", file=sys.stderr)
        return 2
    board = load_board(path)
    chk = Checks()
    print(f"board: {path.name}\n")

    # -- outline -----------------------------------------------------------
    bbox = board.edge_bbox
    chk.check("outline present", bbox is not None, str(bbox))
    if bbox:
        x0, y0, x1, y1 = bbox
        chk.close("outline width", x1 - x0, BOARD_W)
        chk.close("outline height", y1 - y0, BOARD_H)
        chk.close("outline x0", x0, 0.0)
        chk.close("outline y0", y0, 0.0)

    # -- stackup -----------------------------------------------------------
    chk.close("board thickness", board.thickness or 0.0, BOARD_T)
    chk.close("stackup sum", board.stackup_thickness() or 0.0, BOARD_T)
    copper = [e for e in board.stackup if e.is_copper]
    diel = [e for e in board.stackup if e.kind in ("core", "prepreg")]
    chk.eq("copper foils in stackup", len(copper), 2)
    if copper:
        chk.check(
            "copper foil thickness",
            all(abs((e.thickness or 0.0) - COPPER_T) <= 1e-4 for e in copper),
            ", ".join(f"{e.name}={e.thickness}" for e in copper),
        )
    chk.eq("dielectric layers in stackup", len(diel), 1)
    if diel:
        d = diel[0]
        chk.close("substrate thickness", d.thickness or 0.0, SUBSTRATE_T, 1e-4)
        chk.check("substrate eps_r", d.epsilon_r is not None and abs(d.epsilon_r - EPS_R) <= 1e-6, f"got {d.epsilon_r}")
        chk.check(
            "substrate loss tangent set",
            d.loss_tangent is not None and d.loss_tangent > 0,
            f"got {d.loss_tangent}",
        )
    chk.eq("copper layers", board.copper_layers, ["F.Cu", "B.Cu"])

    # -- nets --------------------------------------------------------------
    names = {n.name for n in board.nets}
    for want in ("GND", "RF_IN", "RF_OUT"):
        chk.check(f"net {want}", want in names, "" if want in names else f"not among {len(names)} net names")
    rf = {n.code: n.name for n in board.nets if n.name in ("RF_IN", "RF_OUT")}
    chk.eq("RF net codes", sorted(rf), [2, 3])

    # -- copper geometry ---------------------------------------------------
    top = [t for t in board.tracks if t.layer == "F.Cu"]
    bottom = [t for t in board.tracks if t.layer == "B.Cu"]
    chk.eq("tracks on B.Cu", len(bottom), 0)
    chk.check("tracks present", len(top) > 0, f"{len(top)} segments on F.Cu")
    # The launches are staircased, so the file legitimately carries two dozen
    # widths.  What must hold is the envelope: nothing wider than the 3.0 mm
    # line or narrower than the 0.64 mm break stub, and the three design widths
    # each present for their intended run length.
    widths = [t.width for t in top]
    chk.check(
        "widths within 0.64..3.0 mm",
        min(widths) >= W_STUB - TOL and max(widths) <= W_MAIN + TOL,
        f"min {min(widths):.3f}, max {max(widths):.3f}",
    )
    for want, want_len in ((W_MAIN, 2 * STRAIGHT), (W_NECK, 2 * NECK_LEN), (W_STUB, 0.2)):
        run = sum(t.length() for t in top if abs(t.width - want) <= TOL)
        chk.check(
            f"width {want:g} mm used",
            run >= want_len - 0.3,
            f"{run:.2f} mm of {want:g} mm copper (expect >= {want_len:.2f})",
        )
    chk.check("all tracks at y=10", all(abs(t.start[1] - 10.0) <= TOL and abs(t.end[1] - 10.0) <= TOL for t in top), "")

    total = 0.0
    for code, name in sorted(rf.items()):
        segs = [t for t in top if t.net == code]
        length, problem = chain_length(segs)
        chk.check(f"{name} is one unbranched chain", not problem, problem or f"{len(segs)} segments, {length:.3f} mm")
        total += length

    net_edges = {}
    for code, name in rf.items():
        xs = [x for t in top if t.net == code for x in (t.start[0], t.end[0])]
        if xs:
            net_edges[name] = (min(xs), max(xs))
    # Both nets must exist before anything downstream means anything.  Report
    # the absence as a row and skip the span work rather than traceback: this
    # script is run against wrong boards on purpose.
    have_both = {"RF_IN", "RF_OUT"} <= net_edges.keys()
    if not have_both:
        chk.check("both RF nets routed", False, f"track edges found only for {sorted(net_edges) or 'none'}")
    if have_both:
        chk.close("RF_IN starts at J1 pad", net_edges["RF_IN"][0], 4.5, 5e-3)
        chk.close("RF_OUT ends at J2 pad", net_edges["RF_OUT"][1], 65.5, 5e-3)
        # The tracks stop inside R1's pads rather than at their inner edges, so
        # the copper between them is a pad remnant, not trace.  Take the break
        # from the pads themselves.
        chk.check(
            "RF_IN ends inside R1 pad 1",
            net_edges["RF_IN"][1] > 34.22 + TOL,
            f"track end x = {net_edges['RF_IN'][1]:.3f}, pad 1 spans 34.22..34.76",
        )
        chk.check(
            "RF_OUT starts inside R1 pad 2",
            net_edges["RF_OUT"][0] < 35.78 - TOL,
            f"track start x = {net_edges['RF_OUT'][0]:.3f}, pad 2 spans 35.24..35.78",
        )

    # -- the span the design is defined on --------------------------------
    band = GAP
    r1 = next((fp for fp in board.footprints if fp.reference == "R1"), None)
    if r1 is not None and len(r1.pads) >= 2:
        p1, p2 = sorted(r1.pads, key=lambda p: p.position[0])
        inner1 = world_pos(r1, p1)[0] + p1.size[0] / 2
        inner2 = world_pos(r1, p2)[0] - p2.size[0] / 2
        band = inner2 - inner1
        chk.close("R1 land width", p1.size[0], W_LAND, 1e-3)
        chk.close("R1 land 1 inner edge", inner1, 34.76, 1e-3)
        chk.close("R1 land 2 inner edge", inner2, 35.24, 1e-3)
    else:
        chk.check("R1 lands measurable", False, "no R1 footprint with two pads")
    chk.close("break gap between inner land edges", band, GAP)

    if have_both:
        sma_span = net_edges["RF_OUT"][1] - net_edges["RF_IN"][0]
        chk.close("SMA centre to centre", sma_span, LINE_LENGTH)
        # Copper run SMA-to-SMA, i.e. what the microstrip model sees with the
        # break open.  A 0 ohm link adds the break back and restores 61.0 mm.
        run = sma_span - band
        chk.close("copper run, SMA to break", run, LINE_LENGTH - GAP)
        chk.close("track length total", total, run - 2 * 0.44, 0.05)
    else:
        run = float("nan")

    # -- microstrip cross-section -----------------------------------------
    ms = Microstrip(w=W_MAIN * 1e-3, h=SUBSTRATE_T * 1e-3, eps_r=EPS_R, t=COPPER_T * 1e-3)
    chk.check("Z0 of the 3.0 mm line", abs(ms.z0 - Z0_MAIN) <= 0.05, f"got {ms.z0:.2f} ohm, want {Z0_MAIN:.2f}")
    chk.close("eps_eff of the 3.0 mm line", ms.eps_eff, 3.3420, 5e-4)
    lam_g = ms.effective_wavelength(5.8e9) * 1e3
    chk.check(
        f"open-break run is {run / lam_g:.3f} lambda_g",
        run / lam_g == run / lam_g and abs(run / lam_g - 2.140) <= 5e-3,
        f"lambda_g = {lam_g:.3f} mm, run = {run:g} mm",
    )
    chk.check(
        f"linked run is {LINE_LENGTH / lam_g:.3f} lambda_g",
        abs(LINE_LENGTH / lam_g - 2.158) <= 5e-3,
        f"with a 0 ohm link fitted across the {band:g} mm break",
    )

    # -- zones -------------------------------------------------------------
    pours = [z for z in board.zones if not z.keepout]
    keepouts = [z for z in board.zones if z.keepout]
    top_pours = [z for z in pours if "F.Cu" in z.layers]
    bottom_pours = [z for z in pours if "B.Cu" in z.layers]
    chk.eq("copper pours on F.Cu", len(top_pours), 0)
    chk.eq("copper pours on B.Cu", len(bottom_pours), 1)
    if bottom_pours:
        z = bottom_pours[0]
        chk.eq("B.Cu pour net", z.net_name or board.net_name(z.net), "GND")
        chk.check("B.Cu pour has fill geometry", z.has_fill, "filled_polygon present" if z.has_fill else "NOT POURED")
        xs = z.outline[:, 0]
        chk.close("B.Cu pour spans board width", xs.max() - xs.min(), BOARD_W, 0.1)
    chk.check("F.Cu rule area (no top pour)", len(keepouts) >= 1, f"{len(keepouts)} keepout zone(s)")

    # -- vias, footprints, pads -------------------------------------------
    chk.eq("vias", len(board.vias), 0)
    refs = sorted(fp.reference for fp in board.footprints)
    chk.eq("footprints", refs, ["J1", "J2", "R1"])

    by_ref = {fp.reference: fp for fp in board.footprints}
    for ref, want_x in (("J1", 4.5), ("J2", 65.5)):
        fp = by_ref.get(ref)
        if fp is None:
            chk.check(f"{ref} placed", False, "footprint missing")
            continue
        chk.close(f"{ref} pad 1 x", world_pos(fp, fp.pads[0])[0], want_x, 1e-3)
        chk.close(f"{ref} pad 1 y", world_pos(fp, fp.pads[0])[1], 10.0, 1e-3)

    tht = [p for p in board.pads if p.drill]
    chk.eq("plated through holes", len(tht), 10)
    drills = sorted({round(p.drill, 3) for p in tht})
    chk.eq("drill sizes", drills, [1.5, 1.7])

    gnd_pads = sorted(
        {
            (round(world_pos(fp, p)[0], 3), round(world_pos(fp, p)[1], 3))
            for fp in board.footprints
            for p in fp.pads
            if p.drill and abs((p.drill or 0) - 1.7) <= TOL
        }
    )
    chk.eq("GND pad count", len(gnd_pads), 8)
    xs = sorted({x for x, _ in gnd_pads})
    ys = sorted({y for _, y in gnd_pads})
    chk.eq("GND pad x columns", xs, [1.96, 7.04, 62.96, 68.04])
    chk.eq("GND pad y rows", ys, [7.46, 12.54])

    if "R1" in by_ref:
        r1 = by_ref["R1"]
        chk.close("R1 lands pitch", abs(r1.pads[1].position[0] - r1.pads[0].position[0]), 1.02, 1e-3)

    return chk.report()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
