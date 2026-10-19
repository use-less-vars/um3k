# Local patches to the vendored footprints

The three libraries in this directory are copies of the KiCad official
libraries at the tag in `UPSTREAM_TAG.txt`. One file is patched, on purpose,
and the patch is recorded here so that re-vendoring does not silently undo it.

## `Connector_Coaxial.pretty/SMA_Amphenol_901-143_Horizontal.kicad_mod`

Removed one line:

```diff
-  (fp_line (start 4.3 -4.5) (end -4.3 -4.5) (layer "Edge.Cuts") (width 0.1) (tstamp f78bf029-e907-4428-b53a-981cd964b9ec))
```

**Why.** Upstream draws that stub on `Edge.Cuts` so that the connector body
overhanging the board edge is visible on the outline layer. In this design the
SMA sits *on* the board, with the footprint's 4.5 mm flange line coincident with
the left/right board edge, so the stock stub lands exactly on top of the board
outline. Two coincident `Edge.Cuts` segments is a malformed outline: DRC
reports the board outline as self-intersecting and the plotted outline layer
carries a doubled line.

**Effect of not patching.** `generate_board.py` would still drop the segment
when it embeds the footprint, so the board itself would be identical — but the
board footprint would then differ from the library copy, and DRC would raise
`lib_footprint_mismatch` on J1 and J2 on every run. Patching the library copy
keeps the two in agreement, which is what the check is for.

**None of the pads, courtyards, silkscreen or 3D model are touched.** The pad
geometry in `generate_board.py` (`SMA_GROUND_PADS`, `SMA_GROUND_PAD_R`) was
verified against this file and is unaffected by the patch.
