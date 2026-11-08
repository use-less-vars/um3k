# Direct V/I Forensics (2026-11-08)

## 1. Question

Does the FDTD engine actually contain a reflection at the termination, measured with no free
parameter and no reference impedance?

## 2. Method

The engine already stores per-plane phasors in every extraction-plane JSON under the key
`s11.station_phasors`: `x_m[9]`, `v_re`/`v_im`[9], `i_re`/`i_im`[9], with
`js = [26,29,32,35,38,41,44,47,50]` and `fit_selected`/`fit_x`. From these the local impedance is
formed directly as `Z = v/i` at each station. This uses only the engine's own stored field
quantities: there is no reference impedance, no de-embedding, and no fitted parameter in the
measurement. Script: `evidence/termination/analyze_vi_forensics.py` (508 lines, pure numpy, exit
code 0, committed e85c4d3).

## 3. The nine stations

x from 10.4 mm to 20.0 mm, 1.2 mm apart (columns 26 to 50).

| st | x_mm | \|Z\| ohm | argZ deg | dArg deg |
|---|---|---|---|---|
| 0 | 10.4 | 47.403 | +39.347 | - |
| 1 | 11.6 | 34.225 | +34.409 | -4.938 |
| 2 | 12.8 | 26.192 | +19.954 | -14.455 |
| 3 | 14.0 | 24.174 | -2.432 | -22.386 |
| 4 | 15.2 | 28.646 | -22.259 | -19.827 |
| 5 | 16.4 | 38.446 | -32.425 | -10.166 |
| 6 | 17.6 | 52.767 | -33.634 | -1.209 |
| 7 | 18.8 | 70.631 | -26.819 | +6.815 |
| 8 | 20.0 | 85.627 | -13.624 | +13.195 |

## 4. Result: C2 FIRED

The reflection is real. |Z| runs from 24.174 ohm to 85.627 ohm, max/min = 3.542, mean 45.346 ohm,
mean |argZ| = 24.99 deg, argZ increment spread 35.58 deg.

## 5. Falsifiable ripple prediction

A reflection of magnitude |Gamma| on a line of impedance Z0 confines |Z| between
Z0(1-|Gamma|)/(1+|Gamma|) and Z0(1+|Gamma|)/(1-|Gamma|); the ratio of those two bounds is
((1+|Gamma|)/(1-|Gamma|))^2. For |Gamma| = 0.245 this predicts a ratio of 2.719; for |Gamma| =
0.326 it predicts 3.870. The measured ratio is 3.542, which lies between the two and closer to the
0.326 prediction. "No reflection" is excluded outright by this test.

## 6. Magnitude is constant when the line impedance is the fitted one

With Z0 = 47.305815 ohm the per-station reflection magnitudes are 0.3575, 0.3483, 0.3364, 0.3243,
0.3144, 0.3084, 0.3071, 0.3094, 0.3119: spread only 0.050, mean 0.324. A nearly constant magnitude
across nine planes is exactly what a single termination produces. Z0 = 47.3 also MINIMISES that
spread (0.050) against 0.146 at 39.5 ohm, 0.147 at 55 ohm and 0.073 at 50 ohm, so the fitted line
impedance is independently confirmed even though the fitted reflection magnitude is not.

## 7. Phase rotates constantly

With Z0 = 47.3 the increment of arg(Gamma) is 30.4, 31.2, 32.0, 32.5, 32.8, 32.5, 31.2 and 27.1
degrees per 1.2 mm station, i.e. about 10.5 degrees per 0.4 mm cell. 2*beta*dx = 10.5 deg gives
epsilon_eff of about 3.5. A constant rotation is a genuine travelling/standing wave, not numerical
residue.

## 8. WHY THE EARLIER CONCLUSION WAS WRONG

All nine stations are upstream of the load. The extraction-plane sweep that appeared to converge on
|S11| of about 0.026 was reading columns downstream of the load, where a travelling wave with
nothing to reflect from is the correct answer: cols 51-54 give |Z| = 45.69, 46.06, 46.20, 46.22
ohm with argZ = -2.72, -1.47, -0.68, -0.23 deg. The apparent drift of |b|/|f| was drift in
post-load numerical junk. Every conclusion drawn from that sweep - that the split was in the dock,
that no reflection was present - was measuring on the wrong side of the component.

## 9. Consequences

(1) The port |S11| of 0.326 is CORRECT. The field-derived |Gamma| is 0.324, a 0.5 percent
agreement. The port is not the broken ruler.
(2) The station two-wave fit's |Gamma| of 0.245 is TOO LOW (biased), while the Z0 = 47.3 it
produced is validated.
(3) The actual reflection magnitude of this component is about 0.32, with phase rotating
consistently at about 10.5 degrees per cell, epsilon_eff about 3.5.

## 10. Open question / next step

The remaining defect is in the ruler, not the engine: S11 must be extracted upstream and
de-embedded to the load plane rather than read downstream, and the station two-wave fit should be
re-run constrained to Z0 = 47.305815 ohm. Neither has been attempted yet; no prediction is offered
for either.
