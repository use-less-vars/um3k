# s11 beta test - pre-launch brief (2026-11-04)

One host run that separates `beta_one` from `beta_two_wave` in the recorded s11 phase by differential measurement. Read-only: **no code change is implied by this run** (see CLI gap).

## What is replicated

Baseline `evidence/termination/build_A_50ohm_v3_zeff.json`: build A, series R = 50 ohm at column 50 (x = 0.0200 m), n_line 64, s21 plane 51, cell 0.4 mm, station set 10.4-20.0 mm x 9 stations (`emfit/studies.py:1178-1180`) - held FIXED, it is part of the observable. Recorded: `s11.phase_deg` = -160.26362819520853, `s11.magnitude` = 0.32556486641109117, `line.beta` = 286.35930483082825, `line.beta_two_wave` = 231.55331672912826.

Exactly one variable moves: `ix_port` 8 -> 16, i.e. x_port 3.2 -> 6.4 mm (`run_build_A.py:1411`). Station 0 stays at 10.4 mm, so d = 10.4 - x_port goes 7.2 -> 4.0 mm, delta_d = -0.0032 m.

Graded quantity: `delta_phase := phase(ix16) - phase(ix8)`, same leaf `s11.phase_deg`, wrapped to (-180, 180]. Sign convention: the de-embed SUBTRACTS `2*beta*d`, so shortening d RAISES the recorded phase; the investigation doc's section-5 table writes `2*beta*delta_d = -105.0` because it quotes phase(ix8)-phase(ix16). Same arithmetic, opposite sign - `delta_phase` above is the definition.

## Frame independence (labelled, not assumed away)

The differential reads the recorded phase, which is the ONE de-embed leg only. The F1 cancellation in `s11_phase_investigation_2026-11-04.md` is a two-leg property - both legs share d - so a one-leg distance change is NOT cancelled by it, and the numbers below hold in F1 or F2 alike (frame pinned in `s11_frame_pin_2026-11-04.md`; verdict F2, d_load = 0.0168). Caveat: at ix16 the source sits 4.0 mm (10 cells) from station 0 instead of 7.2 mm (18 cells), so station-fit contamination is a real systematic outside both brackets - that is what Bracket C is for.

## Pre-registered predictions (frozen before the run)

- **Bracket A - `beta_one` (286.3593): delta_phase = +105.0 deg**, i.e. `2*beta_one*0.0032 = +1.8327 rad`; exact +105.0059 deg.
- **Bracket B - `beta_two_wave` (231.5533): delta_phase = +84.9 deg**, `+1.4819 rad`; exact +84.9090 deg. A-B separation 20.0970 deg.
- **Bracket C - anything else: INFORMATIVE, not a failure.** Report the exact number and claim neither A nor B.

Convenience only, contingent on the station fit not moving (station plane +76.0000): predicted phase(ix16) = -55.2574 deg (A) / -30.1362 deg (B). +-3 deg is tight ON PURPOSE - the brackets are only 20.1 deg apart, so a loose gate would not discriminate, and a miss is the more informative outcome.
