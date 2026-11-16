# 01 — Architecture

The short version: a pure-Python FIT solver (`emfit/`), one very large
application file that turns its output into a browsable page (`server/poc_app.py`,
611,825 B), and a study harness that writes the dumps the application reads
(`evidence/termination/run_build_A.py`). Everything else — the panels, the
context object, the tests — exists to keep those three from becoming one file.

Head is `a5886031a3657288751b6098dcbecee2b4965745` on `main`, subject
*"fix(tests): restore the shared trame server in animation volume teardown"*,
dated 2026-11-16, with 9 pre-existing untracked files and nothing modified. The
pack's own baseline was the commit before it, `bb9d142` — *"docs: graded meshing
for the lateral axes - a plan (design only)"* — which added
`docs/design/graded_meshing_plan.md`, and it is the tree every line-number
citation here is stated against. `a588603` touches one file only
(`tests/test_animation_volume.py`, a single hunk inside `_boot`), so advancing the
baseline moved no other citation. Read-only git only: this pack ran no git write
command.

---

## 1. The layers

```
  emfit/                  the solver library. 43 modules, 1,423,908 B.
      board.py            a microstrip coupon as a solver spec
      raster.py           the board -> mesh bridge (build_grid)
      grid.py             node coordinate arrays, frozen
      evolve.py           leapfrog time stepping, CFL
      pml.py, abc.py      absorbing boundaries
      ports.py            port extraction, S-parameters
      studies.py          the study layer. 335,308 B — six times the next module.
      spice.py            circuit co-simulation
      coupling.py         the join: field solve <-> circuit solve
      viz.py, animate.py  legacy visualisation helpers

  server/                 the application. 3 files, 644,501 B. NO __init__.py.
      poc_app.py          trame UI + argparse CLI + page model + dump readers
      um3k_context.py     PageContext — the page data shape
      um3k_panels.py      build_left_panel / build_center_panel / build_right_panel

  evidence/               study drivers and records
      termination/run_build_A.py    produces the vis dumps (--vis-dump, :3332)

  tests/                  93 files, 1,146 def test_  [BRIEFING]
```

Two things about that layout are unusual and both will bite you.

**`server/` is not a package.** There is no `__init__.py`. `server/poc_app.py:77-83`
imports its siblings *bare*:

```python
import um3k_context
from um3k_panels import build_center_panel, build_left_panel, build_right_panel
```

So `server/` has to be importable as a path entry, and an import that works when
you run the script can fail when you import it from a test. This is a real source
of "it works in one shell" reports.

**One file holds the whole application.** 611,825 B of it. The page model, the
CLI, the dump readers, the trame component tree and the event closures are all in
`poc_app.py`. That is not an accident to be cleaned up in a quiet afternoon; it is
the deferred cost of the page dict being the single data shape shared by the CLI,
the UI and the tests. Plan around it.

---

## 2. The bridge: `emfit/board.py`

717 lines. Its docstring states its job: *"A microstrip coupon as a solver spec —
the one bridge from KiCad to a study."* Everything upstream of it is geometry and
everything downstream of it is physics, and this module is the only place the two
meet.

What it defines: `MicrostripBoard`, `Load`, `Port`, `MM = 1e-3`, `TOL = 1e-12`.

The single most important property: **the mm → m conversion happens exactly once,
here.** Board geometry arrives in millimetres (it comes from KiCad, and from
humans), the solver works in metres, and the conversion is done at this boundary
and nowhere else. If you find yourself multiplying by `1e-3` in `raster.py`,
`studies.py` or a study script, you have either found a bug or created one.

The second: `_snap` **raises** when snapping collapses the span (`board.py:545-551`).
Snapping port and load planes onto mesh nodes is a directed search, and if a
directed search would move a boundary past its partner, the answer is a refusal,
not a clamp. Silently clamping is the failure mode the port-plane checks exist to
prevent — a port that snapped to the wrong node still produces a number, and the
number is wrong in a way nothing downstream can see.

---

## 3. The central data shape: the page

Everything the application shows is a **page**, a plain dict. `PageContext`
(`server/um3k_context.py:160`) is the typed-ish view of it, and its docstring is
explicitly about testability: *"Constructible bare, so a test can hold a page with
no dump yet."*

That design decision is why the test suite can test page behaviour without a
solver run, and it is the reason `PageContext` is worth reading early. Relevant
fields include `volume_field: bool` (`:99`) and `plane_stack: bool` (`:103`) —
two flags that decide whether the player has a time axis at all. `PageContext` is
instantiated in the app at `server/poc_app.py:10148`; the docstring points back at
`server/poc_app.py:5396-5398`.

A page dict, as returned by the constructors below, carries at least:

```
{"path": ..., "info": <board dict>, "planes": ..., "multifreq": ...,
 "record": ..., "structure_id": ..., "is_vis": bool}
```

with `info` being the board description the draw sites read.

---

## 4. Four page shapes, and why "bare board" is a real one

This is the part most often got wrong in handoffs, so it is stated precisely.
There are four distinct things a page can be, and they correspond to four
different amounts of known information.

### (a) A visualisation dump page

A page built from a dump on disk, with a board, planes and a field volume. Format
`um3k`, schema `emfit.vis/2` (`server/poc_app.py:149`), with
`"emfit.wavedude/1"` and `"emfit.wavedude/2"` still accepted via
`VIS_LEGACY_SCHEMAS` (`:158`). `is_vis` is true. This is the normal case.

### (b) A bare field dump — a dump with no volume

`is_vis` true, `info["nt"]` present, but no `e_abs_volume` to play. This shape
already existed and already had to be handled: it is exactly the case
`test_a_dump_without_a_volume_keeps_the_plane_clock` covers
(`tests/test_animation_volume.py:1250`, using the `no_volume_page` fixture). The
player falls back to the plane clock (§5).

### (c) A bare **board** — a board with no study record at all

**Yes, this is real and distinct**, and it is *not* the same thing as (b). It is
built by:

```python
def _bare_board_page(structure=None, record_path=None, structure_id=None) -> dict:
```

at `server/poc_app.py:3650`. It returns `"path": None`, `"planes": None`,
`"multifreq": None`, `"is_vis": False`, and an `info` board dict carrying
`format=None`, `cell_m`, `nx/ny/nz` taken from the geometry grid list,
`substrate_h_mm`, `strip_w_mm`, `port_x_mm`, `load_x_mm`, `xcut_near_mm`.

The rule that makes this shape safe: **every unknown is `NaN`, never a
constant.** The draw sites test `isfinite()`, so an unknown stays unknown and is
not drawn. A zero would draw a board at the origin; a plausible default would draw
a wrong board that looks right. `NaN` is the only value that survives to the
draw site and is still honestly "I do not know".

It is used from the CLI at `server/poc_app.py:13211-13222`
(`bare_page = _bare_board_page(...)`, passed on as `loaded_page=bare_page`), and
the draw side has its own diagnostic: `"[poc_app] bare board not framed: {exc}"`
at `:10352`.

There is a documented fall-through: if `not _page_has_board(board)`, it delegates
to `_builder_page(sid)` and prints to stderr

```
[poc_app] no study record with a mesh for <label>: the board is drawn from the emfit builder instead
```

That message is the app telling you which of two truths you are looking at: a
stored board, or one reconstructed from the `emfit` builder. Both are boards; only
one of them is a record.

Because a bare board has no `nt` and `is_vis` is false, it lands in the same
*rendering* path as (b) — but it is a different *data* shape, produced by a
different constructor, and conflating them is how a "why is my field volume empty"
investigation goes wrong for an hour.

### (d) A builder page

`_builder_page` / `_builder_board` (around `server/poc_app.py:3640-3648`) — again
`"path": None`, `"info": _builder_board()`, `"is_vis": False`. A board that exists
only because the builder can produce one from a structure id.

---

## 5. The two clocks, and the thing that makes the player correct

This is the subtlest piece of the application and it is worth more than the rest
of this document.

A visualisation dump can contain **two recordings at two different rates**:

- a set of **planes** captured at many time steps (the plane clock), and
- a **field volume** captured at *fewer*, coarser time steps (the volume clock).

The `desync_page` fixture exists to construct exactly this and it states the shape
in its docstring: *"A page whose |E| volume is the COARSER recording: 3 captures,
12 planes"* (`tests/test_animation_volume.py:1153-1154`, module-scoped). It also
asserts the fixture is honest — `info["e_abs_volume"]` is not `None` and
`int(info["nt"]) > len(DESYNC_VOLUME_STEPS)`.

The player's job, when you drag the slider, is to draw **one** coherent moment: the
plane shown must belong to the same physical time as the volume step being shown.
`_volume_player_plan(info, axis)` (`server/poc_app.py:8851`) computes that mapping.
Supporting guards sit alongside it: `_volume_frame_for_step` (`:8773`),
`_monotonic_axis` (`:8838`), `_synced_frame_counts` (`:8899`). `[BRIEFING]` for
those four line numbers; the behaviour below is verified from the tests.

The plan dict, as the tests read it, carries at least `steps`, `frames`,
`volume`, `plane` and `axis`. The mapping is asserted, not inferred:

- `plan["steps"]` equals the volume steps exactly,
- `plan["frames"]` is their count, and `state.frame_max == len(steps) - 1`,
- `plan["volume"]` walks `(0, 1, 2)` in order,
- `plane[0] == 0`,
- `axis[index] == steps[position]` — i.e. the plane index really is the axis
  position of that step, and
- `max(plane) == axis.index(last step)` — the **LAST FRAME rule**.

Then the assertions that matter to a user: for every player position,
`live.show(position, "ycut")` produces a frame whose `frame_index` equals
`steps[volume_frame]`, and whose label is `f"sim time: t = {t_ns[plane_frame]:.6f} ns"`
— the time of the **plane** frame, not the volume frame. The volume and the plane
agree on time, and the label states which moment you are looking at.

Two consequences that get rediscovered every generation:

1. **`_volume_player_plan(info, "xcut")` returns `None`** when the volume was
   recorded on the other axis. That is asserted at `tests/test_animation_volume.py:1287`
   and it is why the player must not assume the volume is there for the cut you
   happen to be showing. `None` means "no volume on this axis", not "not computed
   yet".
2. **The colour scale is per-frame.** `test_per_frame_clim_follows_the_volume_frame_the_player_is_showing`
   (`:1345`) pins it. A fixed clim would make a decaying field look like a
   flapping colour map.

Where the guarantees are written down in the app itself: the hazard prose is at
`server/poc_app.py:8853-8864`, the agreement claim at `:8874-8878`, and the
plane-clock fallback at `:8891` `[BRIEFING]`. `test_every_player_position_draws_one_time_step`
(`:1196`), `test_the_plan_maps_the_boundaries_and_the_tail` (`:1287`) and
`test_per_frame_clim_follows_the_volume_frame_the_player_is_showing` (`:1345`)
are the executable version, and they are the reason this subsystem is trustworthy
in a way the UI listeners are not (DR-47).

The lesson generalises: **the player is tested as a pure function of `info`, not
through the UI.** That is why DR-47 does not reach it, and it is the pattern to
copy when you need a UI behaviour to be actually tested.

---

## 6. The panels, and the missing context

`server/um3k_panels.py` (22,304 B) builds a three-column row:
`build_left_panel`, `build_center_panel`, `build_right_panel`, composed at
`:19`, `:53` and `:310` `[BRIEFING]`.

The structural fact `[BRIEFING]` from `docs/design/UM3K_UI_ARCHITECTURE.md`: §3.1
(`:63`) is where the panel inventory starts, and §3.6 (`:154`) records that the
panel builders contain on the order of **63 closures** and that the page context
does not reach them — the panels close over their own state rather than reading a
`PageContext` argument. The same document gives §4.4 (`:242`), §5 (`:259`), §6
(`:300`), §7 (`:331`) and §8 (`:371`) as the rest of the UI argument.

Why that matters practically: a change to the page model cannot be made
type-safe across the panels, because the panels do not take the page model. They
take whatever their closure captured. This is the mechanical reason DR-47's class
of bug is possible — a listener that "fires" and a closure that "wires it up" are
two different claims, and only the first is observable.

---

## 7. Constants you will want by heart

All from `server/poc_app.py:140-175` unless noted.

| Name | Value | Line |
|---|---|---|
| `DEFAULT_HOST` | `127.0.0.1` | `:140` |
| `DEFAULT_PORT` | `8080` | `:143` |
| `VIS_SCHEMA` | `emfit.vis/2` | `:149` |
| `VIS_LEGACY_SCHEMAS` | `emfit.wavedude/1`, `emfit.wavedude/2` | `:158` |
| `VIS_SCHEMAS` | current + legacy, both accepted | `:159` |
| `VIS_FORMAT` | `um3k` | `:160` |
| `VIS_FORMATS` | `um3k`, `wavedude` | `:161` |
| `STATE_SCHEMA_VIS` | `emfit.poc-state/3` | `:167` |
| `DEFAULT_FPS` | `24` | `:171` |
| `COLOR_PERCENTILE` | `99.5` | `:175` |
| `STATE_SCHEMA` (legacy) | `emfit.poc-state/1` | `:2062` |
| `DEFAULT_VOLUME_STRIDE` | `100` | `emfit/config.py:79` |

The two schema pairs are not duplication to be tidied. `emfit.poc-state/3` adds
`load_series` and `load_series_reason`; `emfit.poc-state/1` must stay
byte-for-byte and must **never** gain those keys. `um3k` is the new format name
and `wavedude` the old one; both open. Rule and rationale in `00_README.md` §7.

---

## 8. The seams, ranked by how much they will cost you

1. **The page dict.** Shared by CLI, UI and tests. Any new key must be optional
   on every reader, or every dump on disk stops opening. This is the highest-risk
   surface in the repo.
2. **`server/poc_app.py`.** 611 kB, one file, 63-plus event closures in the panel
   tree. Edits here are hard to review and hard to test (DR-47). Make them small.
3. **`emfit/studies.py`.** 335 kB. Changing a default here changes recorded
   results, which changes artefacts, which changes what the register can say.
4. **`emfit/board.py:545-551`.** The snap refusal. Do not soften it to a clamp;
   the clamp is the bug.
5. **The mm→m boundary.** One conversion site. Adding a second is how a board
   comes out a thousand times too big and the mesh silently "works".

---

## 9. How the tests are organised

`tests/` is 93 files `[BRIEFING]`, and the shape worth knowing is that the
strongest tests in the tree test **pure functions over `info`**, not the app.

`tests/test_animation_volume.py` (1,385 lines) is the exemplar. Its structure:

- a module-level `importorskip` trio at `:50-54` (pyvista, `trame.app`,
  `trame.ui.vuetify3`), so a machine without graphics skips the whole module
  cleanly instead of failing to collect;
- fixtures that build pages (`desync_page` at `:1153`, `no_volume_page`, and
  friends) with `tmp_path_factory`, i.e. real dumps written to disk;
- pure-plan tests (`:1287`) that never construct a widget;
- labelled/mapped player tests (`:1196`) that drive `live.show(position, "cut")`
  and compare indices and labels;
- colour-scale tests (`:1345`);
- a "no volume, keep the plane clock" test (`:1250`).

There are no `xfail` markers and no `finalizer` teardowns in that file — a claim
to the contrary is a ghost, see `03_KNOWN_BUGS.md` §9.

The weak spot is the opposite kind of test: the ones that boot the app. Their
shared fixture never lets trame dispatch, so no `@state.change` listener runs.
That is DR-47 and it is the first thing to fix in the next generation, because
until it is fixed, every UI behaviour you "protect" with a test is protected by a
comment.

---

## 10. Reading order for the code itself

If you have one afternoon:

1. `emfit/grid.py` (9,638 B) — what a mesh *is*. Frozen dataclass of node
   coordinate arrays; widths are `np.diff`. Twenty minutes, and the grading plan
   becomes readable.
2. `emfit/evolve.py:74-86` — `cfl_dt`. The stability bound is a one-liner and it
   already uses the minimum width, which is why grading does not destabilise it.
3. `emfit/raster.py:316-330` and `:57-62` — how a board becomes a grid, and what
   actually sets the time step on a stackup.
4. `server/um3k_context.py` (10,372 B, all of it) — the page shape.
5. `server/poc_app.py:3650-3700` — the four page constructors, in one screen.
6. `tests/test_animation_volume.py:1153-1400` — the four tests that specify the
   player. Read the assertions, not the names.
