---
status: current
layer: work
pinned_commit: c6195cfb33e94a289ccabd8d5675bd7ff41d03c9
pinned_at: 2026-11-19
byte_budget: 10240
last_verified: 2026-11-19
reads_when: when you are about to move code out of server/poc_app.py, when a report says the P2 split is done, or when you are adding a simulation input or output format
supersedes: null
superseded_by: null
---

# docs/kb/WORK/poc_app_split.md - the de-monolith plan for server/poc_app.py

Nothing has been moved. This file carries the three things a move needs first: the
measured baseline, the byte-identity gate, and the module order with its phases. It is
a plan for work that has NOT happened, and the first phase that touches render code is
blocked (see Blockers). The header reads `status: current` because that key records
whether this record is up to date, not whether the split is: the record is current, the
split is blocked.

## Verified baseline (measured, not estimated)

- `server/poc_app.py` is 13,465 lines, 315 defs, 61 state keys, 42 of them multi-writer.
- Rough mass: engine 5,040 lines (37.4%), UI shell 4,805 (35.7%), render 2,554 (19.0%),
  glue 7.9%.
- No engine function touches `state` or the UI. That is why a split is mechanical rather
  than a rewrite: the engine does not know the page exists.
- 11 top-level sections.
- `run_web_vis` spans 9894-13287, 3,394 lines. Its closures (`_show`, `_play_loop`, the
  `_on_*` handlers) are reachable only through `__closure__`. That is the hard part of
  any move, and the reason the order below is bottom-up.
- `run_web` at about line 5922 is 853 lines and UNREACHABLE: `main()` dispatches every
  schema entry to `run_web_vis`.
- `main` spans 13290-13465.
- 0 unreferenced symbols, 3 exact duplicate pairs, 0 near-duplicate pairs at or above
  0.72.

## The gate: identical behaviour, proved, not asserted

    PYTHONPATH=. python3 server/poc_app.py --dump-state <path>

writes a JSON snapshot of everything the viewer knows to `<path>` and exits. Run it
before a move and after it; the two files must be identical, byte for byte. numpy only -
no pyvista, no trame - so it runs headless on any host, including one with no display
and no web stack. A move that cannot show two identical snapshots has not been proved
safe, however readable the diff looks.

## Blockers

1. Stage 1b must be green on a git-capable host first. A byte-identity gate stacked on
   top of an unrun gate proves nothing about the tree it ran in.
2. The split must not interleave with any other large diff. Two structural edits in
   flight at once make the snapshot diff unreadable, and unreadable is how a behaviour
   change ships.

Both hold, or no code moves. Nothing in this file lifts either of them.

## The contract the modules talk through: SimulationManifest

The six modules below share one data contract instead of sharing `state`. An artefact
directory IS a manifest, and what exists in it decides which tabs are offered - read,
never assumed.

- `ports.npz` - port planes and their geometry.
- `modes.npz` - mode fields from the 2D eigenmode solve.
- `volume.npz` - 3D volume records with their time axis (`e_abs_volume_stride`,
  `e_abs_volume_step_index`, ...). The recorded stride is data: a decimated volume is
  reported as decimated, never played as continuous motion.
- `s_params.json` - scalars: S-parameters, frequencies, confidence.

Every file is optional. A manifest with no `volume.npz` offers no volume tab and says
why, which is the general form of the Far Field fix in `artifacts/ui_surface/DEFECTS.md`
(A-3): a tab that cannot render states that it cannot, on the artefact in hand.

## Six modules, in move order

1. `data_loader` - manifest reading, the time axis, the aliasing measurement. No Trame,
   no pyvista, no `state`.
2. `geometry_view` - the 3D surface and mesh view.
3. `field_view` - cut planes, the |Ez| sheets, the volume slices.
4. `mode_view` - the mode panel, with its OWN 2D renderer: it must not reach into the
   field renderer, or the two stay welded and neither moves again.
5. `state_machine` - the state keys, their writers, and the refresh discipline that
   DEFECTS.md A-1 and A-2 are about.
6. `ui_builder` - the Trame layout, last, because it is what everything else is called
   from.

The order is dependency order, not size order: a module can move only once the ones
above it no longer reach back into `poc_app.py`.

## Phases: one commit each, each ending in a byte-identical snapshot

- P0 - freeze: capture the gate snapshot, no code move, so P1 has a baseline to fail
  against.
- P1 - `data_loader` moves out; `poc_app.py` imports it.
- P2 - `geometry_view` moves out. BLOCKED until Stage 1b is green on a git-capable host:
  this is the first phase that touches render code.
- P3 - `field_view` moves out.
- P4 - `mode_view` moves out with its own 2D renderer.
- P5 - `state_machine` moves out; every writer is named in `state_keys.tsv` first.
- P6 - `ui_builder` moves out; `poc_app.py` becomes the shim `main()` calls into.

Each phase ends with the gate, two snapshots byte-identical, plus `ast.parse` clean. A
phase that cannot show them is reverted, not debugged forward.

## What a Run would need: four solves, and only one of them is wired

The manifest is a contract for outputs, and nothing in this tree produces three of its
four families:

1. 2D eigenmode solve - would write `modes.npz`.
2. 3D FDTD - would write `volume.npz`.
3. NTFF far-field - `emfit/ntff.py` exists and is UNWIRED (nothing calls it), which is
   why no shipped artefact carries a surface record.
4. S-parameters - would write `s_params.json`.

Until they exist, a Run control can only re-read what an offline run already wrote, and
the honest thing for the page to do is say so rather than offer a button that cannot run.

## Byte budget

`byte_budget: 10240` is measured, not aspirational. PINS.budgets.work is 20,480 B and
the whole WORK layer was 6,727 B before this file grew (`run.md` alone is 4,192 B), so
this plan fits its own header with the layer still far inside its cap.
