# UI surface inventory — poc_app.py / um3k_panels.py

Scope: read-only survey of the Trame web UI in `server/poc_app.py` (counts are 1-based
file line numbers as of this survey). Analysis only; no source was modified.

## 1. Pages

| # | Page builder | Lines | Status |
|---|---|---|---|
| 1 | `run_web` | `poc_app.py:5922-6774` (853 lines) | **ORPHANED** — never dispatched |
| 2 | `run_web_vis` | `poc_app.py:9894-13287` (3394 lines) | **The only reachable page** |

Dispatch evidence: `main()` at `poc_app.py:13290` routes every schema entry to `run_web_vis`;
`tests/test_poc_dispatch.py:108-155` asserts exactly that. No code path reaches `run_web`,
so its 853 lines (and the state keys templated only there — see DEFECTS B-2) are dead weight.

## 2. Screens

Exactly **1 screen** in the reachable page: a three-column `VRow`, asserted by
`tests/test_um3k_panels.py:198-230`, assembled from:

- `um3k_panels.build_left_panel` — `um3k_panels.py:16-47`
- `um3k_panels.build_center_panel` — `um3k_panels.py:50-231`
- `um3k_panels.build_right_panel` — `um3k_panels.py:307-499`

**7 view surfaces** inside that one screen: 1 centre picture + 4 SETUP cards + 5 DATA tabs
(centre is one surface; cards and tabs are the other six groupings — counted as 7 distinct
rendered regions, see §3 and §4).

## 3. SETUP column — 4 cards (`_emit_solve_controls`, `poc_app.py:12197-12460`)

| Card | Control | Type | Binding / handler |
|---|---|---|---|
| Project | Structure | `VSelect` | `v_model = solve_structure` (`12236-12263`) |
| Mesh & Geometry | Cut plane x (mm) | `VTextField` | `v_model = solve_xcut_mm` (`12271-12280`) |
| Mesh & Geometry | Mode | `VBtn` | label `{{mode_view_label}}`, `click = ctrl.mode_view_toggle` (`12296-12301`) |
| Mesh & Geometry | Mesh size | `VSelect` | `disabled=True`, `v_model=("mesh_size_placeholder","fixed (0.5 mm)")`, **no handler** (`12270-12290`) |
| Circuit | Netlist JSON box | textarea | `v_model = solve_netlist_json`, `_on_netlist_toggle` (`12009/12012/12101`), plus load-series selector |
| Action | Solve | `VBtn` | label `{{solve_label}}`, `click = ctrl.solve_start`, `disabled=("solve_disabled",False)` (`12322-12336`) |
| Action | Solve status | `VLabel` | `{{solve_status}}` (`12339`) |

## 4. DATA column — readout strip + 5 tabs (`um3k_panels.py:307-499`)

Readout strip (`um3k_panels.py:331-353`): `structure_readout`, `t_label`, `mode_label`,
`phase_label`, `scale_label`, `velocity_label`, `velocity_note`, plus one static `div`.

Tabs — `RIGHT_TABS` (`um3k_panels.py:240-262`), filtered by `visible_right_tabs`
(`265-304`); when no gating flag is true all **5** are shown:

| Tab | Content gate |
|---|---|
| S-Params | none (always shown) |
| Far Field | none (always shown) |
| Confidence | `ctx.available.record` |
| Modes | none |
| Circuit | none |

Tab bar is `VTabs`/`VTab` with `value=` set explicitly on both sides (fix comment
`423-453`); a stacked-panel fallback exists at `476-499`.

## 5. CENTRE column (`um3k_panels.py:50-231`)

| Element | Condition | Handler / binding |
|---|---|---|
| Cut Y / Cut Z sliders | only if `ctx.available.plane_stack` (`um3k_context.py:132`); emitted by `_emit_cut_sliders` (`poc_app.py:5720-5919`, called `um3k_panels.py:102`) | `_on_cut_y` `10425`, `_on_cut_z` `10441` |
| Station readout | always; written once at `10380`, template `13136`, emitted by `_emit_station_readout` `13105` | static by design — `state.station` set once at `10375` |
| PREV | `nt is not None` | `ctrl.step_back` `11507` |
| Play/pause | `nt is not None` | `ctrl.play_toggle` `12580` |
| NEXT | `nt is not None` | `ctrl.step_fwd` `11529` |
| Frame slider | `nt is not None` | `v_model=("frame",0)`, `max=("frame_max",nt-1)`, `@state.change("frame")` `11481` |
| Switch plane | always | `ctrl.mode_toggle` `11487` |
| Top View | always | `11543` |
| Side View | always | `11561` |
| Keyboard Space / ← / → | always | `ctrl.trigger("kbd_shortcut")` `12615` via `server/web_assets/keyboard.js` (the only web asset) |

## 6. Template-bound state keys (n_reads == 0 in Python, but **not** dead)

These are read by the Trame template, so a "written but never read" grep finding is a
false positive for them:
`solve_status` (`12339`), `play_label` (`um3k_panels.py:166`), `mode_view_label` (`12299`),
`mode_view_caption` (`12975/12980`), `cut_label` (`5890/5892/5915/5919`),
`station_readout` (`13136`), `page_source_text` (`um3k_panels.py:38`),
`structure_readout`/`t_label`/`mode_label`/`phase_label`/`scale_label`/`velocity_label`/
`velocity_note` (`um3k_panels.py:337-343`), `s_params_*`/`far_field_*`/`confidence_*`
(`12474-12556`).

## 7. Capability flags that gate the surface (`um3k_context.py:87-143`)

`volume_field` (VOLUME_KEY `e_centres` or VOLUME_RAW_KEY present in the loaded info),
`plane_stack` (`stations > 1`), `port_planes` (`stations > 0`), `multifreq`, `record`,
`s11_record`, `animation`.

## 8. Shipped artefact key survey (measured, not inferred)

| NPZ | keys | notes |
|---|---|---|
| `evidence/termination/build_A_50ohm_p51_ghostwave_fields.npz` | 11 | `e,h,plane_ez,plane_hy,plane_ey,plane_hz,nstep,nx,ny,nz,cell_m` — plane + volume_raw only, **no `e_centres`** |
| `artifacts/vis_dump_selftest.npz` | 38 | `schema,engine,created_utc,structure_id,load_ohm,ez_ycut,ez_xcut_near,ez_xcut_far,frame_index,frame_index_xcut,x_mm,y_mm,z_mm,t_ns,nx,ny,nz,nt,nt_x,dt_s,cell_m,j_cut,dump_stride,nsteps,f_ref_hz,f_pulse_hz,xcut_near_mm,xcut_far_mm,…` |
| `artifacts/vis_dump_1500.npz` | 36 | no `structure_id`/`load_ohm`; has `port_x_mm`/`load_x_mm` |
| `artifacts/vis_dump_B_100ohm.npz` | 38 | as selftest |
| `artifacts/smoke_A.npz` | 36 | as 1500 |
| `artifacts/live_run.npz` | 43 | richest |

Consequence: **no shipped NPZ carries a far-field surface-dump archive**, so the
"Far Field" tab cannot render on any artefact in the repo (see DEFECTS A-3).

## 9. Placeholder / blankness messages (each is a deliberate fallback, listed for triage)

- `13254` `"[poc_app] no timeline on this page"`
- `6940`, `6982` `"geometry: not drawn - cell_mm=…, nx=…, ny=…"` (legacy page)
- `10123` plane not drawn
- `11118` `"port planes not drawn: this dump does not record …"`
- `3968` `"not drawn in this view"`
- `4397`, `4399` cut sheets not drawn
- `um3k_panels.py:157-159` `"Static field snapshot - no timeline"`

## Counts

- Page builders: **2** (1 reachable, 1 orphaned)
- Screens: **1**
- View surfaces: **7** (1 centre picture + 4 SETUP cards + 5 DATA tabs regions ⇒ 7 distinct regions incl. the centre)
  - SETUP cards: **4** (7 controls inside; 1 disabled/dead)
  - DATA tabs: **5** (1 gated on `record`, 1 permanently unfillable by shipped data)
- Centre controls: **9** (2 cut sliders, PREV/play/NEXT, frame slider, Switch plane, Top View, Side View) + 3 keyboard shortcuts
- Web assets: **1** (`keyboard.js`)
- Non-UI doc complaints found: **2** (`GEN12_HANDOFF.md:72`, `:132`)
