# Graded meshing for the lateral axes: a plan

**Status:** DESIGN ONLY. No file under `emfit/` was edited for this document and no
graded grid was built or run. What was *executed* is the throwaway test module in
§7, which pins the behaviour the plan has to preserve and demonstrates that the
proposed surface does not exist yet; it has been deleted again, so there is no
red test in the tree.

**Provenance labels.** `[ARTIFACT]` = read from a file at HEAD in this container.
`[MEASURED]` = a command was run here and its output is quoted. `[INFERRED]` = an
argument from tagged numbers, shown.

**Tree state.** `git status --porcelain` at the start and end of this session lists
exactly the 9 pre-existing untracked artefacts (`artifacts/freq_panel_preview.png`,
`artifacts/reference_sim_run.json`, three `artifacts/vis_run_*.json`,
`docs/design/c2b_shapes.{pdf,png}`, `docs/design/mispaired_metric_before.png`,
`docs/report/figures/c2b_mode_shape_corrected.png`). `[MEASURED]` The only file this
session adds is this one.

---

## 1. The question

`emfit.raster.build_grid` meshes the two lateral axes of the coupon with **one**
spacing, used for both:

```python
    x = _lateral_axis(_mm_to_m(xmin), _mm_to_m(xmax), dx)          # raster.py:397
    y = _lateral_axis(_mm_to_m(ymin), _mm_to_m(ymax), dx)          # raster.py:398
```

`[ARTIFACT]` The z axis is already graded, and has been from the beginning: it is
built from `np.linspace(lo, hi, cells_per_dielectric + 1)` per dielectric slab plus
a geometric air stretch from `_air_widths` (`raster.py:379-389`). So the mesh
machinery downstream is *not* uniformly-spaced today — only the lateral axes are.

The question this plan answers is what "graded" should mean for x and y: what the
caller passes, what is stored, how the port planes snap, and what it costs.

---

## 2. What exists at HEAD

### 2.1 The lateral axes have exactly one producer

`[ARTIFACT]` `build_grid(board, region, dx, *, cells_per_dielectric=2,
air_above=1.0e-3, air_below=0.5e-3, air_cells=3, periodic=(False, False, False),
warnings=None) -> Grid` at `raster.py:330`. Its only lateral arithmetic is

```python
def _lateral_axis(start, stop, spacing):                          # raster.py:316
    span = stop - start                                           # raster.py:323
    ...
    n = max(1, int(math.ceil(span / spacing - 1e-12)))            # raster.py:326
    return start + span * np.arange(n + 1, dtype=float) / n       # raster.py:327
```

`[MEASURED]` Its only callers are `raster.py:397` and `raster.py:398`; nothing else
in `emfit/`, `server/` or `tests/` calls it. `build_grid` returns a `Grid` object,
never a tuple, so widening the return value is not a breakage risk — but that is
moot, because the plan does not widen it.

### 2.2 `Grid` already stores edges, not cells

`[ARTIFACT]` `Grid` (`grid.py:32-45`) is a frozen dataclass of **node coordinate
arrays** `x, y, z` plus `periodic`; `_axis()` (`grid.py:21-29`) validates 1-D, ≥ 2
nodes, strictly increasing. `.widths(axis)` is `np.diff` (`grid.py:134-136`),
`.dual_widths`, `.edge_shape`, `.face_shape`, `.edge_length` and `.face_area_*`
(`grid.py:197-241`) all derive from the node arrays. There is no scalar `cell`
anywhere inside `Grid`, and the module docstring calls non-uniform spacing "first
class" (`grid.py:7`).

This single fact decides the internal representation (§3A): the answer to "what
does a graded axis look like" is already in the library — *edges*.

### 2.3 The scalar `cell` leaks in three clusters

Outside `raster.py`, a scalar cell size is assumed in exactly three places:

| where | what it does | why grading breaks it |
|---|---|---|
| `board.py:688` `_snap(value, cell, *, up)` | moves a value to the next multiple of `cell`; called at `board.py:542-543` with `cell = self.h / n_sub` (`:541`) inside `cropped_to_strip` (`board.py:480`) | `ceil/floor(ratio) * cell` has no meaning on a graded axis |
| `board.py:566` `to_cell_counts(self, *, n_sub, n_pml)` | `wanted = run / cell - cut` (`:623`) and `_integral(run / (self.h / ns) - cut)` (`:632`) | integer cell counts, not coordinates |
| `mode_profile.py:447` `_section(h, w, n_sub, n_clean, n_air)` | `cell = h / int(n_sub)`; `n_strip = int(round(w / cell))` (`:458`); **refuses** unless `abs(n_strip * cell - w) <= 1e-9 * cell` (`:459-464`); then `Grid.uniform(1, ny, nz, cell, ny * cell, nz * cell, periodic=(True, False, False))` (`:467-469`) | the cross-section is uniform *by construction*: the strip is an integer number of cells wide |

`[ARTIFACT]` `board.py`'s own module docstring says it "imports `emfit.kicad` and
nothing else from the package" (`board.py:16`), so teaching it about a graded axis
adds the first intra-package import to that file. That is a documented property to
update in the same commit, not a free change.

`[MEASURED]` The `_snap` docstring already states the rule this plan must not lose:

> ``value`` moved to the next multiple of ``cell``, up or down, or kept.
> A value that is already a whole number of cells is returned untouched -- not
> recomputed as ``round(value / cell) * cell``, which would differ from it by
> round-off and make a second call look like a change.

Two requirements follow, both executable (§7): **on-node values come back
unchanged**, and **`_snap` is idempotent**.

### 2.4 The stability step is already min-based, and already documented as such

`[ARTIFACT]` `evolve.py:74-86`:

```python
def cfl_dt(grid, *, c=C0, safety=0.99):
    inv_sq = 0.0
    for axis in "xyz":
        d = float(np.min(np.asarray(grid.widths(axis), dtype=float)))
        inv_sq += 1.0 / d ** 2
    return float(safety) / (c * np.sqrt(inv_sq))
```

and its docstring (`evolve.py:77-79`) already says a graded grid must use the
minimum width rather than the maximum. Same formula in `maxwell.py:79-86`
(`FITSystem.cfl_dt`) and in the `check_dt` guard at `maxwell.py:88-99`; the same
statement appears in `raster.py:36-37`, `:57-62`, `:462-466`.

**Nothing about the time step has to change for grading.** That is the good news
and, in §3D, the whole difficulty.

---

## 3. Rulings

### A. The interface: a declarative spec that owns the arithmetic; edges stored

**Ruling.** `build_grid` takes a *cell size spec* per lateral direction, not an
array of widths and not an array of edges:

```python
@dataclass(frozen=True)
class GradedAxis:
    """Cell size along one axis: a base cell plus refined windows."""
    base: float                                        # metres, the coarse cell
    refined: tuple[tuple[float, float, float], ...] = ()   # (lo, hi, cell) in metres

    @classmethod
    def uniform(cls, cell: float) -> "GradedAxis": ...

    def cell_at(self, x: float) -> float: ...          # local cell size at x
    def edges_between(self, start: float, stop: float) -> np.ndarray: ...
```

* **Public form = declarative** (`base` + windows). A caller knows *where* it wants
  resolution ("1 mm, but 0.25 mm across the gap") and does not know how many cells
  that is. Making the caller compute `n` and a `cumsum` is the arithmetic this
  class exists to own.
* **Internal form = edges**, for the three consumers that already want edges:
  `Grid` stores them (§2.2), `np.diff` recovers the widths for every operator and
  for `cfl_dt`, and a snap wants to *search* them (§3B). Storing widths would force
  `Grid` to change — the one change with a byte-identity risk and no upside.
* **The scalar path is a thin wrapper**, `GradedAxis.uniform(cell)`, so `dx: float`
  keeps working unchanged and the uniform branch inside `edges_between` is free to
  keep calling `_lateral_axis` verbatim (§3C).

**Rejected: widths-only as the parameter.** `[INFERRED]` Widths are ambiguous about
origin and alignment (`np.diff` loses the first node; where the coarse/fine
interface lands depends on where you start counting), and every consumer would have
to `cumsum` them back. It also puts the ambiguity in the caller's hands, which is
where the "two widths for one strip" class of bug comes from
(`studies.py:3051-3058` is the existing guard against exactly that failure mode).

**Rejected: edges as the public parameter.** It works — `Grid` takes them — but it
forces every call site to know `n` in advance and to build the array, i.e. it
removes nothing and adds surface. Keep it as the *internal* form only.

### B. Snapping: directed `searchsorted` + the TOL rule kept verbatim + refusal out of domain

```python
def _snap_edges(value: float, edges: np.ndarray, *, up: bool) -> float:
    """``value`` moved to the neighbouring node of ``edges``, up or down, or kept."""
    if not (edges[0] <= value <= edges[-1]):
        raise ValueError(...)
    i = int(np.searchsorted(edges, value, side="left" if up else "right"))
    candidate = edges[min(i, edges.size - 1)] if up else edges[max(i - 1, 0)]
    if abs(candidate - value) <= TOL * max(1.0, abs(value)):   # board.py:59, :715-717
        return value                                          # unchanged, as today
    return float(candidate)
```

* **Directed, not nearest.** The API stays `up=True|False` and the direction
  resolves the midpoint case, so there is no tie rule to invent: the midpoint goes
  up when `up` and down when not. `[ARTIFACT]` `_snap`'s docstring already defines
  the semantics as "the nearer boundary *in the requested direction*, so an upward
  snap never lands below the value it started from".
* **The TOL branch is not optional, and it is the branch that is easiest to lose.**
  `[MEASURED]` With `cell = 0.1`, a value of `3.0 * cell` is `0.30000000000000004`
  and `/cell` is `3.0000000000000004`; the raw `ceil(ratio) * cell` answers `0.4`,
  one whole cell of motion from a 4.4e-16 artefact. On a graded axis the same
  hazard is larger, because node coordinates arrive as `cumsum` of unequal widths
  and a caller's `value` is not a multiple of anything — so the rule becomes "if
  the **directed** neighbour is within `TOL * max(1, |value|)`, return the caller's
  value". It is the directed neighbour and **not** the nearest node:
  `searchsorted(..., side="left")` yields the first node at or above `value` when
  `up`, `side="right"` yields one past the first node at or below it, so the
  comparison is against `edges[i]` or against `edges[i-1]` — a node that happens to
  be nearer in the *other* direction is never consulted, which is exactly what
  keeps an upward snap from landing below where it started.
* **Out of domain raises, and only on the graded path.** A port plane outside the
  axis cannot be snapped without moving it off the axis, and silently clamping is
  the failure this project's port-plane checks exist to prevent (`board.py:545-551`
  raises when the snap collapses the span). The scalar path is untouched, so
  nothing that runs today can start raising.

### C. `build_grid`: one optional keyword, and a byte-identity invariant that is proved, not asserted by eye

```python
def build_grid(board, region, dx: float | GradedAxis,
               *, dy: float | GradedAxis | None = None,      # NEW; None -> dx
               cells_per_dielectric=2, air_above=1.0e-3, air_below=0.5e-3,
               air_cells=3, periodic=(False, False, False), warnings=None) -> Grid
```

* `dy=None` means "same as `dx`", which is what happens today (both axes get `dx`,
  `raster.py:397-398`). Every existing call — `raster.build()` at `:474` and the
  seven in `tests/test_raster.py` — is positional in `dx` only and keeps working.
* z is untouched. It is already graded (§1) and its grading means something
  different (a stackup boundary is not a resolution wish).
* **The invariant that proves nothing moved:**

  > For all-uniform input, `build_grid(...).x` and `.y` are **bit-identical** to the
  > arrays HEAD produces. Checked with `np.array_equal`, never `np.allclose`.

  `[INFERRED]` This is checkable cheaply because the lateral coordinates have a
  single producer (§2.1): pin `_lateral_axis` and you have pinned `build_grid`'s
  lateral output; `Grid.nonuniform` only stores what it is given. §7 does exactly
  that, and additionally pins the float *expression* `start + span*arange(n+1)/n`
  rather than the value, because a rewrite that computes the same numbers a
  different way is still a change to every downstream comparison.

  **Caveat on the word "proves".** That proof is §7's green class, and §7's run is
  unreproducible (it says why), so what stands here today is a *stated* invariant
  with named tests, not a demonstrated one. Re-creating `TestUniformInvariants`
  from the inventory in §7 and watching it go green is what would make the claim a
  proof; until someone does that, byte-identity is an `[INFERRED]` argument from
  §2.1's single producer and should be read as one.
* A uniform `GradedAxis.uniform(cell)` must take the *same* branch as `dx: float` —
  i.e. it must call `_lateral_axis` rather than accumulate widths — which is what
  makes the byte-identity claim true by construction instead of by luck.

### D. The time step: the formula is right, and grading buys memory, not time

**(i) Is the min-cell formula correct?** Yes, and sufficient: `[ARTIFACT]`
`cfl_dt` already sums `1/d²` over the *minimum* width of each axis (§2.4). A graded
mesh cannot destabilise it. It is, however, *conservative*: `[INFERRED]` the answer
is governed by the globally smallest cell even if that cell sits in one corner and
the wave is elsewhere. `cfl_dt` is not the thing to change in this increment.

**(ii) Does grading buy time?** No. It buys memory and feasibility, and the
arithmetic is unforgiving:

* `dt` is pinned by `max_axis(1/min_width)`, so refining anywhere lowers `dt` for
  *every* cell in the domain;
* run time ∝ `n_steps · n_edges`. Refining by a factor `k` over a fraction `f` of
  one axis gives `n_steps ∝ k` and `n_edges ∝ (1 + (k-1)f)`;
* so grading is `k(1 + (k-1)f)` units of work against `k²` for refining the same
  axis *uniformly* — a saving of `k/(1 + (k-1)f)` **against that uniformly refined
  run**, and still a factor `k(1 + (k-1)f)` **of extra work against the coarse
  run**.

`[INFERRED]` Worked: `k = 8`, `f = 0.1` gives `8 · 1.7 = 13.6` against `64` for a
uniform `k = 8` (4.7× cheaper), and against `1` for not refining at all (13.6×
dearer). **A time saving needs local time stepping or subcycling, which is out of
scope here.** Stating this up front is the point: grading is justified by "the
coarse mesh is not accurate enough where it matters and the fine mesh does not
fit", not by "it will be faster".

**(iii) Does a large `dx`/`dy` threaten stability?** No: a large width only makes
its own `1/d²` term smaller. It is an **accuracy** problem, and the diagnostic is
per-axis, not global. Define `S_a = C0 · dt / min_width_a`; then
`sqrt(ΣS_a²) ≤ safety` is the stability condition (already implicit in `cfl_dt`)
and `S_a ≲ 0.5` per axis is the accuracy condition. `[INFERRED]` With x graded to
0.1 mm and y left at 1 mm, `S_y = 10 · S_x`, so the phase advances ten cells per
step in y: the mesh is stable and anisotropic, and the dispersion error that
dominates is the *y* one. That is acceptable exactly when y is the direction
without structure to resolve — for this coupon it is not (fringing beside the
strip), so the honest recommendation is to **report `S_a` per axis** and warn when
one exceeds ~0.5. `CouponInfo` already carries `min_width` and `dt`, so this is an
additive field (default-valued, appended) that no existing caller reads.

**(iv) What does an over-optimistic stability number look like first?** Total
energy that **grows** step over step (`studies.py` records the ringdown energy
trace), with the noise appearing first at the finest-cell / material-discontinuity
region and then NaN within a few hundred steps. The practical triage knob already
exists: `studies.py:3243` builds `dt = cfl_dt(grid) * dt_scale`, so halving
`dt_scale` reproduces or cures a marginal instability without touching the mesh.

---

## 4. The scope fence this forces: grade **x** only, and say so

A graded *y* is not a lateral-refinement change, it is a change to the mode
solver's premise:

* `[ARTIFACT]` `mode_profile._section` builds a **uniform** cross-section
  `Grid.uniform(1, ny, nz, cell, ny * cell, nz * cell, periodic=(True, False, False))`
  and **refuses** any strip width that is not an integer number of cells
  (`mode_profile.py:457-464`). A non-uniform y makes "the strip is `n_strip` cells
  wide" meaningless.
* `[ARTIFACT]` `studies.py:3063` builds its whole box with one `cell`:
  `grid = Grid.uniform(nx, ny, nz, nx * cell, ny * cell, nz * cell)`, with
  `nx = n_pml + n_ref + n_line` etc. as *integer counts*. Every one of the 24 code
  lines (29 occurrences) of forward `index * cell` counted in §5 rests on that.

x is different: it is the long axis, it is where the port planes are
(`cropped_to_strip` snaps only the two x planes, `board.py:542-543`), and it is the
only axis with a coordinate→index inverse that matters (`studies.py:3260`,
probe stations).

**Ruling.** The `GradedAxis` type is direction-agnostic and `build_grid` accepts it
on either lateral axis, but this increment implements and exercises **x only**:
`dy` keeps its `None -> dx` meaning, and a non-uniform `dy` raises
`NotImplementedError` with the `mode_profile._section` reason in the message.
Refusing loudly is cheaper than discovering the cross-section constraint through a
wrong propagation constant.

---

## 5. The scalar-cell sites, counted

`[MEASURED]` Tokenise-and-count over `emfit/studies.py` (6 288 lines), dropping
`COMMENT`, `STRING` and `FSTRING_MIDDLE` tokens and counting every NAME `cell`
that has `OP "*"` or `OP "/"` immediately before or after it. The measurement in
full, so it can be re-run rather than trusted:

```python
toks = [t for t in tokenize.generate_tokens(io.StringIO(src).readline)
        if t.type not in (COMMENT, STRING, FSTRING_MIDDLE, NL, NEWLINE,
                          INDENT, DEDENT)]
for i, t in enumerate(toks):
    if t.type == NAME and t.string == "cell":
        p, q = toks[i-1].string, toks[i+1].string
        if "*" in (p, q):  fwd[t.start[0]] += 1     # forward: index * cell
        elif "/" in (p, q): inv[t.start[0]] += 1    # inverse: value / cell
```

| form | code lines | occurrences | where |
|---|---|---|---|
| forward `index * cell` | **24** | 29 | `3051, 3053, 3058, 3063, 3077, 3164, 3223, 3266, 3973, 4068, 4069, 4085, 4274, 4280, 4281, 4358, 4359, 4363, 4364, 4365, 4375, 4561, 4562, 4565` |
| inverse `/ cell` | **4** | 4 | `3057, 3134, 3260, 4286` |

The two columns differ because three forward lines carry more than one site: `21
lines x 1 + 3051 x 2 + 3063 x 3 + 4274 x 3 = 29`. `[MEASURED]` The earlier estimate
of "~34 sites" does **not** reconcile exactly: the count is **33 occurrences across
28 code lines**, one short of 34 — so the estimate was within one, and no better
than that. The inverse sites are *not* uniformly `round(value / cell)`:

* `3134` `int(np.floor(float(load.position) / cell + 0.5))` — a real index;
* `3260` `js = np.floor(wanted / cell + 0.5).astype(int)`, with `station_x = js * cell`
  at `3266`, a `np.clip` at `3261`, and a "stations collapse onto one node layer"
  guard at `3262-3265` — a real, vectorised index;
* `3057` and `4286` are **human-facing numbers inside messages / metadata**, not
  indices (`n_strip=` advice in a `ValueError`, and `station_fit_cells` for the
  report).

`[MEASURED]` `grep -n 'ceil\|floor\|searchsorted' emfit/studies.py` finds no `ceil`
over a cell ratio and **no `searchsorted` at all**, so the graded rewrite cannot
lean on cell-count machinery that happens to exist already — the `ceil(span / cell)
* cell` idiom is `board.py:700`'s, not `studies.py`'s. Two qualifications, both
taken from that same grep rather than assumed:

* the only `ceil`/`floor` *over* `/ cell` are the two inverse sites already listed
  above, `3134` and `3260` — `np.floor(x / cell + 0.5)`, rounding a coordinate to a
  node index, the direction §5 is not counting;
* the only `np.ceil` calls in the module are `1063-1065`, and they are not a
  counter-example: `lo = float(np.floor(min(ours_db.min(), mie_db.min()))) - 1.0`,
  `hi = float(np.ceil(max(ours_db.max(), mie_db.max()))) + 1.0`,
  `ticks = np.arange(np.ceil(lo / 10.0) * 10.0, hi, 10.0)` round **dB plot-axis
  limits** on a polar Mie plot — plot furniture, not geometry, and `cell` appears on
  none of the three lines.

Outside `studies.py`, `[MEASURED]` `grep -rn '/ cell' emfit/ --include=*.py | grep -v
studies.py` returns **5** lines: `board.py:623` (the `to_cell_counts`
comprehension), `board.py:692` (docstring prose), `board.py:697` (the `_snap`
body), `mode_profile.py:458`, and `mode_profile.py:462` (inside the refusal's
`f`-string). Two more write the same division without the spacing and so miss that
pattern: `mode_profile.py:461` (`w/cell = ` in the same message) and `pml.py:427`
(`~1.5 Np/cell`, prose). So the real inverse sites outside `studies.py` are
`board.to_cell_counts`, `_snap`, and `mode_profile._section` — the three in §2.3.

**What moves in which increment.** Increment 1 (§6) touches `grid.py`, `raster.py`
and `board.py`; `to_cell_counts` *refuses* a graded axis with a `ValueError` rather
than guessing. `mode_profile.py` and `studies.py` are untouched and keep their
uniform `Grid.uniform(...)` boxes, which is exactly why increment 1 cannot silently
change a propagation constant.

---

## 6. The planned diff (proposed, not applied)

`emfit/grid.py` — additive; `Grid` is not touched, so no byte-identity risk:

```diff
+@dataclass(frozen=True)
+class GradedAxis:
+    base: float
+    refined: tuple[tuple[float, float, float], ...] = ()
+
+    @classmethod
+    def uniform(cls, cell: float) -> "GradedAxis":
+        return cls(base=float(cell))
+
+    def cell_at(self, x: float) -> float: ...
+    def edges_between(self, start: float, stop: float) -> np.ndarray: ...
+
+
+def _snap_edges(value: float, edges: np.ndarray, *, up: bool) -> float: ...
```

`emfit/raster.py` — one keyword, one delegated branch, and one guard the current
code makes it impossible to skip. Three hunks:

```diff
 def build_grid(board, region, dx,
+              *, dy=None,
               cells_per_dielectric=2, air_above=1.0e-3, air_below=0.5e-3,
               air_cells=3, periodic=(False, False, False), warnings=None) -> Grid:
```

```diff
@@ raster.py:361-363 @@
-    dx = float(dx)
-    if not dx > 0.0:
-        raise ValueError(f"dx must be positive, got {dx!r}")
+    if isinstance(dx, (int, float)):
+        dx = float(dx)
+        if not dx > 0.0:
+            raise ValueError(f"dx must be positive, got {dx!r}")
+    elif not isinstance(dx, GradedAxis):
+        raise TypeError(
+            f"dx must be a number or a GradedAxis, got {type(dx).__name__}")
```

```diff
@@ raster.py:396-399 @@
     try:
         xmin, ymin, xmax, ymax = (float(v) for v in region)
     except (TypeError, ValueError) as exc:
         ...
+    dy = dx if dy is None else dy
+    if not isinstance(dy, (int, float)):
+        raise NotImplementedError(
+            f"a graded y axis is not implemented: dy={dy!r}.  The lateral "
+            f"mesh takes one spacing per axis (_lateral_axis), so a graded y "
+            f"needs a second axis object and its own byte-identity argument; "
+            f"refusing here is what keeps §4's fence real instead of "
+            f"aspirational")
     x = _lateral_coordinates(_mm_to_m(xmin), _mm_to_m(xmax), dx)
-    y = _lateral_axis(_mm_to_m(ymin), _mm_to_m(ymax), dx)
+    y = _lateral_axis(_mm_to_m(ymin), _mm_to_m(ymax), dy)
```

with `_lateral_coordinates(start, stop, spacing)` = `_lateral_axis(start, stop,
spacing)` when `spacing` is a number (verbatim, same expression, same `n`, so §3C's
byte-identity is not a second argument that has to hold) and
`spacing.edges_between(start, stop)` otherwise. `dy` is keyword-only, so the eight
existing call sites (seven in `tests/test_raster.py` plus `raster.build()` at
`:474`) do not move.

`[MEASURED]` The first hunk is not defensive tidying. As the keyword alone was
first written, a `GradedAxis` arriving as `dx` died at `:361` — `dx = float(dx)`
raises `TypeError: float() argument must be a string or a real number` — so the
`_lateral_coordinates` delegation below it was unreachable and the diff could not
have run as delivered. The guard is what makes the delegation reachable at all.

The second hunk is the refusal that makes §4's fence real. `dy = dx if dy is None
else dy` leaves today's `y` expression untouched (the existing line uses `dx`), and
anything that is not a number is refused *before* it reaches `_lateral_axis`, whose
`n = max(1, int(math.ceil(span / spacing - 1e-12)))` at `:326` would otherwise raise
`TypeError` three frames down on `span / spacing`. It is the same reason
`mode_profile._section` refuses its own graded case out loud (`:457-464`) rather
than guessing: graded `x` only is increment 1's scope, and scope that nothing
enforces is not scope.

`emfit/board.py` — the scalar path stays, a graded branch is added beside it. The
axis arrives as a **new keyword**, not as an overload of `n_sub`: four hunks,
quoted against the code as it stands.

```diff
@@ board.py:480 @@
-    def cropped_to_strip(self, *, n_sub: int | None = None) -> "MicrostripBoard":
+    def cropped_to_strip(self, *, n_sub: int | None = None,
+                         x_axis: "GradedAxis | None" = None) -> "MicrostripBoard":
```

```diff
@@ board.py:528 @@
-        if n_sub is None:
+        if n_sub is None and x_axis is None:
             if abs(self.x_far - self.length) <= TOL * self.length:
                 return self
```

```diff
@@ board.py:535-543 @@
-        n_sub = int(n_sub)
-        if n_sub < 1:
+        if n_sub is not None:
+            n_sub = int(n_sub)
+        if n_sub is not None and n_sub < 1:
             raise ValueError(
                 ...
-        cell = self.h / n_sub
-        x_port = _snap(self.x_port, cell, up=True)
-        x_far = _snap(self.x_far, cell, up=False)
+        if x_axis is None:
+            cell = self.h / n_sub
+            step = f"{cell * 1e3:.6f} mm cells"
+            x_port = _snap(self.x_port, cell, up=True)
+            x_far = _snap(self.x_far, cell, up=False)
+        else:
+            edges = x_axis.edges_between(0.0, self.x_far)
+            step = f"the graded x axis ({edges.size - 1} cells)"
+            x_port = _snap_edges(self.x_port, edges, up=True)
+            x_far = _snap_edges(self.x_far, edges, up=False)
```

```diff
@@ board.py:547 @@
-                f"snapping to {cell * 1e3:.6f} mm cells leaves a span of "
+                f"snapping to {step} leaves a span of "
```

Why a new keyword rather than letting `n_sub` carry a `GradedAxis`: `n_sub =
int(n_sub)` at `:535` runs before any branch at `:542` could test its type, so the
overload would raise `TypeError` on the graded path — and `n_sub` is still the
count `to_cell_counts` takes (`:566`), so the parameter a caller passes must not
change type behind one method. The `:528` early return has to be conditioned on
`x_axis` too, or a graded crop with `n_sub=None` returns the box before anything
is snapped. And the span message at `:547` names `cell`, which does not exist on
the graded path — hence `step`, which carries its unit in both branches. The
docstring's `Args:` gains one entry for `x_axis` and the `n_sub` entry keeps its
text: they are alternatives, not layers.

`edges_between(0.0, self.x_far)` is not a placeholder. The method holds both
`x_port` (`:212`) and `x_far` (`:213`), and `0.0` is the origin `to_cell_counts`
already measures from — its `n_ref` entry is `self.x_port` "measured from x=0"
(`:618`) and `_snap`'s ratio `value / cell` (`:697`) is the same convention. The
far end is `self.x_far` rather than the box's, because `to_cell_counts` insists
the far plane sit on the wall (`:604-611`): snapping to a plane already on the
mesh is a no-op by construction, so the crop cannot lose cells by passing its own
far wall.

`_snap` itself is **not** rewritten; the graded path is a sibling, so the uniform
branch keeps the exact expression `ceil/floor(ratio) * cell` and the `[MEASURED]`
`0.4` hazard of §3B cannot reach it.

---

## 7. Executed evidence: the two-class harness

A throwaway module `tests/test_graded_meshing.py` was written, run, and deleted.
It had two classes, and the split is the deliverable:

* `TestUniformInvariants` — must be green **today** and after the refactor. These
  are the acceptance test for increment 1.
* `TestGradedBehaviour` — must be red **today**, and green after. Red because the
  surface does not exist, not because the assertions were guessed.

`[UNREPRODUCIBLE]` The run itself cannot be repeated: the module was deleted and
never committed, so nothing below can be regenerated from this tree. It is quoted
as it was observed, and a reader is entitled to discount it accordingly.

Observed at the time, verbatim (`python3.12 -m pytest tests/test_graded_meshing.py
-o addopts="" -q -k <class>`; `-o addopts=""` because `pyproject.toml:62` sets
`addopts = "-q"`, which suppresses the count line):

```
-k TestUniformInvariants   ->  9 passed, 8 deselected in 0.51s      (exit 0)
-k TestGradedBehaviour     ->  8 failed, 9 deselected in 0.70s      (exit 1)
```

`[UNREPRODUCIBLE]` The 8 red failures were exactly 3 distinct reasons, all "not
written yet":

```
AttributeError: module 'emfit.grid' has no attribute '_snap_edges'   x4
AttributeError: module 'emfit.grid' has no attribute 'GradedAxis'    x3
AssertionError: assert 'dy' in mappingproxy(...)                     x1
```

The new names are fetched with `getattr` **inside** the test bodies, never at
module import, so the missing symbols cannot poison collection of the invariant
class — which is why the two lines above coexisted in one file.

`[MEASURED]` What did survive the deletion is the compiled module,
`tests/__pycache__/test_graded_meshing.cpython-312-pytest-9.1.1.pyc` (git-ignored,
so absent from `git status`), and it fixes the *shape* even where it cannot fix the
counts: 2 classes, **7** test functions in `TestUniformInvariants` and **6** in
`TestGradedBehaviour`, plus the helpers `_uniform_cell_count`, `_not_yet` and
`_graded_edges`. The 13, in the order the claims below make them:

* `TestUniformInvariants`: `test_lateral_axis_keeps_the_arithmetic_it_has_now`,
  `test_lateral_cell_never_exceeds_the_requested_dx`,
  `test_snap_returns_an_on_node_value_unchanged`,
  `test_snap_brackets_the_value_within_one_cell`,
  `test_cfl_dt_is_pinned_by_the_minimum_width`, `test_snap_is_idempotent`,
  `test_grid_widths_are_the_diff_of_the_edges`;
* `TestGradedBehaviour`: `test_snap_edges_is_directed`,
  `test_snap_edges_leaves_a_node_alone`,
  `test_snap_edges_refuses_to_move_a_plane_off_the_axis`,
  `test_uniform_graded_axis_is_byte_identical_to_today`,
  `test_graded_snap_is_idempotent`,
  `test_build_grid_takes_one_axis_spec_per_lateral_direction`.

`[MEASURED]` So 7 and 6 need not agree with 9 and 8, and the gap is
`pytest.mark.parametrize`: both class bodies carry it, which makes 9 and 8 *cases*
— 7 functions become 9, 6 become 8. The numbered claims below are therefore claims
per **function**; re-creating the module gives 9 and 8 back only if the
parametrisation comes back with it.

What the green class pins (each one is a claim from §2–§3 in executable form):

1. `_lateral_axis` reproduces `start + span * np.arange(n+1)/n` **bit for bit**
   over four spans, `np.array_equal` — the byte-identity anchor of §3C.
2. The cell count is a `ceil`: `span/dx = 10/3` gives 4 cells of 2.5 mm, not 3.
3. `_snap(3.0 * 0.1, 0.1, up=True) == 0.30000000000000004`, while
   `ceil(ratio) * cell == 0.4` — the TOL branch of §3B, with a number that
   distinguishes the two behaviours instead of restating the code.
4. `_snap` brackets the value within one cell, both directions.
5. `_snap` is idempotent, both directions — the docstring's "second call look like
   a change".
6. `cfl_dt` of a grid containing a 0.5 mm cell among 1 mm cells equals the
   min-width formula and is strictly below the max-width one — §3D(i) as a test.
7. `Grid.widths(axis) == np.diff(edges)` — §2.2, why the internal form is edges.

---

## 8. What this document does not decide

1. **Where `GradedAxis` lives.** `emfit/grid.py` is the proposal (it is metric
   arithmetic alongside `Grid`, and `grid.py` imports only numpy, so
   `board.py -> grid.py` adds no cycle). A new `emfit/grading.py` would keep
   `grid.py` smaller and avoid touching the file with the byte-identity risk.
   Either is compatible with everything above; the choice is the reviewer's.
2. **Whether `cropped_to_strip` grows an axis parameter in increment 1 at all.**
   The port planes only need snapping when the x mesh is graded, so increment 1
   could ship "graded x, uniform x crop only" and defer `_snap_edges` entirely.
   §3B is written so that deferring it changes nothing already decided.
3. **`to_cell_counts` on a graded axis** — deferred by refusal (§5). The integer
   -count arithmetic is a second increment with its own byte-identity question.
4. **Whether `CouponInfo` gains per-axis Courant numbers.** Recommended in §3D(iii)
   as an appended default-valued field; not done, because nothing in this document
   was implemented and no `CouponInfo` construction site was audited for positional
   use.
5. **No numerical evidence.** No graded grid was built, no run was timed, and the
   cost model in §3D(ii) is arithmetic, not measurement. If the decision hinges on
   the 13.6× figure, that needs a measured `n_edges · n_steps` from a real coupon
   before it is quoted as more than an argument.
