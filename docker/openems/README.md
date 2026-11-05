# openEMS reference solver (EXPERIMENTAL)

A pinned openEMS 0.0.35 image plus one smoke model, kept so that "the FDTD
engine really executes here" stays reproducible. It is **not** the project's
main runtime and nothing in the toolchain imports it. It is also **not** a
physics validation: the model is an empty air box with two 50 ohm lumped
ports, so all it demonstrates is that meshing, excitation, time stepping and
result writing all happen.

## Build

```sh
docker build -t openems:bookworm docker/openems
```

Pinned apt version `openems 0.0.35+git20190103.6a75e98+dfsg.1-3.2`
(CSXCAD python bindings 0.6.2, python 3.11.2). Measured image size 1.36 GiB.

## Run

No bind mount (results die with the container, which is usually what you want):

```sh
docker run --rm -i openems:bookworm python3 - < docker/openems/smoke_solve.py
```

With a bind mount, to keep the result files:

```sh
mkdir -p out_openems
docker run --rm -v "$PWD/out_openems:/tmp/oems/sim" openems:bookworm \
    python3 - < docker/openems/smoke_solve.py
```

Either way the script prints `SMOKE-OK: .../port_ut_1 (<bytes>) :: <header>`
and exits non-zero if the solver did not write a port file. It takes ~3 min
on 2 threads with the model as committed.

## Measured evidence

`/tmp/oems/sim` after a successful run:

```
-rw-r--r-- 1 root root   33216 et
-rw-r--r-- 1 root root   33189 ht
-rw-r--r-- 1 root root 1174638 port_it_1
-rw-r--r-- 1 root root 1174523 port_it_2
-rw-r--r-- 1 root root 1207446 port_ut_1
-rw-r--r-- 1 root root 1174550 port_ut_2
```

`head -5 port_ut_1`:

```
% time-domain voltage integration by openEMS v0.0.35 @Thu Nov  5 10:02:22 2026
% start-coordinates: (0.005,0.005,0.004) m -> [5,5,4]
% stop-coordinates: (0.005,0.005,0.005) m -> [5,5,5]
% t/s	voltage
0	-0
```

The header line is emitted by the `openEMS` C++ binary, not by the Python
bindings -- that is what distinguishes a real solve from a script that merely
returned.

## API traps in 0.0.35

Every point below was hit and verified against this build.

1. **`from openEMS import openEMS as OEMS` binds the CLASS**, not a module.
   Use `FDTD = OEMS()`. `OEMS.OpenEMS()` fails.
2. **`SetBoundaryCond` needs a six-element list.** A bare string always
   raises. Its docstring is wrong: it advertises `'PML-8'` and `(8,)`.
   - accepted: `PML_8`, `PML_3`, `PML_0`, `PEC`, `PMC`, `MUR`
   - rejected (`Exception: Unknown boundary condition`): `'PML'`, `'PML-8'`,
     `'periodic'`, `'PEC_0'`, `'MUR_0'`, and all-lowercase forms
     (`pml-8`, `pec`, `pmc`, `mur`)
3. **`openEMS/ports.py` uses `np.float`**, removed in numpy >= 1.24:
   `AttributeError: module 'numpy' has no attribute 'float'` at
   `ports.py:67  self.start = np.array(start, np.float)`. Shim it before use:
   ```python
   for a, b in (("float", float), ("int", int), ("complex", complex), ("bool", bool)):
       if not hasattr(np, a):
           setattr(np, a, b)
   ```
4. **`csx.DefineGrid(mesh, unit, smooth_mesh_res=None)` is broken** in
   CSXCAD 0.6.2 -- every argument shape tried raises `TypeError: only integer
   scalar arrays can be converted to a scalar index`. Use the grid object
   instead, and note that **an explicit mesh is mandatory** (no auto-mesh):
   ```python
   g = csx.GetGrid(); g.SetDeltaUnit(1.0)
   g.SetLines("x", xs); g.SetLines("y", ys); g.SetLines("z", zs)
   g.GetQtyLines("x"); g.IsValid()      # GetQtyLines requires a direction
   ```
5. **`ContinuousStructure` has no `AddBox`/`SetGrid`.** Primitives hang off a
   property: `air = csx.AddMaterial("air", epsilon=1); air.AddBox(start=..., stop=...)`.
   `CSPrimitives.CSPrimBox(csx, ...)` raises `TypeError` (it wants a
   ParameterSet). `csx.DefineGrid`, `AddMaterial`, `AddExcitation`, `AddProbe`,
   `AddMetal` are the structure-level entry points.
6. **`AddLumpedPort` / `AddMSLPort` are solver methods, not module
   functions.** `from openEMS.ports import AddLumpedPort` raises
   `ImportError`; `openEMS.ports` only holds the classes (`LumpedPort`,
   `MSLPort`, `RectWGPort`, `WaveguidePort`, ...). Call
   `FDTD.AddLumpedPort(port_nr, R, start, stop, p_dir, excite=0, **kw)` and
   `FDTD.AddMSLPort(port_nr, metal_prop, start, stop, prop_dir, exc_dir, excite=0, **kw)`
   (MSLPort does exist). `start`/`stop` must sit on grid lines and differ only
   along `p_dir`.
7. **`SetSolverType` does not exist** (`hasattr` is `False`; calling it gives
   `None is not a callable object`), nor does `SetMaxThreads`. Threads are a
   `Run()` keyword: `Run(sim_path, cleanup=False, setup_only=False, verbose=None, numThreads=N)`.
   `SetTimeStepMethod` *is* present.
8. **`PML_8` eats 8 cells per side.** On a coarse mesh the absorber swallows
   the whole port region (on a 21-line 1 mm/20 mm span only 4 mm stays
   non-PML). Use `MUR`, coarsen only the interior, or enlarge the domain.
9. **Simulation files written into a bind mount are root-owned.** `Run(...,
   cleanup=True)` clears the directory from inside the container, but the host
   user cannot `rm -rf` the results afterwards; use a throwaway directory per
   run.
