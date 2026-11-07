# Ghost-wave forensics: measuring the load plane directly

**2026-11-07 · dispatch `field-dump-and-ghost-wave-2026-11-07` · status: instrumentation only, the run has NOT been executed**

## The short version

We set out to hunt a ghost wave and did not find one.

The far end of the line is already quiet. The artefact we already have says that only 0.27 % of the power comes back from beyond the load. What is loud is the other side of the ledger: the transmitted wave is reporting |S21| = 0.7644 where the arithmetic only allows 0.6545.

So this dispatch is not a ghost hunt. It is a change of witness. We stop asking the wave decomposition what happened and start asking the fields directly.

## What the numbers we already have say

From `build_A_50ohm_p51.json`, the run that predates this work. Column three is what a 50 ohm series load sitting in a 47.364 ohm line has to produce, worked out on paper.

| quantity | measured | required for a 50 ohm load |
| --- | --- | --- |
| Gamma at plane 51 | -0.02553431 - j0.04555135 | no specific value |
| magnitude of Gamma | 0.0522200 | no specific value |
| phase of Gamma | -119.273 deg | no specific value |
| power returning from beyond the load | 0.27 % | no specific value |
| magnitude of S11 at the reference plane | 0.32556487 | 0.34547 |
| magnitude of S21 | 0.76441849 | 0.65453 |
| S11 squared plus S21 squared | 0.690328 | 1.000000 for a lossless two-port |
| power actually absorbed in the load | 0.309672 | 0.452247 |

Now read a resistance out of that table three different ways.

| route | implied load resistance |
| --- | --- |
| inverting the S11 magnitude | 45.727 ohm |
| inverting the S21 magnitude | 29.194 ohm |
| inverting the power absorbed | 22.439 ohm, or 399.901 ohm on the conjugate branch |
| what we asked the model to build | 50 ohm |

All three routes say the same thing qualitatively: less than 50. None of them says the same thing quantitatively. They span a factor of two.

That combination is the signature of a broken measurement, not a broken component. If the resistor really were 22 ohm, then |S11| would have to be around 0.40, and it is not: it is 0.3256. The two numbers cannot both describe the same load. One of them is being computed from a wave that is not the wave we think it is.

## The name is now a liability

"Ghost wave" commits us to a story in which a reflection off the far end comes back and poisons everything. The one number in that table which is not surprising is the reflection at plane 51. It is small. It should be small. A well-terminated far end is exactly what we built, and the far end is behaving.

So keep the dispatch name, it is in the filename and the log, but do not let it steer the diagnosis. Read the bracket G1 again: "the load edges are fine AND S21 reveals a massive far-end reflection". The first half is still plausible. The second half is now the less likely of the two branches.

G2, "the load edges are shorting", is still live, and this new dump settles it in a single run.

What the small Gamma does rule out: a grossly reflective far end throwing power back at us. What it does not rule out: a standing wave between the reference plane and the load, an error in where the reference plane is, or a transmitted-wave extraction that is simply reporting too much transmission. Those three are the live suspects now.

## What we built

Three new channels of data, all behind flags that default to off, so that every existing run produces byte-identical output to before.

### One: the voltage on each individual load edge

`--dump-load-edges`, and matching keyword `load_edge_dump`.

The load is stamped onto a set of edges. Until now we only ever looked at the load as one lumped element. This records the complex voltage on every single one of those edges, at the operating frequency, separately.

Output lands in the JSON under `load_edge_dump`: how many edges there are, which edges they are, where they sit along the line in metres, and the complex voltage on each one as re, im, magnitude and phase. If any value is not finite it is written as null and a flag `nonfinite_replaced` is set, because a null in that payload is a finding, not a formatting accident.

This is the direct test for G2. If the load edges are shorting, the voltage on them collapses and we see it immediately, per edge, without any wave decomposition in the way.

### Two: the phasors on the S21 plane

`--dump-fields`, and matching keyword `field_snapshot`.

The S21 plane already had voltage and current computed on it during extraction. Those were being consumed and thrown away. They are now also stored: position along the line, and voltage, current, and the forward and backward wave amplitudes, each as re and im.

Output lands in the JSON under `s21_plane`.

### Three: the field state at the last timestep

The same flag also stores the full electric and magnetic field arrays as they stood on the final timestep, plus the timestep index, the grid dimensions and the cell size. These go into a separate compressed `.npz` next to the JSON, never into the JSON itself, because they are large and they are not numbers a human reads.

## Why there is no per-edge current channel

Deliberate omission, and worth writing down so that nobody adds it later thinking it was an oversight.

On this stamp the load is resistive and every load edge carries the same conductance, one over N times R. So the current on edge k is just the voltage on edge k multiplied by a constant we already know exactly. Recording the current would add a channel that contains no information the voltage does not already contain.

The interesting quantity is not the current. It is the spread of the voltage across the load edges. If all N edges carry the same voltage, the stamp is behaving as one lumped element and G2 is dead. If they do not, the stamp is not doing what the model says it does, and the spread tells us which edges are wrong. That spread is the measurement.

## Two ways to get the load resistance without trusting the wave decomposition

This is the real prize, and it is why both dumps are needed in the same run.

Route A. At plane 51 we now have voltage and current as phasors. Their ratio is an impedance. No S-parameters, no reference division, no forward and backward wave separation. Just V over I at a plane, which is the oldest measurement in the subject.

Route B. The load edge voltages give the voltage across the element. The current through the element is the sum of the per-edge currents, and each per-edge current is the per-edge voltage times the known conductance. So the ratio is available there too, entirely inside the load.

If Route A and Route B agree with each other, and agree with 50 ohms, then the load is fine and the S-parameter extraction is what is lying to us. If they agree with each other and disagree with 50, the load genuinely is not 50 and everything downstream is correct and we have been chasing the wrong thing entirely. If they disagree with each other, the problem is in how the fields are being sampled, and we will know that too.

Every one of those outcomes is useful. That is the point of running the two together.

## Cost

The field arrays are flat one-dimensional. At this grid the electric field is 1,050,754 edges at 8 bytes each, 8.41 MB, and the magnetic field is 1,028,936 faces, 8.23 MB. So a snapshot pair is about 16.6 MB in memory. Compressed on disk it should come down to a few megabytes, because most of the domain is quiet.

Runtime is the same as a normal run. Nothing here changes the timestepping. Expect the usual figure, on the order of twenty minutes, within the two gigabyte memory ceiling.

## How to run it

```
sh evidence/termination/run_ghost_wave_test.sh
```

The script resolves its own location, so it works from any directory. It is a one-shot: it enables plane capture through the environment variable `EMFIT_PLANE_CAPTURE=1`, and it writes two files, a JSON and a sibling `.npz` with the same stem plus `_fields`.

It has deliberately not been run. The numbers above are all from the existing artefact, not from this run.

## Decision rule, written before the result

State the rule now so that we cannot rationalise afterwards.

If the load edge voltages are uniform and Route A and Route B both land on 50 ohm, then the load is innocent and the fault is in the transmitted-wave extraction. Next question becomes the S21 plane, its position relative to the reference plane, and the reference exponent.

If the load edge voltages are uniform but Route A and Route B both land well away from 50, then the model is being told to build something other than what we think, and the number to look at is the conductance the stamp actually receives.

If the load edge voltages are not uniform, G2 is confirmed in some form and the edges themselves are the fault, and the per-edge spread tells us where.

If Route A and Route B disagree, the sampling of the fields is the fault and neither the load nor the extraction is to blame.

## What this does not do

It does not fix anything. It is instrumentation. No physics was changed, no maths was changed, and every pre-existing line in both modified files is untouched; the code changes are additions behind flags that default to off.

It does not validate S11. The existing artefact still carries `validation_status` of UNVALIDATED and a null reference, so it is a loaded run compared against nothing. That is unchanged by this work.

It does not produce the pictures. It produces the numbers the pictures have to be drawn from. Renders come after, and only from numbers we trust.

## Status and open items

Committed in this dispatch: the two dumps and their flags, the runner script, and this document.

Open. The run itself is not executed. When it is, the first three things to read are the spread of the load edge voltages, the ratio of voltage to current at plane 51, and the ratio of voltage to current inside the load. Everything else in the payload is context for those three.

Also open, and unchanged from before: the reference exponent of 1.7916666666666667 on an unvalidated S11, the load plane at index 50 and the S21 plane at index 51 with an offset of one cell, and a last clean plane at 65.
