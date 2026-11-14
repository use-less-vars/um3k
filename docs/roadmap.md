# emfit technical roadmap

`emfit` is a 3-D Finite Integral Technique (FIT, Weiland) solver: Maxwell's equations on interlocked cell
complexes, with topology (`G`, `C`, `S` in {-1, 0, +1}) kept strictly separate from metric (Hodge stars `M_eps`,
`M_mu`), so any orthogonal grid -- uniform or graded -- runs on the same algebra. A milestone is **done** only
when it ships a runnable demo *and* a test that locks a physical number (reference value + explicit tolerance),
so a regression turns red instead of becoming an opinion. Milestones are ordered so each one leaves the repo
installable (`pip install -e '.[dev]'`) and green: nothing starts that cannot be finished in one milestone.

## Summary

| ID | Milestone | Status | Key deliverable | Acceptance test |
| -- | --------- | ------ | --------------- | --------------- |
| M0 | Time-domain core + cavity eigensolver | DONE | `emfit/{grid,operators,materials,evolve,maxwell,eigen,viz}.py` | 71 passed; mean error 1.213 % / 0.615 %, ratio 0.507 |
| M1 | Absorbing boundaries (Mur, then PML) | IN PROGRESS | Mur-1 (`emfit/abc.py`) and a matched PML (`emfit/pml.py`), both tested and demoed | absorber validated to -79.09 dB at normal incidence (Mur -49.58 dB); the target was PEC-sphere bistatic RCS vs Mie, ka = 1, 3: < 0.5 dB, and what was achieved is a 2-D PEC cylinder at ka = 3: rms 1.83 dB, max 3.20 dB |
| M2 | Near-to-far-field transform and antennas | IN PROGRESS | `emfit/nearfield.py` delivered and validated, with `emfit/mie.py` as the exact reference | no feed and no port, so the half-wave dipole test (73 ohm, 2.15 dBi) is not reachable in the current 2-D TM code |
| M3 | Waveguide ports and S-parameters | PLANNED | `emfit/ports.py` (2-D modal solve, overlaps, de-embedding) | matched WR-90 line: abs(S21) = 1.000, abs(S11) < -30 dB |
| M4 | PCB import from KiCad | PLANNED | `emfit/kicad.py`, `emfit/raster.py` | microstrip Z0 within 5 % of Hammerstad; patch in band |
| M5 | Large-grid eigensolver, thin features, FEM | IN PROGRESS | `emfit/eigen.py`: ARPACK/LOBPCG on the Helmholtz-projected operator | 100k free edges, 6 modes, < 0.1 % vs dense |
| M6 | MQS eddy currents and parareal | PLANNED | `emfit/mqs.py` (A-V), `emfit/parareal.py` | slab skin depth within 2 % of analytic |

Status provenance: M0 has landed -- 71 tests in about 10-20 s on python 3.12.15 / numpy 2.5.4 / scipy 1.18.1,
and `emfit/` now holds 18 `.py` files spanning M0-M2. M5 is IN PROGRESS because `resonances()` already exposes a
`sigma` shift argument and the `max_dense = 3000` guard is covered by
`tests/test_cavity.py::test_dense_limit_raises_not_implemented` -- neither is a working large-grid path, and the
`sigma = 0` shift-invert route is a dead end (see M5). M1 is IN PROGRESS with most of the work landed: the
first-order Mur boundary and the matched PML are both implemented, tested and demoed, and the absorber is
validated to -79.09 dB at normal incidence; what is outstanding is the acceptance body -- a PEC *sphere* at
`ka = 1` and `ka = 3` -- for which a 2-D TM cylinder at `ka = 3` at 1.83 dB rms is what stands in. M2 is IN
PROGRESS: the near-to-far-field transform and the exact Mie reference are delivered and validated, but the
antenna acceptance test needs a feed and a port, so it is blocked on geometry rather than on numerics. M3, M4
and M6 have no code yet.

## M0 -- Time-domain core and cavity eigensolver

**Goal.** An explicit leapfrog FIT integrator whose discrete energy is conserved *exactly* (to machine precision,
not to `O(dt)`), plus a dense PEC-cavity eigenmode solver used as the validation instrument for the discretisation.

**Deliverables.**
- `emfit/grid.py` -- `Grid`: node coordinates, cell/dual widths, edge lengths, primal/dual face areas, volumes.
- `emfit/operators.py` -- `CellComplex`: metric-free `G`, `C`, `S` + duals, index helpers, PEC tangential-edge masks.
- `emfit/materials.py` -- `M_eps`, `M_mu`, `M_sigma` as `MaterialMatrix` diagonals; scalar/per-entity `Material`.
- `emfit/evolve.py` -- `FITStepper` (leapfrog, PEC constraint, mixed-state energy
  `U = 1/2 e.M_eps e + 1/2 h.M_mu h - (dt/2)(C e).h`), `RickerSource`, `cfl_dt`, `Leapfrog` adapter.
- `emfit/maxwell.py` -- `FITSystem` curl-curl assembly, PEC walls as an unknown-space constraint, `check_dt`.
- `emfit/eigen.py` -- `resonances()`: dense pencil `C^T M_mu^-1 C e = omega^2 M_eps e` on free edges, static-cluster
  filtering, `analytic_box_modes()`; `emfit/viz.py` + `examples/cavity_resonance.py`.

**Acceptance criteria.**
- `test_energy.py::test_energy_exact_conservation` -- relative drift **8.5e-16** over 343 ns (1800 steps).
- `test_energy.py::test_cfl_bound_is_sharp` -- stable at 1.01x the bound, divergent at 1.02x (`6.7e122` growth).
- PEC box `1.0 x 0.7 x 0.5 m`, first six modes: mean error **1.213 %** (10x7x5) and **0.615 %** (14x10x7),
  mean-error **ratio 0.507** (second order for 1.4x refinement); rejected spurious modes exactly 216 and 702.
- Whole suite: **483 tests**, about **13 min** (**469** with `-m "not slow"`); at M0 sign-off it was 71 tests
  in ~10-20 s. The fine-grid cavity is no longer the bottleneck: the growth came from cheap checks -- operators,
  periodic axes, near field, Mie, the web front end -- beside a fast PML and scattering path, and `emfit/` holds
  18 `.py` files.

**Risks / notes.**
- The invariant is fragile: dropping `-(dt/2)(C e).h` gives drift 3.7e-1, using the wrong `h` time level 3.4e-1.
- The PEC restriction does *not* remove the gradient null space; the separator is a static eigenvalue cut.
- `resonances()` is dense; 3000 free edges is a hard ceiling enforced by `NotImplementedError` pointing at M5.

## M1 -- Absorbing boundaries: Mur, then PML

**Goal.** Remove the enclosing PEC box from radiating problems without destroying the exactness of the energy
invariant inside the physical domain.

**Deliverables.**
- `emfit/abc.py` -- **landed.** First-order Mur ABC as a cheap edge-history update on the boundary's tangential
  electric edges: `e_i^{n+1} = e_j^n + (c dt - h)/(c dt + h) * (e_j^{n+1} - e_i^n)`, with `h` the normal cell width
  at the boundary face and `e_i`, `e_j` the tangential edges either side of the boundary. No new unknowns, no
  change to `C`.
- `emfit/pml.py` -- **landed.** A matched lossy layer: an electric conductivity profile through the layer with a
  magnetic loss normalised so that `sigma_m/mu0 = sigma_e/eps0`, which keeps the layer impedance-matched to
  vacuum at every depth and therefore leaves no reflection at the interface. There are **no split fields**: the
  layer is a per-step multiplicative damping applied to the tangential fields inside it, so it adds no unknowns,
  changes no operator, and the material layer never had to become tensorial. No stretched coordinate
  `s_x = 1 + sigma_x/(j omega eps0)` and no complex anisotropic `eps`/`mu` is involved.
- `emfit/scatter.py` -- **landed.** The 2-D TM scattering layer: a uniform line source illuminates a PEC cylinder
  on a single cell layer, and the total run is differenced against the same run without the body so the scattered
  field is available directly.
- `emfit/studies.py` -- **landed.** The `duct`, `scatter` and `rcs` studies behind `python -m emfit run <study>`,
  with `--set termination=pml|mur|pec` selecting the duct termination and `--out` writing the figures.
- `tests/test_pml.py`, `tests/test_scatter.py` -- **landed.**
- `examples/abc_duct.py` -- **landed** (~1.5 s): TE10 pulse in a WR-90 duct, 900 steps, 21.55 ns, `v_ph = 1.0069 c`,
  writes `docs/figures/abc_duct.png`.
- Shared with M2, and listed in full there: `emfit/nearfield.py`, `emfit/mie.py`, `tests/test_nearfield.py`,
  `tests/test_mie.py`. The Mie validation of M1's acceptance test is exactly what these supply.

**Acceptance criteria.**
- Normal-incidence reflection: Mur < -20 dB (measured `-49.6 dB`, i.e. at the dispersion floor), PML < -40 dB
  (`test_abc.py`).
- PEC sphere `a = 0.1 m`, bistatic RCS at `ka = 1` (477 MHz) and `ka = 3`: max deviation from Mie < 0.5 dB over
  `theta` in [0, 180] deg -- blocked on M2 (no near-to-far-field transform yet); pin the first measured tolerance
  when it lands, then freeze it in the test.
- Closed lossless PEC cavity still conserves energy to `1e-15` (the ABC must not leak when it is not applied).

*The criteria above are the plan as originally written and are left unchanged. Where they stand today: the
normal-incidence reflection criterion is met with room to spare; the PEC-sphere criterion is **not** met, and the
"no near-to-far-field transform yet" parenthetical is out of date, because the transform has since landed -- see
"What was achieved, and where it falls short" below.*

**What was achieved, and where it falls short.**
- Normal incidence, measured as the two-run difference between the Mur and PML terminations: PML **-79.09 dB**
  against Mur **-49.58 dB**. The `< -40 dB` target is met with about 39 dB to spare.
- The pytest duct case is a *different geometry* from the normal-incidence one: Mur **-26.50 dB**, PML
  **-65.47 dB**, a margin of **38.97 dB**.
- The `duct` study with `--set termination=pml` prints `-78.31 dB` near and `-79.09 dB` far, an echo/incident
  ratio of `1e-4`, and a phase velocity of `1.00693 c`, in about 3 s warm.
- The layer thickness follows a wavelength law rather than a fixed cell count: about 1 wavelength gives
  **-52 dB**, about 2 wavelengths **-79 dB**; 20 and 40 cells per wavelength at the same *physical* thickness
  agree to **0.6 dB**. Beyond roughly **1.5 Np per cell** the reflection stalls near **-45 dB**, so adding cells
  eventually buys nothing and the grading, not the resolution, is the limit.
- **Shortfall.** The acceptance test asked for a PEC *sphere* at `ka = 1` and `ka = 3` to better than 0.5 dB.
  What exists is a PEC **cylinder in 2-D TM** at `ka = 3` only, at **1.83 dB rms** against Mie. So the absorber
  is validated to -79 dB while the radiating validation body is neither the requested shape nor the requested
  ka, and the Mie target is missed by roughly 1.3 dB rms.

**Risks / notes.**
- Staircasing dominates at `ka = 3`; a tolerance is meaningless unless quoted with the grid (`h/a`). The 1.83 dB
  rms figure is quoted with 20 cells per wavelength and a 2.023 % area excess (293 pinned PEC edges against 286.5).
- The matched layer is a scalar loss profile, so it is matched at normal incidence and is *not* guaranteed at
  oblique incidence; there is no oblique-incidence test in the suite. That, not the material tensors, is the real
  open question about the absorber.
- PML adds loss, so the tests keep two energies: total (monotone decay) and physical-domain-only (flat). The
  discrete energy invariant of M0 is asserted on the closed lossless cavity, where the layer is not applied.
- Mur-1 is first order: exact for normal incidence in 1-D, degrading at oblique incidence and at low frequency where
  the local-plane-wave assumption fails. The duct's `-49.6 dB` is the discrete waveguide's dispersion floor, not a
  boundary-error figure, and it does not generalise; the PML is the broadband answer, not Mur.

## M2 -- Near-to-far-field transform and antennas

**Goal.** Turn a closed-surface field record into pattern, gain and input impedance, and validate on a textbook
structure.

**Deliverables.**
- `emfit/nearfield.py` -- **landed, 2-D TMz only.** A `Contour`: a node-index rectangle in the plane, plus the
  transform that turns the recorded tangential fields into far-field values.
  **Correction:** this entry previously claimed a `HuygensBox` -- "closed axis-aligned surface given by index
  ranges, with outward normals per face" -- lived here. No such class exists, and `nearfield.py` has never held
  3-D geometry. The 3-D closed surface is new work, started in `emfit/huygens.py`.
- `emfit/mie.py` -- **landed.** The exact 2-D TM Mie series for a PEC circular cylinder: series coefficients,
  bistatic scattering width and total scattering width, used as the reference the transform is judged against.
- Field accumulation: one transient run, DFT the tangential `E` and `H` on the box contour -> complex `(E_t, H_t)`
  per angle (broadband, no frequency sweep), run to steady state or long enough to resolve the band.
- Equivalent currents `J = n x H` and `M = -n x E`, integrated with the free-space Green function
  `exp(-jkR)/(4 pi R)` on a contour around the body.
- `tests/test_nearfield.py`, `tests/test_mie.py` -- **landed.**
- Shared with M1, and listed in full there: `emfit/pml.py`, `emfit/scatter.py`, `tests/test_pml.py`,
  `tests/test_scatter.py`, and the `scatter` and `rcs` studies -- the transform is exercised through them.
- **Not delivered:** `examples/dipole.py` and `tests/test_antenna.py`. There is no feed and no port in the code,
  so there is nothing to drive and no `Z_in` to measure (see below).

**Acceptance criteria.**
- Half-wave dipole: `Re Z_in = 73 +/- 5 ohm`, `|Im Z_in| < 20 ohm`, directivity `2.15 +/- 0.15 dBi`, E-plane main
  lobe within 0.3 dB of `cos(pi/2 cos theta)/sin theta` (`tests/test_antenna.py`).
- Two Huygens boxes (3 and 5 cells from the dipole) agree to 0.2 dB -- catches a wrong normal or a missing face.
- One transient run yields every frequency in the band.

**What was achieved, and where it falls short.**
- The transform itself is validated on an analytic Green function: `|a|` flat to **0.4 %** across angles, the
  phase slopes recovering `k*x0` and `k*y0` to **1.6e-3** with the correct signs, and the flatness gate passing at
  **12 cells per wavelength**. A wrong normal, a missing face or a transposed sign shows up here immediately.
- Scattering at `ka = 3` and 20 cells per wavelength: **293** pinned PEC edges against **286.5** analytic (area
  ratio **1.023**), **481** steps, **1.59 s** for the pair of runs, peak `|Ez|` **253.620 V/m** total and
  **193.873 V/m** scattered (ratio **0.9233**).
- Bistatic RCS of that cylinder against exact Mie: rms **1.830 dB**, worst **3.202 dB** at 284 degrees, total
  scattering width **1.6610 m** against Mie **2.3598 m**; the pattern is not mirrored, so the transform's sign
  convention is right.
- **Shortfall.** The acceptance test -- half-wave dipole, `Re Z_in = 73 ohm`, directivity 2.15 dBi -- is
  unreachable in the current 2-D TM layer: there is no feed, no port and no terminal impedance, and a dipole is a
  three-dimensional object. It is blocked on geometry, not on numerics. The pattern/directivity/gain and
  `Z_in` deliverables above are therefore also not delivered; only `pattern`-style far-field values on a contour
  exist.

**Risks / notes.**
- The wire radius must be *resolved*, not lumped (graded `Grid.nonuniform`), or the feed impedance is set by the
  grid. Moot until a feed exists, and it is the reason the dipole check cannot be faked.
- The box must sit outside the reactive near field (`> 0.5 lambda`), otherwise the far-field integral does not
  converge. The 2-D contour used here satisfies that at `ka = 3`, but it fixes the geometry: the same contour at
  `ka = 1` was not run.
- Gain errors hide in the normalisation: divide by radiated power, not input power. Untested, because there is no
  input power without a port.
- The 1.83 dB rms is a *reconstruction* error budget, not a convergence study: the residual is consistent with
  staircase error on the cylinder, and it does not shrink by refining alone.

## M3 -- Waveguide ports and S-parameters

**Goal.** Drive and read a device through modal ports so a multi-port structure yields a proper S-matrix from one
broadband run.

**Deliverables.**
- `emfit/ports.py` -- 2-D eigenproblem on the port cross-section, `C_t^T M_mu^-1 C_t e_t = k_c^2 M_eps e_t` (the M0
  pencil on a reduced complex), returning modal profiles `e_t`, `h_t`, cutoff `k_c`, `beta(f) = sqrt(k0^2 - k_c^2)`.
- Modal excitation: soft longitudinal current proportional to the mode profile, injected on the port face.
- Modal decomposition by overlap integrals `a_m = <e_t, E_t>/<e_t, e_t>` (power-normalised) at each port; then
  `S_ij = b_i/a_j`.
- De-embedding by reference-plane shift `exp(+j beta_m d)` per mode, so results do not depend on source placement.
- `examples/waveguide_line.py` -- WR-90 (`22.86 x 10.16 mm`, TE10 cutoff 6.557 GHz): straight line and a step.

**Acceptance criteria.**
- Matched line, 8-12 GHz: `abs(S11) < -30 dB`, `abs(S21) = 1.000 +/- 0.001`, `arg(S21)` within 1 deg of `-beta d`
  (`tests/test_ports.py`).
- De-embedding invariance: moving the source 5 cells changes `abs(S21)` by < 0.1 % and the phase by exactly `beta d`.
- 2-D cutoff within 0.2 % of `c/(2a)` (TE10) and `c/(2b)` (TE01) on a converged cross-section.

**Risks / notes.**
- Below cutoff `beta` is imaginary: store evanescent modes, never power-normalise them, never feed them into `S`.
- The port plane must be single-moded, or the de-embedding matrix becomes mode-coupled.
- Broadband from one run needs `dt` to resolve `fmax` (~20 cells per `lambda_min`), which already sets the staircase error.

## M4 -- PCB import from KiCad

**Goal.** Go from `.kicad_pcb` to a solved structure without hand-modelling -- the first end-to-end user story.

**Deliverables.**
- `emfit/kicad.py` -- minimal s-expression reader (`(kicad_pcb ...)` -> nested Python lists; KiCad 6/7/8 share the
  shape) extracting layer stack-up, track segments (start/end/width/layer), zones/polygons, pads, vias.
- `emfit/raster.py` -- rasterise copper onto the structured grid (segment-to-cell coverage: distance from face centre
  to segment < width/2; polygon fill), emit a copper mask per layer, map it to PEC edges. Staircase accepted.
- Stack-up -> material map: per-layer `eps_r`, `tan delta` (no dispersion), copper as PEC sheet (optional one-cell
  thickness).
- Ports: gap/lumped port between cell-adjacent copper regions on the feed layer; reuse M3's modal port for microstrip.
- `examples/microstrip.py`, `examples/patch.py`.

**Acceptance criteria.**
- Microstrip `Z0` (from `S11`/`S21` of a terminated line) within 5 % of Hammerstad-Jensen for the same `w/h`, `eps_r`
  (`tests/test_kicad.py`).
- Patch resonance within 3 % of `c/(2 L sqrt(eps_eff))`, and it must move *down* under refinement (staircase bias).
- Parser round-trip: board with tracks, a zone and a pad reads without exception; rasterised copper area within 5 %.

**Risks / notes.**
- Staircase error is one-sided and dominant: a 0.2 mm track on a 1 mm grid needs local refinement to `w/3`; document it.
- Zones have holes and thermal spokes; filling them as solid copper detunes a patch.
- FR4 is dispersive and lossy (Dk 4.2-4.5, tand ~0.02); the acceptance values are for a lossless substrate and the
  test must say so.

## M5 -- Large-grid eigensolver, thin features, FEM

**Goal.** Lift the dense ceiling so a realistic cavity (10^5-10^6 free edges) yields its first modes without letting
gradient null vectors into the answer.

**Deliverables.**
- `emfit/eigen.py` -- discrete Helmholtz projector. The PEC-restricted curl has a gradient null space of dimension
  exactly `(nx-1)(ny-1)(nz-1)` (216 on 10x7x5, 702 on 14x10x7, measured). Build sparse `G_free`,
  `P = I - G (G^T M_eps G)^-1 G^T M_eps` on the free edges, and solve the projected problem
  `P^T M_eps^-1 C^T M_mu^-1 C P e = omega^2 M_eps e`, which annihilates the null space by construction.
- ARPACK (`scipy.sparse.linalg.eigsh`, `which='LM'`) on the projected operator; LOBPCG with the `M_eps` inner product
  when the Krylov basis is the memory bottleneck.
- Thin features: local refinement helper on graded grids (geometric ratio <= 1.3) plus a warning when `cfl_dt` derived
  from the *minimum* width has collapsed the step count.
- Optional `emfit/fem.py`: nodal first-order tetrahedral FEM for the same pencil, only if curved geometry makes the FIT
  route the bottleneck.
- `tests/test_eigen_large.py`.

**Acceptance criteria.**
- `test_projector_annihilates_gradients`: `P` applied to a random gradient returns `< 1e-12 * ||field||`, and
  `rank(P)` = free edges minus `(nx-1)(ny-1)(nz-1)`.
- `test_arpack_matches_dense`: just under the dense limit, < 0.1 % frequency deviation and identical mode ordering.
- `test_large_grid_mode_count`: `>= 100k` free edges, first 6 modes, < 5 min on one core, static rejections still
  exactly `(nx-1)(ny-1)(nz-1)`.

**Risks / notes.**
- **`sigma = 0` shift-invert was tried and is wrong here**: the shift sits on the singular pencil, so the gradient null
  vectors (eigenvalue 0) dominate the factorisation and contaminate the answer. Project first, then iterate; do not
  patch it with a tiny nonzero sigma.
- The projected operator is non-symmetric (`M`-symmetric at best): never assume real eigenvalues without checking
  residuals.
- Graded grids destroy the CFL budget globally (one 0.1 mm cell in a 1 m domain multiplies the step count by ~1e4).

## M6 -- MQS eddy currents and parareal

**Goal.** Cover the low-frequency regime where the displacement current is irrelevant (induction heating, eddy-current
testing, laminations) and make long transients affordable.

**Deliverables.**
- `emfit/mqs.py` -- magnetoquasistatic A-V formulation: edge-based vector potential `A` (so `B = C A` stays an exact
  incidence product) plus a nodal scalar `v` for the gauge/charge part. Drop `dD/dt`:
  `C^T M_mu^-1 C A + M_sigma dA/dt = -J_s`, first order in time, so the leapfrog is replaced by a theta /
  backward-Euler step rather than reused.
- Gauge handling: `A -> A + G phi` leaves a gradient null space again -- reuse the M5 projector, not a penalty term.
- `emfit/parareal.py` -- parareal over the semi-explicit system: coarse implicit propagator `G` (big steps) plus fine
  explicit propagator `F` (small steps), correction `U_{n+1}^{k+1} = G(U_n^{k+1}) + F(U_n^k) - G(U_n^k)`.
- `examples/eddy_slab.py` -- conducting slab/tube driven by a coil or a prescribed tangential `H`, transient and harmonic.
- `tests/test_mqs.py`.

**Acceptance criteria.**
- `test_skin_depth`: aluminium slab (`sigma = 3.5e7 S/m`) decays over `2.7 mm` at 1 kHz and `11.0 mm` at 60 Hz, each
  within 2 % of `sqrt(2/(omega mu sigma))`.
- Parareal converges in `<= log2(N) + 2` iterations to `1e-6` of the sequential fine solution; a 1-iteration result is
  rejected by the test.
- Below the quasi-static limit the MQS solution matches `FITStepper` to < 1 %.

**Risks / notes.**
- Dropping `dD/dt` makes the system first order: M0's exact-energy invariant no longer exists, so M6 needs its own
  invariant (magnetic energy + `I^2 R`) and its own conservation test. Never quote M0's drift figure for MQS.
- Conduction-dominated cells set the step by the fastest diffusion time, not by the CFL wave bound; switch limits
  explicitly.
- Parareal speedup is bounded by the coarse propagator cost and by the iterations actually taken: report measured,
  never theoretical.

## Known limitations (today)

- No ports, no S-parameters and no feed: a device cannot be driven through a mode, and no terminal impedance
  exists. Absorbing boundaries are no longer the gap -- there is a matched PML (`emfit/pml.py`) and a first-order
  Mur boundary (`emfit/abc.py`), both tested and demoed -- but they are validated at **normal incidence** and on
  a single 2-D TM cell layer, not at oblique incidence in 3-D.
- Energy conservation and CFL are validated for PEC cavities on orthogonal grids only; the lossy path (`M_sigma`) is
  assembled but never exercised by a test that regresses loss.
- Materials are scalar per entity: real `eps_r`, `mu_r`, `sigma`. No anisotropy, no complex permittivity, no
  dispersion (Debye/Lorentz/Drude). This is a limitation on *modelled media*, not on the absorber: the delivered
  PML is a real matched lossy layer, so it never needed anisotropic or complex material support.
- The eigensolver is dense and capped at 3000 free edges; it fails loudly with `NotImplementedError`, not slowly.
- Geometry is a structured orthogonal grid with staircase boundaries: no curved/conformal meshing, no subgridding, and
  thin features cost the global time step.
- The 3-D FIT formulation is the main path; the 2-D TM layer used for scattering is a single-cell-layer special
  case (one cell in `z`, `Ez`/`Hx`/`Hy` only), not a general 2-D mode, and there is no axisymmetric mode. Ports
  still need a genuine 2-D cross-section solve.
- Single process, NumPy/SciPy only: no MPI, no GPU, no parallelism beyond BLAS inside `eigh`/matvec.
- Packaging is minimal: `pyproject.toml` + `pip install -e '.[dev]'` works, but nothing is released, tagged or CI-tested.
- The LaTeX report and the written outline exist and are living documents, not one-off artefacts: `docs/report/`
  holds `main.tex` plus one file per section and a checked-in `main.pdf` (~963 KiB), and `docs/OUTLINE.md` is the
  project outline. Both are expected to move in the same commit as the code that changes a number; the numbers in
  this roadmap are the measured ones from the test suite.

## Deferred ideas / parking lot

- Dispersive materials: Debye / Lorentz / Drude via auxiliary differential equations.
- Full anisotropic and gyrotropic tensors (ferrites, magnetised plasma). This is *not* a PML prerequisite any
  more: the matched lossy layer is scalar and impedance-matched through `sigma_m/mu0 = sigma_e/eps0`, so the
  absorber was delivered without the material layer ever going tensorial. Tensors are wanted for the media, not
  for the boundary.
- Conformal / curved meshing and non-orthogonal complexes (the general FIT case).
- Thermal and multiphysics coupling (loss -> temperature -> conductivity).
- GPU/BLAS offload of the sparse matvec; distributed-memory domain decomposition.
- Schematic-level workflow (netlist in, S-parameters out) above the PCB importer.
- A CLI (`emfit solve case.toml`) and a case-file format.
- CI on every commit, and PyPI publication with versioned releases.
- Interactive viewer / ParaView export for 3-D fields.

## Working agreement

- Every milestone lands with tests that lock a physical number; a feature without a regressing test is not done, and a
  tolerance is always quoted together with the grid it was measured on.
- The living LaTeX report under `docs/report/` is updated in the same commit as the code that changes a number -- the
  report is the deliverable, not a souvenir.
- Numbers in the README and in this roadmap are the *measured* ones from the test suite, never aspirational; when a
  measurement contradicts the plan, the plan changes.
- Anything not being built now goes into the parking lot above, not into a commented-out block or a `TODO` in the source.
