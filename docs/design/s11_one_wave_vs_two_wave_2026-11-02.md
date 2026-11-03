# One wave or two: why the loaded termination's `beta` and its three `s11` numbers disagree, and which of the four fits to believe

**Slug** `s11-one-wave-vs-two-wave-2026-11-02`. **Status: reads, arithmetic over banked artefacts, one
synthetic control solved here.** No write under `emfit/`, `evidence/termination/run_build_A.py`,
`tests/` or `decisions.md`; no banked artefact edited; no gate re-priced; no verdict moved; nothing
committed. Every number below is quoted from a file named beside it or is arithmetic over numbers so
quoted; the one exception is §4, which is a synthetic solve run in this pass and is labelled as such.
Three of the four measured artefacts cited are **uncommitted** and live in `.scratch/` — they are
cited by name so the reading is checkable, not to bank them.

Tags: **[M]** measured, artefact named beside it · **[L]** read from the project's own record ·
**[R]** relayed · **[UNVERIFIED]** believed, no means to check here.

---

## 1. The finding, in one paragraph

Four reference-free loaded runs of the same 64-cell line, same load plane (20.0 mm), same extraction
plane (index 51), load `series_r` swept 25 / 50 / 100 / 200 ohm, were read for every reflection the
artefact writes. **Only one of them tracks the load.** The two-wave line fit's `|Gamma|`
(`line.gamma_re`/`line.gamma_im`) runs 0.1964 / 0.3256 / 0.4758 / 0.6123 against the series-R
prediction 0.2082 / 0.3447 / 0.5126 / 0.6778 — ratio **0.9433 / 0.9446 / 0.9282 / 0.9033**, i.e.
5.7 / 5.5 / 7.2 / 9.7 % low, monotone, no kinks. The **one-wave** fit's `line.beta` runs
264.09 / 286.36 / 313.10 / 337.02 rad/m against a load-free 231.0873600620821 — **+14.3 / +23.9 /
+35.5 / +45.9 %** — and its station-fit `Z0` slides 46.26 / 44.21 / 40.98 / 37.76 ohm, **-18.4 %**
end to end. The element-on-its-own-plane reflection (`s11_at_plane`) sits on a **floor near 0.046**
and does not track the load at all. The port-plane reflection (`s11`) is monotone but roughly a factor
1.4 below the two-wave `|Gamma|`. §4 shows the one-wave `beta` excursion is **fully accounted for by
the estimator**: on synthetic data with exactly this geometry, where the true `beta` is known, the
one-wave fit returns +27.05 % and invents an `alpha` of -68.9 Np/m, while the two-wave fit returns the
truth to 0.0000 %.

---

## 2. The four-load table

All seven columns are direct key reads; nothing is fitted here. `p = 20 mm` load, `n_line 64`,
`s21_plane_index 51`, `reference = None` throughout (`run.loaded_without_reference` is `true` in every
artefact).

| R (ohm) | `|Gamma|` = hypot(`line.gamma_re`,`line.gamma_im`) | `line.beta` (rad/m) | `run.station_fit.z0` (ohm) | `s11.magnitude` | `s11_at_plane.magnitude` | predicted `R/(2*47.5366+R)` | ratio |
|---|---|---|---|---|---|---|---|
| 25 | 0.1964113 | 264.0905834 | 46.262524 + j1.134200 | 0.1370889 | 0.0222068 | 0.2082063 | 0.943349 (-5.67 %) |
| 50 | 0.3255649 | 286.3593048 | 44.207501 + j0.379446 | 0.0337934 [^1] | **absent** [^1] | 0.3446536 | 0.944615 (-5.54 %) |
| 100 | 0.4758226 | 313.1000246 | 40.980898 - j0.268207 | 0.3558991 | 0.0475084 | 0.5126281 | 0.928202 (-7.18 %) |
| 200 | 0.6122889 | 337.0215042 | 37.756223 - j0.398273 | 0.4888837 | 0.0463117 | 0.6777979 | 0.903350 (-9.66 %) |

[^1]: The R = 50 row is `evidence/termination/build_A_50ohm_p51_noref.json`, the only one of the four
    that is **committed**, and it was written by the **old writer**: it has no `s11_at_plane` block at
    all, and its `s11.magnitude` **0.03379343163562476** is bit-identical to its `gamma_plane.abs`, i.e.
    the plane quantity under the port name. The 25 / 100 / 200 ohm rows are `.scratch/` runs written by
    the current writer, where `s11` is `gamma_port` and `s11_at_plane` is `gamma_plane`. The column
    labelled `s11.magnitude` therefore mixes two quantities between its own rows — see §5. The R = 50
    *port* number, **0.23216690987276836**, is only available from the separate twin artefact
    `evidence/termination/build_A_50ohm_twin_p51_s11fix.json`, whose plane quantity is
    **0.0489985288420461**.

Artefacts: `.scratch/build_A_25ohm_p20_p51_noref.json`, `…100ohm…`, `…200ohm…` (uncommitted),
`evidence/termination/build_A_50ohm_p51_noref.json`, `evidence/termination/build_A_50ohm_twin_p51_s11fix.json`.

---

## 3. `Z0` slides 18.4 % and `beta` rises 45.9 %, monotonically, with the load's resistance

`run.station_fit.z0` = 46.262524 / 44.207501 / 40.980898 / 37.756223 ohm (real part; the imaginary part
is +1.1342 / +0.3794 / -0.2682 / -0.3983 and only changes sign at 100 ohm) against a load-free
reference `Z0` of **47.53661998575833** ohm [M, `reference.zc` of the load-free twin solve, `.scratch/task2_capture.json`].
The slide is **-18.4 %** end to end and monotone; the load-free number is **-0.2 %** from the
Hammerstad-Jensen closed form 47.576 ohm [L]. A matched-load measurement that returned a *lower* `Z0`
the *more* reflecting the load becomes is not a property of the line: it is the fit moving `Z0` to
absorb what it cannot represent. The same movement is in `line.beta`, which is the **one-wave** fit
(`emfit/studies.py:3092`, `float(fit_one.beta)`) and which reads +14.3 % above the load-free 231.087 at
25 ohm and +45.9 % at 200 ohm — while `line.gamma_re,im`, the **two-wave** fit on the *same* stations
(`emfit/studies.py:3090`, `complex(fit_two.gamma)`), stays inside 9.7 % of a prediction that needs no
tuning.

So the table is internally consistent only under one reading: **the line is close to the closed form and
the one-wave estimator is the thing that moved.** §4 makes that reading a measurement rather than an
inference.

---

## 4. The synthetic control: what each estimator does when the answer is known

`fit_line` was driven directly on a synthetic pair of counter-propagating waves on the eight stations
this run actually uses (cells `[26, 29, 32, 35, 38, 41, 44, 47]`, 0.4 mm apart, span 0.0084 m — the
same `line.station_fit_cells` and `line.station_fit_span_m` the artefact records), with
`beta_true = 231.0873600620821` rad/m and `Z0 = 47.5366` ohm [M, solved in this pass,
`.scratch/a3_fitline_sanity.py`, uncommitted].

| arm | two-wave result | one-wave result |
|---|---|---|
| clean, `alpha = 0`, no backward wave (`B = 0`) | `|Gamma|` — , `alpha_fit` -0.00000, `beta_fit` 231.08736 (**+0.0000 %**) | `beta_fit` 231.08736 (**+0.0000 %**) |
| clean, `alpha = 0`, `|B/A| = 0.34465` | `|Gamma|` 0.34465, **ratio 1.00000**, `alpha_fit` +0.00000 | `beta_fit` 293.60365 (**+27.05 %**), `alpha_fit` **-68.91585** |
| real `alpha = 0.694` 1/m present, `|B/A| = 0.34465` | **ratio 0.97261**, `alpha_fit` +0.69443 | `beta_fit` 293.329 (**+26.93 %**) |

Three statements follow, and they are the load-bearing ones in this record.

1. **The two-wave fit is not biased by a standing wave.** With a backward wave at exactly the amplitude
   the R = 50 run reports (0.34465), it returns `|Gamma|` = the input amplitude to the printed precision
   (ratio 1.00000) and `alpha` = 0. The two-wave `|Gamma|` in §2 is therefore a reflection amplitude,
   not an envelope.
2. **The one-wave fit is biased by exactly the observed amount.** +27.05 % at `|B/A| = 0.34465` against
   the +23.9 % the real R = 50 run shows; and the bias is *monotone in `|B/A|`* over the whole swept
   range: **+17.9 % (0.208) → +27.1 % (0.345) → +34.6 % (0.513) → +36.0 % (0.678)**, rolling over past
   `|B/A| ≈ 0.6`. Those four `|B/A|` values are the four measured `|Gamma|` values in §2, and the
   one-wave `beta` in §2 rises **+14.3 → +23.9 → +35.5 → +45.9 %** in the same order. The correlation is
   the estimator's transfer function, not a dispersion law. (The real arm runs slightly above the
   synthetic at the same `|B/A|`, which is what a non-zero real `alpha` and a real, non-matched `Z0`
   would do; the two extra effects are not separated here.)
3. **The one-wave fit invents `alpha`.** -68.9 Np/m on lossless data, i.e. a large *negative*
   attenuation. Any `alpha` read off `line.beta`'s companion estimator on a loaded run is therefore not
   a measurement of anything physical, and is not used anywhere in this record.

**With real loss present, the two-wave amplitude is attenuated, and predictably so:** ratio 0.97261 is
`e^{-2·0.694·0.020}` = `e^{-0.02776}` exactly. That is the whole of the correction, and it is
arithmetic, not a fit.

---

## 5. Correction 1 — `s11` is three different quantities in this tree, and the key name does not say which

(1) **`s11` means `gamma_plane` in old-writer artefacts and `gamma_port` in new-writer ones.**
`evidence/termination/build_A_50ohm_p51_noref.json` has no `s11_at_plane` block and its
`s11.magnitude` **0.03379343163562476** equals its `gamma_plane.abs` to the last digit; the current
writer writes `s11` = `gamma_port` (**0.23216690987276836** in the twin artefact) *and* `s11_at_plane` =
`gamma_plane` (**0.0489985288420461**). Commit **0545834** is the writer switch that made this so. A
column read across artefacts therefore mixes quantities — that is exactly what the R = 50 footnote in §2
is warning about. **Any `s11` quoted from this tree must carry its artefact name and, where the artefact
has one, the key path `s11` vs `s11_at_plane`.**

(2) **`line.gamma_re` is a signed real part, not a magnitude, and it is not `gamma_plane`.**
`line.gamma_re` / `line.gamma_im` are the two components of the **two-wave fit's** complex `Gamma`
(`emfit/studies.py:3090`); `|Gamma|` is their hypot, 0.3255649 at R = 50, while `gamma_re` alone is
**-0.32412741798822986**. `gamma_plane` is a *different complex number* (`re +0.009290255851863938`,
`im -0.032491339891093325`, `abs 0.03379343163562476`), produced by the travelling-wave split. Reading
`gamma_re` as "the reflection" loses 0.44 % of the amplitude, loses the sign of the phase, and swaps
estimator.

(3) **`line.z0` is not `Z0`.** `line.z0_re,im` = **42.43786214405251 - j15.727993189312496** is the
port ratio `-v_port/i_trunc` (`emfit/studies.py:3254`), not the characteristic impedance; the
characteristic impedance the record means is `run.station_fit.z0_re,im` = 44.207501 + j0.379446. The two
share a key stem and differ by 5 % in real part and by a factor 41 in imaginary part.

---

## 6. Correction 2 — the "32.7 % below the series-R ideal" comparison is against the wrong `s11`, and the number that matters is 5.5 %

The port quantity 0.23216690987276836 is **32.67 %** below the `Z0 = 47.5` ohm series-R ideal 0.3448,
and that figure — carried in the `s11-port-reference-2026-11-02` row — is arithmetically correct *and
about the wrong reflection*: `gamma_port` is the station fit's own `|gamma_v|` moved to the port plane,
and the magnitude is invariant under that move (`emfit/studies.py:3266`, `deembed_reflection`, with the
preservation asserted at `:3274`). It never claimed to equal the load's reflection coefficient.

The reflection that does claim that is the two-wave `|Gamma|`, and on the same artefact its comparison
is **0.3255649 / 0.3446536 = 0.944615, i.e. 5.54 % low** — and 5.67 / 5.54 / 7.18 / 9.66 % low across
the four loads. **The correction is therefore 32.7 % → 5.4 %, on a different key.** The 32.7 % figure
stays in the log as a statement about `gamma_port`; it must not be read as the loaded line's reflection
error.

A second, independent discriminator points the same way: `s11_at_plane`'s plane quantity on the R = 50
twin artefact is **0.0489985288420461**, a factor **4.74** below the port quantity — the number the
`s11-port-reference-2026-11-02` row already reports as the ratio — and 0.0490 cannot be 5 %-accurate for
any load, since it barely moves between R = 100 and R = 200 (§7).

---

## 7. Correction 3 — `beta` 286.36 belongs to the one-wave fit, and the number to compare it with is ~230.9, not 223.35

`line.beta` **286.35930483082825** (R = 50) is `float(fit_one.beta)`, the one-wave fit. Two different
numbers were being compared to it:

- **`line.beta_model` 223.35306683909533** — a *closed form*, not a measurement of this line. Quoting
  "286.36 against a modal 223.35, +28.2 %" compares an estimator's biased output to a formula and calls
  the difference a slowing of the line.
- **~230.87** — the two-wave fit's `beta` on the same eight stations; the load-free twin's independent
  station fit lands at **231.09** [L], and the reference's own `gamma.im` is **231.0873600620821**
  [M, `.scratch/task2_capture.json`]. Three numbers agreeing to 0.1 % where the one-wave fit is 24 %
  away.

**The pair to carry is 286.36 vs 230.87, not 286.36 vs 223.35**, and §4 says what the gap is: +27.05 %
is what the one-wave estimator returns on lossless synthetic data with this `|B/A|` and no physics in
it. No dispersive, slowing or "degenerate medium" explanation is needed or supported.

**Falsification, 2026-11-03.** The gap analysis shows `line.beta` implies `eps_eff = 5.497 > eps_r = 4.4` on this geometry - physically impossible for a passive microstrip. Combined with the +24 % beta error and the 19 % Z0 slide across loads, the one-wave estimator is proven unusable, not merely biased. Cite `gap_analysis_2026-11-03.md` section H3.

---

## 8. `s11_at_plane` sits on a floor, and the floor is not the load

`s11_at_plane.magnitude` = 0.0222068 (R = 25), 0.0475084 (R = 100), 0.0463117 (R = 200); 0.0489985288420461
on the R = 50 twin artefact. Between R = 100 and R = 200 the load's reflection coefficient changes by
32 % and the plane quantity changes by **-2.5 %**, in the *opposite* direction to the prediction. The
plane is 20.4 mm from the port and 0.4 mm from the load cut (index 51 against the load at 20.0 mm);
whatever stands at 0.046–0.049 there is a floor — evanescent content that has not decayed at the cut,
plus the split's own residual — not the load. **Consequence: `s11_at_plane` can neither confirm nor
refute a load reflection at these values, and the sub-0.05 agreement between R = 100 and R = 200 is
evidence of a common floor, not of a matched load.** A load-free reference-free run at plane 51 is what
would measure that floor; it is not banked and not run here (§13).

---

## 9. The split chain is exact to 1e-16, so the disagreement is in the fit, not in the arithmetic

`gamma_plane` is recomputed here from the artefact's own `station_fit.z0` and the cut voltages by the
chain the loader writes (`emfit/studies.py:3336-3348`: `b_cut/a_cut` with `gamma_split = 0j`,
`zc_split = zc = station_fit.z0` on a reference-free run) and reproduces `gamma_plane.re/im` to
**1e-16** [M]. The three-way sensitivity check in `.scratch/task2_step3.json` gives `rho` =
0.03379343163562475 with `zc = station_fit.z0`, 0.05573320699855053 with `zc = reference.zc` and
0.05934502483146269 with `zc = 50 + 0j` — i.e. all three `zc` choices land in 0.03–0.06, none of them
near 0.23 or 0.33. So neither the split nor the choice of `zc` can produce the port quantity, and the
disagreement measured in §2 lives entirely in the station fit and in its `beta`.

---

## 10. The one paragraph about `alpha` — and why it is tagged [UNVERIFIED]

The reference's own attenuation is **3.156516450473238** Np/m [M, `reference.gamma.re`,
`.scratch/task2_capture.json`]. The *loaded* run's `alpha` is written **nowhere**: no reference-free
artefact in `evidence/termination/` carries `loss_fit.*`, `station_fit.gamma_v`, `station_fit.beta`,
`station_fit.alpha`, `station_fit.residual_v` or `alpha_np_per_m` — all six keys are absent from every
one of them, so the fitted `alpha` cannot be read back from disk and is **not obtained** here. What can
be said is bounded and arithmetic: a real `alpha` of 0.694 1/m over the 20 mm to the load attenuates the
two-wave `|Gamma|` by `e^{-2·0.694·0.020}` = 0.97261 (§4), so an unattenuated reflection of at most
0.3255649 / 0.97261 = **0.33473**, which moves the R = 50 ratio from 0.9446 to 0.9712 and the four-load
deficit from 5.5–9.7 % to 2.9–7.3 %. **That 0.694 is [UNVERIFIED] as the loaded run's `alpha`** — it is
the value used in the synthetic arm of §4 because it is the order the reference gives divided by a
factor consistent with the run's own `beta` inflation, and nothing on disk confirms it. The bound is
recorded because it is *small*: even at the largest plausible `alpha` the correction is a few per cent,
against the 24–46 % the one-wave `beta` moves. It therefore cannot change §1's conclusion, and it is
not offered as a value.

---

## 11. Reproduction

The four loaded runs (each ~107–139 s wall on this host, 338–340 MB peak RSS, `--mem-ceiling-mb 500`):

```
evidence/termination/run_build_A.py --n-line 64 --load-at-mm 20 --load-ohm  25 --mem-ceiling-mb 500 --s21-plane-index 51 --out .scratch/build_A_25ohm_p20_p51_noref.json
evidence/termination/run_build_A.py --n-line 64 --load-at-mm 20 --load-ohm  50 --mem-ceiling-mb 500 --s21-plane-index 51 --out evidence/termination/build_A_50ohm_p51_noref.json
evidence/termination/run_build_A.py --n-line 64 --load-at-mm 20 --load-ohm 100 --mem-ceiling-mb 500 --s21-plane-index 51 --out .scratch/build_A_100ohm_p20_p51_noref.json
evidence/termination/run_build_A.py --n-line 64 --load-at-mm 20 --load-ohm 200 --mem-ceiling-mb 500 --s21-plane-index 51 --out .scratch/build_A_200ohm_p20_p51_noref.json
```

The R = 50 line is the exact `meta.command_line` of the committed artefact; the other three are the same
invocation with `--load-ohm` and `--out` changed, and are **not committed**.

Every table cell in §2 is a direct read, e.g.

```
python3 -c "import json;d=json.load(open('evidence/termination/build_A_50ohm_p51_noref.json'));print(d['line']['gamma_re'],d['line']['gamma_im'],d['line']['beta'],d['run']['station_fit']['z0_re'],d['s11']['magnitude'])"
```

and the ratio column is `hypot(gamma_re, gamma_im) / (R / (2*47.53661998575833 + R))`.

The synthetic control of §4 is `.scratch/a3_fitline_sanity.py` (uncommitted): it builds the two station
waves analytically on `x = 0.0004 * [26, 29, 32, 35, 38, 41, 44, 47]` with `beta = 231.0873600620821`,
`Z0 = 47.5366`, optionally `alpha = 0.694`, and calls `fit_line(..., n_wave=1)` and
`fit_line(..., n_wave=2)` on the same array; it needs no solver, no mesh and no FDTD.

---

## 12. What this record does **not** conclude

1. **No gate is re-priced and no verdict moves.** AC-3 (|S11| ≤ 1e-3, |S21| − 1 ≤ 1e-3) fails on every
   loaded artefact and still fails; AC-7 remains unclosable in a single run. This record says which
   quantity should be graded, not what grade it gets.
2. **It does not establish that the loaded line is 5.5–9.7 % away from ideal.** The four-load ratios are
   ratios to `R/(2*47.5366+R)` at the *reference-free* `Z0`; §10 caps the `alpha`-only correction at a
   few per cent and leaves the remainder **unexplained**, not resolved.
3. **The `gamma_port` = 0.23216690987276836 anchor is unchanged and still UNVALIDATED.** It is neither
   adopted here nor dismissed; §6 only says it is not a load-reflection error.
4. **Withdrawn: the shunt reading anchored at `|s11| + |s21| = 0.0321`.** That anchor was quoted off an
   `s11` whose estimator is the plane quantity of §5; with `s11` = 0.23216690987276836 the passivity
   sum is `|s11|² + |s21|²` = 0.643046, which is 1.157× the 5/9 series-R bound — over the bound, not
   under it. The 0.0321 anchor is withdrawn as evidence for a series element and is **not replaced
   here** by the other sum, which is also not a pass.
5. **Withdrawn: the 72.6 ohm effective `Z0` at the load, and the 0.184 factor derived from it.** Both
   came from dividing a load reflection by a forward amplitude taken from the estimator §5 identifies;
   the derivation is not repairable by re-scaling, and nothing in this record restores a `Z0` at the
   load.
6. **Withdrawn: "the station fit is degenerate on this record".** The degeneracy was a property of the
   *one-wave* estimator applied to two-wave data (§4 shows it on lossless synthetic data with no fit
   pathology at all), not of the station set. Calling the data degenerate would have licensed dropping
   the result; the two-wave fit on the same stations is well conditioned and recovers the truth.
7. **It does not say the `Z0` slide of §3 is a port artefact, a mesh artefact, or stray series reactance
   at the cut.** Only that it is monotone in the load, that it is -18.4 %, and that it is too large to
   be the closed form.
8. **It does not close `s11` for grading.** Nothing here makes `gamma_port`, `gamma_plane` or the
   two-wave `|Gamma|` the authorised `s11`; that is a ruling (§13a), not a measurement.

---

## 13. Open

**(a) Which reflection is `s11` for the pipeline?** A ruling, and it is the blocking one: the three
candidates differ by up to a factor 8.4 at R = 50 (`gamma_port` 0.2322 vs `s11_at_plane` 0.0490 vs
two-wave `|Gamma|` 0.3256). This record's evidence favours the two-wave `|Gamma|` on the grounds of §2
and §4, and does not make the choice.

**(b) `alpha` and `station_fit.gamma_v` are not persisted.** Six keys are absent from every
reference-free artefact (§10). Persisting `station_fit.beta`, `.alpha`, `.gamma_v` and `.residual_v`
is a writer change under `emfit/studies.py` (fenced here) or `run_build_A.py` (fenced here); it needs a
dispatch of its own, and until it lands the `alpha` question of §10 stays [UNVERIFIED] by construction.

**(c) The plane-51 floor needs a load-free, reference-free run at plane 51.** One run, same geometry,
`--load-ohm 0` or no load at all, `--s21-plane-index 51`; that measures §8's 0.046–0.049 without a load
in it and decides whether it is evanescent residue or a split residual. Not run, not authorised here.

**(d) The residual 5.5–9.7 % of §2 is unattributed.** Candidates, none separated by this data: a `Z0`
that is not the reference-free 47.5366 at the load, the load stamp's own `dl`/`ds` discretisation, and
the `alpha` of §10. Separating them needs either a two-wave-aware `Z0` extraction at the cut (a code
change, (b)) or a load-free-vs-loaded delta at the same plane ((c)).
