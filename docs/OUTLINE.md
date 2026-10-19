# emfit -- living project outline

`emfit` is a 3-D Finite Integral Technique (FIT, Weiland) solver for computational electromagnetics: Maxwell's
equations on interlocked cell complexes, with topology (`G`, `C`, `S` in {-1, 0, +1}) kept strictly separate from
metric (the diagonal Hodge stars `M_eps`, `M_mu`), so uniform and graded grids run on identical algebra. Today it is
an explicit leapfrog time-domain integrator with an *exactly* conserved discrete energy plus a PEC-cavity eigenmode
solver validated mode-by-mode against the analytic box spectrum (1.2 % coarse, 0.6 % fine, second order). It cannot
yet open the box (no absorbing boundaries), drive a port or an antenna, import geometry, or run lossy materials, and
its eigenmode path is dense, stopping at 3000 free edges.

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
- Headless plotting layer -- spectrum, field slice, energy history -> PNG, Agg backend, no GUI (`emfit/viz.py`).
- 30 tests in ~52 s, every number locked by an explicit tolerance.
- A ~6 s demo that prints the mode table and writes three figures (`examples/cavity_resonance.py`).

**Does not work yet**

- No absorbing boundaries / open regions: Mur and PML are designed (M1) but absent, so every simulation is a closed
  metal box.
- No ports, no S-parameters, no de-embedding (M3): nothing is driven but a soft edge current.
- No near-to-far-field transform, no antenna impedance or pattern (M2).
- No geometry import: structures are PEC faces of a rectangular grid -- staircase only, no CAD/KiCad path (M4).
- No conductivity or dispersion in the stepper: `M_sigma` is assembled but unconsumed, so no loss, no skin depth, no
  eddy currents (M6).
- Eigenmodes are dense (`scipy.linalg.eigh`) with a hard `max_dense = 3000` free-edge stop -- ~2.4x the largest
  validated grid, far from the 10^5 target (M5).

## Architecture at a glance

```text
   Grid ................................... emfit/grid.py
     |  nodes; cell/dual widths, edge lengths, face areas, volumes
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
     +---------+--------+
               v
             viz ...... emfit/viz.py   plot_spectrum / plot_field_slice / plot_energy
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

## Numbers board

Every value below is asserted by a test; break one and the suite goes red.

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
| Suite | 30 tests, ~51 s | `python -m pytest` |

## Milestone tracker

Reproduced from `README.md` (identical to `## Summary` of [`docs/roadmap.md`](roadmap.md), authoritative for the
detailed plans); the last column is the one next concrete step.

| ID | Milestone | Status | Key deliverable | Acceptance test | Next action |
| -- | --------- | ------ | --------------- | --------------- | ----------- |
| M0 | Time-domain core + cavity eigensolver | DONE | `emfit/{grid,operators,materials,evolve,maxwell,eigen,viz}.py` | 30 passed; mean error 1.213 % / 0.615 %, ratio 0.507 | Nothing to build -- keep the suite green |
| M1 | Absorbing boundaries (Mur, then PML) | IN PROGRESS | viz.py + figures (done); `emfit/abc.py`, `emfit/pml.py`; material layer -> diagonal tensors | PEC-sphere bistatic RCS vs Mie, ka = 1, 3: < 0.5 dB | `emfit/abc.py`: first-order Mur on the six outer walls, pulse leaves with < 1 % reflection |
| M2 | Near-to-far-field transform and antennas | PLANNED | `emfit/nearfield.py` (Huygens box -> far field) | half-wave dipole: 73 ohm, 2.15 dBi | Freeze the Huygens-box API (E, H on a closed surface), validate on the analytic dipole |
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

## Open questions

1. Which ABC/PML fits the diagonal FIT metric best -- Mur on primal edges, a graded-sigma layer in `M_sigma`, or a
   stretched-coordinate metric? The primal/dual split may make a naive PML reflective.
2. Is the static-eigenvalue cut robust on strongly graded meshes, where the null cluster may spread and `lam_ref`
   (from `Lmax`) may no longer bound the spectrum? Does it need to become a relative gap test?
3. How to handle non-rectangular PEC boundaries without staircase blow-up -- conformal partially filled cells with a
   modified Hodge star, or subgridding -- and what happens to the exact invariants?
4. Which port-mode normalisation makes S-parameters reciprocal *and* power-normalised on a non-uniform grid (modal V/I
   vs power waves), and does the diagonal metric preserve it?
5. Can graded meshing keep second-order convergence, or does metric error at stretched cells drop the cavity spectrum
   to first order? Only uniform grids have been measured (0.507).
6. How to keep the sparse update fast in pure numpy at 10^6 edges, where per-step allocations dominate -- preallocated
   `scipy.sparse` matvec, or numba/C?
7. Which MQS formulation reuses most of the existing complex (A-V vs T-Omega), and does it need a new Hodge star or
   can `M_sigma` with `C`, `S` carry it?
8. Does gradient deflation preserve 1e-15-class discipline when the null cluster is ~1e13 times smaller than the
   fundamental -- i.e. is the projected Krylov problem stable?

## How to run everything

```bash
cd /workspace
python -m pytest                      # 30 tests, ~52 s (dense eigh dominates)
python examples/cavity_resonance.py   # mode table + 3 PNGs, ~6 s
```

The demo overwrites `docs/figures/cavity_spectrum.png`, `cavity_field_z.png` and `energy_drift.png`, so re-running it
is how the committed figures are regenerated. `pyproject.toml` already sets `-q`, so `pytest -q` becomes `-qq` and
prints no summary line; use bare `pytest` or `pytest -o addopts=''` when you want the timing.

## Deferred

See `## Deferred ideas / parking lot` in [`docs/roadmap.md`](roadmap.md) for the full list (higher-order FIT, a
dedicated 2-D solver, subgridding, schematic-level workflow, ...); it is deliberately not duplicated here so the two
documents cannot drift. Three items are most likely to bite soon: **gradient null-space deflation** (M5 is blocked
above 3000 free edges), **tensor materials** (a PML needs anisotropic `M_eps`/`M_mu`, so M1 depends on the material
layer going tensorial first), and **staircase geometry error** (every curved body -- sphere, patch, PCB -- currently
aliases to whole cells, which can exceed the 0.5 dB / 5 % tolerances of M1 and M4 before any solver work starts).
