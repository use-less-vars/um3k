# 02 — Physics, as it actually exists in code, and what is next

This document answers two questions a new engineer asks in the first week:

1. Where *is* the physics? Not in the book draft — in the Python.
2. What is genuinely the next piece of work, as opposed to what a roadmap
   document from an older generation says?

One warning before the map. `docs/design/roadmap-next-2026-11-08.md` is partly
stale: section 2 (around `:136`) and section 6 (around `:456`) read as though work
that has since started has not started. Treat "not started" from that document as
a claim about 2026-11-08 and nothing later. The authoritative position on the
current front of work is `docs/design/graded_meshing_plan.md`.

---

## 1. The physics map

| Concept | Where it lives | Note |
|---|---|---|
| Mesh | `emfit/grid.py` | Frozen dataclass of **node coordinate arrays** `x, y, z`; `_axis()` at `:21-29` validates 1-D, ≥2 nodes, strictly increasing; `.widths(axis)` is `np.diff` at `:134-136`. `grid.py:7` calls non-uniform spacing "first class". |
| Board → mesh | `emfit/raster.py` | `build_grid(board, region, dx, *, cells_per_dielectric=2, air_above=1.0e-3, air_below=0.5e-3, air_cells=3, periodic=(False,False,False), warnings=None) -> Grid` at `:330`. Lateral arithmetic is `_lateral_axis` at `:316-327`; only callers are `:397` and `:398`. |
| Time step | `emfit/evolve.py:74-86` | `cfl_dt`. See §2 — this is the most under-documented piece of physics in the repo. |
| Leapfrog update | `emfit/evolve.py` | `FITStepper`; default `self.dt = float(cfl_dt(cc.grid) if dt is None else dt)` at `:495`. |
| Operators | `emfit/operators.py` | Discrete curl/divergence and the material matrices. |
| Boundaries | `emfit/pml.py`, `emfit/abc.py` | PML is the main absorbing boundary; `abc.py` carries the Mur1 absorbing boundary used by the duct tests. |
| Ports and S | `emfit/ports.py` (83,854 B), `emfit/modalport.py`, `emfit/modal.py` | Port extraction and modal decomposition. |
| Mode solving | `emfit/mode_profile.py` (33,189 B) | `_section` builds a **uniform** cross-section — the reason grading is fenced in §3. |
| Scattering | `emfit/scatter.py` | Imports `cfl_dt` at `:87`, sets `dt = cfl_dt(grid)` at `:310`. |
| Huygens / NTFF | `emfit/huygens.py`, `emfit/huygens_fields.py`, `emfit/ntff.py` | Near-to-far transformation. |
| Circuits | `emfit/spice.py` (66,405 B), `emfit/coupling.py` | See §5. |
| Studies | `emfit/studies.py` (335,308 B) | The layer above all of it: `[BRIEFING]` references `cfl_dt` at `:508`, `:2541`, `:2862-2866`, `:3243`, `:4631`. |

---

## 2. CFL is not a book chapter. It is code, in five places, and the bound is already min-based.

The question has been asked whether the CFL condition in this project is only a
*planned chapter* in the write-up. It is not. `docs/design/latex_structure.md`
does contain a `sec_energy.tex` row describing a planned chapter that would cover
"the leapfrog update as implemented, the quadratic form actually preserved (not
the obvious one), measured drift, **the CFL bound**, and numerical dispersion" —
that row is an inventory of intended chapters, and it is not evidence about code.
The code treatment is separate and real, and it is this:

### 2.1 `emfit/evolve.py:74` — the library's definition

```python
def cfl_dt(grid, *, c: float = C0, safety: float = 0.99) -> float:
```

Docstring: *Courant-limited time step — safety / (c · sqrt(Σ_axis 1/d_axis²))*.
And then the sentence that makes grading tractable (`:77-79`):

> the leapfrog stability bound is set by the shortest edge in the mesh, so a graded
> grid must use the **minimum** width rather than the maximum.

`cfl_dt` is exported in `__all__` at `:57`.

### 2.2 Where it is used

- `emfit/evolve.py:495` — `FITStepper`'s default step when none is supplied.
- `emfit/evolve.py:750-756` — `RickerSource` and `PointSource` compute
  `dt_max = cfl_dt(cc.grid)` and **refuse** a supplied `dt` above it. The comment
  at `:714-715` states the policy: *"A time step above the CFL limit is refused
  here rather than left to diverge."* This is the single most important
  behavioural choice in the time-stepping layer: the wrong `dt` produces a
  plausible-looking unstable run, and the code chooses to refuse instead.
- `emfit/maxwell.py:79-99` — a second, independent implementation on the
  `Maxwell` object: `cfl_dt(self, safety=1.0)` gives
  `dt ≤ 1 / (c·sqrt(1/dx² + 1/dy² + 1/dz²))` using the **finest** width per axis,
  described as "a bounding-box bound for non-uniform grids"; `:68` sets
  `self.dt = safety * self.cfl_dt()` with default `safety = 0.95`; `:88-99`
  `check_dt` raises `ValueError` — *"dt = ... exceeds the CFL limit ... for this
  grid (refine the grid or reduce dt)"*.
- `emfit/raster.py:36`, `:462-466`, `:490` — `dt = cfl_dt(grid)` on the board
  path.
- `emfit/scatter.py:87`, `:310` — same.

Two implementations exist (`evolve.cfl_dt` free function, `Maxwell.cfl_dt`
method) with *different default safeties* (0.99 and 0.95). That is a live
inconsistency worth knowing about before you compare two runs' wall times.

### 2.3 What actually sets the time step on a real board

`emfit/raster.py:57-62`, section "What sets the time step": `cfl_dt` is limited by
the finest cell on **every** axis, and on a board stackup the finest dimension is
usually a dielectric cell, not the lateral spacing. The worked numbers given
there: the thinnest mid-plane gap is 0.135 mm, so `cells_per_dielectric=2` gives a
0.0675 mm z cell against a 1 mm lateral cell — and the step is z-limited.

This is the practical reason grading the lateral axes buys **memory, not time**.
Halving a lateral cell across the board does not halve `dt`, because `dt` was
already set by z. State it plainly in any plan that promises a speed-up from
lateral refinement.

### 2.4 Where the CFL limit is *discussed* rather than computed

- `emfit/pml.py:678` — the CFL limit caps `dt` while `sigma_max` grows like `1/d`;
  the trapezoidal factor in a naive PML update can turn negative and produce a
  Nyquist oscillation, which is why an `exp` form is used instead. This is a real
  numerical-stability argument, not a citation.
- `emfit/huygens_fields.py:470` — *"On a CFL-limited step it is small: a 1 mm cell
  gives dt = 1.907e-12 s."* A useful sanity constant.
- `tests/test_abc.py` module docstring — *"CFL-limited dt = 2.394e-11 s, 900
  steps"* for its 320×16×1 duct (`dx = 7.5 mm`, `dy = 40 mm`).
- `emfit/studies.py:2862-2866` — the `dt_scale` knob, documented as *"Multiplier
  on the mesh's CFL time step; 1.0 is the step this study has always taken"*.
  `studies.py:3243` builds `dt = cfl_dt(grid) * dt_scale`. This is the escape
  hatch: if you suspect a marginal instability, halving `dt_scale` reproduces or
  cures it without touching the mesh. Do that before you re-mesh.

So: the CFL bound is implemented, cross-checked in two independent places, refused
at the API boundary when violated, used as the default everywhere, and explained
at the throttle. It is not a chapter waiting to be written.

---

## 3. The graded meshing plan — `docs/design/graded_meshing_plan.md`

**This is the filename.** Earlier notes referred to it by other names; the file is
`docs/design/graded_meshing_plan.md`, 650 lines, and it is the subject of `bb9d142`
(`docs: graded meshing for the lateral axes - a plan (design only)`) — the baseline
commit this pack's citations are stated against. It is **not** the subject of the
current HEAD, which is a later test-only fix (`a588603`, touching
`tests/test_animation_volume.py` and nothing else).

**Status: DESIGN ONLY.** No `emfit/` file was edited. No graded grid has been
built or run. A throwaway `tests/test_graded_meshing.py` was written, run and then
**deleted**, deliberately, so that no failing test is left in the tree claiming a
capability that does not exist. If you find that module name anywhere as evidence
that graded meshing works, it is not evidence.

### 3.1 The question (§1, `:22`)

`emfit.raster.build_grid` meshes the two lateral axes with **one** spacing, used
for both x and y. The plan asks what "graded" should mean for those axes: what the
caller passes, what is stored, how the port planes snap, and what it costs.

### 3.2 What exists at HEAD (§2)

- §2.1 (`:44`) — the lateral axes have exactly one producer, `build_grid`
  (`raster.py:330`), whose only lateral arithmetic is `_lateral_axis`
  (`:316-327`); only callers `raster.py:397` and `:398`. `build_grid` returns a
  `Grid`, never a tuple, so widening the return value is not a breakage risk — but
  the plan does not widen it.
- §2.2 (`:63`) — `Grid` already stores **edges**, not cells (`grid.py:32-45`,
  `:21-29`, `:134-136`). Therefore "what does a graded axis look like" is already
  answered by the library: edges.
- §2.3 (`:76`) — a scalar cell size is assumed outside `raster.py` in exactly
  **three** clusters. That count is the reason the change is small.
- §2.4 (`:101`) — the stability step is already min-based (§2.2 above), and the
  plan draws the conclusion at `:119`: **"Nothing about the time step has to change
  for grading."** That is the good news and, in §3D, the whole difficulty.

### 3.3 The rulings (§3)

- **A (`:126`)** — the interface is a *declarative cell-size spec* per lateral
  direction (`GradedAxis`), which owns the arithmetic; edges are the **internal**
  stored form only. Edges as the public parameter is explicitly rejected
  (`:164-166`): it works, but it forces every call site to know `n` in advance.
- **B (`:168`)** — snapping is a *directed* `searchsorted` (`_snap_edges(value,
  edges, *, up)`) with the TOL rule kept verbatim, and **refusal out of domain**.
  Silently clamping is named as the failure the port-plane checks exist to prevent
  (`board.py:545-551`). Because the scalar path is untouched, nothing that runs
  today can start raising.
- **C (`:206`)** — `build_grid` gains exactly one optional keyword, `dy`, plus a
  **byte-identity invariant that is proved, not asserted by eye** (`:237-240`). A
  uniform `GradedAxis.uniform(cell)` must take the *same* branch as `dx: float` —
  i.e. it must call `_lateral_axis` rather than accumulate widths — which makes the
  identity true by construction instead of by luck. This is the single best idea
  in the document; copy it whenever you refactor a numerical path.
- **D (`:242`)** — "the formula is right, and grading buys memory, not time." (i)
  the min-cell formula is correct and sufficient, but *conservative* `[INFERRED]`
  in the plan's own tag: the answer is governed by the globally smallest cell even
  if that cell sits in one corner. `dt_scale` (`studies.py:3243`) is the escape
  hatch.

### 3.4 The scope fence (§4, `:291`) — grade **x** only

A graded **y** is not a lateral-refinement change; it is a change to the mode
solver's premise. `mode_profile._section` builds a **uniform** cross-section, and a
graded y breaks that. The plan's position: refuse loudly rather than discover the
cross-section constraint through a wrong propagation constant. If you are asked to
"just do both axes while you are in there", this is the paragraph to quote.

### 3.5 The measurement (§5 `:320`, §7 `:551`)

§5 counts the scalar-cell sites by tokenising `emfit/studies.py` (6,288 lines),
dropping `COMMENT`/`STRING`/`FSTRING_MIDDLE` tokens and counting every NAME `cell`
adjacent to `OP "*"` or `OP "/"` — and prints the measurement in full so it can be
re-run rather than trusted. §7 describes the two-class harness: `TestUniformInvariants`
must be green **today** and after the refactor (byte-identity, uniform invariants,
the last of which is that the min-width CFL step is strictly below the max-width
one — §3D(i) as a test), plus the new graded behaviour.

### 3.6 What it explicitly does not decide (§8, `:630`)

1. **Where `GradedAxis` lives.** `emfit/grid.py` is proposed (metric arithmetic
   alongside `Grid`, and `grid.py` imports only numpy, so `board.py → grid.py`
   adds no cycle); a new `emfit/grading.py` would keep `grid.py` smaller and avoid
   touching the file that carries the byte-identity risk. Open.

§6 (`:390`) contains the planned diff — **not applied**. Do not read it as a
description of the code.

---

## 4. What is genuinely next

Ordered by value per unit of risk, with the reasoning attached so you can reorder
if you know something I do not.

### Increment 1 — close DR-47 (the listener gap)

Not a physics increment, and it belongs at the top of any list that touches the
UI. Right now every interactive control is untested as a class. Any redesign you
do in the visualiser is unverifiable until this is fixed, and the fix is small:
`state.ready()` in the shared fixture, a listener registry, one behavioural test
per control. Detail and gates in `03_KNOWN_BUGS.md` §2.

### Increment 2 — DR-46's convention (absent vs NaN)

Also not physics, and it blocks clean physics reporting: you cannot quote a
`gamma_plane` number from an artefact until absent and measured are
distinguishable. Convention + schema-version key + sweep. `03_KNOWN_BUGS.md` §3.

### Increment 3 — graded x, per the plan

The design is done and the risk is unusually well characterised: byte-identity is
provable, the CFL step needs no change, only three scalar-cell clusters sit outside
`raster.py`, and the scope fence keeps y out. The blocker is not technical, it is
sequencing: increments 1 and 2 are cheap and this one is not.

The first thing to write is **not** `GradedAxis`. It is the
`TestUniformInvariants` class from §7, running against today's code and green.
If it is not green, the invariant you were about to rely on is not an invariant.

### Increment 4 — the physics that this project has *not* solved

`docs/design/latex_structure.md` is an inventory of intended book chapters and it
is a useful list of unsolved corners, because a chapter that cannot be written is
a capability that is not there. From its own summaries: measured accuracy is
around 1.213 % mean cavity error with a 7.8 % `eps_eff` bias, and the dense
eigenpath *refuses* beyond 3000 free edges rather than running. Those are stated
as facts about the tool, not as plans to improve them, and the direction of travel
(non-uniform meshing; better lateral resolution without a finer time step) is
consistent with both.

### What not to do next

Three things that look like advances and are not:

1. **Renaming the legacy schema literals.** `emfit.wavedude/1`, `emfit.wavedude/2`
   are stored data. Renaming orphans every dump on disk
   (`server/poc_app.py:158`).
2. **Adding `load_series` to `emfit.poc-state/1`.** The old schema must never gain
   the keys that `emfit.poc-state/3` added. Readers upgrade; writers do not.
3. **Grading y** to make the numbers nicer. It breaks the mode solver's uniform
   cross-section premise, and the resulting propagation constant is wrong in a way
   no test in the tree would catch.

---

## 5. Circuit co-simulation — present, not prominent

`emfit/spice.py` (66,405 B) defines `SpiceState` `[BRIEFING]` at `:614`,
`SpicePort` at `:1299`, `initial_state` at `:1366` and `step` at `:1391`.

`emfit/coupling.py` (22,584 B) is where the field solve and the circuit solve
meet: `from .spice import SpicePort` is an **unconditional module-level import** at
`coupling.py:83`, `run_network` is at `:391`, the port is instantiated at `:509`
and driven at `:536` `[BRIEFING]`.

The structural point: because that import is unconditional, the circuit layer is
not an optional extra — importing `emfit.coupling` requires `spice.py` to import
cleanly. If you are ever tempted to make circuit co-simulation optional, this is
the line you would have to change, and it is not a one-line change.

---

## 6. The honest summary

The field solver, its mesh layer, its stability bound, its boundaries and its port
extraction are implemented, measured and documented to the line. The visualiser's
*data* logic is genuinely well tested — the player plan, the boundary mapping, the
per-frame colour scale and the no-volume fallback all have executable
specifications with real assertions. The visualiser's *interaction* logic is
untested as a class, for a reason that is now understood and written down (DR-47).

Lateral mesh grading is designed, argued, scoped, and not begun. The plan is good
and it is unusually cheap to inherit: it says which invariants must not move, proves
the one that could, and refuses the axis it cannot do safely.

That is the state. Read `03_KNOWN_BUGS.md` before you believe anything green.
