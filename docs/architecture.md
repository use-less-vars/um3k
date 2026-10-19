# Architecture: what exists, and what is only a shape

This document describes the code as it is, not as it was meant to be. Where an
intended layer has no implementation, that is stated together with the function
standing in for it, so a gap cannot be mistaken for a design choice.

The intended chain (`Intro.txt:54`): `Geometry -> VoxelMask + MaterialFields ->
FITSystem -> PortDefinitions -> TimeStepper -> Spectrum`, obeying the rule at
`Intro.txt:169`: "The solver core never depends on the geometry front end; KiCad
import, meshing, and visualization are separate layers that call the solver
through a narrow interface." The rule holds in one direction -- the raster,
solver and port layers take a `Board` as an ordinary dataclass argument and
never import the parser -- but the *narrow interface* it implies does not exist
as an object: it is a set of module-level functions that every caller
assembles by hand.

## Layering

| Stage | Module today | Entry point | State |
|---|---|---|---|
| 1 Geometry | `emfit/kicad.py` | `class Board` (kicad.py:402), returned by the parser (kicad.py:758) | present |
| 2 VoxelMask + MaterialFields | `emfit/raster.py`, `emfit/materials.py`, `emfit/copper.py` | `raster.build(...) -> Coupon` (raster.py:448) | partial: dielectrics yes, copper/PML/source no |
| 3 FITSystem | `emfit/operators.py`, `emfit/materials.py`, `emfit/maxwell.py`, `emfit/pml.py` | `CellComplex.pec_edge_mask` (operators.py:265), `material_matrices` (materials.py:241), `PML` (pml.py:278) | present, assembled per caller |
| 4 PortDefinitions | `emfit/ports.py` | `LumpedPort` (ports.py:180), `column_path` (ports.py:253), `plate_current` (ports.py:395), `fit_beta` (ports.py:759) | present, no placement step |
| 5 TimeStepper | `emfit/evolve.py` | `cfl_dt` (evolve.py:47), `FITStepper` (evolve.py:62), `RickerSource` (evolve.py:223) | present |
| 6 Spectrum | `emfit/ports.py`, `scatter.py`, `nearfield.py`, `viz.py`, `cli.py`, `webapp.py`, `studies.py` | `DftAccumulator` (ports.py:474), `STUDIES` (studies.py:1725) | present |

Stage 1 returns plain data: `Board` carries `version`, `generator`, `thickness`,
`copper_layers`, `layer_names`, `stackup` (a list of `StackupEntry`), `nets`,
`tracks`, `vias`, `footprints`, `zones` and `edge_bbox`; stage 3 is not a class
but three calls a caller must make (`material_matrices`, then
`pec_edge_mask(walls=...)`, then `PML(..., walls=...)`).

Stage 2 is honest about its own boundary. `raster.build` returns a `Coupon`
(raster.py:431) holding `grid`, `cc`, `m_eps`, `m_mu`, `dt` and `info` (a
`CouponInfo`, raster.py:407, with mesh statistics and warnings), and its
docstring says: "There is no copper, no PML, no source and no `run` method:
those belong to the rasterisation milestone and to the caller." Copper is added
afterwards by `copper.copper_pec_mask(cc, board, *, layers=None, ...)`
(copper.py:415); stage 3 is not a class but three calls a caller must make.

## Interfaces that must exist

The hook list below is the "narrow interface" as written in the knowledge base,
checked entry by entry against the current code.

| Hook | Status | What stands in for it today |
|---|---|---|
| `layer_stackup` | absent as a method | the `Board.stackup` field, `raster.layer_z_positions` (raster.py:176), `raster.dielectric_intervals` (raster.py:188), `Board.stackup_thickness()` (kicad.py:452) |
| `epsilon_callable` | absent as a method | module function `raster.epsilon_callable` (raster.py:238), returning the `eps(x, y, z)` closure (raster.py:283) |
| `copper_mask` | absent as a method | `copper.copper_pec_mask` (copper.py:415); areas from `copper.copper_area` (copper.py:292) |
| `extrude(mask, grid)` | absent under that name | `copper.copper_pec_mask`: copper is a PEC edge mask, not an extruded volume of conductivity |
| `boundary_conditions(grid, cc)` | absent | two independent calls: `CellComplex.pec_edge_mask` (operators.py:265) and `pml.PML` (pml.py:278) |
| `ports.place(cc, board, netlist)` | absent | `studies.py` builds the port by hand: `LumpedPort("line", port_column, z0=MS_Z0_NOMINAL)` at studies.py:1415, from `ports.column_path` |
| `deembed(probes, freqs)` | absent | `ports.fit_beta` (ports.py:759) with `BetaFit` (ports.py:682): a fit of propagation, not a reference-plane move |
| `studies.STUDIES` | present (studies.py:1725) | the registry exists but is not Board-driven: each study builds its own grid, e.g. `microstrip_wave` at studies.py:1201 |

Two absences are load-bearing rather than cosmetic. There is no single place
where a wall becomes PEC or PML, so the rule that PEC and PML are one decision
is enforced nowhere: a study can pass inconsistent `walls=` arguments to the two
calls and nothing objects. And there is no `ports.place`, so a port's location
is a literal inside a study rather than a property of the board being simulated.

## What is a fixture and what is the product

- **`CMEX.kicad_pcb` (445,613 bytes) is a parser fixture.** It is the input that
  proves the KiCad reader works on a real board. The knowledge base calls it
  "REFERENCE ONLY ... not a simulation target"; nothing should be simulated on
  it, and no result in `reports/` comes from it.
- **`microstrip_wave` (studies.py:1201) is a physics fixture.** It builds a grid
  by hand from constants, with no board file involved, to show that the solver
  reproduces a line whose answer is known independently (Hammerstad-Jensen). Its
  numbers are evidence about the solver, not about any board.
- **The product is `Board -> raster.build -> ports -> studies`, and it does not
  exist yet.** No study accepts a `Board`, no code places a port from a netlist,
  and `raster.build` yields a dielectric-only coupon that must be completed by
  hand. Everything past stage 2 is exercised only through hand-built grids.

## Known entanglements

1. **Two `DFTAccumulator` classes.** `ports.DftAccumulator` (ports.py:474) is
   constructed as `DftAccumulator(freqs, dt, *, window="rect", n_steps=None)`;
   `nearfield.DFTAccumulator` (nearfield.py:138) is a different class with a
   different protocol, constructed as `DFTAccumulator(cc, freq)` and driven per
   step (nearfield.py:876-877). They differ only in capitalisation, so an import
   mistake is silent and plausible. The knowledge base requires this resolved
   before the M3 wave-port milestone.
2. **Boundary conditions are decided twice** (the `boundary_conditions` row):
   PEC and PML are separate calls with separate `walls=` arguments.
3. **Reporting conflated modulus and impedance:** `MicrostripWave.summary()`
   printed `abs(z0)` under the name `z0`. Fixed in `emfit/studies.py`, recorded
   in `decisions.md`.
