# Flux-projection renormaliser: the 0.61 level is `(1 + zc/η_eff)/2` — 2026-11-03 (read-only analysis, no code changed)

Scope: dispatch `flux-renorm-2026-11-03`. Read-only: no `.py` edited, no test changed, no simulation run.
Sources: `emfit/studies.py`, `emfit/ports.py`, `emfit/mode_profile.py`, `emfit/modal_harness.py`, the four
`evidence/termination/build_A_50ohm_v3_flux_p{51,55,63,65}.json` artefacts and the `_flux_off_pin` control.
FACT = quoted from source/artefact or computed from the run's own inputs; INFERENCE = labelled as such.

## Q1. The renormaliser `(1 − zc/η_eff)/(1 + zc·i_cut/v_cut)` — is it what the code is missing? No.

FACT. No constant is applied anywhere. The split is bare (`emfit/studies.py:1294`, called at 3497-3503):
`0.5 * (v + sign*zc*i) * exp(sign*gamma*x)`, with `a_cut = forward_wave_amplitude([v_cut], [i_cut], ...)`.
FACT. Which `zc`: `run.reference = null` in all five artefacts ⇒ `loaded_without_reference` is true, so
`gamma_split = 0j` and `zc_split = zc = station_fit.z0` (studies.py:3459-3479). Quoted `run.station_fit`:
44.207500737130495 + 0.3794459968505162j, `|zc| = 44.209129 Ω`.
FACT. Which `η_eff`: `sqrt(MU0/(EPS0·eps_eff))` on the mode's own `eps_eff` (`emfit/mode_profile.py:652`),
the divisor behind `h_y = −e_z/η_eff` (`mode_profile.py:717`). Rebuilt the run's own plane read-only
(`build_mode_plane`, `modal_harness.py:67`; h 1.6 mm, w 3.2 mm, eps_r 4.4, n_sub 4, k_strip 4,
iy_strip_centre 106, n_clean 96, n_air 12) on the run's grid (72,212,22; cell 0.4 mm):
**η_eff = 202.429805 Ω**, z0_power 45.865286, v_mode 9.577608 V, i_mode 0.208820 A.
DECISIVE. `zc/η_eff = 0.218392`, so the numerator is `(1 − 0.218392)/2 = 0.390804`, and the brief's own factor
on this code's numbers (`i_cut/v_cut = +1/η_eff`) is `0.781608/1.218392 = 0.64150`.
VERDICT Q1. Inapplicable. Applying it drives |s21| 0.4684 → **0.3005**, away from the 0.6553 anchor. Its
"near-cancelling, order `1/(1 − zc/η_eff)` = tens" warning rested on `zc ≈ η_eff`; the code's `zc` is 4.6×
below `η_eff`, so the numerator is 0.3908 — a factor 2.6, not tens. The premise, not the arithmetic, was wrong.

## Q2. Sign composition `i_cut = −cut_spec[1]` × `h_y = −e_z/η_eff` — which branch? Constructive.

FACT. Both channels project onto ONE index set, `e_z[j_centre, 0:n_sub]` and `h_y[j_centre, 0:n_sub]`
(studies.py:3056-3057), and `k_strip = n_sub = 4` is the strip's node layer (studies.py:2738), so the 4-edge
column runs from the ground (k=0) to just under the strip (k=3).
FACT. On that column the mode is exactly the local plane wave: `sum(e_z) = −9.577608`,
`sum(h_y) = +0.047313`, `−sum(e_z)/η_eff = 0.047313` — max deviation `0.00e+00`.
INFERENCE (the sign chain, and it is the crux). Both cut probes store `cut_signals[1]` as a raw sum of the same
`h` unknowns and both are negated at 3230, so the two share one convention; `sum(h) = −sum(e)/η_eff` then gives
`i_cut = −sum(h) = +V'/η_eff`, i.e. `a_cut = 0.5(V' + zc·V'/η_eff) = V'(1 + zc/η_eff)/2`. The lumped arm reads
|s21| = 0.76 — a collapse branch would read ≈ 0 — and that fixes the shared convention.
VERDICT Q2. Constructive (`+`); no double-negation collapse. `(1 + zc/η_eff)/2 = 0.609193`.

## Q3. Does `weights/peak` leak a scale into s21? No — provably inert.

FACT. `run.kwargs.launch = "lumped"` in all four, so the `weights/peak` branch (studies.py:2999-3036) never
runs; `flux_plane` is a fresh `build_mode_plane(..., check=False)` (3046-3052).
FACT. The probe is exactly scale-invariant: `_project_mode` (2380) is `sum(f·m)/sum(m·m)` and the call site
multiplies `sum(m)` back, so `f → λf` leaves `Σ(f·m)Σ(m)/Σ(m²)` unchanged. The unit-power scale cancels
identically — the 3120-3121 comment claims this and the algebra confirms it rather than refuting it.
FACT, measured on the rebuilt plane: cut column `m̄²/⟨m²⟩ = 0.9994961`; launch set (36 values) peak 3.378714,
mean −2.394402, `m̄²/⟨m²⟩ = 0.983126`, peak/mean 1.4111.
VERDICT Q3. Falsified as a source of the 0.61; 1.4111 is what a "modal" launch would attenuate by, and it is
inert at `launch="lumped"`.

## Q4. Decomposing the 0.61

From Q2: `ratio = (V'/V)·(1 + zc/η_eff)/(1 + zc/Z_lumped)`, denominator 2 when `I = V/zc`.
    predicted level   0.609193   (plane-independent)
    observed          0.6140 (p51)  0.6237 (p55)  0.6306 (p63)  0.6346 (p65)
    residual V'/V     1.0080       1.0238        1.0351        1.0418
So 0.6092 of the 0.61 is one number; what is left is a 0.8–4.2 % projection-shape gain drifting with the cut
plane. The physics in one line: the flux probe's second channel carries `V/η_eff`, a field ratio, where the
line carries `I = V/zc`; with `zc/η_eff = 0.218` the split adds 22 % of the second channel instead of 100 %,
roughly halving the forward amplitude. `_project_mode` cannot avoid it — `h_y = −e_z/η_eff` is the plane's own
definition (mode_profile.py:717) and the column is built from it.
VERDICT Q4. `0.61 = 0.609193 × (1.008…1.042)`.
CONSEQUENCE (pinned). The inverse constant `2/(1 + zc/η_eff) = 1.641516` restores the LEVEL — corrected
|s21| = 0.7689 / 0.7639 / 0.7548 / 0.7548 against lumped 0.7628 / 0.7462 / 0.7291 / 0.7246 — but that is the
lumped level, not the 0.6553 anchor (still ≈ +17 %), while the 1.83 % vs 5.02 % drift cut survives. The
renormaliser is a level patch, not a fix; the "flat at 0.6553" branch of the pre-registered table cannot fire.


## What could not be determined

- `v_cut`, `i_cut`, `a_cut`, `a_port` are stored nowhere (s21 subkeys only) ⇒ `V'/V` and `Z_lumped` are
  inferred; the `+` branch rests on the shared-sign argument plus the lumped arm's |s21| = 0.76.
- `line.eps_eff = null` in the artefacts; `η_eff` comes from a read-only rebuild, and the run's own plane was
  built with `check=False`, so the mode identities were never asserted at run time.
- OPEN, for the owner: whether the current channel should be a width-sum projected on the mode's H at all —
  projecting the substrate column cannot be a current. Not resolvable from code.
- No host run, no code change, no AC bar re-priced, no re-grade; `dispatch_log.md:63` is left untouched.
