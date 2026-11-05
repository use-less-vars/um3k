# Beta refit test — 2026-11-05

Dispatch `beta-refit-test-2026-11-05`. **Read-only analysis of phasors already banked on disk.**
No FDTD run, no openEMS, no edit under `evidence/`. This document was written in three passes and
the order is the point: sections 1–4 (inputs, the Step-0 concern, the **verbatim** pre-registered
brackets, and the frozen method) were on disk **before any fit was computed**. Section 5 onward was
filled in after. Nothing in §3 was edited afterwards — the git history of this file, not the file's
own assertion, is what proves that.

| pass | content | written |
|---|---|---|
| A | §1–§4 with empty results skeleton | before any computation |
| B | DR-33/34/35 into `defect_register.md`, one row into `dispatch_log.md` | before any computation |
| C | §5–§8 filled | after |

## 1. Inputs and baseline

All numbers below are read from files; every one carries its leaf path.

| input | value | source |
|---|---|---|
| station phasors | n = 9, `x_m`, `v_re`, `v_im`, `i_re`, `i_im`, `fit_selected` | `evidence/termination/build_A_50ohm_p51_phasors.json` → `/s11/station_phasors` |
| de-embed distance | 0.0072 m | same file → `/s11/station_phasors/deembed_distance_m` |
| `beta_baseline` | 231.55331672912826 rad/m | same block, `beta_two` / `beta_used` (station fit) |
| `beta_rawphase` | 223.5813 rad/m | `evidence/termination/graded_v2_refix.json` → `/criteria/AC-7/achieved/beta_fdtd_rad_per_m` = 223.58131180256908, from `delta_raw_phase_deg` = -128.1026554428571 over `dL` = 0.01 m |
| `beta_hammerstad` | 223.3531 rad/m | `line.beta_model` (Hammerstad–Jensen) in the run artefact |
| series-R anchor | \|Γ\| = 0.34465 | series-R anchor, **β-independent** |
| complex-load anchor | \|Γ\| = 0.307 | TE load-plane value 82.115 − j20.782, **β-dependent** |
| TE s11 phase prediction | −107.68 deg | β-dependent |
| TE s21 phase prediction | +9.11 deg | β-dependent |

**Baseline to reproduce, recorded here before the attempt** (all from
`evidence/termination/build_A_50ohm_p51_phasors.json`):

| quantity | recorded value |
|---|---|
| `/s11/magnitude_one_wave_station_fit` | 0.32588679434738205 |
| `/s11/phase_deg` | −100.49921155605985 |
| `/s21/magnitude` | 0.7644184907560716 |
| `/run/station_fit/z0` | 47.364066848187235 + j1.6449807931078728 |

Reproduction is by calling the library — `emfit.ports.fit_station_impedance` at
`beta_baseline` then `emfit.ports.deembed_reflection` — **not** by reimplementing it. If the
library does not return these values exactly, this document stops there and the miss is reported
as a blocker rather than papered over. Outcome: **§5.1**.

## 2. STEP 0 — concern registered before the results, and it does not move the brackets

`beta_rawphase` is extracted as a **two-plane raw phase difference on a loaded line**: the phase of
the field at one plane minus the phase at another, 10 mm apart, ``−128.1027 deg``, divided by the
span. The run that produced it was terminated with a 50 Ω load and measures ``|S11| = 0.326``
(``/s11/magnitude_one_wave_station_fit``). On a line carrying a standing wave of that strength, the
phase difference between two planes **is not** ``beta * dL``.

Write it out. On a line with forward amplitude ``A`` and reflection coefficient ``Γ`` at the
reference plane, the phasor at position ``x`` is

```
V(x) = A·exp(−jβx) · [ 1 + Γ·exp(+2jβx) ]
```

so

```
arg V(x) = arg A − βx + arg[ 1 + Γ·exp(+2jβx) ]
```

and the two-plane difference over ``Δx = dL`` is

```
Δarg = −β·dL + { arg[1 + Γ·e^{2jβ(x+dL)}] − arg[1 + Γ·e^{2jβx}] }
```

The brace is **not** zero when ``Γ ≠ 0``. Its two terms are bounded independently
(``|arg(1+Γe^{jθ})| ≤ arcsin|Γ|`` for ``|Γ| < 1``, attained at ``cosθ = −Γ``), so the raw-phase
estimator carries an error term of up to ``2·arcsin|Γ|`` in ``Δarg``, i.e. up to
``2·arcsin(0.326) = 38.06 deg`` — on a measured ``128.10 deg``. Relative to ``β·dL`` that is a
possible ``~1.6 %`` bias, one-sided-unknown, and it is **of the same order as the 0.1 % agreement
that is being used to corroborate `beta_rawphase` against Hammerstad**. The consequence is
uncomfortable and is stated here, before the data: the 0.2 %-level agreement between
`beta_rawphase` and `beta_hammerstad` is **consistent with coincidence**, not proof of
corroboration — two independent estimates can agree closely while one of them is a
standing-wave-contaminated estimator and the other is a closed form that knows nothing about loads.

This concern does **not** change the brackets. It is registered here because it decides how the
result is to be read: if the station fit's least-squares residual is materially worse at
`beta_rawphase` than at `beta_baseline`, that is evidence **about beta_rawphase itself** — the
station data, which is fitted rather than differenced, prefers a different phase constant — and it
would be counted as such. The test is run as specified and the residual is allowed to decide. No
assertion is used to resolve it.

## 3. Pre-registered brackets (verbatim, frozen before the data)

The text below was pasted unaltered from the dispatch and not edited after the numbers were seen.

P1 — at beta_rawphase, |gamma_port| in [0.32, 0.34] AND s11 phase residual < 2 deg AND s21 magnitude unchanged from baseline. If fired: the beta error explains both the magnitude and the phase residual. The extraction fix is beta-repoint, and the residual against the series-R anchor becomes the real number. This is the answer we have been looking for.

P2 — at beta_rawphase, |gamma_port| moves toward one anchor but not the other (e.g. toward 0.34465 but away from 0.307). If fired: the beta error explains part of the story; the anchor question is separate and remains open. Document which anchor moves and which does not.

P3 — at beta_rawphase, |gamma_port| moves away from both anchors. If fired: the beta error is not the whole story; there is a second mechanism. Document the direction and magnitude of the move.

P4 (falsifier) — at beta_rawphase, |gamma_port| is identical to beta_baseline (delta < 1e-6). If fired: the station-fit |gamma_v| is beta-insensitive (the de-embed asserts |factor| = 1 at studies.py:3571-3575, so |gamma_port| = |gamma_v| regardless of beta). In that case the beta error explains ONLY the phase, not the magnitude, and the magnitude residual has a different mechanism. Escalate with this specific finding.

**Brackets stand.** Thresholds are not adjusted after the data. If no bracket fires cleanly, that is
what §6 will say — the nearest bracket will not be chosen by preference.

## 4. Method (frozen before the data)

Per beta in {`beta_baseline` 231.55331672912826, `beta_rawphase` 223.5813, `beta_hammerstad` 223.3531}:

1. `emfit.ports.fit_station_impedance(x[sel], v[sel], i[sel], beta)` → `gamma_v`. The **real**
   library function, its real signature, no reimplementation. `sel` = `fit_selected` from the
   artefact, so the load-column drop rule keeps one home.
2. `emfit.ports.deembed_reflection(gamma_v, beta, 0.0072)` → `gamma_port`. Beta enters once,
   `np.exp(-2j·beta·distance)` (`emfit/ports.py:1702-1703`), caller `emfit/studies.py:3565`.
3. Report: `|gamma_port|`, `arg(gamma_port)` in deg, `z0` (Re, Im) from the fit, s21 magnitude at
   that beta, and **the fit's own least-squares residual** with the number of stations used.

The residual is required, not decoration. Beta is baked into the fit basis
(`emfit/ports.py:_fit_design`, ~:806-820), so "a beta that cannot fit the data" is a different
finding from "a beta that fits equally well but shifts the anchor". Only the residual separates them.

Comparisons are made per beta against both anchors — series-R 0.34465 (β-independent) and
complex-load 0.307 (β-dependent, via the TE load-plane value 82.115 − j20.782) — and both phase
predictions (s11 −107.68 deg, s21 +9.11 deg, both β-dependent). **The two anchors are not
interchangeable**: the complex-load anchor pairs *both* ports (it is a two-port model of the same
load), the series-R anchor has *no s21 partner* and cannot be used in a cross-port comparison. That
statement is made once here so that §7 need not repeat it per row; no cross-port comparison in this
document mixes anchors.

## 5. Results

### 5.1 Baseline reproduction — exact

| quantity | recorded in §1 | recomputed here | delta |
|---|---|---|---|
| `/s11/magnitude_one_wave_station_fit` | 0.32588679434738205 | 0.32588679434738205 | 0.0 |
| `/s11/phase_deg` | −100.49921155605985 | −100.49921155605985 | 0.0 |
| `/run/station_fit/z0` (Re) | 47.364066848187235 | 47.364066848187235 | 0.0 |
| `/run/station_fit/z0` (Im) | +1.6449807931078728 | +1.6449807931078728 | 0.0 |
| stations used | 8 of 9 | 8 of 9 (`fit_selected` False on the last) | — |

The reproduction is bit-for-bit at the printed precision, through the library calls named in §4 and
not a reimplementation. The harness is therefore not a variable in anything below: every movement in
§5.2 is attributable to the beta argument alone.

One structural fact, checked directly because §3 P4 turns on it: **|gamma_port| − |gamma_v| = 0.0**
(5.6e−17 at `beta_rawphase`). `deembed_reflection` is unit-modulus over this distance — it applies
`exp(−2j·beta·0.0072)` and nothing else — so `|gamma_port|` inherits its magnitude entirely from the
fit's `gamma_v`, and beta can reach that magnitude only by changing the fitted `gamma_v` itself.

### 5.2 Per-beta results

| beta (rad/m) | source | \|Γ_port\| | arg Γ_port (deg) | z0 Re (Ω) | z0 Im (Ω) | eps_eff |
|---|---|---|---|---|---|---|
| 231.55331672912826 | baseline (station fit) | 0.32588679434738205 | −100.49921155605985 | 47.364066848187235 | +1.6449807931078728 | 3.593986 |
| 223.58131180256908 | rawphase (`graded_v2_refix` AC-7) | 0.3420459260106945 | −91.43910536199752 | 47.925014908638346 | +1.8768221044532465 | 3.350776 |
| 223.35306683909533 | Hammerstad–Jensen | 0.34251672805157274 | −91.17848893535056 | 47.941475429860304 | +1.8836598408501508 | 3.343938 |

Movement from baseline to rawphase, decomposed by the §4 steps:

| component | value |
|---|---|
| Δ\|Γ_port\| | +0.016159131663312398 (+4.96 %) |
| Δ arg Γ_port, total | +9.060106 deg |
| — of which the de-embed alone, 2·Δβ·0.0072 | +6.577376 deg |
| — of which the `gamma_v` rotation (beta enters the fit basis) | +2.482730 deg |

The phase move is therefore mostly (73 %) the de-embed term, as the mechanism predicts — but not
entirely. The 2.48 deg `gamma_v` rotation is the only route by which beta reaches the magnitude, and
it is the route that matters below.

### 5.3 Residuals — the discriminator

The station fit's own least-squares residual is the one number here that depends on neither anchor and
neither predicted phase. §4 made it mandatory for exactly that reason.

| beta | resid_v | ratio vs baseline | resid_i | ratio vs baseline |
|---|---|---|---|---|
| 231.55331672912826 (baseline) | 0.0011009800639328231 | 1.000 | 0.008530219772017723 | 1.000 |
| 223.58131180256908 (rawphase) | 0.009050129916783674 | **8.220×** | 0.008418226158434152 | 0.987× |
| 223.35306683909533 (hammerstad) | 0.009317826552826132 | **8.463×** | 0.008742188421963223 | 1.025× |

**Verdict of the residual: the station data reject the lower beta.** `resid_v` is 8.2× worse at
`beta_rawphase`; `resid_i` is flat (0.99×, 1.03×). So what beta breaks is the *voltage* consistency
of the fit, not the current one. Per §2 this is evidence **about `beta_rawphase` itself**, and §2
committed in advance to counting it as such.

### 5.4 s21

The s21 magnitude leaf is 0.7644184907560716 — `raw_magnitude`, **beta-invariant by construction**,
not beta-insensitive-modulo-noise. There is no refit path: this artefact carries no `a_port`/`a_cut`
leaves, and `/run/reference` is null while `/run/loaded_without_reference` is true (the contested basis
string already tracked as DR-27). P1's third clause therefore could not fire whatever the data said,
and its passing would have proved nothing.

s21 phase, at baseline beta: **5.187960321243577** vs the TE prediction **+9.11 deg** → residual
**−3.922 deg**.

## 6. Which bracket fired

| bracket | condition (as worded in §3) | measured | fired |
|---|---|---|---|
| P1 | \|Γ_port\| ∈ [0.32, 0.34] **and** s11 phase residual < 2 deg **and** s21 magnitude unchanged | \|Γ_port\| = 0.342046 → **above 0.34**; s11 phase residual **16.24 deg**; s21 clause **vacuous** (§5.4) | **no** — all three clauses fail |
| P2 | \|Γ_port\| moves toward one anchor but not the other (e.g. toward 0.34465, away from 0.307) | toward series-R to −0.76 %, away from complex-load to +11.42 % (§7.1) | **YES** |
| P3 | \|Γ_port\| moves away from **both** anchors | moves toward series-R | **no** |
| P4 | \|Γ_port\| identical to baseline (delta < 1e−6) | delta = 0.0162 | **no** — but the mechanism it names is present (§5.1: unit-modulus de-embed, so magnitude moves only through `gamma_v`) |

P1 does not fire, and one of its clauses could not have fired. P4 does not fire, but the structural
fact it was written to detect — a unit-modulus de-embed, so only the fit basis can move the magnitude
— is confirmed exactly. **P2 fires cleanly, in the direction P2 itself spelled out.**

**What P2 firing does not mean.** P2 was written as the partial-news bracket: "the beta error explains
part of the story; the anchor question is separate and remains open." The residual in §5.3 sharpens
that into something less comfortable: the lower beta does not fit the station data as well (8.2×
worse), so the anchor gain it buys is plausibly an artefact of asking the fit basis to work with a
phase constant the data does not support — not a correction of the magnitude. The bracket fired; the
result is not a win. Per §3's closing rule, no threshold was moved to make a harder bracket fit.

## 7. Comparison tables

Both tables are per beta, and the pairing rule of §4 is applied without exception: the complex-load
anchor (0.307) pairs **both** ports, the series-R anchor (0.34465) is **s11-only** and appears in no
cross-port comparison. No row below crosses them.

### 7.1 Anchor offsets

| beta | \|Γ_port\| | vs series-R 0.34465 (s11-only) | vs complex-load 0.307 (both ports) |
|---|---|---|---|
| baseline 231.5533 | 0.3258868 | −5.44 % | +6.15 % |
| rawphase 223.5813 | 0.3420459 | **−0.76 %** | +11.42 % |
| hammerstad 223.3531 | 0.3425167 | **−0.62 %** | +11.57 % |

That is the whole of the P2 finding in one table: the series-R offset collapses from −5.44 % to
−0.76 % while the complex-load offset grows from +6.15 % to +11.42 %. One anchor improves by a factor
of seven, the other degrades. A single scalar moving `|Γ|` along one line cannot satisfy both anchors
at once — the two are in tension under this basis, and P2 is precisely the bracket that names that
tension.

Note also how close the baseline sits to the *midpoint* of the two anchors (0.325825): 0.3258868 is
6.2e−5 above it. The baseline is very nearly equidistant from both, which is why a 5 % move in `|Γ|`
resolves the question so decisively — and why that resolution is worth so little as evidence: a
near-tie was broken by a basis shift the data does not endorse.

### 7.2 Phase residuals

| beta | arg Γ_port (deg) | s11 residual vs −107.68 |
|---|---|---|
| baseline 231.5533 | −100.4992 | **+7.18 deg** |
| rawphase 223.5813 | −91.4391 | +16.24 deg |
| hammerstad 223.3531 | −91.1785 | +16.50 deg |

s21 phase, baseline only (§5.4): 5.1880 vs +9.11 → −3.922 deg. It is reported once and not compared
across betas, because the magnitude a two-port complex-load comparison would need is beta-invariant
here, so the pairing cannot be completed.

## 8. Limitations

1. **The betas are transplanted between runs.** The station phasors come from
   `build_A_50ohm_p51_phasors.json`; `beta_rawphase` comes from `graded_v2_refix.json`, a different
   run. The test assumes both describe the same structure. If they do not, part of the 8.2× residual
   is a run-to-run comparison, and this document cannot separate that from a genuine basis error.
2. **The Step-0 concern is measured, not resolved.** §2 bounds the raw-phase estimator's error at
   38.06 deg on a 128.10 deg measurement (~1.6 % of beta) but cannot say which way it points. The
   residual is consistent with that error being real and adverse; it is equally consistent with the
   frozen beta simply fitting these stations better. This test cannot distinguish those two.
3. **8 of 9 stations, no uncertainty.** With seven usable rows a residual ratio is a blunt instrument:
   8.2× is large, but no uncertainty is attached to it, no bootstrap was run, and no significance is
   claimed.
4. **P2 fired, so by construction the anchor question is still open.** The fired bracket's own text
   says so. Nothing here identifies which anchor is right; it identifies that one beta cannot satisfy
   both, which the 0.307-vs-0.34465 spread already implied.
5. **The magnitude path is entirely through the fit.** §5.1 shows the de-embed is unit-modulus, so
   every magnitude number in §5.2/§7.1 is a statement about `gamma_v` under a beta-dependent basis, not
   a statement about de-embedding. P4 did not fire numerically, but its mechanism is the one in play.
6. **s21 is not refittable from this artefact** (no `a_port`/`a_cut`; `/run/reference` null under
   `loaded_without_reference`, DR-27). Its magnitude 0.7644184907560716 is reported as recorded, not
   as validated, and P1's s21 clause was untestable.
7. **eps_eff adds no independent information.** It is a re-expression of beta, so the closeness of
   3.350776 to the Laplace static value 3.35001 (0.023 %) is a single coincidence of the kind §2 put
   on the record before the data. It is not counted as support for `beta_rawphase`; nor is the
   baseline's 3.593986 — the least plausible of the three against eps_r = 4.4 — counted against it.

   *Clarification added 2026-11-05 by the `anchor-audit-2026-11-05` pass; the numbered text above is
   left untouched so the record of what was believed, and when, survives.* The paragraph is correct
   as written but its scope is narrower than a reader coming from §9.2 will take it to be: **the
   0.023 % belongs to `beta_rawphase` alone.** 3.350776 is (223.58131180256908 / 122.14137132890411)²
   and 3.35001 is the Laplace static value, so the coincidence is a property of the *transplanted
   extraction* beta, not of the beta this document's own residual minimises. At the fit's own minimum,
   β = **231.046199503169** (§9.2), the same formula gives (231.046199503169 / 122.14137132890411)² =
   **3.578261**, i.e. **+6.81 %** above 3.35001 — no match at all, and on the same high side as the
   baseline's 3.593986 (+7.28 %) that item 7 calls "the least plausible of the three". Read as a whole,
   the station fit is therefore **internally self-consistent on `resid_v` while disagreeing with the
   static physics on eps_eff**, which is the tension §9.2 documents and not a validation of anything.
   Nothing in §7 or §9 moves: 3.350776 remains an exact re-expression of `beta_rawphase` with no
   independent content, and the strategic conclusion (a beta scan cannot reconcile the anchors) is
   untouched.


## 9. Late addendum — a beta scan, appended after §8 and not part of the frozen test

§9–§13 were written after §8 and are **not** part of the pre-registered test; P1–P4 and §3 stand as
written. They answer four questions the earlier passes raised and could not settle.

### 9.1 The harness check

Before scanning, the baseline was reproduced from the artefact's own phasors through the library station
fit: β = 231.55331672912826 → |Γ_port| **0.32588679434738205**, arg **−100.49921155606 deg**,
`resid_v` **0.0011009800639328231**, bit-exact against §5.2/§5.3. A scan is only worth reading if the
point it starts from reproduces, so the scan below shares that harness.

### 9.2 Scan 220 → 245 rad/m, step 0.001, four targets

Each row is the beta at which one target is met to within a hair, not a beta that meets all of them.

| target | beta (rad/m) | \|Γ_port\| | arg Γ_port | `resid_v` | s11 resid | s21 resid |
|---|---|---|---|---|---|---|
| minimum `resid_v` | **231.046199503169** | 0.326897944800 | −99.925395 | **0.00090543314492309054** | +7.7546 deg | −4.4218 deg |
| \|Γ_port\| = 0.34465 | **222.321546277827** | 0.344650 | −89.999847 | 0.01052385359 | **+17.6802 deg** | −13.0198 deg |
| arg Γ_port = −107.68 deg | **237.926169033850** | 0.3133803613651421 | −107.680 | 0.0087059853 | ~0 | **+2.3583 deg** |
| s21 phase = +9.11 deg | **235.533114** | — | — | — | — | **0.0000 deg** |

The smallest and largest of these span **15.604623 rad/m = 6.74 %** of the baseline. Three facts follow.

**The residual basin cannot separate the betas.** The minimum is 0.507 rad/m (0.219 %) below baseline and
is only **1.216×** deeper, with the neighbouring 0.001 steps flat to 1e−12
(231.045→0.0009054343538, 231.046→0.0009054331784, 231.047→0.0009054336829); `resid_v` rises to
0.01321 at 220 and 0.01795 at 245, so the minimum is interior and the basin is broad. §5.3's 8.2× ratio
is therefore a statement about β = 223.58, not about 231.55: the data pin beta to roughly
±0.5 rad/m, and the residual gives no reason to move it.

**The phases and the magnitude want different betas, and the two tolerance windows do not overlap.**
|Γ_port| ∈ [0.32, 0.34] (P1's own band) ⇔ β ∈ **[224.575706, 234.529283]**; s11 residual < 2 deg ⇔
β ∈ **[236.146125, 239.710245]**. The gap is **1.617 rad/m**, and the s21-zero at 235.533 lies inside
neither. Local slopes at β ≈ 231: darg/dβ = **−1.131 deg per rad/m**, d|Γ_port|/dβ = **−0.001992 per
rad/m**. Making the s11 phase agree costs ≈ 0.005–0.006 in |Γ|; buying |Γ| = 0.34465 costs 17.7 deg of
s11 phase and 13.0 deg of s21 phase at once. This is the sharpest form of P2's finding: no beta satisfies
the phases and either anchor together, so the conflict is between the anchors themselves and cannot be
beta-absorbed.

**0.34465 sits outside P1's own band, by construction.** P1 required |Γ_port| ∈ [0.32, 0.34]; the
series-R anchor is 0.34465. A beta that lands on the anchor can therefore never fire P1, and the bracket
and the anchor were mutually exclusive before any number was computed. That is a specification conflict,
not a data outcome, and it is invisible in §6's table because §6 reports the |Γ| at `beta_rawphase`,
which happens to be 0.342046 — inside the band and 0.76 % short of the anchor, i.e. the one place where
the two nearly agree is the place §5.3 rejects on residual grounds.

## 10. Where 0.34465 comes from

It is a **derived constant, not a measurement**: |Γ| = R / (2Z0 + R) with R = 50 Ω and
**Z0 = 47.53662 Ω stated, not fitted**. Custody chain: `docs/design/closed_form_with_two_wave_beta_2026-11-02.md`:14
(definition), `docs/design/defect_register.md`:342, the run artefact's own
`validation_reason` (`evidence/termination/build_A_50ohm_p51_phasors.json`:385), and the verification
ledger `reports/2026-11-04_17-13-49_gen8-handoff-repair___verification_ledger.md`:29-33. There are
**zero hits across the 154 `*.py` files**: no code path computes it, so it is hand-propagated and inherits
whatever transcription care it was given.

The ledger also records that it is **configuration-specific** — the same estimator gives 5.5 % / 7.6 % /
13.8 % residuals on the n = 64 20 mm, n = 54 100 Ω and n = 79 30 mm runs. Two consequences for §7.1:
the **−0.76 %** agreement at `beta_rawphase` is a one-configuration coincidence, not a validation; and
since Z0 is asserted rather than fitted, 0.34465 carries an unquantified error bar — so a bracket
([0.32, 0.34]) that excludes it by construction is being compared against a number whose own tolerance
is nowhere on disk.

## 11. s21 — which path produced 5.18796, and the sign of ∂φ/∂β

The recorded phase reproduces to **4.5e−14 deg** as `wrap(raw_phase_deg + deg(β · 0.0172))`:
136.99508249088075 + deg(231.55331672912826 × 0.0172) = **5.187960321243622**. So the no-reference
branch of `line_s21` (`studies.py`:3686, `a1, planes[0], a2, planes[1]`) produced it, with
**d = the real 17.2 mm plane span** — not the 0.0072 recorded as `deembed_distance_m` (with 0.0072 the
value would have been −127.482 deg). This is consistent with `/run/reference` null and
`loaded_without_reference` true, and it means the artefact's `s21.phase_deg_basis` — which claims the
twin-reference `forward_ratio` path — **is wrong for this artefact**; it is the contested string already
tracked as DR-27.

Hence ∂φ_s21/∂β = +d = **+0.98549 deg per rad/m**:

| beta | s21 phase (deg) | residual vs +9.11 |
|---|---|---|
| 231.55331672912826 baseline | +5.187960 | **−3.922040** |
| 231.046199503169 min-`resid_v` | +4.688203 | −4.421797 |
| 223.58131180256908 rawphase | −2.668350 | **−11.778350** |
| 223.35306683909533 hammerstad | −2.893283 | −12.003283 |
| 235.533114 (s21 zero) | +9.110000 | 0.000000 |

Lowering beta moves the s21 phase **down**, away from +9.11: `beta_rawphase` triples the residual, exactly
as it does for s11 (7.18 → 16.24 deg). The two ports move together, so the phase evidence is one
measurement of beta, not two.

**Correction to §7.2's closing paragraph.** That paragraph declined to compare s21 phase across betas
because a two-port comparison would need a magnitude and the magnitude is beta-invariant. The premise is
right and the conclusion does not follow: +9.11 deg is a *phase* prediction and needs no magnitude
partner, so the comparison is completable, and it is completed above. What remains true from §5.4 is that
**P1's third clause (s21 magnitude unchanged) was untestable** — magnitude is beta-invariant by
construction — but "s21 tells us nothing about beta" was too strong, and §7.2 should be read with this
section appended.

## 12. DR-34 re-scope (one line, file wins)

The two AC-7 betas (216.7622 vs 223.5813) are 3.15 % apart and the title says 3.1 % — the title is right.
The **+182.51 rad/m** in circulation is `graded.json`'s `deembedded_slope_rad_per_m`, which
`evidence/termination/README.md`:3 explicitly labels "a different quantity", taken across two runs over
the 10.0 mm between them — it is neither a beta nor part of the comparison. DR-34's register entry
(line 568) already carries that correction; nothing else in the entry needs to change. **Scope: a real
3.15 % beta disagreement between two identically-labelled AC-7 records, with no supersession marker.
The slope figure is not part of it.**

## 13. ε_eff — 3.343938 is correct; 3.34404 is a transcription of the printed value

`emfit.microstrip.eps_eff(2.0, 4.4)` = **3.3439383100189377**, and (β_model/k0)² with
k0 = 2πf/C0 = 122.14137132890411 is the same number to 4e−13. So β_model = k0·√(static ε_eff) with **no
dispersion**, and `summary_line`'s `eps_eff_model=3.34394` is that number at 5 dp. Thickness makes no
difference (identical for t/h = 0, 3.5e−5, 1.8e−5).

3.34404 differs by **+1.02e−4 absolute (+3.04e−5 relative)**, which would require β = 223.3564629239448
(**+0.003396 rad/m, +0.0015 %**) or w/h = 2.0007. **No leaf on disk carries 3.34404**; it is consistent
with a hand-transcription of `3.34394 → 3.34404`. It moves beta by five orders of magnitude less than the
8.2× residual signal and changes no conclusion. **Use 3.343938.**

