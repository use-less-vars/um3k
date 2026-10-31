# The mesher's ladder: which `h` values are actually different meshes

Case: 2D modal cross-section, `H = 1.6 mm` substrate, `eps_r = 4.4`, strip `W = 0.8 mm`,
`clearance = 3.0` (lid `3H`, side walls `3H`), open closure (`dm.boxes(geo)["open"]`) --
i.e. `tools/host_ladder.py`'s **defaults** (`--clearance 3.0 --box-lateral-mult 1
--box-lid-mult 1 --strip-width-mm 0.8`). Container: python3 (system), numpy 2.5.4, scipy 1.18.1.

## Method note

The mesher is not driven by `h`; it is driven by the **substrate cell count**. In
`tools/host_ladder.py`, `grid_for(h_mm)` (L384-392) returns
`(n_sub, cell_m) = (int(round(H_SUB / h_m)), H_SUB / n_sub)` and refuses `n_sub < 1` with
`LadderError`; `dm.section(h, clearance, H=H_SUB, W=W, clearance_lateral=...)` independently
does the same rounding and refuses with `ValueError`. So every `h` that rounds to the same
`nz_sub` produces the **same cell size and the same box**, and therefore the same mesh.

Each row below is measured, not deduced: for one `h` I rebuild the section exactly as
`build_modal` does (same call, same `W`, same `nz_sub`/`cell`) and read off

- `n_e` = `np.flatnonzero(~mode2d.pec_edge_mask(mesh, bounds)).size`
- `n_n` = `np.flatnonzero(~mode2d.pec_node_mask(mesh, bounds)).size`, `n_dof = n_e + n_n`
  (the same two lines `build_modal` uses at L535-538; `n_dof = n_e + n_n` reproduces
  `1262 + 429 = 1691` and `319 + 110 = 429` of `decisions.md` 158.3),
- `ny x nz` = the cell counts on the two grid axes (`geo["ny"]`, `geo["nz"]`);
  `n_nodes`/`n_tris` from `Mesh2D`,
- `fp` = first 16 hex of `sha1(mesh.nodes.tobytes() + mesh.edges.tobytes() + mesh.tris.tobytes())`
  — a fingerprint of the whole mesh, not just its size. **"differs from `h` above"** = the
  row's `fp` is not the `fp` of the row at the next *larger* sampled `h`; `-` means the row
  above it failed, so there was nothing to differ from.

The harness (verbatim; `hs` is the list of trial `h` in mm):

```python
import sys, hashlib
sys.path.insert(0, "/workspace"); sys.path.insert(0, "/workspace/tools")
import numpy as np
import d585_modal as dm
from emfit import mode2d
import host_ladder as hl

H, W, CLEAR = 1.6e-3, 8e-4, 3.0            # hl.H_SUB, default strip, default clearance

def measure(h_mm):
    h_m = h_mm * 1e-3
    nz_sub = int(round(H / h_m)); cell = H / nz_sub
    geo = dm.section(h_m, CLEAR, H=H, W=W, clearance_lateral=CLEAR)
    mesh = geo["mesh"]; bounds = dm.boxes(geo)["open"]
    ne = int(np.flatnonzero(~mode2d.pec_edge_mask(mesh, bounds)).size)
    nn = int(np.flatnonzero(~mode2d.pec_node_mask(mesh, bounds)).size)
    fp = hashlib.sha1(mesh.nodes.tobytes() + mesh.edges.tobytes()
                      + mesh.tris.tobytes()).hexdigest()[:16]
    return (h_mm, nz_sub, cell * 1e3, int(geo["ny"]), int(geo["nz"]), int(geo["ny_strip"]),
            int(mesh.n_nodes), int(mesh.n_tris), ne, nn, ne + nn, fp)
```

Exact commands: `python3 /tmp/m.py` (Mesh2D introspection + the two 158.3 reference points),
`python3 /tmp/sweep.py` (the full sweep, table 1), `python3 /tmp/edges.py` (exact band edges,
`grid_for` verification, the three failure messages, the rung and `n_dof` scans).

**`grid_for()` verified, not assumed:** `hl.grid_for(0.4) == (4, 0.0004)`,
`hl.grid_for(1.2) == (1, 0.0016)`, `hl.grid_for(1.6) == (1, 0.0016)`,
`hl.grid_for(2.0) == (1, 0.0016)`, and its `n_sub` agrees with `geo["nz_sub"]` on every one
of the 48 successful rows below.

## Table 1 — full sweep

| h (mm) | nz_sub | cell (mm) | ny | nz | ny_strip | n_nodes | n_tris | n_e | n_n | n_dof | differs from h above | fp |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 3.2 | — | — | — | — | — | — | — | — | — | — | — | REFUSED (see below) |
| 3.1999 | 1 | 1.6000 | 7 | 4 | 1 | 40 | 56 | 87 | 30 | 117 | - | e23ba3e652a9dcd3 |
| 3.0 | 1 | 1.6000 | 7 | 4 | 1 | 40 | 56 | 87 | 30 | 117 | no | e23ba3e652a9dcd3 |
| 2.5 | 1 | 1.6000 | 7 | 4 | 1 | 40 | 56 | 87 | 30 | 117 | no | e23ba3e652a9dcd3 |
| 2.0 | 1 | 1.6000 | 7 | 4 | 1 | 40 | 56 | 87 | 30 | 117 | no | e23ba3e652a9dcd3 |
| 1.8 | 1 | 1.6000 | 7 | 4 | 1 | 40 | 56 | 87 | 30 | 117 | no | e23ba3e652a9dcd3 |
| 1.6 | 1 | 1.6000 | 7 | 4 | 1 | 40 | 56 | 87 | 30 | 117 | no | e23ba3e652a9dcd3 |
| 1.5 | 1 | 1.6000 | 7 | 4 | 1 | 40 | 56 | 87 | 30 | 117 | no | e23ba3e652a9dcd3 |
| 1.4 | 1 | 1.6000 | 7 | 4 | 1 | 40 | 56 | 87 | 30 | 117 | no | e23ba3e652a9dcd3 |
| 1.2 | 1 | 1.6000 | 7 | 4 | 1 | 40 | 56 | 87 | 30 | 117 | no | e23ba3e652a9dcd3 |
| 1.1 | 1 | 1.6000 | 7 | 4 | 1 | 40 | 56 | 87 | 30 | 117 | no | e23ba3e652a9dcd3 |
| 1.07 | 1 | 1.6000 | 7 | 4 | 1 | 40 | 56 | 87 | 30 | 117 | no | e23ba3e652a9dcd3 |
| 1.0667 | 1 | 1.6000 | 7 | 4 | 1 | 40 | 56 | 87 | 30 | 117 | no | e23ba3e652a9dcd3 |
| 1.0666666666666667 (= 1.6/1.5) | 2 | 0.8000 | 13 | 8 | 1 | 126 | 208 | 319 | 110 | 429 | yes | ac9eaef3f69c5d10 |
| 1.0666 | 2 | 0.8000 | 13 | 8 | 1 | 126 | 208 | 319 | 110 | 429 | no | ac9eaef3f69c5d10 |
| 1.0 | 2 | 0.8000 | 13 | 8 | 1 | 126 | 208 | 319 | 110 | 429 | no | ac9eaef3f69c5d10 |
| 0.9 | 2 | 0.8000 | 13 | 8 | 1 | 126 | 208 | 319 | 110 | 429 | no | ac9eaef3f69c5d10 |
| 0.8 | 2 | 0.8000 | 13 | 8 | 1 | 126 | 208 | 319 | 110 | 429 | no | ac9eaef3f69c5d10 |
| 0.75 | 2 | 0.8000 | 13 | 8 | 1 | 126 | 208 | 319 | 110 | 429 | no | ac9eaef3f69c5d10 |
| 0.7 | 2 | 0.8000 | 13 | 8 | 1 | 126 | 208 | 319 | 110 | 429 | no | ac9eaef3f69c5d10 |
| 0.65 | 2 | 0.8000 | 13 | 8 | 1 | 126 | 208 | 319 | 110 | 429 | no | ac9eaef3f69c5d10 |
| 0.6401 | 2 | 0.8000 | 13 | 8 | 1 | 126 | 208 | 319 | 110 | 429 | no | ac9eaef3f69c5d10 |
| 0.64 | 2 | 0.8000 | 13 | 8 | 1 | 126 | 208 | 319 | 110 | 429 | no | ac9eaef3f69c5d10 |
| 0.6399 | 3 | 0.5333 | 20 | 12 | 2 | 273 | 480 | 730 | 249 | 979 | yes | ef243559cd57551b |
| 0.6 | 3 | 0.5333 | 20 | 12 | 2 | 273 | 480 | 730 | 249 | 979 | no | ef243559cd57551b |
| 0.55 | 3 | 0.5333 | 20 | 12 | 2 | 273 | 480 | 730 | 249 | 979 | no | ef243559cd57551b |
| 0.5 | 3 | 0.5333 | 20 | 12 | 2 | 273 | 480 | 730 | 249 | 979 | no | ef243559cd57551b |
| 0.46 | 3 | 0.5333 | 20 | 12 | 2 | 273 | 480 | 730 | 249 | 979 | no | ef243559cd57551b |
| 0.4571428571428572 (= 1.6/3.5) | 4 | 0.4000 | 26 | 16 | 2 | 459 | 832 | 1262 | 429 | 1691 | yes | 2531f1bd3b2d0c89 |
| 0.45 | 4 | 0.4000 | 26 | 16 | 2 | 459 | 832 | 1262 | 429 | 1691 | no | 2531f1bd3b2d0c89 |
| 0.4 | 4 | 0.4000 | 26 | 16 | 2 | 459 | 832 | 1262 | 429 | 1691 | no | 2531f1bd3b2d0c89 |
| 0.36 | 4 | 0.4000 | 26 | 16 | 2 | 459 | 832 | 1262 | 429 | 1691 | no | 2531f1bd3b2d0c89 |
| 0.35 | 5 | 0.3200 | 32 | 20 | 2 | 693 | 1280 | 1938 | 657 | 2595 | yes | c225fb73717d9ad0 |
| 0.32 | 5 | 0.3200 | 32 | 20 | 2 | 693 | 1280 | 1938 | 657 | 2595 | no | c225fb73717d9ad0 |
| 0.3 | 5 | 0.3200 | 32 | 20 | 2 | 693 | 1280 | 1938 | 657 | 2595 | no | c225fb73717d9ad0 |
| 0.26667 | 6 | 0.2667 | 39 | 24 | 3 | 1000 | 1872 | 2829 | 956 | 3785 | yes | 8e2eaf9f73faedeb |
| 0.25 | 6 | 0.2667 | 39 | 24 | 3 | 1000 | 1872 | 2829 | 956 | 3785 | no | 8e2eaf9f73faedeb |
| 0.23 | 7 | 0.2286 | 46 | 28 | 4 | 1363 | 2576 | 3888 | 1311 | 5199 | yes | 45740f14cad15b83 |
| 0.2286 | 7 | 0.2286 | 46 | 28 | 4 | 1363 | 2576 | 3888 | 1311 | 5199 | no | 45740f14cad15b83 |
| 0.2 | 8 | 0.2000 | 52 | 32 | 4 | 1749 | 3328 | 5020 | 1691 | 6711 | yes | d10dc822bb7c4653 |
| 0.19 | 8 | 0.2000 | 52 | 32 | 4 | 1749 | 3328 | 5020 | 1691 | 6711 | no | d10dc822bb7c4653 |
| 0.18 | 9 | 0.1778 | 58 | 36 | 4 | 2183 | 4176 | 6296 | 2119 | 8415 | yes | f5b2a6d9852e9f1a |
| 0.16 | 10 | 0.1600 | 65 | 40 | 5 | 2706 | 5200 | 7835 | 2634 | 10469 | yes | 5f51451dda4833e9 |
| 0.15 | 11 | 0.1455 | 72 | 44 | 6 | 3285 | 6336 | 9542 | 3205 | 12747 | yes | 1e62cb1d62d7ad84 |
| 0.14 | 11 | 0.1455 | 72 | 44 | 6 | 3285 | 6336 | 9542 | 3205 | 12747 | no | 1e62cb1d62d7ad84 |
| 0.13333 | 12 | 0.1333 | 78 | 48 | 6 | 3871 | 7488 | 11274 | 3785 | 15059 | yes | c3f44e5238d7448a |
| 0.12 | 13 | 0.1231 | 85 | 52 | 7 | 4558 | 8840 | 13305 | 4464 | 17769 | yes | 0b81df526f4ef322 |
| 0.1143 | 14 | 0.1143 | 91 | 56 | 7 | 5244 | 10192 | 15337 | 5144 | 20481 | yes | 2b9fe3846fee6a48 |
| 0.11 | 15 | 0.1067 | 98 | 60 | 8 | 6039 | 11760 | 17692 | 5931 | 23623 | yes | 0990fb2ebb818fc2 |
| 0.1 | 16 | 0.1000 | 104 | 64 | 8 | 6825 | 13312 | 20024 | 6711 | 26735 | yes | 4d2e664b9a5047ba |
| 4.0 | — | — | — | — | — | — | — | — | — | — | — | REFUSED (see below) |
| 5.0 | — | — | — | — | — | — | — | — | — | — | — | REFUSED (see below) |

48 successful rows, 3 refused, 3 fingerprint values distinct per band-boundary crossing and
the same inside every band. Zero rows inside a band differ from the row above them.

## Table 2 — the three spacings, side by side

| h (mm) | `hl.grid_for` | nz_sub | cell (mm) | ny x nz | n_e | n_n | n_dof | fp |
|---|---|---|---|---|---|---|---|---|
| 1.2 | (1, 0.0016) | 1 | 1.6 | 7 x 4 | 87 | 30 | 117 | e23ba3e652a9dcd3 |
| 1.6 | (1, 0.0016) | 1 | 1.6 | 7 x 4 | 87 | 30 | 117 | e23ba3e652a9dcd3 |
| 2.0 | (1, 0.0016) | 1 | 1.6 | 7 x 4 | 87 | 30 | 117 | e23ba3e652a9dcd3 |

Three spacings, one mesh, byte-identical node/edge/triangle arrays. This reproduces
`decisions.md` 158.3 exactly (117-dof, `nz_sub = 1`, cell 1.6 mm, 7 x 4) and its two
reference points: `h = 0.4` -> `n_e` 1262 / `n_n` 429 / `n_dof` 1691 (26 x 16) and
`h = 0.8` -> 319 / 110 / 429 (13 x 8).

## Table 3 — the band structure, and the largest `h` in each band

`nz_sub = int(round(H/h))` with Python's round-half-to-**even**. The tie cases are not
decoration: they decide both the top of band 1 and the top of band 3.

| nz_sub | window of `h` (mm) | cell (mm) | mesh | n_e / n_n / n_dof | largest `h` verified with a **distinct** mesh |
|---|---|---|---|---|---|
| 1 | (1.0666666..., **3.2**) — 3.2 itself excluded | 1.6000 | 7x4 | 87 / 30 / 117 | **3.1999999** (12 sampled `h` in the band, all one fp) |
| 2 | [1.0666666..., **0.64**] — both ends included | 0.8000 | 13x8 | 319 / 110 / 429 | **1.0666666666666667** (= 1.6/1.5; one ulp above it falls back to `nz_sub = 1`) |
| 3 | (0.64, 0.4571428...) — 0.64 excluded | 0.5333 | 20x12 | 730 / 249 / 979 | **0.639999999** (0.64 itself rounds to `nz_sub = 2`) |
| 4 | [0.4571428..., 0.35555...) | 0.4000 | 26x16 | 1262 / 429 / 1691 | 0.4571428571428572 (= 1.6/3.5; round(3.5) = 4, so the band's top is inclusive) |

Reading: the top of band 1 is `h = 3.2` **exclusive** because `round(0.5) = 0` (even) and
`nz_sub = 0` is refused; the top of band 3 is `h = 0.64` **exclusive** because `round(2.5) = 2`;
the top of band 2 is `h = 1.6/1.5` **inclusive** because `round(1.5) = 2`. So the mesher's
`h`-to-mesh map is not even monotone at the exact half-integer ties.

## Refusals, verbatim

```
hl.grid_for(3.2)     ->  LadderError: h = 3.2 mm is coarser than the substrate H = 1.6 mm
hl.grid_for(4.0)     ->  LadderError: h = 4 mm is coarser than the substrate H = 1.6 mm
hl.grid_for(5.0)     ->  LadderError: h = 5 mm is coarser than the substrate H = 1.6 mm
hl.build_modal(3.2e-3, clearance=3.0, n_strip=1, w_m=0.8e-3, k0=209.78570331727553)
                     ->  LadderError: h = 3.2 mm is coarser than H
dm.section(3.2e-3, 3.0, H=1.6e-3, W=0.8e-3, clearance_lateral=3.0)
                     ->  ValueError: h = 0.0032 is coarser than the substrate H = 0.0016
```

Largest `h` at which the mesher succeeds: **3.1999999 mm** (`nz_sub = 1`, 117 dof).
Note on the harness: my `measure()` divides by `nz_sub` *before* calling `dm.section`, so a
refused `h` surfaces first as this harness's own `ZeroDivisionError`; the mesher's own
message is the `ValueError`/`LadderError` pair quoted above, and that is what a caller of
`host_ladder` sees.

## `n_dof < 20000` frontier

Scanning one `h` per band (`h = 1.6/nz_sub`, i.e. `cell = h`): `n_dof` stays under 20000 up to
**`nz_sub = 13`** (`h = 0.12308 mm`, `n_dof` 17769) and crosses it at `nz_sub = 14`
(`h = 0.11429 mm`, `n_dof` 20481). The five `RUNGS_MM` rungs are `nz_sub` = 4, 6, 8, 10, 12
(`n_dof` 1691, 3785, 6711, 10469, 15059) — all inside the budget, and all five meshes distinct
(`fp` 2531f1bd / 8e2eaf9f / d10dc822 / 5f51451d / c3f44e52).

## What this does not establish

It does not measure error, convergence order or accuracy at any `h`: it counts the mesh that
the mesher produces. It says nothing about the `strip_width` production configuration
(`--box-lateral-mult 8 --box-lid-mult 1 --strip-width-mm 2.0`), where `W` and the lateral
padding differ and `n_strip = max(round(W/cell), 1)` will therefore move with `cell` in a
different pattern — a 5 cm-wide box at `lat 8x` also changes `ny`, and none of that was run
here. It does not adjudicate whether `h = 1.2 / 1.6 / 2.0 mm` was *ever* used as a refinement
ladder in any artefact; it establishes only that those three spacings cannot have been three
meshes. And it assumes `dm.section`'s own rounding stays in step with `grid_for`'s: that
equality is verified on the 48 rows of table 1, not proved.
