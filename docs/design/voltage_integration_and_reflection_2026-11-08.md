# Voltage integration and plane reflection: what the dump actually proves

Date: 2026-11-08. Supersedes two claims in
`docs/design/ghost_wave_analysis_2026-11-08.md`. No FDTD was re-run for this
document. Every number is read from `evidence/termination/build_A_50ohm_p51_ghostwave.json`,
recomputed from `evidence/termination/build_A_50ohm_p51_ghostwave_fields.npz`, or
produced by a complex least-squares fit to the nine recorded station phasors.

## 1. The two corrections

CORRECTION 1. The previous document concluded "the current channel is verified,
the voltage channel is not". The second half is WRONG. The voltage channel
verifies to 1.6e-15 relative against the nine recorded station phasors. It was
never broken.

How the error arose: the plane voltage is probed on
`column_path(cc, ix_extract, j_centre, 0, k_strip)` with `ix_extract = 51`, the
node layer at x = 51 * 0.0004 = 0.0204 m (emfit/studies.py:3092, :3263-3264;
column_path at emfit/ports.py:253, :288-290). The dump stores only the nine
station columns `js = [26,29,32,35,38,41,44,47,50]`, x = 0.0104 to 0.0200 m
(emfit/studies.py:3330-3335). ix = 51 is not in the dump at all. The previous
document integrated the wrong z extent (22 cells, the full stack) of the wrong
columns and compared it against a value measured at a column never captured.
Two independent mistakes pointing the same way.

CORRECTION 2. The argument that the standing-wave envelope gave |Gamma| = 0.2122,
agreeing to 0.3 percent with 0.2115 de-embedded from |s11|, and that S11/S21 were
thereby validated, does not stand. 0.2122 was (max-min)/(max+min) over the
22-cell integrals, which are not the line voltage (section 2), and max/min is not
a valid reflection estimator over a 128-degree window in any case: the nine
stations span only 0.356 of a period. The agreement was a coincidence between two
numbers both meaningless for that purpose. The conclusion it supported - that
gamma_plane is wrong - survives section 3, but for different reasons and with a
different factor.

## 2. The voltage channel verifies

Units: `plane_ez` in the dump is ALREADY IN VOLTS per edge, not V/m. Decided
empirically: summing it over the four substrate cells with no cell-width factor
reproduces the recorded `s11/station_phasors` complex v at all nine stations to
1.6e-15 relative. A V/m field would need a 0.0004 factor and be off by 2.5e6.

Path: `flux_projection = False` in this run (/run/kwargs/flux_projection), so the
raw branch `cut_signals[0] = edge_path_voltage(stepper.e, cut_column)` ran
(emfit/studies.py:3263-3264); the mode-projected branch at :3291-3293 is unused.
`k_strip = 4` (/geometry/k_strip, matching n_sub = 4 at
`evidence/termination/run_build_A.py`:451 and :504), and column_path(...,0,4)
returns cells k = 0..3, so Vstrip is identically the four-cell sum.
`j_centre = 106` (nyn = 213) is both the j of maximum |V4| at every station and
the only j that reproduces the recorded phasors.

| station | js | x (mm) | V4 (V) | recorded abs(v) |
|---|---|---|---|---|
| 0 | 26 | 10.4 | 332429 | 332428.752 |
| 1 | 29 | 11.6 | 275232 | 275232.288 |
| 2 | 32 | 12.8 | 227527 | 227527.157 |
| 3 | 35 | 14.0 | 214101 | 214100.840 |
| 4 | 38 | 15.2 | 244466 | 244465.931 |
| 5 | 41 | 16.4 | 298847 | 298847.488 |
| 6 | 44 | 17.6 | 354179 | 354178.514 |
| 7 | 47 | 18.8 | 396188 | 396188.027 |
| 8 | 50 | 20.0 | 416981 | 416980.556 |

Why the 22-cell sum could never match: the full stack adds 18 air cells above the
strip in which E_z reverses sign, so it is a cancellation, not a voltage. At
station 8 it gives 152627.54 V against the true line voltage 416980.56 V. The
figure 152628 V in the previous document is correct arithmetic on the wrong
quantity.

Why 217354 V was unreachable: that is |/s21_plane/v| at x = 0.0204 m, not among
the dumped columns. The dump's highest column is x = 0.0200 m. No slice through
the available data produces it, and none ever could.

## 3. The plane reflection is still wrong, by 5.6x

Method: complex linear least squares on the nine complex station voltages,
fitting v(x) = Vplus*exp(-gamma*x) + Vminus*exp(+gamma*x) with gamma GIVEN (two
complex unknowns, 18 real data points).

| alpha (Np/m) | beta (rad/m) | abs(Gamma) | rel. residual | cond(A) |
|---|---|---|---|---|
| 11.255 | 232.79891853803187 | 0.245108 | 1.78e-2 | 1.52 |
| 11.255 | 223.35306683909533 | 0.256488 | 2.30e-2 | 1.57 |
| 0 | 232.79891853803187 | 0.325863 | 1.44e-3 | 1.27 |
| 0.4344 | 232.79891853803187 | 0.322297 | 1.25e-3 | - |

The last row is the attenuation the data prefer; there the fit is about twelve
times better than at the recorded 11.255 Np/m.

Recorded `gamma_plane` is 0.04390825210124855. Ratios: 0.245108/0.043908 = 5.58;
0.256488/0.043908 = 5.84; 0.322297/0.043908 = 7.34; 0.325863/0.043908 = 7.42.
Driving the fit down to 0.0439 requires alpha of roughly 78 to 80 Np/m, where the
residual is 12.9 percent. That is not a plausible line. The plane reflection is
understated by about a factor of six, and the previous document's "4.8x" was
directionally right but arithmetically accidental.

Robustness: cond(A) = 1.5, so the two exponentials are well separated (they
decorrelate over 2*beta*L = 256 degrees) and the fit is well conditioned; the
128-degree worry applies to max/min, not to this fit. Dropping station 8, which
sits on the load column and is flagged fit_selected[8] = false, moves abs(Gamma)
from 0.325863 to 0.326135 at alpha = 0 and from 0.245108 to 0.243574 at
alpha = 11.255. The verdict does not depend on that station.

## 4. What this costs the previous document

4.1 s11 is not independent corroboration. At alpha = 0 the station fit returns
abs(Gamma) = 0.325863260016623, identical to /s11/magnitude =
0.32586326001662264 to fifteen digits. s11 IS the alpha = 0 two-exponential
station fit. Using it to confirm the phasors is circular, and the previous
document leaned on it.

4.2 The 31 percent power deficit. The arithmetic |s11|^2 + |s21|^2 = 0.686382
with 0.313618 missing, matched by (1-|s11|^2)(1-exp(-2*alpha*d)) = 0.313620, is
sound as arithmetic. But it used alpha = 11.255 Np/m, while the station phasors
over the same span prefer about 0.43 Np/m with a twelve-fold better fit. That
conflict is unresolved. The deficit is real; its attribution to conductor loss is
not yet demonstrated.

## 5. What is established

- The current channel is correct to 1e-4 (4756.623 A from raw plane_hy against
  4757.152 A recorded).
- The voltage channel is correct to 1.6e-15 against the nine recorded station
  phasors, using the correct four-cell path and the correct column.
- The dumped voltage quantity is in volts, not volts per metre.
- The nine load edges are equipotential (spread exactly 0.0), so the load is not
  misbehaving. Z = V/I with I = sum(V*G), G = 1/(N*R) is circular and settles
  only uniformity, not impedance.
- gamma_plane is understated by about 5.6x, on a well-conditioned fit robust to
  the propagation constant within 5 percent and to dropping the load column.

## 6. Open items

6.1 Candidate mechanism. The travelling-wave split uses zc in a = 0.5*(v + zc*i),
b = 0.5*(v - zc*i) (emfit/studies.py:1282, :1294). The run used line.z0 =
42.7585031570 - 16.0461497776j, while the impedance implied by the recorded
a, b, v, i is 47.30581504562189 + 1.5582142987505327j (/run/station_fit). If zc is
too large the split drives abs(b/a) towards zero, which is the observed collapse
to 0.0439. Test: recompute the split at the station-fit zc and check whether
abs(b/a) rises towards 0.24. Not yet run.

6.2 Extrapolating the alpha = 11.255 station fit to x = 0.0204 m gives
abs(v) = 411376 V with a phase error of only -4.8 degrees, against the recorded
cut-plane 217354 V, a ratio of 1.893. A series load at x = 0.0200 m would drop the
node voltage, so this may be the load's own voltage division rather than an error.
Unresolved.

6.3 The attenuation conflict of 4.2: about 0.43 Np/m from the station phasors
against 11.255 Np/m from |s11| and |s21|.

6.4 The dump loop should capture the cut column ix = 51 in addition to the nine
station columns (emfit/studies.py:3330-3335). Until it does, no dump can
reproduce the recorded plane voltage by construction.

## 7. Artefacts and reproduction

Run record `evidence/termination/build_A_50ohm_p51_ghostwave.json` (19.6 KB,
tracked). Field dump `evidence/termination/build_A_50ohm_p51_ghostwave_fields.npz`
(12.9 MB, deliberately NOT tracked; `*.npz` is gitignored and the run repeats in
38.5 s). Renderer `evidence/termination/render_fields.py`, producing
`ez_slice_station4.png`, `ez_3d_station4.png` and `ez_envelope.png` under
`evidence/termination/figures/`.

Command:

    python evidence/termination/render_fields.py

Note: pyvista and vtk are not installed in the worker container and pip has no
network there, so the verified renders are matplotlib, including the 3-D one (an
mplot3d surface). The pyvista path is written and is used automatically wherever
pyvista is importable.
