# 5.8 GHz microstrip coupon board

A two-layer FR4 coupon that measures one 50 Ω microstrip line at 5.8 GHz with a
series 0402 break for a DUT or a 0 Ω link. Everything on the board is generated
by one script, so the copper you plot is the copper the script computed.

```
python3 generate_board.py     # writes the .kicad_pcb, .kicad_pro, fp-lib-table
open kicad_support_project.kicad_pcb
```

Requires only the standard library; if KiCad's `pcbnew` python module is present
the bottom pour is filled as part of generation (see **Zone fill** below).

## What is on the board

| | |
|---|---|
| Outline | 70.0 × 20.0 mm, 1.6 mm FR4, εr 4.4, 1 oz (35 µm) copper, 2 layers |
| Launch | Amphenol 901-143 SMA edge launch (J1, J2), pad 1 to pad 1 **61.0 mm** |
| Line | 3.00 mm wide on 1.51 mm substrate → 48.3 Ω, εeff 3.342, λg 28.27 mm @ 5.8 GHz |
| Break | R1 = 0 Ω 0402 in series at mid-board, land gap 0.48 mm |
| Ground | solid pour on B.Cu only; rule area on F.Cu keeps the top clear |
| Nets | `RF_IN` (J1-1 → R1-1), `RF_OUT` (R1-2 → J2-1), `GND` (all SMA ground pads) |

Copper plan, left half (mirrored about x = 35 for the right half):

```
 4.5 ─ 7.0     neck 2.00 mm
 7.0 ─ 8.65    launch taper 2.081 → 3.00 mm, 0.15 mm stairs, width set by the
               clearance envelope of the four SMA ground pads
 8.8 ─ 32.22   main line 3.00 mm  (whole line, pad to pad: 61.0 mm = 2.158 λg,
              2.140 λg of copper with the break open, 0.372 ns)
32.22 ─ 34.22  break taper 3.00 → 0.64 mm, 14 stairs
34.22 ─ 34.32  stub, then the 0.64 mm wide 0402 lands
```

## Departures from the brief, and why

- **61.0 mm, not 60.0 mm.** The line length is fixed by the two SMA pad centres,
  and those are fixed by where the connector flanges sit on a 70 mm outline
  (4.5 mm in from each edge). Shortening to 60 mm means shrinking the board to
  69 mm or moving a connector off its flange.
- **48.3 Ω, not 50 Ω.** 50 Ω needs w = 2.826 mm on this stackup. A 3.00 mm line
  was chosen so the width is a round number a fab can hold and so the 0402 lands
  (0.54 mm) are a reasonable fraction of it; the 3.4 % low impedance is a
  deliberate, documented offset, not an oversight. Change `W_MAIN` to 2.826 if
  you want 50 Ω exactly.
- **2.00 mm neck at the launch.** The SMA's centre pin is 2.3 mm wide and the
  four ground pads sit 2.54 mm off axis, so a 3 mm line cannot reach the pin
  without breaking the 0.2 mm clearance. The neck is ~60 Ω and is tapered out of
  it over 1.65 mm in 0.15 mm stairs; the taper width is computed as the exact
  clearance envelope of the ground pads (`envelope_width()`), which is why it
  looks stepped rather than straight.
- **0.48 mm land gap.** 0402 lands at ±0.51 mm with 0.54 mm width leave 0.48 mm
  between them; a 0 Ω jumper bridges it, a real component sits in it.
- **No stitching vias.** The top layer carries only the line, so a via would
  reach the pour on one layer only — DRC calls that `via_dangling` and it is
  right. The SMA bodies are grounded through their four through-hole pads.
- **The board has no schematic.** It is a standalone `.kicad_pcb`: do *not* run
  "Update PCB from Schematic" in it, it would delete everything.

## Zone fill

`kicad-cli` cannot fill zones, so `generate_board.py` loads its own output with
`pcbnew`, runs `ZONE_FILLER`, and writes the resulting polygons back into the
KiCad 7 text. The file on disk is therefore filled and DRC-clean as shipped.
If `pcbnew` is unavailable the board is written unfilled (the script says so)
and the only consequence is that you press **B** in KiCad before plotting; the
geometry is unchanged either way.

The pour is drawn from the board rectangle and the keepout is *not* applied to
it — the rule area exists to stop the top layer being poured, and the bottom
pour covers the full board.

## Verification

Two independent checks, both runnable without opening KiCad.

**1. DRC.**

```
kicad-cli pcb drc --severity-all --format json -o /tmp/drc.json kicad_support_project.kicad_pcb
```

Current state of the generated board:

- **0 errors, 0 unconnected items.**
- 2 warnings, both `lib_footprint_mismatch` on J1/J2: the embedded connectors
  carry the assigned nets and the value text `SMA`, so they differ from the
  library copy. Nothing to fix — do not run "update footprint from library",
  it would only re-add the frame the board does not want (see
  `footprints/PATCHES.md`).

`generate_board.py` runs its own checks before writing anything and refuses to
write a board that breaks them: trace continuity, copper inside the outline,
copper-to-edge, copper-to-SMA-ground-pad clearance re-derived from the
footprint's own pad table (currently 0.250 mm worst case against a 0.2 mm
limit), pad 1 of both connectors exactly on the line ends, and a paren balance
check on the output text.

**2. `check_board.py` — the second opinion.**

The generator's checks use the generator's own numbers, so they cannot catch a
modelling mistake shared by both. `check_board.py` reads the *written* file back
with `emfit.kicad.load_board` (a reader that shares no code with the generator)
and re-derives every claim: the 70 × 20 outline, the 1.6 mm / 35 µm / εr 4.4
stackup, the three design widths and their run lengths, each RF net as one
unbranched x-monotonic chain, the 61.0 mm SMA span, the 0.48 mm break derived
from R1's own pad geometry and placement, the 48.26 Ω / εeff 3.342 / λg 28.27 mm
cross-section through `emfit.microstrip`, exactly one poured B.Cu zone and no
top pour, no vias, and the connector and ground pad coordinates.

```
python3 check_board.py                       # 60 checks, exit 0
python3 check_board.py ../CMEX.kicad_pcb     # exit 1, 37 failures: it does say no
```

It prints one row per check and exits non-zero on any failure, so it can gate a
commit or a fab order. Pointing it at a board that is not this coupon is a
useful smoke test of the checker itself.

## Fabrication outputs

```
kicad-cli pcb export gerbers -l F.Cu,B.Cu,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts \
    -o gerbers/ kicad_support_project.kicad_pcb
kicad-cli pcb export drill -o gerbers/ kicad_support_project.kicad_pcb
```

Eight layers plus drill and a `.gbrjob`:

| File | |
|---|---|
| `-F_Cu.gtl` | top copper: 58 track draws, 12 pad flashes |
| `-B_Cu.gbl` | bottom copper: 3 `G36` regions, i.e. the filled pour itself |
| `-F_Mask.gts`, `-B_Mask.gbs` | mask openings, 10 each (the through-hole pads) |
| `-F_Silkscreen.gto` | outline, refs, values, the stackup note |
| `-B_Silkscreen.gbo` | header only: nothing is drawn on the back |
| `-Edge_Cuts.gm1` | 70 × 20 rectangle, 4 segments |
| `.drl` | T1 1.50 mm × 2 (SMA centre pins), T2 1.70 mm × 8 (SMA ground) |

Areas with no copper are simply absent from the copper gerbers, which is what a
fab expects; the B.Cu pour is baked into the file (`filled_polygon`, see **Zone
fill**), so the gerber carries it without KiCad having to refill first. There is
no B.Mask content beyond the pad openings because the back pour is *meant* to stay
under mask.

## Files

| Path | |
|---|---|
| `generate_board.py` | the generator; all dimensions are constants at the top |
| `kicad_support_project.kicad_pcb` | generated board (KiCad 7 format, `20221018`) |
| `kicad_support_project.kicad_pro` | design rules: 0.2 mm clearance, 0.25 mm edge, 3.0 mm track |
| `fp-lib-table` | so KiCad finds `footprints/` |
| `check_board.py` | independent re-measurement of the written board (60 checks) |
| `footprints/` | vendored KiCad libraries, `UPSTREAM_TAG.txt`, `PATCHES.md` |
| `gerbers/` | fabrication outputs: 8 gerbers, drill, `.gbrjob` |

Regenerating is deterministic (UUIDs are derived from fixed names), so a diff of
the `.kicad_pcb` after a regeneration shows only what actually changed.
