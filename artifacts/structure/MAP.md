# MAP — `server/poc_app.py` (13,465 lines) and its two leaves

Structural map of the PoC viewer, measured (not estimated). Everything here is
reproducible from the files in this directory:

| file | what it is |
|---|---|
| `analyze.py` | throwaway AST analyzer that produced every number below |
| `functions.tsv` | 315 defs x {module, qual, lines, args, decorators, kind, layer class, state/ui refs} |
| `functions_by_size.tsv` | same rows, sorted by size |
| `classes.tsv` | the 4 classes |
| `state_keys.tsv` | all 61 `state.<key>` uses with write sites and read sites |
| `_digest.txt` | 722-line human digest (sections, buckets, call bases, dup blocks) |
| `_data.json` | full raw model, machine-readable |

Scope: `server/poc_app.py` 13,465 lines / 621,407 B; `server/um3k_panels.py` 499
lines; `server/um3k_context.py` 228 lines; `server/web_assets/` holds exactly one
file (`keyboard.js`).

---

## 1. The three modules

| module | lines | role | imports the others? |
|---|---|---|---|
| `server/poc_app.py` | 13,465 | everything: loader, numpy-only state dump, pyvista scene, matplotlib charts, two trame shells, CLI | imports `um3k_context` + `um3k_panels` (dual idiom, `poc_app.py:76-90`) |
| `server/um3k_panels.py` | 499 | layout columns only (`build_center_panel` 50-231, `build_right_panel` 307-499, `build_left_panel`, `_emit_*`, `RIGHT_TABS`); takes only `ctx` | no (leaf) |
| `server/um3k_context.py` | 228 | `LoadedDump` (39-71), `Available` (87-143, frozen dataclass), `PageContext` (160-228, 8 methods) + registry helpers (`register`, `register_handle`) | no (leaf) |

`um3k_context` intentionally re-declares literals that also exist in `poc_app`
(`PLANE_KEY`, `VOLUME_KEY`, `VOLUME_RAW_KEY`, `VIS_FORMAT`, `VIS_FORMATS`,
`FALLBACK_SRC` at poc_app 96/100/106/160/161/3138) — a test pins the copies.

There are only **4 classes in the whole tree**: `SolveJob` (poc_app 9640-9724, 7
methods, no bases) and the three context dataclasses. Everything else is a
function: **196 module-level functions in `poc_app`** plus 119 nested ones.

---

## 2. Size and layer accounting

Binary classification by call basis + names, over module-level defs only
(the honest denominator for "what would move"):

| layer | defs | lines | share of def lines |
|---|---|---|---|
| engine (numpy/json/pathlib only) | 154 | 5,040 | 37.4 % |
| UI / trame (`ui`) | 14 | 4,805 | 35.7 % |
| render (pyvista) | 28 | 2,554 | 19.0 % |
| glue not inside any def (docstring, imports, constants, blank) | — | ~1,066 | 7.9 % |

Counting nested defs too (parents double-counted): ui 72/7,810, render 38/2,751,
engine 205/5,713.

**The two shells are the file.** 14 UI defs / 4,805 lines, of which
`run_web_vis` (9894-13287, 3,394) + `run_web` (5922-6774, 853) + `main`
(13290-13461, 172) = 4,419 lines = 92 % of all UI lines and 33 % of the file.

**The separation is already clean where it matters**: engine-class functions
that touch `state.*` or any UI name = **zero**. The 61 `state` keys are read and
written exclusively from UI/trame code (plus one `_volume_quiver_callback`
closure). That is why a layer split is mechanically possible: the numpy half is
already UI-free.

250-line buckets confirm it as a spatial fact: the first ~4,500 lines are
engine-only except `build_frequency_chart`/`build_port_series_chart`; engine
code stops at 9,891; from 9,894 to 13,465 the file is UI and almost nothing else.

---

## 3. The eleven sections (contiguous, chosen to cut only between definitions)

| # | lines | lines | contents |
|---|---|---|---|
| S1 | 1-201 | 201 | module docstring, imports (59-75), um3k import idiom (76-90), constants (93-192), `_resolve` (195) |
| S2 | 203-975 | 773 | dump loaders: `load_dump` 203, npz helpers 330-368, `_vis_colour_limit`, `_frame_*`, `_load_series_block` 434, `load_vis` 520 (203), `load_any_dump` 725, label builders 811-959, `_page_source_text` 882 |
| S3 | 979-1725 | 747 | record + sweep resolution: `_as_float`, `_record_candidates` 987, `load_record` 1081, `_multifreq_candidates` 1139, `_absent_multifreq_reason` 1182, cells parsing 1264-1331, structure registry 1347-1517, `_git_head_short` 1520, `load_multifreq` 1622 |
| S4 | 1729-2500 | 772 | chart series + chart renderers: frequency rows 1831, `build_frequency_chart` 1932 (145), port waves 2149-2326, `build_port_series_chart` 2329, artefact path helpers 2464-2498 |
| S5 | 2501-4570 | 2,070 | state blocks and page dicts: `_field_dump_block` 2501 … `build_state_dump` 3337, `_station_axis_mm` 3407, `_geom_mm` 3474, board/page dicts 3611-3771, `_plane_layout` 3774, `_volume_grid_dims` 4011, `_cut_layout` 4069, `build_cut_sheets` 4217, `_volume_cut_sheets` 4286, `_marker_cut_relation` 4320, `_print_vis_keys` 4403, `print_keys` 4524 |
| S6 | 4572-5680 | 1,109 | plane-page render layer (pyvista): `build_grid` 4572, `create_plotter` 4645, `_add_plane_marker` 4685, `_add_markers` 4769, `plane_bar_args`/scalar bars 4920-4977, `_draw_volume_scene` 4980 (248), extents/outlines 5245-5458, `_draw_scene` 5461 (207), `check_web_requirements` 5683 |
| S7 | 5683-6774 | 1,092 | plane-page UI glue: `_cut_axis_counts`, `_init_cut_state`, `_scene_planes`, `_redraw_scene`, `_on_cut_change`, `_emit_cut_sliders` (5720-5919) and `run_web` (5922-6774) |
| S8 | 6777-8630 | 1,854 | animation-page scene + tools: banner at 6777, `_vis_frame_time_ns`, `_vis_phase_text`, `_vis_grid` 6836, `_vis_geometry` 6889 (283), `_probe_trame_ui` 7174, `solve_argv` 7271, `solve_netlist_file` 7386, `reload_page` 7403, then the mode viewer 7513-8601 (`cross_section_mesh` 7525, `_mode_view` 7958 (170), `mode_view` 8130, mode text helpers 8203-8500, `_mode_quiver_arrows` 8523) |
| S9 | 8635-9891 | 1,257 | volume layer + solve job + frame glue: `_volume_arrows` 8635, `_volume_abs_grid` 8798 (144), player plan 9007, clim 9083-9412, `_volume_frame_grid` 9415, `_volume_quiver_mesh` 9485, `_volume_quiver_callback` 9562, `SolveJob` 9640-9724, `apply_page` 9732, `VRow`/`VCol` 9764/9780, `build_far_field_panel` 9796 |
| S10 | 9894-13287 | 3,394 | `run_web_vis` — one function, 8 args, 118 `state` references, ~55 nested closures |
| S11 | 13290-13465 | 176 | `main` (172) with argparse 13336-13375, main guard 13464-13465 |

Sum 13,445 + ~20 blank separator lines = 13,465. Every cut falls between two
definitions, so the sections can be moved without touching a body.

---

## 4. The one page model (and the two shells)

`reload_page` (7403) reads everything a page shows off disk into one plain dict
(`info`); `_structure_registry`/`load_structures` resolve which structure is
open; `um3k_context.PageContext(info, available, registry, handles)` is the
snapshot the panel builder is handed; `handles` is a plain dict of widget
references registered with `ctx.register_handle(...)`; `state` is the trame
state object.

`main` (13290) is now a **single dispatch**: it reads the page through
`reload_page` and always opens `run_web_vis`, whichever schema came back
(`tests/test_poc_dispatch.py` asserts a field dump is *not* sent to `run_web`).
`run_web` survives only because tests boot it.

Construction sites (the two independent trame builds):

| | `run_web` (5922) | `run_web_vis` (9894) |
|---|---|---|
| server | `get_server(` 6071/6076 | `get_server(` 10170/10175 |
| state/ctrl | `state, ctrl = server.state, server.controller` 6078 | 10177 |
| plotter | `create_plotter(info)` 6068 | `pv.Plotter(off_screen=True)` 10081 |
| context | — (no `PageContext`) | `ctx = um3k_context.PageContext(...)` 10324 |
| layout | `with SinglePageLayout(server) as layout:` 6584 | 13142 (+ `handles["title_setter"]` 13148) |
| start | `server.start(host, port, open_browser=False)` 6757 | same, via `main`'s call |

Controller surface — 24 decorated nested functions (`_digest.txt:698-722`):
`@ctrl.set` `toggle_view`, `cut_y`, `cut_z`, `show_volume_quiver`, `structure`,
`station`, `mode_toggle`, `step_back`, `step_fwd`, `top_view`, `side_view`,
`mode_view_toggle`, `netlist_toggle`, `play_toggle`, `solve_start`;
`@ctrl.trigger("kbd_shortcut")` 12615; `@state.change` `frame`, `mode_choice`,
`volume_clim_mode`, `show_quiver`, `show_load_plane`, `show_port_plane`.

Async machinery inside `run_web_vis`: `_watch_solve` 12687 (the one poll driver),
`_start_watch` 12710, `_poll_solve` 12721, `_run_job` 12839 (worker thread),
`SolveJob` (9640) as the process handle. `run_web_vis` blocks only at
`server.start`; every handler returns immediately (`tests/test_poc_playback.py`).

---

## 5. State contract

61 distinct `state.<key>` names, 224 `state.` references **inside
`poc_app.py` alone**; 42 of the 61 keys are written from more than one function.

| key | writes | reads | writer funcs | reader funcs |
|---|---|---|---|---|
| `mode` | 2 | 19 | 2 | 11 |
| `frame` | 2 | 11 | 2 | 9 |
| `solve_status` | 12 | 0 | 3 | 0 |
| `cut_z`, `cut_y` | 3 | 7 | 3 | 6 |
| `playing` | 5 | 4 | 4 | 4 |
| `station` | 4 | 4 | 3 | 3 |
| `view_mode` | 3 | 5 | 3 | 4 |
| `play_label` | 5 | 0 | 4 | 0 |
| `mode_view_caption`, `mode_view_label`, `mode_choice_items` | 3-4 | 0-1 | 3-4 | 0-1 |

Shape of the coupling: almost every key is written by the shell that owns it and
read by *both* its handlers and the shared `_redraw_scene`/`_show` callbacks.
`_redraw_scene` (5783) alone reads `state.cut_y`, `state.cut_z`,
`state.view_mode`, `state.station`. That function is the single widest reader,
and it is UI-layer, not engine.

---

## 6. Duplication — measured, including the negative results

Exact duplicate bodies (normalised, ≥8 lines): **3 pairs**, all two-liners:

1. `run_web._on_cut_y` (6246-6259) ≡ `run_web_vis._on_cut_y` (10426-10439) — 13 normalised lines;
2. `_on_cut_z` in the same two shells (6262-6275 ≡ 10442-10455) — 13;
3. the two `_redraw` closures that call `_redraw_scene(plotter, info, planes, state, _show_volume_quiver, station_label=False)` (6220-6222 / 10393-10405 / 10496-10505) — 9.

Repeated 4-line blocks in ≥3 functions:

| block | functions |
|---|---|
| `view_handle = handles.get("view") / if view_handle is not None: / try: / view_handle.update()` | 8 |
| `try: view_handle.update() / except Exception as exc: print("[poc_app] view update skipped…")` | 8 |
| `if view_handle is not None: / try: / view_handle.update() / except …` | 8 |
| `value, / state, / n_j, / n_k,` (the `_on_cut_change` call tail) | 6 |
| `) / pre_cls = getattr(html_widgets, "Pre", None) / if pre_cls is not None: / pre_cls(` | 6 |
| `density="compact", hide_details=True, classes="mb-1",` | 6 |
| `img_cls = getattr(html_widgets, "Img", None) / if image and img_cls is not None: / img_cls(` | 5 |
| `type="number", density="compact"…` | 4 |
| `try: number = float(value) / except (TypeError, ValueError): / return None` | 4 |
| `position="upper_left", font_size=10, color="black",` | 4 |

Structural duplication (whole subsystems built twice):

* the `_cut_layout`-driven cut slider + cut controller set exists on both shells
  (5720-5920 legacy vs 10426-10509 animation);
* the centre/right panels are built by one module but called from **both**
  pages (`um3k_panels` import at poc_app 83/90; used inside `run_web` ~6600s and
  `run_web_vis` ~12463) — so the panel layer is already shared and this is the
  pattern to copy;
* `run_web` (853 lines) re-implements a whole page the unified shell also serves.

**Negative result, stated plainly**: a near-duplicate detector (token-ratio
≥ 0.72 on functions ≥ 25 lines) found **zero** pairs. The duplication in this
file is small-block repetition and one whole-page reimplementation, not cloned
large functions. Any claim that "the two shells are near-identical" is false.

---

## 7. Dead code and reachability

Three independent metrics, all zero-or-explained:

* never referenced by loose name or call: **0**;
* unreachable from roots (`main`, `print_keys`, tests): **0**;
* referenced by the *call* graph only but bound as a value (widget callback
  table): 8, all legitimate (`_run_config`, `_mesh_and_geometry`, `_project`,
  `_emit_station_readout`, `_action`, `_emit_circuit_tab`, `_run_job`,
  `_emit_modes_tab`).

Reachable **only from tests** — these are the real dead weight, 1,010 lines:

| function | lines | at |
|---|---|---|
| `run_web` | 853 | 5922 |
| `run_web_vis.<locals>._on_solve_start` | 104 | 12853 |
| `run_web_vis.<locals>._on_kbd_shortcut` | 23 | 12616 |
| `choose_entry` | 12 | 146 |
| `SolveJob.__init__` | 8 | 9655 |
| `PageContext.__init__` | 10 | 168 |

(the two closures are reached in production through trame's registration, not
through a Python call, which is why a name graph calls them test-only — see the
caveat below.)

**Caveat this map must carry**: the reachability graph is name-based. The 24
decorator-registered controllers (`@ctrl.set/@ctrl.trigger/@state.change`) are
reachable *only* through trame, so any "unused" verdict on a nested function must
be checked against the registry list at `_digest.txt:698-722` before acting.

---

## 8. External contract (what a split must not break)

**No Python module imports `poc_app`.** It is driven only as a CLI + as an
importable leaf by tests:

* CLI: `python3 server/poc_app.py --input …` from `scripts/run_reference_sim.py:84/:398/:466`; boot command used by the repo is
  `PYTHONPATH=<repo>:<repo>/.venv/lib/python3.12/site-packages python3 server/poc_app.py`;
  `--list-keys` and `--dump-state PATH` are numpy-only paths (no pyvista, no trame).
* Prose references: `evidence/termination/run_build_A.py:3159`, `reports/*.md`.
* `scripts/em_reading_pack.sh:27-33` slices `server/poc_app.py` by **fixed line
  ranges**: 3512-3625, 6202-6299, 7396-7446, 7912-7947, 8240-8300, 8386-8469,
  8540-8580. (These ranges no longer match their labels even today — 3512 falls
  inside `_geom_mm.<locals>._num`, 7396 inside `solve_netlist_file` — so the doc
  pack is already stale and must be re-anchored by symbol, not by line number.)
* Tests import `poc_app` as a top-level module (`server/` on `sys.path`) and use
  it three ways:
  1. **direct calls/attributes** — `load_dump`, `load_vis`, `main`, `PLANE_KEY`,
     `VOLUME_KEY`, `VIS_FORMAT`, `VIS_SCHEMA`, `DEFAULT_INPUT/HOST/PORT/FPS`,
     `load_dump.__kwdefaults__`;
  2. **`monkeypatch.setattr(poc_app, name, …)`** — `MULTIFREQ_BY_STRUCTURE`,
     `SINGLE_RUN_BY_STRUCTURE`, `SOLVER_SCRIPT`, `LIVE_DUMP`, `mode_view`,
     `reload_page`, `print_keys`, `run_web_vis`, `run_web` (test_poc_playback
     616/617/778/779/1319/1320/1545; test_poc_dispatch 89-98);
  3. **source parsing** — `tests/test_um3k_panels.py:185-195` asserts there is
     exactly **one top-level `run_web_vis` in `server/poc_app.py`** and 198-230
     then require the 3-column `VRow` (left `VCol` = one `build_left_panel(ctx)`,
     centre = `build_center_panel(ctx)`, right = `build_right_panel(ctx)`) to be
     *inside that function's body*.

Boot tests that must keep passing after any move:
`tests/test_animation_volume.py` (patches `trame_server.Server.start`, calls
`app.run_web_vis(info, "127.0.0.1", 8999, fps=FPS)`),
`tests/test_poc_playback.py`, `tests/test_poc_volume_arrows.py`,
`tests/test_poc_state.py` (subprocess `--dump-state`),
`tests/test_poc_dispatch.py`, `tests/test_um3k_panels.py`,
`tests/test_volume_colocation.py`.

---

## 9. Hot spots (top of `functions_by_size.tsv`)

| lines | function | at | args | state refs |
|---|---|---|---|---|
| 3,394 | `run_web_vis` | 9894 | 8 | 118 |
| 853 | `run_web` | 5922 | 6 | 17 |
| 283 | `_vis_geometry` | 6889 | 3 | 0 |
| 249 | `run_web_vis.<locals>._emit_solve_controls` | 12197 | 0 | 0 |
| 248 | `_draw_volume_scene` | 4980 | 6 | 0 |
| 237 | `run_web_vis.<locals>._show` | 11137 | 0 | — |
| 207 | `_draw_scene` | 5461 | — | 0 |
| 203 | `load_vis` | 520 | 1 | 0 |
| 193 | `um3k_panels.build_right_panel` | 307 | 1 | — |
| 182 | `um3k_panels.build_center_panel` | 50 | 1 | — |
| 172 | `main` | 13290 | 1 | — |
| 170 | `_mode_view` | 7958 | — | — |
| 166 | `_draw_volume_layer` | 10923 | 0 | — |
| 161 | `_draw_mode_picture` | 10671 | 0 | — |
| 145 | `build_frequency_chart` | 1932 | — | — |
| 144 | `_volume_abs_grid` | 8798 | — | — |

The 8-argument, 118-state-reference `run_web_vis` is the whole difficulty of
this file: everything else is separable by moving a definition.
