# s11 distance and magnitude - what the beta substitution actually moved (2026-11-04)

Read-only dispatch `s11-distance-and-magnitude-2026-11-04`. Sources: the two artefacts, and the code
that wrote them. Nothing was changed, nothing was run.

## S1 - STEP 0: the two artefacts, read straight out of the JSON

`evidence/termination/build_A_50ohm_v3_zeff.json` (PRE, `beta = fit_one`) vs
`evidence/termination/build_A_50ohm_v3_betafix.json` (POST, `beta = fit_two`).

| field | PRE | POST |
|---|---|---|
| `line.beta` | 286.35930483082825 | 231.55331672912826 |
| `s11.phase_deg` | -160.26362819520853 | -100.49921155605985 |
| `s11.magnitude` | 0.32556486641109117 | 0.32556486641109117 (bit-identical) |
| `s11.magnitude_one_wave_station_fit` | 0.23216690987276836 | 0.32588679434738205 |
| `s11.deembed_distance_m` | 0.0072000000000000015 | 0.0072000000000000015 |
| `s21.phase_deg` | 59.49866046655281 | 5.187960321243577 |
| `s21.magnitude` | 0.7628473102840976 | 0.7644184907560716 |
| `s21.raw_phase_deg` | 137.2951714995182 | 136.99508249088075 |
| `s21.planes_m` | [0.0032, 0.0204] | [0.0032, 0.0204] |

Deltas: `d_beta = -54.8059881017` rad/m; s11 phase **+59.764416639** deg; station-fit modulus
**x1.4036746 (+40.37 %)**; s11 `magnitude` **0.0**; s21 phase **-54.310700145** deg, of which
raw-ratio **-0.300089** deg and de-embed the rest.

## S2 - the code paths (read, not run)

- `deembed_reflection` `emfit/ports.py:1673`, body `:1702-1703`: factor `exp(-2j * beta * distance)`.
  With real `beta` the modulus is exactly 1 - the docstring says so at `:1686-1696`. So this call
  can rotate a reflection, never rescale it.
- s11 call site `emfit/studies.py:3565`: `deembed_reflection(gamma_measured, beta, deembed_distance)`
  with `deembed_distance = float(station_x[0] - x_port)` (`:3562`, = 0.0072 m in both records) and
  `gamma_measured = station_fit.gamma_v` (`:3563`).
- **`beta` enters the station fit as well as the de-embed**: `station_fit` comes from
  `fit_station_impedance(fit_x, fit_v, fit_i, beta, ...)`, and `emfit/ports.py:1517` defines
  `gamma_v = complex(amp_v[1] / amp_v[0])` - the backward and forward amplitudes of a
  **two-wave least-squares fit at that `beta`** (`:1447-1451`: "Fitting both series at the same
  `beta`"). `gamma_v` is therefore a strong function of `beta` in *both* its argument and its
  modulus. A `beta` change here is not a pure phase operation.
- `line_s21` `emfit/studies.py:1243-1279`: `raw = a2/a1`, `d = x2 - x1`, then
  `deembed_transmission(raw, beta, d)`; that function `emfit/ports.py:1707` multiplies by
  `exp(+1j * beta * distance)` (`:1731-1733`) - the opposite sign to the reflection, as its
  docstring states at `:1714-1719`. `d` is the station-span gap, `0.0204 - 0.0032 = 0.0172` m.
- `magnitude_one_wave` (bare) is in **neither** artefact. The only write site of the station-fit
  number is `evidence/termination/run_build_A.py:1590`
  `"magnitude_one_wave_station_fit": finite_or_none(abs(s11))` with `s11 = complex(res.gamma_port)`
  (`:1386`); `s11.phase_deg` is `np.angle(s11)` from the same object. `s11.magnitude` is a
  *different* number: `s11_two_wave_mag = abs(complex(res.gamma))` (`:1392`), the modulus of the
  two-wave B/A from `fit_beta(n_wave=2)`, which takes no `beta` argument - hence the bit-identical
  value across the two records.
- `beta_two_station` (`emfit/studies.py:3384`) is **never** de-embedded with, fitted with, or read
  after being assigned: `:1423` docstring, `:1598` dataclass field, `:2566` comment, `:3943` result
  construction, `:4871` summary line. It reaches no de-embed and no fit.

## S3 - T1

(a) The STEP 0 numbers are as the brief stated: s11 phase moved, s11 `magnitude` did not,
`magnitude_one_wave_station_fit` moved +40.37 %, s21 phase moved -54.31 deg, and the recorded
`deembed_distance_m` is 0.0072 m in both records (s11 and s21).

(b) `s11.phase_deg` and `s11.magnitude_one_wave_station_fit` are the argument and modulus of one
object, `res.gamma_port`; `s11.magnitude` is `|res.gamma|`. They are not the same quantity and a
comparison across records must name which one it means.

(c) No. `beta_two_station` does not enter any de-embed (S2, last bullet).

## S4 - T2: opposite signs are arithmetically required, and the s21 side balances to 1e-4 deg

- s21: `d = 0.0172` m, one forward delay removed, factor `exp(+1j beta d)`:
  `d_beta * d = -54.0106111367` deg, plus the measured raw-ratio change `-0.3000890086` deg
  = **-54.3107001453** deg against an observed **-54.3107001453** deg. Exact.
- s11: `d = 0.0072` m, reflection, factor `exp(-2j beta d)`: `-2 * d_beta * d = +45.2181860679` deg.
  Observed **+59.7644166391** deg, so **+14.5462305712 deg is *not* de-embed**.

So the two records move with opposite signs because one carries `+1 * d_beta * 0.0172` and the other
`-2 * d_beta * 0.0072`: different exponent, different distance, different sign - all three by design
(`ports.py:1686-1696` and `:1714-1719` state the convention gap explicitly). The opposite signs are
**not** evidence of a sign error in `deembed_reflection`. What the s11 side leaves over is a
+14.55 deg argument change in `gamma_measured`, i.e. in the two-wave station fit run at the new
`beta` (S2, third bullet).

## S5 - T3: a 40 % modulus jump is not a phase effect, and here it is not the de-embed either

With real `beta` the de-embed factor has modulus 1, so the de-embed cannot move a modulus: any jump
in `|gamma_port|` had to be in `gamma_measured`. It was. `gamma_v` is `B_V / A_V` of a two-wave
least-squares fit **at `beta`** (`ports.py:1517`, `:1447-1451`), so the split of the measured
standing wave into forward and backward amplitudes is itself a function of `beta`; a 28.2 %
(`286.36 / 223.35 = 1.2821` against `beta_model`) over-estimate in PRE splits that energy
differently from POST's 3.7 % (`1.0367`).

Two independent numbers say the PRE split was the wrong one:

| quantity | PRE | POST | series-R anchor 0.34465 |
|---|---|---|---|
| `\|gamma_port\|` (station fit at `beta`, then de-embedded) | 0.23216691 | 0.32588679 | -32.6 % / -5.5 % |
| `\|res.gamma\|` (two-wave B/A, no `beta` input) | 0.32556487 | 0.32556487 | -5.5 % |

POST lands 0.10 % from the independent two-wave modulus and at the documented 5.5 % anchor residual;
PRE was 29 % away from that same quantity. The 40 % jump is therefore a **correction**, and it is a
second observable channel of the same `beta` error - not a de-embed artefact and not a bug in
`deembed_reflection`.

Limit of the claim: the exact 1.4037 factor is not derivable from stored scalars (it needs the
station phasors re-fitted at both values of `beta`), so the *sensitivity* magnitude is hypothesis,
not measurement. The direction and the magnitude of the residual against the anchor are measured.

## S6 - the implied distances

Recomputed from the recorded phase moves, `d_beta = -54.8059881017` rad/m:

| reading | formula | result | verdict |
|---|---|---|---|
| s11 as pure `-2 d_beta d` | `radians(59.7644) / (2*54.806)` | **9.5162 mm** | arithmetic verified, **refuted as a distance** - 14.5462 deg of that 59.7644 is `arg(gamma_v)`, not de-embed |
| s21 as pure `+ d_beta d` | `radians(54.3107) / 54.806` | **17.2956 mm** | verified - and it *is* the s21 plane span (`0.0204 - 0.0032`); DR-26's 17.2 mm is corroborated as the transmission geometry |
| s21 read with the reflection's factor of two | `radians(54.3107) / (2*54.806)` | **8.6478 mm** | refuted - one forward delay is removed for a transmission, not two |
| recorded `deembed_distance_m` | `station_x[0] - x_port` | **7.2000 mm** | verified in code and in both records |

No single distance satisfies both records: s11 needs 9.516 mm at `-2 d_beta`, s21 needs 17.296 mm at
`+d_beta`. They are different quantities over different spans (reflection to the port plane vs
transmission across the station span), so a shared "distance" that reconciles them does not exist and
looking for one is the wrong test. DR-26's 17.2 mm is not in conflict with the 7.2 mm - it is the
s21 span, a different length in a different formula.

## S7 - what is still open

1. The +14.5462 deg s11 residual and the 1.4037 modulus factor are both attributed to the
   `beta`-dependence of `gamma_v` (`ports.py:1517`) but neither is *derived*: that needs the station
   phasors re-fitted at 286.3593 and 231.5533 rad/m, which is a scratch computation, not a doc.
2. Whether the POST s11 phase (-100.49921155605985 deg) is closer to the load-referenced truth
   cannot be answered in this frame: the frame-pin chain
   (`docs/design/s11_frame_pin_2026-11-04.md`, F2, d = 0.0168 m) has to be recomputed against the
   0.0072 m port distance actually in the code before any s11 phase is called right or wrong.
3. `s11.magnitude` being bit-identical across the two records is a property of `fit_beta(n_wave=2)`
   taking no `beta`: it is not corroboration of anything, and any brief that reads it as "the fix
   changed nothing" is reading the wrong field.
4. The brief's `T4` and the literal wording of `C1..C5` were lost when the dispatching context was
   summarised; every numeric claim they carried (9.516 / 8.647 / ~7.2 mm / 17.2 mm) is answered in
   S6 by recomputation, including the signs.

Status: hypothesis, unresolved. Read-only. No code changed. No run performed by this dispatch.
