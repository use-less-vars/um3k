# The M3c gate, v2 — five clauses, audited against one rule

Design note. **No clause below is implemented, no gate in force is changed, and no solve was run for this note.**
Every number is either already banked in an artefact (cited `file:line`) or arithmetic performed on banked numbers.
Where a number could not be traced to an artefact it is marked `[untraced]` and is **not** adopted as a threshold.

The note does two things. It proposes the v2 clause set (§3), and it applies to that proposal the same test the
record has twice applied to itself by accident: **a clause that cannot fail cannot select** (§1). Two of the five
proposed clauses fail that test today (§6). Saying so is the point of writing this down before the code exists,
because a clause that cannot fail is indistinguishable from a passing clause in every report it will ever produce.

---

## 0. Status and scope

| | |
|---|---|
| what this is | a design note for the M3c gate at v2 |
| what changed in the tree | nothing |
| gates in force after this note | the same as before it |
| runs performed | none |
| artefacts written | this file only |

The v1 gate is `tools/gates_101_20.py` (three clauses, all written and all gated behind
`--i-understand-this-needs-a-solve`, `:15`) plus the two `corr_ez` clauses and the REPRO loop in
`tools/host/c1-audit/c1_audit.py`. §2 audits those against the rule. §3 states the v2 set. §4 records the places
where the record overrules the brief that prompted this note. §5 lists the numbers in the brief that could not be
traced. §6 is the self-audit: which v2 clauses still cannot fail, and why.

---

## 1. The rule, and the two times the record has already paid for it

> **A clause that cannot fail cannot select.**

The corollary is what actually bites, because it is checkable from the record alone:

1. a clause whose **predicate is true by construction** — satisfied by every input the pipeline can produce,
   either because the statistic is degenerate on that input or because the comparison is against the wrong
   quantity — selects nothing; and
2. a clause whose **threshold sits outside the range of the recorded population** — above every member of a
   `>=` screen, below every member of a `<=` screen — selects nothing on that population, whatever it would do
   on a hypothetical one.

Such a clause must be **withdrawn, named as non-selecting, or replaced** — the one thing that is not allowed is
leaving it in a gate list, where it reads as coverage.

The record contains two worked instances, one of each kind. They are not hypothetical.

**(a) The legacy `|corr_ez| <= 0.30` screen** — `CORR_EZ_MAX = 0.30`, `c1_audit.py:156`, applied in the legacy
criterion at `c1_audit.py:561-563`. The quantity it screens is `corr_ez_superseded_longitudinal`, the vertical
reference against the *longitudinal* field `beta*z_free`, and the recorded values on the mode of interest are
`0.1192` (current) / `0.1462` (superseded run) / `0.197856` (31x17 per-column oracle) / `0.199096` (41x22)
(`decisions.md:7308`, `:7917`; `docs/design/zfree_shape.md:84`). Every one of those sits a factor 1.5–2.5 *below*
the 0.30 bar. The bar cannot be violated by any leg in the population. `decisions.md:7938` says the consequence in
as many words: *"the screen was partly load-bearing — corr_e_y alone selected the mode, **corr_ez contributed
nothing**."* The name gives the game away: `MAX` is an **orthogonality** check ("the vertical field is roughly
transverse to the longitudinal one"), not a fidelity screen, and it was read as fidelity for as long as it existed.

**(b) The withdrawn T4 bands** — `R <= 1.0e-2` and `0.1 <= R <= 10` (`docs/design/modalport_ownership.md:192`;
`reports/2026-10-26_13-52-03_…:192`). `decisions.md:7256-7258` withdraws both: they are *"derived from nothing,
present in no implementation"*, present as prose only. The measured value is `2.72e6 / 2.64e6 / 2.54e6`
(`modalport_ownership.md:190`) — five to eight orders of magnitude outside **both** branches, so a run of that
test is a red result regardless of which branch is chosen (`modalport_ownership.md:196`). A threshold that every
possible measurement violates by five orders is not a screen; it is a restatement of a known defect. That is why
the bands were withdrawn rather than tightened, and §4 records the ruling that follows: **they must not be
reinstated at any value.**

Both instances share the failure mode this note exists to prevent: the clause was in a list, the list was read as
evidence, and no reader could tell from the output that one member of it was inert.

---

## 2. v1 as it stands, audited

### 2.1 `T1_stab` — can fail; bar is anchored to the population

| field | value |
|---|---|
| statement | `|beta_a − beta_b| / beta_a <= T1_tol`, all stations, all bases, three meshes (`decisions.md:7131-7133`) |
| implemented | `tools/gates_101_20.py:465` (`def T1_stab`), drop-nearest-station |
| threshold | `T1_TOL = 0.005` (`:132`) |
| provenance | **"measured, not derived"** (`:100-131`, STATUS line) |
| fails today? | not recorded |
| can it fail? | yes in principle — a station/mesh whose beta drifts by >0.5 % |

The rule's clause (2) is not violated (the bar is small and a real drift would breach it), but the bar is
*anchored to the measured spread* rather than derived from a resolution argument. This is the same self-reference
limit that `docs/design/corr_ez_vv_threshold.md` §3.2 states for the `corr_ez_vv` bar — *the scale is measured
from the legs the bar judges* — and it needs the same treatment: a stated derivation, or an explicit
re-base trigger.

One witness is visible and unevaluable. `T1_stab` raises `NotImplementedError` for `basis='mixed'` (`:486-493`),
and the audit note beside it records the mixed-window sensitivity as **3.06 / 2.99 %** with a **6.24 % span**
(`:486-493`). That span is 12× `T1_TOL`: a mixed-basis run would fail this clause by an order of magnitude — if it
could return a number. It raises instead. **An error is not a failure**, and a gate that can only raise on a
whole basis class is §1 corollary (1) in a mild form.

### 2.2 `T2_agree` — has a reachability defect and an unresolved gap

| field | value |
|---|---|
| statement | two independent beta estimates agree to `T2_TOL` |
| implemented | `tools/gates_101_20.py:544` (`def T2_agree`) |
| threshold | `T2_TOL = 0.005` (`:166`); closed at 0.005 by `decisions.md:7222-7228` |
| recorded gap | `beta_fit` vs `beta_eigen` **4.52 %** — nine times the tolerance (`:166` audit note) |
| fails on missing input | `ValueError` if the capture carries no `beta` (`:572-576`) |

Two problems, both of the §1 kind.

* **Reachability.** `TOLFLUX_planes.npz` carries `beta` with shape `(0,)`. On that artefact the clause can only
  raise (`:572-576`). A clause that raises on one of its own banked inputs, and whose only non-raising branch is
  untested for that input, selects nothing on it.
* **A 4.52 % gap against a 0.5 % tolerance.** Either the clause rejects the current population by a factor of
  nine, or the 4.52 % figure is a different pairing from the one the clause compares. The audit note does not say
  which, and this note will not guess. It is listed as an open item in §6.4, because a gate whose pass/fail state
  on the banked population cannot be determined from the record is in the same practical class as one that
  cannot fail.

### 2.3 `T3_scale` / `T3_ey_slot` — implemented, narrow

| field | value |
|---|---|
| registered id | `§101.20.T3_scale` (`decisions.md:7129`) |
| implemented as | `tools/gates_101_20.py:713` (`def T3_ey_slot`) |
| threshold | `T3_TOL = 1e-5` (`:221`); definition (ii) adopted at that value (`decisions.md:7254`) |
| what it gates | **only** the `plane_Ey` slot (`:758-762`); detection is half-open (`>= tol`) |
| sensitivity ladder | `:224` — the flux route is blind at `1.0256e-8` |

The ladder is the useful part: the flux route's floor is three decades below the bar, so the flux route cannot
contribute a near-threshold failure; the clause's discriminating power lives entirely on the plane route, and the
one failing leg the record knows about is an `e_z` leg which this clause does not look at. See §3.3 for the
naming contradiction, which is registered and real.

### 2.4 The two `corr_ez` clauses

* **`corr_e_y` vs `CORR_EY_MIN = 0.90`** (`c1_audit.py:155`) — this is the clause that did the selecting
  (`decisions.md:7938`). It can fail: `PEC col704` records `corr_e_y = −0.426418989`, i.e. `|·| = 0.426`, far below
  0.90. Falsifiable, with a witness. The constant's *value* is a round number and is superseded by the derived bar
  in §3.3; its *role* is sound.
* **`corr_ez_vv` vs `CORR_EZ_VV_MIN = 0.91`** (`c1_audit.py:175`) — the corrected criterion at `:557-559`. This one
  is now derived, not borrowed: `corr_ez_vv_threshold.md` §2 gives `S_good = 0.948530101525844 − 0.9352867303487647
  = 0.0132433711770793`, `T = L − 2·S_good = 0.9087999879946061`, rounded **up** to `0.91`; the rounding delta is
  `0.0012000120053939 = 0.0906·S_good`, a tightening. Falsifiable, with a witness: `PEC col704` records
  `|corr_ez_vv| = 0.083134346`, which the comment block at `c1_audit.py:158-174` quantifies as sitting **62.4
  spreads below** the bar, against passing legs at 1.91 / 2.91 / 2.03 spreads above it. **This clause satisfies the
  rule**, and the shape of its derivation — population, spread, `k=2`, round-up — is the template §3.3 reuses.

### 2.5 `REPRO` — satisfies the rule, and is the one clause with a witness *in history*

`c1_audit.py:722-733` recomputes `e_y` against `ANCHOR_CORR_EY` (`:151`, `0.9207707848111418`) and `e_z` against
`ANCHOR_CORR_EZ` (`:152`, `0.11916043239134175`) and fails on a relative delta beyond `REPRO_RTOL = 1e-6`
(`:182`). The comment at `:177-181` states the intent and the witness: the statue's own drift scale is **2e-2** —
the superseded run records `0.1462` (`.scratch/logs/mesh51.log:18`) against the current `0.1192` — and a `1e-6`
bar is four decades tighter than that. The drift happened, so the clause has been exercised; it is not merely
believable, it is known-falsifiable. This is the standard the other clauses should be held to.

---

## 3. The five v2 clauses

Each block gives: statement, the measured quantity and how it is constructed, the threshold **with its
provenance**, the named failing witness (a measurement already in the record that the clause rejects), reachability
(can it pass — can it fail), and implementation status.

### 3.1 `T1_stab` — stability of the propagation beta

| field | value |
|---|---|
| statement | `|beta_a − beta_b| / beta_a <= 0.005` for all stations, bases, and the three meshes |
| quantity | beta from the drop-nearest-station variant (`gates_101_20.py:465`) |
| threshold | `T1_TOL = 0.005`, `gates_101_20.py:132`, provenance **"measured, not derived"** (`:100-131`) |
| failing witness | none banked. The nearest thing is the mixed-basis window, **6.24 % span** (`:486-493`), which raises rather than evaluates |
| can pass | yes |
| can fail | yes in principle; no recorded failure |
| status | **implemented** (`gates_101_20.py:465`), behind `--i-understand-this-needs-a-solve` (`:15`) |

Action for v2: keep the clause, but either derive the tolerance from the resolution study or publish a re-base
trigger, so that the bar is not silently re-measured into whatever the population does next. Also either make
`basis='mixed'` evaluable or state in the gate output that the basis is unscreened — the current
`NotImplementedError` (`:486-493`) reads in the log as neither pass nor fail.

### 3.2 `T2_agree` — two estimators of the same beta agree

| field | value |
|---|---|
| statement | `|beta_fit − beta_eigen| / beta_eigen <= 0.005` |
| quantity | fit-derived beta vs eigen-derived beta |
| threshold | `T2_TOL = 0.005`, `gates_101_20.py:166`; closure recorded at `decisions.md:7222-7228` |
| recorded gap | **4.52 %** (`:166` audit note) — resolving factor unknown (§6.4) |
| failing witness | the 4.52 % gap **if** it is the same pairing; the record does not establish that |
| can pass | undetermined on the banked population |
| can fail | yes in principle; must not raise instead — see the `(0,)`-shape `beta` defect (`:572-576`, `TOLFLUX_planes.npz`) |
| status | **implemented** (`gates_101_20.py:544`), behind the solve flag |

### 3.3 `T3_ey` — the in-plane correlation bar

| field | value |
|---|---|
| statement | `|corr(A_ey, e_y)| >= 0.89` |
| quantity | `corr_e_y` as constructed at `c1_audit.py:412-432` / `:520-521` (analytic in-plane reference against the solver's own in-plane component, same lattice) |
| threshold | **0.89**, derived: `0.9207707848111419 − 2 × 0.017931395224757 = 0.8849079943616279`, rounded up to 0.89 |
| provenance | `docs/design/corr_ez_vv_threshold.md:303-307` (§9), which flags the value *"for the M3c gate; not changed here"* |
| population | the **two PMC mesh legs**: `max|corr_e_y| = 0.938702180035899`, `min|corr_e_y| = 0.920770784811142` (`docs/design/zfree_shape.md:77`, row M2), both on the corrected metric |
| failing witness | **`PEC col704`, `corr_e_y = −0.426418989`** → `|·| = 0.426`, i.e. **0.46 below** the bar (`corr_ez_vv_threshold.md` §2 population table) |
| can pass | yes — the two PMC legs sit at 0.9208 / 0.9387, above 0.89 |
| can fail | yes — with a recorded witness, by a wide margin, not a near-threshold artefact |
| status | **design-only** as a threshold. The statistic and the screen exist at `CORR_EY_MIN = 0.90` (`c1_audit.py:155`); adopting 0.89 is a one-constant change to a clause already in force |

**The 0.89 is reproducible, and it is a two-leg number.** Re-derive it: `0.938702180035899 − 0.920770784811142 =
0.017931395224757` is exactly `max|corr_e_y| − min|corr_e_y|` over the **two PMC mesh legs** — the same population
*shape* `S_good` uses in `corr_ez_vv_threshold.md` §2 — and `0.9207707848111419 − 2 × 0.017931395224757 =
0.8849079943616279 → 0.89`. That is the correct arithmetic and it stands.

It is **not** a four-leg number. A wider population exists in the record — `{0.920770784811142, 0.938702180035899,
0.912343044811209}` plus the failing `0.426418989` — and including `0.912343044811209` gives `max − min = 0.026359135224690`
and `0.912343044811209 − 2 × 0.026359135224690 = 0.859624774361829 → 0.86`. So **the wider population yields 0.86**
(see §5: this is very probably where the brief's `0.86` came from, and it belongs to *this* clause, not to a fringe
clause). Two reasons not to adopt it:

* it is **looser** (0.86 against 0.89) — widening a population cannot be allowed to loosen a bar; the tightening
  convention in `corr_ez_vv_threshold.md` §2 exists precisely to prevent that;
* the leg that widens it, `0.912343044811209`, has a **disputed `e_y` attribution**: `docs/design/zfree_shape.md:77`
  (M2) labels it 41x22, while `decisions.md:8004-8005` records the **41x22** leg's `corr_e_y` as
  `−0.9387021800358988` — so one of those two labels is wrong and this is a live label defect on the `e_y` side.
  It is a **different, still-open** instance from the `0.119317007` case, which is settled and superseded (§4.1);
  the *shape* of the two defects is nonetheless the same — a label, not a measurement (`decisions.md:8012`).

**Ruling for v2:** adopt 0.89 from the two clean PMC mesh legs, and pre-register the `0.912343044811209` leg as a
*future* re-base input once its attribution is settled — do not use it to set the bar while it is disputed.

**Naming.** The record registers `§101.20.T3_scale` (`decisions.md:7129`); the code function is `T3_ey_slot`
(`gates_101_20.py:713`); this note's brief says `T3_ey`. v2 adopts **`§101.20.T3_ey`** and states plainly that it
**renames a registered id** — it is not a new clause. Note the substantive limit of that rename: `T3_ey_slot`
gates a **scale** ratio at `1e-5` on the `plane_Ey` slot only (`:221`, `:713`), whereas this clause gates a
**correlation** at 0.89 on `corr_e_y`. Those are different statistics. The rename carries the id, not the
definition; if the team wants both, the `1e-5` scale clause needs its own id and the correlation clause should be
registered as new. Overloading `T3_*` across two statistics would repeat the `T1`/`T2` collision already
recorded at `decisions.md:7268` (`T1`/`T2` collide with window lengths at `:4854`, `8926*dt` / `8928*dt`).

### 3.4 `T4_amp` — relative amplitude of the vertical component

| field | value |
|---|---|
| statement | **none exists.** `decisions.md:7258` reserves the criterion as *"the placed route's component ratio within X per cent of the analytic ratio on the same lattice, X from the resolution study"* and **proposes no X** |
| quantity | `R = Σ(e_z²) / Σ(e_y²)` on the placed blocks after the common normalisation (`s10118_basis.py:371-373`; `modalport_ownership.md:190`), invariant under the common scale |
| threshold | **none.** The placeholder bands `R <= 1e-2` / `0.1 <= R <= 10` are **withdrawn** (`decisions.md:7256-7258`); `R_CIRC = 1.0847420002436303` is a diagnostic only (`:7262`), `R_FLUX = 0.9687210847256866` is demoted to a cross-check (`:7264`) |
| recorded value | `2.72e6 / 2.64e6 / 2.54e6` (`modalport_ownership.md:190`) — with the caveat at `:198` that name, comment and sampling disagree |
| failing witness | not applicable — there is no threshold for a measurement to miss |
| can pass | **nothing to pass** |
| can fail | **no** — see §6.1 |
| status | **design-only, and must stay so**; `T4_amp` appears in no `.py` file in the tree |

The blocker is not a missing tolerance; it is a **missing numerator**. `decisions.md:7950-7956` (§5.2): the
`0.0272` ratio on record is *longitudinal*-over-in-plane, `e_z_vv` appears nowhere in it, and *"What the true
vertical-over-in-plane energy ratio is has not been computed."* Until that ratio is measured on the same lattice,
any X would be a number with nothing to compare to — which is exactly the defect that got the old bands withdrawn.

### 3.5 `T5_fringe` — the fringe-localisation clause

| field | value |
|---|---|
| statement | proposed: the fringe band's local correlation with the analytic field `>= 0.86` |
| quantity | local `corr` inside the strip `1.5 < |y−10| <= 3.1` (mm), from the deficit decomposition at `decisions.md:7958-7972` |
| threshold | **0.86 `[untraced]`** — proposed in the brief that prompted this note, present nowhere in the tree and derived from nothing (§5) |
| recorded measurements | `PMC col738`: local corr **+0.8628**, `57.0 %` of the deficit, excess **2.85**. `PEC col699`: **+0.8653**, `57.9 %`, excess **2.89** (`decisions.md:7958-7972`; `reports/2026-10-27_16-16-34_…:77-91`) |
| failing witness | **none.** Both recorded fringe correlations sit *above* 0.86 |
| can pass | yes — both legs do, by 0.0028 and 0.0053 |
| can fail | **not on any measurement in the record** — see §6.2 |
| status | **registered nowhere.** `T5_fringe` is new; it appears in no `.py` file (344 searched) and in no markdown |

The decomposition it would gate is genuinely the most informative thing the record has produced about the vertical
field: the `6.2 mm` band is `13 %` of the modelled y-extent, carries `57–58 %` of the deficit at `15 %` of the
analytic energy, peak deficit density sits `0.4–0.8 mm` **outside** each edge, and the in-plane field's `8 %`
deficit is flat by contrast — *"the in-plane field's 8 % deficit is a distributed amplitude error; the vertical
field's 6.5 % deficit is a concentrated edge error"* (`decisions.md:7972`). That contrast is the finding. A
**correlation** bar is the wrong instrument for it: the fringe correlates at 0.86 *while carrying 2.85× its share
of the energy*, so the defect is in the energy share and the excess ratio, both of which are already recorded and
both of which would fail a bar set anywhere near `1.0`. If this clause is to exist, its statistic is the excess
ratio, not the correlation.

---

## 4. Record wins over brief

| # | the brief says | the record says | ruling for v2 |
|---|---|---|---|
| 1 | `T4_amp` has a band (`R <= 1e-2` / `0.1 <= R <= 10`) | both bands **withdrawn**: *"derived from nothing, present in no implementation"*; criterion reserved with **no X proposed** (`decisions.md:7256-7258`) | **the bands are not reinstated at any value.** `T4_amp` ships with no threshold |
| 2 | `T3_ey`'s derived bar rests on a four-leg population | the derivation in the record is over the **two PMC mesh legs** (`corr_ez_vv_threshold.md:303-307`); the four-leg variant gives 0.86 and depends on a leg whose attribution is disputed | adopt **0.89**, two-leg; 0.86 is the wider-population variant and is held pending attribution |
| 3 | `T5_fringe` threshold `0.86` | the `0.86` has **no lineage in the record at all**: it was a design proposal made in the brief, formed by rounding the observed `+0.8628` down to `0.86`. It is not a transcribed record number, not derived, and was never adopted. The only `0.86` strings in the tree are unrelated (a `0.86 deg` standing-wave bound, `decisions.md:30` / `:191`; a *"backward ratio of 0.86"* tied to SWR ≈ 13, `:2660`) | **`[untraced]`** — not adopted. See §5 |
| 4 | `T3` is named `T3_ey` | registered as **`§101.20.T3_scale`** (`decisions.md:7129`); implemented as `T3_ey_slot` (`gates_101_20.py:713`) | adopt `§101.20.T3_ey` and record it as a **rename of a registered id** (§3.3) |
| 5 | `T5_fringe` extends the registered set | `T4` itself is registered with **no gate in code** (`decisions.md:7268`, `:7129`); `T5_fringe` is registered nowhere | `T5_fringe` is **new**, not a revival — it needs a fresh registration if it ships at all |
| 6 | a two-mesh convergence claim for the `e_z` leg | the 41x22 run **exists** (`.scratch/s10118_mode_41x22.npz`) and `0.119317007` is settled as its column-1318 baseline value (`decisions.md:7998-8016`); `:7936` survives only in its literal wording — no 41x22 `corr_ez` **array** is stored, the number is recomputed on demand. But both meshes' baselines are the *same void statistic* (`:8014`) | no two-mesh convergence claim: the second mesh exists and carries the same mis-paired quantity, so its agreement is about that quantity, not about fidelity. Every `e_z` statement in v2 is single-mesh and labelled so |
| 7 | the vertical-over-in-plane amplitude is a known quantity | *"What the true vertical-over-in-plane energy ratio is has not been computed"* (`decisions.md:7950-7956`) | `T4_amp` stays deferred; no numerator is inferred from `0.0272`, which is longitudinal-over-in-plane |
| 8 | the audit trail is a converging series | *"six small numbers not a converging series"* (`decisions.md:7974`) | no clause in v2 may be justified by "it moved the right way" |

### 4.1 Two record entries that are already superseded

Three of the citations a reader will find in §3.3 and §5 point at entries the log has since resolved. They are kept
rather than deleted, because the *way* they were resolved is the useful part.

| entry | what it said | what supersedes it |
|---|---|---|
| `decisions.md:7982` | `0.119317006502073` is "the **41x22** leg … **But** `zfree_shape.md:68` uses `0.119317007` as the **31x17 legal-operator baseline**. **Both attributions cannot hold.** Unresolved." | **`decisions.md:7998-8016`** ("RESOLUTION: the `0.119317007` double attribution", commit `f693d87`). The value is the **41x22 baseline code-path `corr_e_z`, column 1318**, exact repr `-0.11931700650207343`. One attribution; open item 7.3 closed |
| `decisions.md:7936` | *"no 41x22 corr_ez leg is banked anywhere"* | **`decisions.md:8010`.** The 41x22 **run** exists (`.scratch/s10118_mode_41x22.npz`: `xs (41,)`, `zs (22,)`, `col = 1318`, `beta = 311.95534661849416`, `eps_eff = 3.6103349900617117`, `n_edges = 2581`, `n_nodes = 902`). What is absent is a stored 41x22 `corr_ez` **array** — which is all `:7936` literally claimed. It survives on that literal wording and **must not be read as "no 41x22 mesh exists"** |
| `docs/design/zfree_shape.md:473` | *"`0.119317007` is used here as the 31x17 legal-operator baseline"* | **`decisions.md:8012` / `:8016`.** That sentence is a paraphrase error; `zfree_shape.md` never made that assignment — its M1 row (`:76`, pre-pass `:68`) already pairs `0.119317007` with **41x22** against `0.117276695` **31x17**. `:473` repeats the erroneous paraphrase and was left uncorrected under the append-only rule |

**The lesson worth keeping: the defect was in a *label*, not in a measurement** (`decisions.md:8012`). The baseline
**code-path** figure (`-|beta*z_free|`) is `-0.119317006502073`; the **legal-operator** figures are
`-0.117276694616091` (31x17) and `+0.122104586573519` (41x22). The M1 row paired a code-path value on one mesh
against a legal-operator value on the other, which is exactly why the label looked coherent and the mesh
disagreement looked real. Two consequences for this note: nothing in §1-§5 of *this* file rested on which mesh a
`0.119`-class baseline sat on (both meshes carry the same mis-paired statistic, and that identity is what voided
the metric — `decisions.md:8014`); and the fact that *this* class of defect produces a confident, coherent-looking
contradiction is the reason §3.3 refuses to set a bar from a leg whose *label* is unsettled.

---

## 5. Numbers in the brief that could not be traced

| number | where the brief uses it | trace result | consequence |
|---|---|---|---|
| **`0.86`** | `T5_fringe` threshold | **`[untraced]` — origin known, lineage absent.** It was **proposed in the brief that prompted this note**, formed by rounding the observed fringe measurement `+0.8628` down to `0.86`. It is *not* a transcribed record number, it is *not* derived, and it was never adopted. No `0.86` threshold exists in any `.py` or `.md`; every `0.86` string in the tree is unrelated: `0.86 deg` (standing-wave bound, `decisions.md:30`, `:191`) and `"backward ratio of 0.86"` with SWR ≈ 13 (`:2660`) | **not adopted** for `T5_fringe`. Worth knowing anyway: the *same two digits* also fall out of an **unrelated** construction — `0.912343044811209 − 2 × 0.026359135224690 = 0.859624774361829 → 0.86`, the `k=2` round-up rule on the **wider `|corr_e_y|` population** (§3.3). That is a **coincidence between two unrelated constructions**, not an origin story for either: someone will land on `0.86` again, and it will not mean the fringe clause justified it |
| **`X` in `T4_amp`** | "within X per cent of the analytic ratio" | **no X is proposed anywhere** (`decisions.md:7258`) | none available; clause cannot ship |
| **`0.161983870` vs `0.197856`** | per-column `corr_ez` oracle | **contested**: `docs/design/zfree_shape.md:84` and `:417` record `0.161983870`; `decisions.md:7308` records `0.197856` (31x17) and `0.199096` (41x22); the mismatch is *"pre-existing"* and deliberately not reconciled (`reports/2026-10-27_16-16-34_…:176`) | neither value may be used as a threshold or a population member. Marked **contested** |
| **`0.119317007`** | `e_z` baseline | **settled, not contested**: it is the **41x22 baseline code-path `corr_e_z`, column 1318** (`decisions.md:7998-8016`; repr `-0.11931700650207343`). The earlier "31x17 legal-operator baseline" attribution was a paraphrase error at `decisions.md:7982`, repeated uncorrected at `zfree_shape.md:473`; the residual defect is a **label** (baseline code path vs legal operator), not a mesh (`:8012`) | usable as a *measurement*, never as a threshold input: it is an `e_z` quantity and it is the **mis-paired** statistic. It enters no `T3_ey` population (§3.3), which is `e_y` |
| **`0.0272`** | vertical-over-in-plane ratio | it is **longitudinal**-over-in-plane; `e_z_vv` appears nowhere in it (`decisions.md:7950-7956`) | not a `T4_amp` input |

---

## 6. Self-audit: which v2 clauses still cannot fail

This is the section the rule exists to produce. Applied honestly, **two of the five v2 clauses fail it today**,
and one more has an undetermined state.

### 6.1 `T4_amp` — no threshold, no witness, no numerator

`decisions.md:7258` reserves the criterion and proposes no X; the placeholder bands are withdrawn; the measured `R`
is `2.72e6 / 2.64e6 / 2.54e6` against a unit-order analytic ratio that *does not exist in the tree*. There is
nothing for a measurement to miss. By §1 corollary (1) this clause cannot select, and by corollary (2) it would
reject everything by five to eight orders if a band were invented — which is the same defect stated the other way.
**Verdict: still cannot fail. Do not ship.**

### 6.2 `T5_fringe` at 0.86 — no recorded measurement misses it

Both recorded fringe correlations are **above** the bar: `0.8628` and `0.8653`, by `0.0028` and `0.0053`. There is
no failing witness, and the number has **no lineage at all** besides the brief that proposed it (§5) — so the verdict
rests on the measurements, not on a challenge to the number's provenance. Two further problems:

* The one leg that *would* be the interesting witness — `PEC col704`, the leg that already fails both `corr_e_z`
  clauses — has **no fringe decomposition computed** in the record. The decomposition exists only for the two
  *passing* legs (`PMC col738`, `PEC col699`). So the clause's only plausible falsifying case is uncomputed.
* The statistic is aimed at the wrong quantity: at `0.8628` local correlation the fringe still carries **2.85×**
  its share of the analytic energy. A correlation bar set at 0.86 passes a leg that the record has already
  established is the *site* of the defect (`decisions.md:7970`). The clause would report green on the known fault.

**Verdict: as a 0.86 correlation clause, it cannot fail. Do not ship in that form.**

### 6.3 The `k=2` round-up convention is not usable at fringe-scale spreads

Worth stating numerically, because it is the obvious way someone will try to *derive* a fringe bar from the two
recorded values.

The convention from `corr_ez_vv_threshold.md` §2 is `T = L − k·S`, `k = 2`, then **round up** to 0.01. On the
fringe population `S = 0.8653 − 0.8628 = 0.0025`:

| choice of `L` | `T = L − 2S` | rounded up | verdict |
|---|---|---|---|
| `L = 0.8628` (lower leg) | `0.8578` | **0.86** | passes both legs, by ≤0.0053 |
| `L = 0.8653` (higher leg) | `0.8603` | **0.87** | **rejects both its own legs** (`0.8628 < 0.87`) |

`L = 0.8653` is listed **only to exhibit the convention's failure mode**, not as a candidate derivation: a lower
bound has to admit the lowest leg of the population it judges, so `L = 0.8628` is the only admissible choice — and
that row shows the admissible choice is too loose to select anything, since both legs clear `0.86`.

The rounding quantum (`0.01`) is **four times** the entire observed spread (`0.0025`). Round-*up* is a deliberate
tightening at `corr_ez_vv`'s spread (it cost `0.09·S_good` there, `corr_ez_vv_threshold.md` §2); at this spread it
can push the threshold above a leg it is supposed to admit. **The convention is not scale-free and must not be
applied mechanically.** Any fringe bar needs its own derivation and its own stated rounding rule, not this one.

### 6.4 `T2_agree` — undetermined, not inert

The 4.52 % measured gap against a `0.005` tolerance is a factor of nine. Either the clause fails the banked
population, or the figure describes a different pairing. **The record does not decide this**, and this note will not
invent the answer. Until it is decided, `T2_agree`'s state on the population it would gate is unknown; combined
with the `(0,)`-shape `beta` defect (`:572-576`), the clause is better described as *unreachable* than as
*passing*. Item for the owner: state which two quantities the 4.52 % compares, and either re-close the tolerance or
fix the pairing.

### 6.5 What survives clean

* `T3_ey` at **0.89** — derived, population stated, and with a wide-margin failing witness (`PEC col704`,
  `|corr_e_y| = 0.426`). **Can fail.**
* `corr_ez_vv` at **0.91** — derived, population stated, failing witness at 62.4 spreads below the bar
  (`c1_audit.py:158-174`). **Can fail.**
* `REPRO_RTOL = 1e-6` — falsifiable, and exercised in history by the `0.1462 → 0.1192` drift
  (`c1_audit.py:177-181`). **Can fail.**
* `T1_stab` at `0.005` — can fail in principle; the bar needs a derivation or a re-base trigger, and the
  `basis='mixed'` branch needs to evaluate rather than raise (`:486-493`).

---

## 7. Sites: where each clause lives, or would live

| clause | statistic is computed at | threshold lives at (or would) | status |
|---|---|---|---|
| `T1_stab` | `tools/gates_101_20.py:465` | `tools/gates_101_20.py:132` (`T1_TOL = 0.005`) | implemented, behind the solve flag (`:15`) |
| `T2_agree` | `tools/gates_101_20.py:544` | `tools/gates_101_20.py:166` (`T2_TOL = 0.005`) | implemented; reachability defect at `:572-576` |
| `T3_ey` (scale spelling) | `tools/gates_101_20.py:713` (`T3_ey_slot`) | `tools/gates_101_20.py:221` (`T3_TOL = 1e-5`) | implemented |
| `T3_ey` (correlation spelling, v2) | `c1_audit.py:412-432`, `:520-521` | would be `c1_audit.py:155` (`CORR_EY_MIN`, currently `0.90` → `0.89`) | **design-only**; one-constant change |
| `corr_ez_vv` | `c1_audit.py:557-559` (criterion), arrays at `:633-634` | `c1_audit.py:175` (`CORR_EZ_VV_MIN = 0.91`) | in force; second use site `tools/host/c1-audit/pecbox_variant.py:511-513` |
| `corr_e_y` (legacy) | `c1_audit.py:561-563` | `c1_audit.py:155` (`CORR_EY_MIN = 0.90`) | in force, superseded in value by §3.3 |
| `corr_ez` (legacy, non-selecting) | `c1_audit.py:561-563` | `c1_audit.py:156` (`CORR_EZ_MAX = 0.30`) | in force, **non-selecting** (§1(a)); recorded at `decisions.md:7938` |
| `REPRO` | `c1_audit.py:722-733` | `c1_audit.py:182` (`REPRO_RTOL = 1e-6`) | in force |
| `T4_amp` | `s10118_basis.py:371-373` (R); no gate site | nowhere | deferred; registered, no code (`decisions.md:7268`) |
| `T5_fringe` | deficit decomposition only, ad hoc, `decisions.md:7958-7972` | nowhere | **new**; unregistered; cannot fail as specified (§6.2) |

---

## 8. What is not claimed

None of `T1_stab`, `T2_agree`, `T3_ey_slot` has been run as part of this note (they require
`--i-understand-this-needs-a-solve`, `gates_101_20.py:15`). No tolerance in this note has been validated by a new
solve. The 0.89 in §3.3 is arithmetic on two banked numbers, not a measurement. `T4_amp` and `T5_fringe` are
proposals in prose with no implementation, and §6 argues that both should stay that way in their present form.
