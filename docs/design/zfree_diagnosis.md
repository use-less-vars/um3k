# `z_free` diagnosis — candidate ranking, decision rules, test plan

Design note. **No implementation, no changes to `emfit/`, no new solves.** Everything below is either a
byte-exact quote from source that already exists, a number already banked in an artefact, or arithmetic on
those numbers. Nothing in this document was produced by running the solver, and nothing in it proposes a code
change that should be applied before a specified test says so.

Three preceding analysis passes are inputs to this one and are *not* re-derived here:
`01_formulation_map` (what is computed, by which formula chain), `02_schur_and_coupling` (the elimination, the
coupling sign, the coupling operator), `03_corr_gap` (where the wrongness enters). This note turns those into a
ranked, costed decision programme.

**The one thing this document decides.** The corruption is **not in the operator algebra** — not in the weak
form's seven terms, and not in the Schur elimination that removes the nodal block (`S1`-`S4`, none of which is
reopened here). It *is* still allowed to be in the **assembled coefficients**: the same algebra fed a wrong
`m_eps`, a wrong local cell size, or the wrong eigenvector returns the wrong field, and two of the three live
lines below are exactly of that kind. **Corrected** — an earlier version of this paragraph said the corruption
was "not in the operator layer" without qualification; that is too strong, because C2 attacks the ε mass that
`assemble_mixed` puts *into* the operator and L6 attacks the graded cell size of the pencil, so §6 is right to
re-open the L1/L6 boundary. The defensible form is: **the operator's form is closed; the operator's coefficients
are not.** Two candidates remain live (`C1`, `C2`) plus one bounded line (`C3`, demoted, <1 %); all three are
*distinguishable for free*. Nothing should be "fixed" before that distinction is made.

---

## 0. The four questions asked, and the short answers

The briefing questions Q1-Q4, answered here so that a reader who wants only the verdict does not have to
reconstruct it from the body. Each answer names where it is argued.

**Q1 — What is `z_free`, and is `e_z` reconstructed correctly?**
**Yes, the reconstruction is correct.** `z_free` **is** the nodal potential `Φ` (the LU solve of the nodal block)
and the library's own field is `e_z = iβΦ`; the capture driver reproduces it to machine precision and its
`np.abs` is a no-op on this data (single-signed `z_free`). What is wrong is the **shape** of `Φ` — not the
identity of the object, not the convention, not the arithmetic that turns it into `e_z`.
→ `S7`-`S9`, `C5`.

**Q2 — Is the Schur complement exact?**
**Yes, by construction.** `B = m1 − c D cᵀ` (:1116) is the exact symbolic elimination of the code's own Hermitian
two-field block (:995-996); the coupling matrix is mass-weighted and `tri_sign`-covariant. It is not reopened,
and nothing in §6 touches it.
→ `S1`, §6, §7.3.

**Q3 — Is the coupling sign right?**
**Yes, and it is forced.** `+iβ` in both slots is the unconjugated bilinear form and admits no real β². A flipped
sign is not a live candidate at all — it drives β² *down* while the measurement is *up*. This was a hypothesis
and it is **REFUTED**.
→ `S3`, `S4`, §7.3.

**Q4 — Where does the `corr_e_z` collapse come from?**
**From the shape of `Φ`.** The legal operator reaches |0.770567| on the *analytic* `Φ` with one uniform global
sign, but only |0.117277| = 15.2 % of that ceiling on the *solver's* `Φ`, and a per-column oracle buys just
+0.036 — so the residual is not sign, not scale, not units: it is **shape**. Of the candidate causes, `C1`
(selector) and `C2` (interface ε / graded local cell size) are live; `C3` (the reference itself) is bounded
below 1 % by arithmetic and demoted.
→ §1, §3.1-3.2, §4, §5.

---

## 1. The two measured anomalies

Both come from the same solve and the same selected eigenvector, on two meshes, from
`.scratch/s10118_mixed_mode.npz` (31x17) and `.scratch/s10118_mode_41x22.npz` (41x22):

| quantity | 31x17 | 41x22 | reference | verdict |
|---|---|---|---|---|
| `corr_e_z` (vs analytic E_z) | **0.119160432391** | **0.119317006502** | 1.0 | 0.13% mesh drift — *converged* and *bad* |
| `corr_e_y` (vs analytic E_y) | +0.920770784811 | −0.938702180036 | 1.0 | global sign differs by mesh; magnitude fine |
| `eps_eff` = β²/k₀², **eigenvalue route** | **3.6295122081** | **3.6103349901** | **3.3500085193** | +8.34% / +7.77% — *not converged* (0.53% drift) |
| `eps_eff` = β²/k₀², **fit route** | 3.964798 | 3.969256 | 3.3500085193 (**A**); like-for-like against **B** = 3.564800282: +11.2% / +11.3% (§1.1) | +18.35% / +18.48% against A is a **withdrawn cross-pairing**; **+11.2% / +11.3%** against **B**; *converged-wrong* (0.11% drift) either way |
| β [1/mm], eigenvalue route | 312.7827646323 | 311.9553466185 | 300.4980 = k₀√3.3500085193 | +4.09% / +3.81%; 0.265% mesh drift |
| β [1/mm], fit route | 326.9107654423116 | 327.094486 | 300.4980 (**A**); like-for-like **B** = 309.981864 (§1.1) | +8.79% / +8.85% against **A** — **withdrawn cross-pairing**; **+5.46% / +5.52%** against **B** |
| `ratio_A` = Σe_z²/Σe_y² | 0.0272240 | 0.0264298 | 0.0272240 / 0.0264298 / 0.0253657 (unit-repaired, 3 meshes) | **7.0% mesh spread** — the anchor is *mesh-local*, not an invariant |

**Corrected in this table.** (i) The `ratio_A` row previously printed `0.027223973` for **both** meshes. That is
wrong: the record's unit-repaired ratios are **0.0272240 (31x17), 0.0264298 (41x22), 0.0253657 (51x19)**
(`docs/design/normalization_scheme.md:86`; measured `.scratch/logs/corr_ez_followup.txt:60` and `:143`), i.e. a
~7 % spread across meshes. The duplication is traceable to the evidence log's own annotation at `:143`, which
prints the 41x22 measured value correctly (`0.026429779`) but carries a copy-pasted
`(TASK 1 measured 0.027223973, target 0.0272240)` in the same line — the annotation, not the measurement, is what
got copied into this note. (ii) The `eps_eff` row is now labelled **eigenvalue route**, because it is not the only
route and the fit route gives a different, larger number.

**Why the mesh-locality matters for §5.** T3's kill criterion is written as `Σe_z²/Σe_y² ≤ 0.0272`, and 0.0272 is
correct **on the 31x17 cache**, where the anchor is 0.0272240. It is *not* a curve-wide threshold: transferred to
41x22 (anchor 0.0264298) or 51x19 (anchor 0.0253657) it would kill every candidate including the good one. It
therefore discriminates only as a **same-mesh comparison** — candidate ratio measured on the same mesh as the
anchor it is compared against. Any read of T3 must honour that.

**Retraction of an earlier reading.** An earlier reading of this note treated `ratio_A` as a curve-wide
invariant guarded by a curve-wide threshold; the ~7 % between-mesh spread (0.0272240 / 0.0264298 /
0.0253657) retires that reading — `ratio_A` is mesh-local.

Two facts about the *shape* of the discrepancy matter more than its size:

1. **`E_y` is fine, `E_z` is not.** Same solve, same vector, same 0.92-class correlation available in the
   transverse slot and 0.12 in the longitudinal slot. Whatever is wrong is (nearly) invisible in `x_t` and
   fully visible in `Φ = D cᵀ x_t`.
2. **The two anomalies are of different character.** The correlation is *mesh-converged* (0.13% drift); the
   dielectric constant is *not* (7.77% from 8.34%, drift 0.53%). A single mechanism must produce both: a
   converged-wrong *state* and a level offset in a *scalar*. §1.1 attaches a *second* route (the fit route) whose
   failure has a third character — converged-wrong in the scalar too (0.11 % drift at +18.4 %).

### 1.1 Two routes to ε, and two different percentage scales

Every "ε_eff error" in the record needs two labels attached or it is not a number: **which route**, and **which
scale**. This is the most confusable thing in the record, so it gets its own subsection.

**Two routes.** `ε_eff = (β/k₀)²` holds by construction, so ε inherits whatever β is used — and the record
carries two independent β for the same mode on the same mesh:

| route | where β comes from | β 31x17 | β 41x22 |
|---|---|---|---|
| **eigenvalue** | the generalised eigenproblem's `λ = β²` (the selector at :1150/:1167 reads this) | 312.7827646323 | 311.9553466185 |
| **fit** | `beta_fit = fit_beta(x, v)` (`emfit/modal.py:575`), the phase fit on the captured field | 326.9107654423116 | 327.094486 |

The two differ by **+4.52 %** (31x17) and **+4.85 %** (41x22). That offset is not rounding and is not produced by
anything in this note's candidate list; it is a standing systematic (`emfit/modal.py:575-578`, `:506-509`;
`docs/design/modalport_ownership.md:124-125`; `docs/design/normalization_scheme.md:274`).

**Two scales.** `ε = (β/k₀)²`, so a percentage on β is **not** the percentage on ε: `(1.0879)² = 1.1835` —
**+8.79 % on β is +18.35 % on ε**. Every comparison must say which scale is printed:

| route | β [1/mm] | ε = (β/k₀)² | vs β_analytic = 300.4980 | vs ε_analytic = 3.3500085193 |
|---|---|---|---|---|
| eigenvalue, 31x17 | 312.7827646323 | 3.6295122081 | +4.09 % (recorded as +4.12 %) | **+8.3434 %** |
| eigenvalue, 41x22 | 311.9553466185 | 3.6103349901 | +3.81 % | **+7.7709 %** |
| fit, 31x17 | 326.9107654423116 | 3.964798 | +8.79 % | **+18.35 %** |
| fit, 41x22 | 327.094486 | 3.969256 | +8.85 % | **+18.48 %** |

(The `+4.12 %` for the 31x17 eigen route is the figure on record; dividing the three banked numbers as printed
gives `+4.09 %`. The 0.03-point difference is rounding in the recorded figure and is immaterial at these scales.)

Three consequences that change how the evidence reads:

1. **The "8 %" and the "18 %" are one defect on two scales, or two routes — never two findings.** They must not
   be added, subtracted, or presented as independent evidence. **Corrected (see the resolution below):** the
   "+8.79 % / +18.35 %" pair came from crossing the **fit** route against **A**'s β and **A**'s ε and is
   **withdrawn**; like-for-like it is **+5.46 % / +11.22 %** on **B**. The eigenvalue route reads **+4.09 % /
   +8.35 %** on **A**.
2. **The fit route is *converged-wrong*; the eigen route is *not converged*.** Between the two meshes the fit
   route moves 0.11 % (326.910765 → 327.094486) while the eigen route moves 0.53 % (312.783 → 311.955). A
   mesh-stable route onto a mesh-stable error is **not** evidence of correctness — it is evidence that the fit
   route's error is structural rather than discretisation.
3. **C1 cannot repair both routes at once.** If C1 is right and the +4.52 % fit-vs-eigen offset *persists*, the
   corrected pair would be β_eigen ≈ 300.5 and β_fit ≈ **314.1**, i.e. ε_fit ≈ **3.660** (+9.3 % against
   3.3500). C1 alone therefore cannot close the fit-route gap: either something additional is wrong, or the
   4.52 % offset is itself part of the defect.

**One denominator, stated once.** Every percentage in this note is against the `microstrip_mode_profile`
reference `ε = 3.3500085193` (`.scratch/logs/corr_ez_followup.txt:22`, key `eps_eff`, in the section
"1. ANALYTIC REFERENCE (microstrip_mode_profile → plane_mode)"; earlier versions quoted the number without a
locator — it is cited there explicitly; provenance and status in §8.1). The record also carries a *second* "analytic" ε of **3.564800282**
(`docs/design/modalport_ownership.md:7`), and against that denominator the same eigen-route numbers read only
+1.8 % / +1.3 % instead of +8.3 % / +7.8 % — a change of several-fold in the size of the alleged defect, from the
denominator alone. **Resolved in this pass — and the earlier framing was wrong.** An earlier version of this
paragraph called that second figure an "**unreconciled discrepancy of 6.4 %**" (`3.564800282 / 3.3500085193 =
1.0641`). That framing is **withdrawn**: the second figure is not a second *reading* of the first. The record
carries **two self-consistent analytic pairs**, each closed under ε = (β/k₀)² with k₀ = 164.17940719617263:

| pair | β [1/mm] | ε = (β/k₀)² | provenance | pairs with |
|---|---|---|---|---|
| **A** — the profile reference | 300.4980 | **3.3500085193** | `corr_ez_followup.txt:22`, key `eps_eff` | the **eigenvalue** route (§1 table) |
| **B** — the §101.18 table's analytic column | 309.981864 | **3.564800282** | `docs/design/modalport_ownership.md:7`; `decisions.md:6846`-`:6847` | the **fit** route (§1 table) |

B/A = **+6.41 %** on ε is **+3.16 %** on β (`309.981864 / 300.498268 = 1.031566`), so a re-paired percentage is
not a smaller version of the same defect — it is the same defect measured against a **different analytic
construction**. Two consequences, both of which change numbers in §1 and in `modalport_ownership.md`:

1. **Percentages are quoted like-for-like, and the cross-pairings are withdrawn.** The fit route is **+5.46 %** on
   β (`326.9107654423116` vs `309.981864`) and **+11.22 %** on ε (`3.964798` vs `3.564800282`) — *not*
   "+8.79 % / +18.35 %", which paired the fit route's β and ε against **A**'s β and **A**'s ε. The eigenvalue
   route stays on **A**: **+4.09 %** on β (`312.7827646323` vs `300.498268`) and **+8.35 %** on ε
   (`3.6295122080769704` vs `3.3500085193`). The "+1.8 % / +1.3 %" quoted two paragraphs above is a cross-pairing
   of the same kind — eigenvalue route against **B**, recorded as +1.82 % / +1.28 % at `modalport_ownership.md:9` —
   and carries no evidential weight. `modalport_ownership.md`'s **"+11.2 %"** is, on this reading, **correct
   like-for-like** (11.22 % against **B**) and is no longer "provisional" as *arithmetic*; only its denominator's
   standing is open (next paragraph).
2. **The headline is pair-dependent, and that is now stated rather than hidden.** "8 % high" is the eigenvalue
   route on **A** (8.35 % on ε, 4.09 % on β); "8.6 % high" is `modalport_ownership.md`'s **fit** route on **B**
   (8.61 % on β, from `336.675159` vs `309.981864`). Its "the repair is therefore worth about 3.1 of the 8.61
   points" survives this correction untouched, because it is arithmetic *inside* the B pair: `8.61 − 5.46 = 3.15`.

**What remains open — and it is narrower than before.** Not "which of two numbers is 6.4 % wrong", but "**which
analytic construction is the physically correct reference**": **A** (the repo's own `microstrip_mode_profile`,
electrostatic, on its own converged box) or **B** (the construction behind `modalport_ownership.md:7`, whose β is
3.16 % higher and whose derivation is not recorded in this tree). That decision is **out of scope** here. What *is*
in scope, and is now done, is that no percentage in this note can move because of it: each route is quoted against
its own pair, and the cross-pairings are withdrawn. Corroboration — not adjudication — comes from the closed form
in `C3` (§4): Hammerstad/Jensen gives **3.32546** (recorded as 3.325455 at `README_mode_profile.md:63` and 3.325474
in §8.1; independently recomputed 3.324878), i.e. **0.74-0.756 %** from **A** and **6.7 %** from **B** (equivalently
B is 7.2 % *above* the closed form — the direction was inverted in an earlier wording of this sentence). The closed
form sides with **A**, and is used here only as **corroboration**, never as a third candidate. This paragraph also
no longer needs `D0` to *adjudicate* anything: on the two-pair reading there is no arithmetic ambiguity left for it
to settle, only the (out-of-scope) question of which construction is right.

---

## 2. What is settled and must not be re-opened

Short list, so that nobody spends another pass here. Each line is decided by measurement or by construction,
not by preference.

| # | Settled | Decided by |
|---|---|---|
| S1 | `B = m1 − c D cᵀ` (:1116) is the **exact** Schur complement of the code's own Hermitian block (:995-996) | symbolic elimination; `S/A22 = A11 − C A22⁻¹ Cᴴ` with `C = iβc`, `Cᴴ = −iβcᵀ` |
| S2 | All **seven** weak-form terms match the analytic curl-curl form | term-by-term table (`02`, §b) |
| S3 | The **coupling sign** and `i`-placement are correct and *forced* (anticipating: a form with `+iβ` in both slots is the unconjugated bilinear form and gives no real β²) | `02` §b; independently, the *direction* of the eps_eff error (high) is incompatible with a flipped sign (`02` §c, C1) |
| S4 | The coupling-sign hypothesis is **REFUTED** — do not reopen | `02` §f, P1: a flipped sign drives β² *down*; measured is *up* |
| S5 | `c_f` at :1175 **is the same matrix object** as `C` inside `B` — one `assemble_mixed` (:1052), one restriction (:1104), one LU (:1107) | construction, not measurement |
| S6 | PEC row/column dropping is **exact** (dropped unknowns are homogeneous Dirichlet zeros) | `02` §e |
| S7 | The stale `e^{−iβz}` comment at :15 is a **comment** bug, unobservable in the reported `e_z` magnitude, which is β·abs(Φ) (:641-642) | `02` §b, convention note |
| S8 | The capture driver is **faithful**: its reconstruction equals the library's own `mode.e_z` magnitude to machine precision | `e_z_solver` vs abs(β·`z_free`): max rel diff **0.000e+00** (31x17), **8.484e-16** (41x22) |
| S9 | The `np.abs` at the driver (**(:224)** — the `e_z_node[free_n] = np.abs(beta * z_free)` statement; cited as `:225` in `modalport_ownership.md:37` and in the `design_pass_1` report, which is an off-by-one against the 464-line capture driver, see §8.1) is a **no-op** for any sign-blind statistic on this data | `z_free` single-signed: min/max = (+0.0, +3.951804e-02) on 31x17, (−4.027261e-02, +0.0) on 41x22; rows 1/2a/2b/3c/5a/SOLV all give corr magnitude 0.119160432391 |
| S10 | "Potential mistaken for a field ⇒ take the derivative" is **NOT TAKEN and refuted** — applying the legal operator to `z_free` does not repair anything | **the TE pair against the operator's own ceiling**: \|0.117276695\| vs \|0.770566870\| = **15.2 %** (31x17) and \|0.122104587\| vs \|0.772595941\| = 15.8 % (41x22). **Corrected:** the ratio-of-magnitudes (0.984192 / 1.023363, §8.1) was previously used here and cannot carry this conclusion — a magnitude ratio near 1 says nothing about whether the derivative *shape* route works, which is the actual claim |
| S11 | Units are not the issue for any correlation (scale-free); the reported 2.72e6 energy ratio is a 1/CELL² artefact of one-sided `* CELL`, already documented | `docs/design/normalization_scheme.md` |

The single number that carries most of the diagnostic weight, and the one to keep in front of any proposal:

```
corr( c[z-rows] @ φ_analytic , E_z_analytic )      = |0.770566870|   (31x17)   |0.772595941|  (41x22)
corr( c[z-rows] @ z_free     , E_z_analytic )      = |0.117276695|   (31x17)   |0.122104587|  (41x22)
                                                       15.2% of the operator's own ceiling, non-uniform sign pattern
corr( z_free , φ_analytic )                        = +0.573448286090104
```

The operator *can* produce 0.77 with **one uniform global sign** (201/201 columns flip the same way). Fed the
solver's `Φ`, the same operator produces 0.117 with a *non-uniform* sign pattern (124/201 and 78/201 columns
flipped) and a per-column oracle that buys only +0.036. **The residual is SHAPE.** That is the whole
diagnosis in one line: `Φ` — the output of the mixed solve's nodal block — does not have the `E_z` shape.

---

## 3. The comparison chain, and where a defect can still enter

Audit of every join between "Maxwell" and "the number 0.119". `SURVIVES` means: no measurement currently
excludes it.

| L | Layer | Status | Decided by |
|---|---|---|---|
| L0 | Mesh, PEC masking, edge orientation (`tri_sign`) | excluded | 0.13% / 0.27% / 0.53% cross-mesh drift; `tri_sign` is a *global* `(lo,hi)` convention (:270), cannot flip per element |
| L1 | Operator assembly (`c`, `q`, `k_zz`, `m_zz`, `m1`, `m_eps`) | **partly excluded** — the *form* is excluded by `S2` plus the 0.770567 ceiling with uniform sign; the *coefficients* are **not** excluded (`m_eps` built from nodal ε, graded `h_local` in the pencil) — that is the C2/L6 route | `S2`; §3.2 M1/M2; `02` §b |
| L2 | Coupling sign / `i`-placement / Schur elimination | excluded | `S1`–`S4` |
| L3 | PEC row+column dropping | excluded | `S6` |
| L4 | **Input / model data** (does the solved geometry equal the reference geometry?) | **CLOSED THIS PASS — see §3.1** | static read |
| L5 | **Mode selection rule** | **SURVIVES** | `03` §A/§B; only layer explaining the E_y-good / E_z-bad / eps_eff-high triad |
| L6 | **Interface treatment / graded-cell size in the pencil** | **SURVIVES (new, see §3.2)** | the p ≈ 0.25 scaling argument is weaker than it looks on a *graded* mesh |

### 3.1 L4 is closed, statically, for free

Previously recorded as "untested alternative": the analytic reference vs the mesh actually solved. It is now
settled by reading, with no compute:

* `.scratch/tol/logs/TOLFLUX.json` geometry block: `"width": 0.02`, `"height": 0.0076`,
  `"h": 0.0016`, `"w": 0.003`, `"eps_r": 4.4`, `"n_sub": 16`, `"ny": 200`, `"nz": 76`, `"cell": 0.0001`
  — i.e. **h = 1.6 mm, w = 3.0 mm, eps_r = 4.4, n_sub = 16**, exactly the analytic reference.
* `.scratch/logs/s10118_basis.py:67-71` unpacks that dict into `HSUB, WSTRIP, EPS_R` and derives the
  conductor box from it (`Y0, Y1 = W/2 ∓ WSTRIP/2`).
* the **same three variables** drive both sides of the comparison:
  * the solve: `eps_of` (:97-98) and the `strip` predicate (:110-111) — `eps_of = np.where(p[:,1] <= HSUB + 1e-12, EPS_R, 1.0)`,
    `strip = (p[:,1] == HSUB) & (Y0 <= p[:,0] <= Y1)`, and `solve_modes_mixed(mesh, K0, sigma=1.0, eps_r=eps_of, boundaries=BOUNDARIES)` (:172-173);
  * the reference: `microstrip_mode_profile(HSUB, WSTRIP, EPS_R, n_sub=N_SUB)` (:385).

**Conclusion.** A mismatch between the *solved* model and the *reference* model is **structurally impossible**:
they consume the same literals from the same dict. L4 is closed. (What remains open is a different question —
whether that geometry is the intended board — and it is a design-intent question, not a solver defect, and it
cannot produce a solver-vs-reference discrepancy of any size.)

This *promotes* L5 to the sole survivor of the original seven layers, and it is why L6 below had to be added:
closing L4 removes the only alternative that the previous pass had left standing, so the argument must be
checked against the one remaining discretisation-flavoured possibility.

### 3.2 L6 — the one caveat that must be stated honestly (and is cheap to kill)

`03` §C argued "not discretisation" from a cell-size ratio of 0.75 (30/40 and 16/21) and a fitted gap
exponent p ≈ 0.25. **On a graded mesh that argument uses the wrong length.** The counts 30/40 and 16/21 are
*average* cell counts across the box; what governs a boundary-layer error is the **local** cell size at the
strip edge and at the dielectric interface. If the grading keeps the first cell near y = h fixed while adding
points in the bulk, the local h barely changes between the two meshes, and an O(h_local) error would plateaus
exactly as observed — while still being a discretisation effect.

Two concrete interface mechanisms worth naming, both testable statically:

* **M1 — interface-row ε attribution.** `eps_of` assigns ε by a **node** predicate with a `+1e-12` tolerance
  (`p[:,1] <= HSUB + 1e-12`). Nodes *on* the metal plane (y = h) therefore carry ε = 4.4. If `assemble_mixed`
  builds its ε mass from element-averaged nodal values, then every element immediately **above** the strip
  inherits 4.4 at its interface vertices — the dielectric is effectively one element thicker than the board.
  Direction of the error: **raises** ε_eff, i.e. matches the observed sign. Whether `assemble_mixed` averages
  nodal ε at all is a static question, answered by reading `:470-533`.
* **M2 — strip-on-node vs strip-on-edge convention.** The conductor is the node row `p[:,1] == HSUB`
  (:110-111), so the strip is a Dirichlet *line* of nodes with the ε discontinuity attached to it. A
  quasi-static reference that integrates the flux differently across that same line can disagree at the
  percent level without either side being "wrong".

Neither mechanism is asserted. Each is *cheap to exclude*, and must be excluded before L5 is declared the sole
culprit, because both would raise ε_eff upward and both would leave `E_y` nearly untouched — the same
fingerprint as the selection rule.

---

## 4. Candidate ranking

Ranked by (evidence for) / (cost to decide). Nothing here is a proposal to change code.

### C1 — Mode selection picks a non-fundamental candidate  *(rank 1 — primary)*

**Statement.** `k* = argmax{ β² : finite, > 0, residual < 1e-3 }` (:1150, :1156-1160, :1167) selects the
**largest** admissible β² from a spectrum whose ordering carries no mode information (`B` is indefinite,
:1005-1013). The physical quasi-TEM mode has the **lowest** β of the guided set; the dielectric limit is the
**highest**. The rule therefore aims, systematically and by construction, at the far end of the guided band.

**Evidence for.**
* Explains all three observations at once with one parameter-free mechanism: `E_y` survives a mis-pick
  (transverse shape is nearly shared across candidates), `E_z` does not (hybrid/TM candidates differ
  principally in `E_z`), ε_eff goes **up** (that is where the rule points).
* The quantitative bridge is **arithmetic, and it is brutal** — see `C1.1` below. **Corrected:** an earlier
  version of this bullet claimed that a **~1.5 % admixture** of an `E_z`-dominated candidate would collapse
  corr(`e_z`) 0.92 → 0.12. That figure is wrong by **one to three orders of magnitude**. With corr(`e_z`)
  suppressed from 0.92 to 0.12, the contaminant must be at least **87 %** of the good component (anti-phase
  case; **corrected** from 77 % because the earlier quadratic dropped the −1.84a cross-term — see `C1.1`) and is
  **760 %** if it is uncorrelated with the truth. The bridge is real; the number attached to it
  was not, and `02` §c C3 carries the same error.
* Reproduces the character split: a selector changes *which vector is reported*, so its damage is **converged**
  under refinement — exactly the 0.13% drift of corr(`e_z`).
* Consistent with the sign: max-β² can only err *upward*. Observed 3.63 ∈ (3.35, 4.40).

**Evidence against.** None yet — it has never been tested. Prediction P2 (the chosen candidate is
substrate-concentrated with inflated Σe_z²/Σe_y²) is untested; if the chosen candidate's ratio is *at or below*
0.0272240 (the **31x17** anchor — mesh-local, §1), C1 dies.

**Note on the two selection rules in play.** The library picks max eligible β² (:1167); the capture driver
re-picks by **max `E_strip_t`** (`s10118_basis.py:196-208`, `cand.sort(key=lambda r: -r[3])`). The banked
artefacts therefore contain **both** identifications, and `IDENTIFIED` (:207-208) records `col` and
`solver_eps_eff` side by side. If the two rules agree on the same column, the selector is not the whole story;
if they disagree, the disagreement itself is the discriminator. This comparison needs no solve.

**Cost to decide.** **One re-solve, not zero.** `.scratch/s10118_mixed_mode.npz` holds
`candidates` (shape (1, 4), i.e. one row of `col, beta_sq, eps_eff, E_strip_t`), plus `m1, m_eps_m, c, k_zz,
m_zz, free_e, free_n`, and **no `vecs`**: only the selected row is banked, so the selector **cannot be audited
post hoc from the cache**. The audit needs a re-solve that persists every candidate *and* its vector — which is
what the 41x22 and 51x19 raw caches already carry (`vecs`, `lam`) and the 31x17 cache does not.

**What would change my mind (C1).** (a) No candidate in the banked spectrum satisfies the `C1.1` shape
requirement (corr_e_y ≥ 0.9 **with** corr_e_z ≤ 0.3) — then the selector cannot be the cause and C1 is retired
on arithmetic, before T3. (b) The library's pick and the driver's pick (`T3b`) agree on the column → the
selector is not the discriminator and C1 drops below C2. (c) The chosen candidate's `Σe_z²/Σe_y²` is at or
below the *same-mesh* anchor → P2 fails.

#### C1.1 The admixture arithmetic, done properly

Everything below is scale-free (correlations only), so no normalisation or unit question enters. Write the
reported longitudinal component as a two-term mixture

```
e_z = s + a·t,        corr(s, E_z) = 0.92,        t ⊥ E_z
```

where `s` is the "good" longitudinal part — assumed to correlate with the true `E_z` as well as the transverse
slot does, corr_e_y = 0.9208 on 31x17 (**this is an assumption, and it is the one soft joint in the argument**; the
measured value and its locator are in §8.1)
— and `t` is the contaminating mode's longitudinal part, taken orthogonal to the truth. Set the observed
corr(`e_z`, `E_z`) = 0.12 and `σ_t = σ_s`. There are only three cases:

* **`t` uncorrelated with `s`** (generic): corr = 0.92/√(1+a²) = 0.12 ⇒ √(1+a²) = 0.92/0.12 = 7.667 ⇒
  **a = 7.60**. The contaminant would have to be **7.6× the good component**.
* **`t` perfectly ANTI-aligned with the truth** (the most favourable case that exists; cov → 0.92 − a):
  the headline is the **minimum admissible root a ≈ 0.874 (87 %)**, obtained by carrying the −1.84a cross-term
  in ‖e_z‖² (see the correction immediately below). The contaminant must therefore be **at least ~87 %** of the
  good component — not the 77 % an earlier version of this bullet claimed.
* **`t` aligned with the truth**: this branch is *empty* — with ρ_t = +1 the truth is inside `t` itself, so
  corr can only be pushed *up* (the feasible minimum is 0.92 at a = 0). No value of `a` produces 0.12. That is
  itself information: the contaminant must be largely **anti-phase** with the true `E_z`.

**Corrected — the old "77-110 %" band.** An earlier version of this subsection headed the anti-aligned case
with **a = 0.768 or a = 1.098, i.e. "77-110 %"**, read off `0.9856a² − 1.84a + 0.832 = 0`. That quadratic is
mis-stated: it treats `t` as orthogonal to `s` while `ρ_t = −1`, but `ρ_t = −1` *forces* `corr(s, t) = −0.92`, so
the −1.84a cross-term belongs in ‖e_z‖² and was dropped. Because of that omission the lower corner a = 0.768
(77 %) is **not admissible**; carrying the cross-term through gives a **minimum a ≈ 0.874 (87 %)**, which is the
figure used everywhere below. The band is **superseded** — it was never the operative number, and 77 % was an
under-estimate of the floor. Reading the old "1.5 %" as an **energy** fraction instead of an amplitude fraction
does not rescue it either: a = 0.1225 gives corr = 0.92/√(1.015) = 0.913.

So **"1.5 %" is dead by factors of 58 to 507** — **1.8-2.7 orders of magnitude** — because the *minimum
admissible* contaminant is **87 %** (87/1.5 = 58) and the decorrelated case is **760 %** (760/1.5 = 507), which
bounds the range from above. The contaminant must be anti-phase. **This is an explicit correction of an earlier
claim in this file and in `02` §c**; the earlier text read "factors of 51 to 507 ... ~77 %", where 51 was the
superseded 77 % floor divided by 1.5.

`ratio_A` then selects which branch is live. The measured ratio fixes |e_z|/|e_y| = √0.0272240 ≈ **0.165** on both
meshes (the reference has the same ratio by construction), and it caps the *total* longitudinal content at 16.5 %
of the transverse content — it does not move between branches:

* The **orthogonal** branch (a = 7.60, or ≈ 8.0 with `t` also optimally anti-aligned to `s`'s transverse residual
  — same order) needs |e_z| ≈ 7.6|s| ≈ 7.6 × 0.165|e_y| ≈ **1.25|e_y|**, i.e. a longitudinal part *larger* than
  the transverse part. Measured: 0.165|e_y|. **Excluded by ratio_A.**
* The **anti-aligned** branch (a ≈ 0.87) needs |e_z| = |s + a·t| with the two terms nearly cancelling: a
  contaminant of *comparable magnitude*, largely anti-phase, leaves a small residual while destroying the
  correlation. That is exactly what a fixed small ratio_A permits. **This is the operative branch.**

**What this does to C1.** A contaminant of *comparable magnitude* is not an "admixture" — the reported vector is
half-to-mostly a **different mode**. So the structural question C1 must answer is sharper than "does the selector
pick the wrong candidate?":

> Can the T3 spectrum hold a candidate whose **transverse** part nearly coincides with the fundamental's
> (corr_e_y stays 0.92) while its **longitudinal** part is entirely different (corr_e_z collapses to 0.12)?

That is a *strong* requirement, not a weak one — but it must be checked before T3's ε_eff arithmetic is read,
because C1 can die on it. If no such candidate exists in the banked spectrum, **C1 dies on arithmetic before T3
runs**, and the cost-ordering in §5 has to be re-justified. That is what **T3-pre** (§5) is for.

### C2 — Interface ε attribution / graded local cell size  *(rank 2 — must be excluded before C1 is acted on)*

**Statement.** §3.2. The ε_eff error is a boundary-layer artefact of (i) the node-predicate ε assignment at
the metal plane and/or (ii) the local cell size at the interface not actually shrinking between the two meshes.

**Evidence for.** ε_eff error is ~8% and *barely* shrinks with average refinement — the signature of a
boundary layer whose *local* thickness did not shrink. Explains the level offset without touching `E_y`.
Direction (upward) matches.

**Evidence against.** It must *also* explain the **converged-wrong** `Φ` shape (corr(`e_z`) 0.119 on both
meshes to 0.13%). A boundary-layer error that leaves `E_y` at 0.92 but rotates `E_z` into a different shape
would have to be large and *stable*, which is a stronger requirement than C1 faces — but it is not impossible,
since `Φ` is diffusive (`Φ = D cᵀ x_t`, i.e. a Helmholtz solve on the nodal block) and a locally wrong ε
directly corrupts the operator producing it.

**Cost to decide.**
* C2a (**free, static**): read `assemble_mixed:470-533` for how nodal ε becomes element ε. If it is
  element-averaged, M1 is *live*; if ε is evaluated at element centroids, M1 is dead.
* C2b (**free, arithmetic on banked data**): both caches bank the grids themselves — `xs`, `zs`
  (`.scratch/s10118_basis.py:240`). Compare the **local** spacing at y ≈ h between the two meshes. If it is
  unchanged, the p ≈ 0.25 fit is an artefact of average counts and C2 is promoted to rank 1.

**What would change my mind (C2).** (a) T1 finds ε evaluated per element (not from nodal values) → M1 is dead
and C2 loses its main mechanism. (b) T2 finds the local h at y ≈ h *did* shrink by the average-count ratio →
the boundary-layer story loses its premise. (c) C2 must explain the *converged-wrong* `Φ` **shape** as well as
the scalar offset; if a localised interface error can be shown to be too weak to rotate `E_z` at fixed `E_y`
correlation, C2 falls behind C1. Conversely, C2 becomes rank 1 the moment T2 shows local h unchanged **and**
T1 shows element-averaged nodal ε, because then the ε mass in `assemble_mixed` — an *assembled coefficient*, not
the operator's algebra (§ D5 correction in the abstract) — is wrong in a way that matches the observed sign.

### C3 — The reference itself carries a few percent  *(rank 3 — cheap sanity check on the denominator)*

**Statement.** `microstrip_mode_profile` is the repo's own quasi-static finite-difference solver with
`n_sub = 16` vertical nodes. Its accuracy is **not benchmarked anywhere in this tree**; the entire "8% error"
claim is measured against it. If the reference were 3% low, the defect being chased would be half the size.

**Evidence for.** No independent validation of the reference was found. Its own self-consistency is excellent
(`corr(analytic e_z, −d(analytic φ)/dz) = 1.000000000000000`), but self-consistency is not accuracy.

**Evidence against — and it is now decisive.** **(a) The Hammerstad/Jensen bound, computed here by hand.**
With u = w/h = 1.875, ε_r = 4.4: a = 1 + (1/49)ln[(u⁴ + (u/52)²)/(u⁴ + 0.432)] + (1/18.7)ln[1 + (u/18.1)³]
= **0.999361**; b = 0.564[(ε_r − 0.9)/(ε_r + 3)]^0.053 = **0.542058**; 1 + 10/u = **6.333333**
(= 19/3); exponent −a·b·ln(19/3) = −0.541711 × 1.845827 = **−0.999905**; factor = (19/3)^(−0.541711) = **0.367919**;
ε_eff = (ε_r+1)/2 + (ε_r−1)/2 × factor = 2.7 + 1.7(0.367919) = **3.32546**. The reference `3.3500085193` is
**+0.74 % above the closed form** — comfortably inside T0's >1 % kill criterion. **`D0` therefore PASSES** — hand `3.32546` (−0.74 %), recorded `3.325455` (`README_mode_profile.md:63`, +0.7385 %),
§8.1's `3.325474` (+0.7385 %) and an independent recomputation `3.324878` (+0.756 %); the code says the same at
`emfit/mode_profile.py:586-595` ("+0.74 % off the Hammerstad-Jensen fit") but is not independent. **Band: 1 %-class
only — it does not adjudicate `A` vs `B` (pair B is 6.7 % from the closed form).** C3 is demoted from "candidate" to a **bounded nuisance**: a reference error below 1 % cannot produce
a **4.09 %** (β scale) or **8.35 %** (ε scale) gap, so C3 cannot be the cause of the anomaly, while still being worth the
formal check T0 already specifies (§1.1 also uses it to adjudicate between the two ε denominators in the record).
**(b) Struck claim.** An earlier version of this bullet said the reference "reproduces the published `2.722397e6`
energy anchor exactly". That is **not** evidence of accuracy and must not be quoted as such:
`docs/design/normalization_scheme.md:85`/`:199` rules `2.722397e6` **VOID as a physical ratio** — the `1e8` in it
is a class (ii) unit defect (`normalization_scheme.md:86` gives the repaired 0.0272240 / 0.0264298 / 0.0253657).
Agreement on a void quantity carries no information.

**Cost to decide.** **Arithmetic only, no run** — and it is already done above (3.32546 vs 3.3500085193,
+0.74 %). `D0` stays in §5 as the **formal** check and as the mask on the denominator of every percentage in this
file, but there is no longer a live question for it to settle: C3 is bounded below 1 % and demoted to rank 3.
Its remaining value is negative-space evidence — it rules out the one escape hatch that would have shrunk the
whole problem by a factor of ~20.

**What would change my mind (C3).** T0 finding the reference more than 1 % from the closed form in the
*direction that shrinks the gap* (i.e. reference too **high**) would restore C3 and re-base every target in §1;
the hand computation above gives +0.74 %, on which `D0` has since **passed** (1 %-class band only). C3 is also reopened if the two
ε denominators in §1.1 (3.3500085193 vs 3.564800282) cannot be reconciled — a factor-of-six ambiguity in the
denominator is the one way a few-percent reference question becomes a first-order one.

### C4 — Why none of this was caught (not a cause; a defect in the safety net)

The block-residual guard (:1178-1188) rebuilds the two-field matrix from the *same* signs and checks
`‖block·field‖ / (‖block‖_F‖field‖)`. It is **blind by construction** to any error that is self-consistent —
a wrong selector, a flipped sign, a wrong mode. It validates arithmetic, not physics. Same for the anchors at
:1015-1022, which are documented and never executed (§5). Recording this is not a candidate cause; it is the
reason the defect survived to 0.119.

### C5 — Excluded candidates (each with the number that excludes it)

Do not re-test these; see `01` §Q6 for the full table. Summary: rectifier/`np.abs` (single-signed field,
delta exactly 0.000000000); global sign/conjugation (|corr| invariant, and the eigenvector sign already differs
between meshes: +0.9208 vs −0.9387 for the *same* code); gauge/constant offset (subtracting the mean makes it
*worse*: +0.009491 / −0.002329); PEC gauge sign (3c bit-identical to baseline); numerical `−d(z)/dz` (worst
option: −0.032886, and it moves Σe_z² by six orders); per-column sign scramble (oracle buys +0.036, and the
control's oracle is uniform 201/201 — the control would look like TE if sign were the defect); lost phase/lost
`i` (all arrays real by construction, `e_z = 1jβΦ` and the cache stores `|e_z|` — the `i` is not lost, it is the
reason the stored array is a magnitude); different field in the driver (0.000e+00 / 8.484e-16); cached `c` is
not the operator (max|diff| 0.000e+00); resampling bookkeeping (scatter determinism 0.000e+00; analytic
self-check corr = 1.000000000000); mesh resolution (0.13% drift); the archived `0.14619976001754773`
(matches none of the calculated variants — **still unexplained**, see §7).

---

## 5. The test plan, costed

**Naming.** This section numbers the tests `T0`-`T5`, as first written; later text and `decisions.md` call the
same items `D0`-`D5`. The mapping is fixed here once, so that no reader has to re-derive it:

| §5 as written | `D`-name used elsewhere | standing |
|---|---|---|
| `T0` | `D0` | executed in this pass — **PASS** (see `C3`) |
| — | `D1` | new, design only — the section after this one |
| — | `D2` | new, design only — the section after this one |
| `T3-pre` | `D3-pre` | **DATA-INSUFFICIENT** — see the placement note below |
| `T3` | `D3` | not executed |
| `T3b` | `D3b` | not executed |
| `T4` | `D4` | not executed; not authorised by this note |
| `T5` | `D5` | declined, not postponed |

`D1` and `D2` are **additions, not renamings**: nothing below is renumbered, reordered or re-scoped, and the
cost ordering of this section is unchanged.

**Placement: `D3-pre`.** Executed this pass, outcome **DATA-INSUFFICIENT** — neither a pass nor a kill. It is
not a `C1` kill and `C1` is neither confirmed nor retired by it; the cost ordering is therefore **not**
inverted. The prerequisite the screen needs is the analytic `Phi`, `E_y`, `E_z` it correlates against, and that
is **not on disk**: there is no analytic `.npy` anywhere under `.scratch`, and it is rebuilt at run time
(`tools/corr_ez_101_20.py:181-184`, `.scratch/logs/s10118_basis.py:385-387`). Only scalars were banked: `Phi`
shape `[431, 217]` (`corr_ez_followup.txt:22`), corr_e_y `+0.920770784811` at 31x17 (`:43`), `-0.938702180036`
at 41x22 (`:126`), corr_e_z `0.119160432391` (`:205`). Second blocker: `candidates` is shape (1, 4) in both
caches, so a **per-candidate** screen cannot be run post hoc either. **Costed unblock:** rebuilding the analytic
reference needs **no eigensolve** (deterministic quasi-static FD plus `plane_mode`, seconds); screening the 31x17
candidates additionally needs an eigensolve re-run (1486 edges, dense below `_MIXED_DENSE_MAX = 3000`, ~35 MB,
~35 s class), because that cache banks no `vecs`. "Failed" and "insufficient" point in opposite directions — a
failure retires `C1` and inverts the ordering, insufficiency retires nothing — and only the second is what the
data supports.

Ordered by cost. Each test is stated with **what it decides** and a **kill criterion**, so that a null result
is informative rather than a shrug. No test below edits `emfit/`.

| # | Test | Cost | Decides | Kill / pass criterion |
|---|---|---|---|---|
| **T0** | Hammerstad/Jensen closed form for w/h = 1.875, ε_r = 4.4 vs `microstrip_mode_profile`'s 3.3500085193 | arithmetic, minutes, no run | C3 — is the *denominator* of the 8% claim sound? | If the reference is off by >1%, re-base the ε_eff target before anything else |
| **T1** | Read `assemble_mixed:470-533`: is nodal ε element-averaged? | static read, minutes | C2a / M1 live or dead | If ε is evaluated per element (not from nodes), M1 is **dead** and C2 loses its main mechanism |
| **T2** | Compare **local** cell spacing at y ≈ h using the banked `xs`, `zs` on both meshes | arithmetic on two `.npz`, no solve | C2b — was the boundary layer actually refined? | If local h is unchanged (ratio ≈ 1.0), C2 is **promoted** and the p ≈ 0.25 argument in `03` §C is retracted as an average-counts artefact |
| **T3-pre** | Structural screen on the banked spectrum, run **before** T3: does any candidate pair a near-fundamental transverse part (corr_e_y ≥ 0.9) with a decorrelated longitudinal part (corr_e_z ≤ 0.3)? | arithmetic on one `.npz` **plus one deterministic rebuild of the analytic reference**, which is not on disk — see the `D3-pre` placement note; cheaper than T3, shape screen only, no ε_eff arithmetic, no reassembly | C1 — the precondition `C1.1` says T3 silently assumes | **Kill C1:** no candidate satisfies the shape pair ⇒ selector cannot reproduce the collapse, C1 **dies on arithmetic** and the cost-ordering **inverts** (C2/T1/T2 move ahead). Pass = screen non-empty ⇒ T3 is worth its arithmetic |
| **T3** | Full-spectrum sweep: for **every** admissible candidate in the banked spectrum, recompute ε_eff and the `E_z` overlap, **B unchanged**. **Caveat:** not executable as written on 31x17, that cache banks no `vecs` | arithmetic on one `.npz` **once the 31x17 cache carries `vecs`** — i.e. one 31x17 re-solve, no reassembly | C1, directly; P1 and P2 of `03` §A | **Pass:** some candidate reaches corr(`e_z`) ≥ 0.9 with ε_eff ≈ 3.3500 ⇒ selector is the fault, fix is one line at :1150/:1167. **Kill C1:** no candidate exceeds corr 0.5, or the chosen candidate's Σe_z²/Σe_y² ≤ 0.0272 |
| **T3b** | In the same pass, compare the library's pick (:1167, max eligible β²) against the driver's pick (:200, max `E_strip_t`) — both are already banked as `col` and as `candidates` rows. **Caveat:** the cache banks one candidate row, so a per-candidate statement needs a re-solve | free, same pass | whether the two rules agree | Disagreement is itself the discriminator; agreement weakens C1 |
| **T4** | Promote `.scratch/mode2d/c2_slab2.py` to `tests/` as the first `mode2d` test | ~2.5 min runtime; ~1 h of build | permanent coverage of the **TM** defect class + a selector regression test | Assertions: (a) β²/k₀² within 0.5% of analytic, (b) the *chosen index* equals the analytic mode index, (c) `Σe_z² > 0` and `cᵀx_t ≠ 0` |
| **T5** | A finer microstrip mesh | ~2 min/solve at 1444 free edges (measured 111 s); the whole exercise costs hours | confirm-only | **Deprioritised.** Predicted by `03` §C to still show ≈7.5%. Run last, and only after T1-T3 are clean, and only as a *convergence confirmation*, not as a diagnostic |

**Why this order.** T0-T3 are free or near-free and each can independently terminate the investigation. T4 buys
permanent coverage and is the only step that prevents the *next* recurrence. T5 is the only step that costs
hours and the only one the evidence already predicts will be negative — it is listed so that it can be
explicitly *declined*, not merely postponed.

Three placements are worth stating rather than leaving implicit:

* **T0 sits first because it is a masking test, not a candidate test.** It acts on the *denominator* of every
  percentage in §1: until it certifies ε_eff = 3.3500085193 and the corresponding k₀, "8 % high" is a number
  without a baseline. A T0 failure therefore does not invalidate any *candidate* — it invalidates the
  *comparisons*, so it has to be resolved before any candidate verdict is read off.
* **T3-pre sits between T2 and T3 because it is strictly cheaper and can retire C1 before T3's arithmetic is
  spent.** It is a shape screen on the banked spectrum (corr_e_y ≥ 0.9 with corr_e_z ≤ 0.3) — no ε_eff
  arithmetic, no reassembly. If the screen comes back empty, C1 is dead on arithmetic and the order inverts:
  C2/T1/T2 move ahead of T3 instead of behind it.
* **T4 is listed but not authorised by this note.** Promoting `.scratch/mode2d/c2_slab2.py` to
  `tests/test_mode2d.py` costs ~1 h of build plus ~2.5 min runtime, and it must *first* pass its three
  assertions (a)-(c) standalone against the slab anchors `(k₀, β²/k₀²)` = `(3.0, 4.298278227712)` and
  `(2.095845021952, 4.196297158361)`. Nothing here authorises that promotion; T4 is a separate dispatch.

---

## D1 and D2 -- design only (not executed this block)

Two items are called `D1` and `D2` in later discussion and have no row in the table above. **Neither was executed
in this pass.** They are recorded here as designs, with their inputs pinned and their pass/kill criteria fixed
*before* anyone runs them, so that neither can be retro-fitted to whatever it returns. Both test the **same
candidate, `C2`** -- that the discrepancy is produced by the *solver* rather than by the reference -- and they
split it along its two independent mechanisms: **`C2a`**, the attribution of dielectric contrast to the lattice at
the strip interface, and **`C2b`**, the resolution of the singular field at the strip edge by a uniform structured
lattice. Note what that means: `D1` and `D2` are tests of **`C2`**, not of the reference `A`. The reference's own
accuracy is `D0`'s question and `D0` has passed; the profile's normalisation bookkeeping is settled in §1.1. An
earlier draft of this section made that substitution -- it tested the interface rule's effect on the `+0.74 %`
residual and the 1.164852 % window normalisation -- and both of those are 0.3-1.2 % questions that cannot address
a 4.09-11.22 % gap.

**Prerequisites shared by both.** The default box, not a plane-sized one: `n_clean = n_air = 200`,
`43.0 x 21.6` mm, `Phi` of shape `[431, 217]` (`emfit/mode_profile.py:22`); banked geometry `h = 0.0016`,
`w = 0.003`, `eps_r = 4.4`, `n_sub = 16` (`.scratch/tol/logs/TOLFLUX.json`). No test below edits `emfit/`
unless it says so explicitly and is authorised separately.

### D1 -- does dielectric interface attribution explain the solver's epsilon deficit? (`C2a`)

**Corrected in this pass -- the mechanism as previously written was wrong, and so was the test.** An earlier
version of this subsection claimed that the mixed block's permittivity term was selectable at
`emfit/mode2d.py:995-996` via the library's `interface="dual"` / `"point"` option, and that `C2a` was therefore
testable by flipping a keyword argument. Both halves of that are false, and both are settled by static read:

* **`mode2d.py` contains the token `interface` zero times.** There is no such keyword anywhere in the module, and
  `solve_modes_mixed`'s signature (:935-945) takes no attribution argument at all.
* The `interface="point"|"dual"` switch exists **only** in `emfit/materials.py` -- `_check_interface` (:174),
  `_sampled` (:182), `material_matrices` (:241-254) and its three matrix builders `M_eps` (:354), `M_mu` (:363),
  `M_sigma` (:372) -- with callers `emfit/raster.py:489` and `emfit/quasistatic.py` (docstring :40-46). It is a
  **quasi-static / raster** option. Nothing carries it into the modal path.
* **`:995-996` is inside `solve_modes_mixed`'s docstring, not code.** Those two lines are the block sketch
  `[ [beta^2 m1 + k_q - k0^2 m_eps, i beta c], [-i beta c^T, k_zz - k0^2 m_zz] ][x_t, x_z] = [0]`. Citing a
  docstring as the assembly site is exactly what produced the false premise. The real assembly is `:1051-1052`:
  `k_q, m_mu, m_eps = assemble(...)` and `m1, m_eps_mixed, c, k_zz, m_zz = assemble_mixed(...)`. The matrix this
  subsection used to call `m_eps_m` is therefore `m_eps_mixed`, returned by `assemble_mixed` (:469).

**The real mechanism -- and it is narrower than "which rule did you pick".** In **both** assembly paths the
permittivity is **centroid-sampled**, not averaged from nodes: `assemble` (:397) builds `eps_t =
_per_triangle(eps_r, mesh, "eps_r")` at :416, and `assemble_mixed` does the same at :505-506; `_per_triangle`
(:378-394) evaluates `eps_r` at `mesh.centroid` (:382). There is exactly **one** attribution rule in the modal
path, and it is a **per-element, one-point rule**. `C2a` is therefore not the question "dual or point?" -- it is
the question **"does a one-point centroid rule mis-attribute dielectric contrast at the strip interface, and by
how much?"** A dual/Hodge or edge-averaged attribution of the kind `materials.py` offers does not exist in this
code today, so there is nothing to switch.

**What the claim has to be worth.** `C2a` is quantitative, not qualitative: the attribution artefact has to be a
substantial fraction of the observed gap -- **4.09 %** on `beta` and **8.35 %** on `eps` for the eigen route on
pair **A**, **5.46 % / 11.22 %** for the fit route on pair **B** (§1.1).

**Proposal -- a code patch, not a flag run.** Test `C2a` by adding a second, deliberately different attribution
rule and measuring its spread against the centroid baseline. The patch surface is bounded, and it is listed here
so that its size can be judged before it is authorised:

1. a **per-edge** (or per-triangle averaged) eps rule in or alongside `_per_triangle` (:378-394), returning a
   second `eps_t` variant without disturbing the centroid one;
2. a keyword plumbed through `assemble` (:397 call site, :416 use) and `assemble_mixed` (:469, :505-506);
3. the same keyword threaded through `solve_modes_mixed` (:935-945 signature) and its two assemble calls
   (:1051-1052), and through whatever thin wrapper the 31x17 driver uses;
4. **a decision about the consistency guard.** `:1053-1069` cross-checks `m_eps` against `m_eps_mixed` and forces
   them equal to 1e-12 relative. A patched build must either apply the alternative rule to *both* paths (guard
   left intact) or relax the guard deliberately and say so in the report -- relaxing it silently would remove the
   one check that proves the two paths describe the same operator.

**Standing under the no-edit rule -- BLOCKED.** This is **not** a run of an existing option and cannot be executed
under the current fence: it is a multi-site edit under `emfit/`. It is recorded as **design only, not authorised,
and blocked** until re-authorised explicitly as a code change, with the guard decision taken first. The plumbing
question the earlier draft left open ("does the option reach `m_eps_m` like it reaches the profile builder?") is
now **answered**: it does not, and it cannot without this patch.

**What it decides.** Whether the `eps` gap is an artefact of **interface attribution** -- in which case it is a
solver-configuration defect with a one-parameter fix and both §1 routes shrink together -- or whether it survives
attribution unchanged, in which case `C2a` is **dead** and the gap has to come from `C2b`, or from `C1`/`C3`
being reopened.

**Cost -- re-based.** The earlier costing assumed three to four runs of an existing flag. That is not the shape of
this test. It is **one patched build plus N solves**: one build (items 1-3 above, plus the guard decision), then
two solves on the banked 31x17 mesh (1486 edges, dense below `_MIXED_DENSE_MAX = 3000`, ~35 s class) -- the
centroid baseline, which must still reproduce the banked `3.6295122081`, and the alternative rule -- with a third
only if the first two separate. The build, not the linear algebra, is the cost, and the build is what the no-edit
rule currently forbids.

**Pass / kill.** The band is set **relative to the gap the test must explain**, not chosen for comfort, and the
correction above does not move it. `C2a` survives only if the attribution spread is a substantial fraction of
**4.09 %** (the smallest `beta` gap it is offered against). **Kill `C2a` if the spread is <= ~0.4 %** -- an order
of magnitude below that gap, arithmetically unable to produce it. Between ~0.4 % and 4.09 % the result is
partial: report the fraction and re-rank `C2a` against `C2b` instead of declaring a verdict. **A spread larger
than the gap itself** means the baseline attribution is not the one that produced the banked number -- that is a
provenance finding, not a `C2a` confirmation, and it must be reported before any percentage in §1 is re-read.

### D2 -- does the uniform lattice under-resolve the strip-edge singularity? (`C2b`)

**What it tests.** `C2b`, not the profile's normalisation. The 31x17 mixed mesh is a *uniform* structured
lattice: its cell boundaries do not fall on the strip edge, and the quasi-static TMo field carries an `r^-1/2`
class singularity there, so a discrete `eps_eff` converges from one side as cells shrink. `C2b` claims the
observed 4 %-class `beta` gap is that convergence error evaluated at a coarse mesh, not a modelling error.

**Proposal.** Hold the box, the geometry and the physics fixed and vary **only the cell size near the strip edge**
-- either a graded mesh that refines toward `y = +-w/2, z = h` while leaving the far field coarse, or a nested
local refinement of the edge cells. Report, over a 3-4 point family: `eps_eff`, `beta`, and -- the part that
matters for the record -- a **shape** metric for `Phi` (the banked `corr_e_y` / `corr_e_z` and `ratio_A`, so the
result is directly comparable with §1). Fit the sequence and report the **extrapolated limit**, not the finest
run, so that "converged" means Richardson-extrapolated rather than "stopped moving".

**What it decides.** Whether the gap is a **discretisation error that shrinks as the edge is resolved** -- in
which case it is a mesh-resolution finding, the fix is grading or sub-celling rather than physics, and §1's
percentages are mesh artefacts that must be re-based -- or whether it **persists at the extrapolated limit**, in
which case `C2b` is **dead** and the discrepancy is a genuine model difference between solver and reference.

**Standing under the no-edit rule.** This is the **only** item in §5 that cannot be run as specified without
touching the grid: `mode2d` builds its lattice uniformly, so a graded or nested edge refinement is a prototype
change, not a parameter. It is recorded as **design only and not authorised** for that reason, and it must not be
started before `D1`'s plumbing question is answered -- if `D1` shows the gap is attribution-dominated, `D2` is not
worth its prototype.

**Cost.** A convergence family, not one run: 3-4 solves **plus the grid prototype**. The solves are cheap
(31x17 class, ~35 s); the prototype is the whole cost, and it is the reason this test is deferred rather than
scheduled.

**Pass / kill.** **Kill `C2b` if `eps_eff` and the `Phi` shape metric are both flat to <= ~0.5 % across the
family** -- 0.5 % being an order of magnitude below the 4.09 % gap, so a flat sequence cannot produce it. `C2b`
**survives** if the extrapolated limit moves `eps_eff` by a substantial fraction of the gap *while the shape
metric stays put*: that is the signature of a field-singularity artefact rather than a different mode, and it
re-bases every percentage in §1.

**What neither test does.** Neither can adjudicate the `A` vs `B` question of §1.1 -- `D1` measures a spread
across attribution rules on one construction, `D2` measures convergence of one construction, and the `A`/`B` split
is **6.41 %** on `eps`, larger than either band and a question about which analytic construction is physically
correct. Equally, neither test can **confirm** `C2`: a large spread or a slow convergence shows the solver is
attribution- or mesh-sensitive, not that this sensitivity accounts for the whole gap, which could still be
partly model difference. Both tests are **one-sided** -- they can kill `C2a` / `C2b` cleanly, but they can only
make `C2` more plausible, never establish it.

---

## 6. Decision tree

```
T0 ── reference >1% off? ──yes──► re-base the ε_eff target and re-run this table
 │no
 ├─► T2 (local cell size at y≈h unchanged?)
 │        │no (local h did shrink)          │yes (local h ~unchanged)
 │        ▼                                 ▼
 │   C2 weakened → go to T3            C2 promoted → T1 (element-averaged ε?)
 │                                          │live ──► C2 becomes rank 1; T3 in parallel
 │                                          │dead ──► C2 needs another mechanism; go to T3
 └─► T3-pre ── any candidate pairs corr_e_y ≥ 0.9 with corr_e_z ≤ 0.3?
          │yes                                        │no
          ▼                                           ▼
    T3 ── some candidate has corr_e_z ≥ 0.9      C1 retired on arithmetic — no candidate
    and ε_eff ≈ 3.35?                            can hold the shape pair at the ~87 %
          │yes                       │no         minimum admixture ⇒ re-rank:
          ▼                          ▼           C2/C3 promoted, T3 arithmetic not spent
    C1 CONFIRMED: report selection defect;       C1 dying. Check T3b agreement;
    fix is one line at :1150/:1167, gated on T4   then the defect is in the pencil's
    landing first as a regression test            nodal block itself → re-open §3 L6/L1
                                                  boundary, NOT the coupling sign (S4).
```

Nothing in this tree touches the coupling sign, the Schur complement, or the PEC masks.

---

## 7. Explicit non-scope, and known unknowns

**Not proposed by this document.**
1. Any change to the selection rule **before** T2/T3 report. Changing the rule first would destroy the banked
   spectrum that T3 needs and would make the diagnostic unfalsifiable.
2. A finer mesh as a *diagnostic*. It is a confirmation step at best (T5).
3. Any revisiting of the coupling sign, the Schur elimination, `c_f` identity, or the PEC masks (`S1`-`S6`).
4. Removing the `np.abs` at `s10118_basis.py:224`. It is a **no-op** on this data (`S9`); removing it changes
   nothing except the tool's own narrative. **:224 is the correct locator** — that driver is 464 lines, and
   `docs/design/modalport_ownership.md:37` cites :225, an **off-by-one**, reconciled exactly as in `S9`
   (provenance in §8.1).
5. Editing `emfit/`. T4 lands in `tests/`; the one-line selector change, if T3 confirms C1, is a separate,
   later, explicitly-authorised dispatch.

**Known unknowns.**
* `0.14619976001754773` (the superseded correlation) — **CLOSED-UNRESOLVED.** It is recorded at
  `decisions.md` §101.21(m)(3), and the archaeology scan is **negative** at
  `.scratch/logs/corr_ez_followup.txt:117` and `:200` ("matches: none of the above reproduces
  0.14619976001754773"). It stays a *re-openable locator*, not a number: the transverse correlations on the two
  meshes are byte-identical to their reported values (`0.92077078481114205` at :43; `−0.93870218003589878` at
  :126), so whatever produced 0.14619 came from a variant that is no longer in the tree. It is not explained
  here and must **not** be quoted as a measurement.
* The `e^{−iβz}` comment at :15 contradicts the derived convention (`S7`). Harmless for every reported number;
  a trap for the next reader.
* Whether `microstrip_mode_profile` is accurate to <1% is **checked, and it is** — **`D0` = PASS** (see `C3`):
  the hand closed form `3.32546`, the recorded `3.325455` (`README_mode_profile.md:63`) and an independent
  recomputation `3.324878` all agree to **0.74-0.76 %** on pair **A**. The band is **1 %-class only**: it
  certifies the denominator, it does not adjudicate `A` vs `B` (pair **B** is 6.7 % from the closed form). Read
  the §1 numbers as "the model and this reference differ by **4.09 % on β / 8.35 % on ε**" (eigenvalue route).
* `ratio_A`'s unit repair (0.0272240 vs the printed 2.72e6) is a *documented* one-sided `* CELL`;
  the scheme-A ratio stands, and this note does not touch scheme C (0.00951415).
* **Zero test coverage.** `grep -rln "mode2d" tests --include=*.py` returns nothing, so no committed test
  exercises the TM path at all. This is an already-established finding quoted here, not something re-run for
  this note (this note executes nothing). It is why C4 is a standing risk and why `D4` exists as a deliverable.

**Why measure at all rather than "just fix the selector".** Because the selector rule is *plausible* and
therefore cheap to believe. It has one testable consequence that has never been executed (T3), and C2 has an
equally plausible competing story that also predicts an upward ε_eff bias. Both are free or near-free to
separate. Fixing first would leave the ε_eff error in place with no way to tell which of the two produced it.

### 7.1 The 3.16 % placement beta -- open problem, design only (nothing run)

**Status.** A *known unknown*, recorded after §7's list. This subsection is **entirely design**: no solve, no
extraction and no re-placement was performed to write it, and it exists so that the question is asked with its
falsifiers attached *before* anyone spends a run on it. All three candidates below are **deferred behind the
`C1` audit** (the `T3-pre`/`T3` screen and the full-spectrum re-solve that audit needs) and **none is authorised
this block**.

**The quantity.** Two `beta` values for the same physical mode, from two different constructions of the
reference:

| pair | beta [1/mm] | how it was obtained |
|---|---|---|
| **A** | 300.498268 | converged `microstrip_mode_profile` on its own converged **431x217** box |
| **B** | 309.981864 | `plane_mode` placement of that profile onto the **200x77** archive box, then station phasors, then a travelling-wave least-squares phase slope |

B/A = **+3.16 %** on `beta`, which is **+6.41 %** on `eps` = `(beta/k0)^2` (§1.1). Every percentage in this note
is quoted against one of these two, so a 3.16 % offset *inside the reference pair itself* is not a detail: it is
the same order as the 4.09 % `beta` gap the whole note is about, it is above the ~0.4 % floor used to kill
`C2a`, and it decides **which pair is the analytic reference**.

**What is already ruled out.** The tempting first explanation -- "`beta` runs 4-5 % high on a plane-sized box"
-- describes **a configuration that was never executed**. `plane_mode` only *places* the profile onto the target
box by index offset (`emfit/mode_profile.py:591-593`); it does **not** re-solve on the smaller box. No
smaller-box eigen-solve exists that could have produced such a bias. The only placement number on record is
**1.164852 %** from the 201x77 window normalisation (`emfit/mode_profile.py:597-600`), an order of magnitude too
small to carry 3.16 %. **The mechanism is therefore UNIDENTIFIED**, and the three candidates below are a search
space, not a ranking of known causes.

**Candidate (i) -- index-offset downsampling / aliasing.**
* *Prediction.* 431x217 -> 200x77 selects a subset of samples, so the phase slope is fitted on an under-resolved
  copy of the field. `beta_B` should then depend on **which** sub-window is selected and on the box origin, not
  only on box size.
* *Data needed.* Re-placement only: the same `Phi` placed at different offsets / window sizes at fixed 200x77.
  No eigen-solve.
* *Falsifier.* **Invariance to window offset at fixed size** kills it.
* *Cost.* Cheapest of the three in work; still needs the placement driver re-run per offset.

**Candidate (ii) -- phase-slope estimator bias.**
* *Prediction.* The travelling-wave least-squares fit over station phasors is biased by **station count and fit
  span**: the slope drifts systematically as either is varied.
* *Data needed.* Arithmetic on **already-banked phasors**. No solve, no re-placement.
* *Falsifier.* LS slope **flat to better than ~0.2 %** across station subsets kills it (0.2 % being an order of
  magnitude below the 3.16 % it must explain).
* *Cost.* **Cheapest overall -- recommended FIRST.**

**Candidate (iii) -- genuine box-size effect.**
* *Prediction.* The 200x77 archive box **truncates** the field, so the estimator is genuinely measuring a
  different (truncated) mode. The same estimator applied on 431x217 should then also return ~309.98.
* *Data needed.* Station phasors on 431x217: one extraction, and possibly one eigen-solve.
* *Falsifier.* The same estimator on 431x217 returning **~300.50** puts the offset in the placement route, not
  in the box.
* *Cost.* Most expensive of the three. **Not authorised.**

**What each answer would imply for the reference.** If **(i) or (ii)** is true, the 3.16 % lives in **B's
construction** -- placement or estimator -- so **pair A** is the analytic reference: the §1 percentages quoted
against A (eigenvalue route, 4.09 % on `beta` / 8.35 % on `eps`) stand, and the like-for-like re-pairing against
B is the artefact, not the measurement. If **(iii)** is true, B's `beta` is measuring a truncated mode and
*neither* pair is a clean reference until the box question is settled -- the honest statement then is that the
denominator is undecided at the 3 %-class and every percentage in §1 needs a box label. If **all three are
falsified**, the offset sits in the shared mode construction used by both (i.e. in A's own eigensolve), and
§1.1's "which construction is physically correct" question becomes the only question left.

**Order and cost.** **(ii), then (i), then (iii).** (ii) is arithmetic on banked phasors and can retire the
estimator explanation for the price of a script; (i) is a re-placement sweep at fixed size, no linear algebra;
(iii) needs new phasors on 431x217 and possibly an eigen-solve, so it is last and is the only one with a solve
in it. **None of the three is authorised this block.** All three are **deferred behind the `C1` audit**: if `C1`
is confirmed, the selection defect is the larger term and this 3.16 % reduces to a denominator question that the
audit's own full-spectrum artefacts will make cheaper to answer.

### 7.2 Seven routes to one `beta` -- what the 3.16 % and the 4.09 % are made of

**Status.** Accounting only: **no solve, no extraction and no re-placement was performed to write this**, and every
number below is quoted from a banked file whose locator was opened for this subsection. §7.1 established *that* two
"analytic" references differ by 3.16 % on `beta` and 6.41 % on `eps`. This asks the prior question: how many distinct
constructions on this record emit a `beta` at all, which of them share a definition of `eps_eff`, and how much of the
published spread is construction and how much estimator. That matters because §5, §6 and `D1` all rank hypotheses by
"which route sits closest to the target", which is only meaningful if the routes are read as separate measurements
rather than as seven views of three number-producing mechanisms.

| # | route | `beta` [rad/m] | `eps_eff` | `eps_eff` is | locator |
|---|-------|----------------|-----------|--------------|---------|
| 1 | converged modal solve, 431x217 box | 300.498268 | 3.3500085193 | definitional, `c'/c_air` | `emfit/mode_profile.py:586-600`, `:646-652`; `corr_ez_followup.txt:22` |
| 2 | field placed on 200x77, `fit_beta(n_wave=1)` | 309.9818636706751 | 3.5648002823688385 | **measured**, `(beta C0/omega)^2` | `s10118_result.txt:14-22`, `:108`; `emfit/modal.py:575-578`; `emfit/ports.py:861-903` |
| 3 | `solve_modes_mixed` eigen-solve, 31x17 | 312.7827646323 | 3.6295122080769704 | definitional, `beta_sq/k0**2` | `s10118_result.txt:128-138`; `emfit/mode2d.py:1190-1200` |
| 4 | FDTD board, CW run | 314.03158662735785 | 3.658552575317196 | **measured**, `(beta c/2 pi f)^2` | `decisions.md:3671-3686`, `:3909-3917` |
| 5 | gate estimator `_beta_from_phase_slope` | not banked | derived | measured, full-plane phase slope | `tools/gates_101_20.py:426-445` |
| 6 | quasistatic capacitance ratio, no solve | derived `k0 sqrt(eps_eff)` | 3.3500085193 | definitional by construction | `emfit/mode_profile.py:648-651` |
| 7 | broadband bin `fit_beta(n_wave=1)` + span guards | not banked per tone | derived | measured, station phase slope | `emfit/studies.py:1809-1813`, `:1938-1958` |

**1. Half the table does not measure `eps` at all.** Rows 1, 3 and 6 emit `eps_eff` by definition: `mode2d.py:1193-1195`
sets `eps_eff = beta_sq[chosen]/(k0*k0)` from the eigenvalue the pencil already returned, and `mode_profile.py:648-651`
sets `eps_eff = c_prime/c_air` from the capacitance ratio; in row 6 there is no `beta` at all and it is *derived* as
`k0 sqrt(eps_eff)`. Rows 2, 4, 5 and 7 invert that: `beta` is measured off a field and `eps` is derived from it. The
consequence for §1 is arithmetic, not rhetorical: on rows 2 and 4 a ratio `(1+d)` on `beta` is `(1+d)^2` on `eps`, and
pair B's 6.41 % `eps` gap is exactly the square of its own 3.16 % `beta` gap. **An `eps` percentage quoted next to a
`beta` percentage from the same route is that percentage counted twice** and must be labelled as derived.

**2. Rows 1 -> 2 are a placement difference and nothing else.** Same construction -- one mode read off one field -- and
the only change is the domain: the converged 431x217 box versus the FDTD plane's 200x77 placed by index offset. The
module banks the size of that move in its own words (`emfit/mode_profile.py:586-600`): "A box sized to the FDTD plane
instead would be 4-5 % high", with the window normalisation the clip costs measured at 1.164852 % (`:620-623`). The
observed 3.16 % sits *inside* the range the module warns about, so it is not a new discrepancy; it is the placement
term, and §7.1 (i) is the sweep that would price it.

**3. Rows 3 vs 4 are two independent codes on the same cross-section, and they agree to 0.40 %.** The 31x17 FEM mesh
covers `x_edges [0.0, 0.02]` and `z_edges [0.0, 0.0076]` (`.scratch/s10118_result.txt:117-126`) -- the same 20 mm x
7.6 mm section the FDTD board discretises on 322x200x76 (`decisions.md:3909-3917`) -- and both are driven at `k0` =
164.1794 rad/m. A tetrahedral FEM eigen-solve and a Yee FDTD run with a v/i extraction, sharing no code, land
**+0.3993 % apart on `beta`** (314.03158662735785 vs 312.7827646323) and **+0.8001 % apart on `eps`**
(3.658552575317196 vs 3.6295122080769704). Since row 3's `eps` is definitional and row 4's is extracted, that 0.40 %
bounds code plus extraction together rather than code alone -- but 0.40 % is the whole of it.

**4. Rows 2 vs 3 are one field, one mesh and two extractions -- no re-solve.** Both are read off the same 31x17
capture: `.scratch/s10118_result.txt:14-22` and `:128-138` are two harnesses over one solve, with the identical nine
`station_x` planes recorded twice (`:208-218`, `:267-277`). Fitting the phase of the placed field gives
309.9818636706751; the eigenvalue the capture carries is 312.7827646323. That is **the fit sitting 0.90 % below the
eigen value on the analytic basis** -- and **+4.52 % on the mixed basis** (326.9107654423116 against the same
312.7827646323), the largest single gap on the record and the one the `T2_agree` gate is written around
(`tools/gates_101_20.py:26-32`, `:144-147`). Extraction alone, with no physics changed, therefore moves `beta` by
between 0.90 % and 4.52 %, depending only on which basis is fitted.

**5. The estimator's own window spread is the same order as the 3.16 % it is used to explain.** The gate's measured
table (`tools/gates_101_20.py:98-131`) reproduces the null floor exactly -- repeat of the same process 0.0 bitwise,
BLAS threads 1 vs 4 at 8.13e-11, `float32` round-trip at 1.10e-10, H-destagger 0.0 -- and then shows the dependency
that is *not* noise: across all 21 contiguous station windows the analytic basis spans **2.02 %** and the mixed basis
**31.2 %**; 8-station windows span 0.0700 % and 0.2338 %; the same window fitted with `n_wave=2` instead of `n_wave=1`
moves it 0.164 % / 0.335 %. The 2.02 % is the number to hold next to the 3.16 %: a route whose own reproducibility
under window choice is two-thirds of the gap cannot arbitrate that gap.

**6. The span arithmetic says the fit is well posed but close to a branch.** The nine stations run 0.0104 -> 0.0200 m
in steps of 0.0012 (`.scratch/s10118_result.txt:208-218`), so the span is **0.0096 m** and `beta*span` =
309.9818636706751 x 0.0096 = **2.976 rad** = **0.947 pi** = **0.474** guided wavelengths (`lambda_g` = 0.020268 m).
`emfit/ports.py:887-897` warns that a *two*-wave fit is ill-conditioned over a small fraction of a wavelength and that
"a one-wave fit has no such difficulty: it is well posed for any span", so the harness's `n_wave=1` is the right
choice; but the same span sits 5.3 % below the `> pi` branch-ambiguity refusal the broadband path enforces
(`emfit/studies.py:1946-1958`) and only 2.37x above its `_BIN_SPAN_PHASE_MIN` = 2 pi/5 floor (`:1809-1813`). A span
5 % shorter would put this fit into a branch it could not resolve.

**7. Two estimators that could arbitrate have no banked value at this tone.** Row 5 is a full-plane overlap phase slope
(`tools/gates_101_20.py:426-445`: `z = sum_plane conj(Ey[0])*Ey`, `unwrap(angle(z))`, `np.polyfit(xx, phi, 1)`), row 7
is a station phase slope on a projected modal line (`emfit/studies.py:1938-1958`). They are independent constructions
over the same class of capture, and neither has a stored `beta` for this record, so there is no third and fourth number
to break the tie in item 4. That comparison is currently two points whose members are 0.90 % or 4.52 % apart, and
which one is quoted depends on the basis, not on the physics.

**Decomposition.** The terms multiply rather than add: 1.031566 (placement, rows 1 -> 2, §1.1) x 1.009036 (extraction,
rows 2 -> 3) = **1.040887**, which is the +4.09 % of §1 to three decimals; multiplying in the code term gives x
1.003993 = **1.045037**, which is +4.50 % and is the whole of the 300.498268 -> 314.03158662735785 span. In words:
**the 4.09 % is 3.16 % of placement and 0.90 % of extraction, and the last 0.40 % is two codes agreeing.** The 4.52 %
mixed-basis gap of item 4 is not in that product, because the banked `beta` is the analytic one; it stands beside it as
the estimate of what the extraction term could be.

**What this settles, and what it does not.** It settles the bookkeeping: from here on every percentage in §1 should
carry a term label -- placement, extraction or code -- and none may be described as a solver discrepancy at a fixed
geometry, because item 3 shows the solvers do not disagree. It does not settle which analytic construction is correct:
that is still §1.1's open question, and rows 1 and 3 differ by *placement*, not by formulation, so no comparison among
the seven can decide it. **Nothing here is authorised.** The one experiment that would price the placement term is
§7.1 (i), it remains deferred behind the `C1` audit, and until it runs the 3.16 % and the 4.09 % are a sum of terms
with one term unmeasured.


---

### 7.3 `C2a` pre-registration -- which attribution rule, and what answer would count

**Status.** Design and pre-registration only: **no code was changed, no patched build exists, and no run was
performed.** This subsection fixes, *before* the patch is written, (a) which attribution rule `D1` would add, (b) what
the patch may not touch and what it does to the `1e-12` consistency guard that currently protects every banked number,
and (c) the band in which a spread would count as an answer. It is written in advance for the reason §5 gives: so that
the result cannot be retro-fitted. It is also where `Q2` and `Q3` (`:42`, `:48`) land -- **neither the Schur
elimination nor the coupling sign is reopened here**, and §7's item 3 is why: the `1e-12` guard is the mechanical
evidence that the two assembly paths already agree, and a change that breaks it would be reopening `S1` by the back
door.

**What is already fixed by static read (re-read for this subsection, not quoted from §5).** There is exactly **one**
attribution rule in the modal path and it is a per-element, one-point rule. `assemble` (`emfit/mode2d.py:397`) and
`assemble_mixed` (`:469`) both call `_per_triangle(eps_r, mesh, "eps_r")` (`:416`, `:506`; the helper is `:378-394` and
evaluates a callable at `mesh.centroid`, `:382`), and `assemble_mixed` reaches `eps` only through its internal call to
`assemble` at `:505`. `assemble`'s docstring says it outright (`:408-410`): "``eps_r`` / ``mu_r`` may be a scalar, a
per-triangle array, or a callable taking the ``(nt, 2)`` centroid array -- that is the only place material ever enters,
and it is sampled at the centroid as specified." Neither assembler accepts an `interface` keyword at all. The
alternative rule exists, is tested, and is **not reachable from here**: `emfit/materials.py:241` takes
`interface="dual"` and documents the two conventions at `:248-251` (point = the value at the entity centre; dual = the
weighted average over the whole dual entity), `M_eps`/`M_mu`/`M_sigma` (`:354`, `:363`, `:372`) all forward the
keyword, and the raster path relies on the dual default deliberately (`emfit/raster.py:486-489`: "the library default
interface convention (dual) is wanted here: the board top is a dielectric/air interface exactly on a node plane, the
case point sampling gets wrong by a fixed 5.7 % in capacitance"). So `D1` is not "flip a flag": the flag reaches the
FDTD/raster assembly and does **not** reach the modal assembly, and the 5.7 % on the raster side is why the modal side
may be sensitive too -- and why it cannot be assumed to be the same 5.7 %.

**Item 1 -- the rule `D1` should add, and what would refute it.** *Recommendation: extend the existing `dual` rule to
the modal path; do not invent a third one.* Two reasons, in order of weight. (i) **It is the energy-consistent average
for this configuration.** The interface that matters is the substrate top at `z = h`, where `eps` steps 4.4 -> 1.0
normal to the interface (`n = z_hat`); the field component discontinuous there is `D_z`, so the correct effective
permittivity for a dual entity straddling the interface is the **series / inverse-length-weighted** one,
`1/eps_eff = f/4.4 + (1-f)/1.0`, which is what a dual average over the entity gives. A point rule assigns the whole
entity the value at its centroid -- the wrong average on both sides of the crossing. (ii) **It needs no structural
change.** The matrices stay `K_q`, `M_mu`, `M_eps` on the same edge list with the same sparsity; only the *values*
change, plus plumbing an `interface` keyword through `assemble`/`assemble_mixed`. A Hodge-star or edge-averaged
attribution would change the operator's structure and would no longer be a one-parameter comparison against the
centroid baseline, which is what `D1`'s spread is defined as.
* *Prediction if the rule is right.* The 31x17 and 41x22 `eps_eff` both move **down**, toward 3.3500085193, and the
  movement is **larger on the coarser mesh** (31x17) -- a dual entity straddling `z = h` is a larger fraction of the
  cross-section where the mesh is coarse, so the correction scales with the mis-attributed volume.
* *Data needed, and its cost.* One patched build (the `interface` plumbing plus a dual-valued `eps` per triangle) and a
  solve sweep on the three recorded meshes -- 31x17, 41x22, 51x19 -- whose banked sizes are 527/1486, 902/2581 and
  (51x19) nodes/edges (§8). The dense QZ pencil is the expensive step and its column count is the free-edge count, so
  cost grows with the finest mesh, not with the number of rules. **No flag-only run is possible**: that is the whole
  content of `D1`'s correction -- the `interface` switch lives in `emfit/materials.py` and the raster path
  (`emfit/raster.py:489`) and does not reach `emfit/mode2d.py` at all, so there is nothing to toggle today.
* *Falsifier.* **A spread that is the same sign and magnitude on both meshes but does not shrink with refinement** is
  not an interface artefact -- it is a level shift, and `C2a` as written (§5 `D1`) is the wrong mechanism.

**Item 2 -- what the patch must not touch, and the shape check.** The `eps` mass block only. `K_q`, `M_mu`, `c`,
`k_zz`, `m_zz`, the `tri_sign` factor, the PEC mask set and the selector at `:1150`/`:1167` are all outside it. If a
proposed patch moves more than the `M_eps` values, it is no longer `D1` and the spread it measures is not `C2a`'s. The
second guard on this item is shape, because a spread measured on a changed shape is not `C2a`'s spread either. The one
number available for that check is the **banked** `corr_e_z` = **0.11916043239134175** (`s10118_result.txt:105`, banked
as measured in §8.1 `:1084`): the analytic and mixed bases on 31x17 read shapes that overlap by 12 %, so a `C2a` run
must report the same statistic for the patched build and the spread must be read at matched shape. **The value
`0.14619976001754773` is NOT used and must not be cited here**: §8.1 records it as CLOSED-UNRESOLVED, the archaeology
scan is negative (`.scratch/logs/corr_ez_followup.txt:117`, `:200`), and it is a re-openable locator, never a
measurement.

**Three values, three contexts -- and the difference between them is left standing.** The `corr_e_z` this section
gates on is the PMC pencil, **0.11916043239134175** (`.scratch/s10118_result.txt:105`); the PEC pencil
(`tools/host/c1-audit/pecbox_variant.py`) reads **0.147291446944630**, a genuine new measurement and not a corrected
version of the first; **0.14619976001754773** is retracted and cited nowhere. PMC mesh scatter is small -- 0.119160432391342
(31x17) against 0.119317006502073 (41x22), spread **1.5657e-4** (`.scratch/logs/corr_ez_followup.txt:205`, `:212`) --
but the PEC-minus-PMC shift is **0.028131014553288**, roughly 180x that spread, and it is **unresolved**: established
neither as a wall effect nor as a closed-box or convention artefact (the two pencils also differ in mesh, 1382 vs 1444
free edges). C2b's premise -- that `corr_e_z` is a stable, physics-carrying quantity able to carry an acceptance
threshold -- is therefore **not yet validated**, and it is settled, if at all, in `docs/design/c2b_preregistration.md`.

**Item 3 -- the guard, and the decision that keeps it exact.** `solve_modes_mixed` calls **both** assemblers and then
cross-checks them (`:1051-1052` then `:1053-1069`). Three checks: the edge numberings must agree (`:1053-1057`,
comparing `k_q.shape` against `m1.shape` and `m_eps.shape`); the `1/mu` mass must agree to **`1e-12` relative** --
`gap_mu > 1e-12 * max|m1|` raises (`:1058-1063`); and the `eps` mass must agree to the same **`1e-12` relative** --
`gap_eps > 1e-12 * max|m_eps|` raises (`:1064-1069`). Because `assemble_mixed` reaches `M_eps` **through** `assemble`
(`:505`), the two paths are not independent implementations but the same numbers computed once and twice, so the guard
passes *by construction* today. That is the property the patch is about to change. *Decision: apply the new attribution
rule to **both** paths, so the `1e-12` guard keeps holding exactly as it does today, and relax nothing.* The reasoning
is fail-closed: the guard is the *only* mechanical statement that the two paths agree, it is quoted as such upstream
(§7 item 3 puts the `c_f` identity and the Schur elimination out of scope on the strength of it), and a patch that makes
it fire would invalidate the comparison before the spread is measured -- the solve would raise, not report. **Option
(b)** -- apply the rule to one path and re-base the guard with an explicit reference split -- is **withdrawn as the
default**: it converts a hard structural guarantee into a tolerance, and every banked number in §1 came from a build in
which the guard was *passing*, i.e. in which both paths used the identical rule, so a split build would not be
comparable to the baseline it is being differenced against. *What breaks if this is wrong.* If the physics genuinely
requires the two paths to differ -- if, say, the mixed pencil's nodal `eps` block must keep the point rule while the
edge mass takes the dual one -- then applying the rule to both is the *wrong* patch, the guard becomes a false alarm
rather than a guarantee, and the build must fall back to option (b) with an explicit, documented reference split (which
path is the reference, which is the perturbation, and a tolerance stated per path). That failure mode is **detectable
statically, before any solve is spent**: if the two paths cannot be made to agree analytically for a test case with a
known interface, the "apply to both" decision is refuted.

**Item 4 -- the falsifier band, with its floor measured rather than assumed.** The band is derived from the geometry,
not chosen for comfort. The interface is the substrate top: contrast `4.4 - 1.0` = **3.4** in `eps_r`, and the
substrate occupies `h/H` = 0.0016/0.0076 = **21.05 %** of the box height. The largest `eps_eff` swing the attribution
rule can possibly reach is the whole substrate share mis-attributed at full contrast: `3.4 x 0.2105` = **0.7158**
absolute on `eps_eff`, which on the measured 3.6295122 is **+19.72 % on `eps`** and, since `eps = (beta/k_0)^2` so a
factor `(1+d)` on `beta` is `(1+d)^2` on `eps`, **+9.86 % on `beta`**. Against that ceiling:
* the **gap it must explain** is **+8.3434 % on `eps` / +4.09 % on `beta`** (§1.1, pair A, eigenvalue route), i.e.
  **0.3027** absolute on `eps_eff`, which is **42.3 %** of the 0.7158 ceiling -- a whole-cell-scale mis-attribution,
  not a sub-cell one. After §7.2 that 4.09 % carries a **term label**: it is 3.16 % of placement times 0.90 % of
  extraction, which is precisely why a spread of that size is being asked of a rule that acts on one interface only.
* the **kill floor** is `<= ~0.4 %` on `beta`, and it is **no longer an assumption**. Two independent codes on the same
  20 mm x 7.6 mm cross-section read `beta` **+0.3993 % apart** and `eps_eff` **+0.8001 % apart**
  (314.03158662735785 vs 312.7827646323; 3.658552575317196 vs 3.6295122080769704, §7.2 item 3), so ~0.4 % on `beta` is
  the *measured resolution* at which two solvers on this geometry stop distinguishing a construction from an
  extraction; `(1.004)^2 - 1` = **0.80 %** on `eps` reproduces it, i.e. **0.0291** absolute, **4.06 %** of the same
  ceiling. **This 0.3993 % / 0.8001 % pair replaces the unsourced "`<= ~0.4 %`" of the earlier text**, which asserted
  the floor without a provenance.
* *Verdicts, in advance, thresholds unchanged.* **Spread `>= ~2 %` on `beta`** (i.e. `>= ~49 %` of the gap, `>= 0.145`
  absolute on `eps_eff`, `>= 20 %` of the ceiling): `C2a` **is a substantial fraction of the answer** and the re-rank
  in §5 `D1` applies. **Spread `<= ~0.4 %` on `beta`**: `C2a` is a **4 %-of-ceiling correction on an 8.34 % gap** --
  arithmetically unable to produce it, and at that size indistinguishable from the cross-code floor itself -- killed
  exactly as §5 already preregistered, with the gap moving to `C2b`, `C1` or a reopened `C3`. **Between 0.4 % and 2 %**:
  partial -- report the fraction of the gap and re-rank against `C2b`; do **not** declare a verdict (§5 `D1`,
  unchanged). **Spread larger than the gap itself**: the baseline attribution is not the one that produced the banked
  number -- a **provenance** finding, reported before any percentage in §1 is re-read.
* *Sanity check on the ceiling.* 3.4 x 0.2105 = 0.7158 is the **whole-substrate** bound; the realistic mis-attributed
  volume is a band of triangles straddling `z = h`, so a measured spread anywhere near 9.86 % on `beta` would mean the
  rule changed substantially more than the interface, and should be treated as a bug report, not a result.

**Nothing in this subsection is authorised.** The patch is described on this page so its size can be judged, not so it
can be dispatched: **`C2a` is DEFERRED**, queued behind the `C1` audit for the reason §7 gives -- if `C1` is confirmed
the selection defect is the larger term, and a `C2a` spread measured against a mis-selected eigenvector would be
measuring the selector's error as much as the rule's.

**`C2b` pre-registration (recorded here, not authorised).** The surviving hypothesis after §7.2's decomposition is that
the *shape* defect and the residual are discretisation of the strip edge, not attribution at `z = h`.
* **HYPOTHESIS.** Graded / geometric refinement toward the strip edge moves the converged `beta` by **more than the
  0.3993 % cross-code `beta` agreement** (§7.2 item 3), in the direction of the FDTD value.
* **STEP 0 PREREQUISITE.** `corr_e_z` has **no established noise floor.** Before `C2b` can falsify anything, run
  *identical physics on two different meshes* and report the scatter of `corr_e_z`. Until that number exists any change
  in `corr_e_z` is uninterpretable; on `beta` the floor is known (0.3993 %), on `corr_e_z` it is not.
* **KILL CONDITION.** Refinement moves `beta` by **less than 0.3993 %** while `corr_e_z` moves by **more than its
  Step-0 scatter** -- the shape defect is then not a discretisation artefact, and `C2b` is dead.
* **CONFIRMATION.** `beta` moves by **more than 0.3993 % toward the FDTD value** *and* `corr_e_z` **decreases by more
  than its Step-0 scatter**.
* **WHAT IS NOT CLAIMED.** That `C2b` closes the 6.41 % analytic-internal `eps` gap -- that is §7.2 territory (placement
  versus extraction) and `C2b` says nothing about it. `C2b` addresses the surviving shape defect only.

### 7.4 `C2b` figure run -- what the mode plot measured, and what it did not

**STATUS.** Run, not designed, and not a `C2b` result. `tools/host/mode_plot/run.sh` executed `mode_plot.py` **once** at
git HEAD `295f344` (`mode_plot.log:8`), started `2026-10-27T03:17:02Z` (`mode_plot.log:7`), `exit=0` (`mode_plot.log:36`), **1.6 s** for the
plot inside **3 s** for the wrapper (`mode_plot.log:35`, `:36`). No assembly, no solve, no eigensolve: both spectra are
read from disk -- `c1_spectrum.npz` QZ col 738 (`mode_plot.log:17`) and `pecbox_spectrum.npz` QZ col 699
(`mode_plot.log:23`). It wrote two files and nothing else: `docs/design/c2b_shapes.pdf`, 100568 bytes
(`mode_plot.log:33`), and `.png`, 472872 bytes (`mode_plot.log:34`). Geometry is the standing 20 mm x 7.6 mm
cross-section: `width` 0.02, `height` 0.0076, `h` 0.0016, `strip` 0.003, `eps_r` 4.4, `strip_y` [0.0085, 0.0115]
(`mode_plot.log:16`).

No image was seen in producing this subsection. It was written by an agent with **no image capability**, from (i) the
numbers `mode_plot.py` printed and persisted to `mode_plot.log`, and (ii) the code that draws the panels.
`docs/design/c2b_shapes.pdf` (100568 bytes, `mode_plot.log:33`) and `.png` (472872 bytes, `mode_plot.log:34`) were never
opened by the author, and **no claim in this subsection derives from looking at them**; the human operator holds the only
view of those pixels.

**What the run measured.** Two configurations, one QZ column each, against one analytic reference:

| quantity | PMC / open top | PEC / closed box | source |
|---|---|---|---|
| mesh `h` / nnz | [483, 483] / 3141 | [422, 422] / 2726 | `mode_plot.log:18`, `:24` |
| `c_f` / nnz | [1444, 483] / 5431 | [1382, 422] / 4952 | `mode_plot.log:18`, `:24` |
| QZ column | 738 | 699 | `mode_plot.log:17`, `:23` |
| `beta` [rad/m] | 312.782765 | 311.772112 | `mode_plot.log:19`, `:25` |
| `beta^2` | 9.7833058e+04 | 9.7201850e+04 | `mode_plot.log:19`, `:25` |
| `eps_eff` | 3.6295122080769704 | 3.606094999644309 | `mode_plot.log:19`, `:25`, `:32` |
| `corr_e_y` | +0.920770784811142 | +0.912343044811209 | `mode_plot.log:20`, `:26` |
| `corr_e_z`, banked = reconstructed | +0.119160432391342 | +0.147291446944630 | `mode_plot.log:20`, `:26` |
| gauge sign applied | +1 | +1 | `mode_plot.log:21`, `:27` |
| rms `A_ez`, (201, 76) | 1.409797e-01 | 1.409797e-01 | `mode_plot.log:22`, `:28` |
| rms `e_z`, (201, 76) | 3.999873e+00 | 3.049101e+00 | `mode_plot.log:22`, `:28` |

Read off those rows, not printed by the run:
* `eps_eff` rel_delta **-0.006452** (`mode_plot.log:32`) = **-0.645 %**; the underlying `beta` step is **+0.324 %**
  (312.782765 / 311.772112 - 1). # derived from `mode_plot.log:19`, `:25`
* |`corr_e_z`| rel_delta **+0.236077** (**+23.61 %**, `mode_plot.log:31`); absolute step
  `0.147291446944630 - 0.119160432391342` = **0.028131014553288**. # derived from `mode_plot.log:31`
* the two **extracted** fields agree with each other at |corr| **0.932705** (`rel_rms` 0.366866, max|delta| 0.926972,
  `mode_plot.log:30`) while each agrees with the **analytic** field at only 0.119 / 0.147 (`mode_plot.log:20`, `:26`).
  `1 - |corr|` is **0.067** between the two panels against **0.881** and **0.853** against the reference -- a factor of
  **~13**, so the mismatch is dominated by extraction-versus-reference, not by mask-versus-mask. # derived from
  `mode_plot.log:20`, `:26`, `:30`
* `max|A_ez(PMC) - A_ez(PEC)| = 0.000e+00` (`mode_plot.log:29`): the two panels do **not** carry two analytic fields,
  they carry one, and the run says so in its own line.

**The four questions this figure was asked, and its four answers.**

**1 -- Is the extracted `e_z` the same object as the analytic `e_z`, i.e. is the reconstruction correct?**
**NOT ANSWERABLE BY THIS RUN.** The only agreement the run computes *against a stored reference* is a re-derivation:
`reconstructed` equals `banked` at `delta=0.00e+00` (`mode_plot.log:20`, `:26`), gated at `CORR_TOL = 1e-6`
(`tools/host/mode_plot/mode_plot.py:196`). That proves the diagnostic reproduces the banked statistic, not that the
banked statistic is right. Whether the reconstruction is correct is §0 Q1, settled by `S7`-`S9` on a *field*
comparison, not by a correlation against itself.

**2 -- Does the PEC mask change the extracted longitudinal field -- is the +23.61 % the wall?**
**NOT ANSWERABLE BY THIS RUN**, as an attribution, for a design reason: **three** variables move together between the
two panels -- the mask, the mesh (483 vs 422 free edges, `mode_plot.log:18` / `:24`) and the QZ column (738 vs 699,
`mode_plot.log:17` / `:23`). One observation of a three-way perturbation cannot assign the effect to any one of them.
What *is* measured, without attribution: |`corr_e_z`| 0.119160432391342 -> 0.147291446944630 (`mode_plot.log:31`) and
|corr| 0.932705 between the fields themselves (`mode_plot.log:30`). Note the direction -- closing the box *raises* the
agreement with the analytic reference (0.119 -> 0.147, `mode_plot.log:31`); a wall effect has to explain that sign,
and this run does not try. `mode_plot.py` keeps no region, band, quadrant or mask statistics at all, so the picture
cannot localise a wall term even by eye. # source: `tools/host/mode_plot/mode_plot.py:201-206` (the only builders are
`say` and a global `corr`), `:437-439` (the sole overlay is a strip line, drawn for orientation)

**3 -- Is the shape defect a discretisation artefact, i.e. does `C2b`'s hypothesis survive?**
**NOT ANSWERABLE BY THIS RUN.** §7.3's kill condition needs a refinement ladder and a Step-0 `corr_e_z` floor. This
run has neither: one mesh per configuration (`mode_plot.log:18`, `:24`), no refinement, no repeat statistic, and its
`beta` step of +0.324 % is *inside* the 0.3993 % cross-code floor (§7.2 item 3: two codes on one cross-section,
314.03158662735785 vs 312.7827646323) -- the floor behaving correctly, not evidence either way. `C2b` remains unexecuted.

**4 -- Does the 21-28x rms ratio between the analytic and the extracted field indicate a defect?**
**INFERENCE -- from code, not from this run.** 3.999873 / 0.1409797 = **28.4x** (PMC) and 3.049101 / 0.1409797 =
**21.6x** (PEC) # derived from `mode_plot.log:22`, `:28`. The ratio compares two arrays that are **not on a common
amplitude scale**, so it measures nothing:
* the extracted side is fixed only up to a unit **two-norm of the transverse edge vector**: `normalised = np.real(vecs)`,
  `norms = np.linalg.norm(normalised, axis=0)`, `normalised = normalised / norms` (:1127-1130), the convention of the
  QZ branch that produced these columns; `c1_audit.py` then re-normalises once more (`x = np.real(vecs_all[:, j])`,
  `x = x / nxv`, `tools/host/c1-audit/c1_audit.py:455-459`) before `e_z_node[free_n] = beta * z_free`
  (`tools/host/c1-audit/c1_audit.py:473`), mirroring `e_z[free_n] = 1j * beta * lu_h.solve(c_f.T @ x)` (:1175).
  **No unit-power, unit-peak or region-rms normalisation exists anywhere on that path.**
* the analytic side is one array, identical in both panels (`mode_plot.log:29`) and identical in rms
  (`mode_plot.log:22`, `:28`), carrying whatever normalisation `M.plane_mode` applies. **That convention was not read
  this block and is an open item, not an assertion.**
* the banked statistic is a **correlation**, and `corr(a, b)` is a normalised inner product over the whole array
  (`tools/host/mode_plot/mode_plot.py:206`), hence invariant to the sign and the scale of either argument. That is the
  correct choice, and it is why `corr_e_z` can be compared across the two panels while the rms values cannot. The one
  amplitude statement that *is* on a common convention is PMC-vs-PEC `e_z` rms, 3.999873 vs 3.049101 -- **+31.18 %**
  # derived from `mode_plot.log:22`, `:28` -- and it describes two different operators on two different meshes, not
  either field's physical amplitude.

**Names, as printed.** The run's two arrays are `A_ez` (analytic) and `e_z` (extracted)
(`tools/host/mode_plot/mode_plot.py:394-395`, printed at `mode_plot.log:22`, `:28`). A bare `e_z rms` quoted for the
analytic array is a relabelling the log does not make; **1.409797e-01 belongs to `A_ez`**, and the script prints no
phrase of the form "analytic e_z rms" anywhere.

**The three panel questions, asked literally, and why this run answers none of them.**

**1 -- "What structural features does the extracted `e_z` have that the analytic `e_z` does not?"** (peaks in different
locations, missing sign flips, non-decay at the top wall, amplitude blowup at the strip edges.)
**NOT ANSWERABLE BY THIS RUN**, on two independent grounds. (a) The panels were never seen (STATUS above). (b) No log
statistic can carry the answer: `corr` and `rms` reduce the whole (201, 76) array to one scalar each
(`tools/host/mode_plot/mode_plot.py:206`, `:221`), the only drawing calls are contours (`:415-417`) and a strip line
(`:437-439`), and nothing printed between `mode_plot.log:20` and `:31` is a per-row, per-column or per-region quantity.
The four properties named live in the pixels, and no step converts them back into numbers.
**What would answer it:** four masked reductions -- argmax index per band (peak location), sign-change count per row pair
per band (missing sign flips), `rms(e_z)` on the outermost row pair (non-decay at the wall), `rms(e_z)` on the two
strip-edge column groups (blowup). Bands below; their index bounds are UNKNOWN here.

**2 -- "Is the 37 % rms difference between PMC and PEC concentrated at any specific region -- strip edge, top wall,
substrate-air interface -- or is it uniform?"**
**NOT ANSWERABLE BY THIS RUN**, and this is the one that looks answerable. `rel_rms = 0.366866` (`mode_plot.log:30`) is a
**single whole-plane ratio**: `cross_rel = rms(cross) / sqrt(0.5*(rms(PMC)^2 + rms(PEC)^2))` with a global `rms`
(`tools/host/mode_plot/mode_plot.py:472`, `:221`). It carries no spatial decomposition -- the script never partitions the
array -- so it cannot say where the 37 % sits. The same line prints `max|delta| = 0.926972` (`mode_plot.log:30`), one
element whose *position* is not printed; it does not localise the difference either.
**What would answer it:** the band-share statistic below -- three numbers summing to 1.0.

**3 -- "Do both extracted fields share a structural feature absent from the analytic field? If so, name it."**
**NOT ANSWERABLE BY THIS RUN.** Naming a shared feature needs either the picture (not seen) or a decomposition into a
common part and a differential part. The run computes three whole-array scalars here -- |corr| = 0.932705 between the two
extracted fields (`mode_plot.log:30`) and 0.119160 / 0.147291 from each to the reference (`mode_plot.log:20`, `:26`) --
which rank the disagreement but cannot name anything.

**The one missing instrument, stated once; it is the same for all three.** Band-masked correlation and rms over three
regions fixed by cell index:

| band | definition | anchor |
|---|---|---|
| (i) strip edge | rows nearest `y = 0.0085` and `y = 0.0115` m, +/-2 cells each | `strip_y` (`mode_plot.log:16`); 0.0115 - 0.0085 = 0.003 m = `strip` # derived |
| (ii) top wall | outermost 2 columns (the `z` extreme) | open top (PMC) / PEC wall (`mode_plot.log:17`, `:23`); `H` = 0.0076 (`tools/host/c1-audit/out/run.log:22`) with column coordinate `zc_mid = (i+0.5)*CELL` (`tools/host/c1-audit/c1_audit.py:397`) leaves the wall beyond column 75 (z = 7.55e-3), so columns 74-75 # derived |
| (iii) substrate-air | columns nearest `z = h = 0.0016` m, +/-2 cells | `h` (`mode_plot.log:16`); `ZS[8] = HSUB` on the 17-node FEM z-axis (`tools/host/c1-audit/c1_audit.py:267`); with column coordinate `zc_mid = (i+0.5)*CELL` (`:397`) columns 15 and 16 straddle 1.6e-3 # derived |

Rows are axis 0 of the (201, 76) arrays, columns axis 1: `e_z` is `reshape(NYN, NZN-1)` of an interpolator over
`(ZS, XS)` (`tools/host/c1-audit/c1_audit.py:491-492`). **The indices are resolved, not deferred** -- row coordinate
`yn_node = i*CELL` and column coordinate `zc_mid = (i+0.5)*CELL` (`tools/host/c1-audit/c1_audit.py:394`, `:397`), with
`CELL` 1e-4, `ny` 200, `nz` 76, `H` 0.0076 and `h` 0.0016 (`tools/host/c1-audit/out/run.log:22`): strip edges at rows
**85** and **115** (0.0085/1e-4 and 0.0115/1e-4) # derived; top wall at columns **74-75** (last centre 7.55e-3, wall
7.6e-3) # derived; substrate-air interface at columns **15-16** (1.55e-3 and 1.65e-3, straddling 1.6e-3) # derived.
Reductions, per band and per configuration: masked `corr(A_ez, e_z)`, masked `rms(A_ez)`, masked `rms(e_z)`; across
configurations, masked PMC-vs-PEC `rel_rms` by the same formula as `:472` with the mask applied; and for question 2 the
**band share** `sum_band(delta^2) / sum_all(delta^2)` with `delta = e_z_PMC - e_z_PEC` after the gauge fix
(`mode_plot.log:21`, `:27`).
**Cost:** one re-run of `mode_plot.py` with the statistics added, **no new solve** -- both spectra are already on disk
(`mode_plot.log:17`, `:23`) -- hence seconds-scale, on the order of the 1.6 s the plot itself took (`mode_plot.log:35`).
**ESTIMATE -- not measured.** Not run this block: the execution container is stopped.

**"What field is the mixed solve producing?" -- one panel question with a numerical foothold, and its limit.**
The full question is not answerable here (question 3 above). A weaker statement is licensed by the log alone.
**INFERENCE -- from three scalars, not from the picture.** The two extracted fields agree with each other at
|corr| = 0.932705 (`mode_plot.log:30`); each agrees with the analytic reference at only 0.119160 and 0.147291
(`mode_plot.log:20`, `:26`). In `1 - |corr|` terms -- already tabulated above as 0.067 against 0.881 and 0.853 -- the two
panels are **~13x** closer to each other than either is to the reference # derived from `mode_plot.log:20`, `:26`, `:30`.
That is the signature of a **shared systematic component on the extraction path**, present under both wall conditions,
rather than of two independent local distortions: one field that is internally consistent and externally wrong, which is
what a formula or operator mismatch looks like.
**The limit.** This does **not** name the offending term, does **not** separate a `z_free` formula error from a `z_free`
operator error, and does **not** localise anything; naming it needs the band statistics above plus the §7.3 refinement
ladder.

**What this section does not establish.**
* Nothing about `C2b`. No refinement was run, no mesh scatter was measured, no `corr_e_z` noise floor exists (§7.3
  Step 0), and the figure is a rendering of two already-banked columns.
* Nothing about the wall's contribution to the shape defect: mask, mesh and QZ column are confounded (the design that
  would separate them is §7.3's "same physics, two meshes", and it was not this run).
* Nothing about amplitude in either direction. The 21-28x ratio is a scale mismatch between two differently
  normalised arrays; no physical normalisation of `e_z` was applied, banked or claimed.
* Nothing about `eps_eff` beyond restating it: -0.645 % (`mode_plot.log:32`) between a closed box and an open top is
  not a measurement of the 6.41 % analytic-internal gap, which is §7.2 territory.
* **No code was changed and no test was run to produce this subsection.** The two outputs are the pdf and the png
  (`mode_plot.log:33`, `:34`); the log is the evidence, and every number above is read from it or marked `# derived`.

**Insert note.** This subsection is an insert at line 1080, so every line number >= 1081 in this file moves down by
**179** lines. Bare `:NNNN` references throughout this document are to `emfit/mode2d.py` (the convention stated at the
head of `## 8`) and are unaffected. The document's one *self*-reference, `§8.1 `:1084`` at :995, now points into this
subsection and must be re-read against the shifted file; it already pointed at the blank line under `## 8.
Provenance` rather than at the §8.1 row it cites.

**Second shift, and it is this subsection's own.** The passage above accounts for one insert only. §7.5 was inserted
at :1260 of the 1,313-line file, exactly where that file's `---` stood, and occupies **112** lines here (:1269-:1380,
trailing blank included). This addendum is a second insert above it, of **9** lines (blank separator included), so
every line at or after the insert point has moved 112 + 9, and the three identities close: 1,313 + 112 + 9 = 1,434
lines in the file; 1,260 + 112 + 9 = :1381 for the `---` and 1,262 + 112 + 9 = :1383 for `## 8. Provenance`;
and the original (pre-first-insert) file's `---`, at :1081, is now at 1,081 + 179 + 112 + 9 = :1381. The
179-shifted lines above this subsection (:1081-:1259 of the 1,313-line file) have moved 179 only, and the
*self*-reference `§8.1 `:1084`` at :995 lies above both insert points, unaffected by either.

### 7.5 The two defects, decomposed -- one measured, one unowned

**Retraction.** An earlier phrasing of this diagnosis called the 21-28x rms ratio a second, *amplitude* defect -- the
extracted field 20-30x "too large". That framing is **withdrawn as wrong**, and §7.4 already refuses to make it (its
amplitude bullet, :1247-:1248). The two numbers are 3.999873 / 0.1409797 = **28.4x** (PMC) and 3.049101 / 0.1409797 =
**21.6x** (PEC) (`mode_plot.log:22`, `:28`, both `# derived`). Neither side of that ratio is on a physical scale:

* The extracted side is an eigenvector put on a **unit two-norm**, twice over: once per candidate in
  `emfit/mode2d.py:1127-1130` (`np.linalg.norm(..., axis=0)`, then divide), once on the edge vector in
  `tools/host/c1-audit/c1_audit.py:455-459` (`nxv = float(np.linalg.norm(x))`, then `x = x / nxv`). The longitudinal
  block inherits that scale and multiplies it by `beta` (`c1_audit.py:473`, `e_z_node[free_n] = beta * z_free`) with no
  re-normalisation anywhere downstream. So `e_z`'s magnitude is `beta` times an arbitrary constant; nothing in the
  pipeline ever asserts what it should be.
* The analytic side stands on `M.plane_mode`'s own convention. **OPEN ITEM:** that convention has never been read in
  this diagnosis. Until it is, `A_ez`'s rms of 1.409797e-01 (`mode_plot.log:22`, `:28`, identical in both panels per
  `:29`) has no stated meaning either.

A ratio of two conventions measures neither. The "20-30x excess" is not a physical claim that is merely unproven -- it
is the arithmetic of a unit-norm vector against an unrelated normalisation, so there is nothing there to prove.

**What the ratio does still say.** 3.999873 / 3.049101 = **+31.18 %** (`# derived` from `mode_plot.log:22`, `:28`). The
first version of this paragraph justified that as scale-free by pointing at `:29`, the shared analytic array, and the
justification was **wrong**: this quotient is extracted against extracted, so the analytic array is not in it and
cancels nothing. What cancels is the extraction's *own* arbitrary constant, and only because both extracted arrays were
put on unit two-norm by the same rule (`c1_audit.py:455-459`) and multiplied by the same post-factor (`:473`) before the
rms was taken -- one code, one run (`git HEAD 295f344`, `mode_plot.log:8`). **INFERENCE** -- +31.18 % is therefore a
statement about the two extracted norms *relative to each other*, inside one normalisation rule; it is neither absolute
amplitude nor physics. The one factor that does **not** cancel is `beta`, which moves +0.324 % between the panels
(below).

**The shape defect is untouched by all of this.** It is measured, it is what `C2b` is built to test, and it is
scale-invariant by construction: `corr` is a normalised inner product (`tools/host/mode_plot/mode_plot.py:206`), so
neither argument's scale enters it. `corr_e_z` = +0.119160 (PMC, `mode_plot.log:20`) and +0.147291 (PEC, `:26`) are
therefore as valid after the retraction as before it; correspondingly 1 - |corr| = 0.881 / 0.853 (`# derived`). The
retraction removes one of the two defects from the book; it neither re-opens nor re-grades the other, and §7.4's
STATUS block (:1083-:1096) is unchanged.

**The one piece of positive localising evidence, which the first version of this subsection omitted.** `corr_e_y` =
**+0.920771** (PMC, `mode_plot.log:20`) and **+0.912343** (PEC, `:26`) -- the same log lines as `corr_e_z`, on the same
two columns. The transverse component is recovered to ~0.92 while the longitudinal one sits at ~0.12-0.15: `1 - |corr|`
is **0.079** and **0.088** for `e_y` against **0.881** and **0.853** for `e_z` (`# derived` from `:20`, `:26`).
**INFERENCE** -- this is the only *localising* evidence the run contains. `e_y` and `e_z` come off one eigenvector, one
mesh, one gauge sign (`mode_plot.log:21`, `:27`) and one comparison code (`mode_plot.py:206`), so a failure common to
the extraction would pull `corr_e_y` down with `corr_e_z`; it does not. The defect is therefore not "the extracted mode
is wrong", it is confined to the longitudinal leg -- the extra solve `c1_audit.py:470-473` layers on top of `e_y` --
which is the most a correlation pair can say about location.
**Explicit limit, and it is a hard one.** This is **not** a defect location. The two correlations are not two
measurements of one quantity: `e_y` is the unit-two-norm edge vector (`c1_audit.py:455-459`) and `e_z` is one further
solve plus `beta` away from it (`:473`), so 0.92 and 0.12 are agreements of two *different* fields with two *different*
analytic components, and their gap bounds nothing numerically -- it is a qualitative contrast (component A survives,
component B does not), not a calibrated one. Both are bulk statistics over the whole 201 x 76 window, so neither says
*where* in the cross-section `e_z` departs, and §7.4 measured no band, quadrant or region statistic for `e_y` --
`mode_plot.py:201-206` keeps none. And 0.079 is not zero: `e_y` carries its own unexplained residual, with no noise
floor against which to call it small (§7.3 Step 0). Localise the *component*, not the term.

**INFERENCE -- the two objects are independent.** Shape lives in the direction of the array, amplitude in its norm.
`corr` is invariant to the scale of *either* argument (`mode_plot.py:206`), so a run can move `corr_e_z` with the norm
untouched, or move the norm with `corr_e_z` untouched. Nothing in the pipeline couples them except the normalisation
convention, and that convention is arbitrary (above). Consequence for the plan: a `C2b` result on `corr_e_z` is silent
about amplitude, and no number of refinement levels discharges an amplitude question. §7.4 question 4 states the same
split as a question; this subsection is the answer to the half of it that can be answered without new data.

**What the wall change tells us, and what it does not.** PMC vs PEC, all measured (`mode_plot.log:30`-`:32`):
|corr(e_z PMC, e_z PEC)| = 0.932705, rel_rms = 0.366866, max|delta| = 0.926972; `corr_e_z` rel_delta = +23.61 %;
`eps_eff` rel_delta = -0.645 %; `beta` 311.772112 -> 312.782765 = **+0.324 %** (`# derived` from `:25`, `:19`).
* It *tells* us the shape statistic is strongly wall-sensitive: +23.61 % in `corr_e_z` and 36.69 % in rms for a
  wall-only change, against -0.645 % in `eps_eff` and +0.324 % in `beta`. The wall is a first-order term for the shape
  defect, not a rounding detail.
* It *does not* tell us what the shape defect is made of: mask, mesh and QZ column stay confounded, exactly as §7.4
  records (:1245-:1246).
* It *does not* tell us anything absolute about amplitude. Even the relative +31.18 % carries a scale caveat:
  **INFERENCE** -- `beta` enters `e_z` multiplicatively (`c1_audit.py:473`) and itself stepped by +0.324 % between the
  panels, so a clean relative statement would hold `beta` fixed. At 0.324 % against 31.18 % that term cannot account
  for the move, but it is present and unremoved.

**What would make amplitude measurable.** Nothing here is a solver change; every item is a comparator or a piece of
bookkeeping.
1. **Read `M.plane_mode`'s normalisation** and state it beside the extraction rule. This closes the OPEN ITEM above and
   needs no run at all.
2. **Put `e_z` on one documented convention and apply it to both arrays at the comparison site** (unit power, unit peak
   or unit two-norm -- whichever the physics requires), not inside either solver, so the two sides are commensurable by
   construction instead of by hope.
3. **Print a scale-provenance line.** The log prints rms only (`:22`, `:28`) and never says which norm was applied
   where; one such line would have prevented the retracted claim.
4. **Compare against a case with a closed-form amplitude** -- the PEC box's standing wave has a known peak, so a ratio
   against it is a real excess rather than a mismatch of conventions. This is the only item that turns 28.4x / 21.6x
   into a measurement.
5. **For the wall term specifically: same mesh, one normalisation, both walls.** Otherwise the +31.18 % stays
   uninterpretable for the reason in the last bullet above, and remains confounded with the mesh term.

Cost: items 1 and 3 are a code read and a print line; the spectra item 5 needs are already on disk (`mode_plot.log:17`,
`:23`); the rest are one re-run on the scale of the plot itself (1.6 s, `mode_plot.log:35`). No new eigensolve is
implied by any of them.

**What this subsection does not establish.**
* Nothing about `C2b`. No refinement was run, no `corr_e_z` noise floor exists (§7.3 Step 0), and the +23.61 % is one
  three-way perturbation with no repeat; this subsection re-reads §7.4's numbers and adds no measurement.
* Nothing about the shape defect's *cause*. Mask, mesh and QZ column stay confounded, as §7.4 records (:1245-:1246),
  and the `e_y`/`e_z` contrast above localises the defect to the longitudinal *leg* only -- not to a term inside it.
* Nothing absolute about amplitude in either direction. The retraction removes a claim; it does not replace it with a
  measurement, and `M.plane_mode`'s normalisation remains an **OPEN ITEM** until it is read.
* Nothing about the transverse amplitude either: `corr_e_y` is scale-free for the same reason `corr_e_z` is, so ~0.92 is
  a shape statement about `e_y` and says nothing about its magnitude.
* Nothing about the +31.18 % beyond the caveat stated with it: `beta` is not held fixed across the two runs, and the
  runs differ in mesh, mask and QZ column as well, so neither factor is isolated.
* Nothing from the figures. `c2b_shapes.pdf` and `.png` (`mode_plot.log:33`, `:34`) were never opened by this author
  (§7.4), and no claim above rests on them.

**Status of this subsection.** Bookkeeping: it withdraws a framing, separates two objects that were being reported as
one, and lists what a measurement of the second would require. **No code was changed and nothing was run to produce
it** -- the container is stopped, and every number above is read from `mode_plot.log` or marked `# derived`.

---

## 8. Provenance

| artefact | identity |
|---|---|
| `emfit/mode2d.py` | `9b74d83d7b2c6b0df5b362a391df39dd8940378195b5faef1efe14d84febe032`, 1390 lines |
| `tools/corr_ez_101_20.py` | `a8cc0e9c4785211c957a81b0902c95015785026c2f6151124700f73b588e5456`, 729 lines |
| `.scratch/s10118_mixed_mode.npz` (31x17) | `8603e909dc2f99eff9505eae0cb344765b9d7628fc72ef28150fa197eacd2dff` |
| `.scratch/s10118_mode_41x22.npz` (41x22) | `b8e5c58a459b4230b03e26e77752b78c701dc1f47cf22d590491193278d7c4db` |
| evidence log | `.scratch/logs/corr_ez_followup.txt` (296 lines, 26 Oct 18:34) |
| capture driver | `.scratch/logs/s10118_basis.py` (464 lines) |
| geometry source | `.scratch/tol/logs/TOLFLUX.json` (`geometry`: h 0.0016, w 0.003, eps_r 4.4, n_sub 16) |
| ready-made TM harness | `.scratch/mode2d/c2_slab2.py` — `solve_modes_mixed` on a slab, `LX, LY = 0.4, 3.2`, `SUB_Y = 1.6`, `EPS_SUB, EPS_AIR = 4.4, 1.0`, 1608 edges / `free_e` 1592 / `free_n` 567, CASES `(k₀, β²/k₀²)` = `(3.0, 4.298278227712)`, `(2.095845021952, 4.196297158361)` |
| other scratch harnesses | `c2_ident.py` (independent elimination, `:396-397`), `c2_oldunits.py`, `c2_power.py`, `c2_static.py`, `c2_div.py` |

Line references are to `emfit/mode2d.py` unless another file is named. Key constants:
`_CURL_RTOL = 1.0e-10` (:131), `_MIXED_RESIDUAL_TOL = 1.0e-3` (:150), `_MIXED_DENSE_MAX = 3000` (:151).
Measured sizes: 31x17 — 1486 edges / 527 nodes / `c` (1486, 527) nnz 5852 / 496 vertical edge rows;
41x22 — 2581 edges / 902 nodes / `c` (2581, 902) nnz 10202 / 861 vertical edge rows.

### 8.1 Cited-value provenance (value · where used · source file:line · status)

Every number the argument turns on, with its locator and its standing. "measured" means read out of the banked
logs listed above; nothing in this table was recomputed for this note. A bare `:NNN` is a line in
`.scratch/logs/corr_ez_followup.txt` (the evidence log identified above).

| value | where used | source file:line | status |
|---|---|---|---|
| `3.3500085193` | the denominator of every % in §1, §1.1, §4 | `corr_ez_followup.txt:22` (key `eps_eff`) | **primary, reconciled** — the denominator used throughout |
| `3.564800282` | §1.1, pair **B**'s ε | `docs/design/modalport_ownership.md:7`; `decisions.md:6847` (`\| eps \| 4.205181853 \| 3.564800282 \|`) | **reconciled — pair B**, not an unreconciled rival. Its β counterpart is `309.981864` (`decisions.md:6846`, `\| beta \| 336.675159 \| 309.981864 \|`), and the pair closes under ε = (β/164.17940719617263)². Pair B is +6.41 % above pair **A** on ε. Percentages may be quoted against it **like-for-like** (fit route: +11.2 % on ε) and must not be crossed with A's counterpart |
| `3.32546` | `C3` / `D0`, §4 | §4 `C3` hand computation (Hammerstad/Jensen, w/h = 1.875, ε_r = 4.4) | closed form — **`D0` = PASS**. Recorded `3.325455` (`README_mode_profile.md:63`) and independently recomputed `3.324878` both sit **+0.7385 % / +0.756 %** below pair **A** (3.3500085193), i.e. inside a 1 %-class band. It is **0.74 % below A** and **6.7 % below pair B**, so it corroborates A's ε without adjudicating A vs B |
| `0.0272240` / `0.0264298` / `0.0253657` | `ratio_A`, §1 and §1.1 | `:60` / `:143`; `docs/design/normalization_scheme.md:86` | measured, unit-repaired, mesh-local — never mixed across meshes |
| `0.119160432391` | corr_e_z, 31x17 — §1, `S9` | `:205` | measured |
| `+0.920770784811` | corr_e_y, 31x17 — the `C1.1` assumption | `:43` | measured |
| `−0.938702180036` | corr_e_y, 41x22 | `:126` | measured |
| `+0.0` / `+3.951804e-02` | min/max of `z_free`, 31x17 — `S9` | `:39` | measured |
| `0.0000` | fraction of negative entries, 31x17 — `S9` | `:40` | measured |
| `0.000e+00` | `S8`, faithful operator, 31x17 | `:42` | measured |
| `8.484e-16` | `S8`, 41x22 | `:125` | measured |
| `+0.573448286090104` | corr(`z_free`, φ_analytic) — §2 | `:64` | measured |
| `0.122104587` | TE overlap, 41x22 — `S10` | `:169` / `:199` | measured |
| `0.772595941` | operator ceiling, 41x22 — `S10` | `:177` | measured |
| `0.984192` / `1.023362806` | ratio of magnitudes — `S10` | `:258` / `:181` | measured, but **not used as evidence** (see the `S10` correction) |
| `0.14619976001754773` | §C5, §7 | `:117` / `:200` — scan negative | **CLOSED-UNRESOLVED** — never quote as a measurement |
| `311.9553466185` | β, 41x22 — §1, §1.1 | `:120` | measured |

**Line-number reconciliation (`:224` vs `:225`).** `.scratch/logs/s10118_basis.py` is **464 lines**, and the
`np.abs` call sits at **:224**. `docs/design/modalport_ownership.md:37` cites `:225`; that is an **off-by-one**
against the 464-line file, i.e. the same reconciliation recorded for `S9` and the same conclusion (the `np.abs`
is a no-op on this data). Where a locator here and a locator in another note differ by exactly one line, this
note's is authoritative by construction — every line number in it was read against the file sizes recorded in
the table above.

## Amendment B1 -- 2026-10-27 -- the analytic array's scale convention

1. **What was open.** §7.4 :1164-:1165 "carrying whatever normalisation `M.plane_mode` applies. **That convention
   was not read this block and is an open item, not an assertion.**", restated at §7.5 :1282 and :1369. Read here,
   from source only: it closes the bookkeeping question, not the amplitude one.

2. **The finding: unit modal power over the projection window, not 1 V.** `emfit/mode_profile.py:18-23`: "The
   returned field carries exactly ``1 W`` of modal power through the **projection window** -- the clipped ``201 x 77``
   node plane that :meth:`ModeProfile.plane_window` copies into an FDTD grid", with `0.5 / eta_eff * (sum e_y^2 +
   sum e_z^2) = 1 W     on those slices only.` The class says it in bold: "**The field arrays are normalised to unit
   modal power over the projection window, not to 1 V.**" (:255), "Scale the fields by ``1 / v_mode`` to recover the
   1 V normalisation" (:264-265), `v_mode` = 9.9558 V (:261-263). The arrays are E . dl in volts, zeroed outside the
   clip that drops 1.164852 % of the power (:235-236, :600).

3. **Placement does not rescale.** `emfit/modal.py:290-300` is a pure copy -- `e_y = np.zeros((nyn - 1, nzn))`,
   `e_y[dst] = mode.e_y[src]`, `e_z[dst] = mode.e_z[src]`, `h_y[dst] = mode.h_y[src]` -- through slice pairs from
   `plane_window`, which returns slices only ("Slices placing this profile in an ``(nyn, nzn)`` FDTD plane.",
   `emfit/mode_profile.py:316-324`). No scalar appears in the function, so the placed array keeps the profile's own
   convention: 1 W through the window, zero outside.

4. **What it does not settle / what it does.** Not the 21-28x ratio: the extracted side is still on an arbitrary
   unit two-norm (§7.5 :1276-:1281), so :1286's "A ratio of two conventions measures neither" still holds. No
   quoted correlation needs repair, though: `def corr(a, b)` at `tools/host/mode_plot/mode_plot.py:206` returns
   `float(np.sum(a * b) / (na * nb))` (:220), `na`/`nb` the two two-norms (:216-217), so a positive scalar divides
   out; `corr_e_z`/`corr_e_y` are scale-free as :1370 says, and this convention cannot move one.

5. **Standing.** Bookkeeping **CLOSED**: unit modal power over the projection window, `power = 1 W`
   (`emfit/mode_profile.py:162`, `:250`), not the 1 V solve, copied and never renormalised. Amplitude **STILL OPEN**:
   no comparison of the two sides is licensed, here or by `C2b` Step 0 (`docs/design/c2b_step0_plan.md`, item 8);
   `A_ez`'s rms 1.409797e-01 has a stated convention but no physical reading.

6. **Pointer.** The convention itself, as opposed to this record of it, belongs in `docs/design/zfree_shape.md`
   (not yet written); when that note exists, this amendment is its citation for the analytic side.

