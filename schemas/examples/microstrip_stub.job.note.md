# `microstrip_stub.job.json` — where every number in it comes from

Companion to `schemas/examples/microstrip_stub.job.json`. The example is not invented: it is
the geometry, materials and drive of the demo fixture `demo_microstrip_stub`
(`emfit/demos.py:379-417`) transcribed into `emfit.job.v1`. Every numeric literal below is
either read off a named line or recomputed from named lines, and the recomputation is shown
rather than asserted.

**This job is UNLOADED, and it cannot be anything else.** `demo_microstrip_stub` is defined
by a lumped series resistor — `series_r`, 200 Ω at 12.8 mm from the near wall
(`emfit/demos.py:55`, `:119`) — and `emfit.job.v1` has no load member. The contract at
`decisions.md:7022-7033` names six things a caller may state and a tolerance; a load is not
among them, and the schema (`schemas/emfit.job.v1.schema.json`) is closed, so a `loads`
member would be rejected as an additional property. The example therefore reproduces the
stub fixture's *mesh, substrate and port* but not its defining feature: a job submitted with
it asks for the unloaded line's `S11`. This is a real divergence from the fixture and it is
recorded as such in `docs/design/job_schema.md` rather than hidden by quietly calling the
example a stub.

## Sourcing table

One row per member. "Recomputed here" means the number is derived in the arithmetic section
below from the cited lines, not copied from a comment.

| Member | Value | Source | How it is obtained |
|---|---|---|---|
| `schema` | `"emfit.job.v1"` | `decisions.md:7059` | The document's own name and version; a change to any field name is a bump to `v2`, never a reinterpretation. |
| `geometry.kind` | `"parametric"` | `decisions.md:7036` | The parametric form is required, not optional: every fixture in this repository is parametric and a board-only schema could express none of the tests. |
| `geometry.box_length_mm` | `36.8` | `emfit/studies.py:2556`, `:3262`; counts at `emfit/demos.py:42-44` | Recomputed here: `nx = n_pml + n_ref + n_line = 4 + 2 + 40 = 46`; `cell = h_mm / N_SUB = 1.6 / 2 = 0.8 mm`; `length = nx * cell = 46 × 0.8 = 36.8 mm`. |
| `geometry.strip_width_mm` | `4.8` | `emfit/demos.py:53`, `:80` | Recomputed here: `w = strip_cells * cell = 6 × 0.8 = 4.8 mm` (`DEFAULT_STRIP_CELLS = 6` at `:53`). |
| `geometry.substrate_cells` | `2` | `emfit/demos.py:40`, `:77` | `N_SUB = 2`, and the cell is *defined* as `cell = h / N_SUB`; stating the count rather than the cell size keeps the mesh relation out of the contract. |
| `materials.substrate_eps_r` | `4.4` | `emfit/demos.py:51`; also `decisions.md:7028` | `DEFAULT_EPS_R = 4.4`. Dimensionless; inside the demo's own range `1.0-16.0` (`emfit/demos.py:386`). |
| `materials.substrate_h_mm` | `1.6` | `emfit/demos.py:50`; also `decisions.md:7028` | `DEFAULT_H_MM = 1.6`. Inside the demo's own range `1.3-3.2` (`emfit/demos.py:389`). |
| `sources[0].kind` | `"modal_port"` | `decisions.md:7029` | The only source kind the draft shows and the only one the schema names. |
| `sources[0].name` | `"P1"` | not a sourced number | A name is required (`decisions.md:7030`) because the result's `tolerance_achieved` is keyed by port; the draft's example uses `"J1"` (`:7029`). `P1` is chosen here as the neutral spelling for a parametric port with no board net. |
| `sources[0].x_mm` | `4.8` | `emfit/studies.py:2566`; counts at `emfit/demos.py:42-43` | Recomputed here: `ix_port = n_pml + n_ref = 4 + 2 = 6` cells, and `6 × 0.8 = 4.8 mm` from the near wall. Equal to `strip_width_mm` by coincidence — both are six cells — not by aliasing. |
| `observables[0].kind` | `"sparam"` | `decisions.md:7030` | The only observable kind the draft shows. |
| `observables[0].name` | `"S11"` | `decisions.md:7030` | Verbatim from the draft's observable list. |
| `frequencies_ghz[0]` | `5.0` | `emfit/demos.py:52` | `DEFAULT_F0_GHZ = 5.0`, in gigahertz. Inside the demo's own range `1.0-20.0` (`emfit/demos.py:392`) and far below the schema's 1000.0 GHz unit guard. |
| `tolerance.kind` | `"sparam_abs"` | `decisions.md:7032` | Verbatim from the draft. |
| `tolerance.value` | `0.001` | `decisions.md:7032` | The draft writes `1e-3`; `0.001` is the same double, written in plain decimal because the JSON example carries no exponent. |

## The arithmetic, recomputed rather than copied

The tree never states 36.8, 4.8 or 4.8 directly; it states node counts and derives lengths.
The chain is three lines long:

1. `cell = float(h) / n_sub` — `emfit/studies.py:2555`, i.e. `1.6 mm / 2 = 0.8 mm`.
2. `nx = n_pml + n_ref + n_line` — `emfit/studies.py:2556`, i.e. `4 + 2 + 40 = 46` cells.
3. `"length": nx * cell` — `emfit/studies.py:3262`, i.e. `46 × 0.8 mm = 36.8 mm`.

and the two derived lengths:

4. strip width `w = int(strip_cells) * cell` — `emfit/demos.py:80`, i.e. `6 × 0.8 mm = 4.8 mm`;
5. port plane `ix_port = n_pml + n_ref` — `emfit/studies.py:2566`, i.e. `6 × 0.8 mm = 4.8 mm`.

All five agree with the values in the example. The job states the *results* of this chain
(millimetres, and a cell count) and not the chain itself, because the chain is meshing and
meshing stays on the tool's side of the boundary (`decisions.md:7016-7022`).

## Numbers the job deliberately omits

These all exist in `demo_microstrip_stub` and are all absent from the example on purpose.
They are solver-side: `decisions.md:7016-7022` draws the boundary at "what is to be solved",
so meshing, time stepping, stations and lumped elements are not contract quantities.

| Omitted | Value | Where it lives |
|---|---|---|
| `n_air` | 8 | `emfit/demos.py:45` |
| `n_top` | 4 | `emfit/demos.py:46` |
| `n_clean` | 4 | `emfit/demos.py:41` |
| `n_pml` | 4 | `emfit/demos.py:42` |
| `n_ref` | 2 | `emfit/demos.py:43` |
| `n_line` | 40 | `emfit/demos.py:44` |
| `n_stations` | 9 | `emfit/demos.py:47` |
| `nsteps` | 2400 | `emfit/demos.py:54` |
| load | `series_r`, 200 Ω at 12.8 mm | `emfit/demos.py:55`, `:118-119` |
| `dt` | not stated anywhere as a job quantity | derived from the CFL condition inside the solver |

Two of these deserve a sentence each, because their absence is a *finding* and not
housekeeping. The load is the stub's whole point: a job that cannot name a load cannot
reproduce the fixture it was transcribed from, and `emfit.job.v1` as drafted at
`decisions.md:7022-7033` has no member for one. And `nsteps`/`dt` are absent while the
draft's own example geometry (`decisions.md:7036`) mentions "a stated time step" as part of
what makes the fixtures parametric — so the draft's prose asks for something its own field
list does not carry.
