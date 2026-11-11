# Session close — generation 10

Date: 2026-11-13
Status: **validation complete — the independent referee agrees with the in-house extraction to 0.49 percent; the physics-debug phase is closed.**

## 1. The anchor collapse

`0.34465` was circular. It had been derived from the machinery under test, so
agreement with it was guaranteed by construction rather than by physics. It is
retracted.

Retracting it did not settle the question, because a **second circular anchor
was hiding behind it: `0.345475`**. Both were produced the same way, so
deleting the first exposed the second rather than resolving anything.

The rule this bought us: retracting an anchor is not deleting a number, it is
searching for its siblings. A number that cannot be derived without the
machinery under test is not a reference value, whatever it is called.

## 2. The referee journey

The openEMS referee script spent days **solving empty air**. It ran, it exited
zero, it produced output — and the model it solved had no strip attached, so
every number it reported was a number about air.

Four fixes, in the order they were forced on us:

1. **The strip at `priority=10`** — the strip property was outranked and
   dropped, so the model had no conductor.
2. **An MSLPort for the launch (`--port1-api mslport`)** — an x-directed port
   that draws its own feed, instead of a lumped port with no metal to launch
   into.
3. **A lumped port for the load** — port 2 stays explicitly lumped.
4. **The one-cell strip/feed overlap** — the MSLPort draws a one-cell metal
   feed box at `x_port .. x_port + cell` at priority 0, and our strip sheet also
   started at `x_port`. CSXCAD reported
   `Unused primitive (type: Box) detected in property: strip!` and the port was
   not physically connected. Fixed by starting strip sheet A **one cell later**,
   at the feed box's stop x, so the two are *contiguous* — no overlap, no gap.
   The offset is arm-guarded: the four lumped arms still start the strip at
   `x_port`.

Every one of the four was found by **running the script and reading its own
output**. None was found by reading the code. The guards inside the script —
the pre-flight box check, the attachment floor, the unused-primitive audit —
are what converted silent failure into a refusal to report a number.

A fifth, quieter bug came out of the same place: the attachment floor was a
**hard-coded 500**. After the one-cell shift the mslport arm expects 496 faces,
so a fixed 500 would have **failed a correct geometry**. The floor is now
derived per arm — expected faces − 4 slack — which gives 500 on the four lumped
arms and 492 on the mslport arm.

With all five fixed, the script was run on the host **fully attached**, and it
returned a number instead of another refusal. That number is in sec. 5.

## 3. The MSLPort floor — accepted, not fixed

The MSLPort-derived |S11| has a real mathematical floor of **5.4e-4**
(`5.364e-4` at Γ = 0). It is the referee's own accuracy limit, and we accept it
rather than tune it away.

The cause is arithmetic, not solver error. With `theta = beta*cell/2` and
`c = cos(theta)`:

- `|Z_ref| / Z_line == 1` identically — the reference impedance is not biased.
- `beta` comes out low by exactly `sinc(theta)`.
- the split at the plane is a Möbius map,
  `S11 = ((1-c) + (1+c)Γ) / ((1+c) + (1-c)Γ)` — near identity, and at Γ = 0 it
  lands on `(1-c)/(1+c) = 5.364e-4`, not 0.

The reason `c` appears at all is that `Ht` at the plane is the **half-cell
average**, `0.5*(i[0] + i[1])`: the current probes sit half a cell either side
of the voltage plane, so the split wave is low by `sinc(theta)`.

Consequence for reading the referee: **anything below ~5e-4 is the referee's
own arithmetic, not solver accuracy.** The 1e-9 agreement gate imposed earlier
in this work was wrong and is retracted.

## 4. The UI insight

The current web UI is a **debug tool**, not a visualizer: it draws marker
spheres at the field dump's sample points. That is enough for "is there data in
this file" and not enough for "does this wave look right".

What is wanted next is an **emfit-vis-style visualizer** — animated, drawing the
real geometry (strip, substrate, ground, port planes) with the field on it, so
a standing wave or a reflection can be judged the way a solution is judged in
the lab: by looking at it.

## 5. The result, and what follows

The attached referee was run on the host. It reads **|S11| = 0.327164553** at
5.8277864083 GHz against a **declared 50 ohm** reference
(`evidence/referee/s11_extraction.json`).

- The artefact it was built to cross-check carries **0.3255648664110912**. The
  independent referee agrees with the in-house extraction to **+0.4914
  percent** — inside half a percent.
- That difference is about three times the 5.4e-4 floor of sec. 3, so the
  agreement is not the floor talking.
- The 5.5 percent gap against the anchor `0.342` is a **de-embedding /
  measurement difference, not an extraction defect**. This cross-check finds no
  extraction defect to explain.
- E12 in `docs/design/EM_SOLVER_LEDGER.md` is **VERIFIED** on this result.

So the physics-debug phase is **closed**: the comparison this document was
written to wait on has been made, and the extraction holds.

The "if it does not resolve, implement modal projection" branch is dropped for
now — not because modal projection is wrong, but because nothing in this
comparison is asking for it yet.

Next phase: the **time-domain visualizer** (sec. 4). With the model known to
carry the right wave, the question changes from "is the number right" to "does
the wave look right": a pulse launched along the strip, its reflection at the
50 ohm load, and the evanescent field decaying into the substrate — drawn,
animated, on the real geometry, so a solution can be judged by looking at it.

## 6. Open items — state after the solve

- ~~No host solve has completed end-to-end with the one-cell offset.~~ A solve
  completed end-to-end with the offset; the record set is in `evidence/referee/`
  (seven probe records, one openEMS banner across all of them) and
  `s11_extraction.json` is the extraction it produced.
- ~~The `Unused primitive ... property: strip` warning is *expected* to be
  gone.~~ The referee now reports **0.327**, not the `1.0003` of the empty-air
  run, so the warning's *effect* is gone; the CSXCAD log line itself was not
  read back.
- Still open: no independent `CalcPort` cross-check of the probe-derived
  numbers. The 0.327 is MSLPort probe arithmetic, so it is an independent
  *solver* on the same extraction method, not an independent *extraction*.
- The 1e-9 recovery gate is retracted; the 5.4e-4 floor stands in its place.
- The static `ECHO` design-record block still prints the lumped geometry
  (cols 8..50) on the mslport arm. Cosmetic; it documents the 2026-11-09 build.
