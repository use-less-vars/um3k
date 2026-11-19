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

The two-wave `s11.magnitude = 0.325565` is the reflection carried forward: plane-invariant by construction, stable across arms, within 5.5% of the **circular** anchor 0.3446515 = 50/(50 + 2*47.53662) (Z0 47.53662 Ω) and within 4.9% (coarse mesh) of the **independent** anchor 0.3423544 = 50/(50 + 2*48.0237405) (Z0 48.0237405 Ω, w = 3.2 mm; ledger E10, DR-37). **The -5.5% and the -4.9% are ONE numerator measured against TWO denominators, not two disagreeing measurements.** More than one Z0 candidate exists at all because the artefact carries four z0 values with no arbitration between them (DR-29) and because the ladder's Z1 rung was run at the wrong strip width (DR-37). Case C on the attenuation question: `fit_beta(n_wave=2)` carries no alpha term, so no attenuation was ever applied and there is no e^(+2*alpha*d) to restore. The 5.5% residual is fit bias, already quantified as configuration-dependent in the artefact's own `s11.validation_reason`; these are **circular-anchor** numbers, i.e. against 0.3446515: 5.5% (n=64, 20 mm load), 7.6% (n=54, 100 ohm), 13.8% (n=79, 30 mm load), attributed to the load's near field reaching the last station.

DR-19 REMAINS OPEN: the residual is a separate, now-quantified problem. Against the independent anchor (Z0 48.0237405 Ω, ledger E10) it reads 4.8-4.9% (coarse mesh) and is stable across runs, falling to -3.10% with a dispersive beta; on the fine mesh the same two estimators read 6.52% (two-wave) and 6.42% (one-wave), so the 4.8-4.9% family above is superseded (amendment 2026-11-10, dispatch `substrate-shift-2026-11-10`); it is under active diagnosis, not closed (ledger E1, ledger E11). **AC-3 remains UNGRADABLE** — nothing in this section is a pass.

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

## DR-39 — two test-configuration defaults make a healthy suite report as broken

**id:** DR-39
**title:** Two test-configuration defaults — a duplicated `-q` and a 300 s signal-method timeout — make a healthy suite report as broken.
**status:** OPEN
**severity:** HIGH — a timeout inside a solve is indistinguishable, in the report, from a hang and from a failure, so this defect teaches every reader to discount the suite and can hide a real regression behind an expected timeout. It defeats the verification channel itself, which costs more than either of the two defaults.
**opened:** 2026-11-09

**What is wrong.** Two independent configuration defaults, neither of them a solver defect, combine to make the suite's report say much less than a reader assumes it says.

1. **The `-q` collapse.** `pyproject.toml:62` carries `addopts = "-q"`. Any *further* `-q` — a habitual `pytest -q`, or a `-q` written into a wrapper — makes the effective flags `-qq`, which suppresses the terminal summary line; with `--collect-only` it also suppresses the collected-id list. The consequence is not a wrong number, it is the **absence** of the number: how many tests ran, which ones, and whether they passed all become unavailable at exactly the moment a reader is trying to establish them. Nothing in the output says whether the run was terse or silent.
2. **The un-interruptible clock.** `pyproject.toml:64` carries `timeout = 300`, and **no `timeout_method` is configured anywhere**: `pyproject.toml` is the only pytest configuration file in this tree — there is no `setup.cfg`, `pytest.ini`, `tox.ini`, `conftest.py` or `tests/conftest.py` — so the method falls through to pytest-timeout's own default, `signal` (`pytest_timeout.py:26-30`, resolution at `pytest_timeout.py:372-373`), which arms `SIGALRM`. `SIGALRM` cannot interrupt a blocked C call, so a slow-but-**correct** sparse solve runs past the deadline and is reported as `Timeout (>300s) from pytest-timeout`. Observed inside `scipy/sparse/_compressed.py:395` — `fn(M, N, self.indptr, self.indices, self.data, other, result)`, the CSR matvec call into `_sparsetools` — on a **185108 x 190296** matrix with **740432** stored entries: a real FDTD solve, not a pathological input.

**Evidence.** Measured on the 2026-11-09 tree, every test file run on its own with an explicit per-file clock (`python3 -m pytest tests/<file>`, one file at a time, with the timer's own budget raised externally) rather than in one `pytest` invocation. Interpreter facts, re-read here: python 3.12.15, pytest 9.2.0, pytest-timeout 2.4.0, scipy 1.18.1.

- **The tree holds 49 `tests/test_*.py` files, at HEAD and on disk; `python3 -m pytest tests/ --collect-only -o addopts="" -q` collects 584 tests across all 49 with zero collection errors.** So the suite's size is 49 files / 584 tests, and any smaller figure is a figure about a run, not about the tree.
- **Reconciled form, and the only form that may be quoted: 43 of the 46 files the sweep attempted ran to completion with zero failures and zero errors; 3 stalled on the clock. The remaining 3 of the 49 were outside that sweep, by name: `tests/test_cpp_parity.py` and `tests/test_step_extraction.py` need the compiled C++ extension on `PYTHONPATH` (an earlier measurement with `PYTHONPATH=build/cpp` recorded 20 passed - NOT re-run today, so it is quoted as recorded, not as verified), and `tests/test_demo_picker.py` was excluded as environmental and passes alone in 9.81 s.
- The three that stalled, named: `tests/test_studies.py` (61 items collected; the sweep did not reach the end of the file and one `pytest-timeout` was raised), `tests/test_board.py` (**20 of 21** completed) and `tests/test_mode2d.py` (**1 of 3** completed). They are **unrun at the clock, not broken** - with one honesty clause: that `F` for `tests/test_studies.py` is a `pytest-timeout` raised under a 60 s budget tighter than the 300 s configured at `pyproject.toml:64`, not an assertion failure. Nothing in this entry asserts a wrong result in any of the three, and none may be described as failing.
- **Every non-green result in the entire investigation was a `pytest-timeout` inside a scipy sparse matvec — never an assertion failure, never an error.**
- `tests/test_demo_picker.py`'s reputation as a hang is **pre-existing and environmental**, not this defect: it POSTs a real demo FDTD solve through `emfit/webapp.py` and `emfit/studies.py` with a **600 s** HTTP client deadline — `HTTP_TIMEOUT = float(os.environ.get("EMFIT_TEST_HTTP_TIMEOUT", "600"))` at `tests/test_demo_picker.py:43`, used at `:87` — because its own module docstring records the suite running "~40-75x slower than documented" under container load (`tests/test_demo_picker.py:17-21` and the comment block at `:37-43`). Run alone it passes in **9.81 s**.

**Why it matters.** A timeout inside a solve is indistinguishable, in the report, from a hang and from a failure. Every reader of a truncated run learns to discount the suite; a real regression that happens to surface as a slow solve hides behind an expected timeout; and a `-qq` run cannot answer the one question it was invoked to answer. This is a defect in the reporting instrument, not in the solver, and it makes "the tests pass" unfalsifiable in both directions — "green" is unavailable, "red" is meaningless.

**Why it was not fixed in Dispatch 2.** The fix touches `pyproject.toml` and test configuration, not `server/poc_app.py`; Dispatch 2's write scope was the viewer, and its row states the timer behaviour as a limitation rather than repairing it (`docs/design/dispatch_log.md`, row `dispatch-2-abcd-2026-11-09`, items (g)-(i)). It is recorded here so the limitation is owned by the register and not only by a dispatch row.

**What closes it.** (a) An interruption method that can actually stop a blocked C call — the `thread` method, or better, per-test `timeout` markers with a solve-sized budget, so a deadline means "this solve is broken" rather than "this machine was loaded"; either way with `timeout_method` **written down** in `pyproject.toml` instead of inherited from a third-party default. (b) The `-o addopts=""` discipline in any recording harness, so the summary line and the collected-id list survive and a duplicated `-q` cannot silence them. (c) A re-run of the three files that never completed, at a budget that fits them, so that `unrun` becomes either `passed` or a named assertion.

**Gates:** it gates no acceptance criterion directly, but it gates the credibility of every "the tests pass" claim made about this repo. Barred until (a) and (c) above are done: any sentence of the form "the suite is green"; any count of passing tests taken from a `-q`/`-qq` invocation whose summary line is absent; and any report that treats a `pytest-timeout` as evidence of a failing test.

## DR-40 — the load-station filter silently un-filters itself, and tests the wrong membership

**id:** DR-40
**title:** `_station_fit_selection` (`emfit/studies.py:2347`, called at `:3529`) drops a station from the impedance fit only when its column is *exactly* a load column, and returns **all** stations untouched — load column included — whenever the filter would leave fewer than four. It then reports `excluded = False`, so no downstream reader can tell a filtered fit from an unfiltered one. The docstring describes the opposite behaviour.
**status:** OPEN
**severity:** MEDIUM — latent: it does not fire on the p51 record (`load_station_excluded: true`, 8 of 9 stations kept), but both branches are silent, and the failure they produce is not an exception — it is a plausible-looking `z0` fitted to a boundary condition. Any run whose station list starts at the load column, or whose stations sit beyond it, gets the load column inside the impedance fit with no record of it.
**opened:** 2026-11-10 (this entry)

**What is wrong.** The function's whole purpose — stated in its own docstring at `:2349-2361` — is that "any station on a load column is therefore dropped from the *impedance* fit", with the stated exception that "``excluded`` is ``False`` and the three arrays are returned unchanged when there is nothing to drop, or when dropping would leave fewer than the four stations :func:`emfit.ports.fit_station_impedance` requires" (`:2359-2361`). The implementation is four lines:

```python
2363:    load_columns = {int(entry["column"]) for entry in loads_used}
2364:    if not load_columns:
2365:        return station_x, v_stations, i_stations, False
2366:    keep = np.array([int(col) not in load_columns for col in js], dtype=bool)
2367:    if bool(keep.all()) or int(keep.sum()) < 4:
2368:        return station_x, v_stations, i_stations, False
2369:    return station_x[keep], v_stations[keep], i_stations[keep], True
```

Two facts follow from `:2366-2368`, and they are separate defects:

1. **The `<4` fallback silently un-filters.** `keep.sum() < 4` is a real condition — `fit_station_impedance` refuses fewer than four stations (`emfit/ports.py:1490-1492`, `raise ValueError(f"a two-wave fit on both sides needs at least 4 stations, got {x.size}")`) — but the response to it is to hand the fit **every** station, including the one the docstring says must never reach it. `excluded` comes back `False` (`:2368`), identical to the "nothing to drop" case (`:2365`), so the record cannot distinguish "there was no load column" from "there was one and I gave up". The alternative the docstring implies — drop the load station and let the caller see the refusal — is not taken, and nothing warns.
2. **The membership test is exact, and only exact.** `int(col) not in load_columns` (`:2366`) compares a station's integer column against the load's integer column. A station *strictly beyond* the load column — inside the load's near field, on the far side of the stamp — is never matched, so it is kept. The docstring's rationale ("the field AT that column is the load's boundary condition") is about the immediate column, so this is arguably by design; the defect is that nothing in the record or the code distinguishes "station outside the load column" from "station in the load's near field", and the `z0` fit's contamination mechanism (near-field, not the single column) does not stop at the stamp. `load_station_excluded` is therefore a claim about one integer, quoted as though it were a claim about near-field exclusion.

`fit_station_impedance` also needs at least four stations for a reason worth stating: it is a two-wave fit on both sides (`:1490-1492`), so three stations cannot resolve forward and backward amplitudes at all. The `<4` branch therefore protects against a hard `ValueError` by producing a softer wrong number.

**Evidence — and why it is not firing on p51.** On `evidence/termination/build_A_50ohm_p51_phasors.json` the nine station columns are `[26, 29, 32, 35, 38, 41, 44, 47, 50]`, the load sits on column 50, and the record reports `line.station_fit_n = 8`, `line.load_station_excluded = true`, and `station_phasors.fit_selected = [true ×8, false]` — the ninth row (column 50) is dropped, and `station_phasors.fit_x` equals `x_m[fit_selected]` exactly (max difference `0.0`). So on this record `keep.all()` is `False` and `keep.sum()` is `8 ≥ 4`: neither fallback limb is taken, the filter does what the docstring says, and the 0.32588679434738205 `|S11|` read off it is a filtered number. The defect is recorded, not observed on this leaf. The adjacent far-station leaf shows the other side of the same coin: `evidence/termination/build_A_50ohm_v3_farstations.json` has nine fit cells `[9, 12, 14, 18, 21, 24, 27, 30, 33]` with `line.station_fit_n = 9` and `load_station_excluded: false` — a *different* station span (columns 9 to 33 = 3.6 mm to 13.2 mm, so its first station is 0.4 mm from the port plane at 3.2 mm and its last is 6.8 mm short of the 20.0 mm load; 9.6 mm long), kept with the flag set false.

**Candidate causes** — (i) the `<4` branch was written to keep `fit_station_impedance` from raising, and the cheapest way to do that was to return the unfiltered arrays; (ii) the return value conflates two different facts ("nothing needed dropping" / "dropping was abandoned") into one boolean, so the honest state has nowhere to be recorded; (iii) the membership test models the load as one column rather than as a near field, and no part of the record carries the distance from the last kept station to the load.

**What closes it.** [PROPOSED here, not stated by the source] (a) Distinguish the two cases in the return value — a three-state result (`not_needed` / `applied` / `abandoned_below_minimum`) recorded into the artefact, so "abandoned" is visible rather than spelled `false`. (b) On the `<4` branch, warn (`warn_station_fit_skipped` already exists at the call site for the fit's own refusals) instead of returning silently, or let the fit refuse — the current behaviour converts a loud failure into a quiet one. (c) Record the distance from the last kept station to the nearest load column, so "excluded" is a statement about a gap and not about an integer. (d) Any change here must keep `fit_station_impedance`'s `x.size < 4` guard (`emfit/ports.py:1490-1492`) as the hard stop; the filter must never be the reason a fit runs on three stations.

**Gates:** any `z0` / `|S11|` quoted from a loaded run whose record carries `load_station_excluded: false` **and** whose station list reaches or crosses the load column — that number is an unfiltered fit and must be labelled as one; any sentence of the form "the load station is excluded from the impedance fit" that cites only that boolean, without `station_fit_n` and the station list beside it; and any future edit that adds a station inside the load's near field without re-reading this entry.

## DR-41 — the openEMS MSLPort silently drops its own launch primitive, and the probe files are named the other way round

**id:** DR-41
**title:** `FDTD.AddMSLPort` forwards `priority` into the launch metal's `AddBox` (`infra/openems/reference/ports.py:349`) and defaults it to **0** (`:107`), the CSXCAD default; at 0 the launch box is coplanar with the substrate's top face at `z_strip` and *ties* with it, so CSXCAD keeps one and discards the other — the launch — with no error, and the model solves with a port that excites nothing while the energy trace flattens at **-8.54 dB**. The same referee's extraction reader, written against the intuitive `port_1_utA` ordering, then finds no files at all, because openEMS builds the names as `port_ut_1A` / `port_it_1B`: the component token precedes the port number, because `_{}` in `lbl_temp` is bound to the number at construction time rather than at build time.
**status:** FIXED-TESTED — both halves carry a code fix in `docker/openems/build_A_referee.py` and a host run that reads through it (`evidence/referee/s11_extraction.json`: `port1_api` `"mslport"`, `s11_abs` 0.3271645531273824), recorded as E12 VERIFIED at `docs/design/EM_SOLVER_LEDGER.md:37`. This is a resolved defect recorded for its landmine, not an open item, and the landmine is the whole reason it is filed.
**severity:** HIGH — it produced a wrong number without raising, which is the shape DR-37 carries HIGH for: a correct solve of a *wrong model* whose output was believed. It is not MEDIUM-latent like DR-40, because it fired on every run rather than on a branch; and it is confined to the referee channel rather than the graded in-house artefacts only because the in-house FDTD builds no CSXCAD primitive to tie (see *Scope*). Nothing in the output marked the model as unattached — exit status zero, a plausible `|S11|` — so the only defence available was comparison against a second instrument.
**opened:** 2026-11-12 (this entry)

**What is wrong.** Two defects in one script, both silent, in the same direction: the model was not the model it was said to be, and the record could not say so.

1. **A priority tie deletes geometry instead of raising.** CSXCAD resolves overlapping primitives by `priority`, and a primitive that *ties* with a coplanar face it overlaps loses — the loss appears only as a line in the solver log, `Unused primitive (type: Box) detected in property: port1_feed`. The MSLPort's launch metal is an ordinary box built at the port's own priority (`infra/openems/reference/ports.py:349`), it is collapsed onto the excitation plane (`:348`), and `self.priority` is **0** unless the caller passes `priority=` (`:107-109`). `build_model()` passed nothing, so the launch box was coplanar with the substrate's top face at `z_strip`, tied with it, and was discarded. What is left is a port measuring a field its own feed never excited: the run exits zero, writes its reports, and the energy trace is flat at **-8.54 dB**. The same loss had already taken the *strip* (`Unused primitive ... property: strip`) in the earlier empty-geometry runs, so this was the second object to die of the same rule and the first to die silently enough to be read as a result.
2. **The probe records are named component-first, not number-first.** `self.lbl_temp = self.prefix + 'port_{}' + '_{}'.format(self.number)` (`infra/openems/reference/ports.py:119`) binds the `_{}` to the port *number* at construction, leaving the earlier `{}` for the *component* token at build time: `u_name = self.lbl_temp.format('ut') + suffix[n]` (`:375`) and the `'it'` counterpart (`:390`) therefore yield `port_ut_1A` / `port_it_1B`, not `port_1_utA` / `port_1_itB`. A reader written against the intuitive ordering resolves nothing — and because these records are extension-less ASCII rather than `.h5`, it finds no file under either extension, which is indistinguishable from a run that wrote none.

**Evidence — both halves, at source and on disk.** The tie and its cost are recorded in-code at `docker/openems/build_A_referee.py:1206-1212` (and again in the dry-run echo at `:1036-1038`): "at the default 0 that box is coplanar with the substrate's top face at z_strip, ties with it, and CSXCAD drops it (`Unused primitive ... property: port1_feed`), which flatlines the energy trace at -8.54 dB". The fix is at `:1213-1215`, `priority=port1_msl_priority(priority)`, with `port1_msl_priority` at `:1012` returning the strip's priority and `STRIP_PRIORITY` when the representation passes none, and `STRIP_PRIORITY = 10` at `:388` documented as "any value above the CSX default 0 wins; 10 is arbitrary-but-fixed and deliberately NOT tuned". The naming is source-verified at `ports.py:119`, `:375`, `:390`; the tolerant mapping is `PROBE_NAME_CANDIDATES` at `build_A_referee.py:1806-1812`, which tries the openEMS spelling first and keeps the canonical spelling as a fallback so a record set written by a patched namer still reads. The fix is verified *on disk*, not just in the source: `evidence/referee/` holds `port_ut_1A`, `port_ut_1B`, `port_ut_1C`, `port_it_1A`, `port_it_1B` — the openEMS spellings, so the second half is measured rather than inferred — and `evidence/referee/s11_extraction.json` reports `port1_api` `"mslport"` (`:94`) with `s11_abs` 0.3271645531273824 (`:99`) against `s11_artefact_target` 0.32556486641109117 (`:101`), i.e. a reflection read off a launch that exists.

**Scope — a referee-integration defect, not a physics defect.** Neither half is a statement about how a microstrip behaves. The in-house `emfit` FDTD terminates the line with a **conductivity stamp** on dedicated grid edges — the load-sigma stamp DR-32 names — rather than with a CSXCAD primitive, so it has no priority field to tie and no overlap to lose; and the probe-name convention is openEMS's own `lbl_temp` formatting, which exists nowhere else in this tree. Nothing here transfers to the in-house artefacts, and nothing here should be read as a numerical disagreement between the two solvers: it was three days of debugging spent on the referee's *attachment*, before any of its numbers were about a microstrip at all. What does generalise is the failure mode — a silent drop, findable only by an assertion on a physical observable — which is recorded as L11 in `docs/design/lessons_learned_emfit_addendum.md` and is L7 earned a second time.

**Candidate causes** — (i) `AddMSLPort` mirrors `AddLumpedPort`, where `priority` barely matters, so the argument reads as optional decoration and is passed by nobody; the default is the hazard, not the parameter; (ii) CSXCAD's tie-breaking rule is not documented in this tree — the package is not vendored, and `docs/design/dispatch_log.md:66` records the mechanism as INFERENCE — so the only record of the rule is an in-code note written after the fact; (iii) `lbl_temp` reads as though `{}` were the port number, and the `_{}`-bound-early construction at `ports.py:119` is a trap for exactly the reader who then writes the extraction filenames; (iv) the reader's assumption about on-disk names was never exercised against a written record until the run that needed it, so the first test of the naming was the run itself (L7).

**What closes it — done, not proposed.** (a) `priority` is passed explicitly to `AddMSLPort` and carries the strip's own value, falling back to `STRIP_PRIORITY = 10` and never to 0 (`build_A_referee.py:1012`, `:1213-1215`, `:388`); any value above the CSXCAD default wins, and 10 is deliberately not tuned so it is not mistaken for a calibrated number. (b) The extraction reader resolves through `PROBE_NAME_CANDIDATES` (`:1806-1812`) — openEMS spelling first, canonical spelling as fallback — so both orderings read. (c) The path actually opened is recorded in `PROBE_NAME_ROUTE` and logged **once** to stderr (`read_port`, `:1721-1722` and `:1732-1735`), so a name that stops matching cannot rot silently: the log is the assertion that the second defect cannot recur unobserved. (d) Not closed, and not to be claimed closed: the tie-breaking rule itself is still undocumented in this tree, so the *next* coplanar primitive will be lost the same way unless its builder sets a priority — the fix is per-primitive discipline, not a repaired toolchain.

**Gates:** any `|S11|` quoted from the openEMS referee whose extraction does not report `port1_api` — that key is what says which launch was modelled, and a lumped-port or empty-air run answers a different question; any referee number quoted without its probe route, since a name resolved by fallback is not the name the plan expected; any new `AddMSLPort` / `AddLumpedPort` / coplanar primitive added without an explicit `priority=`; and any verdict that treats exit status zero plus a plausible `|S11|` as evidence that the model was attached.

## DR-42 — the OpenMP default thread team makes the C++ kernel ~33x slower than single-thread, and single-thread is already 2.4x faster than Python, so E3 is a regression unless the thread count is pinned

- **id:** DR-42
- **title:** The compiled kernel is ~33x slower than the Python path it is meant to replace when it inherits the default OpenMP thread team, and ~78x slower than the same kernel at one thread — so a naive E3 wiring would deliver a large slowdown while looking like a speedup.
- **status:** FIXED-TESTED
- **severity:** HIGH. It does not move any verdict today (the kernel is not on any call path — `emfit/` never imports it, see E3), but it would turn the E3 rewrite into a ~33x regression if the thread team were left unpinned, and it is why no kernel figure may be quoted without a thread count.
- **opened:** 2026-11-12 (this entry)

**AMENDMENT 2026-11-12 (the parenthetical is superseded; DR-42 stays OPEN).** The `severity` bullet's parenthetical, "not on any call path — `emfit/` never imports it", is superseded by commit 6cbb89d: `emfit/evolve.py` `FITStepper.step` dispatches to `emfit_core.fit_leapfrog` when `_KERNEL` is loaded and the ABI matches, `emfit.evolve.engine_report()` names the path per process, and `tests/test_cpp_dispatch.py` / `tests/test_cpp_parity.py` gate it. DR-42 itself stays OPEN on its actual subject, the OpenMP default thread team, which the dispatch did not address: whether the kernel is now reached with a pinned thread team is NOT established here. No ladder number may be carried forward — see the retraction recorded in E3's 2026-11-12 amendment (`docs/design/EM_SOLVER_LEDGER.md:28`). The bullet above is left standing: registers are amended, never rewritten.

**SECOND AMENDMENT 2026-11-12 (the hazard is contained in the tree and still live in the artefact; DR-42 stays OPEN).** Two corrections, both verified this session, neither of which retires the entry. (i) *The tree already pins the thread team — in the consumer, not in the build.* `emfit/_env.py:44-70` (`pin_threads`) sets `OPENBLAS_NUM_THREADS`, `OMP_NUM_THREADS`, `MKL_NUM_THREADS` and `NUMEXPR_NUM_THREADS` to `"1"` when they are unset (a set value wins, including `"0"`; an empty value counts as unset), and `emfit/__init__.py:33-37` calls it at package import, under a comment stating why it sits there: "Thread pinning must run before anything imports numpy: BLAS reads its thread count once, when the shared library is loaded". Any process that reaches `emfit_core` through `emfit` therefore does so with the variables already set. (ii) *The containment is environmental, not structural, so the artefact on its own is unpinned.* The installed extension `.venv/lib/python3.12/site-packages/emfit_core.cpython-312-x86_64-linux-gnu.so` carries `NEEDED libgomp.so.1` (`readelf -d`) and an undefined `GOMP_parallel@GOMP_4.0` (`nm -D --undefined-only`); `src/CMakeLists.txt:55` compiles it with `-O2 -fno-fast-math -ffp-contract=off -fopenmp`; `src/emfit_core.cpp` carries five `#pragma omp parallel for schedule(static)` at `:83`, `:92`, `:103`, `:114`, `:130`. The default team is chosen by the *runtime* from the process environment, so a process that loads that `.so` without importing `emfit` first — a bare probe, a second interpreter, a subprocess that inherited nothing — gets the team this entry is named after, and the 78x that goes with it. Nothing in the artefact states a thread count; only the caller does.

**Evidence that the 33x is a property of the golden grid, not of the kernel, and that this register cannot yet tell two grids apart.** Commit `42d319d` ("evidence(e3): second speedup data point, OpenMP thread probe, scaling summary") adds `artifacts/build_C_stub_cpp_t1.json`, `artifacts/build_C_stub_pyengine.json` and `artifacts/ladder_engine_scaling.json`, and its own summary is that DR-42's 33x is **not reproduced anywhere here**: *no ratio in this file exceeds* **1.3877** (*one ladder rung, Python engine vs cpp at default threads, FDTD phase only*) and *no thread-related ratio exceeds* **1.3435** (*structure C, whole-process wall, default threads vs `OMP_NUM_THREADS=1`*), with **n = 1 per arm** and the two families not comparable in kind — the ladder ratios are FDTD-phase only, the structure-C ratios are process start + assembly + eigen solve + FDTD, because no per-phase timing exists at that mesh; the file says so itself. It also refuses the weaker claim that the kernel is merely slower: on the ladder the default-vs-1-thread ratio (**1.1588**) is the *same magnitude* as a same-configuration repeat (**1.1595** — two runs of one rung, 51832 cells, 2400 steps, h = 0.4 mm, identical command apart from the `--json` path), and at `OMP_NUM_THREADS=1` the cpp engine **beats** the Python engine on structure C (0.862). "cpp is about 1.16x slower" is not supported once threads are pinned. That does not refute the mechanism in "What is wrong"; it bounds it. The 33x figure is measured on the golden grid (133 edges, 392 nonzeros), where a row's dot product is a handful of flops so the barrier is the arithmetic; at board scale a row is long enough to amortise the barrier, and the ratio falls to order one. Two measurements of two grids, neither wrong — and this register has no way to say which grid a quoted number came from, because **neither `tools/host_ladder.py` nor `evidence/termination/run_build_A.py` records any thread count in its `meta`** (grepped: no thread-count key in either) — a gap the scaling artefact states about itself: `artifacts/ladder_engine_scaling.json:57` records that a recursive search for thread/omp/openmp keys returns `[]` in all seven artefacts, its `launch_omp_num_threads` field being *operator launch-environment knowledge, marked as such, not an artefact value*. An engine ratio produced by either file is therefore unattributable after the fact — the same class of provenance hole the amendment above closed for *which engine ran*.

**What this amendment adds, and what it does not.** DR-42 stays OPEN: nothing here re-measures the kernel under an inherited default team, and 3.71 us / 291 us stand as measured on the golden grid. What moves is the diagnosis. The defect is not "the build forgets to call `omp_set_num_threads`" — the build is a shared object and cannot; it is that (a) the pin is a *consumer-side* obligation discharged only by processes that import `emfit` first, and (b) no artefact records the thread count it ran with, so a figure produced under a pinned team is indistinguishable from one produced under an inherited team. The dispatch that produced this amendment adds `--force-python` to `tools/host_ladder.py` and `evidence/termination/run_build_A.py`, which lets the two engines be compared **in one process** — deliberately, with `meta.step_engine` reading `python` because the Python reference is what ran — so a compiled/Python comparison no longer needs two runs in two environments that may differ in a variable nobody wrote down. It does **not** add a thread count to either `meta`, and the gap in (b) is not closed by it. **Gates:** (a) no kernel timing, and no compiled/Python ratio, may be quoted without the thread count and the grid size beside it; (b) the 3.71 us / 291 us table above may **not** be cross-compared with anything in `artifacts/ladder_engine_scaling.json` — different grid, different arms, n = 1; (c) a kernel timing taken from a bare `.so` probe is a different experiment from one taken through the package, and must say which it is; (d) any claim that E3 is a speedup must name the engine **and** the thread count, or it is not a claim about anything.

**THIRD AMENDMENT 2026-11-12 (the "thread" ratios in `42d319d` are not thread measurements; that commit's mechanism claim is WITHDRAWN; DR-42 stays OPEN).** `emfit/_env.py:44-70` `pin_threads` runs at `emfit/__init__.py:33-37`, before either artefacted process does any work, and it sets `OMP_NUM_THREADS=1` when the variable is absent — so the arm `42d319d` calls "default (inherited) threads" and the arm it calls `OMP_NUM_THREADS=1` were the same configuration: one thread each. Neither **1.3435** (structure C, 289168 cells, whole-process wall, 58.0408 s / 43.2006 s) nor **1.1588** (ladder, FDTD phase, 7.2474 s / 6.2544 s) is a thread measurement, and the mechanism sentence in `42d319d`'s message — that the default thread team explains 58.04 s — is **WITHDRAWN** by this amendment. What the numbers do establish is repetition spread: two runs of one configuration, everything else held equal, differ by **1.3435** at structure C and by **1.1595** on the 51832-cell ladder rung. The consequence is a resolution limit, not a mechanism: **no single timing on this host at these sizes may be quoted to better than about ±34 % at structure C.** The 33x stays unreproduced for a *new* reason — not "the default team was slow", but "no run has ever reached the kernel with an inherited team, because the package will not let a team be inherited". It will let one be *chosen*: `pin_threads` overwrites only an unset or blank variable, so a non-empty `OMP_NUM_THREADS` propagates and `OMP_NUM_THREADS=4` reaches the runtime. Anyone measuring DR-42 must therefore either load the bare `.so` in a process that never imports `emfit`, or set `OMP_NUM_THREADS>1` **and confirm it reached libgomp** (`omp_get_max_threads()`, `/proc/self/environ`) — because the pin is silent, and a run will not otherwise announce that its team was one thread.

**FOURTH AMENDMENT 2026-11-13 (the pin is in the binary, not in the consumer — so DR-42 closes FIXED-TESTED and E3's verdict does not move).** The `status` bullet above now reads `FIXED-TESTED`, and this paragraph is why. **Where the pin is.** Not in the consumer. `src/emfit_core.cpp:69` is `static int g_num_threads = 1;` — a static initialiser, and the only load-time assignment to the team counter; `:71` returns it; `:73-80` is `set_num_threads(n)`, which clamps `n < 1` to `1` (`:74-76`), calls `omp_set_num_threads(n)` (`:77`), stores `g_num_threads = n` (`:78`) and returns it (`:79`); and every row-dot region carries the clause `#pragma omp parallel for schedule(static) num_threads(get_num_threads())` at `:102`, `:111`, `:122`, `:133` and `:149`. `grep -rn '#pragma omp' src/` returns exactly those five lines, so no region is left un-claused. The module initialiser `src/bindings.cpp:290` `PYBIND11_MODULE(emfit_core, m)` sets no thread state at all — `:305-306` and `:314-315` are the ABI and name attributes — and `grep -rn getenv src/` returns **zero** matches, so the extension never reads `OMP_NUM_THREADS` and an ambient team in a process that loads this binary is never consulted for those five loops. Through the package the team is set rather than inherited: `emfit/evolve.py:279` fetches `set_num_threads`, `:280-290` raises rather than proceeding when an ABI-2 kernel lacks it, `:292` calls `setter(1)` **unconditionally**, and `:324` `_KERNEL = _load_kernel()` runs at import, so the pin is taken when `emfit.evolve` is imported and holds for the process lifetime. **Correction to `:797`'s mechanism, not to its findings.** `:797` calls the pin "a *consumer-side* obligation discharged only by processes that import `emfit` first". That described the tree before `0c8da31`; as of ABI 2 the obligation moved into the binary, and a bare `.so` load gets one thread with no consumer cooperation at all. The sentence is left standing — registers are amended, never rewritten — and is superseded by this paragraph. The same commit also drifted the SECOND AMENDMENT's pragma citations at `:793`, re-anchored here: the five pragmas it places at `:83`, `:92`, `:103`, `:114` and `:130` are now at `:102`, `:111`, `:122`, `:133` and `:149` (each +19, the size of the block that inserted the accessor and the setter), and they now carry the clause it quotes them without. **The ABI boundary, which is the part of `:793` that still bites.** Only an ABI-2 binary is safe standalone. Measured on this disk on 2026-11-13 — 1e6 rows, 6 nonzeros, 5 steps, median of runs, `OMP_NUM_THREADS=12` in the environment — an ABI-2 bare load costs **0.0464 s** and matches an explicit `set_num_threads(1)` at **0.0471 s**, against **0.1045 s** at `set_num_threads(12)` (ratio **2.251**); the ABI-1 binary at `artifacts/cpp_build_e3/emfit_core.cpython-312-x86_64-linux-gnu.so` (`KERNEL_ABI` 1, no `set_num_threads`) bare-loads at **0.1031 s**, inheriting the ambient team exactly as `:793` says. Those four constants are quiet-container figures and are load-sensitive: re-measured under this session's own agent load the same arms cost about five times as much, in the same order and with a 2.29 multiple where 2.251 is quoted here, so what reproduces is the ordering and the ratio, not the constants. Through the package an ABI-1 binary never runs: the gate at `emfit/evolve.py:273-274` returns `None`, so dispatch silently falls back to the Python step, and `tests/test_cpp_dispatch.py:204` asserts that silence. The residual hazard is a *bare* `.so` probe against a stale build, not the package. The only remaining route to a team above one is an explicit `set_num_threads(n>1)` — public API, no in-tree caller, the tree's one call site being `emfit/evolve.py:292` with `1`; `OMP_THREAD_LIMIT` and `OMP_DYNAMIC` can only reduce a team below an explicit clause, never raise one. **Measurement, which is how "tested" is being claimed.** Three arms on structure A, 289168 cells, 2400 steps, `cell_mm` 0.4, on the operator's host and not in this container, recorded in `docs/design/e3_dr42_closure_benchmark.md`: cpp through the package, five runs 35.44 / 34.72 / 33.09 / 34.25 / 36.22 s, mean **34.74** (σ sample **1.19**); python with `--force-python`, five runs 45.11 / 44.65 / 46.31 / 54.08 / 47.60 s, mean **47.55** (σ sample **3.83**); cpp with `OMP_NUM_THREADS=12` exported, **one** run **34.6 s**. Ratio **47.55 / 34.74 = 1.37x**, the compiled path **36.9 %** faster than the Python path on this build. The twelve-thread arm discharges the THIRD AMENDMENT's warning that the pin is silent: the environment asked for twelve, `meta.n_threads_kernel` still reads **1**, and the cost moved **0.4 %** — in the *faster* direction, inside the pinned arm's own spread. A leak would have been a multiple, not a rounding; the container's own twelve-thread arm measures **4.506x** on the same question (`docs/design/e3_baseline_benchmark.md:96`), which is what a real team does at this size. The arm is n = 1 and settles nothing about spread; it settles what it was for. **Provenance hole (b) of `:797` is closed, and this is the mechanism rather than a promise.** `evidence/termination/run_build_A.py:3352` writes `n_threads_kernel`, `:3353-3356` is the comment explaining why two thread facts are recorded and not one, `:3357` writes `n_threads_env` and `:3358` writes `n_threads_env_requested` — all inside the same `meta` block that carries `step_engine`. The requested value survives the pin because `emfit/_env.py:48` captures `_REQUESTED_OMP_THREADS = os.environ.get("OMP_NUM_THREADS")` at module import, before `pin_threads` (`:64`) overwrites an absent variable with `'1'`, and exposes it through `requested_omp_threads()` (`:51-61`), whose docstring is explicit that `None` means absent rather than one. The operator's two runs report exactly that pair: the pinned run's `meta` as `step_engine: cpp, n_threads_kernel: 1, n_threads_env: '1', n_threads_env_requested: None`, the twelve-thread run's as `step_engine: cpp, n_threads_kernel: 1, n_threads_env: '12', n_threads_env_requested: '12'`. Those values are **operator-reported and not banked** — no `cpp_1.json` or `cpp12.json` exists anywhere in this tree (`find . -name 'cpp_1.json' -o -name 'cpp12.json'` returns nothing) — so they carry the standing of the banked host timings, and what is verified here is the code path that emits them. Gate (d) is discharged for these runs on that basis: engine named, thread count named, grid named, both arms. **Verification.** `tests/test_cpp_parity.py` reports **13 passed** against the ABI-2 binary in this container via `PYTHONPATH=build/cpp pytest tests/test_cpp_parity.py -o addopts="" -q`; bare `pytest tests/test_cpp_parity.py -o addopts="" -q` reports **13 skipped**, which is a different result and not a weaker pass, because the test module does a top-level `import emfit_core` at `tests/test_cpp_parity.py:94` and never touches `sys.path`, so a run that supplies no `PYTHONPATH` skips. A skip is never a pass, and the skip count is why the `PYTHONPATH` form is the quoted one. `KERNEL_ABI` reads **2** and `engine_report()` returns `{'step_engine': 'cpp', 'kernel_abi': 2, 'kernel_name': 'emfit_core.fit_leapfrog'}` from a from-source build using the recipe the test itself carries (g++ 14.2.0, Python 3.12.15, no warnings) as well as from the installed package. Byte count for the record: `build/cpp/emfit_core.cpython-312-x86_64-linux-gnu.so` is now **275648** bytes where the `What is wrong` paragraph below records 258720; both are true of their builds, and the ABI attribute is the reason the difference matters. **E3 does not move.** `docs/design/EM_SOLVER_LEDGER.md:28` is untouched by this amendment and its verdict stays **UNVERIFIED**: a pin is not a speed figure, and this entry never claimed one. The title's 33x and 2.4x stand as measured on the golden grid and are not withdrawn. **The 1.81x is not withdrawn and the 1.37x does not replace it: they are different builds.** Banked, cpp **27.44 s** (σ 0.37) against python **49.6 s**, ratio **1.81** (`artifacts/ladder_engine_host_timing.json:16`, `:10`, `:22`). Today, cpp **34.74 s** on the same mesh, steps and cell, so this build is **26.6 %** slower than the banked one — a **7.3 s** gap, about **20σ** of the banked cpp spread (7.3 / 0.37 = 19.7) and about **6σ** pooled (√(1.19² + 0.37²) = 1.25) — while python moved **−4.1 %**, inside its own spread. The leading candidate is the optimisation level: `src/CMakeLists.txt:55` compiles `-O2 -fno-fast-math -ffp-contract=off -fopenmp` where the ledger's E8 cell (`docs/design/EM_SOLVER_LEDGER.md:33`) records `-O3 -fopenmp -std=c++17 -shared -fPIC -Wall -Wextra`. That is **UNVERIFIED** and stays a candidate, and the tree does not agree with itself on the point: `src/emfit_core.cpp:20-21` states the kernel is "built with -O3 only (see CMakeLists.txt), never -ffast-math / -fassociative-math", while the file it names, `src/CMakeLists.txt:55`, specifies `-O2`. It stays a candidate because `artifacts/ladder_engine_host_timing.json` records no compiler flags, no `argv`, no `command_line` and no revision — its provenance block (`:24-30`) names only `/tmp/timing_py_*.json` and `/tmp/timing_cpp_*.json`, hand-copied, `raw_files_in_repo: false`. Until a rebuilt-at-`-O3` arm is measured, 1.81x and 1.37x are both real and neither may be quoted alone. **The structure label is a documentation defect, not a pin defect.** `artifacts/ladder_engine_host_timing.json:4` says `structure: "C"` while the operator's runs today are labelled `A`, on the identical mesh — `:5` `mesh_cells: 289168`, `:6` `steps: 2400`, `:7` `cell_mm: 0.4` — and the physics agree to the digits that matter (|s21| 0.761705423 against `0.7617054231929281` at `evidence/termination/gate_gate_build_A_p51.json:21`, |s11| 3.258633e-01, passivity 0.686382015950 against `0.6863820159501787` at `artifacts/build_C_plain_cut.json:286`). The label was inferred rather than recorded: the file's own `checks.mesh_cells.basis` (`:39`) derives it from the cell count in `artifacts/ladder_engine_scaling.json`. The banked artefact is not edited; the ambiguity is carried for Gen 13. **Gate, restated and widened.** (e) No kernel timing and no compiled/Python ratio may be quoted without the **build flags** beside it, in addition to the thread count and the grid size already required — because the two figures on record for the same mesh and the same steps differ by 26.6 % and the only surviving candidate explanation is a flag. This extends (a) of `:797` rather than replacing it; (b), (c) and (d) stand unchanged.

**What is wrong.** The compiled kernel (`src/emfit_core.cpp`, authoritative `.so` `build/cpp/emfit_core.cpython-312-x86_64-linux-gnu.so`, 258720 bytes) is built with `-fopenmp` and its row-dot loops carry OpenMP pragmas. Run with the default thread team it is ~33x slower than the Python path it is meant to replace. At this grid size the parallelism is not merely unhelpful, it is the dominant cost: each row's dot product is a handful of flops, so a thread team's barrier and spin cost is paid per row and dwarfs the arithmetic it distributes.

**Evidence** — re-measured in this container on 2026-11-12, golden grid (133 edges, 392 nonzeros), kernel step timed in isolation:

| configuration | per call |
|---|---|
| compiled, 1 thread | **3.71 us** |
| compiled, default OpenMP team | **291 us** (~78x the 1-thread figure, ~33x the Python step) |
| Python `step_explicit` | **8.84 us** |

- Thread ladder, same grid: 3.8 / 19.6 / 54.3 / 145.6 / 351.5 us per call at 1 / 2 / 4 / 8 / 12 threads. Monotonically worse with more threads; no crossover anywhere in the tested range.
- The Python step's own budget on the same grid: the two scipy matvecs `C@e` 2.46 us and `Ct@h` 2.53 us are **56 percent**, the remaining **44 percent** is numpy dispatch. So the compiled kernel at one thread (3.71 us) is **2.4x faster** than the interpreter path, and at the default team it is **33x slower** than it.
- The cgroup's own limit is `cpu.max` 50000/100000 = **0.5 CPU**, so a 12-thread team is contending for half a core; the ladder is a symptom of that as much as of the arithmetic.

**Recorded versus measured — do not quote the older ladder as current.** The ladder recorded in `docs/design/cpp-kernel-status-2026-11-09.md` section 5 and repeated in the E3 row of `EM_SOLVER_LEDGER.md` reads 1 thread 5,926 ns, 2 threads 49,252, 4 threads 124,111, 8 threads 353,937, over 98/133 iterations with 392 nonzeros. The **shape** reproduces exactly — monotone degradation with thread count — but the **magnitudes** do not: this container measures **145.6 us at 8 threads** against the recorded 353,937 ns (a factor of **2.43**), and 3.8 us at 1 thread against the recorded 5,926 ns. The conclusion (one thread is the only defensible configuration at this size) is robust to that discrepancy; the individual timings are not, and no ladder number may be carried forward from either document without re-measuring it here.

**Candidate causes** — (i) one OpenMP region per row: the team is synchronised once per row for a few flops, so barrier latency is the whole cost; (ii) oversubscription against a 0.5 CPU quota, with spinning threads burning the quota they are waiting for; (iii) any parallel reduction reassociates the row sum, which would cost bit-parity with the Python path — an independent second reason not to enable it, and the trade the E3 row already names as the open decision.

**What closes it — done, not proposed.** Pin the thread count in the kernel entry point or the binding so a caller cannot inherit an ambient team; re-run the ladder with the pin in force and record it beside the machine's `cpu.max`; and state the thread count on every kernel figure from then on. The E3 performance gate must be written as a statement at target mesh size with the thread count pinned, never as a bare ratio.

**Gates:** `tests/test_cpp_parity.py` (13 tests, passing with the `.so` importable) pins numerics and neither pins nor measures thread count — nothing in the suite fails today if a caller passes an ambient 12-thread team, which is part of what this entry is about. This entry does not move E3, which stays UNVERIFIED.


## DR-43 — the writer publishes a station-span amplitude ratio as |S21|, and the passivity gate sums it against |S11| as if the two were one measurement

- **id:** DR-43
- **title:** With `s21_plane` unnamed — the DEFAULT — `emfit/studies.py` has no single-plane transmission to report and falls back to a raw forward-amplitude ratio across the station span. The writer published that ratio as `s21.magnitude` without recording which estimator produced it, and the passivity gate summed it against |S11|² as a coherent pair, producing |S11|²+|S21|² ≈ 1.15 and `FAIL_PASSIVITY` on a fixture that is passive by construction.
- **status:** FIXED-TESTED — the writer now publishes |S21| only when an estimator names the plane it was taken on (`s21_provenance` is the licence), writes the eight `s21` numeric keys as null with an unchanged key set when it does not, and the gate reports `NOT_ASSESSABLE` with a null `power_sum` instead of summing a ratio (`emfit/studies.py`, `evidence/termination/run_build_A.py`, `evidence/termination/grade_2b.py`, `tests/test_writer_station_phasors.py`).
- **severity:** HIGH — it produced a *wrong verdict*, not just a wrong number: a passive 50 Ω series termination was reported non-passive, and the same estimator on the diode arm reported "passive, ok" for a record whose |S21| was equally untrustworthy. It fired on every run that did not name a plane, i.e. on the default path.
- **opened:** 2026-11-12 (this entry)

**What is wrong.** `emfit/studies.py` reaches `s21` through three branches with three different meanings, and before this entry it published whichever one ran under one name. (a) The cut branch, `emfit/studies.py:4109-4120`: with `s21_plane` named (`--s21-plane-index`/`--s21-plane-col`, or the CW default policy's `S21_PLANE="cut"`) it splits the field into travelling waves on the element's own cross-section and de-embeds port→cut — against the twin's forward ratio when a `reference` is supplied (`:4111-4112`), on the run's own `beta` when it is not (`:4113-4114`) — so it is a transmission referred to a plane. It is the only branch that writes `s21_provenance` (`cut_plane@…`, `:4119`), and so the only one this entry lets publish. (b) The ratio of ratios, `:4121-4136`: taken instead when a `reference` is supplied and `s21_plane` is **None**, it divides the run's own forward-amplitude ratio across the station span by the twin's on the same two planes, which cancels the line's delay and impedance and leaves what the load did — the estimator behind the 0.549464 quoted for the 100 Ω series load at `tests/test_studies.py:954`. It writes no `s21_provenance`, so this entry withholds that number too: coarser than the branch deserves, since it is a real transmission between the two station planes and lacks a name rather than a meaning, but no banked artefact carries it (every driver artefact names the cut plane, `S21_PLANE="cut"`). With `s21_plane` **None** — the default for every pulse run — the cut branch never runs: (b) runs when a `reference` was supplied, and the fallback below when none was. (c) That fallback, `:4137-4153`, is `forward_wave_amplitude[-1]/forward_wave_amplitude[0]` over the station span that *ends in the load*. That ratio carries the load's absorption plus the line loss between two probes; it is de-embedded by `line_s21` at the run's own `beta` and is **not** referenced to any plane, so it is not an S21. The writer published it as `s21.magnitude` all the same, with nothing in the record saying which of the three branches wrote the file, and `passivity_guard` then summed |S11|² + |S21|² as though both came from the same cross-section. Two different estimators were added together as if they were one measurement, and the sum crossed 1 + 4e-9.

**Evidence** — arm A (microstrip, 50 Ω `series_r` at 20.0 mm, one mesh, cell 0.4 mm), six solves from `artifacts/passivity_sweep_A2.json`:

| nsteps | excite | `s21_plane` | \|S11\| | \|S21\| | `power_sum` | status |
|---|---|---|---|---|---|---|
| 2400 | pulse | none | 0.327238 | **1.021737** | **1.151030784** | FAIL |
| 2400 | cw | none | 0.325863 | 1.020459 | 1.147522965 | FAIL |
| 1200 | pulse | none | 0.327700 | 1.010565 | 1.128628182 | FAIL |
| 4800 | pulse | none | 0.327219 | 1.021712 | 1.150968772 | FAIL |
| 9600 | pulse | none | 0.327219 | 1.021712 | 1.150968768 | FAIL |
| 2400 | cw | 51 | 0.325863 | **0.761705** | **0.686382016** | ok |

Everything below is measured, and each line is a reading a later reader needs:

- **The number is a property of the geometry, not of the time window.** Rows 1–5 agree within 0.02 and rows 4 and 5 agree to **4e-9** in `power_sum` (1.150968772 vs 1.150968768) across a 2x step count.
- **The excitation is not the cause.** Row 2 is CW and reproduces the violation to **99.7%** of row 1's.
- **The extraction plane moves the number; nothing else does.** Row 6 is the SAME 2400-step CW run as row 2 with a plane named: `|S11|` is identical to six digits (0.325863) while `|S21|` falls from 1.020459 to 0.761705 and `power_sum` from 1.147523 to 0.686382. A one-flag change from FAIL to `ok` on a passive fixture is a defect in the number, not in the fixture.
- **Geometry, stated once so it is not re-derived wrongly.** Arm A's probe span is **9.6 mm** — `artifacts/passivity_sweep_A2.json` → `runs[*].station_x_mm` = [10.4 … 20.0] mm, 9 stations, 1.2 mm pitch — for a load of **series_r 50 Ω at 20.0 mm** (`evidence/termination/build_A_50ohm.json` → `run.kwargs.loads[0]`, `position_m` 0.02) and a cut plane of **20.4 mm** (`geometry.cell_m` 0.0004 × `geometry.s21_plane_index` 51, corroborated by `s21.planes_m` = [0.0032, 0.0204]), whose provenance string is `cut_plane@20.400mm` (`emfit/studies.py:4119`). **Two numbers that look like geometry on that same artefact are NOT geometry and must not be quoted as such:** `geometry.station_fit_span_m` = 0.0084 is the *impedance-fit window* (8 stations, 10.4–18.8 mm, taken after the load station at 20.0 mm is dropped), and `s21.deembed_distance_m` = 0.0072 is the *port→first-station de-embed distance* (10.4 − 3.2 mm). Neither is the S21 span and neither is a plane position.
- Arm E is a **different configuration**, not the same fixture: load at 30.0 mm, `s21_plane` named `cut`, plane index 75 → 30.0 mm, `|S21|` 1.013186295836005 (`evidence/termination/build_E_50ohm.json`). No figure on this page should be carried between the two arms.

**Candidate causes refuted** — each with the measurement that refuted it:

- **Truncation / reflected energy still in flight.** Rows 4 and 5 agree to 4e-9 across a doubled step count, and the load-trace tail energy at 4800 steps is **7e-16 of the total**. There is nothing left to arrive.
- **Split-impedance bias (`zc` wrong, so the two travelling waves are wrongly separated).** Re-splitting the SAME record under four impedance choices gives `zc_published` 47.150633+1.746455j → **1.021737**, against 50+0j → 1.023621, `power_z0` 40.085 → 1.049814, and 0j → 1.196544. The published figure is already the **best** of the four; no admissible `zc` brings it to the cut-plane value.
- **Pulse bandwidth / the analysed tone sitting outside the excited band.** CW reproduces the ratio (row 2), and the analysed tone 6.0099 GHz sits **8.59 dB below** the drive peak, inside the reported 2–12 GHz band. The fallback is wrong on a single tone as well.

**Consequence.** The gate's verdict was made of one honest term and one polluted term, so its verdict was a property of whichever happened to dominate. On the diode arm `|S21|` = 0.93472 read **"passive, ok"** for exactly that reason — it was cleared only because `|S11|` = 0.146 there, not because the |S21| meant anything. **Any claim resting on that arm's S-parameters is void**; its rectification result is unaffected, because that rests on load V(t)/I(t) and never on the S21 ratio. The general lesson is recorded in the entry rather than in a comment: a gate that sums two numbers must be able to say which estimator produced each, or it is summing a measurement and a residual.

**What closes it — done, not proposed.** (a) The cut branch sets `s21_provenance = f"cut_plane@{x_cut*1e3:.3f}mm"` and clears `s21_unmeasured_reason` only when a finite number actually came out of it; every fallback branch leaves both untouched (`emfit/studies.py:4047-4048`, `:4119-4120`, and the span-fallback comment at `:4144-4151`). (b) `SPAN_S21_UNMEASURED` states the refusal in words, naming the fallback and its measured cost (1.02 on a span whose cut plane gives 0.76), and says why a silent skip would not be acceptable (`emfit/studies.py:129`). (c) The writer decides before it publishes: `s21_measurement` → `published_s21_magnitude` → `passivity_record` → `published_s21_block` (`evidence/termination/run_build_A.py:2216-2314`), the last of which writes all eight numeric keys as `None` rather than dropping them, so the key set is identical on every record and neither artefact writer (loaded and twin) can disagree about what a published S21 is. (d) The gate returns `PASSIVITY_NOT_ASSESSABLE` with a null `power_sum` and a `basis` that says no sum is quoted, distinct from `passive` (null) and from `FAIL_PASSIVITY`; the console prints `passivity=NOT_ASSESSABLE(no single-plane |S21|)` and `|s21|=unmeasured(...)` rather than a number. (e) `grade_2b.py` treats a null `s21.*` as a **warning** when `s21.measured is False` and as a **problem** otherwise, and `grade_ac7` grades such a file unscored rather than achieved. (f) `PASSIVITY_TOL` stays **4.0e-9**; nothing is clipped, rescaled or special-cased, and no magnitude is manufactured to make a fixture pass. (g) `tests/test_writer_station_phasors.py` pins each guard by the one test that fails without it. Measured on 2026-11-12 by disabling the guard, re-running the file, and restoring it byte-for-byte (sha256 unchanged): disabling `published_s21_magnitude`'s `if not decision["measured"]: return None` (`evidence/termination/run_build_A.py:2251`) fails `test_a_station_span_ratio_is_never_published_as_s21` at `tests/test_writer_station_phasors.py:289` with `AssertionError: assert 1.021737 is None`; disabling `passivity_record`'s `PASSIVITY_NOT_ASSESSABLE` branch (`:2264`) fails `test_an_unmeasured_s21_makes_passivity_not_assessable_not_ok` at `:306` with `AssertionError: assert None == 'NOT_ASSESSABLE'`. Each revert fails exactly 1 of the file's 13 tests (`1 failed, 12 passed` both times), and the file is `13 passed` with both guards in place. The other two named tests, `test_a_cut_plane_s21_is_published_and_summed_unclipped` and `test_a_passing_record_keeps_a_null_status_and_the_guard_key_set`, pin the *published* path rather than the refusal and pass under either revert — they are not revert-detectors for the guards above.

**Known gap — open, not closed by this entry.** Artefacts written before this change (`evidence/termination/build_A_50ohm.json`, `build_E_50ohm.json`, `build_B_100ohm.json`) carry **no** `s21.measured` / `s21.provenance` key at all, so "key absent because the file predates the schema" and "key null because the record legitimately has no published |S21|" are currently indistinguishable to every reader that tests for null — including `grade_2b.py`, where the absent case is downgraded to a warning and `grade_ac7` returns unscored. The three files above are exactly the ones the termination grading reads. This is recorded, not repaired: the honest fix is a schema/version key, not a guess about which nulls are old.

**Gates:** any `|S21|` quoted from a record whose `s21.provenance` is `None` — that number is a station-span ratio, not a transmission; any `s21.magnitude` written beside a null `provenance`; any passivity verdict computed from two magnitudes without the estimator named for each; any edit that makes the fallback branch publish again, or that clips/rescales a magnitude to bring a sum under `1 + 4e-9`; and any reading of a pre-DR-43 artefact that treats a *missing* `s21.measured` key as a measured null.

**AMENDMENT 2026-11-12 (the pulse path is verified by run but not yet pinned by a test; status stays FIXED-TESTED; DR-43 stays as recorded).** This is DR-43's first amendment block, and the register's fourth amendment overall (DR-42 holds the first three at `:791`, `:793`, `:799`). It adds evidence, not a repair: nothing in `emfit/studies.py`, `evidence/termination/run_build_A.py` or `grade_2b.py` changed to write it, and the `- **status:**` line at `:828` is untouched. **What was run.** A fresh pulse solve at the tree state `984742f` — the tree's HEAD when the run was made, an attribution no file in this container records — using exactly the argv the record kept: `evidence/termination/run_build_A.py --structure C --nsteps 2400 --out /tmp/dr43_fresh_pulse.json --vis-dump /tmp/dr43_vis_C_stub.npz`. The record it left is 24,415 B and reads back `meta.status` `ok`, `meta.step_engine` `cpp`, `meta.kernel_name` `emfit_core.fit_leapfrog`, `meta.kernel_abi` 1, `meta.peak_rss_mb` 378.4375 against `meta.cgroup_limit_mb` 2048.0 and `meta.trip_clause.mem_ceiling_mb` 2000.0, `meta.python` 3.12.15, `meta.git_rev` `null`, and `meta.started_utc` 2026-11-12T22:47:10+00:00 → `meta.finished_utc` 2026-11-12T22:48:01+00:00, i.e. **50.6 s** wall elapsed (≈51 s at the record's one-second resolution). **What it shows.** The refusal holds on the live default path, not only under the two reverts measured at `:861`: `s21` carries 22 keys — the 19 the pre-fix schema wrote plus `measured`, `provenance` and `unmeasured_reason` — with `magnitude` `null`, `measured` `false`, `provenance` `null`, and an `unmeasured_reason` that names `emfit/studies.py:4137-4153` as the station-span fallback it declined to publish; `s11.validation_status` is `NOT_ASSESSABLE` and `s11.passivity` reports `status` `NOT_ASSESSABLE` with `power_sum` `null` at `tolerance` 4e-09. There is no top-level `power_sum` key on the record at all: the null lives at `s11.passivity.power_sum`. The failure mode of row 1 of the table at `:838` — `|S21|` **1.021737** published from the span ratio, summed to 1.151030784 — is therefore no longer reachable on the default path. **What it does not do.** This is EVIDENCE, not a GATE. No test in the tree yet executes the pulse writer end to end, so a regression that made the fallback publish again would still be caught only by the unit-level reverts pinned at `:861`, and the entry stands FIXED-TESTED on that file's authority rather than on this run's. VERIFIED-BY-RUN is not FIXED-TESTED; it becomes the latter on that path only when a test lands that fails without the guard — not when a run is read. The frozen pre-fix artefacts named at the gap above (`:863`) — `build_A_50ohm.json`, `build_E_50ohm.json`, `build_B_100ohm.json` — plus the 19-key records beside them still carry **no** `s21.measured` / `s21.provenance` / `s21.unmeasured_reason` key at all, and all of them were written before the repair recorded as `a69ed43` (`fix(solver): correct S21 extraction path (cut-plane for CW, unmeasured for pulse)`; the commit itself is unverifiable from this container, whose `.git` is empty). The gap at `:863` is not closed by this block, and the schema/version key that gap asks for is still the honest fix. Coverage: the pin test in `tests/test_dr43_pulse_writer.py` pins the default path end-to-end and passes (41.87 s), but it does not close the `:863` gap. FIXED-TESTED therefore means that no station-span ratio is published on any reachable code path; it does not mean the pre-fix artefacts are schema-current. This coverage sentence supersedes the clause "No test in the tree yet executes the pulse writer end to end" earlier in this paragraph, which was true when the block was written: the pin test landed afterwards, in `tests/test_dr43_pulse_writer.py`. Everything else in this paragraph stands as the record of the state at the time of the run.

## DR-44 — Untracked file overwrite during housekeeping: a 49,352-byte `GEN12_HANDOFF.md` was replaced rather than renamed

- **id:** DR-44
- **title:** Untracked file overwrite during housekeeping — an existing 49,352-byte untracked `docs/design/GEN12_HANDOFF.md` was replaced rather than renamed
- **status:** OPEN — unrecoverable content; the rule the entry exists to state is in force from here
- **severity:** MEDIUM — no measurement, figure or verdict was destroyed, and the file's substance was rewritten from the sources it cited; but 49,352 bytes of prose left no copy anywhere, and the loss is permanent, which is a kind of damage this record had no entry for
- **opened:** 2026-11-12 (this entry)

**What is wrong.** A write was instructed for `docs/design/GEN12_HANDOFF.md` at a moment when a file of that name already existed — 49,352 bytes, untracked — and the write replaced it in place. Nothing was renamed aside, nothing was copied, nothing asked whether the path was occupied. The write was instructed by the agent filing this entry; this is not a report of a tool doing something unexpected but of an instruction that did not look before it wrote. The existing file was a working draft of the same document, which is exactly the file most likely to be rewritten and least likely to be recoverable: it had never been committed, so the working tree held the only copy, and an overwrite is the whole of the loss. Because it never entered the object store there is no revision, no reflog entry and no stash from which its bytes can be read back; the content is unrecoverable, not merely misplaced.

**The rule, stated once because the case is general.** Before writing any path that already exists, read `git status` for that path. If the existing file is untracked, rename it or copy it aside first; only then write. A tracked file is protected by git — an overwrite that was never committed can be recovered from `HEAD`, and one that was can be recovered from the previous commit — so the tracked case costs a command and forgives the mistake. An untracked file is protected by nothing, and that asymmetry is why the check belongs on the untracked case specifically: the write that feels safe because the target is "just a document" is the one with no floor under it.

**Evidence.** (a) The destroyed file: `docs/design/GEN12_HANDOFF.md`, 49,352 bytes, untracked at the time of the write. (b) The orchestrator's verification, quoted and not re-run here: the artefact that replaced it is commit `bd2d9b9` ("docs(handoff): GEN12 onboarding package"), which carries the handoff package now in the tree, and the destroyed file is in no commit at all — no revision holds its 49,352 bytes. This session's git reads return hashes and subjects without dates or blob sizes and no shell is available, so the commit facts in this entry are the orchestrator's reading and are cited as such rather than re-measured. (c) What was lost is prose, not data: the destroyed draft restated the ledger rows, the register's open entries and the state file's inventory, all of which still exist in their own files, which is why the rewrite was possible and why the loss is bounded. What is not bounded is anything the draft said that its sources do not say — an untracked draft is where a session writes what it has not yet decided to record, and that layer is gone.

**Candidate causes.** (i) **The check was never made.** The write treated "the path exists" and "the path is mine to overwrite" as one question; nothing in the instruction distinguished them. (ii) **Untracked read as scratch.** An untracked file looks like a file nobody has claimed, when in this tree it is more often a file not yet committed — the newest thing present. The heuristic inverts the risk. (iii) **Nothing enforces the check.** The rule above is a habit, not a gate: no step between the instruction and the write demands a `git status` read, so it fails precisely when the session is busy, which is when multi-file housekeeping happens. (iv) **A repeated write to the same path within one session** — the first write creates the file, the second assumes the file is what the first one left — produces the same outcome with no moment at which a human would notice.

**What closes it — done, not proposed.** The bytes are gone; the closure available is the rule and the record, and both are here. In the same pass the document was rewritten from its sources — the ledger, this register, `GEN12_HANDOFF_STATE.md` — rather than reconstructed from memory, and it is committed with the package as `bd2d9b9`; the file standing at that path is the replacement the overwrite produced, and this entry names it as such rather than presenting it as the draft it displaced. Refused: no attempt to reconstruct the 49,352 bytes from quotation elsewhere in the tree, because nothing quotes them and a reconstruction would be a new document wearing the old one's name. Not done: no backup convention exists for the next session that rewrites a path it did not create.

**Gates:** any write to a path that already exists without a `git status` read on that path in the same turn; any write that replaces an untracked file instead of renaming or copying it aside first; any claim that a lost file "can be recovered from history" when it never entered the object store; any report of this incident that softens "the content is unrecoverable" into "was superseded"; and any housekeeping pass that rewrites several documents at once without checking, per path, whether what it is about to overwrite is tracked.

## DR-45 — Documentation dates ran ahead of the commit record: 2026-11-14 against a 2026-11-12 tree

- **id:** DR-45
- **title:** Documentation dates ran ahead of the commit record — documents carried 2026-11-14, two days ahead of a tree whose newest reachable commit is authored 2026-11-12
- **status:** OPEN — corrected in this record: the ledger's E3 `:28` and E5 `:30`, `session_open_gen11.md`:3, the six handoff-package lines that quote those rows, and one residual citation in DR-42's amendment at this register's `:791`; two carriers still read 2026-11-14 (`docs/design/visualizer_architecture.md`:7, `docs/design/lessons_learned_emfit_addendum.md`:28) and three more are left standing by decision — see Evidence
- **severity:** MEDIUM — no figure, verdict or status turns on a date, so nothing measured is at stake; but a date is the only chronology this record has, and while written dates and commit dates disagree no two documents can be ordered and every "as of HEAD" or "measured on" sentence loses its anchor
- **opened:** 2026-11-12 (this entry)

**What is wrong.** Documents written in the Gen 11 session were dated **2026-11-14**, and the tree they were written against carries no commit later than **2026-11-12**. A document cannot have been written two days after the last commit that could have produced it, so at most one of the two dates is true, and every reader who orders this record by its own dates orders it wrongly. The gap is **two days**, not one — the written date is 2026-11-14 against a 2026-11-12 record — which matters because a one-day gap invites the reading "the clock ticked past midnight mid-session", and that reading is excluded here. The defect is narrow and total at once: inside the ledger's E3 and E5 cells nothing was wrong except the day they claim to have been written — the retracted ladder, the 414-line / 11-test inventory, the gate coverage all stand as stated. This entry exists because the conflict had been on record as an unresolved finding and was never given an id: `reports/2026-11-12_19-19-03_GEN12_handoff_package___verification_and_correctio.md`:47 ("Documents dated 2026-11-14 (ledger E3/E5 rows, `session_open_gen11.md`) coexist with a HEAD authored 2026-11-12. Either commit dates are skewed or docs run ahead of commits."), and the CONFLICT table in `GEN12_HANDOFF_STATE.md` §1 built on it. An unresolved finding that lives only in a report is not tracked; it is remembered.

**Evidence — which direction, and why a reader can re-run it.** Two independent checks settle that the documents were early and the history is right, and they agree with a third record that never went through a document at all. (a) No commit in this repository is dated 2026-11-13 or later, so text dated 2026-11-14 cannot have existed at the time a 2026-11-12 commit was made; the fork the report names at `:47` — "either commit dates are skewed or docs run ahead of commits" — is answered, because a skew would have to have produced commits *later* than the documents, and no later-dated commit is reachable. (b) Commit `be803fd` made this same correction once already, re-dating DR-41 and DR-42 from 2026-11-14 to 2026-11-12 — so this pass is a repeat of a repair already accepted in this repository, not a new judgement about which side is wrong. (c) `artifacts/ladder_engine_scaling.json` independently records `assembled_utc` **2026-11-12T14:53:20Z**, and `GEN12_HANDOFF_STATE.md`:127 records the ledger artefact as "34,243 B, mtime 2026-11-12 14:53" — the measurement artefact and the file both carry the 2026-11-12 date, with no document in the path. (d) The past session's own report file is named `2026-11-12_19-19-03_GEN12_handoff_package___verification_and_correctio.md`: its filename timestamp was stamped by the machine at write time, not typed into prose, and it says 2026-11-12. The commit-date facts in (a) and (b) are not re-derived here: this session's git reads return hashes and subjects without dates and no shell is available, so those two figures are the orchestrator's verification, as `GEN12_HANDOFF_STATE.md`:45 records the same reading.

**Evidence — the carriers, with what became of each.** (i) Carried the date natively, corrected in the first pass: `docs/design/EM_SOLVER_LEDGER.md`:28 ("AMENDMENT 2026-11-14 (SUPERSEDES THE LADDER ABOVE — the verdict is unchanged)") and `:30` (four occurrences: the "AMENDMENT 2026-11-14 (INVENTORY CORRECTION" header, "Measured in this container on 2026-11-14:", "was written on 2026-11-14 as `docs/design/spice_adapter_scope.md`", and the "NOTE 2026-11-14" header); `docs/design/session_open_gen11.md`:3 ("Written 2026-11-14, at HEAD `3848d46`"). (ii) Quoted the ledger's date rather than carrying one, re-dated in the sweep that followed: `docs/design/GEN12_HANDOFF.md`:89, `docs/design/GEN12_HANDOFF_WARS.md`:183, `docs/design/GEN12_HANDOFF_STATE.md`:45, `:46`, `:47` and `:133`, and this register's `:791`. (iii) Still reading 2026-11-14, untouched: `docs/design/visualizer_architecture.md`:7 and `docs/design/lessons_learned_emfit_addendum.md`:28 — both outside the handoff package, and neither re-read against its own subject in this pass, so correcting them would be a guess about what each line dates. (iv) Left standing by decision, and the decision is part of the record: `.thoughtmachine/gen12_factsheet.md`:59 is scratch, `.thoughtmachine/knowledge/personal/lessons_learned.md`:556 is an agent notebook, and `reports/2026-11-12_19-19-03_GEN12_handoff_package___verification_and_correctio.md`:47 is the generated report of a past session — a historical record whose value is that it says what that session concluded at the time. Tidying a report so it agrees with later corrections destroys the only witness to the disagreement.

**Candidate causes.** (i) **Typed, not read from a clock.** The cheapest explanation is that the date was written by hand and typed forward, once, and that every other occurrence is a citation of that one string — `GEN12_HANDOFF.md`:89, `GEN12_HANDOFF_WARS.md`:183 and this register's `:791` all quoted "the 2026-11-14 amendment", which is copy-forward rather than four independent mistakes. This explanation fits every carrier. (ii) **A container clock ahead of the host.** The E5 row said "measured in this container on 2026-11-14", so a skewed container clock would date measurements honestly-to-it and dishonestly-to-the-repository. Against it: the skew would have to be exactly two days, persist across two sessions, and still would not explain `session_open_gen11.md`:3 or `visualizer_architecture.md`:7, which date themselves against a commit rather than a clock — and the report filename in Evidence (d) shows the machine clock reading 2026-11-12 at the time. (iii) **A rewrite moving one side and not the other.** A rebase, reset or amend moves commit dates and never moves the prose of a document; for the conflict to arise this way the documents would have had to be rewritten in place with a new date while the commits were left alone — the same act as (i) with a different motive. (iv) The general hazard this entry records: a date typed into prose is an unsourced claim that nothing checks, and it is checked only when a reader compares it to a git date, which happens when someone is already suspicious.

**What closes it — done, not proposed.** Done, and this is the whole of the change: the five disputed dates in the ledger (`:28` once, `:30` four times) and the one in `session_open_gen11.md`:3 were changed from 2026-11-14 to **2026-11-12**; each of those three places gained a correction sentence that states what the date read before, what it reads now, and the evidence by which the direction was settled — the missing later-dated commits, `be803fd`'s earlier identical correction, and the artefact's own `assembled_utc` — so a reader can re-run the argument rather than take the correction on trust; the six handoff-package lines that quote the amended rows were re-dated to name the row as it now reads; `GEN12_HANDOFF_STATE.md` §1's conflict table was rewritten from a statement that three documents disagree with HEAD into a record that the conflict was found, resolved, and on what evidence. One residual was repaired at this register's `:791`: DR-42's amendment header already read 2026-11-12, from `be803fd`'s earlier pass, while a sentence inside the same cell still cited "E3's 2026-11-14 amendment" — a leftover the earlier correction missed because it fixed headers and not the body text under them. It now reads "E3's 2026-11-12 amendment". No figure, no verdict and no status in either ledger cell was touched: the 414 lines and 11 tests, the 3.8/19.6/54.3/145.6/351.5 us ladder, the "50x slower" withdrawal and both UNVERIFIED verdicts read exactly as before, and only date strings and the appended correction sentences differ. Not done: the two carriers in Evidence (iii) still read 2026-11-14, and the entry stays OPEN on them.

**A finding worth keeping.** Correcting the ledger did not make the three documents that quote it right; it made them wrong. Before the correction they cited a date the ledger contained, and after it they cited a date the ledger no longer contained — the citation became stale in the act of repairing its source. The sweep in this pass is the repair of that second-order damage, and it is recorded rather than folded silently into the first: the sequence was correction, then disagreement, then sweep, and `GEN12_HANDOFF_STATE.md`:45-47 was rewritten rather than re-dated because its purpose is to record that the dates ever disagreed.

**Gates:** any date in a document that is later than the newest reachable commit date; any "as of HEAD" or "measured on" claim whose only warrant is a written date rather than an artefact hash or a machine-stamped filename; any correction that changes a figure, verdict or status while fixing a date — the correction is date strings plus a named note, nothing else; any citation of the ledger's amendment date in another document that has not been re-read against the ledger since the correction; any tidying of `reports/`, `.thoughtmachine/gen12_factsheet.md` or the agent notebook to make their dates agree with later corrections — those three are witnesses, not drafts; and any future pass that rewrites `GEN12_HANDOFF_STATE.md` §1 into flat agreement, which would erase the record that the two dates ever differed.

## DR-46 — gamma_plane written as bare NaN on the default path — a strict-JSON violation in a block that has no null convention

- **id:** DR-46
- **title:** gamma_plane written as bare NaN on the default path — a strict-JSON violation in a block that has no null convention
- **status:** OPEN — recorded, not repaired; this entry changes no code, artefact or test
- **severity:** MEDIUM/HIGH — justified by failure class rather than magnitude: bare `NaN` is not a JSON literal (RFC 8259 has none), so a strict parser does not get a null or a partial record from that file — it gets nothing at all
- **opened:** 2026-11-12 (this entry)

**What is wrong.** `evidence/termination/run_build_A.py:3896-3901` writes `gamma_plane.{re,im,abs,arg_deg}` unconditionally from `gp = complex(res.gamma_plane)` (assigned at `:3608`), so a non-finite `gamma_plane` is serialised as a bare `NaN` token. The same file contradicts itself about this: at `:2626-2630` the artefact-writing comment states gamma_plane "is left out rather than written as nan", while the code writes it, as nan.

**Evidence.** Six in-tree artefacts carry all four `gamma_plane` leaves as bare `NaN`: `build_A_50ohm.json`, `build_A_50ohm_nsub6_p76.json`, `build_A_n_default_p51.json`, `build_A_p51_n4800.json`, `build_A_p51_n9600.json`, `gate_gate_build_A_p51.json`. A fresh default-path run regenerated this session (`/tmp/dr43_fresh_pulse.json`) shows the same four leaves as bare `NaN`, so the writer is not a stale artefact of one campaign. AC-6 already knows the value is unusable — it sets `gamma_plane_recorded` False (`:2846-2849`) and `"pass": False` (`:2853-2856`) — and the writer emits it anyway.

**Cross-reference — the DR-43 gap at `:863`, quoted verbatim and not restated.** “**Known gap — open, not closed by this entry.** Artefacts written before this change (`evidence/termination/build_A_50ohm.json`, `build_E_50ohm.json`, `build_B_100ohm.json`) carry **no** `s21.measured` / `s21.provenance` key at all, so "key absent because the file predates the schema" and "key null because the record legitimately has no published |S21|" are currently indistinguishable to every reader that tests for null — including `grade_2b.py`, where the absent case is downgraded to a warning and `grade_ac7` returns unscored. The three files above are exactly the ones the termination grading reads. This is recorded, not repaired: the honest fix is a schema/version key, not a guess about which nulls are old.” The shape is the same and the remedy is the same: that gap is a key **absent**, which a null-testing reader cannot tell from a legitimate null; this one is a key **present and unreadable**, which no reader can tell from corruption.

**What closes it.** Nothing closed; this entry fixes nothing. It requires a decision on the convention (omit the block / emit `null` / keep `NaN` and declare the file non-strict) plus a schema-version key so a reader can tell which convention a file follows.

**Gates:** (1) a null-or-omission convention is chosen instead of bare `NaN`; (2) no reader may treat a bare-NaN record as strict JSON — every consumer either fails loudly or is fixed.

## DR-47 — the shared UI boot fixture never lets a state change fire, so no listener is exercised by the suite

- **id:** DR-47
- **title:** The shared `_boot_app` fixture never lets a state change fire — every `@state.change` listener in the application is outside the reach of the test suite
- **status:** OPEN — logged by the owner's instruction; deliberately not repaired in this pass
- **severity:** HIGH — justified by failure class, not by magnitude: the defect class it permits is a press that silently stops applying its result while forty-five UI tests stay green, which is a failure that has already occurred once in this series rather than a hypothetical one
- **opened:** 2026-11-13 (this entry)

**What is wrong.** The shared `_boot_app` fixture in `tests/test_poc_playback.py` replaces `server.start`, so `protocol.port_callback` never runs and `state.is_ready` stays false. Trame's `State.flush()` refuses to dispatch while the state is not ready, so **no `@state.change` listener registered anywhere in the application is ever executed by the suite**. Every listener the UI depends on is therefore untested by construction, however many assertions surround it.

**Evidence.** The workaround is visible in the tests that needed a listener to fire: `tests/test_poc_mode_picker.py` calls `srv.state.ready()` explicitly before triggering `mode_choice`, because without it the picker's listener never runs and the assertions would read untouched state. The structural alternative is what the playback suite settled for — `tests/test_poc_playback.py::test_solve_button_reloads_the_page` asserts that the string `_start_watch` occurs in the solve press's closure, which is a statement about source text rather than about behaviour. That assertion did catch a real regression in this series: an edit to the solve press deleted its `_start_watch()` call, so `_start_watch → _watch_solve → _poll_solve → apply_page` became unreachable and a solve would run and never apply its page. It was caught because someone had written a string test for that one call site, not because the suite can execute a listener.

**Candidate causes.** The fixture is shared and old, and calling `state.ready()` on every test would change the verdict of tests that currently pass precisely because nothing fires. Repair is therefore not a one-line fixture change: it is a re-baseline of the whole UI suite whose end state is unknown until it is run.

**What closes it.** `state.ready()` belongs in the shared fixture, with the listener registry driven afterwards; the change is a single commit whose body records the count of previously green tests that change verdict, and names each one and why. Until that is done, every listener in the application is verified only by explicit per-test `state.ready()` calls, and a listener with no such test carries no coverage at all.

**Gates:** (1) the shared fixture produces a state in which `flush()` dispatches, and the re-baseline count is recorded in the commit that does it; (2) at least one test per interactive control asserts its listener fired by an observable effect — a draw or a recomputation that can only have happened inside the listener — rather than by inspecting source text for a call.

## DR-48 — the cut label prints a cell centre that the drawn sheet is half a cell away from

- **id:** DR-48
- **title:** The cut label prints a cell centre that the drawn sheet is half a cell away from
- **status:** OPEN — recorded, not repaired; this entry changes no code, and the behaviour it names is held by a test marked `xfail(strict=True)` rather than left to prose
- **severity:** MEDIUM — justified by what the number is for: it is half a lattice cell (5 µm on the 0.01 mm decimated lattice, 50 µm on a 0.1 mm cell, 200 µm on the 0.4 mm cell of the reference build), far too small to move a picture, but the label is the coordinate an operator quotes back to the solver, and it names a plane the drawn sheet is not on
- **opened:** 2026-11-19 (this entry)

**What is wrong.** Two numbers describe the same cut and only one of them is where the sheet is. `_cut_layout` (`server/poc_app.py:9011-9024`) sets `off_mm = 0.5 * cell_mm if source == "volume" else 0.0` and returns `y_mm = j * cell_mm + off_mm`, `z_mm = k * cell_mm + off_mm`; `_cut_text` (`:9040-9047`) prints those `*_mm` fields, so the label reads `z = 0.0250 mm`. The sheets are an `extract_subset` of the |E| image at one `k`, so where a sheet lands is whatever `image.origin` the volume path gave the image. Undecimated, `:14017` sets `origin = (0.5 * cell_mm, 0.5 * cell_mm, 0.5 * cell_mm)` and the two numbers agree. Decimated — the boot banner's own words are `Volume Decimated ×4` — the decimated image keeps origin 0, so sheet `k` is drawn at `k * cell_mm` while the label still prints `k * cell_mm + 0.5 * cell_mm`. The half-cell offset is right in the case it was written for and silently wrong in the other, and nothing at `_cut_layout` says which case it assumed: `source == "volume"` is a claim about the grid, not about the image's origin.

**Evidence.** Measured on the live page, through the harness dump `volume.npz` (`cell_m = 1e-5` m = 0.01 mm, lattice `(4, 8, 6, 5)`, stride 3), at `k = 2` of `n_k = 5`: `tests/test_animation_volume.py::test_the_drawn_sheet_is_half_a_cell_from_the_labelled_coordinate` fails with `assert 0.019999999552965164 == 0.025 ± 1.0e-06` — the label prints the `_cut_layout` value `0.025` mm, and the sheet's own `bounds` put it at `0.019999999552965164` mm, which is `2 × 0.009999999776482582`, i.e. `k × cell` off the decimated image's zero origin. The gap is `0.005` mm, half a cell exactly. The test carries `@pytest.mark.xfail(strict=True)`, so the suite states the defect instead of hiding it: 25 collected, 24 passed, 1 xfailed. The day the two numbers agree it XPASSes, which is a failure, so the marker cannot be left behind by accident.

**Candidate causes.** `off_mm` was derived from the sample's MEANING (a cell centre) rather than from the image being cut, and it was verified on the undecimated path only; the decimated path was added afterwards and inherited an origin of 0 without anyone asking whether that was a decision or a default. This is also why no test caught it: the sheet's MOVEMENT is right in either convention (one cell per slider step either way, pinned by `test_dragging_the_cut_slider_moves_the_sheet`), so only a comparison of the label against the drawn bounds can see it, and until this session no test made that comparison.

**What closes it.** One convention, applied to both numbers. Either `off_mm` becomes a property of the image actually being cut — read `origin` off `info[VOLUME_ABS_KEY]["image"]` and use half the origin's own offset, 0 when it is 0 — or the decimated image is given `origin = (0.5 * cell_mm, ...)` too, which makes the existing offset right in both cases with one line. The second is the more defensible: a decimated |E| volume's samples are still cell CENTRES, they are the same cells every fourth one, so its origin should never have been 0 in the first place. Recorded, not repaired: this entry changes no code, and the undecimated path — the one that is right today — must be re-measured after any change rather than assumed.

**Gates:** (1) `test_the_drawn_sheet_is_half_a_cell_from_the_labelled_coordinate` XPASSes and its `xfail` marker is deleted in the same commit that fixes the offset; (2) the fix names the convention in a comment at `_cut_layout`'s `off_mm` — where the offset is read from, and the rejected alternative — instead of leaving `source == "volume"` to imply it; (3) the label and the drawn sheet are compared at more than one `k`, because a constant error and a per-step error are indistinguishable at a single cut.

## DR-49 — tooth F is a proposed proof with no citation, and it is recorded here rather than relied on

- **id:** DR-49
- **title:** Tooth F is a proposed proof with no citation, and it is recorded here rather than relied on
- **status:** OPEN — `[UNCITED]` / `[proposed]`; recorded by the owner's instruction so that it is neither blocked nor forgotten
- **severity:** LOW — justified by failure class rather than magnitude: a tooth with no citation cannot break anything, because nothing may depend on it. The cost is the opposite kind — an obligation that reads as proven while nothing stands behind it — which is exactly why the owner asked for it to sit here instead of in a chat log
- **opened:** 2026-11-19 (this entry)

**What is wrong.** A proof obligation labelled F was proposed in this series and never carried a citation. In this repository a tooth means one thing: a mutation that makes a named test fail. Without the mutation and the observed failure there is no tooth, only an intention, and an intention recorded as though it were a proof is worse than an intention recorded as an intention. F is in that state, and this entry is the honest status of it.

**Evidence — the search, and its negative result.** `grep -rni` over the whole repository (excluding `.git`, `.venv`, `__pycache__`, `node_modules`) for `\btooth[ _-]?f\b`, and a second fixed-string pass over the spellings `tooth F`, `Tooth F`, `TOOTH F`, `tooth_f`, `Tooth_f`, `TOOTH_F`: **zero hits.** No document, log, test or report in this tree names a tooth F. Every occurrence of "tooth" or "teeth" here is the colloquial engineering sense or the name of a mutation rig — `probes/P2_LOG.md`, `probes/P2c_LOG.md`, `probes/cut_planes_p1_log.md`, `probes/p2c_teeth/`, `probes/verify_reader_teeth.py` — and the enumerations in them name no F: `probes/P2_LOG.md:35-38` records `if state.show_other_family:` → `if False:` as 1 failed, 4 passed, and `entry["family"] in _visible_families(mode)` → `entry["family"] == mode` as 2 failed, 3 passed. So F cannot be reconstructed from the tree at all; it exists only in the conversation that proposed it, and a conversation is not a citation. For contrast, and without overclaiming on its behalf: the four tests committed in `37b5374` for the |E| layer (the cut sheets move one cell per slider step, the page's own policy switches the layer on, the switch speaking OFF drops it, and the half-cell gap above) are BEHAVIOURAL only — no mutation run stands behind them either, and this entry does not pretend otherwise. What makes them worth having is that each one can be broken in a stated way; what F needs before it can join them is the same statement.

**What closes it.** One of two things, and neither is "remember harder". Either F is restated in a single sentence naming the mutation, the test expected to break, and the run in which it broke — at which point it is a tooth and the sentence belongs in the log of the step it was earned in — or it is withdrawn by the owner. Until one of those happens it stays `[UNCITED]` / `[proposed]`, and no artefact, gate, commit message or claim in this repository may cite it as evidence.

**Gates:** (1) an F entry exists only in the form the other teeth of this series were recorded — mutation, expected failure, observed failure, quoted (`probes/P2_LOG.md:35-38`); (2) anything outside this entry that cites F is deleted until then, because a citation of an uncited proof propagates the defect it was meant to prevent.

## DR-50 — the memory estimate is anchored on one measurement and extrapolates linearly

- **id:** DR-50
- **title:** The pre-flight estimate is a linear extrapolation from a single 280,984-cell anchor
- **status:** OPEN — recorded, not repaired; this entry changes no code, and the estimate and the 12,000 MB constant are described here as they behave today
- **severity:** HIGH — justified by what the check is FOR rather than by a wrong number: it exists to refuse a run that would be killed, and at the one size that actually killed the host it returns a PASS
- **opened:** 2026-11-19 (this entry)

**What is wrong.** The pre-flight that decides whether a run may start prices the mesh linearly in edge and face counts, anchored on one measured run at 280,984 cells. Its error at the scale that actually killed the host is unknown, and the direction of that unknown is under-prediction: an 18.7 M-cell mesh prices at 9,979.4 MB, which passes a 12,000 MB limit, yet the host was killed at 15,673 MB. It only refuses above roughly 29 M cells (about `--n-line 5000`). Stated plainly: the gate can PASS a run of the size that may have killed the host. That is a known limit of the check as delivered, not an oversight discovered afterwards — the model was built from one anchor and its behaviour above that anchor was never measured.

**Evidence.** Measured numbers, all from this session: 62x212x22 = 289,168 cells -> 303.2 MB; 62x206x22 = 280,984 cells -> 298.9 MB against a recorded peak RSS of **297.82 MB** (`evidence/termination/run_build_A.py:2064-2066`, `evidence/termination/build_A_50ohm.json`) = **+0.4 %**; `--n-line 1200` -> **3,113.4 MB**; `--n-line 4000` (18.7 M cells) -> **9,979.4 MB**. The model is linear by construction: `_solve_estimate_mb` (`evidence/termination/run_build_A.py:1057-1094`) sums `MEM_EDGE_ARRAYS * n_edges + MEM_FACE_ARRAYS * n_faces` at 8 B, 3 masks per edge, and a 4-entry / 12-B CSR curl, then adds a **FIXED** 150 MB residual — so no mechanism in it can represent superlinear growth; every term is a count times a constant. Corroboration that the model is shape-sensitive but scale-linear: two meshes with identical cell counts (4x5x6 and 3x8x5, 120 cells each) price differently, and the per-cell price falls with size. Note also that the 12,000 MB constant (`MEM_SAFE_LIMIT_MB = 12000.0`, `evidence/termination/run_build_A.py:584`) was chosen as a figure below the host's 15,673 MB kill, not derived from a mesh.

**Candidate causes.** (a) the real cost IS superlinear in cells — solver workspace, CSR scratch and transient copies inside `emfit.studies` — and a linear model cannot see it; (b) `MEM_SAFE_LIMIT_MB = 12000.0` (`:584`) was picked as a round number under the kill, without measuring which mesh produces 12 GB; (c) the 150 MB residual is itself a measurement at 281k cells and may grow with the import-time and workspace footprint at larger meshes.

**What closes it.** One measured peak RSS at a substantially larger mesh — `--n-line 600` or more — giving the model a **SECOND anchor**, so it becomes a fit through two measurements instead of an extrapolation from one, and then re-deriving the constant or making the model piecewise. Explicitly rejected, and the reason: multiplying the estimate by a fudge factor to make it refuse sooner. That is tuning, not estimating; it would make the prediction that is currently +0.4 % right at 281k cells wrong by the same factor, and it would hide (a) rather than settle it.

**Gates:** the seven tests in `tests/test_preflight_memory.py` hold this model — the anchor assertion keeps 62x206x22 above 297.82 MB, the limit test pins `min()`, the AST tests pin the two-line refusal and its position above the dry-run return. Those seven pin the SHAPE of the model and must not be cited as evidence that the estimate is accurate at 15 GB, because none of them measures a large mesh.

## DR-51 — a default shipped for one machine refuses every run on a smaller one

- **id:** DR-51
- **title:** The default `--mem-ceiling-mb` is above the container limit, so non-dry-run CLI invocations are refused before they start
- **status:** OPEN — recorded, not repaired; the guard is left as it is, and its consequence is held by a `skip` that names this entry rather than by lowering the ceiling to fit the box
- **severity:** MEDIUM — justified by failure class rather than magnitude: no wrong number is produced and the refusal is loud (rc 2, a message naming both numbers), but a non-dry-run invocation cannot start at all on any container under 2 GB, and the message instructs the operator to correct a value they never set
- **opened:** 2026-11-19 (this entry)

**What is wrong.** In any container whose memory limit is below `MEM_CEILING_MB_DEFAULT` (**2000.0**, `evidence/termination/run_build_A.py:129`), every non-dry-run invocation is refused before it starts, by the trip-vs-container guard at `evidence/termination/run_build_A.py:3766-3772`. That guard sits BELOW the `--dry-run` early return (`:3764`), so it only ever bites a test or a user who actually intends to solve. The refusal message tells the operator to pass a lower `--mem-ceiling-mb`, but the operator never set 2000 — it is the default shipped for the owner's 16 GB host. So the default is unusable anywhere else, and the condition is reported as a failed RUN rather than as a configuration warning.

**Evidence.** `tests/test_dr43_pulse_writer.py` was red in this workspace for this reason and no other: stderr `REFUSED: --mem-ceiling-mb 2000.0 MB is above the container limit 512.0 MB, so the trip could never fire before the container is killed. Pass --mem-ceiling-mb below 512.0 MB.`, rc 2, no timestep taken. The guard predates this session's memory pre-flight: the byte-identical block exists in `.scratch/zeff_before/run_build_A.py` dated 2026-11-03, which contains no `MEM_SAFE_LIMIT_MB`, no `_memory_preflight` and no `MEM: estimated footprint` at all (grep returns nothing for all three). The pre-flight is NOT implicated: on that same argv `_memory_preflight` returns 0 with empty stderr. The red went unnoticed because every other CLI test in the tree passes `--dry-run` and stops above the guard.

**Candidate causes.** The guard was written to catch an operator who typed a ceiling above the container. It cannot distinguish a ceiling the operator WROTE from one the file DEFAULTED to, and the default was never revisited when the same script started running inside containers.

**What closes it.** Either (a) treat a non-explicit ceiling differently from an explicit one: when `--mem-ceiling-mb` was not passed, use `min(default, container limit minus a margin)`, print one line saying the ceiling was clamped and why, and reserve the refusal for a value the operator actually stated; or (b) keep refusing, and have the message say the DEFAULT is at fault rather than instructing the operator to correct a number they never chose. (a) changes the semantics of the memory guard that the owner ruled on in this session — it decides when a run may start — so it needs the owner's decision and must not be settled by a worker.

**Gates:** `tests/test_dr43_pulse_writer.py` now skips, quoting this container's measured limit and naming `:3766`, with a comment naming the rejected alternative (lowering `--mem-ceiling-mb` to fit the box, which would assert that a 2400-step 3-D solve survives a trip a few hundred MB above its own footprint — one environment-dependent red traded for a flaky one). The skip is the RECORD of this defect, not a fix: if (a) lands, that skip must be deleted, not left to accrete.

## DR-52 — the reference-sim config document carries a load and a wall ceiling, and its reader drops both

- **id:** DR-52
- **title:** The `CONFIG_DRIVEN` table in `scripts/run_reference_sim.py` forwards neither `wall_limit_s` nor `load_ohm`, so a document that names a load validates and then runs without it
- **status:** OPEN — the UI path forwards both; the scripted path does not
- **severity:** MEDIUM — justified by the runtime consequence rather than by magnitude: a dropped `load_ohm` does not refuse, it re-terminates arm A at the solver's 50 ohm, which is a physics change nobody is told about and worse than a refusal; but it is confined to the scripted path, whose in-tree code callers number two (`tests/test_run_config.py` and a scratch copy of it under `probes/p3_scratch/`), the documented hand command being the third route
- **opened:** 2026-11-19 (this entry)

**What is wrong.** The document has two fields its consumer cannot deliver. `RunConfig` gained `wall_limit_s` (`emfit/config.py:162`) and `load_ohm` (`:168`), `server/poc_app.py`'s form forwards both (`:14679-14682`), and `scripts/run_reference_sim.py`'s `CONFIG_DRIVEN` (`:209-220`) lists ten field names and neither of them. `apply_config` (`:236-240`) only walks that table, so neither name is ever copied onto the namespace; `reference_argv` (`:253-286`) therefore never emits `--load-ohm` or `--wall-limit-s`; and the script's own parser (`:499-595`, thirteen arguments) has no such flags either, so there is no route by which a document's value can reach the solve. A JSON that names a load is validated, priced, and run without it.

**Evidence.** Run against the reader itself. A document carrying `"load_ohm": 75.0, "wall_limit_s": 300.0, "nsteps": 100` is accepted by `load_config` → `RunConfig.from_json_file` (`scripts/run_reference_sim.py:181-202`); after `apply_config` the namespace has neither attribute (`hasattr` False for both), and `reference_argv` returns `['--structure', 'A', '--nsteps', '100', '--vis-dump', ..., '--n-line', '54', '--xcut-near-mm', '20.4', '--xcut-far-mm', '22.0']` — no `--load-ohm`, no `--wall-limit-s`. A full `--dry-run` of that document exits 0, writes nothing to stderr, and prints the headline `PLAN - the reference simulation (arm A, 50 ohm series_r at p2)` (`:383-386`): it states 50 ohm while the file says 75. What gets lost is decided by the reference, not by this script — `run_build_A.py:3593-3594` is `if args.load_ohm is None: args.load_ohm = STRUCTURES[structure]["load_ohm"]`, and A's entry is `"load_ohm": LOAD_VALUE_OHM` (`:692`) = `50.0` (`:137`); the ceiling falls back to `WALL_LIMIT_S_DEFAULT = 1400.0` (`:128`), so a document's 300 s is lost the same way. The gap is admitted at the field itself: `emfit/config.py:166-167` — "`scripts/run_reference_sim.py`'s CONFIG_DRIVEN table (:205-220) does not forward this field yet; `server/poc_app.py` does." (that comment's range is stale besides — the table is `:209-220`). Both fields arrived in `437b5a0`, the commit that added them to `emfit/config.py` and `server/poc_app.py`; `scripts/run_reference_sim.py` is not in it.

**Candidate causes.** The fields were added for the UI's press, and the press builds its argv in `server/poc_app.py:_run_config_argv` (`:14630-14683`), not here — so the commit rewrote the builder that needed the fields and left this reader alone with a comment in its place. Nothing failed, because the table is a hand-written mapping with no drift test: `tests/test_run_config.py:186` is named `test_every_config_field_reaches_the_reference_argv`, but its body is eleven literal `flag_value` assertions (`:195-206`) over `VARIANT` (`:77-86`), and neither `VARIANT` nor the assertions name either new field. The name promises a coverage test the body does not perform: `grep -rn 'CONFIG_DRIVEN' --include=*.py .` returns four hits — `scripts/run_reference_sim.py:209`, `:224`, `:236` and the comment at `emfit/config.py:166` — and not one of them is a test.

**What closes it.** Forward both fields in the table, on the rule the form already follows (`server/poc_app.py:14679-14682`): the wall ceiling always, because `RunConfig`'s 1400.0 default IS the reference's own `WALL_LIMIT_S_DEFAULT`, and a load only when the document names one, because `None` is the ARM's termination and a 50 sent for a B press would itself be a silent re-termination. Then make the drift test real: iterate `dataclasses.fields(RunConfig)` and require every name to be a key of `CONFIG_DRIVEN` or to sit on an explicit, documented exclusion list (`schema_version` is excluded as the document's version, not a run number; with both fields forwarded it is the only name left over), so the next field added to `RunConfig` cannot be dropped by this table in silence. `_namespace` in that test (`:175-183`) spells the flags by hand and needs the two names added in the same commit, or `apply_config`'s `getattr` raises `AttributeError`.

**Gates:** (1) the drift test above — it fails today on `wall_limit_s` and `load_ohm`, and it is the gate that would have caught `437b5a0`; (2) running the scripted reference path itself with a document that names both, which is what this entry's Evidence is and what no test does — every test in `tests/test_run_config.py` passes `--dry-run`, and none of them names either field.
