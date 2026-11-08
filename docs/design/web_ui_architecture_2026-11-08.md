# Web UI architecture (PoC)

This is a design note for a proof of concept, not a description of a shipped feature. The single goal is an
interactive 3-D view of one field dump in a browser: load `build_A_50ohm_p51_ghostwave_fields.npz`, orbit it,
and step through the captured planes without re-running the solver.

## What the data actually is

The npz (12.9 MB) was inventoried directly:

- `plane_ez`, `plane_hy`: (9, 213, 22) complex128 - Ez and Hy on the 9 captured x-planes.
- `plane_ey`, `plane_hz`: (9, 212, 23) complex128 - Ey and Hz on the same planes.
- `e`, `h`: (906144,), (886676,) float64 - flattened per-step channels; scalars `nstep` 2399,
  `nx`/`ny`/`nz` 62/212/22 (cells), `cell_m` 0.0004 m.

Three properties matter for the UI and are easy to get wrong:

- **Cells versus nodes.** The scalars count cells, the planes are sampled on nodes: Ez/Hy carry ny + 1 = 213
  samples on axis 1, Ey/Hz carry nz + 1 = 23 on axis 2. One count for all four is off by one on every axis.
- **No axis vectors.** No x, y or z array exists, so coordinates are synthesised from `cell_m` = 0.4 mm:
  y spans 213 * 0.4 = 85.2 mm, z spans 22 * 0.4 = 8.8 mm.
- **Nine planes only.** x is not solved, it is sampled: 9 planes one cell apart give 9 * 0.4 = 3.6 mm of x at
  exactly 9 positions. Any volume is those 9 slices; between-station structure is not in the input.

**Open question, UNCONFIRMED: is the x label one cell low?** The PoC labels station i at `x = i * 0.4 mm`, giving
0.0000 .. 3.2000 mm. The ghost-wave forensics place the load at plane 50 and the reflection one cell later at
plane 51. If the first captured plane is plane 51, every label is one cell low and the true span is 0.4000 ..
3.6000 mm: +0.4 mm exactly, +12.5 % of the 3.2 mm span. The dump cannot settle it - no first plane index is stored.

## Recommendation: Trame

Trame (Kitware) is the primary candidate. Three concrete reasons:

1. **It wraps VTK/PyVista directly.** No second rendering stack to maintain: the scene graph a desktop
   PyVista session would build is the scene graph the browser shows.
2. **The same object that builds the scene serves it.** Server-side Python keeps the mesh, so there is no
   export step, no glTF/OBJ round trip, and no duplicated geometry to drift from the source data.
3. **It is an ordinary Python package.** `pip install trame pyvista` sits in the same dependency class as
   the existing numpy/scipy stack, so deployment gains no new runtime.

### Rejected or deferred alternatives

- **Panel / HoloViews** - good tools, but a second abstraction layer over VTK for no gain here.
- **Dash / Plotly** - excellent for charts, the wrong tool for volumetric VTK data.
- **Custom three.js front end** - most control, most work: a second language, a second deploy.
- **Desktop-only PyVista** - zero web, which is exactly the thing being built.

## Client-server model

```
+-----------+      WebSocket       +--------------------------------+
|  browser  | <=================>  |  trame server (Python process) |
|  slider   |                      |   npz held in memory           |
|  3-D view |                      |   PyVista scene, rendered      |
+-----------+                      |   off-screen by VTK            |
                                   +---------------+----------------+
                                                   | read once at start
                                                   v
                                evidence/termination/*.npz on disk
```

1. The server loads the npz once at startup and keeps the arrays in memory.
2. It builds the `pyvista.ImageData` grid once: 9 x 213 x 22 points at 0.4 mm spacing.
3. A state change (the station slider) triggers a re-render on the server.
4. The rendered frame is pushed to the browser over the same WebSocket.

The consequence, plainly: this is server-side rendering - the browser does no 3-D work and the server pays for
every frame. Fine for one user on localhost; the wrong choice for many, where client-side rendering is needed.

## Proof of concept

`server/poc_app.py` stacks the 9 planes at cell spacing into a `pyvista.ImageData`, volume-renders `|Ez|` with
the turbo colormap, exposes a slider over the station index with an x readout, and serves on 127.0.0.1:8080.

Status, split honestly. The numpy-only path (`--list-keys`) is **VERIFIED** - run against the real dump, output
below. The web path is **UNVERIFIED**: pyvista, VTK and trame are absent here and there is no network.

```
file        : /workspace/evidence/termination/build_A_50ohm_p51_ghostwave_fields.npz
plane       : plane_ez shape=(9, 213, 22) dtype=complex128
nstep       : 2399
nx/ny/nz    : 62 / 212 / 22 (cells)
cell_m      : 4.000000e-04 m  (0.400000 mm)
extent      : 3.6000 x 85.2000 x 8.8000 mm
samples     : 9 x 213 x 22
station x/mm: 0.0000, 0.4000, 0.8000, 1.2000, 1.6000, 2.0000, 2.4000, 2.8000, 3.2000
Re(Ez)      : min=-1.685409e+05  max=1.245009e+05
|Ez|        : min=0.000000e+00  max=1.793070e+05
```

That is current output, not a target. The `station x/mm` line is arithmetic from `cell_m`, not read from the file.

## Towards co-simulation

The hook point already exists. `emfit/studies.py` lines 2917-2922 are the `series_r` branch of the load stamp:
the load's edges are selected, cleared from the PEC mask, and the conductivity is incremented by
`sigma += 1.0 / (edges.size * R)` - one resistor of value R spread across the `len(edges)` parallel paths.

In plain English: the load is already a circuit element inside the grid, a material property on a known set of
edges, so a co-simulation boundary has a natural home right there.

Not implemented today: no port abstraction (the load is a value on a column, not an object with a name); no
netlist or SPICE model input; no iterative coupling loop between field solve and circuit solve; and no way to
inject a time-domain waveform arriving from a circuit solver.

Why this is the right next milestone: the interface is a single location in the source, not a rewrite, and
turning that fixed conductivity into a function of external circuit state is a local change at 2917-2922.

## Known risks and open questions

1. Web path unproven on the operator's machine. Mitigation: run `evidence/termination/check_pyvista.sh` first.
2. trame 2 versus trame 3 vuetify API drift. Mitigation: `poc_app.py` tries vuetify3 then vuetify2 - untested.
3. The npz is gitignored (`*.npz`), so the PoC cannot ship sample data. Mitigation: add a tiny fixture.
4. The 9-plane quantisation bounds any x-structure claim. Mitigation: label the axis as sampled stations.
5. Suspected one-cell x-label offset. Mitigation: record the first plane index, fix one line of arithmetic.
6. Server-side rendering cost per frame. Mitigation: acceptable for one localhost user; revisit if needed.

## Run it

```
sh evidence/termination/check_pyvista.sh
```
```
python3 -m pip install pyvista trame
```
```
python3 server/poc_app.py
```

Then open http://localhost:8080. `--list-keys` works with numpy alone: no install, no display.
