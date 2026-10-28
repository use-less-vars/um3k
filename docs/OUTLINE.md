# emfit -- living project outline

`emfit` is a 3-D Finite Integral Technique (FIT, Weiland) solver for computational electromagnetics: Maxwell's
equations on interlocked cell complexes, with topology (`G`, `C`, `S` in {-1, 0, +1}) kept strictly separate from
metric (the diagonal Hodge stars `M_eps`, `M_mu`), so uniform and graded grids run on identical algebra. Today it is
an explicit leapfrog time-domain integrator with an *exactly* conserved discrete energy, a PEC-cavity eigenmode
solver validated mode-by-mode against the analytic box spectrum (1.213 % coarse, 0.615 % fine, second order), and a
truncated open region: first-order Mur on the six outer faces plus a matched lossy layer (`emfit/pml.py`) that
reflects at `-79.09 dB` against Mur's `-49.58 dB` at normal incidence. On top of that it now scatters and measures:
a 2-D TMz PEC cylinder in a plane-wave-like beam (`emfit/scatter.py`), a near-to-far-field transform on a contour
around the body (`emfit/nearfield.py`), and an exact Mie series to check the result against (`emfit/mie.py`), which
agrees to `1.830 dB` rms and `3.202 dB` worst case at ka = 3. Five studies run from one command line or from one
local web page. What it still cannot do: drive a port or an antenna, import geometry (staircase only), run lossy or
dispersive materials, or scatter anything other than a z-invariant PEC cross-section; and its eigenmode path is
dense, stopping at 3000 free edges.

For how the machine got here -- the order the pieces were built in, the measurement that forced
each turn, and the numbers that were withdrawn along the way -- see [`HISTORY.md`](HISTORY.md).
It is the narrative these documents imply when read together; this file stays the statement of
where things stand.

## Where we are

**Works today**

- 3-D FIT time-domain solver, PEC walls on any subset of the six faces, plus Ricker soft sources (`emfit/maxwell.py`,
  `emfit/evolve.py`).
- Exact energy conservation: relative drift `1.298e-15` over 2000 steps -- machine precision, not merely "small"
  (`tests/test_energy.py`).
- PEC cavity eigenmodes: 6 modes of a `1.0 x 0.7 x 0.5 m` box, mean error 1.213 % on `10x7x5`, 0.615 % on `14x10x7`,
  every mode below the analytic value, and a measured error ratio `0.507` against the theoretical `1/1.4^2 = 0.510`
  (second order).
- Graded (non-uniform) grids: they change only the metric, never the integer operators
  (`tests/test_operators.py::test_operators_are_metric_free`).
- Periodic axes: the seam bookkeeping keeps one value per seam edge, closes the dual widths, and leaves the exact
  topological identities intact on a torus, so a periodic axis is a boundary option and not a second solver
  (`emfit/operators.py`, `tests/test_periodic.py`, 9 tests).
- Headless plotting layer -- spectrum, field slice, energy history -> PNG, Agg backend, no GUI (`emfit/viz.py`).
- First-order Mur absorbing boundary (`emfit/abc.py`): `Mur1Boundary` updates the tangential `e` on the six outer
  faces in fixed plane order, so no edge is double-updated at an edge or corner; a pulse leaves a 2-D PEC duct with
  `-49.57 dB` and `-49.58 dB` of reflection against `-49.24 dB` of discrete-dispersion theory (`tests/test_abc.py`).
- Matched PML (`emfit/pml.py`, class `PML`): a lossy layer whose electric and magnetic profiles are matched
  (`sigma_m/mu0 = sigma_e/eps0`), applied as a per-step multiplicative damping of `e` and `h` -- no split fields, no
  extra state, and no tensorial Hodge stars. At normal incidence, measured as the two-run difference between the two
  terminations, it reflects at `-79.09 dB` against Mur's `-49.58 dB`, and `FITStepper(pml=None)` is asserted
  bit-identical to the pre-PML stepper (`tests/test_pml.py`, 7 tests).
- 2-D TMz scattering off a PEC cylinder (`emfit/scatter.py`): the PEC edge mask is built from edge coordinates rather
  than a cell-centre radius, and the scattered field is the difference between a with-body and a without-body run of
  the same grid (`tests/test_scatter.py`, 3 tests).
- Exact 2-D TMz Mie series as a reference, not as a solver (`emfit/mie.py`): truncation rule, `abs(b_n) <= 1`,
  optical theorem, `(1/2 pi) int sigma dphi = sigma_tot` (`tests/test_mie.py`, 5 tests).
- Near-to-far-field transform (`emfit/nearfield.py`): `DFTAccumulator` phasors on an axis-aligned `Contour`, a
  Kirchhoff far-field integral, and a bistatic scattering width `sigma(phi)`. Validated on a point source whose
  closed form is known: `abs(a)` flat to `0.4 %` against `0.25 sqrt(2/(pi k))` and the phase ramp recovering `k x0`
  and `k y0` to `1.6e-3` with the right signs (`tests/test_nearfield.py`, 5 tests).
- One study registry, two front ends (`emfit/studies.py`, `emfit/cli.py`, `emfit/__main__.py`, `emfit/webapp.py`):
  `python -m emfit list`, `run <study>`, and `serve` on `http://127.0.0.1:8010` (`--port N`,
  since 8000 is usually taken). Values are validated by
  `emfit.studies.coerce`, and the web app runs one study at a time behind a lock (`tests/test_webapp.py`, 7 tests).
- 483 tests in about 13 min (469 with `-m "not slow"`), every number locked by an explicit tolerance.
- 5 studies and 2 example scripts, writing eight figures into `docs/figures/`.

**Does not work yet**

- Only 2-D scattering: the radiating body is a z-invariant PEC cross-section, so there are no spheres, no dipoles and
  no 3-D patterns. The incident front is plane-wave-*like*, not a plane wave -- the y-PML that should absorb the
  drive also damps its own footprint, and the centre-line profile `abs(Ez)/peak` is `0.07, 0.58, 1.00, 0.92, 1.00,
  0.07`; a PEC y-wall is worse, and a TF/SF injector was designed and deliberately rejected.
- The Mie target is missed: bistatic RCS of the cylinder at ka = 3 sits at `1.830 dB` rms and `3.202 dB` worst case
  against the `0.5 dB` the milestone asked for, with a broad ~`2 dB` underestimate on the shadow side that is left
  visible rather than tuned away.
- The PML is validated at normal incidence only. Oblique incidence is unmeasured, and the reflection stalls near
  `-45 dB` once the damping exceeds about `1.5 Np/cell`, so the sizing law cannot be pushed past about two
  wavelengths.
- Staircase geometry: a curved body aliases to whole cells, and at ka = 1 the mask area is already `+16 %` off at
  3.18 cells of radius.
- No ports, no S-parameters, no de-embedding (M3): nothing is driven but a soft edge current.
- No antenna feed or terminal impedance, so the half-wave dipole acceptance test (73 ohm, 2.15 dBi) of M2 is not
  reachable -- it is blocked on geometry, not on numerics.
- No geometry import: structures are PEC faces of a rectangular grid -- staircase only, no CAD/KiCad path (M4).
- No conductivity or dispersion in the stepper: `M_sigma` is assembled but unconsumed, so no loss, no skin depth, no
  eddy currents (M6).
- Eigenmodes are dense (`scipy.linalg.eigh`) with a hard `max_dense = 3000` free-edge stop -- ~2.4x the largest
  validated grid, far from the 10^5 target (M5). The eigensolver's energy cache also has a cliff: 60x60 takes 64 s
  where 40x40 takes 0.09 s.

## Architecture at a glance

```text
   Grid ................................... emfit/grid.py
     |  nodes; cell/dual widths, edge lengths, face areas, volumes; periodic axes
     v
   CellComplex (topology) ................. emfit/operators.py
     |  G, C, S in {-1,0,+1} + duals; index helpers; PEC tangential-edge mask
     v
   Hodge stars (metric) ................... emfit/materials.py
     |  diagonal M_eps, M_mu, M_sigma; C0; scalar or per-entity parameters
     v
   FITSystem .............................. emfit/maxwell.py
     |  C e = -d/dt(M_mu h)   C^T h = d/dt(M_eps e) + j   (PEC as constraint e = (e_free, 0))
     +------------------+--------------------+
     |                  |                    |
     v                  v                    v
   FITStepper        resonances()         M_sigma: built, unused (M6 hook)
   time domain       eigenmodes
   emfit/evolve.py   emfit/eigen.py
     |                  |
     |                  +--> emfit/mie.py ...... exact 2-D TMz series (reference only)
     v
   post-step hooks on the outer faces
     |
     +-- Mur1Boundary ....... emfit/abc.py    e_tan update, fixed plane order
     +-- PML ................ emfit/pml.py    per-step multiplicative damping in the layer
     |
     v
   emfit/scatter.py ....... PEC mask from edge coordinates; (total - background) pair
     |
     v
   emfit/nearfield.py ..... DFT phasors on a Contour -> Kirchhoff integral -> sigma(phi)
     |
     v
   emfit/studies.py ....... registry: cavity, modes, duct, scatter, rcs; coerce; FigureSink
     |
     +--> emfit/cli.py + emfit/__main__.py .... python -m emfit list | run <study>
     +--> emfit/webapp.py ..................... python -m emfit serve, 127.0.0.1:8010
     +--> emfit/viz.py ........................ PNG figures
```

Two invariants hold in exact integer arithmetic; everything else rests on them.

- `C @ G == 0` identically -- the curl of a gradient vanishes, so discrete Faraday never invents a field
  (`test_curl_of_gradient_is_zero`, `test_identities_hold_on_uniform_grid`).
- `S @ C == 0` identically -- the divergence of a curl vanishes, so the Ampere update conserves charge exactly
  (`test_divergence_of_curl_is_zero`).
- Both are metric-free: the same integer matrices serve uniform and graded grids, so refinement or stretching can only
  change the metric -- never the algebra, hence never the conservation laws. That is also why the leapfrog has a
  closed-form invariant `U = 0.5 e.(M_eps e) + 0.5 h.(M_mu h) - 0.5 dt (C e).h`, conserved to 1e-15.
- `S C = 0` additionally tells us the gradient null space analytically -- exactly the subspace the eigenmode solver
  must cut out (Research log, finding 5).
- The PML cannot break either invariant, because it never touches `C`, `G` or `S`: it multiplies `e` and `h` after
  the step, and the `pml=None` path is asserted bit-identical to the plain stepper.

## Numbers board

Every value below is asserted by a test unless the row says *study*; break one and the suite goes red.

| Quantity | Value | Locked by |
| -------- | ----- | --------- |
| Relative energy drift, 12x10x8, 2000 steps | `1.298e-15` (assert < 1e-6) | `tests/test_energy.py::test_energy_exact_conservation` |
| Drift with all six PEC walls | exact (assert < 1e-10) | `tests/test_energy.py::test_pec_conservation` |
| CFL sharpness | bounded at 1.01x, diverges at 1.02x `cfl_dt` (x6.7e122) | `tests/test_energy.py::test_cfl_bound_is_sharp` |
| Wavefront speed | `0.904 c`, 40x6x6, lambda ~ 10 cells | `tests/test_energy.py::test_wave_propagates_at_c` |
| Cavity `10x7x5` (n_free 762) | mean abs err `1.213 %`, max `1.390 %`, all low | `tests/test_cavity.py::test_coarse_grid_approximates_analytic_modes` |
| Cavity `14x10x7` (n_free 2355) | mean `0.615 %`, max `0.711 %`, all low | `tests/test_cavity.py::test_fine_grid_approximates_analytic_modes` |
| Convergence ratio 1.213 / 0.615 | `0.507` (theory `0.510`) | `tests/test_cavity.py::test_error_converges_at_second_order` |
| Analytic modes 1-6 | 261.388 / 335.178 / 368.416 x2 / 397.743 x2 MHz | `tests/test_cavity.py::test_analytic_reference_spectrum` |
| Static modes cut | `216 = 9*6*4`, `702 = 13*9*6` = `(nx-1)(ny-1)(nz-1)` | `tests/test_cavity.py::test_coarse_grid_static_mode_count` |
| Non-physical modes rejected | `0` on both grids | same two cavity tests |
| TE/TM degenerate pairs | equal to 1e-6 relative | `tests/test_cavity.py::test_coarse_grid_degenerate_pairs_coincide` |
| Hodge-star scaling | 2x cell -> exactly 2x `M_eps`, 2x `M_mu` | `tests/test_energy.py::test_material_matrix_units` |
| Dense eigensolver guard | `NotImplementedError` above `max_dense = 3000` free edges | `tests/test_cavity.py::test_dense_limit_raises_not_implemented` |
| Periodic seam | exactly one value per seam edge, no seam layer | `tests/test_periodic.py::test_seam_holds_exactly_one_value` |
| Periodic topology | `C G = 0` and `S C = 0` hold on a torus | `tests/test_periodic.py::test_torus_keeps_the_exact_topological_identities` |
| Periodic group velocity | matches the unbounded Yee stencil | `tests/test_periodic.py::test_group_velocity_matches_unbounded_yee` |
| Energy on a torus | conserved | `tests/test_periodic.py::test_energy_conserved_on_torus` |
| Mur-1 duct end reflections, 320x16x1 | `-49.57 dB` / `-49.58 dB` (assert < -40 dB), theory `-49.24 dB` | `tests/test_abc.py::test_mur_absorbs_outgoing_pulse` |
| Mur `K -> 0` limit | one-cell translation, bit-identical (`rtol 1e-15`) | `tests/test_abc.py::test_k_zero_limit_is_one_cell_translation` |
| PEC control | `+0.21` / `+0.22 dB`, i.e. the wall does reflect | `tests/test_abc.py::test_pec_control_reflects` |
| PML vs Mur, pytest duct geometry | Mur `-26.50 dB`, PML `-65.47 dB`, margin `38.97 dB` (assert >= 10 dB) | `tests/test_pml.py::test_pml_reflects_at_least_10_db_less_than_mur` |
| PML `sigma_max` | closed form to relative `1e-15` | `tests/test_pml.py::test_sigma_max_matches_the_closed_form` |
| PML interior / corner | `sigma_e = 0.0` exactly inside; corner = sum of both 1-D profiles | `tests/test_pml.py::test_sigma_is_zero_in_the_interior_and_grows_into_the_layer`, `::test_corner_sigma_is_the_sum_of_the_two_profiles` |
| PML per-step damping | in `(0, 1]`, matches `exp(-sigma dt/eps0)` to `1e-14`, non-increasing | `tests/test_pml.py::test_multipliers_are_bounded_exact_and_monotone` |
| PML energy after the source stops | monotone non-increasing, last value < `1e-3` of the first | `tests/test_pml.py::test_energy_decays_monotonically_after_the_source_stops` |
| PML oversize guard | a layer thicker than half the grid is refused | `tests/test_pml.py::test_layer_thicker_than_half_the_grid_is_refused` |
| PML, normal incidence, two-run difference | PML `-79.09 dB` against Mur `-49.58 dB`; phase velocity `1.00693 c` | *study*: `python -m emfit run duct --set termination=pml` |
| PML sizing law | ~1 wavelength `-52 dB`, ~2 wavelengths `-79 dB`; 20 vs 40 cells per wavelength at equal thickness agree to `0.6 dB` | *study* measurements, inverted by `cells_for_wavelength(lam0, h, target_db=-79)` |
| PEC disc edge count, ka = 3 | `293` edges vs `286.5` analytic, area ratio `1.023` (assert within 10 %) | `tests/test_scatter.py::test_pec_mask_area_matches_the_disc` |
| Empty mask | scattered field bitwise zero (`np.array_equal`) | `tests/test_scatter.py::test_empty_mask_gives_an_exactly_zero_scattered_field` |
| `ez` on PEC nodes | exactly `0.0` | `tests/test_scatter.py::test_scattered_field_is_large_and_forward_peaked` |
| Scatter peak ratio, ka = 3 | `253.620 / 193.873 V/m = 0.9233`, forward peaked | *study*: `python -m emfit run scatter` |
| Near-field `abs(a)` flatness | `0.4 %` against `0.25 sqrt(2/(pi k))` at 20 ppw; asserted 2 % with `0.2 dB` ripple | `tests/test_nearfield.py::test_point_source_amplitude_is_flat_and_correctly_normalised` |
| Near-field phase slopes | `k x0`, `k y0` recovered to `1.6e-3`, correct signs (assert 1 %) | `tests/test_nearfield.py::test_point_source_phase_ramp_has_the_right_slopes` |
| Zero phasor | exactly zero amplitude and zero width | `tests/test_nearfield.py::test_zero_phasor_gives_exactly_zero_amplitude_and_width` |
| DFT accumulator | phasor equals the closed form for every frequency | `tests/test_nearfield.py::test_accumulator_reproduces_the_closed_form_phasor` |
| Mie series | `abs(b_n) <= 1`, optical theorem, `(1/2 pi) int sigma dphi = sigma_tot` | `tests/test_mie.py::test_coefficients_are_lossless`, `::test_optical_theorem_forward_amplitude`, `::test_bistatic_pattern_integrates_to_total_width` |
| Bistatic RCS vs Mie, ka = 3 | rms `1.830 dB`, worst `3.202 dB` at 284 deg, every point within 6 dB (assert) | `tests/test_nearfield.py::test_scattering_width_beats_the_mirror_and_tracks_mie` |
| Web front end | unknown path 404, out-of-range value 400 not 500, `healthz` plain ok | `tests/test_webapp.py` (7 tests) |
| Suite | 483 tests, about 13 min (469 with `-m "not slow"`) | `python -m pytest` |

## Milestone tracker

Reproduced from the summary table in `README.md`, which stays the authority for the rows and for the first five
columns; this outline only adds one extra final column, the next concrete step. [`docs/roadmap.md`](roadmap.md) still
carries an older copy of that table (34 passed, no PML, M2 PLANNED), so treat it as the source for the detailed
per-milestone plans, not for the status columns.

| ID | Milestone | Status | Key deliverable | Acceptance test | Next action |
| -- | --------- | ------ | --------------- | --------------- | ----------- |
| M0 | Time-domain core + cavity eigensolver | DONE | `emfit/{grid,operators,materials,evolve,maxwell,eigen,viz}.py` | 71 passed; mean error 1.213 % / 0.615 %, ratio 0.507 | Nothing to build -- keep the suite green |
| M1 | Absorbing boundaries (Mur, then PML) | IN PROGRESS | Mur-1 (`emfit/abc.py`) and a matched PML (`emfit/pml.py`), both tested and demoed | absorber validated to -79.09 dB at normal incidence (Mur -49.58 dB); the target was PEC-sphere bistatic RCS vs Mie, ka = 1, 3: < 0.5 dB, and what was achieved is a 2-D PEC cylinder at ka = 3: rms 1.83 dB, max 3.20 dB | Sweep the two-run difference in angle: the layer is built and needs no tensor metric, so the open question is oblique incidence -- and the measured stall near -45 dB past ~1.5 Np/cell, which caps the useful thickness |
| M2 | Near-to-far-field transform and antennas | IN PROGRESS | `emfit/nearfield.py` delivered and validated, with `emfit/mie.py` as the exact reference | no feed and no port, so the half-wave dipole test (73 ohm, 2.15 dBi) is not reachable in the current 2-D TM code | Give the cylinder a feed: a port and a terminal impedance, so a radiating-object check becomes possible without leaving 2-D |
| M3 | Waveguide ports and S-parameters | PLANNED | `emfit/ports.py` (2-D modal solve, overlaps, de-embedding) | matched WR-90 line: abs(S21) = 1.000, abs(S11) < -30 dB | Solve the 2-D modal eigenproblem on one port face, check orthogonality |
| M4 | PCB import from KiCad | PLANNED | `emfit/kicad.py`, `emfit/raster.py` | microstrip Z0 within 5 % of Hammerstad; patch in band | Raster one straight track, compare quasi-static Z0 to Hammerstad |
| M5 | Large-grid eigensolver, thin features, FEM | IN PROGRESS | `emfit/eigen.py`: ARPACK/LOBPCG on the Helmholtz-projected operator | 100k free edges, 6 modes, < 0.1 % vs dense | Deflate the gradient null space (`G G^T` projection), then `eigsh` on the deflated operator |
| M6 | MQS eddy currents and parareal | PLANNED | `emfit/mqs.py` (A-V), `emfit/parareal.py` | slab skin depth within 2 % of analytic | Wrap the existing complex in an A-V diffusion step that consumes `M_sigma` |

## Research log

### 2026-10-19 -- session 1

Each finding is a claim the code or a test already relies on; re-introducing the opposite is a regression.

1. **The conserved quantity is the mixed-state invariant, not the naive energy sum.** `U = 0.5 e.(M_eps e) + 0.5
   h.(M_mu h) - 0.5 dt (C e).h` drifts `1.298e-15` over 500 steps on 12x10x8 random fields, while every "obvious"
   alternative drifts at O(1): `+` sign 4.79e-01, `h_prev` in the mixed product 3.40e-01, no correction term 3.71e-01.
   So `FITStepper.energy()` is the only acceptable definition; any refactor must reproduce this number.
2. **The Courant bound is sharp, so the default `safety = 0.99` is mandatory.** White noise on 12x10x8: 0.98x `cfl_dt`
   stays bounded (x9.8e2, flat out to 5000 steps), 1.01x still bounded, 1.02x already at x6.7e122. Never expose a knob
   that lets a caller run at or above `cfl_dt` -- "1.05 is probably fine" produces garbage that looks like physics.
3. **The measured wavefront speed `0.904 c` is grid dispersion, not a bug.** On 40x6x6 with 0.02 m cells and lambda ~
   10 cells the Ricker arrival time gives 0.904 c; the 10 % shortfall is the expected dispersion of a
   10-cells-per-wavelength stencil. The test therefore asserts causality (zero signal in the first three steps) plus
   `0.7 < ratio < 1.3` -- sign/units errors fail, an unattainable speed is never demanded -- and every accuracy claim
   must quote cells per wavelength.
4. **The Hodge stars are not length-invariant; both scale *linearly* with cell size.** `M_eps ~ eps0 h` (a
   capacitance), `M_mu ~ mu0 h` (an inductance), so doubling every cell exactly doubles both. "Make the metric
   dimensionless" is a wrong refactor; the sharp test is that exact 2x scaling (`test_material_matrix_units`).
5. **The PEC free-edge restriction does *not* kill the gradient null space, and a divergence test cannot see it.** Its
   dimension is exactly `(nx-1)(ny-1)(nz-1)` -- 216 on `10x7x5`, 702 on `14x10x7`. On the restricted problem `C_free
   G_free != 0`, so a strict `div e = 0` filter fails: residual 0.45-0.78 for physical modes vs 2.44-2.48 for
   gradients, the same order of magnitude. The unambiguous separator is the static-eigenvalue cut `vals > 1e-10
   lam_ref` with `lam_ref = (pi c0 / Lmax)^2`, where the null cluster sits at `1.3e-13 lam_ref` and the fundamental at
   `3.0 lam_ref` -- 12 orders of margin. This is the most load-bearing finding in the solver.
6. **`analytic_box_modes` must drop triples with exactly one non-zero index.** A mode like `(1,0,0)` violates the PEC
   tangential-H condition; triples with exactly two non-zero indices are TE/TM degenerate, so the sorted reference
   list *intentionally* repeats values (368.416 and 397.743 each twice). The reference spectrum and the "all modes
   low" assertion are only correct with that rule, and de-duplicating the list would break both.
7. **The curl residual `rcurl = ||C e|| / (||e|| omega/c0)` is not a spuriousness indicator.** It equals the mesh
   pitch `h` for *every* mode, physical or not, because it merely restates the stencil geometry. Never filter modes
   with it: the static-eigenvalue test (finding 5) is the only discriminator, and `n_rejected_nonphysical == 0` is
   asserted to keep it so.
8. **ARPACK shift-invert is a dead end here; dense `eigh` is the shipped path.** With `sigma = 0`, `eigsh` mixes null
   vectors into the physical ones (the null space is 216-702 dimensional on the validated grids); escalating `sigma`
   is worse -- it returns a window *above* the fundamental, so the lowest mode is missed silently. `resonances()`
   therefore keeps the dense path with a `max_dense = 3000` guard raising `NotImplementedError` at M5, and the roadmap
   fix is explicit gradient deflation before the Krylov solve, not a cleverer shift.

### 2026-10-19 -- session 2

1. **Both Mur history terms must be sampled at time level n, not at n and n-1.** The correct first-order update is
   `E_tan^{n+1}(0) = E_tan^n(1) + K (E_tan^{n+1}(1) - E_tan^n(0))`. The implementation detail that decides
   everything: the field snapshot must be taken *before* the leapfrog step. Taken after, the boundary reads
   `E^{n-1}` and the measured absorption collapses from `-49.6 dB` to `-9.0 dB` -- 40 dB lost while the code still
   runs and the field still looks like a wave leaving the domain. Evidence: 320x16x1 PEC duct, `dx = 7.5 mm`,
   `dt = 2.394e-11 s`, 900 steps, TE10 2 GHz pulse, both end reflections `-49.57 dB` / `-49.58 dB` against a PEC
   control of `+0.21` / `+0.22 dB`. The lesson: this was caught only because a cheap independent oracle existed,
   and that oracle is the `K -> 0` limit below.

2. **The `K -> 0` limit is an exact, free unit test of the boundary wiring.** As `K = (c dt - h)/(c dt + h) -> 0`
   the update degenerates to `E_tan^{n+1}(0) = E_tan^n(1)`, a pure one-cell translation of the boundary layer.
   That prediction is checkable bit-for-bit (`np.array_equal` plus `rtol = 1e-15`) with no physics modelling at
   all, and it catches index-map and ordering mistakes that a dB-threshold test passes happily. It must be paired
   with a positive check that the boundary still moves once `K` is restored, otherwise a completely bypassed
   update also passes.

3. **The `-49.6 dB` absorption is the discrete waveguide's dispersion floor, not a boundary-error figure.** The
   continuum prediction for the same guide, `|v_ph - c| / (v_ph + c)` at `v_ph = 1.00693 c`, is `-49.24 dB`; the
   measurement lands 0.35 dB away. The boundary is therefore already at the limit of the physics in that
   benchmark and no absorber tuning improves the number -- only a finer grid would. Corollary: the residual is a
   dispersion diagnostic, which is why the `0.904 c` wavefront and this floor must always be quoted together with
   cells per wavelength.

4. **Mur-1 is first order, so it is not a substitute for a PML.** It is exact at normal incidence in the 1-D limit
   and degrades at oblique incidence and at low frequency, where the local-plane-wave assumption fails. Its real
   value is that open-region problems stop being silently wrong; the broadband answer is a PML. Record too that a
   parallel-plate TEM validation is impossible in this codebase and must not be attempted: it needs `E = Ey`, but
   with `nz = 1` and PEC z-walls `Ey` is forced to zero, and a y-uniform `Ez` violates the PEC y-walls.

5. **The corner/edge rule must be a fixed single-owner assignment.** Every boundary-layer tangential edge is
   claimed by exactly one of the six planes, in the order xmin, xmax, ymin, ymax, zmin, zmax. Updating one edge
   from two planes double-counts the correction and destabilises the mode, so the test asserts that no edge
   appears in two planes' index arrays and that no PEC edge enters the maps at all.

### 2026-10-19 -- session 3

1. **A reflection level is measured as a two-run difference, with the *same* absorber at the near end both times.**
   Run once with the far end Mur and once with it PML, subtract, and everything except the far-end reflection
   cancels -- the source, the near-end absorption, the dispersion floor of the guide. The two runs must differ in
   one axis only, or the subtraction is meaningless. That is why the quoted `-79.09 dB` is a comparison and not an
   absolute number, and why the single-run figures (`-49.57 dB` for Mur) must never be read as a PML error bar.

2. **A Mur plane reflects at the wall; a PML reflects at its interface.** The two echoes therefore arrive at
   different times (`10.08 / 12.07 ns` for Mur against `9.38 / 11.04 ns` for PML in the 320x16x1 duct), so a
   measurement window that spans only one arrival silently compares a reflection against nothing. The window must
   cover both, and the arrival times are printed for that reason rather than for decoration.

3. **`exp(-sigma dt/eps0)` underflows in the profile tail, so the damping must be asserted monotone, not strict.**
   Deep in the layer the exponent is large enough that the multiplier rounds to `0.0`, and a strict
   `diff < 0` assertion then fails on a correct layer. The test asserts `factor` non-increasing (`diff <= 1e-15`),
   inside `(0, 1]`, and equal to the exponential to `1e-14` where it is representable. Anything stronger is a
   test bug, not a physics bug.

4. **The layer needs no split fields and no tensorial Hodge star -- the roadmap prerequisite was unnecessary.** A
   matched profile (`sigma_m/mu0 = sigma_e/eps0`, second-order polynomial, target `1e-4`) applied as a per-step
   multiplicative damping of `e` and `h` reaches `-79.09 dB` in the existing diagonal metric, and `pml=None` is
   bit-identical to the old stepper. Two consequences worth keeping: thickness is a wavelength law, not a cell count
   (`cells_for_wavelength`, ~1 wavelength `-52 dB`, ~2 wavelengths `-79 dB`, 20 vs 40 cells per wavelength at the
   same physical thickness agreeing to `0.6 dB`), and the reflection stalls near `-45 dB` once the damping exceeds
   about `1.5 Np/cell`, so "make it thicker" stops paying.

5. **A PEC mask must be built from edge coordinates, not from a cell-centre radius.** Testing "is the distance from
   the centre below r" classifies an edge differently depending on which axis it runs along, and the body area then
   comes out wrong by percent both ways: at 20 ppw the edge count is `293` against `286.5` analytic (ratio `1.023`,
   fine), but at ka = 1 the same rule gives `+16 %` area at 3.18 cells of radius. The masked nodes must also be
   read back: `ez` on a PEC node is asserted *exactly* `0.0`, and an all-false mask is asserted to reproduce the
   background bitwise (`np.array_equal`), which is the only cheap proof that the pair subtraction is honest.

6. **The eigensolver's energy cache has a cliff, so total runtimes are not a smooth function of grid size.** 40x40
   takes `0.09 s` and 60x60 takes `64 s` -- a factor of ~700 for 2.25x the grid -- because the cache crosses a size
   where the dense path stops fitting the fast tier. Any timing quoted for `modes` or `cavity` must name the grid it
   was taken on, and no timing should be inferred by interpolation.

### 2026-10-19 -- session 4

1. **The phase slope across `phi` is what catches a sign error in `exp(+j k s.r')`, and nothing else does.** A
   point source placed at the centre of the contour is isotropic, so the amplitude is flat in `phi` no matter which
   sign the exponential carries or whether `phi` is mirrored: flatness alone passes both bugs. Recovering `k x0` and
   `k y0` *with their signs* from the fitted slope (to `1.6e-3` here) is the only absolute check on the orientation
   of `n`, `dl` and the exponential, so it must stay in the suite even though the flatness gate is the number the
   milestone quotes.

2. **The far-field amplitude carries a global factor `e^(i pi)`, and it is invisible to every number reported.**
   As evaluated, the quadrature returns `-T` rather than `T`, so `a_code = -a_true`; this was confirmed twice, once
   from the Hankel asymptotics and once from an exact Green-identity quadrature that uses no asymptotics at all
   (`-1.000000`), and it cancels in `abs(a)^2`, i.e. in the scattering width. It must be written down rather than
   "fixed", and it is carried explicitly in `flatness_gate`'s expected phase so that a later reader does not chase
   a sign that is not broken.

3. **`FigureSink` was PNG-only by contract, so the animated figure needed an explicit attachment path.** The
   gallery, the web page and the tests all treat `FigureSink` as "a name and a PNG"; a GIF therefore cannot be
   sneaked in as a figure. `add_attachment` exists so the animation is declared as what it is, and it is why
   `rcs` writes a `rcs-animation.gif` next to `rcs-pattern.png` without breaking the one-figure contract.

4. **`PillowWriter` resolves its parent directory strictly, so the GIF must be written through a real temporary
   directory.** Handing matplotlib a path whose directory does not exist yet fails at animation-save time, after
   the whole time-domain pair has already been run -- the most expensive possible place to discover it. The writer's
   path is created first and the finished file is moved into the figure sink, never assembled in place.

5. **In 2-D the mean over `phi` *is* the total scattering width, and the RCS agreement is quoted honestly.** The
   measured pattern sits at `-2.01 / -0.80 / -2.83 / -0.88 / +0.12 dB` at 0/45/90/135/180 degrees against Mie,
   `1.830 dB` rms, `3.202 dB` worst at 284 degrees, with a broad ~`2 dB` shadow-side underestimate that is left
   visible: the candidates are the near-field solve, the staircase body and the finite windowed beam, and none of
   them is isolated yet, so the gap is not attributed to any one of them.

## Open questions

1. The PML question is answered for normal incidence -- a per-step multiplicative layer in the existing diagonal
   metric, no split fields, `-79.09 dB` -- so what is open now is oblique incidence (unmeasured: the two-run
   difference holds one axis fixed) and the measured stall near `-45 dB` past `~1.5 Np/cell`, which caps the useful
   thickness at about two wavelengths.
2. Where does the residual `~2 dB` shadow-side RCS underestimate come from: the near-field contour (3.60 x 3.60
   wavelengths, possibly too close), the staircase body, or the finite windowed beam? Which of the three can be
   separated first, and by how much does each move the number?
3. How do we get a genuine plane wave? The incident front is plane-wave-like -- `abs(Ez)/peak` across the centre
   line is `0.07, 0.58, 1.00, 0.92, 1.00, 0.07`, because the y-PML that should absorb the drive damps its own
   footprint; a PEC y-wall is worse. A TF/SF injector was designed and deliberately rejected as more machinery
   than the current measurement needs, so the question is when it stops being optional.
4. Is the static-eigenvalue cut robust on strongly graded meshes, where the null cluster may spread and `lam_ref`
   (from `Lmax`) may no longer bound the spectrum? Does it need to become a relative gap test?
5. How to handle non-rectangular PEC boundaries without staircase blow-up -- conformal partially filled cells with a
   modified Hodge star, or subgridding -- and what happens to the exact invariants? The staircase is already
   measurable rather than hypothetical: `+16 %` body area at ka = 1.
6. Which port-mode normalisation makes S-parameters reciprocal *and* power-normalised on a non-uniform grid (modal V/I
   vs power waves), and does the diagonal metric preserve it?
7. Can graded meshing keep second-order convergence, or does metric error at stretched cells drop the cavity spectrum
   to first order? Only uniform grids have been measured (0.507).
8. How to keep the sparse update fast in pure numpy at 10^6 edges, where per-step allocations dominate -- preallocated
   `scipy.sparse` matvec, or numba/C? The eigensolver's `0.09 s -> 64 s` cliff (session 3, finding 6) is a reminder that the
   answer may be "watch the memory tier", not "watch the flop count".
9. Which MQS formulation reuses most of the existing complex (A-V vs T-Omega), and does it need a new Hodge star or
   can `M_sigma` with `C`, `S` carry it?
10. Does gradient deflation preserve 1e-15-class discipline when the null cluster is ~1e13 times smaller than the
    fundamental -- i.e. is the projected Krylov problem stable?

## How to run everything

```bash
cd /workspace
python -m pytest                                        # 483 tests, about 13 min; 469 with -m "not slow"
python -m emfit list                                    # the five studies with their parameters
python -m emfit run cavity --out docs/figures           # mode table, spectrum/field/energy PNGs
python -m emfit run modes --out docs/figures            # one panel per eigenmode
python -m emfit run duct --out docs/figures             # Mur vs PML vs PEC, ~3 s (2.9-3.0 s warm)
python -m emfit run duct --set termination=pml --out /tmp/duct_pml   # the -79.09 dB run
python -m emfit run scatter --out docs/figures          # 2-D PEC cylinder, ~1.4 s
python -m emfit run rcs --out docs/figures              # bistatic RCS vs Mie, ~11.2 s (1.57 s of it time domain)
python -m emfit serve                                   # http://127.0.0.1:8010, one study at a time
python examples/cavity_resonance.py                     # mode table + 3 PNGs
python examples/abc_duct.py                             # Mur vs PEC duct, the 4th PNG
```

The `cavity` study overwrites `docs/figures/cavity_spectrum.png`, `cavity_field_z.png` and `energy_drift.png`; `modes`
writes one panel per eigenmode; the duct demo writes `abc_duct.png`; `scatter` writes `scatter-snapshot.png` and
`scatter-sequence.png`; `rcs` writes `rcs-pattern.png` and `rcs-animation.gif` (24 frames at 8 fps, 274 KiB). Those are
the eight committed figures, and re-running the commands above is how they are regenerated.
`pyproject.toml` already sets `-q`, so `pytest -q` becomes `-qq` and prints no summary line; use bare `pytest` or
`pytest -o addopts=''` when you want the timing.

## Deferred

See `## Deferred ideas / parking lot` in [`docs/roadmap.md`](roadmap.md) for the full list (higher-order FIT, a
dedicated 2-D solver, subgridding, schematic-level workflow, ...); it is deliberately not duplicated here so the two
documents cannot drift. Three items are most likely to bite soon: **gradient null-space deflation** (M5 is blocked
above 3000 free edges), **a genuine plane wave** (every scattering number here rides on a plane-wave-like front, and
the TF/SF injector that would fix it was deliberately left out), and **staircase geometry error** (every curved body
-- sphere, patch, PCB -- currently aliases to whole cells, which can exceed the 0.5 dB / 5 % tolerances of M1 and M4
before any solver work starts). One item has left this list: **tensor materials** is no longer a PML prerequisite,
because the layer was built inside the existing diagonal metric.
