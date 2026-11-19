---
status: current
layer: work
pinned_commit: c6195cfb33e94a289ccabd8d5675bd7ff41d03c9
pinned_at: 2026-11-19
byte_budget: 6144
last_verified: 2026-11-19
reads_when: when you are about to start server/poc_app.py, or tell another session how to start it
supersedes: null
superseded_by: null
---

# docs/kb/WORK/run.md - the single source of how to start the app

This file is the maintained source of run instructions. The root `RUN.md` is a
four-line pointer at it and adds nothing of its own.

## Start it

From the repository root:

    PYTHONPATH=. python3 server/poc_app.py

The same command with the bind address and the port spelled out, which are the
defaults it already uses:

    PYTHONPATH=. python3 server/poc_app.py --host 127.0.0.1 --port 8080

Then open http://127.0.0.1:8080/ in a browser. The process does not open one for
you: the `server.start(...)` call passes `open_browser=False`.

## PYTHONPATH is mandatory

`PYTHONPATH=.` is not a convenience. `server/poc_app.py` imports the `emfit`
package from the repository root, so from the root it must be on the path.
Without it the process dies at import with:

    ModuleNotFoundError: emfit

## Preflight: --list-keys

    PYTHONPATH=. python3 server/poc_app.py --list-keys

Prints the dump's metadata and exits. It is numpy only - no pyvista, no trame -
so it is the first thing to run on a machine whose web stack is in doubt: if it
works, the data side is sound and only the view can be at fault.

## Flags

All nine, with the meaning taken from the `argparse` block in `main()` in
`server/poc_app.py`:

| flag | meaning |
| --- | --- |
| `--input` | npz dump to read; wins over `--structure` when given (default: the selected structure's own dump path, else `evidence/termination/build_A_50ohm_p51_ghostwave_fields.npz`) |
| `--structure` | structure id from `structures.json` (default: `build_A_50ohm`) |
| `--surface-dump` | Huygens surface archive, npz schema `emfit.surface-dump/1`, whose far field the Far Field tab draws; a separate input from the dump the page animates (default: none, and the tab then says so) |
| `--host` | bind address (default: `127.0.0.1`) |
| `--port` | port to bind (default: `8080`) |
| `--station` | initial station index (default: 4) |
| `--fps` | frames per second for the wave animation (default: 24); applies to an `emfit.vis/2` dump only, because a legacy station dump has no time axis and ignores it |
| `--list-keys` | print the dump metadata and exit; numpy only, no pyvista |
| `--dump-state` | write a JSON snapshot of everything the viewer knows to the given path and exit; numpy only, no pyvista, no trame |

## Stop it

Press Ctrl-C in the terminal that launched it. `server.start(...)` blocks in the
foreground: nothing is daemonised and there is no pid file to chase.

## Headless

Where there is no display the server still binds and `GET /` returns HTTP 200, so
a container can prove the process is up. Rendering needs OpenGL, so there are no
pixels without a display: a headless run is a liveness check, never a view.

## Dependencies

The browser view needs the trame/pyvista/VTK stack. Present here: trame 4.0.0,
trame_pyvista 0.3.6, pyvista 0.49.2, vtk 9.7.2. `requirements-web.txt` names six
packages - trame, trame-vuetify, trame-pyvista, trame-vtk, pyvista, vtk - and
pins no versions, so an install is whatever pip resolves that day. The numpy-only
paths (`--list-keys`, `--dump-state`) need none of it.

## Known broken

- `.venv/bin/python` is stale: its `pyvenv.cfg` says 3.12.3. Use the system
  `python3` unless you have rebuilt that environment.
- The README's historical run command omitted `PYTHONPATH` and fails as written.
  The two commands at the top of this file are the corrected form.

## First load

What you see on first load may not include a rendered geometry surface: the
default structure's evidence file is a legacy single-plane dump. Why that is, and
what the poc_app split does about it, is in `docs/kb/WORK/poc_app_split.md`.
Two further caveats belong with that first look: the browser view draws a debug
scaffold - marker spheres at the dump's sample points - rather than the full
production visualisation, and it has not been verified in this workspace, which
has no OpenGL.
