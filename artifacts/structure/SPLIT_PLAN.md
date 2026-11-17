# SPLIT_PLAN — carving `server/poc_app.py` (13,465 lines) into a façade + flat siblings

Companion to `artifacts/structure/MAP.md` (measured inventory: `functions.tsv`, `classes.tsv`,
`state_keys.tsv`, `_data.json`). Everything below is derived from that data plus the test/script
files cited inline.

## 0. Goal, budget, non-goals

**Goal.** `server/poc_app.py` becomes a façade of **≤ 400 lines** (imports + re-exports +
`main()` + argparse + import guard). All code moves into **flat sibling modules in `server/`**
(no package, no `__init__.py`): 13 modules, then 17 after the optional P6.

**Size budget.** No module may exceed **1,200 lines**, with exactly one exemption:
`poc_shell_vis` is allowed to stay at **3,394** after P4 and must reach **≤ 1,300** after P6
(its output is 3 coupled closures that cannot be cut without the C8 work).

**Behaviour gate.** Zero behaviour change. The binding test is a **byte-identical**
`--dump-state` JSON for *both* dump schemas (field schema and vis schema), plus byte-identical
`--list-keys` output. Nothing else counts as evidence.

**Non-goals (explicitly out of scope for this plan).**
- No renames, no signature changes, no "while we're here" fixes (see R8).
- No new dependencies; no import reordering that changes matplotlib/pyvista/trame load order.
- `um3k_panels` API untouched (it is the shared view layer for both shells).
- The duplicated literals in `um3k_context` stay (a test pins them).
- No dedup of the 3 exact duplicate pairs and the small repeated blocks; they are recorded in
  MAP.md and stay where they are.

## 1. HARD CONSTRAINTS

These are not preferences; each one is enforced by an existing test or script. Breaking any of
them breaks the build silently or loudly.

| # | Constraint | Evidence |
|---|---|---|
| **C1** | **`main()` must stay in `poc_app.py`.** The dispatch tests monkeypatch `poc_app.reload_page` / `poc_app.print_keys` / `poc_app.run_web_vis` / `poc_app.run_web` and then call `poc_app.main()`. Monkeypatch only reaches readers that resolve the name **in that module's namespace**, so `main` must live there and the four callees must remain module attributes of `poc_app`. | `tests/test_poc_dispatch.py:89-105` |
| **C2** | **Rebound-global ownership.** `MULTIFREQ_BY_STRUCTURE`, `SINGLE_RUN_BY_STRUCTURE`, `SOLVER_SCRIPT`, `LIVE_DUMP`, `mode_view` are rebound/read as module globals by tests. Each must move **with its consumer**, and the 7 test sites must be repointed in the **same commit**. | `tests/test_poc_playback.py:616,617`; `:778,779`; `:1319,1320`; `:1545` |
| **C3** | **`run_web_vis` is source-parsed.** A test asserts there is exactly **one top-level `run_web_vis` definition in `server/poc_app.py`** and that its body builds the 3-column `VRow` (`left=build_left_panel(ctx)`, centre `build_center_panel(ctx)`, right `build_right_panel(ctx)`). Moving it means repointing the `POC_APP` constant. | `tests/test_um3k_panels.py:185-195`, `:198-230`, constant at `:52` |
| **C4** | **CLI contract frozen.** `--dump-state`, `--list-keys` and the module-as-script entry stay; `--list-keys` must remain numpy-only (it must not import pyvista/trame). | `scripts/run_reference_sim.py:84,398,466`; `tests/test_poc_state.py` (subprocesses `--dump-state`) |
| **C5** | **Reuse the dual import idiom** (`try: from X import * / except ModuleNotFoundError as exc: if exc.name not in (...): raise`). The narrow `exc.name` tuple is tested — do not widen it. | `server/poc_app.py:76-90`; `tests/test_um3k_panels.py:1136-1148` |
| **C6** | **Flat files in `server/`.** The tests put `server/` on `sys.path` by path idiom; no package, no relative imports. | `tests/test_poc_playback.py:32-36` |
| **C7** | **The doc pack slices `poc_app.py` by hard line numbers** and is **already stale** (3512 lands inside `_geom_mm.<locals>._num`, 7396 inside `solve_netlist_file`). Re-anchoring is mandatory in P4. | `scripts/em_reading_pack.sh:27-33` (3512-3625, 6202-6299, 7396-7446, 7912-7947, 8240-8300, 8386-8469, 8540-8580) |
| **C8** | **Closure cells ARE the test harness.** Tests dig `_show` out of `trigger`'s cells, then reach `_draw_volume_layer`, `handles`, `page`, `plotter` from *its* cells; and read `handles`/`state` off `play_toggle`'s cells. So `_show`, `_play_loop`, `_on_*` must stay closures; P6 extracts **around** them, never converts them to parameter-taking functions. | `tests/test_animation_volume.py:330-340`; `tests/test_poc_playback.py:612-626` |

## 2. Target layout

| module | source ranges (current `poc_app.py`) | ~lines | may import |
|---|---|---|---|
| `poc_config` | 93-201 consts; `RUN_CONFIG_FIELDS` 9176-9257; `SOLVE_DEFAULT_XCUT_MM` 9637; `PAGE_KEYS` 9729 | 260 | stdlib, json |
| `poc_dumps` | S2 203-975 (loaders / dump readers) | 773 | numpy, poc_config |
| `poc_records` | S3 979-1725 (record + sweep + registry) | 747 | numpy, poc_config |
| `poc_charts` | S4 1729-2500 | 772 | matplotlib, numpy, poc_config |
| `poc_boards` | S5 2501-4570 (state blocks, page dicts, `_geom*`, `_plane_layout`, `_cut_layout`, `print_keys`) | 2,070 | numpy, matplotlib, poc_config |
| `poc_scene` | S6 4572-5680 **minus** `check_web_requirements` | 1,074 | pyvista, numpy, poc_boards |
| `poc_vis_scene` | 6777-7464 (`_vis_geometry` 6889) | 688 | pyvista, numpy |
| `poc_mode` | 7467-8601 (mode viewer) | 1,135 | pyvista, numpy |
| `poc_volume` | 8635-9634 | 1,000 | pyvista, numpy |
| `poc_solve` | `SolveJob` 9640-9724; `solve_argv` 7271; `solve_netlist_file` 7386; `_next_solve_run_tag` 7242; `_solve_netlist_slug` 7256; run-config 9148-9354; `check_web_requirements` 5683; `build_far_field_panel` 9796 | 700 | numpy, subprocess, poc_config |
| `poc_widgets` | `apply_page` 9732; `VRow` 9764; `VCol` 9780 | 90 | trame |
| `poc_shell_legacy` | S7 5720-6774 incl. `run_web` (5922-6774) | 1,057 | everything above |
| `poc_shell_vis` | 9894-13287 (`run_web_vis` 3,394) | 3,394 → ≤1,300 after P6 | everything above |
| `poc_app` (façade) | imports/re-exports + `main` 13290-13461 + argparse + guard | ~250 | all of the above |

**Dependency rule.** `poc_config` and `poc_dumps` are roots (no sibling imports). Only
`poc_shell_legacy`, `poc_shell_vis` and the façade may sit on top of everything. **Nothing
imports `poc_app`** (except the outer scripts/tests, unchanged). Engine-side modules
(`config/dumps/records/charts/boards/solve`) must **not** module-import `pyvista` or `trame` —
that is what keeps C4's `--list-keys` numpy-only.

**Minimum first cut** (if the whole plan is too much): config + dumps + records + boards + scene
= **4,924 lines, 36.6%** of the file, and leaves the two shells untouched.

## 3. The three seams

The split works because only three interfaces cross module boundaries:

1. **Data seam** — the `info` dict and the page dict (`PAGE_KEYS`, 61 keys). Already dict-shaped,
   already passed as a parameter everywhere outside the shells.
2. **Layout seam** — `um3k_context.PageContext` + `handles`. Already consumed by `um3k_panels`
   from *both* shells, so it is a proven boundary.
3. **State seam** — only `poc_shell_*` may touch `state` / `ctrl` / `handles`. Everything below
   takes them as arguments. The model to imitate already exists:
   `_redraw_scene(plotter, info, planes, state, show_quiver, station_label=...)`.

An engine-side function that touches `state` or `ui` is a boundary violation; the measurement
found **0** such functions today, so this rule costs nothing to keep.

## 4. Phases

Each phase is a commit series that ends with the full gate green (§5).

- **P0 — freeze baseline.** `sha256sum` of `poc_app.py`; `--dump-state` JSON for both schemas;
  `--list-keys`; `sh scripts/em_reading_pack.sh | wc -c`; full suite green. Store under
  `artifacts/structure/baseline/`.
- **P1 — numpy leaves.** `poc_config`, `poc_dumps`, `poc_records`. C2 work here:
  `MULTIFREQ_BY_STRUCTURE` / `SINGLE_RUN_BY_STRUCTURE` move to `poc_records`, get re-exported
  from `poc_app`, and `test_poc_playback.py:616,617,778,779` are repointed in the same commit.
- **P2 — render leaves.** `poc_charts`, `poc_scene`, `poc_vis_scene`.
- **P3 — engine/UI middles.** `poc_boards`, `poc_mode`, `poc_volume`, `poc_solve`,
  `poc_widgets`. `SOLVER_SCRIPT` / `LIVE_DUMP` move to `poc_solve`, repoint
  `test_poc_playback.py:1319,1320`.
- **P4 — shells out.** `poc_shell_legacy` (incl. `run_web`) and `poc_shell_vis`; `poc_app`
  becomes the ≤400 line façade. Three coupled edits land **in this commit**:
  (a) `tests/test_um3k_panels.py:52` `POC_APP` → the new home of `run_web_vis`; (b)
  `test_poc_playback.py:1545` `mode_view` repoint; (c) re-anchor every slice in
  `scripts/em_reading_pack.sh:27-33` by symbol (snippet in §5).
  At this point the accounting is: façade ~250 / 15 modules / largest 3,394.
- **P5 — OPTIONAL, product decision: retire `run_web`.** Present, do not act. Evidence:
  `main` dispatches **every** schema to `run_web_vis` (`tests/test_poc_dispatch.py:108-155`), so
  the legacy `run_web` path is unreachable in production; the 6 test-only symbols total
  **1,010 lines**, of which `run_web` is **853**. Deleting it also retires the legacy fixture,
  the `[run_web]` parametrisation (`test_poc_playback.py:2368`) and the `run_web` recorder
  (`test_poc_dispatch.py:95`).
- **P6 — carve `run_web_vis`** (the only genuinely hard part; 3,394 lines, 8 args, 118 `state`
  references). Order:
  1. Introduce a `Page` object mirroring the existing `PageContext` (layout seam), so the body
     stops closing over 8 locals.
  2. **Pure emitters → `poc_shell_vis_emit.py` (~700 lines):** `_emit_solve_controls` 249,
     `_emit_circuit_netlist` 126, `_emit_vector_toggle` 84, `_emit_load_series_panel` 55,
     `_emit_s_params_panel` 51, `_emit_mode_picker` 47, `_emit_far_field_panel` 36,
     `_emit_confidence_panel` 26, `_emit_mode_caption` 25, `_emit_station_readout` 24.
  3. **Draw mutators → `poc_shell_vis_draw.py` (~640 lines):** `_draw_volume_layer` 166,
     `_draw_mode_picture` 161, `_rebuild_sheets` 84, `_draw_mode_quiver` 58, `_swap_scalar_bar`
     40 — plus `_show` 237, which **stays a closure wrapper** in `poc_shell_vis` (C8) over the
     moved implementation.
  4. **Solve/watch → `poc_shell_vis_solve.py` (~400 lines):** `_watch_solve` 12687,
     `_start_watch` 12710, `_poll_solve` 12721, `_on_solve_start` 12853, `_run_job` 12839,
     `_drop_netlist` 12825.
  5. **Panel loaders** + the cut-slider block duplicated at 10426-10509, which should **call**
     `poc_shell_legacy`'s function instead of re-declaring it.
  Result: `poc_shell_vis` ≤ 1,300; façade unchanged ~250 / 17 modules.

## 5. Verification gates

Run after **every** phase; all must pass.

```sh
# import integrity (no circulars, dual idiom intact)
PYTHONPATH=.:server:./.venv/lib/python3.12/site-packages python3 -c "import poc_app"

# C4: CLI still numpy-only
python3 server/poc_app.py --list-keys \
    evidence/termination/build_A_50ohm_p51_ghostwave_fields.npz

# THE behavioural gate: byte-identical dumps, both schemas
python3 server/poc_app.py --dump-state /tmp/after_fields.json  <fields inputs>
cmp /tmp/after_fields.json artifacts/structure/baseline/dump_fields.json
python3 server/poc_app.py --dump-state /tmp/after_vis.json     # artifacts/vis_dump_selftest.npz
cmp /tmp/after_vis.json    artifacts/structure/baseline/dump_vis.json

# cheap set
pytest -q tests/test_um3k_panels.py tests/test_poc_dispatch.py \
          tests/test_poc_state.py tests/test_volume_colocation.py
# boot set (slow, needs the 3D stack)
pytest -q tests/test_animation_volume.py tests/test_poc_playback.py tests/test_poc_volume_arrows.py

# doc pack size must not move more than ±2 kB
sh scripts/em_reading_pack.sh | wc -c
```

**Pack re-anchor helper** (replaces C7's stale line slices with symbol-anchored ranges):

```sh
awk '/^def NAME\(/{s=NR} s&&/^def |^class /&&NR>s{print s","NR-1;exit}' server/poc_app.py
```

## 6. Risk register

- **R1 — monkeypatched globals go inert silently.** If a name is re-exported by `poc_app` but read
  from a *sibling's* namespace, `monkeypatch.setattr(poc_app, ...)` stops affecting behaviour and
  the test still passes for the wrong reason. Mitigation: add a guard test asserting each patched
  name is **owned by exactly one module** and that `poc_app.<name> is <owner>.<name>`.
- **R2 — closure-cell tests (C8).** Any transform of `_show` / `_play_loop` / `_on_*` into
  parameter-taking functions breaks the harness with an `AttributeError` deep in a helper.
- **R3 — layout source parsing (C3).** `test_um3k_panels` reads `run_web_vis` out of the *file*;
  a moved function with the constant un-repointed fails.
- **R4 — `--dump-state` drift.** Import order can change float formatting and dict ordering.
  Gate on bytes, not on "looks right".
- **R5 — circular imports via the dual idiom.** A sibling that imports back into `poc_app` will
  only fail on some entry points. Mitigation: AST test computing module import rank by phase.
- **R6 — doc pack silently mislabels (C7).** `em_reading_pack.sh` degrades gracefully: it prints
  whatever lines 3512-3625 contain, correct or not, so a wrong split looks fine. Re-anchor by
  symbol and eyeball the excerpt headers once per phase.
- **R7 — draw order.** `plotter.clear()` + quiver re-add at 10385-10392 is order-sensitive.
  P1-P4 move modules **only**; no reordering of draw calls. P6 changes call sites, so P6 is the
  phase that re-verifies the vis dump.
- **R8 — no while-here dedup.** The 3 exact duplicate pairs (`_on_cut_y`, `_on_cut_z`, `_redraw`)
  and the 4-line blocks repeated in 8/8/8/6/6/5/4 functions stay. Mixing dedup into a move makes
  a failed gate unattributable.

## 7. Accounting

| stage | façade lines | modules | largest module | public names | behaviour gate |
|---|---|---|---|---|---|
| now | 13,465 | 3 | 13,465 | — | — |
| after P4 | ~250 | 15 | 3,394 (`poc_shell_vis`) | all preserved via re-export | byte-identical |
| after P6 | ~250 | 17 | ≤1,300 (`poc_shell_vis`) | all preserved via re-export | byte-identical |
