# Findings: how to run the web UI

Read-only recon, 2026-11-17. Every "measured" claim below was executed in the agent
container; transcripts are in `boot_attempt.log` (§1-§4). `RUN_draft.md` is the
user-facing run document built from these answers.

The six questions are answered in order. Summary first:

- start command: `cd /workspace && PYTHONPATH=/workspace:/workspace/.venv/lib/python3.12/site-packages python3 server/poc_app.py`
- port/URL: `127.0.0.1:8080` by default -> `http://127.0.0.1:8080/`; **no** browser auto-open
- it works headless here: server boots, HTTP 200 on `/`, no crash — measured
- three blockers to a *rendered* field: (1) the two `PYTHONPATH` entries are undocumented and the README command alone fails, (2) no EGL/OSMesa/X in this image, so `Plotter.render()` segfaults and pixels were never verified here, (3) the default dump carries no frame axis/geometry keys, so the timeline, the y-cut/x-cuts and the board geometry are all "not drawn" regardless of GPU.

---

## Q1. Is there an existing document that says how to run the web UI?

**No dedicated one.** The only run-shaped text is a short block, not a run book:

- `README.md:138-153` — heading "## Web UI", three commands (`:141-143`), and prose
  naming `--input`, `--station` (default 4), `--host`, `--port` (`:146-148`).
- `server/poc_app.py:1-13` — module docstring: "Run: python3 server/poc_app.py \n
  Then open http://localhost:8080"; `:12-13` "Minimum packages: pyvista and trame
  (with a working VTK build). Nothing beyond numpy is needed for the --list-keys /
  --help path."
- `docs/design/onboarding/00_README.md:149-158` — §4 "How to run it": binds
  `127.0.0.1:8080` (`DEFAULT_HOST`/`DEFAULT_PORT`), no auto browser, and says
  outright "The exact invocation is not restated here because this pack did not run
  it".

Everything else in `docs/design/` is architecture or hazard material, not a run
guide: `web_ui_architecture_2026-11-08.md` (design note), `TRAME_HAZARDS.md` (139
lines of hazards), `visualizer_architecture.md:102-115` (dependency policy),
`EM_SOLVER_LEDGER.md:32` (status row E7). `scripts/` contains no web script
(`test_all.sh`, `em_reading_pack.sh`, `repin_kb.py`, `mutate_kb_gate.sh`,
`run_reference_sim.py`); `docker/` contains only `openems/`. So the "run the web UI"
page does not exist and `RUN_draft.md` is net-new.

Evidence quality note: the two docs that do discuss line numbers cite **stale**
ones — `00_README.md:154` says `open_browser=False` at `:4497` and `:7885`,
`onboarding/STATE.json:73-75` the same; the real sites are `:6757` and `:13270`.
`server/poc_app.py:50-56` still says the Trame path is UNTESTED, which
`docs/design/GEN12_HANDOFF.md:72` already flags as stale.

## Q2. What is the exact command, and what does it need on `PYTHONPATH`?

Documented form (`README.md:141`, docstring `server/poc_app.py:1-13`):

```bash
python3 server/poc_app.py
```

Measured: **that alone fails in this container**, and *not* for the reason the
READMEs give. It fails on `import emfit`, before any web package is consulted:

```
File "/workspace/server/poc_app.py", line 764, in load_any_dump
  from emfit.ntff import SURFACE_DUMP_KEYS, SURFACE_DUMP_SCHEMA, load_surface_dump
ModuleNotFoundError: No module named 'emfit'
```

Cause: with the script form, `sys.path[0]` is `/workspace/server`, so the sibling
package `/workspace/emfit` (which exists, `emfit/__init__.py`, 2331 B) is not
importable. The `-m` form puts the cwd on `sys.path`, which is why
`python3 -m server.poc_app` gets past this point and `python3 server/poc_app.py`
does not. `server/` has no `__init__.py`; `server/poc_app.py:77-90` supports both
forms for its own sibling imports.

The working invocation, measured end-to-end (`boot_attempt.log` §4):

```bash
cd /workspace
export PYTHONPATH=/workspace:/workspace/.venv/lib/python3.12/site-packages
python3 server/poc_app.py
```

- `/workspace` is for `emfit`.
- `/workspace/.venv/lib/python3.12/site-packages` is for the web stack: measured to
  contain trame 4.0.0, trame_server 4.1.0, trame_pyvista 0.3.6, trame_vtk 2.11.17,
  trame_vuetify 3.3.0, pyvista 0.49.2, vtk 9.7.2. Consistent with
  `docs/design/EM_SOLVER_LEDGER.md:32` (E7 correction) and
  `docs/design/GEN12_HANDOFF.md:71`.
- Do not use `.venv/bin/python`: `pyvenv.cfg` targets 3.12.3, the image ships
  3.12.15 (`GEN12_HANDOFF.md:71`, `tests/test_animation_volume.py:43-48`).

Environment correction to the task briefing: `echo $PYTHONPATH` was **empty** in
this shell, i.e. neither `/workspace` nor the venv tree was pre-set. The statements
in the docs are therefore recipes, not the ambient environment.

## Q3. What port and URL, and does it open a browser?

| Item | Value | Evidence |
|---|---|---|
| host | `127.0.0.1` | `DEFAULT_HOST` `server/poc_app.py:140` |
| port | `8080` | `DEFAULT_PORT` `server/poc_app.py:143` |
| URL | `http://localhost:8080` / `http://127.0.0.1:8080/` | docstring `:1-13`, printed `:13267-13268` |
| auto-open browser | **no** (`open_browser=False`) | `:13270`, legacy path `:6757` |

Startup prints `[poc_app] serving on http://127.0.0.1:8080` and `[poc_app] open that
URL in a browser; Ctrl-C to stop` (`:13267-13268`), then Trame prints its own
`App running at: - Local: http://127.0.0.1:8080/`. `--host` (`:13341-13343`) and
`--port` (`:13344-13346`) override. A taken port is reported, not crashed on:
`port {port} is already in use` (`:13271-13280`).

## Q4. Prerequisites and optional switches?

Required: Python 3.12 (3.12.15 measured), numpy/scipy/matplotlib (importable in the
bare interpreter), `emfit` importable (i.e. repo root on `PYTHONPATH` or
`pip install -e .`), the web stack (`WEB_MODULES` at `:5673-5679` = trame,
trame_pyvista, trame_vtk, vtk, pyvista; `WEB_VUETIFY_MODULES` `:5680`), and a dump
(`DEFAULT_INPUT` `:95` = `evidence/termination/build_A_50ohm_p51_ghostwave_fields.npz`,
present).

The documented install is `python3 -m pip install -r requirements-web.txt`
(`requirements-web.txt:1-9`; six packages, **no version pins**, `README.md:152-153`,
`docs/design/visualizer_architecture.md:102-115`). It needs network, so it is
`[UNVERIFIED]` here — but unnecessary, because the packages are already on disk in
`.venv/lib/python3.12/site-packages` and import cleanly from the system interpreter.

Switches, all from `main()` (`server/poc_app.py:13290`): `--input` (`:13378-13425`),
`--structure` (default `build_A_50ohm`, `:138`, `:13336-13340`), `--station` (default
4, `:13363-13365`), `--fps` (default 24, `:171`, `:13366-13375`), `--host`, `--port`,
`--list-keys` (`:13347-13352`, exits 0 at `:13446-13448`), `--dump-state`
(`:13353-13362`, returns 0 at `:13428-13434`). No environment variable is required by
the app itself; `PYTHONPATH` is the only one that matters in practice.

## Q5. Does it actually run here, headless?

**Yes — boots and serves; it does not render.** Measured twice (§2 module form, §4
script form):

```
[poc_app] web dependencies present
[poc_app] trame 4.0.0 - ui modules: trame.ui.vuetify3
PyVistaDeprecationWarning: pyvista.trame is deprecated ... (server/poc_app.py:9999)
vtkXOpenGLRenderWindow WARN| bad X server connection. DISPLAY=
vtkOpenGLRenderWindow  WARN| Failed to load EGL!
vtkOSOpenGLRenderWindow WARN| libOSMesa not found.
[poc_app] serving on http://127.0.0.1:8080
```

and, while it was up, `GET http://127.0.0.1:8080/` returned **HTTP 200, 1383 bytes**,
body `<!doctype html><html lang="en" data-app-name="trame" ...>`. The process stayed
alive until `timeout` killed it (rc 124). Nothing crashed.

Two distinct limitations, which must not be conflated:

1. **No pixels here.** No EGL, no libOSMesa, no X server; a real
   `pyvista.Plotter.render()` segfaults the interpreter
   (`tests/test_animation_volume.py:11-16`, `EM_SOLVER_LEDGER.md:32`,
   `GEN12_HANDOFF.md:70`). Boot survives only because no client connects.
   `[UNVERIFIED]` in-container: the 3-D image. `OPERATOR-REPORTED`, 2026-11-11:
   seven-step playback works on a host (`GEN12_HANDOFF.md:67`,
   `EM_SOLVER_LEDGER.md:32` E7).
2. **Even with a GPU this dump cannot fill the page.** The app printed
   `[poc_app] plane ez_ycut not drawn: 'ez_ycut'` (same for `ez_xcut_near`,
   `ez_xcut_far`), `[poc_app] geometry: not drawn - substrate_h_mm=absent,
   strip_w_mm=absent, port_x_mm=absent, load_x_mm=absent, xcut_near_mm=absent`, and
   `[poc_app] no timeline on this page: it records no frame axis`. Those are missing
   **record fields**, not missing OpenGL — `web_ui_architecture_2026-11-08.md:7-28`
   documents the npz as nine sampled x-planes with no axis vectors. So the default
   page is the station view, not the animated sheet.

Also measured: the numpy-only smoke path works once the repo root is on
`PYTHONPATH` (`PYTHONPATH=/workspace python3 server/poc_app.py --list-keys`, rc 0,
prints plane shape `(9,213,22) complex128`, `nstep 2399`, `cell_m 0.4 mm`, the nine
station x/mm values and per-station |Ez|). This is the right pre-flight check,
because a missing-dependency failure is *reported clearly* while the
`import emfit` failure is a raw traceback: `check_web_requirements()`
(`:5683-5717`) prints `[poc_app] cannot import X (provides: pip-name)` per package
and `run_web_vis()` (`:9940-9956`) then prints `the web UI cannot start: packages are
missing.` + `fix: python3 -m pip install ...` + `or: python3 -m pip install -r
requirements-web.txt` + `then re-run the same command.`, returning 1 with no
traceback (measured, §1).

## Q6. What is wrong with the current state, and what should the run doc do?

1. **The README command is not runnable as written** in this tree: `python3
   server/poc_app.py` dies on `import emfit` (Q2). The gap is `PYTHONPATH`, and it is
   undocumented in all three places that tell you how to run it (`README.md:138-153`,
   docstring `:1-13`, `00_README.md:149-158`).
2. **The README's "absent from the container" claim is false and should be corrected**
   (`README.md:150-152`, and the same claim already corrected in
   `EM_SOLVER_LEDGER.md:32` E7): the stack is in `.venv/lib/python3.12/site-packages`
   and imports on the system interpreter. What is broken is `.venv/bin/python`.
3. **Three files carry stale line numbers** for the app they describe:
   `00_README.md:154` and `onboarding/STATE.json:73-75` (`open_browser=False` at
   `:4497`/`:7885`; real `:6757`/`:13270`), `EM_SOLVER_LEDGER.md:32` quoting a
   64,355-byte `poc_app.py` with `main()` at `:1614` (actual size 621,407 B
   measured, `main()` at `:13290`, `run_web_vis()` at `:9894`), and `server/poc_app.py:50-56` still calling the Trame path
   UNTESTED.
4. **`requirements-web.txt` pins nothing** — six names, no versions
   (`requirements-web.txt:1-9`), while `visualizer_architecture.md:115` warns that
   pinning `vtk` by hand recreates the resolver conflict. Not this task's job to fix,
   but the run doc must not pretend a pinned set exists.
5. `--list-keys` is a good troubleshooting step but fails with a traceback rather
   than a diagnosis when `emfit` is missing; the run doc leads with the `PYTHONPATH`
   requirement instead.

`RUN_draft.md` therefore: leads with prerequisites (including both `PYTHONPATH`
entries and the "do not use `.venv/bin/python`" warning), gives the measured
one-liner, states port/URL/auto-open, tabulates the switches, separates
"headless/no-pixels" from "this dump has no timeline/geometry", carries a
symptom -> cause -> fix table with `file:line` citations, and marks every unverified
statement `[UNVERIFIED]` or `OPERATOR-REPORTED`.
