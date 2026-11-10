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
