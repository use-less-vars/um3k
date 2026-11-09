# Defect register (DR-14 onward)

**This register records defects DR-14 onward.** The numbering follows the owner's defect
register, which is kept **outside this tree**. DR-1 to DR-13 therefore do not appear here, and
their absence is **not a gap in this file** — it is where the series starts in this copy. Nothing
here renumbers, summarises or supersedes a DR number held outside it.

**Field set, per entry:** id · title · status · severity · opened (date) · what is wrong ·
evidence (with numbers) · candidate causes · what closes it · gates.

**Conventions.** Entries are append-only: a wrong statement is corrected beside it, never deleted.
Status is `OPEN`, `CLOSED` or `RESERVED` (a number held for a check not yet run — reserved numbers
carry no entry body). A defect is only `CLOSED` when the "what closes it" line has actually been
done and is cited on that line.

---

## DR-14 — microstrip closed forms disagree by 1.77 % at w = 3.2 mm, h = 1.6 mm, and the FDTD result sits between them

- **id:** DR-14
- **title:** Two closed forms for the same microstrip cross-section disagree by 1.77 % in β — 17.7× the AC-7 bar — and neither is displaced by the FDTD result far enough to settle which is right.
- **status:** OPEN
- **severity:** MEDIUM. It does not move any current verdict (see *gates* below), but it invalidates any sentence of the form "the FDTD β agrees with the closed form" unless the closed form is named, and it sets a floor of ~1.77 % under any comparison that mixes the two references.
- **opened:** 2026-11-01

**What is wrong.** `emfit.mode_profile.microstrip_mode_profile` (the reference AC-7 is graded
against, `docs/design/absorbing_termination_scope.md:266-268`) and the Hammerstad-Jensen closed
form carried in the run artefact as `line.beta_model` describe the same cross-section — w = 3.2 mm,
h = 1.6 mm, ε_r = 4.4, w/h = 2.0, one tone — and differ by **1.7717 %** in β and by **3.5748 %** in
ε_eff, both quoted with **Hammerstad in the denominator** — the convention this entry uses for every
gap it states. With **mode_profile** in the denominator (the convention AC-7 itself uses, since its
`rel_error` is |β_FDTD − β_modal| / β_modal) the same two gaps are **1.7409 %** and **3.4514 %**, so
both denominators are named wherever a percentage appears. Each is used as "the model" somewhere in
the termination work, and no document states which one is correct at this geometry.

**Evidence** (all from `evidence/termination/graded_v2.json`, `criteria.AC-7.achieved`; the same
values appear in `graded_v2_refix.json`):

| quantity | mode_profile | Hammerstad (`line.beta_model`) | gap |
|---|---|---|---|
| β [rad/m] | **227.31018858464796** | **223.35306683909533** | 3.9571217455526266 rad/m — **1.7717 %** of Hammerstad, **1.7409 %** of mode_profile |
| ε_eff | **3.4634763080674587** | **3.3439383100189377** (derived: (β/k0)², k0 = 2πf/c0 = 122.14137132890411) | 0.11953799804852094 — **3.5748 %** of Hammerstad, **3.4514 %** of mode_profile |
| Z0 [Ω] | **47.119454769635006** | 48.0987 (artefact `z0_model`, `strip_width_reconcile_2026-11-01.md`) | ≈ 2.0 % |

- Tone and geometry are the **same on both sides**: `beta_modal` carries `f_hz` 5827786408.327286
  (5.8277864083 GHz), `h_m` 0.0016, `w_m` 0.0032, `ms_eps_r` 4.4, `c0_m_per_s` 299792458.0; the
  Hammerstad side is the run's own `line.beta_model` and equals the grader's
  `beta_hammerstad_rad_per_m` **223.35306683909533** to all digits, so it is the same width, the
  same substrate height and the same tone. What differs between the two numbers is **ε_eff**, not f
  and not h.
- The gap is **17.7× the AC-7 bar** of `1.0e-3`: 1.7717 % / 0.1 % = **17.7169×** with Hammerstad
  in the denominator and 1.7409 % / 0.1 % = **17.4085×** with mode_profile in it. The **multiplier is
  not sensitive** to that choice — both ≈ 17.4–17.7× a 0.1 % bar — while the **percentage** is, which
  is exactly why every percentage in this entry names its denominator.
- The measurement does **not** separate them. β_FDTD = **223.58131180256908 rad/m** sits
  **+0.1022 %** from Hammerstad (`rel_error_vs_hammerstad` = 0.0010219020795365688) and
  **−1.6404 %** from mode_profile (`rel_error` = 0.016404353915224042). It is 18× closer to
  Hammerstad than to mode_profile, but 0.1022 % is only ~1.0× the bar, so proximity is suggestive,
  not a resolution: the FDTD run cannot by itself declare the reference wrong.

**Explicitly *not* the earlier Flag 1 scare.** This is not a repeat of the ~2.9 % "reference spread"
recorded in the `strip-width-reconcile-2026-11-01` dispatch row. That one was a **frequency
artefact** — Hammerstad-Jensen evaluated at 6.0 GHz against mode_profile at the realised tone
5.8277864083 GHz — and it vanishes when the tone is fixed. The 1.7717 % / 1.7409 % gap above is
at **one tone** (5.8277864083 GHz) and **one h** (1.6 mm) on both sides, and it survives that fix; it lives in
ε_eff (3.463476 vs 3.343938), where a tone error cannot reach. Before this figure is quoted as a
spread anywhere, the same f and the same h must be re-confirmed on both sides — if a future
artefact cannot be shown to hold them equal, the disagreement must be recorded as **unconfirmed**
rather than carried as 1.7717 % / 1.7409 %.

**Candidate causes** (listed, **none picked** — there is no evidence yet that selects one):

1. **mode_profile's 2D Laplace edge treatment at this h.** `microstrip_mode_profile` solves the
   transverse cross-section numerically; at h = 1.6 mm with w/h = 2.0 the strip-edge field
   singularity is resolved by a finite grid, and a grid-dependent ε_eff at the sub-percent level is
   the expected signature.
2. **Hammerstad-Jensen's own error band at w/h = 2.0.** The fit is a curve fit to a numerical
   family; its stated accuracy is at the ~1 % level over parts of its range, and w/h = 2.0 is not a
   corner it is tuned to. A 1.77 % ε_eff gap is inside the fit's plausible band, not outside it.
3. **Different physics under the same label.** The two may not be computing the same quantity:
   finite strip thickness (mode_profile's thickness handling vs the zero-thickness fit), the
   edge-singularity exponent, or a difference in how ε_eff is defined (quasi-static filling factor
   vs (β/k0)² of the dispersive mode). Any of these would make the 1.77 % a category difference
   rather than an error in either number.

**What closes it.** Identifying which reference is correct **at this geometry** — w = 3.2 mm,
h = 1.6 mm, ε_r = 4.4, 5.8277864083 GHz — and recording the reason (a converged third method, a
grid-refinement study of mode_profile at fixed geometry, or a published value at this w/h). A
candidate route is a theory-engineer round 3. Re-running the same comparison cannot close it: the
disagreement is between two closed forms, and the FDTD point at 0.1022 % from one of them is not
enough separation to arbitrate.

**Gates:** **nothing currently.** AC-7 is graded against **mode_profile**, as
`docs/design/absorbing_termination_scope.md:266-268` names it — so DR-14 does not move AC-7's
verdict in either direction (AC-7 fails on the mode_profile bar at 1.6404 %, and that stands). It
does gate **wording**, not verdicts: no result may be described as agreeing "with the closed form"
without naming which one, and no future criterion may be scored against Hammerstad while claiming
the mode_profile reference, or vice versa.

---

## DR-16 — the twin's reference refused every run measured on other planes, so `--with-twin` could not normalise a graded run

- **id:** DR-16
- **title:** `LineReference.forward_ratio` raised unless the run's `s21` planes were *identical* to the reference's own first and last station, so the load-free twin — the only measured alternative to an assumed `zc` — could not normalise any graded run: run A/B extract on (3.2 mm, 20 mm) against stations (10.4 mm, 20.0 mm).
- **status:** OPEN. It moves to **FIXED-TESTED** only on a host run of A / E / B with `--with-twin` in which the magnitude criterion **and** the transport criterion of (iii) both pass — the owner set that transition, and nothing in this tree can discharge it.
- **severity:** HIGH. It produced no wrong number (it raised rather than dividing by a ratio measured on the wrong length), and that is the whole of the good news: every graded `s21` still comes from the `reference=None` path, where `zc_split = zc` and `loaded_without_reference = True`, so the AC-3/AC-4 magnitudes are graded against an **assumed** `zc` — the record's own station-fit `z0` (`emfit/studies.py:3252`), a two-wave fit over stations that straddle the cut and so carry the load as well as the line — and **no artefact records it**: `build_A_50ohm_v2.json` / `build_B_100ohm_v2.json` / `build_E_50ohm_v2.json` carry only `line.z0_re` / `line.z0_im`, the *port-plane* `V / I` (`emfit/studies.py:3201`), which is a different quantity (42.75850315700394 - 16.046149777568516j on A, 31.61552461014143 - 23.302927114467472j on B, 90.45351416808899 + 31.127472443073763j on E) and mask even that to `n/a` in `summary_line` (`emfit/studies.py:1647-1649`). The `50.54736386461998 + 4.024590867955236j` quoted in this entry's first draft is none of those: it is the *default* 44-line run's station-fit `z0` (`evidence/board_poc/A_microstrip.json`, `metrics["line Z0 from stations, real part"]` = 50.5474 ohm, modulus 50.7073 ohm, phase 4.5523 deg), a measurement on another mesh, not the number the graded arms assumed. The defence against assuming it away was, as shipped, unreachable. It also fires only after the expensive half of a two-solve run has been paid for.
- **opened:** 2026-11-02

**What is wrong.** On 2026-11-01 the `--with-twin` smoke spent **34.56551695801318 s** on the load-free
twin and wrote `evidence/termination/build_smoke_50ohm_twin.json` (`meta.status` `"ok"`, `line.station_span_m`
**0.0096**, `s21.planes_m` **[0.010400000000000001, 0.02]**), and the *loaded* solve then raised at the
normalisation step:

```text
ValueError: reference stations span (0.0104, 0.02) m but the run's planes are (0.0032, 0.02) m:
s21 is normalised by a ratio measured on the same two planes of the same mesh, or not at all
```

Exit 1 after **80.7 s**. The twin half of the run is banked and the loaded half does not exist, so the one
artefact the option has ever produced grades nothing, and the failure arrives after the twin's wall cost
has been spent — the guard is at the end of the run, not at argument parsing.

**The guard's premise is true and its conclusion is false.** A `LineReference` does not supply a piece of
the line; it supplies the *residual* left after its own de-embedding. Computing `a+` has already divided
out `exp(gamma x)`, so the measured ratio is 1 for a line whose stations agree with the fit and departs
from 1 only where the line departs from it — a couple of degrees of phase over the station span, not a
quarter turn. **How big that residual is, this smoke does not measure.** The loaded solve raised before any
ratio was formed, so the twin's own residual has **not** been measured by anything, and
`build_smoke_50ohm_twin.json` records the fit (`line.gamma_re` / `line.gamma_im`, `line.z0_re` /
`line.z0_im`), not the ratio. The size this entry quotes is the fixture's — **[M, a synthetic fixture in
`tests/test_studies.py` — a wave built from `GAMMA*1.0177`, not a run]**: **2.2630 deg** of phase and
**4.2e-4** of log-magnitude over the 9.6 mm station span are what a reference whose `gamma` is **1.77 %**
off carries there (`GAMMA_OFF = GAMMA * 1.0177` feeding `RESIDUAL_REF`, `tests/test_studies.py:1256-1262`).
Small, real, and the honest size of the error such a reference leaves behind, which is the whole reason the
twin is worth running. A departure from the fit grows like `exp(dgamma * L)` over the span `L` it was
measured on, so the residual **is** per-metre and **can** be carried to another span. What cannot be
done is to apply the same complex number to a different length. The guard's text says exactly that, and
it is right — and refusing is still the wrong answer, because the repair is to *exponentiate*,
`ratio ** (run_span / station_span)`, not to declare the normalisation impossible.

**The planes a run uses are set by the port and the load, never by the stations.** Run A's two planes are
the source plane near the port and the load's own cut plane at 20 mm — `(0.0032, 0.02)` m, read off the
raised message above — while the stations are the typed-in first and last probe at 10.4 and 20.0 mm. The
run span is 16.8 mm on A / B and 26.8 mm on E (port to cut) against a station span of 9.6 mm, so **no**
graded arm matches and the guard did not police an exotic case: it made the option unusable on the only
runs it exists for. A guard that cannot pass on any legitimate input is not a safety check, it is a
prohibition — and it was documented as an option.

**The fix.** `forward_ratio` keeps the endpoint case **byte-identical** — `if all(abs(w - g) <= 1e-9 ...):
return ratio`, where the exponent is 1 and the measured ratio comes back untouched — and otherwise returns
`complex(np.exp(np.log(ratio) * (run_span / span)))`. Guarded still: a zero station span, a residual of
exactly `0.0` ("no residual to rescale"), and a `gamma` that is missing or not finite. The power is taken
through the principal branch of the logarithm, so a residual whose phase exceeds pi is rescaled with the
phase wrapped — stated in the docstring rather than discovered later. Eight tests in
`tests/test_studies.py:1265` (`TestForwardRatioTransport`) carry it:
`test_matching_endpoints_is_bit_identical`, `test_a_perfect_reference_rescales_to_one`,
`test_residual_rescales_as_a_power_of_the_span`, `test_the_transport_does_not_rotate_the_residual`,
`test_rescaling_composes`, `test_reversing_the_planes_inverts_the_ratio`, `test_guards`,
`test_the_reference_transports_off_its_own_two_planes`. What the library change has **not** been shown to
do is normalise a **loaded** run, because the run that would have shown it is the one that failed — this
entry stays OPEN on that.

**THE NEAR MISS.** The obvious repair, and the one nearly written, is to carry the residual over the
difference in span as a travelling wave: multiply by `exp(-gamma * dL)` with `dL = 16.8 - 9.6 = 7.2` mm and
`gamma = 2.4697 + 232.44695963784835j`. It reads as physics, it is dimensionally right, and it is wrong in
the quantity nothing checks. `exp(-gamma * 7.2e-3)` = **-0.10083169180007594 - 0.9771869048957996j** —
magnitude **0.9824**, phase **-94.86 deg** — at distance **1.5175** from the value it was meant to
reproduce; all three read off the fixture at run A's geometry. The residual is not a wave: on the same
synthetic fixture (`tests/test_studies.py:1258-1262`) its phase is **2.2630 deg** over the reference's
9.6 mm stations, and **3.9603 deg** at run A's (3.2, 20) mm planes is what the **power law** produces from
that 9.6 mm residual there — exponent **1.75** (16.8 / 9.6), not a separately measured number — with the
log-magnitude scaling by the same 1.75x.
The rejected operator would have shipped a **~95 deg rotation** and a **1.8 % attenuation** into every
normalised `s21`, and no acceptance criterion now in force would have caught it: AC-3
(`docs/design/absorbing_termination_scope.md:235`), AC-4 (`:246`) and AC-5 (`:251`) are **magnitude-only**,
and that document contains **no phase criterion at all**. The operator's magnitude **0.9824** sits inside
AC-5's **1.00001** tripwire and AC-3's `1e-3`, so a magnitude-only criterion does not merely fail to catch
this rotation, it **passes** it. The power law and the multiplicative reading are
distinguishable by composition alone, with no reference value needed: two hops that must equal one — 9.6 mm
then 7.2 mm against 16.8 mm — disagree by **-0.628 + 0.809j** under the multiplicative reading and by
**1.8e-16** under the power law. Exponents add; transport factors do not, once what is being carried is a
residual rather than a mode.

**Explicitly *not* a solver, sign or `s21`-convention defect.** Nothing in the FDTD run, the estimator or
the cut-plane extraction is implicated: the twin fitted, the fit produced a reference, and the reference
declined to be applied. No number in `graded_v2.json` or `graded_v2_refix.json` is wrong, and none moves
here — they are measured on the assumption this option exists to replace, and they say so on their face.

**Relation to DR-15.** DR-15 remains **reserved** and is not this defect: DR-15 holds the seam check on
`line.beta` across runs A / E / B (< 1 % on identical geometry), which this entry neither runs nor
discharges. A twin-backed run would *supply the material* for that check; it does not perform it.

**What closes it.**

(i) **A loaded run that completes with the reference.** The same command that failed —
`python3 evidence/termination/run_build_A.py --n-line 44 --load-at-mm 20 --load-ohm 50 --with-twin --out
evidence/termination/build_smoke_50ohm.json` — with `loaded_without_reference` coming back **False**. No
amount of reading closes this entry; the transport is exact on a uniform line and a loaded line is not
one, which is precisely the case that has to be measured.

(ii) **The transported residual quoted, not inferred.** The twin measures its residual on (10.4, 20.0) mm
and the run normalises on (3.2, 20) mm, so the artefact must carry the measured residual *and* the exponent
**1.75** it was raised to. A residual carried across a span is only as good as the span ratio recorded
beside it; a bare normalised `s21` hides which of the two it was.

(iii) **AC-3b, registered here and deliberately not added to `absorbing_termination_scope.md`** — that
document is append-only and outside this dispatch's fence, and a criterion added after the answers are known
would widen a set its §5 certifies as pre-registered. **AC-3b** is the phase companion the magnitude
criteria lack: a residual measured directly on the run's own two planes (a second twin whose stations *are*
those planes) must be reproduced by the one transported off (10.4, 20.0) mm to within **5 deg** in
`arg s21` and **1 %** in `|s21|`; and no `s21` may be reported without the residual it was normalised by.
The **5 deg** figure is **PROPOSED at registration, RATIFIED 2026-11-02**: the owner pre-registered only
the magnitude criteria, and this phase companion is registered here because a magnitude cannot see a
rotation. At registration it was not to be adopted until the second-twin run is shown able to meet it — a
criterion that cannot pass on legitimate input is a prohibition, not a safety check, and that is the defect
this entry documents; the **Ratified 2026-11-02 by dispatcher** note below is what lifts that hold.
Neither number is measured by anything yet; the second twin is what would measure them. **Ratified 2026-11-02 by dispatcher:** 5 deg phase / 1 % magnitude; AC-3b is a DR-16 criterion, not a scope criterion. The PROPOSED wording above is retained because the record is PROPOSED then RATIFIED, not always-ratified.

(iv) **The graded arms re-checked with a reference in hand.** A / B / E were graded with `reference=None`
and an assumed `zc`; when a twin-backed run exists, the difference in `|s21|` and `|Gamma|` from the
assumed-`zc` values must be reported, and AC-3 / AC-4 re-graded only if it falls outside their existing
bars. Until then the entry gates *wording*: no result may be described as normalised "with the reference",
and `loaded_without_reference = True` must be quoted wherever a graded `s21` is.

(v) **The graded arms re-graded after the transport change.** The AC-7 grader was re-run
over the three committed v2 artefacts with no FDTD run at all — it reads only what those
artefacts already carry:
`python3 evidence/termination/grade_2b.py evidence/termination/build_A_50ohm_v2.json
evidence/termination/build_B_100ohm_v2.json evidence/termination/build_E_50ohm_v2.json
--out .scratch/graded_v2_after_transport.json`, from the repository root. Exit **0**, no
warnings, and the same verdict set as `graded_v2_refix.json` — AC-3 False, AC-4 None,
AC-5 False, AC-5b None, AC-6 True, AC-7 False. A recursive walk of every JSON leaf against
`graded_v2_refix.json` found **136 leaves on each side and 0 differing**: identical at every
JSON leaf — a statement about the numbers, not about the bytes of the two files, whose
`/inputs/{A,B,E}/path` entries echo whichever argv they were given. The caveat is the
important half. `grade_2b.py` contains **zero** occurrences of `forward_ratio` and never
constructs a `LineReference`: it reads `s21.magnitude`, `s21.phase_rad` and
`s21.raw_phase_rad` out of the artefacts and computes the AC-7 reference itself from
geometry. So this check shows that the graded numbers and the criterion maths did not move.
It does **not** exercise the changed function. Bit-identity of the endpoint path therefore
rests on `test_matching_endpoints_is_bit_identical` alone, and nothing in this tree
exercises the loaded path. The re-grade is necessary and not sufficient: DR-16 stays
**OPEN**.

**Gates:** **nothing currently moves.** **Updated 2026-11-02 (commit `7addacf`).** The v3 run A pair now
exists — `build_A_50ohm_v3.json` with `build_A_50ohm_v3_twin.json` — and `run/kwargs/reference` is
populated: `zc_re_ohm` 47.50588686424766, `zc_im_ohm` 1.7863178861130007, `gamma_im_rad_per_m`
232.73432451555712, `station_span_m` 0.0096, `n_stations` 9. Against that pair: (i) **PASSES** — the loaded
run completed with `loaded_without_reference` False; (ii) **PARTIAL** — the residual's per-metre rate and the
span are stored, neither the rescaled residual nor the exponent is, though **1.75** is exactly
(0.02 - 0.0032)/0.0096; (iii) **PARTLY VIOLATED** — the 5 deg / 1 % half needs a second twin and none
exists, but the clause that no `s21` may be reported without the residual it was normalised by is evaluable
and is not met: a normalised `s21` is reported with no residual recorded; (iv) **PARTIAL** — only arm A
carries a reference, B and E were deliberately not run and still stand on an assumed `zc`; (v) does not
apply. None of that is a re-grade, so this entry **changes** no graded number: the re-grade in (v) is what
shows that, its output coming back
identical at every JSON leaf. AC-3b is registered in (iii) above and is graded by **AC-3b (5 deg phase, 1 % magnitude) against a second twin whose stations are the run's own planes**. What
does bind is wording: a graded `s21` must name the assumption it stands on, and an untested transport
must not be presented as a measured normalisation — the near miss is what happens when it is.

### DR-16 update — 2026-11-03: the twin-backed A arm exists; (i)-(iii) pass, (iv) still partial

**Status: OPEN, narrowed.** One thing this entry no longer has to take on faith is that a loaded run *can* complete with a twin-produced reference in play. It now has an artefact behind that sentence. Nothing else in the entry is discharged.

- **(i) A loaded run that completes with the reference — PASS.** `evidence/termination/build_A_50ohm_v3_twin_check.json`: `reference_used: true`, `loaded_without_reference: false`, `wall_seconds_twin 42.696844035061076` + `wall_seconds_loaded 44.25408294098452` = `wall_total_s 87.40410260902718`. Its reference comes from `build_A_50ohm_v3_twin_check_twin.json`, which is a **producer**, not an arm: `run.reference_produced` present, `run.reference` absent, no `line` section (so no `beta`), `plane: null`.
- **(ii) The transported residual quoted, not inferred — PASS.** `run.reference_residual = 1.0516081798504253 + 0.02671534706460333j` with `reference_exponent = 1.7916666666666667`, both read from the artefact rather than reconstructed.
- **(iii) AC-3b registered here and deliberately absent from `absorbing_termination_scope.md` — PASS, as registration only.** Unchanged by this pass; recorded so that silence is not read later as a decision.
- **(iv) The graded arms re-checked with a reference in hand — STILL PARTIAL.** A is discharged on the `|s21|` half — `0.7628473102840976` → `0.7675574763802439`, relative `+6.17e-3` — and **not** on the `|Gamma|` half, which is satisfied only trivially: `|s11|` is `0.32556486641109117` in both the reference-free and the twin-backed artefact and *could not* have moved, because s11 is built from `station_fit` + `deembed_reflection` and never consumes the reference (`emfit/studies.py:3434-3436`); the reference is applied to s-parameters only, at `emfit/studies.py:3519-3522`. B and E still stand on `reference=None`. **AC-3 / AC-4 are not re-graded**, because a re-check that can move only one of the two quantities this item names is not the re-check the item asks for.
- **(v) The graded arms re-graded after the transport change — already done** at `75c7a0e`; not re-opened.

**H5, ruled out in one direction only.** If the absent twin reference were what separated the graded `|s21|` from the anchor, supplying it would have moved the number by the size of the gap. It moves it by `6.17e-3` against a gap of about `1.6e-1` — a factor of roughly `26` short. What is *not* established is the converse: that no other consequence of flying blind (`reference=None` plus an assumed `zc`) sits inside that `6e-3`. The entry's wording gate therefore binds every other graded `s21` in the thread unchanged — the four `fluxcur` arms, B and E, each carrying `loaded_without_reference = True` — and is relaxed **for A's plane-51 value alone**, which may now be described as reference-normalised because it now is.

**Carried, not repaired:** the v3 series' `meta.git_rev: null` and `line.eps_eff: null` provenance gap is untouched by this pass.

---

## DR-15 — RESERVED, not opened

**DR-15 is reserved and carries no entry.** It is held for the seam check on the unloaded-twin
build: `line.beta` across runs A / E / B must agree to **< 1 %** on identical geometry (same mesh,
same cross-section, differing only in the load), and if it does not, the twin fix carries a defect
of its own and that defect is DR-15. The check has not been run; this line only reserves the number
and states what it is for. It must not be cited as an open defect.

---

## DR-18 - AC-6 compared a value with itself, so the check could not fail

**Severity:** record integrity. **Status:** fixed in `dbb76f7`; void on every artefact written before it. **Found:** 2026-11-02 during the shorted-strip reconnaissance; confirmed against source in the s21-shorted-stub-verification pass.

The writer's AC-6 `indices_agree` test read the extraction index back out of the record and compared it against the same integer the wave loop had just stored there. Both sides were `int(ix_extract)`, so the comparison was an identity: it reports `True` for every plane value, including planes placed inside the xmax PML, and no input could make it report `False`. As the writer's own in-code note records at `evidence/termination/run_build_A.py:752-756` [R], the old check compared `res.s21_plane_index` with `res.geometry["s21_plane_index"]`, which are the same quantity.

Any recorded AC-6 pass on a pre-`dbb76f7` artefact is therefore void as evidence, not merely weak. Note also that the four arms used throughout this session's records - `build_A_50ohm_v3c.json`, `build_B_100ohm_v3d.json`, `build_E_50ohm_v3d.json`, `build_A_50ohm_v3b_c51.json` - carry no `criteria` block at all, so AC-6, AC-3 and AC-4 were never scored on them; the vacuous passes live in other runs.

**Fix (`dbb76f7`):** `indices_agree` now compares the extraction index against the request (`run_build_A.py:774-788`), `load_plane_index` is re-semanticised to the load's own column, and `pass` additionally requires the plane to lie outside the xmax PML via `last_clean_plane = nx - n_pml - 1`.

**Lesson:** a check whose two sides are produced by the same expression is not a check. A criterion must be able to fail, and should be demonstrated failing once before it is trusted.

**Related:** dispatch row `s21-default-plane-writer-2026-11-02`. AC-3 is a separate and much larger defect: it is testable today and false on every arm (`s11_at_plane.magnitude` 0.0490 / 0.4266 / 0.3132 against a 1e-3 bar), and it is not merely failing but unmeetable while the strip runs PEC into the far wall. AC-4 is unscorable for want of a second unmatched arm, not for want of a load kind.

## DR-19 — the graded `s11` and the load-plane `s11_at_plane` describe incompatible reflections in the same artefact

**id:** DR-19
**title:** `s11.magnitude` = 0.326 (gamma_port, station-fit two-wave B/A) and `s11_at_plane.magnitude` ≈ 0.049 (gamma_plane, b_cut/a_cut at load column) cannot both describe the same 50 Ω series load. The artefact carries both; `s11.validation_status` is `UNVALIDATED`; which is the real reflection is unrecorded.
**status:** OPEN
**severity:** HIGH (record integrity; gates AC-3)
**opened:** 2026-11-03

**What is wrong.** In `evidence/termination/build_A_50ohm_v3_twin_check.json`:
- `s11.magnitude = 0.325565` — gamma_port, from `station_fit` over the two-wave fit
- `s11_at_plane.magnitude ≈ 0.049` — gamma_plane, from `b_cut/a_cut` at the load column
- `magnitude_one_wave_station_fit = 0.23217` — the pre-`5dda96d` one-wave value, preserved

For a 50 Ω series load in a 47.54 Ω line, the **circular** anchor applies, Z0 47.54 Ω -> |Γ| = 0.3446. **`s11` is within 5.5% of the anchor; `s11_at_plane` is 86% below it.** Neither extraction produces the third number (`s11_at_plane = 0.049` is 7× lower than anchor, `s11 = 0.326` is 5% lower). If `s11_at_plane` is right, `s11` is 6.6× too large. If `s11` is right, `s11_at_plane` is 7× too small. **At most one is correct, and the artefact doesn't say which.**

Note on the loss budget: for a lossy line the de-embedding relation is `Γ_port = Γ_load · e^(+2γd)` with `γ = α + jβ`, i.e. de-embedding REMOVES loss, so the port-plane magnitude must be LARGER than the load-plane magnitude. With `α = 1.5 Np/m` and `d = 0.0168 m`, `e^(+2·1.5·0.0168) = 1.052`. So the load-plane 0.049 should become port-plane 0.051, and the port-plane 0.326 should become load-plane 0.310. Loss therefore cannot bridge a 6.6× gap: the discrepancy is not the de-embedding attenuation.

**Evidence.** `build_A_50ohm_v3_twin_check.json` and `build_A_50ohm_v3_beta2wave.json` (same record structure, `s11 = 0.3256`, `s11_at_plane = 0.0490` in the twin artefact). The z_eff analysis (`docs/design/z_eff_analysis_2026-11-03.md`) verified the σ stamp is 50.000 Ω and that the load-plane inversion to |Z| ≈ 49.94 is consistent with the stamp; the 0.326 measurement is inconsistent with the stamp's own local reading.

**Candidate causes (none picked):**
1. **Station fit straddles the load.** `MS_X_FIRST/MS_X_LAST = 10.4/20.0 mm` and `load_at = 20.0 mm` — the last fitted station is on the load column. The `_station_fit_selection` mask (`s11-fit-and-s21-plateau-2026-11-02`) excludes the load station from the fit, but the *load's near field* still contaminates the remaining stations. The port-plane de-embedding from those stations carries that contamination.
2. **`b_cut/a_cut` at the load plane is degenerate.** At the load column, the split `(V ± Z_0·I)/2` may be ill-conditioned because `V` and `Z_0·I` are approximately equal (Γ ≈ 0.05 means one is nearly cancelled by the other). `s11_at_plane = 0.049` would be dominated by numerical noise, not signal.
3. **The port-plane de-embedding exponent is wrong for the load distance.** `deembed_distance_m = 0.0072` m (port 3.2 mm to station 10.4 mm), applied with `station_fit.beta`. If `beta_two_wave` (231.55) is closer to correct than `station_fit.beta` (286.36), the de-embedding phase is off by `(286.36−231.55)·0.0072 = 0.395` rad — which would rotate the port reflection significantly.

**What closes it.** A settling artefact that carries, in one record:
- `v_cut, i_cut` (raw, at column 50)
- `a_cut, b_cut` (from `b_cut/a_cut`)
- `a_port, b_port` (from the station fit's `V', I'`)
- `gamma_plane`, `gamma_port` (both as recorded)
- `deembed_distance_m`, `deembed_gamma_used`, `beta_used`
- The load's inverted impedance from each path

With all intermediate quantities, one of the two extractions is falsifiable by direct arithmetic. **Do not pick a winner until the settling artefact lands.**

**Gates:** AC-3 is not gradable while DR-19 is open — the reflection that AC-3 compares against `|R − Z_c|/(R + Z_c)` must be the load's physical reflection, and we don't know which number that is. **DR-16 is not gated** (twin normalisation is orthogonal). **No AC bar re-priced.**

### DR-19 update — 2026-11-03: cause 2 fires; the load-plane split is quarantined and the two-wave value is carried forward

Cause 2 fires. `s11_at_plane` is QUARANTINED at plane 51 and any plane within ~3 cells of the load: the split at the load column is ill-conditioned (|b|/|a| ~ 3.4%, so the difference of two large numbers dominates), and a 7% zc change produces a 134 deg phase swing. The measured 0.034 (reference-free) / 0.049 (twin) is a real measurement of a real ill-conditioned quantity - NOT the load's reflection. QUARANTINED IS NOT RETRACTED: the number stands as recorded; it simply cannot be used to describe the load at the cut plane. Any future use requires extraction at a downstream plane plus de-embedding, not extraction at the cut.

The two-wave `s11.magnitude = 0.325565` is the reflection carried forward: plane-invariant by construction, stable across arms, within 5.5% of the **circular** anchor 0.3446515 = 50/(50 + 2*47.53662) (Z0 47.53662 Ω) and within 4.9% of the **independent** anchor 0.3423544 = 50/(50 + 2*48.0237405) (Z0 48.0237405 Ω, w = 3.2 mm; ledger E10, DR-37). **The -5.5% and the -4.9% are ONE numerator measured against TWO denominators, not two disagreeing measurements.** More than one Z0 candidate exists at all because the artefact carries four z0 values with no arbitration between them (DR-29) and because the ladder's Z1 rung was run at the wrong strip width (DR-37). Case C on the attenuation question: `fit_beta(n_wave=2)` carries no alpha term, so no attenuation was ever applied and there is no e^(+2*alpha*d) to restore. The 5.5% residual is fit bias, already quantified as configuration-dependent in the artefact's own `s11.validation_reason`; these are **circular-anchor** numbers, i.e. against 0.3446515: 5.5% (n=64, 20 mm load), 7.6% (n=54, 100 ohm), 13.8% (n=79, 30 mm load), attributed to the load's near field reaching the last station.

DR-19 REMAINS OPEN: the residual is a separate, now-quantified problem. Against the independent anchor (Z0 48.0237405 Ω, ledger E10) it reads 4.8-4.9% and is stable across runs, falling to -3.10% with a dispersive beta; it is under active diagnosis, not closed (ledger E1, ledger E11). **AC-3 remains UNGRADABLE** — nothing in this section is a pass.

Correction to record (framing errors caught within one dispatch): (i) an earlier "13x inconsistency" reading compared three different estimators by design - that was not a bug; (ii) the expectation that a station-internals block would reveal whether alpha explains the 5.5% was void because no alpha term exists in `fit_beta(n_wave=2)`.

## DR-20 — `line.gamma_re` / `line.gamma_im` are a reflection coefficient stored under a propagation-constant name

**id:** DR-20
**title:** `line.gamma_re` / `line.gamma_im` are a REFLECTION coefficient (B/A of the two-wave fit) stored inside the `line` block. The naming invites the exact misreading that `line.gamma` is a propagation constant.
**status:** OPEN
**severity:** LOW
**opened:** 2026-11-03

**What is wrong.** The field sits on the `line` block beside `alpha_np_per_m` and `beta`, where every other `gamma`-named quantity is a propagation constant, but it holds the two-wave fit's reflection B/A. Contract site: `emfit/studies.py:1447-1449`.

**What closes it.** Rename to `reflection_two_wave_re` / `reflection_two_wave_im`, or add an explicit basis string.

**Gates:** none — the numbers are unaffected; only the name is wrong.

## DR-21 — `|line.gamma| == s11.magnitude` is a tautology, not a cross-check

**id:** DR-21
**title:** `|line.gamma| == s11.magnitude` is a TAUTOLOGY, not a cross-check: both are derived from the single attribute `res.gamma`.
**status:** OPEN
**severity:** LOW — but a METHODOLOGICAL HAZARD, flagged loudly. It is the one defect in this register that can make a *review* wrong rather than a run wrong.
**opened:** 2026-11-03

**What is wrong.** Both sides come from the single attribute `res.gamma`: split into re/im at `evidence/termination/run_build_A.py:1554-1555` and modulus'd at `evidence/termination/run_build_A.py:1291`. It can never falsify anything.

**What closes it.** A basis string must name the identity explicitly, and it must NEVER be cited as independent confirmation in any report or review. Anyone citing it is confirming a variable against itself.

**Gates:** any report or review that quotes the two numbers as agreeing with each other.

## DR-22 — `line.alpha` is absent on the loaded branch by omission

**id:** DR-22
**title:** `line.alpha` is ABSENT on the loaded branch by omission: only the twin branch emits `alpha_np_per_m` (`evidence/termination/run_build_A.py:752`).
**status:** OPEN
**severity:** MEDIUM
**opened:** 2026-11-03

**What is wrong.** The loaded branch of the `line` block carries `beta` and no attenuation at all; the twin branch is the only writer of `alpha_np_per_m`. The absence is by omission, not by a null: a consumer cannot tell "no alpha was measured" from "alpha was not asked for".

**What closes it.** Emit `alpha_np_per_m` on the loaded branch (or emit an explicit null with a reason string) so a consumer can distinguish "no alpha was measured" from "alpha was not asked for".

**Gates:** this is the still-open section 10 gap.

## DR-23 — the artefact's `s11.basis` cites a line that no longer holds the cited code

**id:** DR-23
**title:** `s11.basis` cites `emfit/studies.py:3266`, but HEAD has unrelated bookkeeping at that line. Real sites: `emfit/studies.py:3486`, `:1608`, `:1528-1532`.
**status:** OPEN
**severity:** LOW
**opened:** 2026-11-03

**What is wrong.** Citation drift in the artefact. The cited line holds unrelated bookkeeping; the code the basis names lives at `emfit/studies.py:3486` (`gamma_port = deembed_reflection(...)`), `:1608` (the `gamma_port` field) and `:1528-1532` (its docstring). Same class as tonight's other stale-citation corrections.

**What closes it.** Correct `s11.basis` in the writer to the real sites.

**Gates:** none — the number is unaffected; the citation is not.

---

## DR-24 — `s11.magnitude` (two-wave) and `s11.phase_deg` (one-wave) are mis-paired under one key

**id:** DR-24
**title:** `s11.magnitude` (two-wave) and `s11.phase_deg` (one-wave) are MIS-PAIRED under one key: the block reports a modulus from one estimator beside a phase from another, as if they were one complex reflection.
**status:** OPEN
**severity:** HIGH
**opened:** 2026-11-04

**What is wrong.** A reader who pairs `/s11/magnitude` with `/s11/phase_deg` gets a quantity that exists in no model. The modulus comes from the two-wave fit; the phase comes from the one-wave station fit. The pairing site is `evidence/termination/run_build_A.py:1589-1591`, and the block's own `/s11/basis` leaf describes the mismatch rather than preventing it.

**Evidence.** `evidence/termination/run_build_A.py:1589-1591`; leaf `/s11/basis` on `evidence/termination/build_A_50ohm_p51_phasors.json`. Numbers, quoted from `docs/design/s11_phase_investigation_2026-11-04.md` §4: the AC-3 grade `/ac/AC-3/achieved/s11_abs` = **0.23216690987276836** is the ONE-wave magnitude, while `/s11/magnitude` = **0.32556486641109117** — so the gate grades a number the `s11` block does not report.

**What closes it.** [PROPOSED here, not stated by the source] Split the pair: emit the two-wave modulus and the one-wave phase under separate keys (or one key plus a basis string naming both estimators), so no reader can pair them.

**Gates:** AC-3 — the source states this defect gates it.

## DR-25 — the de-embed uses beta_one while the magnitude uses beta_two

**id:** DR-25
**title:** The de-embed is performed at `beta_one` = 286.3593 rad/m while the magnitude it sits beside is computed at `beta_two` = 231.5533 rad/m: one `s11` is assembled from two phase constants.
**status:** OPEN
**severity:** HIGH
**opened:** 2026-11-04

**What is wrong.** Metadata that describes a de-embed cannot be trusted while the beta it used is a different fit from the beta that produced the magnitude. The substitution site is `emfit/studies.py:3387` (beta repointed at the two-wave fit); the leaves that expose the two constants side by side are `/line/beta` and `/line/beta_two_wave`.

**Evidence.** `emfit/studies.py:3387`; leaves `/line/beta`, `/line/beta_two_wave` on `evidence/termination/build_A_50ohm_p51_phasors.json`. Measured consequence, from `docs/design/s11_phase_investigation_2026-11-04.md` §4: the gap between the two betas is the gap the investigation was opened on.

**What closes it.** [PROPOSED here, not stated by the source] One beta per `s11`, named in the basis string; a record must not mix the two fits.

**Gates:** none assigned by the source (§4 gives none).

## DR-26 — `s21.deembed_distance_m` records 0.0072 but the operation used the 0.0172 span

**id:** DR-26
**title:** `s21.deembed_distance_m` records **0.0072** m but the s21 de-embed operated over the **0.0172** m plane span (x_cut 0.0204 − x_port 0.0032). The field is either the wrong distance or the wrong operation's name.
**status:** OPEN
**severity:** MEDIUM
**opened:** 2026-11-04

**What is wrong.** A reader cannot tell from the record whether 0.0072 is the distance used or a copy of the s11 distance. From the source's own arithmetic: `x_cut = 51 * 0.0004 = 0.0204` m and `x_port = 8 * 0.0004 = 0.0032` m give **0.0172** m (derived), against a recorded 0.0072.

**Evidence.** Leaves `/s21/deembed_distance_m`, `/geometry/s21_plane_index` on `evidence/termination/build_A_50ohm_p51_phasors.json`. This defect is **s21-ONLY**: `docs/design/s11_distance_and_magnitude_2026-11-04.md` §3 corroborates 0.0172 as the transmission geometry and shows the 7.2 mm s11 figure is a different distance, not a conflict — there is **no s11 case** for DR-26.

**What closes it.** [PROPOSED here, not stated by the source] Record the distance actually used by each operation, with the field named for the operation.

**Gates:** none assigned by the source (§4 gives none).

## DR-27 — the s21 basis strings describe the twin-reference branch the run did not use

**id:** DR-27
**title:** `s21.phase_deg_basis` and `s21.raw_basis` describe the TWIN-reference branch, but the run was reference-free: the strings are not justifications of the numbers beside them.
**status:** OPEN
**severity:** MEDIUM
**opened:** 2026-11-04

**What is wrong.** `raw_basis` claims a 5.8 % difference against a value the same block records identically, and `phase_deg_basis` describes a twin-reference construction while `/run/reference` is null and `/run/loaded_without_reference` is true. The prose outlived the branch it was written for.

**Evidence.** Leaves `/s21/phase_deg_basis`, `/s21/raw_basis`, `/run/reference`, `/run/loaded_without_reference` on `evidence/termination/build_A_50ohm_p51_phasors.json`. Artefact-leaf evidence only — §4 gives no code `path:line` for the basis writer, and none is invented here.

**What closes it.** [PROPOSED here, not stated by the source] Emit the basis string from the branch that actually ran, so a reference-free run cannot carry twin-branch prose.

**Gates:** none assigned by the source (§4 gives none).

**CLASS NOTE (2026-11-05, from `docs/design/anchor_audit_2026-11-05.md` §5).** DR-27 is not a one-off wording slip in one leaf: it is the first member of a class, **"a recorded basis/provenance string does not describe the operation that was performed"**. Two further instances were found in the same artefact while auditing every phase quantity, so the class now has three members, and they are what §5 of the audit sizes (3 of ~10 leaves swept).

- *Instance 1 (DR-27 itself, restated).* `/s21/phase_deg_basis` describes the twin `forward_ratio` construction (`emfit/studies.py:3352`) while the run was reference-free; `/run/reference` is null and `/run/loaded_without_reference` is true.
- *Instance 2 (new).* `/s21/phase_deg` was produced by the **no-reference** `line_s21` path (`emfit/studies.py:3686`, `emfit/ports.py:1702-1703`) over **0.0172 m**, but the artefact records `deembed_distance_m = 0.0072` and its basis string claims the twin branch. The branch is wrong **and** the distance is wrong, so the same defect class that mislabels the branch also hides a 2.4× plane error. The 0.0172 m is independently confirmed in the artefact by `/ac/AC-7/phase_degeneracy/dL_m`. The line references are also stale after the edit that introduced the reference-free branch (`emfit/ports.py:1707-1731`), so the prose cannot even be followed back to the code it describes.
- *Instance 3 (new, and the class is not confined to strings).* `/s21/raw_reference_independent` is `true` while `/s21/raw_basis` describes a reference-dependent (twin) construction — a boolean and a prose string in the same block are directly contradictory.

**Why this matters for grading.** Each instance is cheap to fix and each is expensive to live with: a reader who trusts the basis string is told which branch, which de-embedding distance and which quantity a number came from, and in all three cases the answer given is not the answer that holds. Nothing here is a calculation error — every number checked out against its actual producing branch; what fails is the provenance layer, which is precisely the layer this project relies on instead of re-running host jobs (DR-28 makes the tree state unrecoverable, so provenance is the only handle left). **What closes the class:** emit the basis string from the branch that actually ran (the DR-27 proposal, unchanged, now applied to three sites), and derive the recorded de-embedding distance from the plane the value was taken at rather than carrying a constant.

## DR-28 — `meta.git_rev` is null, so no artefact is tieable to a commit

**id:** DR-28
**title:** `meta.git_rev` is **null** on the termination artefacts, so no v3 artefact can be tied to the tree state that produced it and no defect above can be reproduced at that state.
**status:** OPEN
**severity:** MEDIUM
**opened:** 2026-11-04

**What is wrong.** Provenance is unrecoverable after the fact: the record names no revision.

**Evidence.** Leaf `/meta/git_rev` on `evidence/termination/build_A_50ohm_p51_phasors.json` (null). Artefact-leaf evidence only — there is no code `path:line` for this in §4, and none is invented here; the writer site was not identified by the source.

**What closes it.** [PROPOSED here, not stated by the source] Stamp `meta.git_rev` from the working tree at write time, or accept the artefact as unattributable on the page rather than in principle.

**Gates:** every reproduction claim made from a v3 artefact, including the ones in this register.

## DR-29 — four z0 values in one artefact, and `summary_line` prints n/a for each it labels

**id:** DR-29
**title:** Four different z0 values live in one artefact — `line.z0`, `run.station_fit.z0`, `z0_model` and the TE 47.54 ohm figure — with no arbitration between them, and `summary_line` prints **n/a** for each it labels.
**status:** OPEN
**severity:** MEDIUM
**opened:** 2026-11-04

**What is wrong.** Nothing in the record says which impedance is the line's, so any reader may pick the one that suits. `line.z0` = **42.43786214405251 − j15.727993189312496**, `run.station_fit.z0` = **44.207500737130495 + j0.3794459968505162**, `z0_model` = **48.0987**, TE **47.54**.

**Evidence.** Leaves `/line/z0_re`, `/line/z0_im`, `/run/station_fit`, `z0_model`, TE 47.54 on `evidence/termination/build_A_50ohm_p51_phasors.json`. Artefact-leaf evidence only — §4 gives no code `path:line`, and none is invented here.

**Correction (2026-11-04, housekeeping).** The `station_fit` figure quoted above, **44.207500737130495 + j0.3794459968505162**, is the **beta_one** fit and is **STALE**: the current record's own `run.station_fit` is **47.364066848187235 + j1.6449807931078728** (the beta_two fit, z0_re `47.364066848187235`, z0_im `1.6449807931078728`, span 0.0084 m). The quote is kept unaltered as the record of what was written; the live value and the reproduction are in `docs/design/s11_refit_from_phasors_2026-11-04b.md` §6.

**What closes it.** [PROPOSED here, not stated by the source] One arbitrated z0 per artefact, with each of the four named as to which quantity it is, and `summary_line` printing the values it labels.

**Gates:** none assigned by the source (§4 gives none).

## DR-31 — a record asserts an anchor and retracts it in the same string

**id:** DR-31
**title:** Six records compute a percent-low residual against the series-R anchor and, in the same `s11.validation_reason` string, withdraw that anchor — with no superseded marker, and with the retraction last.
**status:** OPEN
**severity:** LOW
**opened:** 2026-11-04

**What is wrong.** The number and its refutation share one string, and the number comes first. A reader who stops at the percent-low keeps a figure that the same sentence says does not describe the structure, and nothing in the record marks it superseded. The arithmetic is reproducible, so this is a record-integrity defect rather than a numerics one: two incompatible claims stand side by side with no marker between them.

**Evidence.** The 6 records, the note's exact 331 characters and the counts are in `docs/design/anchor_note_extraction_2026-11-04.md` (X1 fires; X2 and X4 do not; X3 fires on 6 of 6 — every note-carrying record computes the residual first and appends the retraction after it). Leaf `s11.validation_reason` on those records under `evidence/termination/`. Artefact-leaf evidence only — the source gives no code `path:line` for the `validation_reason` writer, and none is invented here.

**What closes it.** [PROPOSED here, not stated by the source] Working rule: when an anchor is retracted, any residual computed against it is marked superseded or omitted — a retraction may not trail a number it withdraws.

**Gates:** none assigned by the source. The rule above would gate any residual quoted against a retracted anchor.

## DR-32 — the anchor note's stated reason is refuted

**id:** DR-32
**title:** The note under which 6 records decline to apply the series-R anchor justifies that decision by a "shorted stub" termination that the tree refutes; the conclusion may survive, but not for the reason given.
**status:** OPEN
**severity:** MEDIUM
**opened:** 2026-11-04

**What is wrong.** The note dated 2026-11-02 states that the strip mask is PEC-continuous from the port plane to the far `xmax` PEC wall, so the load sits in series with a shorted stub instead of terminating a matched line, and on that ground declines the series-R anchor. The premise is right and the inference is not. The mask is PEC-continuous in the code — `emfit/studies.py:2854-2861` marks the `ex` and `ey` edges from `ix_port` to `nx` as strip and or's them into the PEC mask — but the strip runs through the PML absorber, so the wave is absorbed rather than reflected off the wall, and the unloaded run reflects almost nothing. The note's citation was accurate when it was written: that block sat at `emfit/studies.py:2704-2712` on the note's dates and has since drifted +150 lines (the same shift moves the load-sigma stamp from `2732-2736` to `2882-2886`). This is therefore not a citation defect but a physical inference that the measurement contradicts. It does **not** show the note's conclusion to be wrong — it may hold for a different reason (the load is 50 ohm in parallel with 0.35 pF, not a pure series R) — but the stated justification cannot be what carries it.

**Evidence.** `docs/design/strip_termination_refuted_2026-11-03.md` is the refutation. The measurement that supports it: the load-free (unloaded) run measures `abs(result.gamma) < 0.02` (`tests/test_studies.py:507`), where a shorted stub would give `|Gamma|` of order 1 — a 2 % reflection is not a short. Membership of the note in the records, and its character-identical text, are in `docs/design/anchor_note_extraction_2026-11-04.md`. DR-31 is independent of this defect: it is about how a record presents a retracted anchor, not about whether the retraction's reason is sound. The note's own line reference is frozen inside six artefact strings and cannot be corrected in place; read it as pointing at `emfit/studies.py:2854-2861` in the current tree.

**What closes it.** [PROPOSED here, not stated by the source] Re-state the reason the anchor is not applied, on grounds the tree supports, or apply the anchor. Which of the two is correct is a decision this register does not make; the task is only to stop the records from resting on a refuted justification.

**Gates:** none assigned by the source. It bears directly on any anchor decision taken from these 6 records.



## DR-33 — a record named *through* is a 50 Ω loaded run

**id:** DR-33
**title:** `build_A_50ohm_through_p51.json` carries the 50 Ω loaded physics of `build_A_50ohm_p51_noref.json` to the last digit; the name asserts a through-line the run did not use.
**status:** OPEN
**severity:** MEDIUM
**opened:** 2026-11-05

**What is wrong.** A record labelled `through` is a loaded run. Flattening both artefacts to leaves (203 each) leaves **8 differing leaves, every one of them under `/meta/`** — `argv`, `command_line`, `started_utc`, `finished_utc`, `pid`, `peak_rss_mb`, `wall_call_s`, `wall_total_s`. Every physics leaf is identical, including `/s11/magnitude` = **0.03379343163562476** (= `/ac/AC-3/achieved/s11_abs`) and `/s21/magnitude` = **0.7628473102840976**. Both records carry `/run/load_port` = **`p2`**. The `through` record's own `/meta/argv` is `--n-line 64 --mem-ceiling-mb 500 --s21-plane-index 51 --out evidence/termination/build_A_50ohm_through_p51.json` — the `--load-at-mm` and `--load-ohm` flags are **absent**, so the defaults applied, and `--load-ohm` defaults to `LOAD_VALUE_OHM = 50.0` (`evidence/termination/run_build_A.py:133`, argument declared at `:1242`). The loaded sibling spells the same two flags out explicitly in its `/meta/argv` (`--load-at-mm 20 --load-ohm 50`), which is why the two runs land on identical physics with different names.

**Correction to the dispatch's phrasing (file wins).** The pair is **not** byte-identical: different `sha256`, 11,547 B against 11,629 B. It is the **physics leaves** that are identical; the `/meta/` block differs because they are two separate runs. The defect is unchanged — a name asserting a topology the flags contradict — but the claim should be stated as "identical in every physics leaf, differing in `/meta/` only", not "bit-identical".

**Evidence.** Leaves `/meta/argv`, `/meta/command_line`, `/run/load_port`, `/s11/magnitude`, `/s21/magnitude`, `/ac/AC-3/achieved/s11_abs`, `/ac/AC-3/achieved/s21_abs` on `evidence/termination/build_A_50ohm_through_p51.json` and `evidence/termination/build_A_50ohm_p51_noref.json`; the default at `evidence/termination/run_build_A.py:133` and `:1242`.

**What closes it.** [PROPOSED here, not stated by the source] Retire the `through` label, and let the artefact's own load block state whether a load flag was defaulted — a run must not be identifiable as loaded only from a filename or from a diff against a sibling.

**Gates:** any table, figure or claim that treats `build_A_50ohm_through_p51.json` as a matched through-line (it is the record most easily mistaken for the reference-free run, and it is not one).

## DR-34 — two AC-7 records, 3.1 % apart in β and opposite in verdict, both labelled AC-7

**id:** DR-34
**title:** `graded.json` scores AC-7 **pass** at β = 216.7622 rad/m on the `w = 0.8 mm` mesh; `graded_v2_refix.json` scores AC-7 **fail** at β = 223.5813 rad/m on the `w = 3.2 mm` mesh — same bar string, opposite verdict, no supersession marker.
**status:** OPEN
**severity:** MEDIUM
**opened:** 2026-11-05

**What is wrong.** The criterion is graded twice, on two different strip widths, and the two graders disagree about whether it closes. The `pass: true` record is the one the same directory disowns: `evidence/termination/README.md:3` describes the artefacts on disk as recorded by the revision that passed `n_strip` 2 — "a strip 4x narrower than the `w` its own phase reference is computed for" — while the refix, at `w_m` 0.0032, fails. A criterion recorded as closed therefore rests on a mesh the directory itself refuses, and nothing in either file marks which is live.

**Evidence.** `evidence/termination/graded.json` → `/criteria/AC-7`: `pass` **true**, `/achieved/beta_fdtd_rad_per_m` **216.7621604119496**, `/achieved/beta_modal_rad_per_m` **216.86115860414054**, `/achieved/beta_modal/eps_eff` **3.152375648868031**, `/achieved/beta_modal/w_m` **0.0008**, `/achieved/rel_error` **0.0004565049491949793**, `/achieved/deembedded_slope_rad_per_m` **182.5103483472008**. `evidence/termination/graded_v2_refix.json` → `/criteria/AC-7`: `pass` **false**, `status` "scored: outside the 0.001 bar", `/achieved/beta_fdtd_rad_per_m` **223.58131180256908**, `/achieved/beta_modal_rad_per_m` **227.31018858464796**, `/achieved/beta_modal/eps_eff` **3.4634763080674587**, `/achieved/beta_modal/w_m` **0.0032**, `/achieved/rel_error` **0.016404353915224042**, `/achieved/rel_error_vs_hammerstad` **0.0010219020795365688**, `/achieved/deembedded_slope_rad_per_m` **240.77618158901416**. The bar string is character-identical in both blocks.

**Correction to the dispatch's phrasing (file wins).** The dispatch states "README AC-7 beta = +182.51 rad/m". The file does not support that reading: `evidence/termination/README.md:3` attributes **+182.51 rad/m** to `graded.json`'s `deembedded_slope_rad_per_m` and explicitly calls it "a different quantity" from β. Quoting it as the README's β would be a misquote, and the defect below does not need it: the contradiction is between the two `/criteria/AC-7` blocks, which is a reporting-chain fact on the artefact leaves themselves. `rel_error` **0.0164** is the refix's, and it is the refix that records `pass: false`.

**Scope note (β refit test, 2026-11-05).** Re-read against the files: the entry's numbers and its title stand unchanged (216.7622 vs 223.5813 is 3.15 % apart, titled "3.1 %"), and the correction above is confirmed — the **+182.51 rad/m** figure is `graded.json`'s `deembedded_slope_rad_per_m`, which `evidence/termination/README.md:3` calls "a different quantity" taken across two runs over the 10.0 mm between them, so it is neither a β nor part of this comparison. DR-34's scope is therefore exactly **a 3.15 % β disagreement between two identically-labelled AC-7 records with no supersession marker**; see `docs/design/beta_refit_test_2026-11-05.md` §12.

**What closes it.** [PROPOSED here, not stated by the source] One live AC-7 per graded state, with the mesh it was scored on (`w_m`, `n_strip`) carried in the same block and a supersession field on the older one.

**Gates:** any statement that AC-7 closes. On the corrected-width mesh it does not.

## DR-35 — the loaded siblings of one cross-section carry physically impossible ε_eff at both bounds

**id:** DR-35
**title:** Three loaded records of the same cross-section carry β = 286.87 / 286.36 / 173.41 rad/m, i.e. ε_eff **5.5162 / 5.4966 / 2.0157** — one bound above `ε_r`, the other below anything the geometry can support, a **24.3 %** spread inside one batch.
**status:** OPEN
**severity:** HIGH — **top of the board.** It invalidates the phrase "the β for this geometry" wherever it appears without a named extraction state, and it is the reason every β in this document is quoted with its source leaf.
**opened:** 2026-11-05

**What is wrong.** β and ε_eff are linked exactly by `eps_eff = (beta*c0/(2*pi*f))**2` (`emfit/studies.py:3543`), so a β is a claim about the effective permittivity, and the claim can be checked against physics. On a quasi-TEM line printed on `ε_r` = **4.4** (`/geometry/eps_r` on every run artefact) ε_eff cannot exceed 4.4 — that is a bound, not an estimate. Two of the three siblings exceed it; the third is below every static estimate the tree carries.

| record | `line.beta` (rad/m) | ε_eff from it | physical? |
|---|---|---|---|
| `build_A_50ohm_v3.json` | 286.8686891628 | 5.5162090250313955 | **impossible** — ε_eff > ε_r 4.4 |
| `build_A_50ohm_twin_p51.json`, `build_A_50ohm_v3c.json`, `build_A_50ohm_v3_twin_check.json` | 286.35930483082825 | 5.49663647596545 | **impossible** — same bound |
| `build_E_50ohm_v3d.json` | 173.4121373161 | 2.0157348231222967 | **impossible** — below anything the geometry supports |
| *(reference)* Hammerstad `line.beta_model` 223.35306683909533 | — | 3.343938 | plausible upper |
| *(reference)* `mode_profile` at `w` = 3.2 mm, 227.31018858464796 | — | 3.4634763080674587 | plausible upper |
| *(reference)* static/Laplace solve, `mode_profile` docstring | — | 3.35001 (`Z0` 50.088 Ω) | plausible lower |

The floor is as hard as the ceiling: the Laplace/static solve of the same cross-section gives ε_eff **3.35001** (`emfit/mode_profile.py` module docstring, the same figure as `evidence/t4/rung4_routeC_report.json` → `/eps_eff` 3.3500085193372136), and Hammerstad gives **3.343938**; **2.0157** is 40 % below the lower of the two, which no meshing or port artefact can produce for this geometry. The range 173.41 → 286.87 is a factor **1.654** in β and **2.74** in ε_eff, **24.3 %** in β, **within records that differ only by `n_line` and load.** β is not a property being measured here; it is an extraction state being mislabelled as one.

**Note, in the other direction.** `beta_baseline` (the station fit) 231.55331672912826 corresponds to ε_eff **3.593986** — high against both closed forms (+7.5 % on Hammerstad, +3.8 % on `mode_profile` at `w` = 3.2 mm) but **physical**, and the least implausible of the four. The pathological values are the per-record `line.beta` ones, not the station fit's. That ordering is the reason the refit test in `docs/design/beta_refit_test_2026-11-05.md` is worth running at all.

**Correction to the dispatch's numbers (file wins).** The dispatch quotes Hammerstad ε_eff **3.3425**; computing it from `line.beta_model` = 223.35306683909533 at `/geometry/f_hz` = 5827786408.327286 gives **3.343938**, a 0.043 % difference. The table above quotes the computed value; the 3.3425 figure does not reproduce and is not used.

**Evidence.** `evidence/termination/build_A_50ohm_v3.json`, `build_A_50ohm_twin_p51.json`, `build_A_50ohm_v3c.json`, `build_A_50ohm_v3_twin_check.json`, `build_A_50ohm_v3b_c51.json`, `build_E_50ohm_v3d.json` → `/line/beta`, `/line/eps_eff`; `/geometry/eps_r`, `/geometry/f_hz`; `emfit/studies.py:3543` for the conversion; `emfit/mode_profile.py` docstring for ε_eff 3.35001. Twin-mapping corrections carried forward from `docs/design/beta_drift_analysis_2026-11-05.md` are not re-derived here.

**What closes it.** [PROPOSED here, not stated by the source] One arbitrated β per record from a **load-free** extraction, with an admissibility test on ε_eff against `[eps_eff_static, eps_r]` before the value is allowed into any artefact field named `beta`. Until then, no document may quote "the β for this geometry" without naming which extraction produced it.

**Gates:** every β-dependent number in the termination work — AC-7, the de-embeds, and every phase residual reported against a TE prediction.

## DR-36 — a box-limited rung (`Z0` = 50.088 Ω at a 20 mm box) is recorded and cited as a converged value

**id:** DR-36
**title:** The modal quasi-static `Z0` = **50.088 Ω** carried by `emfit/mode_profile.py:586-596` is quoted as converged; a same-solver ladder puts that figure on the `n_clean = n_air = 200` rung of a sequence still drifting **0.073 %** per doubling at `n` = 800, with a limit of **49.90 Ω** — **0.37 %** below the quoted value, and **0.91 %** between the two coarsest rungs.
**status:** OPEN
**severity:** MEDIUM — it moves no verdict by itself (see *gates*), and it is **not** a numerical error: 50.088 is a correctly computed number, the word "converged" attached to it is not.
**opened:** 2026-11-05

**What is wrong.** `emfit/mode_profile.py:586-596` solves the cross-section on a finite box built by `_section` (`:447`, grid filled at `:467-469`), and the box is not a fixed property of the geometry: the wall stands `n * cell` from the strip, so the production setting `n_clean = n_air = 200` is a **20 mm box per side**, and any other `n` is a different box. The `Z0` = 50.088 Ω that falls out of that one rung is recorded there and cited downstream as *the* quasi-static impedance, with the box unstated. It is a rung, not a converged value. The same solver on the same section — `h` = 1.6 mm, `w` = 3.0 mm, `n_sub` = 16, ε_r = 4.4 — at `n_clean = n_air` = 100 / 200 / 400 / 800 gives:

| `n_clean = n_air` | box per side | `Z0` (Ω) | ε_eff | drift per doubling |
|---|---|---|---|---|
| 100 | 10 mm | 50.546918 | 3.392371 | — |
| 200 | 20 mm | **50.088467** | 3.350009 | **−0.91 %** |
| 400 | 40 mm | 49.954238 | 3.337458 | −0.27 % |
| 800 | 80 mm | 49.917788 | 3.334033 | −0.073 % |
| → ∞ | — | **49.90** (window 49.899–49.904) | — | — |

The trend fit `Z0(n) = Z0_inf + a/n^p` over the four rungs gives `Z0_inf` = **49.901498**, `a` = 2468.4, `p` = 1.79126 (fit residuals −6.0e-5 / +4.8e-4 / −1.1e-3 / +7.2e-4; the ±0.001695 the fit prints is a covariance and is **not** quoted as an error bar), and the limit is confirmed independently of the fit: a 3-point fit on 100/200/400 (`p` 1.772071, `Z0_inf` 49.898667) predicts `Z0(800)` = **49.914938** against **49.917788** measured (+0.0057 %); two successive triples give 49.8987 / 49.9042; Richardson on the finest pair gives 49.8371 (`p` = 1) / 49.9062 (`p` = 2). Quoted limit **49.90 Ω**, window 49.899–49.904 — **0.372 %** below the rung the record quotes, and still creeping at the finest rung, which is what "not converged" means here.

**Evidence.** Same grid, same code path — this is not a second implementation disagreeing with the first: at `n` = 200 the ladder reproduces the recorded static ε_eff **3.35001** to **1.5e-6** (`eps_eff(200×200)` = 3.350008519 against 3.35001, the figure `emfit/mode_profile.py:588-596` itself carries and the same figure as `evidence/t4/rung4_routeC_report.json` → `/eps_eff` 3.3500085193372136). ε_eff converges long before `Z0` does, and that is the whole mechanism: an ε_eff-based convergence claim, transferred to `Z0`, is false at the same skill. Full ladder, fit, cross-checks and the downstream arithmetic: `docs/design/z0_quasistatic_ladder_2026-11-05.md` §3 (ladder and fit), §4 (where 50.088 sits among the seven other `Z0` candidates — **−0.372 %**, the closest of the set), §7 (verdict). Row: `z0-quasistatic-ladder-2026-11-05` in `docs/design/dispatch_log.md`. The figure is quoted bare in more than one place — the `mode_profile` docstring, the `Z0` tables in `docs/design/anchor_audit_2026-11-05.md`, and this register's own DR-35 reference row (`mode_profile` docstring, ε_eff **3.35001**, `Z0` 50.088 Ω) — so it reads as geometry-intrinsic when it is rung-intrinsic.

**Candidate causes** — none picked here, and none needs to be: (i) the docstring figure was never a convergence claim and the word "converged" was supplied by a later citation, so only the citing sentence is wrong; (ii) the 20 mm box is genuinely too small — the fringing field is truncated by the air wall / ground boundary — so the number is a finite-box effect at every `n` production can afford; (iii) `Z0` is a ratio of two integrals that converge at different rates and simply converges more slowly than ε_eff, so a convergence claim measured on ε_eff was transferred to it unchecked. The three differ only in *why* the rung is box-limited; all three are closed by the same rule below.

**What closes it.** [PROPOSED here, not stated by the source] A citation rule, not a code change. No document or artefact may quote `Z0` = 50.088 bare: it is quoted either as the rung **with its box** — `50.088 Ω @ n_clean = n_air = 200, 20 mm box` — or as the limit, **49.90 Ω** (window 49.899–49.904). The docstring line carrying 50.088 gains the same parenthetical, and the word "converged" is not applied to `Z0` at a fixed box. No existing number changes: the ladder adds rungs, it does not correct 50.088, and nothing in the solver or the extraction needs to move.

**Gates:** any anchor computed at `Z0` = 50.088 — `50/(2*Z0+50)` = **0.332942**, which reads **−2.216 %** (−0.195 dB) against the measured `|Gamma_port|` 0.3255649, and both the anchor and the residual are rung-dependent; any statement that the modal `Z0` is converged, or that "the quasi-static `Z0`" *is* 50.088; and any DR-14-style "`Z0` to ~1 %" phrasing, which the 0.91 % coarse-pair swing already meets by itself and which must therefore name the rung it quotes. The direction matters and is not a rescue: at the limit the same anchor is **0.333772** and the residual **−2.459 %** (−0.216 dB), i.e. refining `Z0` *downwards* makes a **larger** anchor and a slightly **worse** residual, so this defect sharpens the anchor disagreement rather than softening it.

## DR-37 — a production-geometry quasi-static solve was run at a test-fixture width (3.0 mm, not the board's 3.2 mm)

**id:** DR-37
**title:** The Dispatch 10 `Z0` ladder — and the §2 sentence that describes its geometry as "production microstrip … the FDTD board's own cell" — was run at `w = 3.0e-3` m, which is `W_CONVERGED` from `tests/test_mode_profile.py:64`, a **test fixture**. The production board is `w = 3.2e-3` m (`MS_W`, `emfit/studies.py:1159`; `MS_N_STRIP = 8`, `:1197`; cell `h/n_sub` with `n_sub = 4`, `:1188`). Re-run at the board width the limit moves **49.9015 → 48.0237 Ω** (**−3.763 %**), which withdraws the Dispatch 10 conclusion that the extraction family carries a common systematic bias.
**status:** OPEN
**severity:** HIGH — unlike DR-36 this one moved a verdict: a correct solve at the wrong width produced a limit that agreed with the wrong width's closed form to 0.16 %, and that agreement was read as the extraction family being 4.1–5.4 % low when it is in fact within 1.4 % of the board-width solve.
**opened:** 2026-11-05

**What is wrong.** `_section(h, w, n_sub, n_clean, n_air)` (`emfit/mode_profile.py:447`) takes `w` from its caller and derives `n_strip = int(round(w / cell))` (`:458`) — the section has no notion of which line it belongs to, so any caller's `w` is accepted and silently meshed. `emfit/mode_profile.py:535-543` passes whatever the caller supplied, and `docs/design/z0_quasistatic_ladder_2026-11-05.md` §2 supplied `3.0e-3`, the width that `tests/test_mode_profile.py` pins its convergence test to (`W_CONVERGED = 3.0e-3`, `:64`, used at `:83`). The production board is `3.2e-3` m at a `0.4e-3` m cell (`h/n_sub` = `1.6e-3/4`), strip 8 cells — the same numbers `/geometry/` records in the artefact (`w` 0.0032, `n_strip` 8, `cell_m` 0.0004, `n_sub` 4, grid `62x212x22`). The two widths differ by **6.25 %**, and at this `h`/ε_r the closed form the tree already carries (`emfit/microstrip.py:141`, `t` = 35 µm) separates them by **3.91 %** in `Z0` — `49.9797` vs `48.0987` Ω. Nothing in the code or in the doc's own text reconciled the two: §2 called the geometry "production" and "the FDTD board's own cell" in the same sentence that set `w` to the test fixture's value, and `n_sub = 16` (making the cell `0.1e-3` m, i.e. **not** the FDTD board's `0.4e-3` m cell) was in the same sentence. The ladder therefore answered a question about a line the project does not have.

Re-run with only `w` changed (`3.2e-3`, so `n_strip = 32`), same solver (`emfit/quasistatic.py:334`), same constructor, same `n_clean = n_air` rungs:

| `n_clean = n_air` | box per side | `Z0` (Ω) | ε_eff | drift per doubling |
|---|---|---|---|---|
| 100 | 10 mm | 48.658870 | 3.412440 | — |
| 200 | 20 mm | 48.209081 | 3.369119 | −0.924 % |
| 400 | 40 mm | 48.076346 | 3.356179 | −0.275 % |
| 800 | 80 mm | 48.040141 | 3.352632 | −0.075 % |
| → ∞ | — | **48.0237** (window 48.004–48.028) | **3.350989** | — |

Fit `Z0_inf + a/n^p`: `Z0_inf` = 48.023741, `a` = 2315.9, `p` = 1.78091 (residuals −6.3e-5 / +5.0e-4 / −1.2e-3 / +7.5e-4; the printed covariance is not an error bar). Cross-checks, all consistent: the 3-point fit on 100/200/400 predicts `Z0(800)` = 48.037175 against 48.040141 measured (+0.0062 %); successive triples give 48.0208 / 48.0266; Richardson on the finest pair gives 48.0039 (`p` = 1) / 48.0281 (`p` = 2). The board's own box is the `n` = 200 rung — 20 mm per side — so the physically honest board figure is **48.209 Ω @ 20 mm box**, and the limit is the extrapolation.

**Evidence.** The move is not a shift of the whole ladder, it is the closed form's own width sensitivity: solver limits `49.901498 → 48.023741` = **−3.763 %**; closed form `49.9797 → 48.0987` = **−3.764 %**. The two methods agree on the width effect to **0.03 %** of it, and the board-width solver limit sits **0.156 %** from the board-width closed form — the same 0.16 % agreement that made the 3.0 mm limit look right against the 3.0 mm closed form. ε_eff carries the same signature: solver width difference at fixed box (`n` = 200) `+0.019110`, closed form `+0.018483` (+0.56 %, matched to 0.2 %). Downstream: at the board-width limit the anchor `50/(2*Z0+50)` = **0.342354** and the measured `|Gamma_port|` 0.3255649 reads **−4.904 %** (−0.437 dB), against the 3.0 mm limit's −2.459 %; at the board's own 20 mm box it is 0.341488 / **−4.663 %** (−0.415 dB). Full ladder, fits, residuals and anchor table: `docs/design/z0_quasistatic_ladder_2026-11-05.md` §9. Row: `dispatch-11-board-width-ladder-2026-11-05` in `docs/design/dispatch_log.md`.

**Candidate causes** — (i) `w` has no production binding at the quasi-static call site, so the section is only as correct as its caller's argument and no assertion can catch a wrong one; (ii) the ladder was written against the test that validates the *solver*, and the test's geometry constant (`W_CONVERGED`) was mistaken for the project's geometry — a provenance error in the doc, not in the solver; (iii) `n_sub = 16` in the same sentence shows the same drift: it is `mode_profile`'s default, and the board's is 4. All three are the same defect class: the section was described as "production" while being parameterised entirely from test/default constants.

**What closes it.** [PROPOSED here, not stated by the source] (a) The doc of record's §2 sentence is corrected in place with a dated note (§9 there), and every number derived from it carries the board-width value as well — done in §9. (b) A citation rule: a quasi-static `Z0`/ε_eff is quoted with **`w` and the box** attached, not with the word "production" — the same rule DR-36 imposes on the box. (c) The durable fix, not made here and not authorised here: give the call site a production-geometry constant (`MS_W`, `MS_H`, `n_sub` from `emfit/studies.py`, or one shared `BOARD` record) so a cross-section solve cannot be run at a test fixture's width while calling itself production. No solver change is implied and none of the numbers above needs re-deriving.

**Gates:** any `Z0` quoted from a quasi-static cross-section without its `w`; any statement that the extraction family sits 4–5 % below the quasi-static limit (Dispatch 10 §7.3, **withdrawn** — the family is within **1.4 %** of the board-width limit: twin `zc` −1.01 %, `beta_base` −1.37 %, TE −1.01 %, `beta_rawphase` −0.21 %, `beta_hammerstad` −0.17 %, `z0_model` +0.16 %); any anchor residual quoted at 49.90 Ω (−2.459 %), which is a 3.0 mm number and not this board's; and any "the 5.5 % is an artefact of the twin's `zc`" phrasing (Dispatch 10 §6.1 / bracket Z1) — at board width the limit gives **−4.90 %** and the board's own box **−4.66 %**, so the −5.5 % order of magnitude stands and `Z0` is **not** excluded as its explanation.

## DR-38 — narrative drifts from labels in fluent prose

**id:** DR-38
**title:** Narrative drifts from labels in fluent prose.
**status:** OPEN
**severity:** MEDIUM — class-level: no single instance moves a grade, but the class is what produced the KeyError recorded in `multifreq_beta_test_2026-11-07.md` §8, where a worker read two field names out of fluent prose and both were wrong. Prose is the interface workers actually read.
**opened:** 2026-11-07

**What is wrong.** The record is checked where it is code and unchecked where it is English: a citation, a constant, a boolean, a label or a bracket limb written into a sentence is trusted by the next reader exactly as an artefact key is, and nothing re-reads it against its source leaf. Six instances, one class.

1. **Citation drift** — the three source lines for the fitted split sit at `emfit/ports.py:1516`–`1518`; both the split and the docstring condition were first cited 14 lines low.
2. **A number never computed** — "48.0269" appears in prose as an implied `Z0`; inverting the same closed form gives 51.7896 Ω. The printed figure is the anchor quoted back to itself, and reported as agreement with it.
3. **A stale constant** — 0.65535 is `1 − 0.344654`, carried forward from a superseded leaf; re-derived for this leaf the factor is 0.657646.
4. **A boolean contradicting its own prose** — `raw_reference_independent: true` on leaves whose accompanying prose describes a reference that is not independent of what it references.
5. **Labels on the wrong quantity** — the dispatch-log row added in `a6ba7f6` used `Re(Z_sim)` / `Re(Z_analytic)` as column labels over β values; corrected to `beta_fit rad/m` / `beta_model rad/m` / `delta_beta_frac` in `fc9fc0e`. The numbers were right; the labels would have carried β into anchor arithmetic.
6. **Bracket verdicts citing unregistered limbs** — verdicts scored against limbs that were not in the frozen bracket text. A limb invoked at scoring time was not pre-registered.

**What closes it.** [PROPOSED here, not stated by the source] **Standing fix rule: any number written into a table cell or a bracket verdict must be re-read against its source leaf before commit, not against the dispatch text.** Workers already do this for code — five audit defects were caught that way — and it is not yet done for prose. A citation is opened before it is typed; a derived figure is recomputed before it is printed; a constant is re-derived for this leaf rather than carried; a label is checked against the type of the column under it; a bracket limb is quoted verbatim from the frozen text.

**Gates:** any citation typed without opening the cited range; any derived figure in prose without a stated recomputation; any constant recited from an earlier leaf; any `Re(Z)` / `Z0` label over a β column; any bracket verdict whose limb cannot be found verbatim in that bracket's frozen text.

**Subordinate sub-item, NOT fixed here.** Unescaped pipes inside table cells in `docs/design/dispatch_log.md` break GFM rendering only: no number is affected and no cell content is lost in the source. Deferred to housekeeping, and recorded here so it is neither rediscovered as a new defect nor repaired as a side effect of an unrelated edit. The count is unadjudicated and fixing it starts by adjudicating it: one pass recorded 15 across 6 rows (lines 20, 21, 30, 79, 142, 197), a re-count on the 2026-11-07 tree found 44 extra pipes across 4 rows (lines 19, 21, 22, 31), with lines 79, 142 and 197 carrying no pipe characters at all.
