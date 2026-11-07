# S11 port forensics — 2026-11-07

Dispatch `s11-port-forensics-2026-11-07`. Read-only analysis of station phasors already banked on
disk. No FDTD run, no openEMS, no host run, no edit under `emfit/`, `tests/` or `evidence/`.

## 1. Question

The dispersion dispatch settled beta to 1-2 % and demoted the static Hammerstad reference. This
dispatch asks the next question in order: is the remaining |S11| shortfall — 5.6 % against the
series-R anchor — a bias in the extraction routine? The order matters. If the routine is biased, a
more complex physics model would conceal the bias rather than remove it, so the routine is
interrogated before the physics is changed.

Inputs: `evidence/termination/build_A_50ohm_p51_phasors.json` gives `/s11/station_phasors` (n = 9,
keys `x_m`, `v_re`, `v_im`, `i_re`, `i_im`, `fit_selected`) and `/s11/deembed_distance_m` = 0.0072.

## 2. Gates

**GATE 0 — baseline reproduction, bit-exact.** Through the library calls and not a reimplementation:
`fit_station_impedance(x[sel], v[sel], i[sel], 231.55331672912826)` then
`deembed_reflection(gamma_v, beta, 0.0072)`. Recorded baseline: |gamma_port| = 0.32588679434738205,
arg = -100.499211556060 deg, z0 = 47.364066848 + j1.644980793, 8 of 9 stations. Reproduced with zero
deviation. The harness is therefore not a variable in anything below.

**GATE 1 — the de-embed is unit-modulus.** |gamma_port| - |gamma_v| = 0.0, float-identical.
`deembed_reflection` applies only exp(-2j*beta*distance), so |S11| inherits its magnitude *entirely*
from the fitted gamma_v, and beta can move |S11| only by changing the fit itself. Every magnitude
number in this document is therefore a statement about the fit basis, not about de-embedding.

## 3. Variants

Station selection fact, checked before running anything: the station nearest the load is index 8
(x = 0.020 m, js = 50), and it is the station the baseline already drops. A variant that dropped
"the station nearest the load" would therefore have reproduced the baseline exactly, so V5 drops the
two nearest, indices 7 and 8.

| variant | stations | \|gamma_port\| | arg (deg) | resid_v | resid_i | z0 (ohm) | vs A | vs B |
|---|---|---|---|---|---|---|---|---|
| V1 baseline | 8 of 9 | 0.32588679 | -100.4992 | 1.101e-03 | 8.530e-03 | 47.364 + j1.645 | -5.646 % | -6.623 % |
| V5 stripped load | 7 of 9 | 0.32611068 | -100.5472 | 6.645e-04 | 5.228e-03 | 47.512 + j1.795 | -5.384 % | -6.559 % |
| V6 all stations | 9 of 9 | 0.32556487 | -100.4771 | 1.456e-03 | 1.821e-02 | 47.224 + j1.255 | -5.931 % | -6.715 % |

The residuals move sharply while the magnitude does not. Dropping the two near-load stations improves
`resid_v` by 40 % and `resid_i` by 39 %; restoring the dropped station doubles `resid_i` from
8.5e-03 to 1.8e-02. Across the same three variants |gamma_port| spans 0.1675 %. The fitted magnitude
is decoupled from how well the stations are fitted, and that decoupling is the substance of the
result.

## 4. Declared infeasible

V2 voltage-only, V3 current-only and V4 phase-only produced no numbers.
`fit_station_impedance(x, v, i, beta, sigma_beta=None, alpha=0.0)` fits the two-wave model to the
voltage and current series jointly; no leaf, kwarg or public helper fits one series alone. `gamma_i`
is reported, but only as a by-product of a current-series fit that already runs beside the voltage
one. A single-series or phase-only fit would mean reimplementing `_two_wave_fit`, which this project
does not do, because a reimplementation proves nothing about the code under test. **A declared gap is
the result here; a substituted quantity would not have been.** The consequence is registered in
section 7 and it limits what F2 can mean.

## 5. Anchors

Anchor A is the series-R anchor, |Gamma| = R/(2*Z0 + R) with R = 50. Computed with the stated
Z0 = 47.53662 it gives 0.34465350, which reproduces the 0.34465 in circulation and so validates the
formula. Z0 is an *output* of the fit, not an input, so "at fixed Z0" is not a knob; each variant's
residual is quoted against the anchor built from that variant's own fitted z0, and the z0 is printed
in section 3 so the choice is visible. Anchor B is the QUCS R||C model at 0.349, external, not
recomputed here. The two are not interchangeable and no row mixes them.

## 6. Bracket verdict

SPREAD across the feasible variants is 5.458137e-04, which is 0.167502 % of the mean 0.325854.

**F2 fires:** "all feasible variants agree tightly (SPREAD <= 2 %) and all sit near 0.326, far from
both anchors". F1 does not fire — the spread is twelve times under its threshold. F3 does not fire:
V5 and V6 bracket V1 symmetrically and both lie within 0.17 %, so there is no single outlier to
isolate.

## 7. What F2 establishes and what it does not

F2 establishes that the extracted magnitude is not a station-selection artefact: three different
subsets, including the two directions away from the default, return the same number to 0.17 %.

It does not establish that the estimator is unbiased in *form*. V2, V3 and V4 were infeasible, and
all three surviving variants are the same estimator applied to different station subsets. F2's own
wording, "the extraction is clean", is stronger than this evidence supports. The accurate statement
is narrower: **the extraction is selection-stable, and no variant of it moves the magnitude toward
either anchor.** Testing model form would require an estimator that does not go through
`fit_station_impedance` at all, which is a different dispatch and a different risk.

## 8. Addendum — the magnitude is strongly beta-sensitive, and 35 % of the shortfall is stale basis

Not a bracket, not pre-registered; recorded separately, in the same spirit as section 9 of
`beta_refit_test_2026-11-05.md`.

| beta (rad/m) | source | \|gamma_port\| | z0 (ohm) | vs A |
|---|---|---|---|---|
| 231.55331672912826 | current baseline fit | 0.32588679 | 47.364 + j1.645 | -5.646 % |
| 231.046199503169 | residual minimum | 0.32689794 | 47.399 + j1.659 | -5.307 % |
| 228.62882383816375 | dispersive Kirschning-Jansen | 0.33174966 | 47.567 + j1.728 | -3.677 % |
| 223.58131180256908 | raw-phase extraction | 0.34204593 | 47.925 + j1.877 | -0.192 % |
| 223.35306683909533 | static Hammerstad | 0.34251673 | 47.941 + j1.884 | -0.032 % |

Local slope, central difference over +/-0.5 rad/m about the baseline: d|gamma_port|/dbeta =
-1.991630e-03 per rad/m. Quoting |S11| at the corrected dispersive reference instead of at the fit's
own beta raises the magnitude by 1.799 % and cuts the shortfall against anchor A from -5.646 % to
-3.677 %. **1.97 of the 5.65 percentage points — 35 % — is stale basis, not code and not physics.**
A minority of that recovery is the anchor drifting with the fitted z0 (0.345386 to 0.344413,
-0.28 %), but the effect is dominated by the magnitude itself.

The operational consequence is a policy, not a preference: **|S11| must always be quoted at a stated
beta.** The figure 0.3259, quoted at beta = 231.5533, is superseded by 0.3318 at beta = 228.6288. Any
comparison that mixes the two is comparing a basis change to a physical effect.

## 9. The sign of the residual is the actionable finding

After the basis correction the measurement sits 3.68 % *below* both anchors. Both structural
refinements currently on the table move the prediction the wrong way. A pure series R predicts
0.34465. Adding shunt capacitance around that resistor — the R||C model — makes the predicted
element impedance complex and *raises* the predicted reflection to 0.3450-0.349. A refinement that
raises the prediction cannot close a shortfall, so building R||C next would widen the discrepancy,
not narrow it.

Inverting the residual names the quantity that is actually wrong. If the load is a pure series
impedance Z, then |Gamma| = |Z|/|2*Z0 + Z|, and the measured 0.331750 implies |Z| = 47.2 ohm against
a nominal 50 ohm — a 5.6 % deficit. This is a re-expression of the residual and carries no
independent information by itself. Its value is that it names a physical quantity which can be
inspected directly in the model definition, which a residual percentage cannot.

## 10. Limitations

1. **Model form is untested**, per section 4 and section 7. F2 is narrower than its wording.
2. **Beta is an input here.** |S11| moves 1.8 % across the plausible beta range, so choosing
   228.6288 imports the Kirschning-Jansen model's own 1-2 % error straight into |Gamma|. The
   surviving 3.68 % shortfall is conditional on that choice.
3. **Anchor A is a derived constant, not a measurement**, and carries no uncertainty bar of its own.
4. **The de-embed distance 0.0072 is an input from a different run.** It is beta-independent by
   construction, as GATE 1 shows, but it is not verified against geometry anywhere in this dispatch.
