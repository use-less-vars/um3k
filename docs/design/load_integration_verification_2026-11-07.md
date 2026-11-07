# Load integration verification

**Date:** 2026-11-07
**Dispatch:** `load-integration-verification-2026-11-07`, authorised verbatim.
**Scope:** read-only. No `emfit/` edit, no FDTD, no electrostatic solve, no new artefact.
**Under test:** `evidence/termination/build_A_50ohm_p51_phasors.json`.
**Method:** every number below is measured from that file or read from the source at the cited
line. Nothing is re-simulated, and no fit is re-run except where the text says so.

## 0. Result in one sentence

The load is 50 ohm. It always was. The phase that made it look unphysical was measured at the
wrong plane: S11 is reported at the port plane, 42 cells upstream of the load, and a textbook
50 ohm series resistor seen from 42 cells away has a load-plane rotation of -85.8 deg, so a
reflection phase near -90 deg is what a correct 50 ohm load looks like from there. This artefact
records -100.5 deg. Measured where the load actually is, the phase is -24.4 deg and the
resistance is 50.35 ohm shunted by 0.38 pF.

## 1. What the artefact actually contains

Phasors and scalars, nothing else. 254 leaf paths, 216 numeric, 12 lists, and the largest array
in the file has length 9 while the grid has 335,808 cells and 1,050,754 edges. Top-level keys:
`ac, gamma_plane, geometry, line, meta, run, s11, s11_at_plane, s21, summary_line`.

Absent, by substring count over the whole file (all exactly 0): `m_sigma`, `edge_current`,
`edge_`, `conduct`, `impedance_matrix`, `zmat`, `e_field`, `snapshot`, `current`, `ez`, `hx`,
`hy`. There is no field data, no per-edge data, and no state dump anywhere in it.

## 2. V1 and V2 cannot fire

V1 was to be the per-edge current test (under 1 pct means the load discretisation is clean) and
V2 the failure side of it (over 1 pct means the cut is shorting across the gap). Both need the
current through the element and the voltage across it, edge by edge. Neither exists in the
artefact, and no amount of reading the file will produce them: `m_sigma` is allocated inside
`microstrip_wave` at `emfit/studies.py`:2871-2897 and is never returned, and `run_build_A.py`
persists no FDTD state.

So the honest verdict on V1 and V2 is **UNRUNNABLE**, not passed and not failed. The bracket
cannot be adjudicated with this artefact.

A substitute test is available and is run in section 6: at the load plane the element's own
impedance is the whole of the answer, so inverting the measured reflection coefficient there
tests the element as a lumped object. That is strictly weaker than the per-edge test - it cannot
see a single shorted edge, only a net effect - and it is not a substitute that may be reported as
V1 passing.

## 3. Geometry, in the numbers the pipeline uses

| quantity | value | source |
|---|---|---|
| cell | 0.0004 m | `Grid.uniform(nx,ny,nz,nx*cell,...)`, `emfit/studies.py`:2820-2823 |
| n_sub (cells through the substrate) | 4 | 1.6 mm / 4 |
| ix_port | 8 | `n_pml + n_ref`, `emfit/studies.py`:2830 |
| x_port | 0.0032 m | 8 * 0.0004 |
| ix_load | 50 | `floor(0.0200/0.0004 + 0.5)`, `emfit/studies.py`:2877 |
| x_load | 0.0200 m | column 50 |
| s21 plane | column 51, x 0.0204 m | one cell past the load |
| n_edges in the load | **9** | `geometry.loads[0].n_edges`, stamped at `emfit/studies.py`:2883-2886 |
| nx, ny, nz | 72, 212, 22 | n_pml 6, n_ref 2, n_line 64 |
| dt | 7.626299478123987e-13 s | `geometry.dt` |
| nsteps / n_warm / n_acc | 2400 / 600 / 1800 | recorded |

**Correction.** An earlier verbal summary said eight edges. It is nine. The stamped conductance
per edge is `1.0/(edges.size*value)`, so the two counts differ by 11 pct in the per-edge number
while the total stays 1/R either way.

## 4. V3 fires - twice over

**From the code.** The only de-embed distance in the pipeline is produced at
`emfit/studies.py`:3561-3562:

    x_port = float(ix_port*cell)
    deembed_distance = float(station_x[0] - x_port)

That is (26 minus 8) times 0.0004 = 18 cells = 0.0072 m exactly, bit for bit; the recorded
0.0072000000000000015 is that float64 expression. It is not hard-coded anywhere. Its only
consumer is `deembed_reflection(gamma_measured, beta, deembed_distance)` at
`emfit/studies.py`:3565, whose factor is `exp(-2j*beta*d)` (`emfit/ports.py`:1673).

**From the data, without trusting the code.** Regressing the phase of the per-station reflection
coefficient on x gives a line that crosses the recorded -100.499211556 deg at x = 0.003018 m,
which is 7.545 cells. The port plane is 8 cells, 0.0032 m. The agreement is 0.45 cell.

So the recorded S11 phase really is referenced to the port plane, and the de-embed really does
what its own code says it does. **V3 fires.**

**The amendment matters more than the confirmation.** 0.0072 m is not a load distance. The load
is 24 cells (0.0096 m) beyond station 0 and 42 cells (0.0168 m) beyond the port plane, and that
leg appears nowhere in the pipeline. Every earlier comparison of a port-plane phase against a
load-plane anchor therefore carried an unstated rotation of 2*beta*0.0168 = 445.7721 deg, or
85.7721 deg modulo 360, as an error. The number is confirmed; the meaning we had put on it was
ours and it was wrong.

## 5. Re-referencing the phase

With `Gamma(x) = Gamma_L * exp(+2j*beta*(x - x_L))`, inverting for the load plane;
d = x_load - x_port = 0.0168 m, start phase -100.499211556 deg:

| leg | cells | 2*beta*d at beta_fit | mod 360 | resulting load-plane phase |
|---|---|---|---|---|
| port to load | 42 | 445.7721 deg | 85.7721 deg | -14.7271 deg |
| port to station 0 | 18 | 191.0452 deg | 191.0452 deg | +90.5460 deg |
| station 0 to load | 24 | 254.7269 deg | 254.7269 deg | +154.2277 deg |

At beta_model (223.353067) the port-to-load leg gives 429.9855 deg, mod 360 = 69.9855 deg, and a
load-plane phase of -30.5137 deg. Only the 42-cell leg puts the phase anywhere near the 0 deg a
real series resistance requires.

**Checked directly, with no de-embed and no beta.** Station 8 is stored at x = 0.0200, exactly the
load column, so `(V - Z0*I)/(V + Z0*I)` there is already the load-plane reflection coefficient:

| Z0 used | abs(Gamma at load) | arg(Gamma at load) |
|---|---|---|
| 47.364066848 + j1.644980793 | 0.315998 | -24.4293 deg |
| 47.364066848 (real part) | 0.308772 | -21.7622 deg |
| 50.0 | 0.286025 | -23.9680 deg |

The re-referenced values, -14.7271 and -30.5137 deg, bracket the direct -24.4293 deg within 9.7
and 6.1 deg. Three routes, one answer: at the load plane the phase is about -24 deg.

**The methodological point.** At the load plane beta cancels. The direct measurement needs no
beta at all, which is why the beta ambiguity that dominated the previous dispatch stops mattering
for this question.

## 6. The load itself

Inverting the measured load-plane reflection coefficient to a resistance in parallel with a
capacitance - the topology the geometry implies, since the cut capacitance sits across the same
cut as the resistor:

| Z0 | R (ohm) | C (pF) | residual in amplitude | residual in phase |
|---|---|---|---|---|
| 47.364066848 real | 50.353567 | 0.377313 | 1.11e-16 | 3.55e-15 deg |
| 47.364066848 + j1.644980793 | 49.224945 | 0.358045 | 0.00e+00 | 3.55e-15 deg |

Two constraints, two unknowns, so the fit itself is not evidence. What is evidence is where it
landed: 0.7 pct from the declared 50.0, with a capacitance in the same band as its two
independent estimates - 0.1246669644 pF from a naive parallel plate over the 0.4 by 3.2 mm cut,
and 0.2347077263 pF as required for the amplitude alone in the previous dispatch. One physical
object, three routes, factor 3 spread.

Pinning R at exactly 50.0 tests the same thing with one free parameter: the amplitude alone then
fixes C at 0.296277 pF and the predicted load-plane phase is -19.5469 deg against a measured
-24.4293 deg, a 4.8814 deg residual. Down from 100.50 deg.

For completeness, the same coefficient read as a series impedance: 33.93 - j23.61 ohm from the
raw amplitude, 35.15 - j24.86 ohm from the fitted amplitude, equivalent series capacitance 1.157
and 1.099 pF, Q 0.696 and 0.707. That reading implies the reactance is in series with the
resistor rather than across the cut, which the geometry does not support, so it is recorded and
not used.

## 7. beta is measured here, not reused

Regressing the unwrapped station phase on x, from the raw phasors:

| Z0 | stations | beta from data | rms | ratio to beta_fit 231.553317 |
|---|---|---|---|---|
| 47.364066848 real | 8 selected | 231.859636 | 0.7851 deg | 1.001323 |
| 47.364066848 + j1.644980793 | 8 selected | 229.483313 | 0.7904 deg | 0.991060 |
| 50.0 | 8 selected | 219.863819 | 1.3538 deg | 0.949517 |
| 47.364066848 + j1.644980793 | all 9 | 226.230771 | 1.9150 deg | 0.977014 |

The fitted beta is reproduced from the raw phasors to 0.13 pct, and beta_model 223.353067 is
excluded at 2.7 pct. The frequency-domain fit is therefore not being trusted on its own word.

The fit span is stated, not assumed: 8 of the 9 stored stations are selected, spanning
0.0104 to 0.0188 m (0.0084 m). Station 8 is excluded because it sits on the load, which is
correct for a travelling-wave fit and is also why the one station that measures the load
directly was the one thrown away.

The complex Z0 also gives the most nearly constant amplitude along the line: abs(Gamma) spreads
6.7242 pct across the 9 stations against 16.5748 pct for its real part and 22.7581 pct for
Z0 = 50. A travelling wave has constant amplitude, so the complex Z0 is the better decomposition
by its own data.

## 8. What is still wrong, and it is not the load

abs(S11) squared plus abs(S21) squared is 0.690328111251, leaving 0.309672 of the incident power
absorbed. A 50 ohm series element in a 47.364 ohm line must absorb 0.452247 and transmit 0.428400.
The measured pair transmits too much and absorbs too little, and no single series resistance
produces both of its own numbers:

| estimate | value (ohm) | from |
|---|---|---|
| R from abs(S11) | 45.727381 | `2*Z0*abs(S11)/(1 - abs(S11))` |
| R from abs(S21) | 29.193690 | `2*Z0*(1/abs(S21) - 1)` |
| R from the power budget | 22.439077, or 399.901445 | `4*R*Z0/(R + 2*Z0)^2 = 0.309672` |

Spread across those: 103.78 pct; S11 against S21 alone: 56.63 pct. This is independent of
reference planes, because magnitudes do not move under de-embedding.

abs(Gamma) is also not constant along the line, spreading 6.7242 pct over 9 stations. A single
travelling wave plus its reflection has one amplitude; a ripple means a second wave in the
measurement section. The leading unverified hypothesis is a reflection off an imperfect far-end
termination returning through the load with amplitude of order T*Gamma_far*T, which would produce
both symptoms at once and is consistent with `run.reference null` and
`loaded_without_reference true`. Not tested here. It is the first thing a new run should settle.

Recorded and not used: the strip-to-ground node ratio at the load column is 84.704225 ohm at
-14.2026 deg under the `+V/I` convention, or the same 84.704225 magnitude at +165.7974 deg
under `-V/I`, where Re Z is -82.115180. The two series-element readings a tracer can produce
differ by Z0 - 50 ohm across the cut against 97.36 ohm to ground one side of it - and 84.70
matches neither, so the number cannot identify the element. Its relative sign convention is
undocumented in the artefact, which is why every impedance in this document names the convention
it used.

## 9. Verdicts against the four brackets

| bracket | verdict | on what |
|---|---|---|
| V1 current clean, under 1 pct | **UNRUNNABLE** | no per-edge current or gap voltage in the artefact; substitution in section 6 is weaker and is not a pass |
| V2 current dirty, over 1 pct | **UNRUNNABLE** | same |
| V3 distance confirmed | **FIRES** | 0.0072 m reproduced exactly from `emfit/studies.py`:3561-3562 and confirmed from the data to 0.45 cell, but it is the port-to-station-0 leg and not a load distance |
| V4 distance wrong | does not fire | the number is right; the interpretation we had put on it was wrong |

## 10. Retractions and corrections

- Eight edges becomes **nine** (`geometry.loads[0].n_edges`; `emfit/studies.py`:2883-2886).
- **Retracted:** the banked non-passivity argument. The full complex inversion returning
  Re Z_load of -11.13 to -11.94 ohm reproduces here exactly at -11.927611, and it is now
  explained: it was performed at the port-plane angle. The same measured amplitude inverted at
  the load-plane angle gives +33.93 - j23.61 ohm, which is passive. Non-passivity was a property
  of the reference plane, not of the model's load.
- **Superseded:** the banked conclusion that a wrong value and missing physics cannot be
  separated with this estimator. Measured at the load plane they separate into a resistance
  0.7 pct from nominal and a capacitance of 0.30 to 0.38 pF.
- **Re-expressed, not retracted:** the 5.333447185 deg monotone drift. At the load plane the
  residual is 24.43 deg, of which a cut capacitance fixed by the amplitude alone accounts for
  19.55 deg, leaving 4.8814 deg.

## 11. What closes, and with what

Closable now, nothing further needed: the load is 50 ohm to 0.7 pct with a 0.30 to 0.38 pF shunt
at the load plane; beta_fit is validated from raw phasors to 0.13 pct; the de-embed distance is
verified twice, from code and from data, and points at the port plane.

Closable only with a new run, in priority order: (1) dump the per-edge V and I across the load
edges, which closes V1 and V2 for good and costs one line in `run_build_A.py` plus a repeat run;
(2) dump the S21 plane phasors as well as the S11 stations, which settles whether abs(S21) is
contaminated and would identify the far-end reflection; (3) state the `(V, I)` sign convention in
the artefact.

Not closable at all with this estimator: whether individual edges short across the cut. That is
exactly what item (1) is for.
