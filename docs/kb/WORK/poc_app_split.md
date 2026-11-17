---
status: current
layer: work
pinned_commit: null
pinned_at: null
byte_budget: 6144
last_verified: 2026-11-17
reads_when: when you are about to move code out of server/poc_app.py, or when a report says the P2 split is done
supersedes: null
superseded_by: null
---

# docs/kb/WORK/poc_app_split.md - the P2 split of server/poc_app.py, and why it is blocked

**Status: blocked - not done, and not proposed for landings.** Nothing has been
moved. This file records the measured baseline and the gate the split has to
pass; it is not a plan for a split that has happened. (Its header reads
`current` because that key records the currency of this record, not the state
of the split: the record is up to date, the split is blocked.)

## Verified baseline

- `server/poc_app.py` is 13,465 lines with 315 defs and 61 state keys, 42 of them
  multi-writer.
- Rough mass: engine 5,040 lines (37.4%), UI shell 4,805 (35.7%), render 2,554
  (19.0%), glue 7.9%.
- No engine function touches `state` or the UI. That is the whole reason a split
  is mechanical rather than a rewrite: the engine does not know the page exists.
- 11 top-level sections.
- `run_web_vis` spans lines 9894-13287, 3,394 lines. Its closures (`_show`,
  `_play_loop`, the `_on_*` handlers) are reached only through `__closure__`, and
  that is the hard part of any move.
- `run_web` at about line 5922 is 853 lines and is UNREACHABLE: `main()` only ever
  returns `run_web_vis`.
- `main` spans 13290-13465.
- 0 unreferenced symbols, 3 exact duplicate pairs, 0 near-duplicates at or above
  0.72.

## The gate: identical behaviour, proved, not asserted

    PYTHONPATH=. python3 server/poc_app.py --dump-state <path>

writes a JSON snapshot of everything the viewer knows to `<path>` and exits. Run
it before a move and after it; the two JSON files must be identical, byte for
byte. That is the whole acceptance test, and it is the point of this file: a
split that cannot show two identical snapshots has not been proved safe.

The command is numpy only - no pyvista, no trame - so the gate runs headless on
any host, including one with no display and no web stack installed.

## Blockers

1. Stage 1b must be green on a git-capable host first. A byte-identity gate
   stacked on top of an unrun gate proves nothing about the tree it ran in.
2. The split must not interleave with any other large diff. Two structural edits
   in flight at once make the snapshot diff unreadable, and unreadable is how a
   behaviour change ships.

Until both hold, the status stays blocked.
