# How to run the web UI (draft)

Status of this draft: **verified by execution in the agent container on 2026-11-17**
except where a line is marked `[UNVERIFIED]`. Evidence for every claim: the
commands and transcripts in `boot_attempt.log` (sections 1-4) next to this file.
Nothing here required editing the repo; everything below is read-only recon.

The app is `server/poc_app.py`: one 621 kB Python file that is both the Trame web
UI and an argparse CLI (`docs/design/onboarding/00_README.md:134`, `:151`).

---

## 1. Prerequisites

| # | Requirement | Why | Evidence |
|---|---|---|---|
| 1 | Python 3.12 | the only interpreter in the image; 3.12.15 measured | `python3.12 -V` |
| 2 | numpy, scipy, matplotlib | imported at module import time | bare interpreter imports all three OK |
| 3 | **repo root on `PYTHONPATH`** | `server/poc_app.py` does `from emfit.ntff import ...`, and the script form puts `/workspace/server` (not `/workspace`) on `sys.path` | traceback in `boot_attempt.log` §3 |
| 4 | **trame + pyvista + vtk stack** | `WEB_MODULES = trame, trame_pyvista, trame_vtk, vtk, pyvista` | `server/poc_app.py:5673-5679`, `WEB_VUETIFY_MODULES` `:5680`, `check_web_requirements()` `:5683-5717` |
| 5 | a field dump to show | default input | `DEFAULT_INPUT` at `server/poc_app.py:95` = `evidence/termination/build_A_50ohm_p51_ghostwave_fields.npz` (present) |

Installing the web stack the documented way (needs network, **not** available here
`[UNVERIFIED]`):

```bash
python3 -m pip install -r requirements-web.txt   # requirements-web.txt:1-9; README.md:152-153: six, no pins
```

But: **the six packages are already on disk in this repo**, in the repo's own venv
tree, and the system interpreter can use them:

```bash
export PYTHONPATH=/workspace/.venv/lib/python3.12/site-packages
```

`.venv/lib/python3.12/site-packages` contains trame 4.0.0, trame_server 4.1.0,
trame_pyvista 0.3.6, trame_vtk 2.11.17, trame_vuetify 3.3.0, pyvista 0.49.2,
vtk 9.7.2 (measured: `ls` of that directory; `trame.ui.vuetify3` imports from it).
`docs/design/EM_SOLVER_LEDGER.md:32` (E7 correction, 2026-11-11) and
`docs/design/GEN12_HANDOFF.md:71` say the same thing.

Do **not** try `.venv/bin/python`: `pyvenv.cfg` says 3.12.3 while the image ships
3.12.15, so that interpreter's `sys.path` never reaches those site-packages
(`docs/design/GEN12_HANDOFF.md:71`, `tests/test_animation_volume.py:43-48`).

## 2. One-line start command

The README command (`README.md:141`, docstring `server/poc_app.py:1-13`) is:

```bash
python3 server/poc_app.py
```

**In this container it needs both paths on `PYTHONPATH`**, because of prerequisite 3
and 4. This exact line was run and served HTTP 200 (`boot_attempt.log` §4):

```bash
cd /workspace
export PYTHONPATH=/workspace:/workspace/.venv/lib/python3.12/site-packages
python3 server/poc_app.py
```

Equivalent forms that also work:

```bash
# module form: cwd is on sys.path, so only the venv tree needs adding
PYTHONPATH=/workspace/.venv/lib/python3.12/site-packages python3 -m server.poc_app

# if emfit is pip-installed (pip install -e .) the repo-root entry is unnecessary
python3 server/poc_app.py
```

Smoke test that does not need any of the web stack (numpy only,
`README.md:150-152`, docstring `server/poc_app.py:12-13`, exit 0 at
`server/poc_app.py:13446-13448`):

```bash
PYTHONPATH=/workspace python3 server/poc_app.py --list-keys
```
It prints the dump inventory (plane shape, nstep, cell_m, the nine station x/mm
values, per-station |Ez|). Run this first: if it fails, the fault is `emfit` or the
input file, not trame.

## 3. Port and URL

| Thing | Value | Evidence |
|---|---|---|
| default host | `127.0.0.1` (loopback only) | `DEFAULT_HOST` `server/poc_app.py:140` |
| default port | `8080` | `DEFAULT_PORT` `server/poc_app.py:143` |
| URL to open | `http://localhost:8080` / `http://127.0.0.1:8080/` | docstring `:1-13`; printed at `:13267-13268` |
| browser auto-open | **no** — `open_browser=False` | `server/poc_app.py:13270` (and the legacy path at `:6757`) |

Override with `--host` (`:13341-13343`) and `--port` (`:13344-13346`).
Reaching it from outside the machine needs `--host 0.0.0.0` (or a tunnel); the
default binds loopback `[UNVERIFIED]` whether the container port is published.

Port already taken: `server.start` raises `OSError`/`EADDRINUSE` and the app prints
`port {port} is already in use` and returns non-zero (`:13271-13280`).

## 4. Optional arguments / environment variables

| Flag | Default | Meaning | Evidence |
|---|---|---|---|
| `--input PATH` | `evidence/termination/build_A_50ohm_p51_ghostwave_fields.npz` | the dump to display | `:95`, resolution `:13378-13425` |
| `--structure NAME` | `build_A_50ohm` | board/structure record (`structures.json`) | `:138-139`, `:13336-13340` |
| `--station N` | `4` | which captured plane is shown first | `:13363-13365` |
| `--fps N` | `24` | playback frame rate | `:171`, `:13366-13375` |
| `--host` / `--port` | `127.0.0.1` / `8080` | bind address | `:140`, `:143`, `:13341-13346` |
| `--list-keys` | off | print dump inventory and exit 0; numpy only | `:13347-13352`, `:13446-13448` |
| `--dump-state FILE` | off | write the page model as JSON and exit 0 | `:13353-13362`, `:13428-13434` |

Environment variables: **none are required**. The only one that matters is
`PYTHONPATH` (prerequisite 3/4). `EMFIT_FORCE_PYTHON=1` belongs to the solver, not
the UI (`docs/design/GEN12_HANDOFF.md:31`).

`--structure` pointing at a record-only structure does not fail: the app opens a
bare board page instead (`:13398-13415`).

## 5. Headless / container notes

Measured here (`boot_attempt.log` §2 and §4): the server boots and serves with **no
X server, no EGL, no OSMesa**. On startup VTK warns and the app degrades instead of
dying:

```
vtkXOpenGLRenderWindow WARN| bad X server connection. DISPLAY=
vtkOpenGLRenderWindow WARN| Failed to load EGL! ...
vtkOSOpenGLRenderWindow WARN| libOSMesa not found. ...
[poc_app] plane ez_ycut not drawn: 'ez_ycut'          (also ez_xcut_near/far)
[poc_app] geometry: not drawn - substrate_h_mm=absent, strip_w_mm=absent, ...
[poc_app] no timeline on this page: it records no frame axis, ...
```

Those "not drawn" lines are about **missing record fields in this dump**, not about
the missing GPU: this npz carries the nine x-planes only, so the y-cut/x-cut sheets,
the board geometry and the time scrubber have nothing to draw
(`docs/design/web_ui_architecture_2026-11-08.md:7-28`).

What genuinely cannot be done in this container: **see the picture.** There is no
EGL/OSMesa/Xvfb, and a real `pyvista.Plotter.render()` segfaults the interpreter
(`tests/test_animation_volume.py:11-16`, `docs/design/EM_SOLVER_LEDGER.md:32`,
`docs/design/GEN12_HANDOFF.md:70`). Nothing crashes at boot because no client ever
connects; the moment a browser asks for pixels the render path is the risk.
`[UNVERIFIED]` in-container: that the browser client shows a 3-D field.
`OPERATOR-REPORTED`: it does on a normal host — seven-step playback, 2026-11-11
(`docs/design/GEN12_HANDOFF.md:67`, `docs/design/EM_SOLVER_LEDGER.md:32` E7).

## 6. Troubleshooting

| Symptom | Cause | Fix | Evidence |
|---|---|---|---|
| `[poc_app] cannot import trame (provides: trame-pyvista)` x6, then `the web UI cannot start: packages are missing.` | web stack not on `sys.path` | `export PYTHONPATH=/workspace/.venv/lib/python3.12/site-packages`, or `pip install -r requirements-web.txt` | `:5683-5717`, `:9940-9956`, `boot_attempt.log` §1 |
| `ModuleNotFoundError: No module named 'emfit'` before any web output | script form puts `/workspace/server` on `sys.path`, not the repo root | `export PYTHONPATH=/workspace` (or `pip install -e .`) | traceback `boot_attempt.log` §3 |
| `port 8080 is already in use` | another instance / another service | `--port 8081` (or stop the other one) | `:13271-13280` |
| `bad X server connection` / `Failed to load EGL!` / `libOSMesa not found` | headless box, no GPU/EGL/OSMesa | harmless at boot; for real pixels run where a GL context exists, or install `libegl1`/`libosmesa6` | `boot_attempt.log` §2/§4 |
| browser reaches nothing at `localhost:8080` | default bind is loopback `127.0.0.1` | `--host 0.0.0.0` or tunnel; check the container publishes the port | `:140`, `:143` |
| page loads, 3-D pane blank | client-side render, no server-side pixels pushed until the client renders | expected on a headless box; `[UNVERIFIED]` whether any VTK warning in the browser console accompanies it | see §5 |
| `[poc_app] no timeline on this page` | this dump records no frame axis, so no player bar is built | use a dump with a frame axis | printed at `:13290ff` flow; `boot_attempt.log` §4 |
| `plane ... not drawn` / `geometry: not drawn - ...=absent` | the npz lacks those plane/geometry keys | not an error; that panel is simply absent | `boot_attempt.log` §2/§4 |
| `PyVistaDeprecationWarning: pyvista.trame is deprecated` | pyvista 0.49 moved the trame UI into `trame_pyvista` | cosmetic; the fallback import still works | `server/poc_app.py:9999` |

## 7. What you should see

On stdout, in this order (`boot_attempt.log` §4, verbatim):

```
[poc_app] study record: /workspace/evidence/termination/build_A_50ohm_p51_ghostwave.json
[poc_app] no multi-frequency sweep in /workspace/evidence/termination ...
[poc_app] web dependencies present
[poc_app] trame 4.0.0 - ui modules: trame.ui.vuetify3
... VTK WARNs (headless) ...
[poc_app] serving on http://127.0.0.1:8080
[poc_app] open that URL in a browser; Ctrl-C to stop

App running at:
 - Local:   http://127.0.0.1:8080/
 - Network: http://127.0.0.1:8080/
```

Then `GET http://127.0.0.1:8080/` returns **HTTP 200** with the Trame index page
(1383 bytes here, measured), beginning
`<!doctype html><html lang="en" data-app-name="trame" ...>`. Ctrl-C stops it.
`[UNVERIFIED]`: the rendered field image inside that page.

**What the page is supposed to contain** (documentation claim, not observed here):
`README.md:148-149` calls the view "currently a DEBUG SCAFFOLD, not a real field
visualizer: it draws marker spheres at the dump's sample points, nothing more".
`docs/design/web_ui_architecture_2026-11-08.md` describes the richer target (orbited
3-D field plus a station scrubber). Treat the README wording as arbitration until
someone looks at a real frame.
