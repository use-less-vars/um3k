# E11 — The residual against the independent Z0: preregistration

**Status:** PREREGISTERED (no results yet). Closes when exit criteria met.
**Date:** 2026-11-09
**Author:** Gen 10
**Supersedes:** none. Complement to E1 (open for the residual) and E10
(independent Z0 verified at 48.02374054929774 for w=3.2 mm).
**Refs:** DR-36 (quasistatic Z0 box-limited), DR-37 (w=3.2 rerun at
48.023741), DR-39 (pytest config defects).

## 1. The question

Given the retraction of the circular 0.34465 anchor (E1) and the verification
of an independent quasistatic anchor Z0 = 48.02374054929774 ohm for the
w = 3.2 mm build_A geometry (E10, `evidence/quasistatic_z0_ladder_w3.2mm.json:91`
and `:191`, DR-37 at `docs/design/defect_register.md:643,648,653,661`), the
anchor value is:

    Gamma_anchor = 50 / (50 + 2 * 48.02374054929774) = 0.3423544

Five residuals against this anchor:

| estimator | file:line | S11 | residual vs 0.3423544 |
|---|---|---|---|
| two-wave, run A | `evidence/termination/build_A_50ohm.json:278` | 0.32586326 | **−4.82 %** |
| one-wave, run A | `evidence/termination/build_A_50ohm.json:279` | 0.32613492 | −4.74 % |
| two-wave, run B | `evidence/termination/build_A_50ohm_p51_phasors.json:286` | 0.32556487 | **−4.90 %** |
| one-wave, run B | `evidence/termination/build_A_50ohm_p51_phasors.json:287` | 0.32588679 | −4.81 % |
| one-wave, run B at β_KJ | `docs/design/s11_port_forensics_2026-11-07.md:99` (row) | 0.33174966 | **−3.10 %** |

Four of the five lie in [−4.90 %, −4.74 %], spread 0.16 pp across two runs
(n_line 54 vs 64) and two estimators. Run variation ~0.08 pp, estimator
variation ~0.08 pp; neither is the source. The fifth closes 1.80 pp, the
largest single identified contribution.

**Reference-label caution.** `s11_port_forensics_2026-11-07.md:99` prints
−3.677 %, not −3.10 %. Same |Γ| 0.33174966, different denominator:
−3.677 % is vs the forensics table's own baseline (≈0.344414, itself the
p51 one-wave at β_static, `:97`); −3.10 % is vs the independent anchor
0.3423544. Every percentage in this doc names its reference.

**The preregistered question:** what accounts for the −4.74 % to −4.90 %
residual against Gamma_anchor = 0.3423544, and what fraction of the drop
to −3.10 % is attributable to a defensible β?

## 2. Hypotheses with frozen brackets

A bracket is a numeric range with stated pass/fail. "Interesting" is not a
bracket. Brackets were fixed before their tests ran.

**Conversion constant used throughout.** From Γ = 50/(50 + 2·Z0) at
Z0 = 48.02374054929774: |dΓ/dZ0| = 100/(50+2·Z0)² = 4.688e-3 Ω⁻¹;
relative sensitivity (dΓ/dZ0)·Z0/Γ = 0.657. **1 % of Z0 → 0.66 pp of
residual.** Stated here once, referenced wherever it is used (meta-rule 1).

### H1 — anchor dispersion (Z0 at 5.828 GHz differs from quasistatic)

Quasistatic Z0 is the DC transverse value. At 5.828 GHz, dispersive eps_eff
moves Z0. Producing Γ = 0.32556487 (run B two-wave) would require
Z0 = 51.7896 ohm (+7.84 %); producing Γ = 0.33174966 (run B one-wave at
β_KJ) would require Z0 = 50.3580 ohm (+4.86 %). The question is not what Z0
would have to *move to*, but what Z0 would *produce* the measured Γ
(replacing "closing" with "explaining", per correction #4 in §7.1).

**Bracket H1:** a frequency-aware modal Z0 computed at 5.828 GHz differs
from 48.0237 by ≥ 1 % (|ΔZ0| ≥ 0.48 Ω, equivalently ≥ 0.66 pp residual
shift, per the conversion constant). **Fires:** H1 is a real contributor;
partial. **Does not fire:** |ΔZ0| < 0.48 Ω (residual shift < 0.66 pp);
H1 is not a contributor.

### H2 — discretization (mesh size)

0.4 mm cells over 3.2 mm strip = 8 cells. Halving tests whether the
residual converges or saturates.

**Bracket H2:** h-refinement (0.4 mm → ≤ 0.27 mm) moves S11 by ≥ 1.0 pp
**and** monotonically toward the anchor. **Fires:** discretization is a
contributor. **Does not fire:** < 1.0 pp, and the measured pp still enters
the partition table (e.g. 0.7 pp = 14.6 % of 4.8 pp); "saturated" is a
courtesy label for the < 0.5 pp case and has no arithmetic effect.

**Floor convention — rejected.** The 3× declared-floor rule is **not
adopted** for H2; the fixed ≥ 1.0 pp threshold stands. Reason:
`evidence/h_refine/PREREG.md`'s Δ_min of 0.0734 pp is a resolution floor
for a *β* comparison inherited from `box_sweep`, not a floor for an |S11|
measurement, and no identical-configuration replicate of |S11| exists at
w = 3.2 mm. The only candidate floors in the record conflate the measured
quantity with the measurement: the feasible-variant spread of 0.167502 %
(`docs/design/s11_port_forensics_2026-11-07.md:71`) is a selection
sensitivity, and the run-A-vs-run-B difference of 0.30 pp is a
configuration difference. Adopting the convention would in fact have
**weakened** the test: 3 × 0.1675 % = 0.50 pp.

**Prior-artefact disclosure.** `evidence/h_refine/` contains an earlier,
unrelated experiment: PREREG.md (2026-10-31 02:21), runs at h = 0.40 and
h = 0.267 mm (`h040.json`, `h0267.json` + logs), analyse.py, SUMMARY.md
(02:33). It is **not** a prior measurement of H2's quantity and does not
unblind it: it is a β-offset study — strip width 0.8 mm
(`evidence/h_refine/PREREG.md:22-25`), tone 10.19862621457275 GHz, graded
Hammerstad–Jensen reference 384.7489672644 rad/m, pass/fail in percentage
points of β at 3·Δ_min = 0.22 pp. It contains no S11, no Γ, no reference
plane, no de-embedding and no impedance (literal greps: zero matches for
all five terms). H2 asks a different question on a different cross-section
at a different frequency, and is therefore a fresh test.

Three carry-overs recorded rather than inherited silently:

- **(i) grid_for rounding trap** (`evidence/h_refine/PREREG.md:33-35`):
  h = 0.3 mm is not representable — `n_sub = round(1.6/0.3) = 5` re-derives
  cell = 0.32 mm silently. At the prior study's 0.8 mm width that produced
  a −20 % meshed-width error; at H2's 3.2 mm width it is harmless —
  3.2/0.32 = 10 exactly. H2's ≤ 0.27 mm endpoint is cleanly attainable as
  h = 0.26667 mm (n_sub = 6, meshed width exactly 3.2 mm).
- **(ii) resolution-floor convention**: see the rejection above.
- **(iii) dispersive-vs-quasi-static β precedent**
  (`evidence/h_refine/PREREG.md:39-46`, citing `decisions.md` 146/148(b)):
  the tree already declines to grade against quasi-static β. This is
  **context for H5**, not a measurement of H5's quantity.

### H3 — extraction model / modal projection

Two-wave fit is selection-stable (`docs/design/s11_port_forensics_2026-11-07.md:73-74`,
F2 condition; variant spread `:71` = 0.167502 % of mean 0.325854; variant
counts `:39-41`) but selection-stability is *within* the two-wave model.
TE Q3: scalar V/I in a near-field region includes evanescent components;
correct extraction requires modal projection at a uniform reference plane.
DR-19 (`docs/design/defect_register.md:302` heading, `:338` quarantine
heading, `:340` operative sentence) quarantines plane 51 and any plane
within ~3 cells of the load.

**Bracket H3:** modal-projection S11 at a plane ≥ 3 cells past the load
differs from the two-wave S11 by ≥ 1.0 pp. **Fires:** extraction model
carries ≥ 1 pp; H3 prioritized. **Does not fire:** two-wave validated to
≤ 1 pp; H3 deprioritized as an explanation.

**Cost:** new extraction method, not a re-run. **Gate:** executed only if
H1+H2+H4+H5 partition < 80 % (see §4 and §5).

### H4 — anchor box-limit precision

DR-36 (`docs/design/defect_register.md:615`) records quasistatic Z0 as
box-limited: 0.91 % at n=100, 0.37 % at n=200. If the w=3.2 rerun has the
same convergence rate, Z0∞ differs from 48.0237 by up to 0.37 %, shifting
the residual by up to 0.24 pp (0.657 × 0.37 = 0.24).

**Bracket H4:** the box-limit correction at w=3.2 moves Z0 by ≥ 0.10 Ω
(≥ 0.2 %, equivalently ≥ 0.13 pp residual shift, derived). **Fires:**
H4 is real but small. **Does not fire:** < 0.10 Ω (< 0.13 pp).

### H5 — β discipline (which β the record should carry)

The record's β is the two-wave fit's own β (231.5533 rad/m). β_KJ
= 228.6288 (Kirschning-Jansen closed-form, `docs/design/beta_dispersion_comparison_2026-11-07.md:25`,
L38 column order) gives S11 = 0.33174966 (`docs/design/s11_port_forensics_2026-11-07.md:99`
row; the derivative d|Γ|/dβ = −1.991630e-03 per rad/m is at `:103-104`).

Mechanism: β is a fitting parameter in `fit_station_impedance`; the fit
determines gamma_v; |Γ| inherits from gamma_v. De-embedding is unit-modulus
(`docs/design/s11_port_forensics_2026-11-07.md` GATE 1), so β moves |Γ|
*through the fit*, not through propagation.

**What is already known:** adopting β_KJ moves the residual from −4.90 %
to −3.10 % (1.80 pp vs independent anchor 0.3423544), and from −5.47 %
to −3.68 % against the forensics baseline ≈0.344414 (1.80 pp, `:99`
publishes −3.677 % at this baseline). Either reference, ≥ 1 pp. The test
is therefore not "does β move the number" — it is "**is β_KJ more
defensible than β_fit for this cross-section?**"

## 3. H6 — declared out of scope, with magnitude stated

The load's effective impedance near 5.828 GHz is unresolved. Two estimates
exist and disagree at ~14 % — larger than the residual itself:

- `docs/design/s11_port_forensics_2026-11-07.md` implies an effective
  |Z| ≈ 47.2 Ω against nominal 50.
- `docs/design/complex_load_analysis_2026-11-04.md:124-151` fits R_p ‖ C_p
  = 34.57 − j20.78, giving |Z| ≈ 40.4 Ω.

A candidate with ~10 pp potential magnitude cannot honestly be given a
≥ 1.0 pp bracket, and behind three cheaper hypotheses it would be
evaluated last or never. It is therefore **excluded from the partition**.
E11 exit criterion B does not require H6 to fire or not fire; it requires
H1–H5 to partition the residual among themselves.

**What would open H6:** an E12 preregistration, placed once the two load
definitions (forensics inversion vs parallel-RC fit) are reconciled, or
once an independent measurement of Z_load exists. The 4.8 % observed
residual itself bounds the load model: either it is approximately right,
or the two estimates are not measuring the same thing. That ambiguity is
*why* it cannot be bracketed yet.

## 4. Execution order (cheapest first)

The gate on H3 is aligned to criterion B's 80 % (§5).

1. **H5 (partly on record)** — run one mode_profile cross-section solve at
   w=3.2, apply bracket.
2. **H4** — read DR-36 at w=3.2, extrapolate box-limit, apply bracket.
3. **H2** — read `evidence/h_refine/SUMMARY.md` sealed until this step,
   plus `h040.json` and `h0267.json`; apply bracket.
4. **H1** — compute frequency-aware modal Z0 at 5.828 GHz via
   `emfit/mode_profile.py:447` `_section` + `emfit/quasistatic.py:334`
   `z0_eps_eff` at frequency; apply bracket.
5. **H3** — only if H1+H2+H4+H5 partition < 80 %. See §5 for why the gate
   number matters.

## 5. Exit criteria

E11 closes when ONE is true and the result is on record:

**A.** One hypothesis fires with contribution ≥ 60 % of the residual, its
fix is implemented, post-fix residual < 1 %.

**B.** The hypotheses partition the residual with arithmetic summing to
100 % ± 20 % (i.e. **≥ 80 %** covered), each bracket fired or did not fire
with a stated number.

**C.** A new hypothesis (H6+) is opened. E11 closes to "superseded by E12";
E12 carries the residue forward.

**Why the H3 gate is 80 %, not 60 %.** Criterion B requires ≥ 80 %.
A gate at 60 % leaves a 60–80 % band where H3 is skipped AND criterion B
already fails — E11 could neither close nor invoke its only remaining
hypothesis. The gate must match B.

## 6. What this does NOT test

- The circular 0.34465 anchor (already retracted by E1,
  `docs/design/anchor_audit_2026-11-05.md:37` heading "A3", table row
  `:150` "A3 ... FIRES").
- Whether the engine is "correct" for arbitrary geometries. E11 is a
  single-geometry investigation (w=3.2 mm, 5.828 GHz).
- The E4(c) β = 231.55 vs 232.80 A-vs-B disagreement (a *different* β,
  inherited from run A vs run B; corrected by Dispatch 2's E4(c) reframe).
- The load's physical impedance at 5.828 GHz — see H6 in §3.

## 7. Process discipline

**Meta-rule 1 — dual-currency brackets require shown arithmetic.** Any
bracket, threshold or equivalence stated in two currencies (Ω ↔ pp,
% ↔ dB, β ↔ pp) must show its conversion factor at the point of statement.
The single conversion needed throughout this doc is 1 % of Z0 → 0.66 pp
(derivation in §2). H1 and H4 both drifted in the sent version; §7.1
records the corrections.

**Meta-rule 2 — pre-placement corrections are dated, not silent.** The
version sent to the agent for review is the frozen reference; the placed
file is a corrected descendant and carries §7.1 below. Same discipline as
`evidence/termination/build_A_50ohm.superseded.json`: additive pointer,
never silent edit.

**If a resolution contradicts a bracket during execution, do not silently
correct the bracket.** Write an "E11 bracket correction" entry stating:
(i) which bracket, (ii) what the resolution found, (iii) why the original
bracket was set based on an incomplete read, (iv) the revised bracket with
the same frozen-before-reading discipline. Dated and attributed.

### 7.1 Pre-placement corrections

| # | Sent version said | Placed version says | Why |
|---|---|---|---|
| 1 | §6 of the sent version: "H2's question was asked nine days before E11 existed" | **deleted** | False. The prior study is a β-offset study at 0.8 mm / 10.19862621457275 GHz with zero matches for S11, Γ, plane, de-embed, impedance. It does not ask H2's question. |
| 2 | §6 of the sent version: PREREG's threshold presented as a resolution floor for the H2 comparison | restated as a floor for a **β** comparison (3·Δ_min = 0.22 pp); explicitly not an \|S11\| floor | Δ_min 0.0734 pp is inherited from `box_sweep`; it has no transferable units. |
| 3 | H1: second Z0 figure "49.54 Ω (+3.15 %)" | **50.3580 Ω (+4.86 %)** | Inversion Z0(Γ) = (50/Γ − 50)/2 at Γ = 0.33174966 gives 50.35803; the intermediate 50.3576 was a 4-dp slip. Percentage unchanged. |
| 4 | H1: "closing the residual" | "**explaining** the residual" | Eliminating the residual requires Z0 = 48.0237 by construction; H1 tests a Z0 that *would produce* the measured Γ. |
| 5 | H1 bracket companion: "≥ 0.5 pp" | "**≥ 0.66 pp**" | d\|Γ\|/dZ0 = 100/(50+2Z0)² = 4.688e-3 Ω⁻¹; relative sensitivity 0.657. 1 % of Z0 → 0.66 pp. |
| 6 | H4 bracket: "≥ 0.10 Ω (≥ 0.13 pp)" | Ω-only at statement: "**≥ 0.10 Ω**"; 0.13 pp given as a *derived consequence* | 0.2 % of Z0 × 0.657 = 0.13 pp. Two currencies at one statement invited drift. |
| 7 | H2: dead band 0.5–1.0 pp | Single threshold: fires iff **≥ 1.0 pp AND monotone**; otherwise does not fire, and the measured pp still enters the partition table (0.7 pp = 14.6 % of 4.8 pp); "saturated" demoted to a courtesy label for < 0.5 pp with no arithmetic effect | A "does not fire but also undefined" class made the partition non-exhaustive. |
| 8 | H2: threshold convention left as 3 × floor if defensible | **3×Δ_min convention rejected for H2; fixed ≥ 1.0 pp**, with reasons stated (see H2 floor convention block) | No defensible \|S11\| floor exists at w = 3.2 mm; 3 × 0.1675 % = 0.50 pp would have weakened the test. |
| 9 | H5: no prior-artefact reference | H5 gains: "Prior-artefact precedent at `PREREG.md:39-46` rejects quasi-static β as a grading basis; this is context for H5, not a measurement of H5's quantity." | The tree already declines to grade against quasi-static β (`decisions.md` 146/148(b)). |
| 10 | Citations given as bare ids | file:line everywhere | Standing citation rule (dispatch L58). |
| 11 | DR register headings as `###` | `##` | Register convention is `## DR-NN`. |
| 12 | H5: "from −5.54 % to −3.68 % against the forensics baseline ≈0.344414 (1.86 pp)" | "**from −5.47 % to −3.68 %** against ≈0.344414 (**1.80 pp**)" | −5.54 % reproduces only against the retracted circular anchor 0.3446515 (0.32556487/0.3446515 = 0.94462); against ≈0.344414 the two-wave residual is −5.473 % (0.32556487/0.344414 = 0.94527), and the β_KJ value at that baseline is −3.677 %, so the span is 1.80 pp, not 1.86 pp. |

### 7.2 Bracket records added during execution

§7.1 records corrections made to the sent version *before* placement. This
subsection records the other direction: brackets and premises that were not in
the placed file and were fixed only at execution time. Both are dated and
attributed, per meta-rule 2.

1. **H5's bracket was not in the placed document.** The placed file carries
   `**Bracket H1:**` through `**Bracket H4:**` lines and no `**Bracket H5:**`
   line, so H5 (§2) had no numeric pass/fail at placement. The operator
   supplied one at execution time, before the solve ran, and it reads: whether
   the computed β_KJ matches 228.6288 to ≥ 1 %; if yes record H5 FIRES and the
   residual becomes −3.10 %; if no record H5 DOES NOT FIRE and the residual is
   stated as β-dependent. **This bracket is recorded after placement and must
   be read as an execution-time bracket, not as a pre-placement one.** Dated
   2026-11-09, attributed to the operator.

2. **Premise correction: H5 is a closed-form evaluation, not an eigensolve.**
   The execution brief stated that H5 needed a `mode_profile` cross-section
   solve costing 1–3 min, extrapolated from `test_mode2d` timings. That is
   wrong. β_KJ is the closed-form Kirschning–Jansen exponent at
   `tools/d585_modal.py:86`, exposed as `hammerstad_beta` at
   `tools/d585_modal.py:103`; measured cost was 0.715 s wall including
   interpreter start and the numpy/scipy import. The 2D eigensolve is a
   different quantity (β_eig). No timeout budget is implicated.

3. **The reproduction result, with its non-independence stated in the same
   breath.** β_KJ at the artefact's own bin 5827786408.327286 Hz is
   228.62882383816375 rad/m, bit-identical to the published figure — because it
   is the same function at the same bin, so bit-identity there is guaranteed by
   construction and is not corroboration. At the rounded tone 5.828 GHz it is
   228.6374412810108 rad/m, +0.003769 % from the published value; that is the
   3.66e-5 relative offset between the rounded tone and the real bin, not model
   disagreement. The ≥ 1 % check therefore passes, and it cannot carry H5:
   H5's preregistered question (§2) is whether β_KJ is *more defensible* than
   β_fit at this cross-section, which a reproduction check does not answer.
   **Status: UNRESOLVED pending operator ruling. H5 is recorded neither as
   fired nor as not fired.** The arithmetic that follows *if* the operator
   rules for β_KJ — residual against anchor 0.3423544 moving from −4.90 % to
   −3.10 % — is conditional and is not established here.

### 7.3 E11 bracket correction — H4

Per the rule stated in §7 above: (i) bracket, (ii) what the resolution found,
(iii) why the original bracket was set on an incomplete read, (iv) the revised
bracket, frozen before reading. Dated 2026-11-09, attributed to this session.

1. **Which bracket. Bracket H4** (§2, `:145-148`): "the box-limit correction at
   w=3.2 moves Z0 by ≥ 0.10 Ω (≥ 0.2 %, equivalently ≥ 0.13 pp residual shift,
   derived). **Fires:** H4 is real but small. **Does not fire:** < 0.10 Ω
   (< 0.13 pp)." Its premise (`:141-144`) is that DR-36's 0.91 % / 0.37 % box
   limits apply to the w=3.2 rerun "if the w=3.2 rerun has the same convergence
   rate", so that Z0∞ differs from 48.0237 by up to 0.37 %, worth 0.24 pp.

2. **What the resolution found.** Three things, from
   `evidence/quasistatic_z0_ladder_w3.2mm.json` and
   `evidence/e11_h4_box_limit_2026-11-09.json`:

   **(a) DR-36 is a w = 3.0 mm ladder.** `docs/design/defect_register.md:615`
   (heading) and `:623` ("`h` = 1.6 mm, `w` = 3.0 mm") — its 0.91 % and 0.37 %
   are the per-doubling drift and the n=200-to-limit gap **at that width**.
   Neither figure is a w = 3.2 mm measurement and neither is a correction owed
   to the w = 3.2 mm limit. What ports across is the convergence *rate*, and it
   does: the w=3.2 ladder's own per-doubling relative drifts are −0.924 %,
   −0.275 %, −0.075 % against DR-36's −0.91 %, −0.27 %, −0.073 %. A rate that
   transfers is not an offset that transfers.

   **(b) The bracket runs two different quantities under one label** (`:142`).
   "the box-limit correction" conflates (1) a *modelling offset* between the
   finite-box model and the true half-space, and (2) the *estimator/convergence
   uncertainty* in reading a limit off a four-rung sequence. A box-limit
   correction is the first; what the ladder actually bounds is the second. H4 as
   written cannot be answered without separating them.

   **(c) The offset is zero by construction, so the bracket's quantity is a
   category error** (`:143`). The w=3.2 ladder widens the transverse box at
   every rung (0.1632 m × 0.0816 m at n=800,
   `geometry.transverse_box_m`), so **48.02374054929774 already is the wide-box
   limit** of that sequence. There is no second box-limit correction to apply to
   it: correcting a limit for the thing it is the limit of. **Correction =
   0.000 Ω.** The only live number is the estimator span — the five cross-check
   estimators in that file (3-point fit 48.020776417, lower triple
   48.020776417, upper triple 48.026562484, Richardson p=1 48.003936759, p=2
   48.028073158) span **0.024136399 Ω = 0.0503 %**, with the 4-point refit
   (48.023740549) inside the interval. The `curve_fit` covariance on 4 points
   and 3 parameters is **not** an uncertainty and is not used
   (`refit.covariance_is_an_error_bar: false`).

3. **Why the original bracket was set on an incomplete read.** At placement the
   only box-limit evidence to hand was DR-36, one width over, and it was read as
   an unapplied offset on the w=3.2 limit rather than as a n=200-to-limit gap at
   w=3.0. The w=3.2 ladder's `cross_checks` block — the only thing that turns
   "the same convergence rate" into an answer — was not read. The 0.13 pp
   companion itself was arithmetically right (0.657 × 0.2 % = 0.13 pp, §7.1
   row 5); it was applied to a quantity whose definition had not been fixed.

4. **Revised bracket — threshold unchanged, definition fixed.** The ≥ 0.10 Ω
   (≥ 0.2 %, ≥ 0.13 pp) threshold **stands exactly as frozen**; nothing here
   lowers a bar after the fact. What is fixed is the quantity it is applied to:
   the box-limit correction is 0 by construction, and the live quantity is the
   0.024136399 Ω (0.0503 %) five-estimator span of the w=3.2 ladder, which is
   **24.1 %** of 0.10 Ω (0.0503 % against the 0.208 % that 0.10 Ω corresponds
   to). **Verdict: H4 DOES NOT FIRE.** In residual currency the whole question
   is worth 0.657 × 0.0503 % = **0.0331 pp out of the 4.904 pp residual, i.e.
   0.67 % of it** (residual −4.904 %, `docs/design/EM_SOLVER_LEDGER.md:36`).

   **The alternative reading, stated so it cannot be called cherry-picked.** Had
   the n=200 rung (48.209080873) been taken as "the" value awaiting correction,
   the correction would be 0.185340 Ω = 0.3859 %, which **does** exceed 0.10 Ω
   and H4 would fire as "real but small". It would be worth 0.2538 pp = **5.2 %**
   of the residual. That reading is not taken because 0.185340 Ω is the
   *truncation gap of a coarse rung*, not a box-limit effect — the ladder
   extrapolates through it — but even if it were taken, 4.65 pp of residual
   would remain unaccounted for. **Under either reading H4 does not explain the
   residual.**

### 7.4 E11 bracket correction — H5

Per the rule stated in §7 above: (i) bracket, (ii) what the resolution found,
(iii) why the original bracket was set on an incomplete read, (iv) the revised
bracket, frozen before reading. Dated 2026-11-09, attributed to this session.

1. **The bracket as written (:150-167).** H5 asked whether the residual is a
   dispersion-model artefact rather than a solver artefact: replace the fitted
   β by the Kirschning-Jansen closed form (β_KJ = 228.6288 rad/m,
   `docs/design/beta_dispersion_comparison_2026-11-07.md:25`; |S11| =
   0.33174966 at `docs/design/s11_port_forensics_2026-11-07.md:99`; slope
   d|Γ|/dβ = -1.991630e-03 per rad/m at the same file `:103-104`) and see
   whether the residual collapses toward zero. The bracket was frozen in
   execution-time wording and is quoted verbatim from this artefact's
   `bracket.text`:

   > whether the computed beta_KJ matches 228.6288 to >= 1 percent; if yes
   > record H5 FIRES and the residual becomes -3.10 percent; if no record H5
   > DOES NOT FIRE and the residual is stated as beta-dependent

2. **What the resolution found.** The reproduction check computed
   β_KJ = 228.6374412810108 rad/m, i.e. 228.6288 to 0.0038 %, comfortably
   inside the bracket's 1 % gate — so the first clause passes. The consequence
   clause does not. The number the bracket printed, -3.10 %, is the
   *one-wave-station* estimator of |Γ_port| evaluated at β_KJ (0.33174966
   against A = 50/(50 + 2·48.02374054929774) = 0.3423544153167928, i.e.
   -3.097596 %), not the estimator of record. The estimator of record is the
   two-wave fit, whose |S11| at the β of record (231.55331672912826 rad/m) is
   0.32556486641109117 -> -4.904142 %
   (`evidence/e11_h4_box_limit_2026-11-09.json` records
   residual_pct_measured = -4.904142652976361 from the same bytes). Applying
   the same in-tree slope to the *two-wave* curve at β_KJ gives ≈ -3.21 %, not
   -3.10 %. So "swap β" is not by itself worth the 1.8 pp the bracket implied:
   part of that move is the estimator swap, which the bracket silently bundled
   into the β swap.

3. **Why the bracket was set on an incomplete read.** It treated one printed
   scalar (-3.10 %) as the unique consequence of adopting β_KJ. It is not
   unique. |Γ_port| is not a stored key in the artefact — there is no
   `gamma_port` field — it is a reflection recomputed from the fit at a stated
   β by the `docs/design/s11_port_forensics_2026-11-07.md` §8 recipe, so the
   same phase bundle yields -3.10 % (one-wave at β_KJ), ≈ -3.21 % (two-wave at
   β_KJ), -4.81 % (one-wave at β_fit, 0.32588679434738205), -4.90 % (two-wave
   at β_fit) and -5.25 % (one-wave extrapolated to the modal β; item 4(a)
   below). The bracket also assumed that the choice between β_KJ and β_fit is a
   fact the reproduction check can settle. It is a model choice.

4. **The ruling and the revised bracket.** Ruled 2026-11-09: **H5 DOES NOT
   FIRE**, and the residual is stated as β-dependent. Reproducing the closed
   form to 0.004 % shows only that β_KJ is internally reproducible; it does not
   adjudicate which dispersion model this geometry actually has. The residual
   is therefore carried as an interval over β, not as the single -3.10 % the
   bracket hoped for. Frozen before reading any further artefact:

   **(a)** On the one-wave curve the interval runs from -3.10 % at β_KJ
   (228.6374412810108 rad/m) up to **-5.25 %** at the modal β of
   232.30694631182445 rad/m, obtained by the
   `s11_port_forensics_2026-11-07.md:103-104` slope:
   0.32588679434738205 + (-1.991630e-03)(232.30694631182445 -
   231.55331672912826) = 0.3243858387142148 -> -5.2485 %. Cross-check by
   linearising the residual between the two one-wave anchors (-4.81 % at
   β_fit, -3.10 % at β_KJ; slope -0.58731 pp per rad/m) gives -5.2527 %. Both
   routes round to -5.25 %, so the figure does not depend on which is taken.

   **(b)** That extrapolation is 1.5x the support the slope was fitted over.
   Δβ = 232.30694631182445 - 231.55331672912826 = 0.753630 rad/m against a
   ±0.5 rad/m window, and the target β itself is not stored in any artefact —
   it comes from the ruling, not from a measurement of this geometry. -5.25 %
   is therefore quoted as the *top of the β interval*, not as the residual, and
   not as a measured value.

   **(c)** The naive -5.37 % that appears if one interpolates the two *quoted*
   endpoints (-4.90 % two-wave at β_fit, -3.10 % one-wave at β_KJ; slope
   -0.61731 pp per rad/m) is a mixed-estimator artefact: those two numbers are
   not two points on one curve. On the one-wave curve β_fit reads -4.81 %; on
   the two-wave curve β_KJ reads ≈ -3.21 %. Interpolating across the β axis and
   the estimator axis at once double-counts the estimator change, which is why
   it lands about 0.12 pp past -5.25 %. -5.37 % is not used anywhere.

   **(d)** Scale, for §7.5: the β interval is 2.15 pp wide (-3.10 -> -5.25).
   H4's entire box-limit contribution was 0.0331 pp (0.67 % of the residual,
   §7.3); the estimator spread is 0.1675 % (`s11_port_forensics_2026-11-07.md`
   F2, 5.458137e-04 of 0.325854) and the run-to-run spread ~0.30 pp. The β
   choice dominates this budget by roughly an order of magnitude over every
   other term except run noise. That is the finding: the residual is
   β-dependent, and E11's status stays UNVERIFIED rather than becoming
   confirmed-by-explanation.

### 7.5 E11 bracket correction — H2

Per the same rule, and frozen before the fine rung exists: at the time of
writing no fine-mesh result has been produced, so this bracket cannot have been
set on a read of one. Dated 2026-11-09, attributed to this session.

1. **The bracket as written (:76-79).** H2 asks whether the residual is
   discretization. The bracket text, verbatim from §2, is: h-refinement
   (0.4 mm -> ≤ 0.27 mm) moves S11 by ≥ 1.0 pp **and** monotonically toward the
   anchor. **Fires:** discretization is a contributor. **Does not fire:**
   < 1.0 pp, and the measured pp still enters the partition table (e.g.
   0.7 pp = 14.6 % of 4.8 pp).

2. **The rule, restated operationally.** Fires iff the coarse -> fine move is
   (a) at least 1.0 pp in magnitude and (b) monotone toward the anchor, i.e.
   |Γ| must move *up* toward A = 0.3423544153167928 as the cell shrinks. A
   move smaller than 1.0 pp does not fire the hypothesis, but it is not
   discarded: the measured pp is written into the partition table and stated as
   a fraction of the 4.8 pp residual, exactly as the bracket says. No
   post-hoc widening of the 1.0 pp gate after the run.

3. **What will be run — one rung, one code path.** The fine rung is
   `evidence/termination/run_build_A_nsub6.py --n-line 96 --load-at-mm 20
   --load-ohm 50 --mem-ceiling-mb 2000 --s21-plane-index 76 --nsteps 3600`.
   The wrapper exists because `evidence/termination/run_build_A.py` has no flag
   for the seven mesh keys: its `build_kwargs` literal (`:502-525`) hard-codes
   n_sub 4 / n_air 12 / n_top 6 / n_clean 96 / n_pml 6 and does not pass
   n_strip or n_ref at all, so those fall through to the emfit/studies.py
   defaults (`MS_N_STRIP` 8 at `:1202`, `MS_N_REF` 2 at `:1206`). The wrapper
   imports the base module by file path, patches
   n_sub 6 / n_strip 12 / n_air 18 / n_top 9 / n_pml 9 / n_clean 144 / n_ref 3
   onto the returned kwargs, re-runs `check_mesh` (`:396`, which enforces
   n_top == n_pml per `emfit/studies.py:2555-2557`), and delegates to the same
   `main`. Nothing in run_build_A.py or under emfit/ is edited. The coarse
   anchor is the same script unpatched
   (`--n-line 64 ... --s21-plane-index 51`, as recorded in
   `build_A_50ohm_p51_phasors.json` meta.argv), so the rung-to-rung delta is
   attributable to the mesh and not to a second code path.

   *[Post-hoc annotation, added after the run. The command above is preserved
   exactly as frozen, including the absence of any `--out`, so the divergence
   stays auditable. The command actually executed added one flag:
   `--out evidence/termination/build_A_50ohm_nsub6_p76.json`. The reason is
   that `OUT_DEFAULT` at `evidence/termination/run_build_A.py:114` is
   `evidence/termination/build_A_50ohm.json`, which is tracked and committed:
   the frozen command as written would have overwritten committed evidence
   with a different mesh's numbers. The artefact's own `meta.command_line`
   records the command as it was actually executed, so the file and the record
   agree. Result in §7.6. This is a post-hoc annotation of a sealed
   pre-registration and the original wording is kept deliberately: a
   pre-registration that misquotes the command that ran is a defect, and
   hiding the defect would be a worse one.]*

4. **The fine mesh, stated before the run.** Grid 108 x 318 x 33 = 1,133,352
   cells (coarse: 72 x 212 x 22 = 335,808; ratio 3.375x), cell h/n_sub =
   1.6e-3/6 = 2.6667e-4 m (coarse 4.0e-4 m). Box unchanged at 84.8 x 8.8 x
   28.8 mm: nx = n_pml + n_ref + n_line = 9 + 3 + 96 = 108, ny =
   2(n_pml + n_clean) + n_strip = 2(9 + 144) + 12 = 318, nz = n_top + n_air +
   n_sub = 9 + 18 + 6 = 33. Strip 12 cells = 3.2 mm, so the
   `emfit/studies.py:2582` strip-must-equal-width guard still holds; PML 2.4 mm;
   side clearance 38.4 mm. nsteps 3600, not 2400, because dt scales with the
   cell: 3600 x 2.6667e-4 holds the coarse run's 1.830 ns of physical time
   (n_warm = nsteps//4 = 900, `emfit/studies.py:3020-3022`).

5. **The three baseline scalars and nothing else.** The fine rung will be
   differenced against (i) `s11.magnitude` = 0.32556486641109117, the two-wave
   |B/A| at z = 0 (not de-embedded); (ii) `s11.magnitude_one_wave_station_fit`
   = 0.32588679434738205; and (iii) Γ_port at the β of record
   231.55331672912826 rad/m, which has no native key in the artefact and is
   therefore named as the fit's reflection recomputed at a stated β by the
   `docs/design/s11_port_forensics_2026-11-07.md` §8 recipe — 0.32588679434738205
   at β_fit, 0.33174966 at β_KJ = 228.62882383816375. Context carried with them:
   `line.beta = line.beta_two_wave` = 231.55331672912826, `s11.phase_deg` =
   -100.49921155605985, `s11.validation_status` = "UNVALIDATED". No other
   scalar is available to be quoted after the fact.

6. **Stop rule, fixed now.** Each run is gated at 1400 s wall and 2000 MB
   (`run_build_A.py:124-125`). A rung that trips either gate is refused, not
   truncated, and is not re-run with a raised ceiling. One rung only; a third
   rung requires a new preregistration. Projected cost for the fine rung is
   ~5.06x the coarse run (~221 s, RSS 0.9-1.2 GB) against the measured coarse
   43.68 s / 339.5625 MB, so both gates should clear with margin — but the
   projection is stated here in advance so that a gate trip is evidence, not a
   surprise.

7. **The plane caveat, inherited — and its arithmetic corrected.** The earlier
   text of this item read column 76 at 2.6667e-4 m as sitting at 20.4 mm and
   coarse column 51 as sitting at 20.0 mm. Both figures are wrong, and the
   correction is made here, before the fine rung exists. `--s21-plane-index` is
   forwarded unchanged and honoured downstream only (`run_build_A.py:520-521`
   sets the column directly; the default-policy branch at `:534-580` runs only
   when the flag is absent). The column-to-x map is node-layer arithmetic,
   `x = ix * cell`, with no half-cell offset and no n_pml term:
   `emfit/studies.py:2863` names `ix_port = n_pml + n_ref` "node layer of the
   port plane"; `:2940` records a load as `"x": ix_load * cell, "column":
   ix_load`; `:3037` places the probe stations at `station_x = js * cell`; and
   `:3630` fixes the port at `x_port = float(ix_port * cell)`, "the same plane
   the lumped port drives". At the coarse cell 4.0e-4 m, column 51 is
   **20.4000 mm**, not 20.0 mm — 20.0 mm is column 50, the column
   `--load-at-mm 20` lands on (`ix_load = floor(0.020/4.0e-4 + 0.5) = 50`,
   `:2920`). At the fine cell 2.6667e-4 m the same load argument lands on
   column 75 = 20.0000 mm and the requested plane is column 76 =
   **20.2667 mm**; the fine neighbours read 75 = 20.0000, 76 = 20.2667,
   77 = 20.5333 mm, and 20.4 mm is not a node there at all
   (20.4/2.6667e-4 = 76.5, a half-cell tie between columns 76 and 77).

   What the two rungs share is the *rule*, and it is exact: both planes sit one
   column downstream of their own load's cut, coarse 50 → 51 and fine 75 → 76.
   That is not a coincidence of two typed flags — it is the documented default
   plane policy, `col = ... else ix_load + 1` (`run_build_A.py:559`, policy
   stated at `:535-559`), so both explicit flags reproduce the column the
   default would have chosen on their own mesh; `plane_from_default_policy` is
   False for both only because the column was passed (`:1698-1699`). The
   correspondence is therefore same-rule-same-ordinal, which is a stronger
   claim than the "same coordinate to the micron" the earlier text had to
   disown: the ordinal offset is identical, and only the physical size of that
   one cell differs — 0.4000 mm coarse against 0.2667 mm fine, so the fine
   extraction plane sits 1.5x closer to the load, a 133.3 µm difference in
   de-embed distance. That difference is pure phase at real beta, and
   de-embedding is unit-modulus
   (`docs/design/s11_port_forensics_2026-11-07.md` GATE 1): it rotates the
   reflection and cannot move its magnitude, so no part of a coarse-vs-fine move
   in |S11| can come from this plane offset. DR-19 quarantines plane 51 and any
   plane within ~3 cells of the load
   (`docs/design/defect_register.md:302,338,340`), so the H2 comparison is
   same-rule-same-plane and inherits that quarantine rather than escaping it.

8. **What each outcome will mean.** If H2 fires, discretization is a
   contributor and §7.3's 0.0331 pp box-limit figure is read as a lower bound on
   the mesh term, with the measured pp joining the partition table beside the
   2.15 pp β interval from §7.4. If it does not fire, the mesh term is bounded
   above by 1.0 pp and the residual remains β-dominated. Either way the
   residual is not declared explained: H4 was worth 0.67 %, H5 was ruled a model
   choice rather than a measurement, and what remains is an interval, not a
   number.

### 7.6 H2 resolution - the fine rung runs, and does not fire

1. **The bracket, quoted (:76-79).** H2 fires iff "h-refinement (0.4 mm →
   ≤ 0.27 mm) moves S11 by ≥ 1.0 pp **and** monotonically toward the anchor".
   Unit convention,
   as used throughout §2 and not restated anywhere below: **pp are percentage points**, an absolute
   difference of two percentages (0.5523 pp = 0.005523 in |Γ|), never a
   relative percentage change. Both appear in this section and they are
   different numbers.

2. **What was run.** The command, verbatim as executed:
   `evidence/termination/run_build_A_nsub6.py --n-line 96 --load-at-mm 20
   --load-ohm 50 --mem-ceiling-mb 2000 --s21-plane-index 76 --nsteps 3600
   --out evidence/termination/build_A_50ohm_nsub6_p76.json`. The one-flag
   divergence from item 3 of §7.5 is annotated there and is not re-argued here.
   Both gates cleared: wall 198.74779609497637 s against the 1400 s limit, peak
   RSS 927.625 MB against the 2000 MB ceiling; `meta.status` = ok,
   `meta.tripped` = false, no trip file written. Against §7.5's projection of
   ~221 s and 0.9-1.2 GB the run came in slightly under on wall and inside the
   memory band. Artefact: `evidence/termination/build_A_50ohm_nsub6_p76.json`.

3. **Geometry proof, from the artefact and not from a log.** 108 x 318 x 33 =
   1,133,352 cells at cell 2.666666666666667e-4 m, n_sub 6, n_line 96, 3600
   steps; load at column 75 (x 0.02 m, series_r 50.0 ohm, 13 edges); extraction
   plane column 76 at `x_m` 0.02026666666666667. There is no startup echo in
   this harness - every print is post-solve - so the proof is the `geometry`
   block itself, not a launch-time log line. The run **confirms** §7.5 item 7:
   the plane is load column + 1, which is the default policy, so
   `--s21-plane-index 76` reproduces the default rather than departing from it.
   The mesh is genuinely finer than the coarse rung (72 x 212 x 22 = 335,808
   cells, cell 4e-4 m, n_sub 4, 2400 steps), about 3.4 times the cell count.

4. **The numbers.** Two |S11| estimators at both rungs. Two-wave: coarse
   0.32556486641109117 -> fine 0.3200422153280212. One-wave station fit:
   coarse 0.32588679434738205 -> fine 0.3203898880823538. In pp, coarse -> fine
   moves |S11| by **-0.005522651083069985** two-wave and
   **-0.005496906265028245** one-wave, i.e. **-0.5523 pp** and **-0.5497 pp**,
   a relative change of -1.6963289509552073 per cent and -1.6867533021816057
   per cent. Supporting detail, subordinate to the magnitudes above and
   port-referred: |S21| = 0.7730201981988544 at 5.449605938169487 deg,
   `s11.phase_deg` = -98.88711363245368 deg, `s11.deembed_distance_m` =
   0.0072000000000000015 m.

5. **The verdict: DOES NOT FIRE.** Both limbs are unsatisfied, and the magnitude
   limb is the one that decides.
   - *Magnitude limb fails on its own terms*: 0.5523 pp two-wave and 0.5497 pp
     one-wave, both below the 1.0 pp threshold. This limb decides the verdict.
   - *Direction limb is unsatisfied too, but is not claimed as tested*: |S11| moved DOWN,
     i.e. AWAY from the anchor, so the gaps to A = 0.3423544153167928 widened
     on both estimators - 0.016789548905701612 -> 0.022312199988771597
     two-wave, 0.016467620969410734 -> 0.02196452723443898 one-wave.
     Monotonicity toward an anchor is not decidable from two rungs, so this is
     a direction observation, not a passed or failed monotonicity test.
   - *The consequence, not softened*: the residual per rung, r = (|γ|/A - 1)*100,
     went -4.904143 -> -6.517281 per cent two-wave and -4.810109 -> -6.415728
     per cent one-wave. Refinement made the agreement WORSE, not better. The
     mesh term is therefore 0.5523 pp out of a 4.904143 pp residual -
     0.5523 / 4.904143 = 11.3 per cent of it - and it is signed the wrong way:
     the coarse mesh was flattering the agreement, and refinement cannot be
     concealing the remaining gap. That is the finding: the residual is not a
     discretisation artefact that further refinement would erase.

6. **Honest limits.**
   - One fine rung. Nothing here measures a convergence rate; it is a single
     two-point comparison against the coarse rung.
   - Monotonicity is untestable at two rungs, so no monotonicity claim is made
     here or anywhere else in this document.
   - The plane-local S11 is NULL in this artefact: `s11_at_plane.valid` is
     false with `invalid_reason` `plane_beyond_load`, magnitude and phase null,
     and the four `gamma_plane` fields are NaN. The extraction plane is
     strictly beyond the load column, so there is nothing past it to reflect
     from; the runtime warning states all port-referred `s11` quantities are
     unaffected. No plane-local reflection claim may be made from this run, and
     the NaN is a null-by-design, not a crash.
   - The artefact contains four literal NaN tokens and is therefore not
     RFC-8259-strict JSON: it parses only under a permissive reader. This is a
     property of the writer when `gamma_plane` is invalid - a defect to fix,
     not a defect fixed.
   - `s11.validation_status` is UNVALIDATED, and its `validation_reason` prose
     was NOT refreshed for this rung: it still enumerates residues of 5.5 per
     cent (n=64), 7.6 per cent (n=54) and 13.8 per cent (n=79), and omits this
     run's own 6.52 per cent. That string must not be quoted as this run's
     residual.
   - β is mesh-dependent at the -0.22071743754995543 per cent level
     (231.55331672912826 -> 231.0422381818818 rad/m, a change of
     -0.5110785472464556 rad/m). Arithmetic, not measurement: at the recorded
     sensitivity of about -1.991630e-03 per rad/m, that β drop would imply
     |S11| moving UP by roughly 0.10 pp, whereas the measured move is DOWN
     0.5523 pp - so the β drift does not account for the |S11| move and the two
     are anti-correlated. `line.beta_model` is unchanged at 223.35306683909548,
     as a closed form must be.
   - `meta.git_rev` is null because git is absent from the execution container,
     so the artefact cannot be tied to a commit from its own contents; that
     linkage comes from the commit that files it. `meta.nsteps` does not exist -
     the step count lives in `geometry.nsteps` - so nothing should be read from
     the former.

7. **What this does and does not settle for the partition.** H2's mesh term is
   bounded and small but wrongly signed: it does not move the residual toward
   the anchor and does not account for the shortfall. The measured 0.5523 pp
   falls between the two limbs of the operator's H2-to-H1 routing rule (below
   0.5 pp, discretisation is not dominant and H1 is worth building; at or above
   1.0 pp, H1 is confounded), so that routing decision is the operator's and is
   not made in this document. The argument that bears on it: an 11.3 per cent
   term carrying the wrong sign cannot be hiding the gap, which weighs against
   treating the residual as a discretisation artefact regardless of which side
   of the 0.5 pp line it lands. H1 is not decided and not started here, and H4
   and H5 are not re-opened.

## 8. What this does NOT claim

E11 does not claim the extraction is broken, the anchor is wrong, or the
physics is in question. It claims a small, stable, configuration-specific
residual exists on a well-defined geometry, and names five testable
explanations. Whichever fires, E11 closes with the residual accounted for,
not "believed explained."

**Nothing here is a claim of correctness. A closed row means the question
is settled, not that the solver is right.**
