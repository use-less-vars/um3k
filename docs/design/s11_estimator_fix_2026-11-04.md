# s11 estimator fix - one beta for both de-embeds (2026-11-04)

## 1. The change

`emfit/studies.py:3387`, inside `microstrip_wave` (def at :2467), one line:

-    beta = float(fit_one.beta)
+    beta = float(fit_two.beta)

`fit_one` = `fit_beta(station_x, v_stations, n_wave=1)` (:3385), `fit_two` = `fit_beta(station_x, v_stations, n_wave=2)` (:3386). One variable moves and nothing else in the file changes. No None guard: `fit_beta` is declared `-> BetaFit` (`emfit/ports.py:861`) and has a single `return BetaFit(` (:967), so `fit_two` is never None on any reachable path and a guard would be unreachable code.

## 2. Why

`docs/design/s11_frame_pin_2026-11-04.md` section 3 pins the TE reference at the LOAD plane (F2, d = 0.0168 m): the TE phase is (Z-Z0)/(Z+Z0) applied to the impedance measured on the load's own node column, which is a point reflection coefficient with no propagation term, so the reference sits wherever that impedance was measured. Under F2 the one-wave/two-wave substitution moves the s11 phase residual from -52.92 deg to +7.37 deg (`s11_phase_investigation_2026-11-04.md` section 5). The de-embed has been quoting `beta_one` throughout.

## 3. Pre-registered prediction, frozen before the run

`s11.phase_deg` moves from -160.26362819520853 to approximately **-115.04 deg**: delta = **+45.2182 deg** = 2*(beta_one - beta_two)*0.0072, with beta_one = 286.35930483082825 and beta_two_wave = 231.55331672912826 rad/m. Second pre-registered outcome: the F2 TE residual moves from -52.92 to **+7.37 deg**.

## 4. Brackets (delta measured against the -160.26 baseline)

| bracket | delta | reading |
|---|---|---|
| **A** | +45.2 +/- 3 deg | beta_one was in play; the fix works |
| **B** | 0 +/- 3 deg | beta_one was NOT in play; another code path feeds the de-embed |
| **C** | -45 +/- 3 deg | sign flip in the fix, or the sign convention is wrong |
| **D** | outside all three | new information; report exactly, do not interpret |

Joint outcome: A **and** residual +7.37 +/- 2 deg -> the beta miswiring is confirmed AND the phase pathway is closed for both s11 and s21, which share this one local (`emfit/studies.py:3565` for s11, `:3659` and `:3686` for s21). A but residual off +7.37 -> something beyond the frame arithmetic contributes; report exactly and do not move the bracket.

## 5. Scope

ONE line. Deliberately NOT fixed here, all follow-ups: `s21.deembed_distance_m` records 0.0072 while the operation used the 0.0172 span (DR-26); AC-3 still grades the one-wave magnitude (DR-24); the `*_basis` prose describes a branch not taken (DR-27). DR-24..DR-29 remain reserved only and are still not in `defect_register.md`.

Status: pre-registered fix, not yet run. One line changed. No FDTD run performed.
