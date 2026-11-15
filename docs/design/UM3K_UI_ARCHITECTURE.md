# UM3K UI architecture: one page, panels as data

This document describes the web UI in `server/poc_app.py`, states what is measurably wrong with its
structure, and specifies a target architecture and migration path. It is not a plan of record:
everything in Sections 4 and 7 is a proposal until Section 9 is answered.

Conventions: every factual claim carries a `file:line` citation into the tree at the time of writing.
Where evidence is absent the text says `unknown` rather than guessing. Ranges are inclusive; bare line
numbers refer to `server/poc_app.py` (9,771 lines). Those counts and line numbers describe the working
tree at the time of writing, which carries 52 net uncommitted lines of C2 follow-up work in `_view_label`,
`_draw_scene`, `_show_volume_quiver` and `_volume_quiver_mesh`, all of them between `:3245` and `:6790`; at
commit `7d6683c` the same code therefore sits up to 52 lines lower, and nothing cited above `:3245` moves.

---

## 1. Status and scope

**Status.** Draft for review by Gen 13 and the PI. Nothing in Sections 4 and 7 has been implemented,
and no code was changed to produce this document.

**In scope.** The structure of the two trame applications in `server/poc_app.py` (`run_web` at `:3901`,
`run_web_vis` at `:7044`), the data they are handed, the naming that leaks through them, and the tests
that constrain any change to them. **Out of scope:** the solver, the dump writers, the geometry kernel
and the chart builders, except where their signatures force a shape on the UI (Section 10).

**Why now.** The file is 9,771 lines and the two builders are 3,459 of them (35.4%): `run_web` spans
`:3901-4800` (900 lines, 9.2%, 17 nested `def`s), `run_web_vis` `:7044-9602` (2,559 lines, 26.2%, 46
nested `def`s), 63 closures in total. Features added for the `vis` dump have had to be written twice or
not at all, and 3.4 shows the second option was taken in practice.

---

## 2. Evidence base

Assembled from static reading of the tree, from `pytest`, and from two performance reports already in
the repository. It contains **no** claim derived from a rendered browser session: nothing here is known
about how any page looks, what a user saw, or any pixel. Statements of the form "the user sees" are
absent on purpose; where a runtime symptom matters it is an open question (Section 9), not an assertion.

- **Structure and counts**: read or parsed from `server/poc_app.py` — spans, `def` counts, `state`
  attribute writes, call-site counts.
- **Behaviour already pinned**: `tests/test_poc_state.py`, `tests/test_poc_playback.py`,
  `tests/test_poc_mode_picker.py`, `tests/test_poc_mode_quiver.py`, `tests/test_poc_farfield.py`,
  `tests/test_poc_volume_arrows.py`.
- **Measured cost**: `reports/2026-11-15_02-49-32_volume-quiver-in-run_web___verification_report.md` and
  `reports/2026-11-15_02-56-40_Lazy_volume_colocation___final_verification_report.md`; the figures in
  5.4 come from these two files only.
- **Naming history**: commit `8bb4dfe`, "refactor: excise 'wavedude' naming, migrate to 'vis' (schema
  emfit.vis/2)", plus the surviving sites listed in Section 6.

Two caveats. Line spans are inclusive and measured on the current revision; a rebase invalidates them, so
re-derive rather than trust a stale number. The container used here has a 512 MB ceiling, which makes
`tests/test_dr43_pulse_writer.py` fail (needs ~4 GB): an environment artefact, not a regression (8.3).

---

## 3. What is actually wrong

The complaint was, in substance, "the UI is broken and there are two of it". Measurement supports the
second half without qualification and forces a much narrower claim about the first. Subsection order is
by cost, not by visibility.

### 3.1 Two applications, not one application with two modes

`main()` composes a page once (`page = reload_page(src)` `:9723`, `info = page["info"]` `:9724`) then
forks on the dump schema at `:9736` (`if _is_vis(info)`). The `vis` branch calls
`run_web_vis(info, args.host, args.port, args.fps, structure, structures, surface_dump=...)` at
`:9740-9750`; the other branch falls through station clamping and returns
`run_web(info, args.host, args.port, station, structure, structures)` at `:9767`.

First consequence: the fork is decided by the artefact, not the user. No runtime path switches a
running server between pages, and no flag selects the layout independently of the schema.

Second: the two share almost nothing. Each builds its own trame state — `get_server` `:4050-4055` and
`state, ctrl` `:4057` for `run_web`; `get_server` `:7264-7269` and `state, ctrl` `:7271` for
`run_web_vis`. `run_web` writes 12 `state` attributes, `run_web_vis` 39; the union is 50 and the
intersection is exactly one, `trame__title` (`:4058` against `:7275` and `:7387`). No `state` attribute
is written at module scope. The pages cannot address each other's state, which is why neither can host
the other's panels.

The closures are equally disjoint: the intersection of nested helper *names* is empty. The shared
surface is only 11 module-level helpers (`load_multifreq`, `load_structures`, `build_frequency_chart`,
`check_web_requirements`, `_structure_by_id`, `_chart_title`, `_cell_mm`, `_frequency_caption`,
`_absent_multifreq_reason`, `_structure_key`, `_structure_label`), against 26 module-level calls from
`run_web` and 45 from `run_web_vis`. The page logic lives in the closures, and no closure is shared.
Even the widget-capability probe is duplicated: `run_web` decides in an inline candidate loop
`:3948-4009`, assigned `:4009`; `run_web_vis` calls module-level `_probe_trame_ui()` (`:5103-5166`),
invoked `:7112`, assigned `:7131`.

### 3.2 Two data shapes behind one entry point

`load_any_dump` (`:588-671`) dispatches on the npz schema. `VIS_SCHEMAS` (`:139`) goes to `load_vis`
(`:615`, defined `:427-585`), returning roughly 45 keys; a surface dump is refused explicitly in the
same dispatcher. Everything else goes to `load_dump` (`:671`, defined `:181-270`), returning `path`,
`plane_ez`, `nstep`, `nx`, `ny`, `nz`, `cell_m` and either `e_centres` or `e_raw`.

These are not two variants of one record: `load_dump` is a stack of 2-D planes indexed by station,
`load_vis` a time series of 3-D snapshots plus derived series. The key sets barely overlap, so every
consumer branches. `_is_vis` (`:333`, body `return info.get("format") == "wavedude"` `:338`) appears 11
times: `:333` (definition), `:338`, `:3037`, `:3052`, `:3077`, `:3078`, `:3084`, `:3568`, `:5346`,
`:5375`, `:9736`. Two are dispatch (`:5375` in `reload_page`, `:9736` in `main`); the rest are panel and
document-composition branches deciding what to emit and what to omit. The shape of the data is thus
tested where the set of panels is chosen, in nine places.

### 3.3 The data is loaded more than once per session

`reload_page` (`:5318`) already loads everything — `load_any_dump` `:5335`, `load_record` `:5345`,
`load_multifreq` `:5370` — and returns `path`, `info`, `planes`, `multifreq`, `structure_id`, `record`,
`is_vis`. `PAGE_KEYS` (`:6879`) enumerates a page's contents, `apply_page` (`:6882`) installs them.

The builders then ignore parts of it and re-read from disk: `run_web` calls `load_record` again `:4068`
and `load_multifreq` again `:4113`; `run_web_vis` re-reads `multifreq` `:8120`. The legacy page does not
even receive the composed page object — `main` passes `info` and `station` to `run_web` `:9767`, while
`run_web_vis` (`:9740-9750`) gets the same `info` plus `surface_dump`. `reload_page` exists so that "boot
and reload cannot load a dump two different ways" (comment `:9719-9722`); the re-reads are that failure.

### 3.4 The features are split across the two pages

The defect a user is most likely to feel, asymmetric in both directions. The 3-D volume quiver exists
only on the legacy page: `_emit_volume_quiver_toggle` `:4439` called `:4713`, `_clear_volume_quiver`
`:4149`, `_show_volume_quiver` `:4161`, flag at `state.show_volume_quiver` written `:4107` and `:4279`.
The frequency and port-wave panels also exist only there (`:4540`, `:4575`, rendered `:4737`, `:4738`).
Everything added for the `vis` dump exists only on the new page: solver controls
(`_emit_solve_controls` `:8628`, mounted `:9305`), the time player (`_on_frame` `:8022`, `_play_loop`
`:8882`, `_on_play_toggle` `:8900`, player bar `:9338-9413`), the mode viewer, S-parameters, far field,
confidence, circuit netlist and load series (tab items `:9512-9542`, fallback stack `:9559-9569`).

Neither page is the good one: a `vis` dump cannot show the volume quiver, a plane dump cannot show the
solver controls or the player. Section 4 makes panel presence a property of the data instead.

There is a second duplication inside the new page alone: the right-hand panels are wired twice, through
`VTabs`/`VTab`/`VTabsWindow`/`VTabsWindowItem` (probes `:9462-9480`, tab items `:9512-9542`) and as a
plain stacked fallback (`:9559-9569`). The emitters are also forced eagerly during first render (warm-up
over `_load_s_params_panel`, `_load_far_field_panel`, `_load_confidence_panel` in the right column,
`:9414-9569`). Panel availability therefore depends on which trame widgets exist at runtime, and on a
cost paid whether or not the panel is ever shown.

### 3.5 The layout exists on one page only

The three-column layout is implemented only in `run_web_vis`: `with VRow(` `:9287`; left `VCol` `:9295`
(`flex: 0 0 230px`, min 200, max 280, `border-right`, solver controls `:9305`); centre `VCol` `:9306`
(`flex: 1 1 0`, min 240, `html_div` `:9317` holding `plotter_ui(mode="server", add_menu=False)` `:9330`,
player bar `VRow` `:9338`); right `VCol` `:9414` (`flex: 0 1 380px`, min 300, max 460, `border-left`,
readout `html_div` `:9422` with `structure_readout` `:9428`, `t_label` `:9429`, `mode_label` `:9430`,
`phase_label` `:9431`, `scale_label` `:9432`, `velocity_label` `:9433`, `velocity_note` `:9434`, panels
to `:9569`, `handles["view"] = view` `:9571`).

`run_web` has no `VRow` or `VCol` at all: `VContainer` `:4695` holding `html_div` `:4696` (flex column,
100vh), banner `:4702`, row div `:4703` (cut sliders `:4709`, quiver toggle `:4713`), plotter div
`:4723` (`plotter_ui` `:4726`), panel div `:4731` (frequency `:4737`, port wave `:4738`, station label
`:4739`). The whole legacy layout is 45 lines, `:4695-4739`, and none of it composes with the new one;
`VRow` (`:6914-6927`) and `VCol` (`:6930-6943`) are module-level and importable, so this is not scoping.

### 3.6 63 closures, no page context

Because state (3.1) and helpers (3.1) are disjoint, all shared context in a builder is a closure over a
local: 17 such destinations in `run_web`, 46 in `run_web_vis`. A panel emitter written for one page
cannot be called from the other without being lifted out of the closure it was written inside — the
mechanical reason 3.4 happened. Putting the quiver on the `vis` page means rewriting
`_emit_volume_quiver_toggle` (`:4439`) and its helpers (`:4149`, `:4161`) against a different state
object and a different redraw path.

### 3.7 Two corrections to the record

The brief that commissioned this document contained two claims the code does not support. Both are
corrected here, because a plan built on them would target the wrong defect.

**Correction 1: "Switch View drops you into a broken page" is not what the code does.** The control is
`VBtn("Switch view")` `:4646`, in the toolbar `:4627`, guarded `:4644`, wrapped `try/except`
`:4649-4656`. Its handler is `_on_toggle_view` `:4223`, registered `@ctrl.set("toggle_view")` `:4222`.
It toggles `state.view_mode` between `"port"` and `"volume"` (`:4224`), updates the label (`:4225-4230`),
calls `_redraw()` (`:4231`) and `view_handle.update()` (`:4235`). It does not rebuild the layout, reload
the dump or restart the server; page identity is the schema fork `:9736`/`:9767`, so no in-page control
can change which application runs. If the `"port"` branch renders badly, that is a real and separate bug
in the view code reached from `_redraw` (`:4231`), not a page-structure problem. Whether it does is
`unknown` to this document: the code was read, not the browser. It is Q1 in Section 9.

**Correction 2: "the `wavedude` naming has been excised" is not true and cannot be made true.** The
rename shipped for identifiers (commit `8bb4dfe`), but `VIS_LEGACY_SCHEMAS` `:138` deliberately keeps
`("emfit.wavedude/1", "emfit.wavedude/2")`, and the comment `:133-137` says why: the only permitted
survivors, schema literals embedded in stored data rather than identifiers, never to be renamed. Nine
sites remain in `poc_app.py` (`:133`, `:136`, `:137`, `:138`, `:335`, `:338`, `:485`, `:647`, `:3077`),
four test assertions pin the old value, three data files store it, and `artifacts/verify_wd.py` already
refers to symbols that no longer exist (`WAVEDUDE_SCHEMA` `:92`, `load_wavedude` `:128`,
`run_web_wavedude` `:153`; docstring `:1`, comment `:33`). Section 6 lists every site with its action,
because a plan assuming a full purge will stall on a schema literal that must not move.

---

## 4. Target architecture

One page builder, one state object, one server, and panels whose presence is a function of the loaded
data. Names below are proposals, not agreed API, and nothing here is callable.

### 4.1 One builder, two layouts

A single entry point takes the composed page and builds the layout. `main` keeps its schema fork only
until Phase 7; the fork's job becomes supplying `fps` versus `station`, which is CLI plumbing, not page
identity. The three-column skeleton `:9287-9435` is lifted out of `run_web_vis` verbatim in Phase 4 and
parameterised: left column solver controls when the data supports solving, centre column the plotter and,
when the data has a time axis, the player bar `:9338-9413`, right column the readout and panels. The
legacy 45-line layout `:4695-4739` is deleted, not preserved beside it: its two panels (`:4540`, `:4575`)
become ordinary right-column panels and its quiver toggle (`:4439`, `:4713`) a centre-column control.

### 4.2 A `PageModel` instead of `info`

Builders stop receiving `info` and receive a model in two parts: fields common to every dump, and an
explicit availability section. Proposed groups (illustrative, not exhaustive):

| group | contains | present for |
| --- | --- | --- |
| identity, geometry | `path`, `schema`, `format`, `structure_id`, `nx`, `ny`, `nz`, `cell_m`, cell centres or mesh | every dump |
| time, planes | `nstep`, `fps`, current frame index; `plane_ez`, station index | dumps with a time axis; the plane fields for plane dumps |
| series | `multifreq`, S-params, far field, confidence, load series | `vis` dumps, when the side files exist |
| record | `load_record` output | when a record file is found |
| availability | the flags in 4.3 | every dump, always |

The point is not tidiness: `_is_vis` stops being what panels branch on. It survives at most in the loader
dispatch (`load_any_dump`, `:588-671`) and, until Phase 3 completes, in `main`'s plumbing; the seven
builder-side branches (`:3037`, `:3052`, `:3077`, `:3078`, `:3084`, `:3568`, `:5346`) become flag reads.

### 4.3 Availability flags, computed once

Computed by the loader, once, never re-derived in the builder. Names parallel the emitters they gate:

| flag | gates | evidence for the condition |
| --- | --- | --- |
| `has_time_axis` | player bar, frame scrubbing | `_on_frame` `:8022`, `_play_loop` `:8882` |
| `has_volume` | 3-D volume quiver toggle | `_emit_volume_quiver_toggle` `:4439` |
| `has_planes` | station slider, plane viewer | `plane_ez` in `load_dump` `:181-270` |
| `has_multifreq` | frequency and port-wave panels | `load_multifreq` `:5370`, `_absent_multifreq_reason` |
| `has_s_params` | S-parameters panel | `_emit_s_params_panel` `:8782` |
| `has_far_field` | far-field panel | `_emit_far_field_panel` `:8818` |
| `has_confidence` | confidence panel | `_emit_confidence_panel` `:8855` |
| `can_solve` | solver controls | `_emit_solve_controls` `:8628`, `solve_argv` `:5200` |
| `has_netlist` | circuit netlist | `_emit_circuit_netlist` `:8445` |

A panel whose flag is false is not built at all: not hidden, not empty. That removes the eager warm-up
(`:9414-9569`) for every dump lacking the panels, and makes the fallback stack (`:9559-9569`)
unnecessary: tabbed path and stacked path render the same list, so there is one list and one renderer.

### 4.4 One page context instead of 63 closures

Replace the closures with one object per page holding the state handle, controller handle, model, view
handle, redraw function and panel list; panel emitters become module-level functions taking that context.
This is what makes 3.4 reversible: moving the quiver to the `vis` page becomes adding an emitter to a list
rather than rewriting three closures against a foreign state object. `VRow` (`:6914-6927`) and `VCol`
(`:6930-6943`) already show the target shape: importable, side-effect free, used where needed.

### 4.5 One widget probe

Fold the inline loop `:3948-4009` onto `_probe_trame_ui()` (`:5103-5166`), which is module-level and
answers the same question. Answer once per process, before either layout is built, and pass the result
in the page context; the fallback stack `:9559-9569` then keys off that one answer instead of local
probes.

---

## 5. The data pipeline

### 5.1 Present dispatch

`load_any_dump` (`:588-671`) is the only entry point to the two shapes and is correct in one respect
worth preserving: schema decides the loader, in one place.

| schema class | branch | loader | returns |
| --- | --- | --- | --- |
| `VIS_SCHEMAS` (`:139`) | `:615` | `load_vis` (`:427-585`) | ~45 keys: time series, derived series, side-file data |
| surface dump | refused in the dispatcher | none | explicit refusal |
| anything else | `:671` | `load_dump` (`:181-270`, `e_raw=True`) | `path`, `plane_ez`, `nstep`, `nx`, `ny`, `nz`, `cell_m`, `e_centres` or `e_raw` |

### 5.2 The model is built here, once

`PageModel` is produced by `load_any_dump`, beside the dispatch (`:615` and `:671`), so availability (4.3)
is decided where the keys are known. Builders never see a raw `info`.

### 5.3 Reload is the only load path

`reload_page` (`:5318`) is the single composition point (`load_any_dump` `:5335`, `load_record` `:5345`,
`load_multifreq` `:5370`). After Phase 6 it returns a `PageModel` and the re-reads at `:4068`, `:4113`,
`:8120` are deleted; `PAGE_KEYS` (`:6879`) and `apply_page` (`:6882`), the reload/build contract, move too.

### 5.4 What stays lazy, and why (measured)

Eager loading of the volume data was measured and rejected once. Colocating it eagerly in `run_web` cost
954.9 ms mean (`reports/2026-11-15_02-49-32_volume-quiver-in-run_web___verification_report.md:96`),
+949.4 ms, 173.40x (`:97`; per-run 1024.4 / 895.1 / 945.2 ms, `:93-95`). The lazy stash with `e_raw=True`
costs 52.484 / 51.065 / 42.861 ms
(`reports/2026-11-15_02-56-40_Lazy_volume_colocation___final_verification_report.md:18`), and the warm
mesh build is 845.007 ms of which 835.026 ms is `edge_to_cell_centres` (`:21`, `:22`); peak RSS moved
33.1 to 129.7 to 148.1 MB (`:23`).

The rule: a flag (`has_volume`, `can_solve`) may be computed eagerly because it is cheap; the payload
behind it may not be. Loading stays behind the first use that needs it, and the model records *that the
payload exists*, not the payload. Any proposal to "just load everything in the model" must beat
949.4 ms with a measurement, not an argument.

---

## 6. Naming

`wavedude` survives in four kinds of place, each needing a different action. Conflating them is how a
rename campaign fails.

| site | kind | action |
| --- | --- | --- |
| `poc_app.py:138` `VIS_LEGACY_SCHEMAS` | schema literals in stored data | **keep forever**; comment `:133-137` forbids renaming |
| `poc_app.py:133`, `:136`, `:137` | comments explaining the exemption | keep, point at this document |
| `poc_app.py:335` | comment on the serialized format value | update when the writer (`:485`) changes |
| `poc_app.py:338` | reader of a serialized value | accept both spellings before the writer moves |
| `poc_app.py:485` | writer in `load_vis` | new spelling, after the reader accepts both |
| `poc_app.py:647` | stderr prose | rename (text only, no data) |
| `poc_app.py:3077` | format value in the state dump | new spelling; dump reader accepts both |
| `tests/test_poc_playback.py:453`, `:454`, `:459`; `tests/test_poc_state.py:446` | assertions on the stored value | assert new **and** accepted legacy value |
| `artifacts/verify_wd.py:1`, `:33`, `:92`, `:128`, `:153` | already broken script | delete or repair in its own commit |
| `state.json:31`, `:320`; `build/wavedude_state.json:31`, `:320`; `build/wd2.json:31`, `:320` | stored data | do not touch |
| `artifacts/vis_run_1500.json:199`, `:205`; `smoke_A.json:203`, `:207`; `smoke_B.json:203`, `:207`; `vis_run_B_100ohm.json:201`, `:207` | recorded `--wavedude-dump` argv | do not touch: records of what was run |
| `docs/visualizer_architecture.md:96`; `docs/GEN12_HANDOFF_WARS.md:243`, `:245`, `:249`, `:259`; `docs/GEN12_HANDOFF_STATE.md:310` | prose | rename, or mark historical in place |
| `build/wavedude_state.json` (path), `reports/*wavedude*` (filenames) | artefact names | keep; renaming breaks the records that cite them |

The resolving rule: **serialized values and artefact names are data and do not rename; identifiers,
prose and user-facing text do.** A value already on disk needs a reader accepting both spellings for at
least one release before its writer changes, or old dumps stop loading — which is how
`artifacts/verify_wd.py` ended up referring to `WAVEDUDE_SCHEMA` (`:92`), `load_wavedude` (`:128`) and
`run_web_wavedude` (`:153`) after those symbols were excised: the best evidence that the rename shipped
half-done. The live solver flag is already `--vis-dump` (`evidence/termination/run_build_A.py:3153`), so
the CLI surface is renamed and the rest is the table above.

---

## 7. Migration plan

Each phase ships alone and is gated by Section 8; a phase that cannot be gated has been split. Ordering is
by risk: tests first, deletion of the legacy layout only after the phase proving the shared one equivalent.
- **Phase 0 — characterise before touching anything.** No production change. Confirm the six UI test files
pass in a supported container and record that `tests/test_dr43_pulse_writer.py` fails only on the 512 MB
ceiling. Done when a reviewer can point at a green run and the one known environment failure. Risk: none.
- **Phase 1 — golden page documents.** Capture state dumps for one dump of each schema via `--dump-state`
(`main` `:9726-9732`), stored under the test tree, not under `build/`. Done when both schemas produce a
document and it is stable across two runs. Risk: size; keep one per schema.
- **Phase 2 — `PageModel` and flags.** Introduce the model beside `info`, build it inside `load_any_dump`,
assert both loaders yield it with correct flags. No UI change. Done when every flag in 4.3 is covered by
a test per schema. Risk: low, additive.
- **Phase 3 — panels read flags, not `_is_vis`.** Replace the builder branches (`:3037`, `:3052`, `:3077`,
`:3078`, `:3084`, `:3568`, `:5346`) with flag reads, leaving `:5375` and `:9736` as dispatch. Behaviour
must be identical, gated by Phase 1 goldens. Risk: medium — an omission becomes a missing panel, which
the goldens catch.
- **Phase 4 — lift the layout.** Move `:9287-9435` into a module-level builder parameterised by the page
context, leaving `run_web_vis` a thin caller. Nothing renders differently; the diff is a move plus an
argument list. Done when the tabbed path (`:9512-9542`) and the stacked path (`:9559-9569`) still render
the same panels and the goldens are unchanged. Risk: medium, mechanical.
- **Phase 5 — one widget probe.** Fold `:3948-4009` onto `_probe_trame_ui()` (`:5103-5166`), computed once
per process. Done when both pages build from the same probe result. Risk: low.
- **Phase 6 — one server, one state, one load.** Single `get_server`/`state, ctrl` construction; delete the
re-reads `:4068`, `:4113`, `:8120`; make the legacy page receive the composed page object (`:9767` gains
the argument `:9740-9750` already has). Done when `reload_page` (`:5318`) is the only caller of
`load_record`/`load_multifreq` in a web session, checked by grep and a test. Risk: high — touches both
entry points, so do it after Phase 4 removed the layout duplication.
- **Phase 7 — panels become data.** Move the quiver (`:4439`, `:4149`, `:4161`, `:4713`) and the
frequency/port-wave panels (`:4540`, `:4575`, `:4737`, `:4738`) into the shared panel list, gated by
`has_volume` and `has_multifreq`; then delete `:4695-4739`. Done when one dump per schema renders every
panel its flags allow and none they forbid. Risk: highest — this changes what a plane-dump user can do,
so it ships with all of Section 8.
- **Phase 8 — naming and the broken artefact.** Apply Section 6 in order: reader accepts both, writer
changes, tests assert both. Separately repair or delete `artifacts/verify_wd.py`. Done when no
module-level reference to a renamed symbol remains and `:138` is untouched. Risk: low, but not zero: do
not bundle it with Phase 7.

---

## 8. Test strategy and gates

### 8.1 What "no behaviour changed" has to mean

The repository already holds the pattern to copy. `tests/test_poc_volume_arrows.py` `:495-519` computes
one quantity by two routes and asserts they agree: `n_points` and `n_cells` equal, then `allclose` with
`rtol=0.0`, `atol=1e-12`. That is the shape of proof this migration needs: two implementations, one
answer, tolerance not widened to pass.

A refactor phase passes when (1) the six UI test files pass — `tests/test_poc_state.py`,
`test_poc_playback.py`, `test_poc_mode_picker.py`, `test_poc_mode_quiver.py`, `test_poc_farfield.py`,
`test_poc_volume_arrows.py`; (2) the Phase 1 goldens are byte-identical for every field the phase did
not intend to change, or differ only in the declared way, documented in the commit; (3) nothing in the
diff widens a tolerance, skips a test, or fits a constant to observed output. A numeric change is a
behaviour change needing its own justification. No test here asserts anything about appearance:
layout equivalence is structural (same panels, same order, same flags), never visual.

### 8.2 Gates per phase

| phase | gate |
| --- | --- |
| 0 | suite green except the known environment failure |
| 1 | goldens stable across two consecutive runs, both schemas |
| 2 | one test per schema asserting every flag in 4.3 |
| 3 | goldens unchanged; no `_is_vis` branch left outside loader/dispatch |
| 4 | tabbed (`:9512-9542`) and stacked (`:9559-9569`) paths render the same panels |
| 5 | one probe result per process, identical for both pages |
| 6 | `reload_page` is the only caller of `load_record`/`load_multifreq` |
| 7 | full suite; one dump per schema renders exactly its flagged panels |
| 8 | no dangling symbol reference; `:138` unchanged |

A gate is a check a reviewer performs. A phase with an unmet gate is not merged.

### 8.3 The environment failure that is not a regression

`tests/test_dr43_pulse_writer.py` fails in the 512 MB container used here; it needs roughly 4 GB. It is
unrelated to the UI and to this plan, and every phase report must say so explicitly, because a red suite
beside a UI refactor will otherwise be read as a regression.

---

## 9. Open questions for Gen 13 and the PI

- Q1. **What happens when "Switch view" (`:4646`, handler `:4223`) is used on a real dump?** The code
toggles `state.view_mode` and redraws (`:4224`, `:4231`, `:4235`) and does nothing else. If the `"port"`
branch is visibly wrong, the bug is in the view code reached from `_redraw` (`:4231`), not in page
identity (3.7). No browser was involved in this document, so the symptom is `unknown` and must be
supplied before that bug is scoped.
- Q2. **Should the format sentinel change at all?** `:485` writes `"format": "wavedude"`, `:338` reads it.
Safe only with a two-spelling reader (Section 6). Is the cosmetic gain worth a serialization migration,
or do `:485`/`:338`/`:3077` join `:138` on the do-not-rename list?
- Q3. **Does a plane dump still need a supported page?** Phase 7 removes the legacy layout `:4695-4739`
and re-hosts its two unique panels. If plane dumps are being retired, retiring the page is cheaper.
Whether any plane dump is still expected to open is `unknown` here: a product question, not a code one.
- Q4. **Which panels may cost what?** Section 5.4 settles one argument with a measurement. A per-panel
latency budget, or an explicit "panels may be lazy" rule, would settle the rest mechanically.
- Q5. **How is availability declared when side files are missing rather than absent by schema?** The `vis`
page models this for multifreq (`_absent_multifreq_reason`) but not uniformly for S-parameters, far field
and confidence. Is "flag false plus a reason string" the contract?
- Q6. **Is the 4 GB ceiling available in CI for `tests/test_dr43_pulse_writer.py`?** If not, that test
should carry a skip-with-reason rather than a permanent red (8.3).
- Q7. **Keep both `VTabs` paths?** Tabbed (`:9512-9542`) and stacked (`:9559-9569`) are maintained in
parallel today. Section 4.3 makes the fallback unnecessary; deleting it is a behaviour change for
whichever trame versions lack `VTabs`, so it needs a decision.
- Q8. **Who owns the Phase 1 goldens?** They are the only mechanical defence against Phase 3 and Phase 7
regressions. Unowned, they become stale fixtures that fail for the wrong reason.

---

## 10. Non-goals

- **No change to the solver, dump writers or geometry kernel.** Section 5.4 quotes their costs only to
  constrain the UI.
- **No new UI framework, no migration off trame.** The duplication in 3.1 is in this codebase, not
  caused by the toolkit.
- **No visual redesign.** The layout `:9287-9435` is adopted as-is; 4.1 moves it, it does not restyle it.
- **No claim about appearance and no screenshot.** Nothing here came from a rendered page.
- **No renaming of schema literals or recorded artefacts** (`:138`, `state.json:31`,
  `artifacts/*.json` argv fields). Section 6 says which `wavedude` occurrences are data.
- **No deletion of `run_web` before Phase 7's gate passes**, and no bundling of the naming work (Phase 8)
  into the layout work.
- **No performance work.** The 949.4 ms figure is a design constraint, not a task.
- **No fix for Q1 in code.** The `"port"` branch symptom is diagnosed before it is touched.
