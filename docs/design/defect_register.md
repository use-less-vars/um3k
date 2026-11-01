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

## DR-15 — RESERVED, not opened

**DR-15 is reserved and carries no entry.** It is held for the seam check on the unloaded-twin
build: `line.beta` across runs A / E / B must agree to **< 1 %** on identical geometry (same mesh,
same cross-section, differing only in the load), and if it does not, the twin fix carries a defect
of its own and that defect is DR-15. The check has not been run; this line only reserves the number
and states what it is for. It must not be cited as an open defect.
