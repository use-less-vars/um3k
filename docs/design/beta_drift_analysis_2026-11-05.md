# Beta drift across the three load-free twins — is the `beta` vs `beta_model` gap a mesh artefact?

**Date** 2026-11-05 (session date) · **Type** read-only analysis, one doc written, **no code change, no run, no evidence edit, nothing re-graded.**
**Question** the artefacts carry `line.beta` = 229.5–232.7 rad/m beside `line.beta_model` = 223.35306683909533 rad/m, i.e. **+2.7 % to +4.2 % high**. Three load-free twins differ in `n_line`. If `beta` is a mesh-refinement sequence, extrapolating it to infinite refinement should land on the Hammerstad number. Does it?

**The file wins.** Every number below was parsed out of `evidence/termination/*.json` by this session. Where a value the operator quoted is not in any file, that is stated and the file's value is used instead (§2.2, §6.1).

---

## 1. Population — the three load-free twins (only three exist)

| # | file | `n_line` | grid `nx×ny×nz` | β rad/m | β/β_model | `eps_eff` (file) | `eps_eff` from β | Δ |
|---|---|---|---|---|---|---|---|---|
| A | `build_A_50ohm_v3_twin.json` | 54 | 62×212×22 | **232.73432451555712** | +4.200 % | 3.6307412162627744 | 3.630741 | **+0.0000 %** |
| B | `build_A_50ohm_twin_p51_twin.json` *(also `…_s11fix_twin`, `…_v3c_twin`, `…_v3_twin_check_twin` — byte-identical β)* | 64 | 72×212×22 | **231.0873600620821** | +3.463 % | 3.5795365321344415 | 3.579537 | **+0.0000 %** |
| E | `build_E_50ohm_v3d_twin.json` | 79 | 87×212×22 | **229.49183675350866** | +2.748 % | 3.5302779521649104 | 3.530278 | **+0.0000 %** |

Common to all three: `line.beta_model` = `line.eps_eff_model` = 3.3439383100189377 · no load (`geometry.loads` = `[]`, `run.loaded_without_reference` false) · `station_span_m` 0.0096 · 9 stations at 10.4→20.0 mm (cells 26…50), 3-cell spacing · `dt` 7.626299478123987e-13, `nsteps` 2400 (`n_warm` 600 / `n_acc` 1800) · f 5.827786408327286e9 Hz · `n_strip` 8 · `n_clean` 96.
`build_smoke_50ohm_twin.json` (52×212×22, β 235.184, |S21| 0.00289) is a broken smoke record and is **excluded**.

`eps_eff` is not a second measurement: `eps_eff = (beta*C0/(2*pi*f0))**2` is written one line after β at **`emfit/studies.py:3543`**. Reproducing the stored value to 0.0000 % in all three rows is a **PASS on internal consistency**, and proves nothing about β — it is the same number.

---

## 2. Two framing corrections

### 2.1 This is not a mesh-refinement series. dx does not move.

`geometry.cell` = `cell_m` = **0.0004 m** and `run.kwargs.cell` = `'h / n_sub'` (h = 1.6 mm, `n_sub` = 4) in **all** records ⇒ **dx = dy = dz = 0.4 mm identically**. What moves is `nx = n_pml(6) + n_ref(2) + n_line` → 62 / 72 / 87 cells, i.e. the **domain x-length** `geometry.length` = nx·0.4 mm = **24.8 / 28.8 / 34.8 mm**. `ny`/`nz` are frozen at 212/22.
**Consequence:** the abscissa is *domain length past the stations*, not cell size. β(n_line) is a **truncation** series (how much padded line sits between the last station and the PML), and no amount of it can diagnose a discretisation error. The stations themselves span 10.4–20.0 mm in all three runs, so the station window is **identical**; only the line beyond station 9 and the absorber end move.

### 2.2 The operator's file mapping does not match the files

| operator said | the file actually says |
|---|---|
| `build_A_50ohm_twin_p51.json` = 62×212×22, n_line 54, β 232.734 | **72×212×22, n_line 64, β 231.0873600620821** |
| `build_B_100ohm_v3d_p51_twin.json` = 87×212×22, n_line 79, β 229.492 | **62×212×22, n_line 54, β 232.73432451555712** |
| (the 87×212×22 / n_line 79 / β 229.492 record) | `build_E_50ohm_v3d_twin.json` |

Also note `build_A_50ohm_twin_p51.json` is itself a **loaded** record (β 286.35930483082825); its load-free twin is `build_A_50ohm_twin_p51_twin.json`. Nothing in this doc depends on the operator's labels — the table in §1 is the population.

---

## 3. The series, and what it does

β is monotone decreasing in domain length: **−0.324249 rad/m per mm** over 24.8→34.8 mm.

| model | β_inf rad/m | vs β_model (223.35306683909533) | max residual |
|---|---|---|---|
| β(L) linear | 240.5233 | **+7.688 %** | 2.30e-01 |
| β(1/L) | 221.4292 | **−0.861 %** | 5.32e-02 |
| β(1/L²) | 226.1673 | **+1.260 %** | 3.74e-02 |
| 2-point 1/L (24.8, 34.8) | 221.4505 | −0.852 % | 0 |
| 2-point 1/L² (24.8, 34.8) | 226.1458 | +1.250 % | 0 |

**Three points, two free parameters per model ⇒ every model above is exactly determined and its residual is a property of the rounded table, not evidence.** The spread of the extrapolants (**−0.86 % to +7.69 %**) is ~15× the 0.5 % bracket the question is graded on. **No model-independent β_inf exists in this population**, and the family is too small to select a model. Any single quoted β_inf would be a choice of model, not a measurement.

---

## 4. β inside the downstream numbers — does the drift buy anything back?

### 4.1 STEP 3 — `Z_plane`: β-free by construction

* `z_plane_ohm = zc * (1 + gamma_plane) / (1 - gamma_plane)` — **`emfit/studies.py:2444-2448`** (`z_ohm`). No β anywhere in this expression.
* `gamma_plane = b_cut / a_cut` — **`emfit/studies.py:3653`**, both amplitudes formed **on one plane** `x_cut` (`forward_wave_amplitude` / `backward_wave_amplitude`, `:3641-3652`). A single-plane ratio carries no propagation factor ⇒ **no β**.
* The only β-dependent factor is `zc = complex(station_fit.z0)` — **`emfit/studies.py:3601`** — and `z0 = complex(amp_v[0] / amp_i[0])` — **`emfit/ports.py:1516`** — whose basis is `forward = np.exp(-(alpha + 1j*beta) * z)` / `np.column_stack((forward, np.exp((alpha + 1j*beta) * z)))` — **`emfit/ports.py:804, 817, 820`**.

Because `z_plane` is *exactly proportional* to `zc`, the fractional change in `Z_plane` equals the fractional change in the fitted `zc`. Measured with `emfit.ports.fit_station_impedance` on exact two-wave data at 9 stations over the record's own 9.6 mm span (`zc_true` 44.207500737130495 + 0.3794459968505162j, `gamma_v` 0.006763509427404474 + 0.008891638046269575j — the twin's own values, β0 = 231.0873600620821):

| β used | Δβ | Re zc | Im zc | **ΔRe(Z_plane)** |
|---|---|---|---|---|
| 231.0874 | baseline | 44.2075 | +0.3794 | — |
| 227.8521 (−1.4 %) | −3.2352 | 44.2153 | +0.3795 | **+0.0176 %** |
| 221.8439 (−4.0 %) | −9.2435 | 44.2301 | +0.3796 | **+0.0511 %** |
| 223.3531 (Hammerstad) | −7.7343 | 44.2263 | +0.3796 | **+0.0426 %** |
| 240.7930 (+4.2 %) | +9.7057 | 44.1851 | +0.3793 | **−0.0507 %** |

**Verdict: `Z_plane` is ~β-blind.** A 4 % error in β moves it by 0.05 % (a factor ~80 smaller). The 82.115 − j20.782 figure quoted to this doc is **not in any twin artefact** — the twins carry no `z_plane` field at all (`/s11/basis`: "gamma_plane is nan on every record extracted over the station span"); the only `z_plane_ohm` on disk is `evidence/termination/build_A_50ohm_v3_settling.json` `/s11_settling/z_plane_ohm` = **44.96581035387751 − 2.5379675807982722j** at `beta_used` **286.35930483082825** with `reference_zc` 44.207500737130495 + 0.3794459968505162j. That baseline — not the quoted one — is the one above.

### 4.2 STEP 4 — the de-embed carries β **once**, and cannot touch a magnitude

`deembed_reflection` — **`emfit/ports.py:1673`**, multiplier at **`:1702-1703`**:
```python
out = np.asarray(gamma, dtype=complex) * np.exp(-2j * complex(beta) * float(distance))
```
One multiplicative factor; the `2` is the reflection's round trip, **not** a second β application. Caller: `gamma_port = deembed_reflection(gamma_measured, beta, deembed_distance)` — **`emfit/studies.py:3565`**; the same exponent is stored at **`emfit/studies.py:3989-3990`**. `deembed_distance_m` = **0.0072000000000000015** (`s11.deembed_distance_m`).

**The magnitude cannot move:** |exp(−2jβd)| = 1.000000000000000 exactly for real β, and this is *enforced in code* — assert at **`emfit/studies.py:3571-3575`** ("`de-embedding changed |gamma| with a real beta`"). So no β error can change a single |S| or any tolerance; **the entire β lever is phase**, with ∂φ/∂β = −2d = **−0.0144 rad per rad/m**:

| β used | Δβ | Δφ (`d` = 7.2 mm) | ‖factor‖ |
|---|---|---|---|
| 232.7343 (baseline, A) | — | — | 1.000000000000000 |
| 229.4760 (−1.4 %) | −3.2583 | **+2.688°** | 1.000000000000000 |
| 223.4250 (−4.0 %) | −9.3094 | **+7.681°** | 1.000000000000000 |
| 223.3531 (Hammerstad) | −9.3813 | **+7.740°** | 1.000000000000000 |
| 242.5092 (+4.2 %) | +9.7748 | **−8.065°** | 1.000000000000000 |

From the B baseline (231.0874): −1.4 % → +2.669°, Hammerstad → +6.381°, +4.2 % → −8.008°.

**But `gamma_measured` itself is β-hungry.** `gamma_measured = station_fit.gamma_v` (`emfit/studies.py:3564`) = `amp_v[1]/amp_v[0]` (`emfit/ports.py:1517`), fitted on the same β-dependent basis. In the same synthetic refit, |γ_v| moved **+70.4 % at −1.4 % β, +204.5 % at −4 %, +170.4 % at Hammerstad** (0.0110 → 0.0170 / 0.0335 / 0.0298), with residual_v 5e-16 → 6e-3 / 2e-2. So:
* **the de-embed cannot change `|S11|`** (assert-enforced, exactly one β, magnitude untouched);
* **the fit that produces `|S11|` changes a lot with β** — which is exactly why the recorded |S11| runs 0.0035 / 0.0111 / 0.0030 across the three twins;
* `|S11|`'s *phase* takes both: Δarg ≈ Δarg γ_v − 2Δβd, and for a −1.4 % β the two arms are +1.8° and +2.7° — same order, so **neither may be dropped**.

---

## 5. Grading (as issued; thresholds applied literally)

1. **"identical dx"** — **PASS**, and it is the finding: dx = dy = dz = 0.4 mm in all three records; only `nx`/`L` varies (§2.1).
2. **"the three are a refinement series"** — **FAILS.** Identical cell size, three domain lengths. β(n_line) is a truncation ladder.
3. **monotone in length** — **FIRES, 3/3**, −0.324249 rad/m per mm.
4. **"β_inf within 0.5 % of 223.35306683909533"** — **UNGRADEABLE as posed.** 1/L gives −0.861 % (passes a 1 % bar, fails 0.5 %); 1/L² gives +1.260 %; linear-in-L gives +7.688 %. Three points cannot separate the models (§3).
5. **`eps_eff` consistent with β** — **PASS, 3/3, 0.0000 %.**
6. **Does the domain-length axis explain the +2.7…+4.2 % β gap?** **NO.** The offset *shrinks* with domain length (−1.45 pp over +10 mm) but no extrapolant reaches 223.353 except 1/L, and 1/L is indistinguishable from 1/L² on 3 points. **The truncation ladder does not close the gap**; the remaining candidates are the cross-section discretisation (`ny` = 212, `nz` = 22 — never varied here) and the extraction itself.

---

## 6. Limitations, stated so they cannot be read past

1. **n = 3.** Every extrapolant in §3 is exactly determined. Nothing here is a convergence result; it is a table with two fitted parameters and one degree of freedom too few.
2. **The length axis is not clean.** `alpha_np_per_m` is 1.4999067748813653 / 3.156516450473238 / **−0.07251138428904241** in A / B / E — the loss fit is not converged (E's is *negative*, which no passive line produces). α and `n_line` move together, so the series is confounded.
3. **β is not a per-geometry constant in these artefacts.** Loaded siblings of the same cross-section carry `line.beta` 286.35930483082825 (n_line 64) / 286.86868916283123 (n_line 54) / 173.41213731608636 (E), against 229.5–232.7 for every load-free twin; and `build_A_50ohm_v3_settling.json` de-embeds with `beta_used` **286.35930483082825** while its own twin's line fit is **231.0873600620821** — a 24 % spread inside one batch. β is being read off whatever standing-wave content the record happens to have.
4. **`n_clean` = 96** in these artefacts against a library default of 12 (`emfit/studies.py:1199`), and the 72-grid twin's `run.reference_exponent` is **1.7917** against **1.75** on the 62-grid — two further axes that move with the grid in this population.
5. **`gamma_plane` is nan on every twin** (`/s11/basis` in the artefacts), so no `Z_plane` exists in this population to test against; §4.1's sensitivity is computed from the record's own `zc`/`gamma_v` through the library's own `fit_station_impedance`, not read from a field.
6. **The 82.115 − j20.782 quoted baseline is not on disk** for these records (§4.1). Graded against the file's 44.96581035387751 − 2.5379675807982722j instead.

---

## 7. Disposition

* **No host run is licensed by this analysis, and none was performed.** The `--mesh-factor` route stays cancelled: it was conditional on a spatial-collocation defect that did not fire, and this doc adds no new reason to refine dx — β here never saw a dx change to respond to.
* The only test that *this* ladder can still address is **truncation**: a fourth and fifth `n_line` at fixed dx would give the models a chance to separate. It is named here as an option, **not** recommended, and not authorised.
* **Nothing was written outside this file: no source edit, no evidence edit, no other doc, no commit.**
