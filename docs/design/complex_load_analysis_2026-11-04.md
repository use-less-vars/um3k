# Complex load analysis - 2026-11-04
Read-only analysis of `evidence/termination/`. **No source change, no run performed.** Phase-1
extraction on disk: `.scratch/cl_data.json` (160189 B), `.scratch/cl_data.md` (22605 B);
phase-2 arithmetic transcript `.scratch/p2_st3.txt`, generator `.scratch/write_doc.py` + inline scripts.

## 1. Purpose and data provenance
Question: the A-arm record contains 44 artefacts carrying `s11`/`s21`, but `Z_eff` (the complex
impedance of the load, measured on the load's own column) exists in exactly **one** of them. This
document states what that single complex datum does and does not pin down: the parallel/series
element values, the pi-network family and its bounds, and - the decisive part - whether the
"s11 and s21 share a common scale factor" reading survives a change of reference impedance.

| input | value | key path |
|---|---|---|
| primary arm | `build_A_50ohm_v3_zeff.json` | only artefact of 44 with `z_eff_measurement` |
| measured plane impedance | `82.11518049761072 - j20.78227124428749` ohm | `z_eff_measurement.z_eff.{re,im}` |
| farstations arm | `|s11|=0.318553`, `|s21|=0.763737`, `ang = -36.6507 / -52.7856` | `build_A_50ohm_v3_farstations.json` |
| TE anchors (Z0=47.54) | `|S11|=0.3072`, `|S21|=0.7241`, `|ratio|=0.4242751`, `ang=-31.0088` | TE reference, not in any artefact |
| station-fit Z0 (arm) | `44.207501 + j0.379446` ohm | `run.station_fit.z0_re/z0_im` |

`omega = 2*pi*f = 36617061934.18289` rad/s. All in doc/scratch: "computed from named inputs".

## 2. Ratio test across the record
`|ratio| = |s11|/|s21|` cancels any factor common to both, so it is the only record-wide scalar
available without a measured plane impedance. Full 44-row table: `cl_data.md` section "Task 3".

| artefact | `|s11|` | `|s21|` | `|ratio|` meas | `|ratio|` pred | delta % |
|---|---|---|---|---|---|
| `A_v3_zeff` (measured Z_plane) | 0.325565 | 0.762847 | 0.426776 | 0.424278 | **+0.5887** |
| `A_v3_beta2wave` / `v3_flux_off_pin` / `v3_lumped_check` / `v3_settling` (identical) | 0.325565 | 0.762847 | 0.426776 | 0.025873 | +1549.5 |
| `A_v3_farstations` | 0.318553 | 0.763737 | 0.417098 | 0.025873 | +1512.1 |
| `A_v3c` / `A_v3_twin_check` | 0.325565 | 0.767557 | 0.424157 | 0.025873 | +1539.4 |

**Only one row above is a test.** The `pred` column for the other 43 is `|50 - 47.54| / (2*47.54)`
= `0.025873`, i.e. the DC stamp used as a `Z_plane = 50 + j0` proxy - it measures the failure of the
proxy, not the load, and must not be quoted as a ratio residual. `|ratio|` actually spans
`0.0035 .. 5.32` across the record because the arms differ in what they measure, not by a scale
factor. **n = 1** for anything involving a complex plane impedance: `z_eff_measurement` appears in
1 of 44 A-arm artefacts. Against the TE anchor the single measured row is **+0.5887 %** high.

Excluded, not compared (quarantined at-plane value `|s11| = 0.033793` = `run.s11_at_plane`, not a
reference-free measurement): `build_A_50ohm_p51_noref.json`, `build_A_50ohm_sweepN51.json`,
`build_A_50ohm_through_p51.json`.

## 3. Phase discrepancy - OPEN

Measured `angle(s11) - angle(s21)` wrapped to (-180,180] = `+140.2377` deg. Anchored to the
TE value `-31.0088` deg:

| convention | computed | residual vs -31.0088 |
|---|---|---|
| A (as wrapped) | `+140.2377` | **`+171.2465` deg** |
| B (sign of the difference flipped) | `-140.2377` | `-109.2289` deg |

`171.2465 + 109.2289 = 280.4754 = 360 - 79.52`, so the two conventions are not additive inverses and
neither is a rounding of the other. Convention-independent statement: the measured angle difference
differs from the anchor by **`171.2465` deg in magnitude**. Arithmetic handle on what would zero it:
`angle(s11) = -31.0088 + 59.4987 = +28.4899` deg, against the recorded `-160.2636` deg - a
`188.7535` deg offset. **Status: OPEN. No mechanism proposed here.** The +0.5887 % magnitude residual
of section 2 and this phase residual are independent statements; the magnitude one is explained as a
scale factor in section 5, the phase one is not explained by that scale factor at all.

## 4. Pi-network bounds

Assumption **A1**: `Z_down = Z0_TE = 47.54` ohm, real. Then
`Z_bridge = Z_plane - Z_down = 34.575180497610724 - j20.78227124428749` ohm
(`|Z| = 40.3403756`, angle `-31.0090175` deg). A1 is not in any artefact; changing it moves every
number in this section (section 4d).

### (a) Parallel-RC form - CONFIRMED

`Y = 1/Z_bridge = 0.0212463622 + j0.0127706539` S -> `R_p = 47.066881` ohm, `C_p = 0.348762` pF.
TE's stated `47.07 ohm // 0.349 pF` at 5.8278 GHz gives `Z = 34.5637502 - j20.7909330`
(`|Z| = 40.3350434`, angle `-31.0279277` deg). Residual `0.01143 + j0.00866` ohm = **0.0356 %** of
`|Z_bridge|`; `R_p` off by `-0.0066 %`, `C_p` off by `-0.0681 %`. **Confirmed.**

### (b) Series-RC form - a different circuit

`R_s + 1/(j*w*C_s)` for the same `Z_bridge`: `R_s = 34.575180` ohm, `C_s = 1.314085` pF.
`C_s/C_p = 3.7679`. **The 1.31 pF-vs-0.349 pF trap:** the two capacitances describe the same
impedance and differ by a factor 3.77 because one is in the series branch and one is across it.
Quoting "the load capacitance is 1.3 pF" and "0.35 pF" as a discrepancy is a category error; the
recorded series-form value is **1.314085 pF**, not 1.35 pF. This trap is closed here.

### (c) The pi family - one complex datum, one free parameter

Topology used (assumption **A2**), measured at the plane node, `Z_down` already removed by A1:

```
  plane o--+--- C_s1 ---o GND
           |
           +--- C_s ---+--- C_s2 ---o GND
                       |
                       +--- R_s ---o GND
```

Three capacitors, one complex datum -> one-parameter family. Table (all rows reproduce
`Z_bridge` exactly, `|Z| = 40.3403756`, angle `-31.0090175` deg; `R_s` is fitted, **not** pinned to
`R_DC`):

| case | `C_s` (pF) | `C_s1` (pF) | `C_s2` (pF) | `R_s` (ohm) | reproduced `Z_plane` (ohm) |
|---|---|---|---|---|---|
| (ii) pure series bridge | 1.314085 | 0 | 0 | 34.575180 | 82.115180 - j20.782271 |
| intermediate | 1.425639 | 0.050000 | 0 | 37.203363 | 82.115180 - j20.782271 |
| intermediate | 3.507634 | 0.250000 | 0 | 45.741646 | 82.115180 - j20.782271 |
| (i) open series arm | `inf` | 0.348762 | 0 | 47.066881 | 82.115180 - j20.782271 |

Case (ii) = section 4b. Case (i) = section 4a. Every intermediate point is exact (`|err| < 1e-14`)
because `2` real equations pin `R_s` and `C_s` once `C_s1` is chosen: `R_s = Re(T)`,
`C_s = 1/(w*(-Im(T)))` with `T = 1/(Y_bridge - j*w*C_s1)`. `C_s2` is free in the table (set to 0,
meaning no far shunt) because it is what makes the third unknown.

**Hard bound on the third capacitor, with `R_s` pinned to `R_DC = 50`.** Solving the full
three-capacitor topology for `(C_s1, C_s2)` with `C_s` fixed and `R_s = 50`: solutions exist only
with `C_s2 < 0` - e.g. `R_s = 47.0669 -> C_s1 = 0.21372 pF, C_s2 = -0.13504 pF`;
`R_s = 36 -> C_s1 = 0.02671 pF, C_s2 = -0.01709 pF`; `R_s <= 30` -> no solution at all. The sign of
`C_s2` does not change anywhere in `R_s` in [20, 47]. **Statement: no all-positive-capacitor
pi-network of topology A2 reproduces `Z_bridge` while its through-path resistance is held at the
DC stamp 50 ohm.** The upper limit is structural: `1/Re(Y_bridge) = 47.066881` ohm is the largest
real part this topology can present, and `50 > 47.066881`.

### (d) Feasible region extents

Under A1 (`Z_down = 47.54`), A2, and all-positive capacitances:

| parameter | min | max | condition |
|---|---|---|---|
| `C_s1` (plane-end shunt) | 0 pF | 0.348762 pF | max at `C_s` open = parallel form (a) |
| `C_s` (series arm) | 1.314085 pF | unbounded | min at `C_s1 = 0` = series form (b) |
| `C_s2` (far shunt) | - | - | `>= 0` only if `R_s` freed below 47.066881 |
| `R_s` (through-path R) | 34.575180 ohm | 47.066881 ohm | endpoints are (b) and (a) |
| `R_p` (parallel form) | 47.066881 ohm | 47.066881 ohm | fixed once A1 is fixed |
| `C_p` (parallel form) | 0.348762 pF | 0.348762 pF | fixed once A1 is fixed |

A1 sensitivity (same `Z_plane`, `Z_down` varied; `R_p`, `C_p`, `R_s`, `C_s` recomputed):

| `Z_down` (ohm) | `Z_bridge` (ohm) | `R_p` (ohm) | `C_p` (pF) | `R_s` (ohm) | `C_s` (pF) |
|---|---|---|---|---|---|
| 50.00 (DC stamp) | 32.115180 - j20.782271 | 45.567790 | 0.333156 | 32.115180 | 1.314085 |


## 5. Anchor re-derivation, residual factors, three-Z0 sweep

`S11 = (Z - Z0)/(Z + Z0)`, `S21 = 2*Z0/(Z + Z0)` (formula as specified; for complex `Z0` this is not
the power-wave definition). `factor = |S_measured| / |S_expected|`.

Primary arm, `Z_plane = 82.115180 - j20.782271` (measured):

| Z0 (ohm) | `|S11|e` | `ang S11e` | `|S21|e` | `ang S21e` | `|ratio|p` | `ang ratio p` | `f_s11` | `f_s21` | `f_s11/f_s21` |
|---|---|---|---|---|---|---|---|---|---|
| 47.54 real (TE) | 0.307214 | -21.9026 | 0.724087 | +9.1064 | 0.424278 | -31.0090 | **1.059732** | **1.053530** | **1.005887** |
| 44.2075 + j0.3794 (station_fit) | 0.339282 | -19.9973 | 0.690985 | +9.6665 | 0.491012 | -29.6638 | 0.959571 | 1.104000 | 0.869177 |
| 42.4379 - j15.7280 (line.z0) | 0.308165 | +9.0780 | 0.697392 | -3.9979 | 0.441881 | +13.0758 | 1.056464 | 1.093857 | 0.965816 |

Farstations arm, `Z_plane` **not measured**; proxy `50 + j0` (assumption A0, the section-2 proxy):

| Z0 (ohm) | `|S11|e` | `|S21|e` | `f_s11` | `f_s21` | `f_s11/f_s21` |
|---|---|---|---|---|---|
| 47.54 real | 0.025220 | 0.974780 | 12.630756 | 0.783497 | 16.120998 |
| 44.2075 + j0.3794 | 0.061618 | 0.938540 | 5.169816 | 0.813750 | 6.353078 |
| 42.4379 - j15.7280 | 0.186117 | 0.965349 | 1.711574 | 0.791151 | 2.163398 |

**Plain statements.**

1. On the primary arm at `Z0 = 47.54` the two factors agree: `f_s11 = 1.0597` and
   `f_s21 = 1.0535`, i.e. within **0.589 %** of each other, both about `+5.5` to `+6.0 %` above 1.
   A common scale factor of `1.057 +- 0.003` is what that pair supports.
2. On the primary arm at the run's own station-fit `Z0 = 44.2075 + j0.3794` the two factors
   **split**: `f_s11 = 0.9596` (`-4.0 %`) against `f_s21 = 1.1040` (`+10.4 %`) - a
   **13.08 %** disagreement, and no common factor exists. At `42.4379 - j15.7280` they split by
   `3.42 %` and point the same way but are not equal.
3. **HEADLINE. The common-factor hypothesis does not survive. It exists only at `Z0 = 47.54`** -
   the TE reference, which is stored in no artefact - and it disappears at the two complex `Z0`
   values the run itself writes. The `+0.589 %` ratio agreement of section 2 is the same statement
   evaluated at the same `Z0`: `f_s11/f_s21 = 1.005887` is algebraically identical to the ratio
   residual. The agreement is therefore a property of the pair (`Z_plane` measured, `Z0 = 47.54`),
   not a property of the measurement, and it cannot distinguish "one scale error common to s11 and
   s21" from "a `Z0` choice that happens to make the two discrepancies equal".
4. Between arms the hypothesis is not testable: the farstations arm has no measured `Z_plane`, so
   every row in its proxy table is a statement about the proxy. Borrowing the primary `Z_plane`
   gives `f_s11 = 1.0369`, `f_s21 = 1.0548` at `47.54` (agreeing to `1.69 %`) - close, but that is
   the borrowed datum, not an independent arm, and the same borrowed datum splits by `15.05 %` at
   the station-fit `Z0`. No inter-arm agreement is established.
5. The phase residual of section 3 is not touched by any of this: a real scalar factor applied to
   both `s11` and `s21` leaves `angle(s11) - angle(s21)` invariant, so the `+171.2465` deg residual
   survives every reading in this section. **No mechanism is proposed.**

## 6. What is NOT settled

1. **No second arm with a measured `z_eff`.** Every conclusion in sections 4 and 5 rests on n = 1
   (`build_A_50ohm_v3_zeff.json`). A second artefact with a `z_eff_measurement` block would make the
   ratio test a test rather than a single point.
2. **No twin `Z_down` measurement.** A1 (`Z_down = 47.54`, real) is assumed, not measured. A
   measurement of the `Z_down` node's impedance would collapse the section-4 family from
   one-parameter to a point and would settle whether `R_p = 47.07` ohm is the load or the anchor.
3. **`column: None` in the `z_eff_measurement` block** (the schema gap opened by
   `z-eff-direct-2026-11-04`): the block records `v_load`, `i_load`, `z_eff`, `f_hz` but not which
   column the load occupies. The `column` value is `None` in the artefact even though
   `loads_used[-1]["column"]` is resolved in code, so the measured `Z_eff` cannot be re-attached to
   a geometry from the artefact alone.
