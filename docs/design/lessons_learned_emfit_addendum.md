# Lessons learned — EM fitting, addendum (generation 10)

Companion to `lessons_learned_emfit.md` (L1–L6), which is unchanged.

Date: 2026-11-13

## L7 — A script is not a tool until it has run

**What happened.** The openEMS referee (`docker/openems/build_A_referee.py`)
was written, reviewed and treated as evidence before it had been run end to end.
When it was finally run it exited zero, wrote its reports, and had solved
**air**: the strip property was outranked and dropped, so the model had no
conductor. Every number it produced was a number about empty space, formatted
exactly like a number about a microstrip. Finding this required three more fixes
before the model had a conductor at all — the strip at `priority=10`, an MSLPort
launch, and a one-cell strip/feed overlap — none of which were visible in the
source.

**What it cost.** Days. Every conclusion drawn from the script's output before
the first real solve had to be discarded, and the discard was silent: nothing
about the output marked it as air.

**The rule.** A script is not a tool until it has run on known geometry and its
output has been read. Written code is a hypothesis about behaviour; only an
execution turns it into an instrument. Before quoting a number a script emits,
name the run that produced it and what that run was checked against.

**Amendment 2026-11-14 — earned a second time.** The same lesson was paid for
again on the referee integration: `docker/openems/build_A_referee.py` existed,
imported cleanly and was cited as the referee, but its MSLPort launch path had
never been exercised against the shipped geometry, so the same class of failure
— a model that solves without the physics it claims to model — came back and
was caught only by running it and reading the observable (see L11 and DR-41).
This is an **amendment to L7, deliberately not a new L-number**: restating a
rule that already exists in new words is how a knowledge base stops being
searchable. When a lesson fires again, date it in place and say what the second
occurrence taught that the first did not.

## L8 — Zero-thickness lumped ports activate zero cells. That is physics, not a bug.

**What happened.** A guard demanded a non-zero solver `Active cells:` count for
the lumped port on every arm. A zero-thickness lumped port is a **surface
impedance owning no cell volume**, so `Active cells: 0` is the correct reading
on such an arm and always was. The "repair" applied to satisfy the guard broke a
load that had been working, and the launch at port 1 had no metal to excite into
until it was moved to an MSLPort (`--port1-api mslport`), which draws its own
feed.

**What it cost.** One working port arm broken to satisfy a check that was
wrong, plus a launch that reported clean numbers while exciting nothing.

**The rule.** A guard must be calibrated against a known-good run before it is
allowed to condemn one. When a check fails a model that has worked, suspect the
check first. Zero active cells on a zero-thickness lumped port is physics:
record which arms are permitted to read zero explicitly instead of demanding
that none do.

## L9 — An anchor is circular if it is derived from the machinery under test

**What happened.** `0.34465` was carried as the reference `|S11|` for the
referee's comparison. It had been produced by the same extraction machinery the
referee exists to check, so agreement with it was guaranteed by construction
rather than by physics. It is retracted. Retracting it exposed a second anchor
hiding behind it — `0.345475`, produced the same way — so deleting the first
resolved nothing.

**What it cost.** The comparison the referee was built to make was vacuous for
as long as the number was believed, and the retraction had to be done twice.

**The rule.** Before quoting a number as a reference, ask what produced it. If
the answer is the thing under test, it is not a reference, whatever it is
called. And when you retract one, audit its siblings in the same pass: a
circular anchor rarely travels alone.

## L10 — A guard whose threshold is a literal will eventually reject correct geometry

**What happened.** The port-attachment check demanded a hard-coded floor of
**500 PEC edges**, derived as 504 expected faces minus 4 slack. After the
one-cell shift the mslport arm expects only **496 faces**, because the
MSLPort's own feed box occupies that cell; 496 is below a floor of 500, so the
fixed threshold would have failed a **correct** geometry, and the failure
would have pointed at the geometry rather than at the guard.

**What it cost.** A latent green-model red-build: the next engineer to touch the
offset would have been sent into the mesh instead of into the check.

**The rule.** Derive thresholds from the model, per arm — expected faces minus a
stated slack, which yields 500 on the lumped arms and 492 on the mslport arm —
and make the expectation the thing written down. A literal is a fact about one
geometry; write the derivation so the fact stays true when the geometry
legitimately changes.

## L11 — A priority tie in CSXCAD does not raise; it deletes geometry

**What happened.** CSXCAD resolves overlapping primitives by `priority`, and a
**tie is resolved by dropping one of them, silently**. openEMS's own `MSLPort`
leaves `priority` at its default of `0` (`infra/openems/reference/ports.py:107`,
consumed at `:349` when the port's metal box is added), which is exactly the
priority a substrate top face carries. On the referee the port's feed box sat
coplanar with the substrate at `z_strip`, lost the tie and vanished: no
exception, no warning on stdout, a fully populated result set, and a `|S11|` of
-8.54 dB that reads as a well-matched line and is in fact a measurement of
nothing. The fix is one explicit number — `STRIP_PRIORITY = 10`
(`docker/openems/build_A_referee.py:388`), chosen because any value above the
CSXCAD default `0` wins and deliberately not tuned — passed through to
`FDTD.AddMSLPort(..., priority=...)` (`:1213-1215`). The drop is visible only in
the CSXCAD echo, as `Unused primitive (type: Box) ... property: port1_feed`
(`:1036-1038`).

**What it cost.** Three days on the openEMS side, and a model that measured
nothing being read as a model that measured something — DR-41.

**The rule.** Set `priority` explicitly on every primitive that can be coplanar
with a substrate or with another primitive; an inherited default is a tie
waiting to happen. More generally: a failure mode that cannot raise must be
caught by an assertion on the **physical observable** — total energy in the
box, field amplitude in the gap, the trace itself — and never inferred from the
absence of an exception. Silence is not success; for a silent-drop mode,
silence is the symptom.

## L13 — A Trame `@ctrl.set` handler is a callback, not a coroutine host

**What happened.** The WaveDude play trigger in `server/poc_app.py` (`ctrl.play_toggle`) was written as an `async` handler that ran the animation loop inline and did not return until playback stopped. An async trigger that never returns blocks the client RPC: every subsequent button click and camera drag stops reaching the server. The animation still renders (the loop is inside the pending RPC and flushes per tick), which makes the symptom look like "the controls are dead but the picture is fine." That inversion is what makes the bug expensive: a live picture is read as proof that the server is healthy, so the investigation starts in the client's button state and event wiring instead of in the handler's return.

**The rule.** Long-running work belongs in `asyncio.create_task`, and the trigger must return. Corollary: any handler that clears `state.playing` must also set `state.play_label = "play"` — otherwise the button sticks on "pause" the next time the task exits from a path other than the play-toggle trigger.

**Amendment 2026-11-11 — the logic layer was testable all along.** Only `Plotter.render()` segfaults headless; the plotter, mesh add, view setup, and `plotter_ui(mode='server')` all run. Double `render()` and the Trame handler logic is CI-testable — the visualizer is no longer an untested surface. The fix landed as `5e0758e` and the test as `7d53f65` (`tests/test_poc_playback.py`), and the test doubles `pyvista.Plotter.render` rather than skipping: a skipped test proves nothing in CI, while a crash is the container telling you the test is wrong. This is the same error as the E7 ledger row's "no pyvista/vtk/trame in this container" claim — an environment limitation generalised by one level too far, hiding a surface that could have been tested all along. Test the layer below the one that fails, and state the limitation as narrowly as the observation supports.

**Numbering note.** This entry is L13 as assigned. The addendum previously ended at L11 and no L12 entry exists in this file; the gap is recorded rather than closed by renumbering, because numbers in this sequence are never reused.
