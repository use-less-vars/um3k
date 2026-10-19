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
| M0 | Time-domain core + cavity eigensolver | DONE | `emfit/{grid,operators,materials,evolve,maxwell,eigen,viz}.py` | 34 passed; mean error 1.213 % / 0.615 %, ratio 0.507 |
| M1 | Absorbing boundaries (Mur, then PML) | IN PROGRESS | Mur-1 done (`emfit/abc.py`, `tests/test_abc.py`, `examples/abc_duct.py`); remaining: `emfit/pml.py` | PEC-sphere bistatic RCS vs Mie, ka = 1, 3: < 0.5 dB (needs M2 near-to-far field) |
| M2 | Near-to-far-field transform and antennas | PLANNED | `emfit/nearfield.py` (Huygens box -> far field) | half-wave dipole: 73 ohm, 2.15 dBi |
| M3 | Waveguide ports and S-parameters | PLANNED | `emfit/ports.py` (2-D modal solve, overlaps, de-embedding) | matched WR-90 line: abs(S21) = 1.000, abs(S11) < -30 dB |
| M4 | PCB import from KiCad | PLANNED | `emfit/kicad.py`, `emfit/raster.py` | microstrip Z0 within 5 % of Hammerstad; patch in band |
| M5 | Large-grid eigensolver, thin features, FEM | IN PROGRESS | `emfit/eigen.py`: ARPACK/LOBPCG on the Helmholtz-projected operator | 100k free edges, 6 modes, < 0.1 % vs dense |
| M6 | MQS eddy currents and parareal | PLANNED | `emfit/mqs.py` (A-V), `emfit/parareal.py` | slab skin depth within 2 % of analytic |

Status provenance: M0 has landed (34 tests, ~30-55 s, numpy 2.5.4 / scipy 1.18.1). M5 is IN PROGRESS
because `resonances()` already exposes a `sigma` shift argument and the `max_dense = 3000` guard is covered by
`tests/test_cavity.py::test_dense_limit_raises_not_implemented` -- neither is a working large-grid path, and the
`sigma = 0` shift-invert route is a dead end (see M5). M1 is partially landed: `emfit/viz.py`, the figures it
produces, and the first-order Mur boundary (`emfit/abc.py`, `tests/test_abc.py`, `examples/abc_duct.py`) are in
place, while `emfit/pml.py` and the PEC-sphere RCS validation are outstanding. M2-M4 and M6 have no code yet.

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
- Whole suite: 34 tests, ~30-55 s (`test_abc.py` adds 4 tests in ~1 s; the fine-grid cavity sets the wall clock).

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
- **Next task: widen the material layer from scalars to diagonal tensors** (`Material` holding `eps_xx, eps_yy,
  eps_zz`, same for `mu`). A stretched-coordinate PML is a complex anisotropic medium and cannot be a scalar.
- `emfit/pml.py` -- PML as an anisotropic lossy layer of `n` cells with stretched coordinates
  `s_x = 1 + sigma_x/(j omega eps0)`, polynomial grading `sigma = sigma_max (d/L)^3`, giving complex `eps`/`mu` inside
  the layer only -- expressed through the diagonal tensor above, not as a special-case absorber.
- `examples/sphere_rcs.py` -- PEC sphere under plane-wave illumination, bistatic RCS with the Mie series overlaid.
- `tests/test_abc.py` -- **landed** (4 tests, ~1 s): reflection of a normally incident plane wave in a 320x16x1
  duct, Mur measured at `-49.57` / `-49.58 dB` against the `-49.24 dB` dispersion floor (asserted < -40 dB), PEC
  control `+0.21` / `+0.22 dB`, incident amplitude ratio `1.000000`; PML < -40 dB at 8-10 cells stays the target.
- `examples/abc_duct.py` -- **landed** (~1.5 s): TE10 pulse in a WR-90 duct, 900 steps, 21.55 ns, `v_ph = 1.0069 c`,
  writes `docs/figures/abc_duct.png`.

**Acceptance criteria.**
- Normal-incidence reflection: Mur < -20 dB (measured `-49.6 dB`, i.e. at the dispersion floor), PML < -40 dB
  (`test_abc.py`).
- PEC sphere `a = 0.1 m`, bistatic RCS at `ka = 1` (477 MHz) and `ka = 3`: max deviation from Mie < 0.5 dB over
  `theta` in [0, 180] deg -- blocked on M2 (no near-to-far-field transform yet); pin the first measured tolerance
  when it lands, then freeze it in the test.
- Closed lossless PEC cavity still conserves energy to `1e-15` (the ABC must not leak when it is not applied).

**Risks / notes.**
- Staircasing dominates at `ka = 3`; a tolerance is meaningless unless quoted with the grid (`h/a`).
- A complex *scalar* `eps` is not enough: the PML needs `s_y`, `s_z` active per face orientation.
- PML adds loss, so keep two energies in tests: total (monotone decay) and physical-domain-only (flat).
- Mur-1 is first order: exact for normal incidence in 1-D, degrading at oblique incidence and at low frequency where
  the local-plane-wave assumption fails. The duct's `-49.6 dB` is the discrete waveguide's dispersion floor, not a
  boundary-error figure, and it does not generalise; the PML is the broadband answer, not Mur.

## M2 -- Near-to-far-field transform and antennas

**Goal.** Turn a closed-surface field record into pattern, gain and input impedance, and validate on a textbook
structure.

**Deliverables.**
- `emfit/nearfield.py` -- `HuygensBox`: closed axis-aligned surface given by index ranges, outward normals per face.
- Field accumulation: one transient Ricker run, DFT the tangential `E` and `H` on the box -> complex `(E_t, H_t)` per
  face cell per frequency (broadband, no frequency sweep), run to steady state or long enough to resolve the band.
- Equivalent currents `J = n x H` and `M = -n x E`, integrated with the free-space Green function
  `exp(-jkR)/(4 pi R)` (chunked matvec above ~1e5 face cells).
- Post-processing: `pattern(theta, phi)`, directivity/gain normalised by the Poynting flux through the box, and
  `Z_in = V(f)/I(f)` from the feed probe in the same DFT.
- `examples/dipole.py` -- half-wave dipole at 300 MHz (`lambda = 1 m`), delta-gap feed, E- and H-plane cuts.

**Acceptance criteria.**
- Half-wave dipole: `Re Z_in = 73 +/- 5 ohm`, `|Im Z_in| < 20 ohm`, directivity `2.15 +/- 0.15 dBi`, E-plane main
  lobe within 0.3 dB of `cos(pi/2 cos theta)/sin theta` (`tests/test_antenna.py`).
- Two Huygens boxes (3 and 5 cells from the dipole) agree to 0.2 dB -- catches a wrong normal or a missing face.
- One transient run yields every frequency in the band.

**Risks / notes.**
- The wire radius must be *resolved*, not lumped (graded `Grid.nonuniform`), or the feed impedance is set by the grid.
- The box must sit outside the reactive near field (`> 0.5 lambda`), otherwise the far-field integral does not converge.
- Gain errors hide in the normalisation: divide by radiated power, not input power.

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

- No broadband absorber, no ports, no far-field transform: the only truncation is the first-order Mur boundary
  (`emfit/abc.py`), accurate at normal incidence only, so radiating problems are modelled crudely at best.
- Energy conservation and CFL are validated for PEC cavities on orthogonal grids only; the lossy path (`M_sigma`) is
  assembled but never exercised by a test that regresses loss.
- Materials are scalar per entity: real `eps_r`, `mu_r`, `sigma`. No anisotropy, no complex permittivity, no
  dispersion (Debye/Lorentz/Drude).
- The eigensolver is dense and capped at 3000 free edges; it fails loudly with `NotImplementedError`, not slowly.
- Geometry is a structured orthogonal grid with staircase boundaries: no curved/conformal meshing, no subgridding, and
  thin features cost the global time step.
- Only the 3-D FIT formulation exists (the 2-D pencil is still planned for ports); no 2-D TM mode, no axisymmetric mode.
- Single process, NumPy/SciPy only: no MPI, no GPU, no parallelism beyond BLAS inside `eigh`/matvec.
- Packaging is minimal: `pyproject.toml` + `pip install -e '.[dev]'` works, but nothing is released, tagged or CI-tested.
- The LaTeX report and the written outline exist and are living documents, not one-off artefacts: `docs/report/`
  holds `main.tex` plus one file per section and a checked-in `main.pdf` (~350 KiB), and `docs/OUTLINE.md` is the
  project outline. Both are expected to move in the same commit as the code that changes a number; the numbers in
  this roadmap are the measured ones from the test suite.

## Deferred ideas / parking lot

- Dispersive materials: Debye / Lorentz / Drude via auxiliary differential equations.
- Full anisotropic and gyrotropic tensors (ferrites, magnetised plasma).
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
