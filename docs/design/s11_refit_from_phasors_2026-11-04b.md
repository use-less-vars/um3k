# S11 refit from the record's own station phasors

- Dispatch `s11-refit-from-phasors-2026-11-04b`, 2026-11-04. **Read-only**: one doc + one log row.
- Re-runs the preceding `...-2026-11-04` doc's *"DATA: refit NOT possible - no per-station phasors are banked"*, now that `s11-writer-station-phasors-2026-11-04` banks them.

## Verdict

The **+40.367460 %** one-wave jump in `s11.magnitude_one_wave_station_fit` (0.23216690987276836 -> 0.32588679434738205) is now **DERIVED, not inferred**: it is reproduced from the POST record's own banked phasors by `emfit.ports.fit_station_impedance(x, v, i, beta)` -- the exact routine the claim names -- with the shift to the port plane done by `emfit.ports.deembed_reflection`. The recovery path is self-validating twice over: `fit_beta(x, v, n_wave=2)` reproduces the recorded `beta_two` 231.55331672912826 at **delta 0.0**, and the refit at the reconstructed `beta_one` 286.35930483082825 reproduces the pre-fix artefact's |gamma_port| 0.23216690987276836 **bit-for-bit**. Nothing here is a field test, an FDTD run, or an inference from a phase difference: the numbers come from stored phasors. The only residual is the 3.219e-4 gap between |gamma_v|@beta_two (0.32588679434738205) and the two-wave `s11.magnitude` (0.32556486641109117) -- a different estimator, still unexplained (C1, §5c).

## 1. Inputs, quoted

`evidence/termination/build_A_50ohm_p51_phasors.json`, `/s11/station_phasors` (status `ok`):

| field | value |
|---|---|
| `n` / `js` | 9 / `[26, 29, 32, 35, 38, 41, 44, 47, 50]` |
| `x_m` | 0.0104 ... 0.0200 (`0.02` is the load column) |
| `fit_selected` | 8 x `true`, then `false` (sum 8) |
| `fit_x` | 0.0104, 0.0116, 0.0128, 0.014, 0.0152, 0.0164, 0.0176, 0.0188 |
| `beta_one` | **null** |
| `beta_two` / `beta_used` | 231.55331672912826 / 231.55331672912826 |
| `deembed_distance_m` | 0.0072000000000000015 |

Targets on the record: `s11.magnitude` 0.32556486641109117, `s11.magnitude_one_wave_station_fit` 0.32588679434738205, `s11.phase_deg` -100.49921155605985, `s21.magnitude` 0.7644184907560716.

`beta_one` is **not stored** and the block says so ("beta_one is null: the n_wave=1 phase constant is not stored on the record"). It is **reconstructed**, with the library's own `emfit.ports.fit_beta(x_m, v, i, n_wave=1)` (`emfit/ports.py:861`; the same call `emfit/studies.py:3386` makes) over all nine stations. The reconstruction is checked by the same call at `n_wave=2`: 231.55331672912826, delta from the recorded `beta_two` **0.0**.

## 2. Result table 1 - the same 8 stations at the two betas

`fit_station_impedance(x[sel], v[sel], i[sel], beta)` -> `gamma_v = amp_v[1]/amp_v[0]` (`emfit/ports.py:1517`), then `deembed_reflection(gamma_v, beta, 0.0072)` (`:1673`).

| beta | rad/m | \|gamma_v\| | arg gamma_v (deg) | \|gamma_port\| | z0 (ohm) |
|---|---|---|---|---|---|
| one, reconstructed | 286.35930483082825 | 0.23216690987276833 | 75.99975791672752 | 0.23216690987276836 | 44.207500737130495 + 0.3794459968505162j |
| two, recorded | 231.55331672912826 | 0.32588679434738205 | 90.5459884879649 | 0.32588679434738205 | 47.364066848187235 + 1.6449807931078728j |

Both z0 rows reproduce a **stored** number, which is the cross-check that this is the routine the writer used: the `beta_two` row *is* `run.station_fit` (z0_re 47.364066848187235, z0_im 1.6449807931078728, span 0.0084); the `beta_one` row *is* the pre-fix record's `run.station_fit` (44.207500737130495 + j0.3794459968505162). The de-embed moves the phase and not the modulus, as the `< 1e-9` guard at `emfit/studies.py:3572-3576` requires.

Ratio `|gamma_v|@two / |gamma_v|@one` = **1.403674599993487**; observed jump 0.32588679434738205 / 0.23216690987276836 = **1.4036745999934868**; relative difference **2.22e-16**.

## 3. Result table 2 - the matched PRE/POST pair (plane 51, flux off)

A PRE file must be flux-off at plane 51: `build_A_50ohm_v3_flux_p51.json` is **flux_projection = True** (`s21` 0.46841917252219006), so it is **not** the s21 baseline. `..._v3_zeff`, `..._v3_settling`, `..._v3_lumped_check` and `..._v3_flux_off_pin` agree bit-for-bit on all three fields below.

| field | PRE `build_A_50ohm_v3_flux_off_pin.json` | POST `build_A_50ohm_p51_phasors.json` | delta |
|---|---|---|---|
| `s11.magnitude` | 0.32556486641109117 | 0.32556486641109117 | **0.0** |
| `s11.magnitude_one_wave_station_fit` | 0.23216690987276836 | 0.32588679434738205 | **+40.367460 %** |
| `s21.magnitude` | 0.7628473102840976 | 0.7644184907560716 | **+0.2059 %** |

`build_A_50ohm_p51_phasors.json` and `build_A_50ohm_v3_betafix.json` carry identical numbers. The "~+0.2 %" s21 move is **confirmed** at +0.2059 %; `s11.magnitude` does not move at all, in every non-modal artefact -- the two-wave fitted modulus is beta-free. Only `build_A_50ohm_v3_modal.json` differs (one-wave 0.23202604, magnitude 0.32542054).

## 4. Pre-registered checks

- **C1 - FAILS as written, HOLDS on the field the claim is about.** C1 asked the refit's |gamma_v|@beta_two to equal `s11.magnitude` 0.32556486641109117. It misses by **3.219e-4** (0.099 %). `s11.magnitude` is `res.gamma` from `fit_two`, a *different* estimator; the field that carries the station-fit `gamma_v` is `s11.magnitude_one_wave_station_fit`, and against that the refit is exact (delta **0.0**). Recorded as FAIL: the check names the wrong key, and a mis-specified check is not silently re-scored.
- **C2 - HOLDS.** |gamma_port|@beta_one = 0.23216690987276836 is bit-identical to the pre-fix value. The shape of the validation matters: the PRE file has **no** `station_phasors` block, so the refit necessarily runs on the POST record's phasors -- and that is what keeps it non-circular, because those same phasors reproduce *both* the recorded `beta_two` (delta 0.0) *and* the pre-fix |gamma_port| at the reconstructed `beta_one`.
- **C3 - HOLDS, with the brief's ratio INVERTED.** The brief stated the jump as `|gamma_v|@one / |gamma_v|@two`; that ratio is **0.71241582629238998**, the wrong orientation. The jump is `|gamma_v|@two / |gamma_v|@one` = **1.403674599993487** against the observed 1.4036745999934868 (rel 2.2e-16).
- **Brief's 2a prediction - FAILS.** "|gamma_v| does not move with beta" is false on this record: it moves **+40.37 %**. What is beta-free is the two-wave fitted modulus `s11.magnitude`, a different quantity; the prediction conflates the two.
- **2d - HOLDS.** `|s11| / 0.307` = 1.06047, `|s21| / 0.724` = 1.05583: equal within **0.46 %**, inside the 1 % bar.
- **3 - UNTESTABLE as posed; partially answered.** The block carries no `a_port`/`a_cut`, so S21's **absolute** scale cannot be probed here. Its **beta-dependence** can: the whole fix moves `s21` by 0.2059 %, far short of the 5.5 % excess it was asked to explain, so that excess is not beta.

## 5. Honest limit

This reproduces the **arithmetic chain**, not the FDTD fields: it refits banked phasors at a reconstructed beta, so it can falsify an arithmetic account and cannot validate the solve. Three things sit outside it. (a) `beta_one` is reconstructed, not read -- it is trustworthy only to the extent that `fit_beta(n_wave=2)` reproducing `beta_two` at 0.0 validates the recovery path, which is a strong check on the *code path* and not a stored-number check on `beta_one` itself. (b) `s21`'s absolute scale is not testable from this block at all. (c) The 3.219e-4 gap between |gamma_v|@beta_two and `s11.magnitude` is **unexplained**: it is 0.099 %, twelve orders of magnitude larger than the 2e-16 match above, so it is neither a rounding artefact nor a refutation, and it is the one number in this doc left open.

## 6. One stale number noticed, not repaired

`docs/design/defect_register.md` DR-29 (and the earlier investigation) quote the station-fit z0 as 44.207500737130495 + j0.3794459968505162. On the current record that is the **beta_one** fit; the record's own `run.station_fit` is 47.364066848187235 + j1.6449807931078728, the beta_two fit. The quote is a pre-fix leftover. Outside this dispatch's write scope -- recorded, not edited.
