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

## 8. What this does NOT claim

E11 does not claim the extraction is broken, the anchor is wrong, or the
physics is in question. It claims a small, stable, configuration-specific
residual exists on a well-defined geometry, and names five testable
explanations. Whichever fires, E11 closes with the residual accounted for,
not "believed explained."

**Nothing here is a claim of correctness. A closed row means the question
is settled, not that the solver is right.**
