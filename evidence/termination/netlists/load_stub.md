# `load_stub.json` — a quarter-wave shorted stub, i.e. an OPEN at the design tone

The document next to this note (`load_stub.json`) is the termination of
`STRUCTURES["C"]` in `../../run_build_A.py`. It is read by
`emfit.netlist.parse_netlist`, so it may not carry comments: that parser allows
exactly three top-level fields (`elements`, `name`, `nodes`) and rejects
anything else rather than ignoring it. The physics therefore lives here, and the
arithmetic that produced `tau` is in the `STRUCTURES["C"]` row that uses it.

## What the circuit is

| element | kind | nodes     | meaning                                     |
|---------|------|-----------|---------------------------------------------|
| `stub`  | `T`  | `1` → `2` | lossless line, `z0 = 50 ohm`, one-way `tau` |
| `short` | `V`  | `2` → `0` | ideal short (`value = 0.0`) at the far end  |

Node `1` is the cut (the solver's termination node), node `0` is ground. So the
cut sees a **shorted stub of delay `tau` to ground**.

## Why that is an OPEN, not a short

A lossless line of delay `tau`, shorted at its far end, presents at its input

    Zin(f) = j z0 tan(2 pi f tau)

`tau` is chosen as a quarter period at the design tone
`f0 = 5.827786408327286e9 Hz` (the `geometry.f` the A arm reports):

    tau = 1 / (4 f0) = 42.89793456444743 ps

At that frequency `2 pi f0 tau = pi/2`, `tan(pi/2) -> inf`, so

    Zin(f0) = OPEN

**The far end is shorted and the cut is nevertheless open.** That is the whole
point of the document and it is not a bug: a short-circuited quarter-wave line
is the classic impedance inverter, and `tan` is what makes a short at one end
look like an open at the other. The visible consequence at the measurement
plane is a **stopband**: the incident wave is fully reflected in phase, so
`|S11| -> 1` and `|S21| -> 0` (a notch at `f0`), where the matched 50 ohm arm A
has `|S11| ~ 0` and `|S21| ~ 1`.

## Do not "fix" the open

Any edit whose stated purpose is to raise `|S21|` — replacing the `V` short with
a resistor, re-tuning `tau` away from `1/(4 f0)`, deleting the stub — destroys
the one thing this arm measures: that the cut *is* blocked when the termination
presented to it is an open, and that a real transmission line can synthesise
that open at a single tone without any resistive element anywhere in the
circuit. A run whose `|S21|` does not collapse is a finding to be reported, not
a result to be repaired.

## Why the stub is a `T` and not a lumped element

`tau` is a quarter period at the tone the artefact reports; the flux of the
structure is what the arm measures, so the stub's delay has to be carried as a
delay rather than approximated by a one-pole ladder whose phase would be wrong
by `O((omega dt)^2)` per segment. The method-of-characteristics `T` element
carries the delay exactly and losslessly, so the depth of the notch is limited
by the arm's own resolution and not by the discretisation of the stub.

## `tau` against the solver's step

`tau / dt` is **not** an integer: `dt = 7.626299478123987e-13 s` gives
`tau/dt = 56.25`. The line's history lookup therefore runs its
linear-interpolation path with weight `0.25` (`emfit.spice._line_history`:
`back = tau/dt - 1`, `weight = back - floor(back)`), which is unbiased and errs
by `O((dS/dt * dt)^2)` inside one sample — it does not shift the realised delay
by a quarter of a step. Nothing was snapped to 56 samples: `56 dt = 42.707 ps`
is 0.44 % short of `tau` and would move the notch off the tone.
