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

## Is the stub actually doing anything? (plain-cut control)

A stub that changes nothing and a stub that is silently ignored look the same
from a single arm, so arm C was re-run beside its own control: the same mesh,
the same port planes, the same 50 ohm load at 20 mm, the same `--nsteps 2400`
and `--n-warm 600` (that last one for the CW pair; the pulse pair discussed
below runs with `n_warm = 0`, equally on both its arms), with the netlist as the
**only** difference. The plain cut
is `--structure A` because `run_build_A.py` resolves a structure's netlist
unconditionally (`args.netlist is None` -> the row's own netlist), so "C with no
netlist" cannot be expressed; A's row carries no `netlist` key and is otherwise
byte-identical in `build_kwargs`.

| run | command | termination | \|S11\| (two-wave B/A) | \|S11\| (one-wave station fit) | \|S21\| | \|S11\|²+\|S21\|² | passivity | wall |
|---|---|---|---|---|---|---|---|---|
| plain cut (arm A, banked as `artifacts/build_C_plain_cut.json`) | `--structure A --out artifacts/build_C_plain_cut.json --mem-ceiling-mb 500` | lumped `series_r` 50 ohm | 0.32586326 | 0.32613492 | 0.76170542 (arg 5.7752°) | 0.68638202 | ok | 38.94 s (`meta.wall_total_s`; 39.87 s outer) |
| stub (arm C, banked as `artifacts/build_C_stub.json`) | `--structure C --out artifacts/build_C_stub.json --mem-ceiling-mb 500` | netlist `load_stub.json` (T stub + V short) | 0.85595644 | 0.85562154 | 0.63612344 (arg 47.5181°) | 1.13731446 | FAIL_PASSIVITY | 49.35 s (`meta.wall_total_s`; 49.53 s outer) |
| stub, pulse-excited (arm C + `--vis-dump`, banked as `artifacts/build_C_stub_pulse.json`) | `--structure C --out artifacts/build_C_stub_pulse.json --vis-dump --mem-ceiling-mb 500` | netlist `load_stub.json` (T stub + V short), tau re-derived for 6.009905 GHz | 0.69988671 | 0.70128913 | 1.02457909 (arg 2.8588°) | 1.53960372 | FAIL_PASSIVITY | 48.1 s (stdout wall; 48.49 s outer) |
| plain cut, pulse-excited (arm A + `--vis-dump`, banked as `artifacts/build_C_plain_cut_pulse.json`) | `--structure A --out artifacts/build_C_plain_cut_pulse.json --vis-dump artifacts/vis_dump_C_plain_cut_pulse.npz --mem-ceiling-mb 500` | lumped `series_r` 50 ohm | 0.32723831 | 0.32753812 | 1.02173670 (arg 3.1127°) | 1.15103078 | FAIL_PASSIVITY | 41.09 s (`meta.wall_total_s`; 41.5 s outer) |

Both CW runs: `cells=62x212x22 = 289168`, `nsteps=2400`, `n_warm=600`,
`geometry.f = 5827786408.327286 Hz` (5.827786 GHz, the bin k=8 the CW path
snaps to), `s21_plane_index = 51`, peak RSS 312.3 MB / 312.0 MB.

The pulse rows are NOT that tone. `--vis-dump` forces `excite='pulse'`
(`VIS: excite='pulse' at 15.000 GHz: the dump is the march of one packet, so the
excitation is overridden for this run`), hence `n_warm = 0` and
`geometry.f = 6009904733.587513 Hz` (6.009905 GHz, bin k=11 of the longer span).
Because the document declares `quarter_wave_hz = 5827786408.327286 Hz`, the
library's quarter-wave check FIRED on stderr:

```
emfit.studies.microstrip_wave: QUARTER-WAVE TONE MISMATCH
  netlist element 'stub' declares a quarter-wave line
  at 5.827786 GHz, but this run is ANALYSED at
  6.009905 GHz.
  Its tau has been re-derived for the tone in use: 4.289793456444743e-11 s -> 4.159799715340357e-11 s (tau/dt = 56.25 -> 54.54545454545455).
```

The delay simulated is therefore 41.598 ps, not 42.898 ps: the stub was a
quarter wave at the tone it was actually run at. `geometry.load_netlist_quarter_wave`
is **present** on that artefact — `declared_hz = 5827786408.327286`,
`tau_document_s = 4.289793456444743e-11`, `tau_s = 4.159799715340357e-11`,
`f_hz = 6009904733.587513`, `declared_tone_retuned: true`. `cells=62x212x22`,
`nsteps=2400`, peak RSS 312.5 MB. The `--vis-dump` npz it wrote (16.5 MB,
`artifacts/vis_dump_C_stub.npz`) proved the pulse path ran and was then
**deleted**, not banked: what this section needs is the S-parameter row, not a
16 MB time series.

The fourth row is the pulse row's own control, and it exists now: arm A with the
same `--vis-dump`, so the SAME tone. `label = A` (the expected, harmless
`WARNING: the --out filename names arm C but this run is arm A (50 ohm)`), no
`--netlist` at all — `run.kwargs` has no `load_netlist` key and `loads` is the
lumped `series_r` 50 ohm — `excite = 'pulse'`, `n_warm = 0.0`, `n_acc = 2400`,
`geometry.f = 6009904733.587513 Hz` (the stub row's tone to the last digit).
`geometry.load_netlist_quarter_wave` is **ABSENT**, which is the compatibility
property the writer must keep: no netlist, no declared tone, no key. Its own
`--vis-dump` npz (16.5 MB, `artifacts/vis_dump_C_plain_cut_pulse.npz`) was
also **deleted**. `cells=62x212x22`, `nsteps=2400`, peak RSS 312.5 MB.

**Verdict: the stub is doing something, and a large amount of it.** The two
branches of the control were: (a) if the stub arm's |S11| reproduces the plain
cut's, the netlist is not reaching the field update and the arm says nothing
about a stub; (b) if it moves, the netlist is on the cut and the arm's numbers
are the stub's. This is branch (b), decisively: |S11| moves 0.3259 -> 0.8560
(+0.53, and the phase -101.42° -> -116.39°), |S21| collapses 0.7617 -> 0.6361
and its phase swings 5.78° -> 47.52°. A short-circuited quarter-wave line is an
open at the analysed tone, so the cut is expected to block and reflect; a plain
50 ohm resistor at the same station does not. The pulse pair repeats the
|S11| half of that at its own tone (below); its |S21| half does not, for a reason
that belongs to the pulse extraction and not to the stub. The remembered |S11| ~ 0.732 for this arm is **not** reproduced at either
banked tone (0.8560 CW, 0.6999 pulse); see "What is measured, and what is
inferred" below — that figure is an inference, not a measurement.

### What is measured, and what is inferred

**Measured, same tone, controlled:** the CW pair (the first two rows). Both ran
at `geometry.f = 5827786408.327286 Hz` with the netlist as the only difference,
so |S11| 0.32586326 -> 0.85595644 and |S21| 0.76170542 -> 0.63612344 differ
because the termination differs and for no other reason. That is the whole of
the controlled evidence, and it is what licenses the verdict above.

**Measured, same tone, controlled — the pulse pair (third and fourth rows):**
both ran at `geometry.f = 6009904733.587513 Hz` (`excite='pulse'`, `n_warm = 0`),
same mesh, same port planes, the netlist the only difference. At that tone |S11|
**is 0.69988671 with the stub and 0.32723831 without** (+0.37265): the stub still
loads the line at the pulse tone too, and it does so in the same direction as at
the CW tone (plain 0.3259 -> stub 0.8560 there). That is now a controlled
statement and not a single-armed one.

**What the pulse pair does NOT give: transmission.** |S21| is 1.02457909 with the
stub and 1.02173670 without — it does not collapse at all, and both values are
**greater than 1**. The pulse configuration's own |S21| is over-unity, and its
passivity guard fails on the PLAIN CUT as well (1.15103078), where the CW plain
cut passes at 0.68638202. So the pulse arm separates "stub vs no stub" on |S11|
only; its |S21| column is not readable as transmission and is not quoted as one
anywhere in this document.

**Does the tone change alone explain 0.6999 vs 0.732? No.** The plain cut is
nearly tone-insensitive (|S11| 0.32586326 CW -> 0.32723831 pulse, +0.00137),
while the stub moves a lot (0.85595644 CW -> 0.69988671 pulse, -0.15607): the
stub's |S11| is strongly tone-dependent, so the tone is part of any explanation
of a stub number. But 0.732 lies BETWEEN the two measured stub values and equals
neither, and the new pair neither reproduces it nor identifies its provenance. The
pulse control changes the numbers again without closing the 0.732 question, and
the over-unity |S21| above is a second reason not to treat a pulse |S11| as a
certified value.

**Inferred, not measured:** the remembered |S11| ~ 0.732 matches neither measured
stub value (0.8560 CW, 0.6999 pulse), and the matched-tone pulse control did not
produce it either. The likeliest reading — explicitly an inference — is that 0.732 came
from a **pre-fix pulse run**: one where the stub still carried the CW tau
(4.289793456444743e-11 s, a quarter wave at 5.827786 GHz) while the run was
analysed at 6.009905 GHz, i.e. a mismatched-tone arm, with
`geometry.load_netlist_quarter_wave` silently dropped by the writer. That
artefact no longer exists, so the identification cannot be checked. What would
settle it: (i) a same-tone plain-cut pulse control (`--structure A ...
--vis-dump`) so the pulse row gets the control the CW row has, and (ii) a stub
run forced back to the pre-fix tau (a document declaring `quarter_wave_hz` at
5.827786 GHz while analysed at 6.009905 GHz is exactly what the fix now
prevents, so this needs a hand-edited tau) — which would either reproduce 0.732
or retire the figure.

**Passivity is the known-by-design trip, not a regression.** Arm C's
|S11|²+|S21|² = 1.1373 exceeds 1 + 4e-9 and the artefact keeps
`s11.validation_status = FAIL_PASSIVITY` with the failing numbers published
unclipped. A lossless reactance at the cut is not a passive *pair* of published
S-parameters — the guard is reporting exactly the configuration it was written
to catch, and it was neither silenced nor bypassed. The plain cut's CW 0.6864
(comfortably passive) is the same guard passing on the same mesh, which is what
makes the CW comparison readable: at that tone the difference is the
termination, not the extractor. The qualifier is new and it matters: at the
PULSE tone the guard fails on the PLAIN CUT too (1.15103078, from |S21| > 1), so
the guard is reporting the pulse extraction as well as the reactance there. That
is not a reason to relax it — it is the guard doing its job on a second,
different defect.

**The quarter-wave retune banner did NOT fire on the CW arm**, and on that run that is correct: the
document declares `quarter_wave_hz = 5827786408.327286 Hz` and the run is
analysed at `geometry.f = 5827786408.327286 Hz`, so `_quarter_wave_retune` saw
`moved = False` and wrote nothing to stderr. `geometry['load_netlist_quarter_wave']`
is therefore **absent** from `artifacts/build_C_stub.json`. That absence has TWO
possible causes, and separating them mattered: (a) the library writes the key
only when a declared tone exists (`emfit/studies.py:4270-4274`: one record per
declaring `T`, the key written iff the list is non-empty), and (b) — a defect,
now fixed — `run_build_A.py`'s scalar geometry sanitiser dropped the key even
when the library had produced it. The library was already correct; the writer
was not. Fixed in `evidence/termination/run_build_A.py` with a module-level
`quarter_wave_records()` helper that re-adds the list in BOTH artefact writers
(conditional, so a document declaring no tone still yields no key), pinned by
`tests/test_netlist.py::test_the_writer_carries_a_declared_tone_into_the_artefact`.
The CW artefact above predates that fix; a CW re-run (no `--vis-dump`) would now
carry the key with `tau_s == tau_document_s == 4.289793456444743e-11` and
`declared_tone_retuned: false` — stated as an expectation, not shown, because it
had not been re-run when this was written. The pulse row above is the run that
shows the key present with `true`. The declaration itself survives in
`run.kwargs.load_netlist`: `{"kind": "T", "name": "stub", "nodes": ["1","2"],
"quarter_wave_hz": 5827786408.327286, "tau": 4.289793456444743e-11, "z0": 50.0}`
plus `{"kind": "V", "name": "short", "nodes": ["2","0"], "value": 0.0}` — i.e.
tau = 42.89793456444743 ps = 1/(4 f0), the delay the run actually used. The comment at `run_build_A.py` that the pair is recorded in
`geometry.load_netlist_quarter_wave` was loose against THIS banked artefact — on
the non-moved path the pre-fix writer recorded nothing there, so the only
forensic record of the declared tone in this file is `run.kwargs.load_netlist`.
The writer fix above is what makes the comment true going forward.

Artefacts banked (all plain JSON; the first two carry no `vis_dump` npz and were
not pulse-excited, the two pulse runs' npz files were produced and deleted):

- `artifacts/build_C_plain_cut.json` — 19,442 bytes, label `A`, 38.94 s
- `artifacts/build_C_stub.json` — 21,379 bytes, label `C`, 49.35 s
- `artifacts/build_C_stub_pulse.json` — 22,225 bytes, label `C`, 48.1 s (the
  `--vis-dump` run; its 16.5 MB `artifacts/vis_dump_C_stub.npz` was deleted, see
  above)
- `artifacts/build_C_plain_cut_pulse.json` — 19,287 bytes, label `A`, 41.09 s
  (the matched-tone control; its 16.5 MB
  `artifacts/vis_dump_C_plain_cut_pulse.npz` was deleted)

Settings note: all four runs were given `--mem-ceiling-mb 500` because the container
they ran in caps memory at 512 MB; the flag is recorded in `meta` only and
changes no physics, and it was identical on both arms. The plain cut emitted
`WARNING: the --out filename names arm C but this run is arm A (50 ohm); the
label follows the run, not the filename.` — the label is `A` in the artefact,
the filename is the control's, and no number moves. Both CW runs also emitted the
library's `s11_at_plane is unavailable (valid = False)` RuntimeWarning, which is
expected for a probe one column past the load and does not touch the port-plane
`|S11|` quoted above.

