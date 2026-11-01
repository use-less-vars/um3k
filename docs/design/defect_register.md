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
The **5 deg** figure is **PROPOSED and NOT ratified**: the owner pre-registered only the magnitude
criteria, and this phase companion is registered here because a magnitude cannot see a rotation. It must
not be adopted until the second-twin run is shown able to meet it — a criterion that cannot pass on
legitimate input is a prohibition, not a safety check, and that is the defect this entry documents.
Neither number is measured by anything yet; the second twin is what would measure them.

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

**Gates:** **nothing currently moves.** No artefact carries a twin reference — `--with-twin` has produced
exactly one file (`build_smoke_50ohm_twin.json`) and its loaded counterpart does not exist — so every graded
number rests on the `reference=None` path with `zc_split = zc` and `loaded_without_reference = True`, and
this entry **changes** no graded number: the re-grade in (v) is what shows that, its output coming back
identical at every JSON leaf. AC-3b is registered in (iii) above and is graded by **nothing**. What
does bind is wording: a graded `s21` must name the assumption it stands on, and an untested transport
must not be presented as a measured normalisation — the near miss is what happens when it is.

---

## DR-15 — RESERVED, not opened

**DR-15 is reserved and carries no entry.** It is held for the seam check on the unloaded-twin
build: `line.beta` across runs A / E / B must agree to **< 1 %** on identical geometry (same mesh,
same cross-section, differing only in the load), and if it does not, the twin fix carries a defect
of its own and that defect is DR-15. The check has not been run; this line only reserves the number
and states what it is for. It must not be cited as an open defect.
