# `load_stub.json` — a quarter-wave shorted stub, i.e. an OPEN at the ANALYSED tone

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
cut sees a **shorted stub of delay `tau` to ground**. The arm also carries
`load_ohm = 50`, and that number is *not* the termination: it is the number that
frees the cut before the netlist replaces it, exactly as in arm A.

### Why a shorted quarter-wave line is an OPEN

A lossless line of delay `tau`, shorted at its far end, presents at its input

    Zin(f) = j z0 tan(2 pi f tau)

`tau` is the quarter period at one specific tone `f0` (`tau = 1 / (4 f0)`, see
the next section — *which* `f0` is the whole point of this note). At that
frequency `2 pi f0 tau = pi/2`, `tan(pi/2) -> inf`, so

    Zin(f0) = OPEN

**The far end is shorted and the cut is nevertheless open.** That is the whole
point of the document and it is not a bug: a short-circuited quarter-wave line
is the classic impedance inverter, and `tan` is what makes a short at one end
look like an open at the other. The visible consequence at the measurement
plane is a **stopband**: the incident wave is fully reflected in phase, so
`|S11| -> 1` and `|S21| -> 0` (a notch at `f0`), where the matched 50 ohm arm A
has `|S11| ~ 0` and `|S21| ~ 1`.

### Why the stub is a `T` and not a lumped element

The flux of the structure is what the arm measures, so the stub's delay has to
be carried as a delay rather than approximated by a one-pole ladder whose phase
would be wrong by `O((omega dt)^2)` per segment. The method-of-characteristics
`T` element carries the delay exactly and losslessly, so the depth of the notch
is limited by the arm's own resolution and not by the discretisation of the
stub.

## The delay is a tone, not a constant

`stub` declares the tone its delay was cut for, beside the delay itself:

    quarter_wave_hz = 5827786408.327286      (Hz, the design tone)
    tau             = 4.289793456444743e-11  (s, = 42.89793456444743 ps)

`quarter_wave_hz` is the only field a `T` may carry beside `z0`/`tau`
(`emfit/netlist.py`, `_ELEMENT_FIELDS["T"]`); `len_mm`/`eps_eff` are
deliberately absent, because a delay derived from geometry here would be a
second source of truth for the one number the line is made of.

**The declaration is checked, at staging, RELATIVELY.** `emfit.netlist`
(`_QUARTER_WAVE_RTOL = 1e-6`) requires

    |tau - quarter_wave_tau(quarter_wave_hz)| <= 1e-6 * quarter_wave_tau(quarter_wave_hz)

with `quarter_wave_tau(f) = 1 / (4 f)` the single definition of the tie between
the two numbers. A document that fails it is refused with a `NetlistError`
naming the element, the `tau` it wrote and the `quarter_wave_tau` it should have
written. The tolerance is relative for a reason: `tau` is ~1e-11 s, so an
absolute 1e-6 s would accept every tone in the band, while 1e-6 relative is
loose enough that a delay written down as a rounded float still agrees with its
own tone and tight enough that the smallest real retune in this tree (3 %)
cannot pass. **A `T` may not declare one tone and carry another's delay** —
without the check a file could say "cut for 5.83 GHz" while carrying `4.16e-11`
s, and every reader (and every re-derivation from the declared tone) would be
reading a lie.

**The declaration is also honoured, and that is what makes it worth having.**
`parse_netlist(source, *, f_hz=None)` takes the tone the caller will actually
analyse at:

* `f_hz=None` (the default): every `tau` is delivered exactly as written —
  byte-compatible with every caller written before the parameter existed.
* `f_hz=<tone>`: every `T` that declared a tone is DELIVERED
  `quarter_wave_tau(f_hz)`, the quarter-wave delay of *that* tone, instead of
  the delay in the file. A `T` that declares no tone is never touched; nothing
  can know what its delay was cut for.

`emfit.studies.microstrip_wave` parses this document with `f_hz=f0`, its own
analysed tone, so the delivered delay is the quarter-wave delay of the tone the
run uses and `geometry.f`, `s11`, `s21` and the stub finally describe the same
frequency.

Both numbers are recorded. `Netlist.quarter_wave` is a tuple with one record per
declaring `T`, in element order, with keys `name`, `declared_hz`,
`tau_document_s`, `tau_s`, `f_hz` (`tau_s` is what the parse actually
delivered). `emfit.studies._quarter_wave_retune` adds `declared_tone_retuned`
and sets `f_hz` to the run's tone, and `microstrip_wave` copies the list into
`geometry["load_netlist_quarter_wave"]` — **only when it is non-empty**, so the
geometry of every run whose netlist declares no tone is unchanged. For the
default CW run of this arm the single record is

```json
{"name": "stub",
 "declared_hz": 5827786408.327286,
 "tau_document_s": 4.289793456444743e-11,
 "tau_s": 4.289793456444743e-11,
 "f_hz": 5827786408.327286,
 "declared_tone_retuned": false}
```

and for a `--vis-dump` run of the same document `tau_s` is
`4.159799715340357e-11`, `f_hz` is `6009904733.587513` and
`declared_tone_retuned` is `true`.

A moved tone is announced on **stderr** by `_quarter_wave_retune` — a banner
naming both tones, both delays and both `tau/dt` — and it **never raises**. The
run about to be launched is self-consistent, because `tau` is the quarter-wave
delay of the tone that run uses; raising would refuse a correct run *and*
destroy the forensic record of a tone that moved, which is the one thing the
check exists to keep. The move test is relative:
`|declared_hz - f_hz| > 1e-9 * max(declared_hz, f_hz)`, about 6 Hz here, far
below the ~0.55 GHz bin spacing. The artefact itself repeats all of this in
`load_netlist.tau_note`.

## Two paths, two analysed tones

A run is never analysed at `f_target`. `emfit.studies.snapped_tone(dt, nsteps,
n_warm, f_target) -> (f0, n_warm, n_acc)` is the one home of the rule:

    n_acc = nsteps - n_warm,        span = n_acc * dt
    k     = max(1, round(f_target * span))
    f0    = k / span

`n_warm` defaults to `nsteps // 4`, but a PULSE run passes `0`: a wavelet is the
whole record and has no tone to settle. That is the entire reason the tone of
this arm depends on more than `f_target`.

At the defaults (`nsteps = 2400`, `f_target = 6.0e9` = `MS_F_TARGET`,
`dt = 7.626299478123987e-13` s on this mesh):

| path | `n_warm` | `n_acc` | `span` (s) | `f_target*span` | `k` | `f0` | `tau = 1/(4 f0)` | `tau/dt` |
|------|----------|---------|------------|-----------------|-----|------|------------------|----------|
| CW (default) | 600 (`nsteps//4`) | 1800 | 1.3727339060623177e-9 | 8.236… | 8 | **5827786408.327286 Hz** (5.827786408328 GHz) | `4.289793456444743e-11` s (42.8979 ps) | **56.25** |
| `--vis-dump` / pulse | 0 | 2400 | 1.8303118747497569e-9 | 10.98… | 11 | **6009904733.587513 Hz** (6.009904734 GHz) | `4.159799715340357e-11` s (41.598 ps) | **54.5454…** |

The two tones are **3.1 % apart** (~3 %), so a stub cut for the first is *not* a
quarter wave at the second. The CW tone is `VIS_F_REF_HZ`
(`5827786408.327286`) exactly, which is why that is the `geometry.f` every
banked A artefact reports; the pulse path lands on a different bin of a
different window.

**`evidence/termination/run_build_A.py --vis-dump` silently changes the ANALYSIS
tone, not just the visualisation.** It forces `excite="pulse"` (with
`f_pulse`, `s21_plane=None`, `load_trace=True`) on the run it dumps, and the
pulse path sets `n_warm = 0`, so that run's notch sits at ITS tone — 6.0099 GHz
at the defaults — and **not** at `VIS_F_REF_HZ` (5.8278 GHz). Two further
numbers in a dump are *not* that tone and must not be read as it: the recorded
reference frequency is unconditionally `VIS_F_REF_HZ`, and the wavelet is struck
at `VIS_F_PULSE_HZ = 15.0e9`. A `--vis-dump` run is also a visual run in
general: `s21_plane` is dropped and its `s21`/AC numbers are not a measurement.

## `tau` against the solver's step

On this mesh (`cell = 0.4` mm, `dt = 7.626299478123987e-13` s) neither ratio is
an integer: `56.25` on the CW path, `54.5454…` on the pulse path. The line's
history lookup therefore runs its **linear-interpolation** path
(`emfit.spice._line_history`): `back = tau/dt - 1` (55.25, 53.5454…),
`whole = floor(back)`, `weight = back - whole` (**0.25** and **0.5454…**), and

    sample = (1 - weight) * s[newer] + weight * s[older]

Interpolation errs by `O((dS/dt * dt)^2)` inside one sample, does not bias the
delay, and still lands on the exact sample when `tau/dt` happens to be whole.
Rounding to a sample was rejected: it shifts the phase velocity by up to half a
step per pass and compounds every round trip. Nothing was snapped to 56 samples:
`56 dt = 42.70727707749433 ps` is **0.44 %** short of the CW `tau` and would pull
the notch off the tone.

## Traps and do-nots

* **Do not "fix" the open.** Any edit whose stated purpose is to raise `|S21|` —
  replacing the `V` short with a resistor, re-tuning `tau` away from `1/(4 f0)`,
  deleting the stub — destroys the one thing this arm measures: that the cut
  *is* blocked when the termination presented to it is an open, and that a real
  transmission line can synthesise that open at a single tone without any
  resistive element anywhere in the circuit. A run whose `|S21|` does not
  collapse is a finding to be reported, not a result to be repaired.
* **Do not hard-code `1/(4 * VIS_F_REF_HZ)`.** It is a second source of truth
  for the tone, and it has already drifted once: the CW default resolves to
  `VIS_F_REF_HZ` only because `n_warm = nsteps//4` with `nsteps = 2400` and this
  mesh's `dt`; change any of them, or take the pulse path, and the constant is
  simply the wrong tone. `quarter_wave_tau(snapped_tone(...))` is the rule.
* **Do not delete `quarter_wave_hz`.** Without it `parse_netlist(f_hz=...)` has
  nothing to re-derive a delay *from* (a `T` with no declaration is delivered
  verbatim, for ever), `geometry["load_netlist_quarter_wave"]` disappears from
  the artefact, and the next retune becomes silent and unknowable. Its absence
  in an artefact means "no tone was declared", never "the tone did not move".
* **Do not edit `tau` and `quarter_wave_hz` independently.** They are checked
  against each other at 1e-6 relative; changing the tone without re-writing
  `tau = quarter_wave_tau(tone)` makes this document unparseable, and the run is
  refused before the mesh exists.
* **Do not hand `microstrip_wave` an already-parsed `Netlist`.** A frozen
  `TransmissionLine` keeps the `tau` it was parsed with, so the stub is cut for
  the DECLARED tone while the run analyses `f0`, and `_quarter_wave_retune` can
  only *warn*, not repair. `run_build_A.py` therefore passes the JSON document,
  not the parsed object.
* **Do not treat the stderr banner as a failure.** A moved tone is reported, not
  raised: the launched run is consistent by construction.
* **Do not read a `--vis-dump` artefact's reference frequency as its analysis
  tone.** The stub, the notch and `geometry.f` follow the snapped tone of that
  run; the reference frequency is a fixed label of the geometry.
* **Do not snap `tau/dt` to a whole number** to avoid the interpolation path.
  0.44 % of a quarter-wave delay is a visible shift of the notch.
* **Do not move `nsteps`, `n_warm`, `dt_scale` or `excite` casually.** Every one
  of them changes `span`, hence `k`, hence `f0`, hence the `tau` the stub needs
  (`k = max(1, round(...))`, so a short window also has a floor at bin 1).
* **Do not add fields to `load_stub.json`.** The parser accepts `kind`, `name`,
  `nodes`, `z0`, `tau`, `quarter_wave_hz` on a `T` and nothing else, and three
  top-level fields; an unknown key is a refusal, not a warning.
