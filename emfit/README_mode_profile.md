# `emfit/mode_profile.py` -- the transverse field of a microstrip cross-section

**Library code: commit it.** (The `.scratch/` harness that measured the numbers
below is throwaway and should not be committed.) No frozen script and no entry in
`emfit/studies.py` was touched by this work; the module and
`tests/test_mode_profile.py` are the whole of it.

## What it computes

`emfit/quasistatic.py` answers *how much* -- `C'`, `Z0`, `eps_eff` -- from a
scalar potential solve on the transverse plane. This module keeps the **field**
that same solve produces and hands it over in the layout a time-domain run
needs:

| array | lattice position | shape | unit |
| ----- | ---------------- | ----- | ---- |
| `e_y` | y-cell x z-node (`EY` edge) | `(ny, N2)` | V |
| `e_z` | y-node x z-cell (`EZ` edge) | `(N1, nz)` | V |
| `h_y` | collocated with `e_z` (`FY`) | `(N1, nz)` | A |
| `h_z` | collocated with `e_y` (`FZ`) | `(ny, N2)` | A |

plus `phi` on the nodes and the line parameters of the same solve
(`c_prime`, `c_prime_air`, `eps_eff`, `z0`, `eta_eff`). The fields live on the
**staggered edges of the FIT/Yee lattice the solver is already built on**, so no
interpolation is involved, and `h` is the local plane-wave companion of `e`
(`h = (1/eta_eff) x_hat x e`, i.e. the forward-travelling wave). Values are
`E . dl` in volts per edge, not V/m; divide by `cell` for V/m.

## Normalisation: the strip is at exactly 1 V

The strip is held at `1 V` and the ground plane at `0 V`, so the potential
*difference* across the gap is 1 V by construction and `phi` is already the
normalised potential. This is checkable, not assumed: the vertical z-edges of
every strip column telescope,

    sum_{k < n_sub} e_z[i, k] = -(phi[i, n_sub] - phi[i, 0]) = -1 V,

exactly to roundoff. `microstrip_mode_profile(..., check=True)` (the default)
asserts it, together with the energy identity `sum(m e^2)/(V^2 L) = phi^T K phi
/(V^2 L) = C'`, `C'` against `capacitance_per_length`, and `eps_eff`/`Z0` against
`z0_eps_eff`, at `rtol = 1e-12`.

## Converged defaults, from a measured plateau

    n_sub   = 16     -> cell = h/16 = 0.1 mm, the production FDTD board's cell
    n_clean = 200    -> 20 mm of clean dielectric each side of the strip
    n_air   = 200    -> 20 mm of air above it

431 x 217 nodes, 43.0 x 21.6 mm. These are **not** plane-sized: they were set
from a box sweep (`.scratch/mp_study.py`) that showed `eps_eff` and `Z0` flattening
but not yet vertical -- the last 5 mm of lateral wall still moves `eps_eff` by
0.33 %, the last 8 mm of air by 0.19 %, and the walls bind harder than the air
ceiling (0.119 %/mm vs 0.093 %/mm). The box is deliberately much wider than any
FDTD plane so the physics is settled first and placement is a separate,
index-level step.

At the defaults (`h = 1.6 mm`, `W = 3.0 mm`, `eps_r = 4.4`):

| quantity | value | vs Hammerstad-Jensen |
| -------- | ----- | -------------------- |
| `c_prime` | 1.218889992e-10 F/m | -- |
| `c_prime_air` | 3.638468335e-11 F/m | -- |
| `eps_eff` | **3.350008519** | +0.74 % (fit: 3.325455) |
| `Z0` | **50.08846719** ohm | -1.05 % (fit: 50.617262) |
| `eta_eff` | **205.8294963** ohm | -- |

Both deviations are inside the closed form's own ~1 % accuracy, so the pair is
consistent with the oracle rather than merely near it.

## Clipping: the profile is normally wider than the plane

`ModeProfile.plane_window()` places the profile in a different transverse plane
by **integer index offset** (same cell size, same strip node row), so the Yee
stagger survives the copy. Because the converged box is wider than the
production plane, it **clips** rather than raising -- and reports what it
clipped:

    profile 431 x 217  ->  FDTD plane 201 x 77 nodes (20.0 x 7.6 mm)
    iy_shift = -115, k_shift = 0, dropped = 740 source entries
    report(): e_y/h_z, y: 115 below, 115 beyond; e_y/h_z, z: 0 below, 140 beyond;
              e_z/h_y, y: 115 below, 115 beyond; e_z/h_y, z: 0 below, 140 beyond

* the destination slices fill the plane **exactly** (200 y-cells / 201 y-nodes,
  77 z-nodes / 76 z-cells), and the strip lands on `k = 16`, `iy = 100`;
* **98.208 %** of `sum e_y^2` is retained, and the placed strip column still
  telescopes to `v_mode` bit-for-bit -- no renormalisation is needed;
* **1.164852 % of the modal power is invisible to the FDTD plane** (from a
  `0.5/eta * int |E_t|^2 dA` integral on the converged profile). The projection
  window is the **full 201-node plane, `|y| = 10 mm`**; the `8.5 mm` width that
  appears in older notes was the *PML-interior* width, **not** the projection
  domain, and is not the boundary this number refers to.

  Of the 1.164852 % outside the projection plane, 0.571953 % lies beyond the
  lateral `|y| = 10 mm` boundary, 0.780454 % above the z ceiling, and 0.187555 %
  in the corner counted by both; the decomposition satisfies inclusion-exclusion
  to all printed digits. Most of the invisible modal power leaves through the
  ceiling, not the sides.

  1.164852 % of the modal power lies outside the FDTD box. This is a constant
  lateral truncation, identical at every station, so it biases the LEVEL of a
  projection and cannot contribute to a decay along x; the observed decay is
  separately accounted for by the lateral PML flux that sx_station measures. It
  is therefore not in the decay budget at all, and with unit-power normalisation
  over the projection window it does not bias the level either.

  For the record: the earlier 1.1466 % figure was computed on a **different
  window** (a clip at `|y| = 8.5 mm`) and must never be quoted alongside the
  projection numbers -- two numbers for one quantity is how a bookkeeping
  artefact starts.

`PlaneWindow` exposes the audit trail as `clipped`, `dropped`, `full_coverage`
and `report()`; only a placement with *no* overlap at all (or a mismatched cell
size, or `k_strip < n_sub`) still raises `ValueError`.

## Tests

`tests/test_mode_profile.py`, 12 tests, all passing in ~17 s: the edge field as
the exact gradient of `phi`; the `v_mode` telescoping over all five strip columns
(roundoff) and the per-cent fringing bound off the strip; the normalisation
domain (unit power on the projection window, 1.01178580 W on the wide box); `e_z < 0` over the whole
strip footprint; verticality under the strip; `h = e/eta` bit for bit; and the
placement both ways -- clipped (98.208 % retained, 740 dropped) and unclipped
(pure offset, `nothing clipped`), plus the three rejections.
