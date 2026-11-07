# Load definition forensics: what the 50 ohm resistor becomes on the grid

**Dispatch:** `load-definition-forensics-2026-11-07` -- **Date:** 2026-11-07 -- **Status:** read-only. No FDTD run. No `emfit/` change. No model applied. Every number below is a re-analysis of `evidence/termination/build_A_50ohm_p51_phasors.json` with beta as the only free parameter.

## 1. The question

The banked port forensics left a shortfall and gave it a name. At the corrected dispersive beta = 228.628823838164 rad/m the fitted abs(gamma_port) is 0.3317496573106 while the ideal series-resistor anchor is 0.34465350053531579; the gap is 1.2904e-02 in abs(Gamma), i.e. 3.744 % of the anchor (the earlier note recorded 3.677 % for the same comparison; recomputed from the two printed magnitudes it is 3.744 %, a 0.07 pp normalisation difference I have not chased and that changes nothing below). The note then re-expressed that shortfall as "the effective load is about 47.2 ohm against a nominal 50 ohm". This dispatch asked the prior question: how does the number 50 become a grid quantity at all, and can the measured S11 say whether the value is wrong or whether something reactive is missing?

## 2. The anchor belongs to a topology, and the topology is series

Build A cuts the strip at one node column, bridges the cut with the resistor, and lets the line continue into a matched termination. Seen from the line, the resistor is in series with a matched section, so

    Gamma = Z / (Z + 2*Z0)     not     (Z - Z0)/(Z + Z0)

At Z = R = 50 and the stated Z0 = 47.53662 this gives 0.34465350053531579, the anchor A of the banked document, and it reproduces to the last digit. Two consequences govern everything below: the anchor is real and positive, so a purely real load puts Gamma on the positive real axis; and abs(Gamma) alone cannot recover R without fixing beta, because abs(Gamma) moves with beta through the fit basis (banked slope d abs(gamma_port)/d beta = -1.991630e-03 per rad/m).

## 3. What the model actually does with the resistor

| step | what happens | citation |
|---|---|---|
| declaration | `Load(position_m, "series_r", value_ohm)`; `value` is SI ohms and the dataclass carries no geometry | `run_build_A.py:134`, `:392`; `emfit/board.py:74`, `:78-83` |
| column choice | `ix = floor(position/cell + 0.5)`, `cell = h/n_sub` | `emfit/studies.py:2875` (mirror `run_build_A.py:433-435`) |
| cut | the E_x edges at that one column are removed from the PEC set | `emfit/studies.py:2883-2885` |
| R to grid | `sigma[edges] += 1.0/(edges.size * value)` -- a conductance in siemens per edge | `emfit/studies.py:2886-2887` |
| hand-off | passed unconverted as the `m_sigma` diagonal | `emfit/studies.py:2897`, `:2966`; `emfit/evolve.py:8-10` |
| time update | `loss_num = m_eps/dt - m_sigma/2`, `loss_den = 1/(m_eps/dt + m_sigma/2)` | `emfit/evolve.py:151-155` |

The decisive fact is what is absent. There is no per-unit-length conductivity, no sigma = dL/(R dA) conversion, and no cell length, face area, dx, dy, dz or mu0 anywhere in the path. (The material conversion sigma*A_e/L_e does exist, at `emfit/materials.py:290-292`, and is never used for loads.) Because R enters only as a conductance in siemens, and because the 1/N split is one conductance divided over N parallel paths, the total stamped conductance is N * 1/(N*R) = 1/R exactly, with float error of order N*eps, about 1e-15. There is no length to cancel because no length is ever introduced.

Three residual risks, all bounded. Position quantisation by `floor(pos/cell + 0.5)` moves the load by at most half a cell, which is a phase-plane effect and not a value effect. The split is exact. And the split is exact only if all N freed edges actually conduct: if one is later masked or PEC'd, N_eff < N gives R_eff = R*N/N_eff > R, which pushes abs(Gamma) UP, the wrong direction to explain a shortfall. The code pins the E_y rails precisely so the two halves cannot short to each other along them (`emfit/studies.py:2865-2871`), and that assertion is the only load-side assumption worth testing numerically: lowering the effective resistance needs a parallel path, i.e. a partial short, not a missing conductance.

One thing the model deliberately includes. The cut is one cell wide and the field across it is not removed; the code says so in its own words, that the capacitance of the cut "is therefore part of the model... at the default 0.4 mm cell it is a few hundred ohms of reactance at a few gigahertz, which is not small" (`emfit/board.py:86-91`). The simulated load is therefore not a bare 50 ohm. It is a two-terminal element bridging a 0.4 mm gap, and the gap's capacitance is inside the simulation while it is outside every analytic anchor quoted so far.

## 4. The implied load, and why the number moves

| beta | abs(gamma_port) | arg deg | z0 fitted | resid_v |
|---|---|---|---|---|
| 222.321546277827 | 0.344650000000 | -89.999846513 | 48.01614725715 + j1.914703664143 | 1.05238536e-02 |
| 224.575706 | 0.340000000740 | -92.573756512 | 47.85356343764 + j1.847164015843 | 7.88057636e-03 |
| 228.628823838164 | 0.331749657311 | -97.185304392 | 47.56671138488 + j1.728471819260 | 3.09551923e-03 |
| 231.046199503169 | 0.326897944800 | -99.925394838 | 47.39894775627 + j1.659331005689 | 9.05433145e-04 |
| 231.553316729128 | 0.325886794347 | -100.499211556 | 47.36406684819 + j1.644980793108 | 1.10098006e-03 |
| 237.926169033850 | 0.313380361365 | -107.680000000 | 46.93487871585 + j1.469116205338 | 8.70598530e-03 |

Inverting at each beta, with z0 the fitted complex value from that same beta:

    Z_load = 2*gamma_port*z0/(1 - gamma_port)          (full complex)
    Z_real = 2*Re(z0)*abs(gamma_port)/(1 - abs(gamma_port))   (modulus only)

| beta | Z_load | abs(Z_load) | angle deg | Z_real |
|---|---|---|---|---|
| 231.553316729128 | -11.94433075895 - j25.22394237797 | 27.90903628516 | -115.339028349 | 45.79445642952 |
| 228.628823838164 | -11.13106631655 - j26.68505561527 | 28.91354060875 | -112.642351466 | 47.22852857155 |

The modulus-only inversion reproduces the circulated 47.2 ohm, but only at beta = 228.6288. At the GATE-0-validated beta = 231.5533, which is the project's beta of record, the identical formula returns 45.79 ohm. The implied value therefore migrates 1.43 ohm across a 2.92 rad/m span of beta, which is narrower than the spread of beta candidates currently on the table. "The effective load is 47.2 ohm" is not a measurement; it is a restatement of abs(S11) at one chosen beta.

The full complex inversion is not merely noisy, it is unusable: it returns a negative real part, which is not a passive one-port. Section 5 says why.

## 5. The phase cannot carry the distinction

For a real load, Gamma is real and positive. The measured arg(gamma_port) is -100.499211556 deg at the fitted beta, and -89.999846513 deg at the magnitude-optimal beta; that is within 0.001 deg of minus ninety at the point where abs(Gamma) is largest. A phase sitting near -90 deg at the load is not a load phase, and the de-embed explains only part of the rotation: across the sweep arg(gamma_port) moves 19.680153476 deg, of which 2*beta*d accounts for 14.346706291 deg (72.899 %). The remaining 5.333447185 deg is a monotone drift in arg(gamma_v) itself, from 93.428596157 deg to 88.095148972 deg. So 27.1 % of the phase excursion is not a reference-plane rotation, and it is not identifiable as load reactance either. The estimator therefore cannot separate "the value is wrong" from "a reactive term is missing", because the only channel that could carry the separation is the phase, and it is not clean to the few-degree accuracy such a separation would need.

## 6. One coincidence, and why it is not evidence

At beta = 222.321546277827 the sweep returns abs(gamma_port) = 0.344650000000 against anchor A 0.344653501, agreement to 1.0e-5 relative, with arg = -89.999846513 deg. It is tempting to read that as the extraction reaching the ideal anchor somewhere inside beta, hence the shortfall is basis and there is no load defect at all. It is not evidence. The magnitude optimum is by construction the beta where abs(Gamma) is largest, so agreement with the anchor there is a property of an extremum rather than of the model, and the fit at that beta is the worst in the sweep: resid_v = 1.05238536e-02, which is 11.623 times the minimum of 9.05433145e-04 at beta = 231.046199503169. An 11.6x-worse fit does not certify a better S11.

## 7. How big a capacitance the residual would need

Take the series topology of section 2 and put a capacitance in parallel with the element, Z = R/(1 + j*w*R*C), with R = 50, Z0 = 47.53662 and f = 5827786408.327286 Hz. Requiring abs(Gamma) = 0.3317496573106 gives C = 0.2347077263 pF, whose reactance is 116.3560900352 ohm. The crude parallel-plate value over the 0.4 mm by 3.2 mm cut, using the full substrate permittivity, is C_pp = 0.1246669644 pF, which yields abs(Gamma) = 0.340861126978, i.e. 1.100 % below anchor A, or 29 % of the 3.744 % shortfall on its own. The required value is 1.883 times the naive one. Sensitivity: C = 0.05 / 0.10 / 0.20 / 0.30 / 0.50 pF gives 0.344035 / 0.342199 / 0.335139 / 0.324285 / 0.295548.

Read that as a size argument, not a computation. A capacitance within a factor 1.9 of a parallel-plate estimate that ignores fringing is agreement, not measurement. But it is enough to make a statement that the earlier analysis could not make: a reactance of the size the geometry actually has is a sufficient explanation of the residual, and it is not a defect in the model, because the simulation already contains that term. It is the anchor that omits it. The comparator is wrong, not the model.

## 8. Two things I got wrong

First, the 47.2 ohm. The port forensics presented it as "a re-expression of the residual, not independent evidence... its value is that it names an inspectable physical quantity". The first half was right. The second half overstated it: the quantity moves 1.43 ohm with beta, and beta is the least-settled number in the project, so naming it bought less than was claimed. It is retracted as a measurement of the load.

Second, and worse because it changed a decision, the direction of a shunt capacitance. The port forensics concluded that adding shunt capacitance "raises the prediction" and that a refinement raising the prediction cannot close a shortfall, so R-C was deprioritised. That used anchor B = 0.349, which does not sit in the same reference frame as anchor A. In the topology this code implements, a capacitance in parallel with the series element LOWERS abs(Gamma) (section 7), so the deprioritisation rested on the wrong sign. R-C is reinstated, with its topology stated. From here on every anchor is quoted with three things attached: its topology, its beta, and the Z0 used to build it.

## 9. Verdict

1. The 50 ohm to grid mapping is exact and clean. The resistance enters only as a total edge conductance of 1/R in siemens, with no geometry and no cancellation, so nothing in the stamp can turn 50 ohm into 47 ohm. The resistor is not the problem.
2. The model's load is a 50 ohm element bridged by a gap capacitance that the code documents as significant and every anchor so far omits. That is the only identified term with the right size and the right sign.
3. The about-47.2-ohm figure does not survive a change of beta, moving between 45.79 and 47.23. Retracted as a measurement.
4. The measured Gamma cannot be inverted into a passive complex load, because its phase is near minus ninety at the load and carries 5.33 deg of unexplained monotone drift. The question "is the value wrong or is physics missing" is not answerable with this estimator, and that unanswerability is itself the result of this dispatch.

## 10. What would actually discriminate (none of it applied)

D1. Test the rail assertion at `emfit/studies.py:2865-2871` directly: integrate the current through the load edges and check it equals the voltage across the cut times 1/R. A partial short shows up as excess conduction and is the only load-side mechanism that can lower abs(Gamma).
D2. Compute the gap capacitance electrostatically, with the substrate, and put the resulting abs(Gamma) in the same table as anchor A and the measurement, so the residual has a candidate rather than a hypothesis.
D3. Verify the de-embed distance of 0.0072 m against the geometry. It sets 72.9 % of the phase rotation and remains unverified.
D4. No change to the load stamp is proposed. There is nothing to fix there.

## 11. Limitations

The gap model of section 7 is a single lumped element standing in for a distributed one-cell cut; it is a size argument. The 0.4 mm cell width is taken from the code comment and not re-derived from h/n_sub here. The sensitivity sweep uses a real Z0 = 47.53662 while the fit returns a complex z0; using that complex value would move the required capacitance by a few percent. Section 2's complex inversion does use the fitted complex z0, so its negative real part is not an artefact of a real-Z0 substitution.
