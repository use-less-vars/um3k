# The M3c gate, v2.1 — five clauses, audited against one rule

**v2.1 revision (this file is not append-only; the changes are listed, not silently patched).** Three changes
against v2, plus the tally they move.

1. **Ids.** The correlation clauses are registered in the `§101.20.T5_*` family — `§101.20.T5_ey_corr`
   (§3.3), `§101.20.T5_ez_corr` (§3.6), `§101.20.T5_fringe_excess` (§3.5). v2's ruling that the
   in-plane clause should be adopted as `§101.20.T3_ey` and described as a *rename* is **withdrawn**: `T3` is
   already `§101.20.T3_scale` (`decisions.md:7129`), a different statistic, and it keeps the id.
2. **Open items closed, or narrowed to one question each.** `T2_agree`'s "undetermined pairing" (§6.4) and
   `T4_amp`'s "missing numerator" (§6.1) are both re-stated against arithmetic on banked arrays
   (`docs/design/t4_amp_ratio.md`). `T2_agree` is now a clause that fails on one of two fits; `T4_amp` now has its
   analytic ratio and still has no extracted ratio to compare it with.
3. **The in-plane bar is in force, not proposed.** `CORR_EY_MIN = 0.89` at `c1_audit.py:234`, with its derivation in
   the comment block above it (`:216-233`). The change moves one constant and, as a side effect, the floor of the
   superseded `shape_pair_ok_legacy` screen; no recorded verdict flips.
4. **Tally.** At v2, two of five clauses could not fail (§6). At v2.1, one cannot (`T4_amp`, §6.1) and one is
   red on the recorded population (`§101.20.T5_fringe_excess`, §6.2). The fringe clause changed verdict because
   its **statistic** changed, not its threshold — the distinction §1 exists to enforce.

Unchanged in v2.1: `T1_stab`, `T3_scale`, `REPRO`, the two `corr_ez` clauses of §2.4, and every citation.
Still true after v2.1: **no gate was run and no solve was performed for this note.**

Design note. **No solve was run for this note.** One constant did change — `CORR_EY_MIN = 0.89` (§3.3, item 3 of the revision note) — and everything else below is design, not code. Every number is either already banked in an artefact or arithmetic performed on banked numbers.
Where a number could not be traced to an artefact it is marked `[untraced]` and is **not** adopted as a threshold.

The note does two things. It proposes the v2 clause set (§3), and it applies to that proposal the same test the
record has twice applied to itself by accident: **a clause that cannot fail cannot select** (§1). Two of the five
proposed clauses failed that test at v2 (§6). The v2.1 revision above replaces the *statistic* of one of them
rather than its threshold, which moves the tally to one — and that replacement is the only reason to believe the
new count, because relabelling a number cannot produce it. Saying so is the point of writing this down before the
code exists, because a clause that cannot fail is indistinguishable from a passing clause in every report it will
ever produce.

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

**(a) The legacy `|corr_ez| <= 0.30` screen** — `CORR_EZ_MAX = 0.30`, `c1_audit.py:235`, applied in the legacy
criterion at `c1_audit.py:728-730`. The quantity it screens is `corr_ez_superseded_longitudinal`, the vertical
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

### 2.2 `T2_agree` — a reachability defect explained, and a gap that is real

| field | value |
|---|---|
| statement | two independent beta estimates agree to `T2_TOL` |
| implemented | `tools/gates_101_20.py:544` (`def T2_agree`) |
| threshold | `T2_TOL = 0.005` (`:166`); closed at 0.005 by `decisions.md:7222-7228` |
| recorded gap | `beta_fit` vs `beta_eigen` **4.52 %** (`:166` audit note) — the fit is `326.9107654423116` against an eigenvalue of `312.7827646322591` (`out/c1_spectrum.npz:beta`, column 738), nine times the tolerance. A second fit, `TOLFLUX.json:beta = 314.03158662735785`, sits **0.40 %** above the same eigenvalue (`docs/design/t4_amp_ratio.md:37`, `:41`) |
| fails on missing input | `ValueError` if the capture carries no `beta` (`:572-576`) |

Two problems. The first is a §1 defect of the fixable kind; the second is a plain failure, once the fit is named.

* **Reachability — the `(0,)` is a serialisation choice, not a missing measurement.** `TOLFLUX_planes.npz` carries
  `beta` with shape `(0,)` because the tone dump that builds it writes *empty* frequency arrays by design
  (`emfit/studies.py:3242-3246`: `freqs=np.empty(0)`, `spectra=np.empty((0, spec.size))`), so every
  frequency-indexed key in that artefact is empty, not `beta` alone. The beta the clause needs **is** banked — in
  `TOLFLUX.json`. The raise is therefore fixable by one line of I/O, without a solve; v2's *"selects nothing on it"*
  overstated a defect of the wrong kind.
* **A 4.52 % gap against a 0.5 % tolerance, with the fit identified.** `docs/design/t4_amp_ratio.md:37` gives
  `beta_fit = 326.9107654423116` against `beta_eigen = 312.7827646322591`: `4.516873 %`, and
  `gates_101_20.py:552` calls that outcome *intended*, as do `decisions.md:7371` and `:7375`. A second fit of the
  same eigenvalue exists — `TOLFLUX.json:beta = 314.03158662735785`, `0.399262 %` high, *inside* the tolerance with a
  1.25× margin. So the honest state is not "undetermined pairing": **on the scored fit the clause fails by 9.03×**,
  and it passes on the other one. What remains open is narrower (§6.4): which fit the gate is scored on is not
  settled by the banks (`docs/design/t4_amp_ratio.md:50`; `decisions.md:7680`) — and a 4.1 % spread between two fits of
  one eigenvalue, against a 0.5 % tolerance, is a defect the record has not named.

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

* **`corr_e_y` vs `CORR_EY_MIN`** (`c1_audit.py:234`; `0.90` when §2 was written, `0.89` in v2.1) — this is the clause that did the selecting
  (`decisions.md:7938`). It can fail: `PEC col704` records `corr_e_y = −0.426418989`, i.e. `|·| = 0.426`, far below
  0.90. Falsifiable, with a witness. The constant's *value* is a round number and is superseded by the derived bar
  in §3.3; its *role* is sound.
* **`corr_ez_vv` vs `CORR_EZ_VV_MIN = 0.91`** (`c1_audit.py:255`) — the corrected criterion at `:724-726`. This one
  is now derived, not borrowed: `corr_ez_vv_threshold.md` §2 gives `S_good = 0.948530101525844 − 0.9352867303487647
  = 0.0132433711770793`, `T = L − 2·S_good = 0.9087999879946061`, rounded **up** to `0.91`; the rounding delta is
  `0.0012000120053939 = 0.0906·S_good`, a tightening. Falsifiable, with a witness: `PEC col704` records
  `|corr_ez_vv| = 0.083134346`, which the comment block at `c1_audit.py:237-254` quantifies as sitting **62.4
  spreads below** the bar, against passing legs at 1.91 / 2.91 / 2.03 spreads above it. **This clause satisfies the
  rule**, and the shape of its derivation — population, spread, `k=2`, round-up — is the template §3.3 reuses.

### 2.5 `REPRO` — satisfies the rule, and is the one clause with a witness *in history*

`c1_audit.py:977-985` recomputes `e_y` against `ANCHOR_CORR_EY` (`:191`, `0.9207707848111418`) and `e_z` against
`ANCHOR_CORR_EZ` (`:192`, `0.11916043239134175`) and fails on a relative delta beyond `REPRO_RTOL = 1e-6`
(`:262`). The comment at `:257-261` states the intent and the witness: the statue's own drift scale is **2e-2** —
the superseded run records `0.1462` (`.scratch/logs/mesh51.log:18`) against the current `0.1192` — and a `1e-6`
bar is four decades tighter than that. The drift happened, so the clause has been exercised; it is not merely
believable, it is known-falsifiable. This is the standard the other clauses should be held to.

---

## 3. The five v2 clauses

Each block gives: statement, the measured quantity and how it is constructed, the threshold **with its
provenance**, the named failing witness (a measurement already in the record that the clause rejects), reachability
(can it pass — can it fail), and implementation status.

There are **six** blocks. Five are the v2 clause set this file counts §6 against; the sixth (§3.6) is a
**registration**, not a proposal — the statistic, the population and the bar are already in force in code and it is
named here only so that the register has one row per gated quantity.

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
| recorded gap | **4.52 %** on the scored fit: `beta_fit = 326.9107654423116` vs `beta_eigen = 312.7827646322591` → `4.516873 %` (`4.321669 %` taken on the fit) = **9.03× `T2_TOL`**. A second fit, `TOLFLUX.json:beta = 314.03158662735785`, sits `0.399262 %` above the same eigenvalue — inside the tolerance, 1.25× margin |
| failing witness | **yes, and it is the scored fit**: the 4.52 % gap, 9.03× the tolerance. Recorded as *intended* at `gates_101_20.py:552`, `decisions.md:7371`, `:7375` |
| can pass | yes — on the `TOLFLUX.json` fit (`0.40 %`) |
| can fail | yes — and it does, on the `c1_spectrum` fit. It must not *raise* instead: see the `(0,)`-shape `beta` defect (`:572-576`, `TOLFLUX_planes.npz`), whose cause is `emfit/studies.py:3242-3246` |

### 3.3 `§101.20.T5_ey_corr` — the in-plane correlation bar

| field | value |
|---|---|
| statement | `|corr(A_ey, e_y)| >= 0.89` |
| quantity | `corr_e_y` as constructed at `c1_audit.py:679-694` / `:694` (analytic in-plane reference against the solver's own in-plane component, same lattice) |
| threshold | **0.89**, derived: `0.9207707848111419 − 2 × 0.017931395224757 = 0.8849079943616279`, rounded up to 0.89 |
| provenance | `docs/design/corr_ez_vv_threshold.md:303-307` (§9), which flags the value *"for the M3c gate; not changed here"* |
| population | the **two PMC mesh legs**: `max|corr_e_y| = 0.938702180035899`, `min|corr_e_y| = 0.920770784811142` (`docs/design/zfree_shape.md:77`, row M2), both on the corrected metric |
| failing witness | **`PEC col704`, `corr_e_y = −0.426418989`** → `|·| = 0.426`, i.e. **0.46 below** the bar (`corr_ez_vv_threshold.md` §2 population table) |
| can pass | yes — the two PMC legs sit at 0.9208 / 0.9387, above 0.89 |
| can fail | yes — with a recorded witness, by a wide margin, not a near-threshold artefact |
| status | **in force**, not design-only. `CORR_EY_MIN = 0.89` at `c1_audit.py:234`, derivation in the comment block above it (`:216-233`), screen applied at `:724-730`. The side effect is stated in that comment: the same constant is the floor of the *superseded* `shape_pair_ok_legacy` screen, so that floor moves `0.90 → 0.89` with it; no recorded verdict flips (passing legs 0.92 / 0.94, witness 0.43) |

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

**Ruling, carried out.** 0.89 from the two clean PMC mesh legs is now the constant in the tree (`c1_audit.py:234`);
the `0.912343044811209` leg is pre-registered as a *future* re-base input, not used while its attribution is disputed.

**Naming (revised in v2.1).** v2 adopted `§101.20.T3_ey` and described it as a *rename of a registered id*. That
was wrong and is withdrawn. `§101.20.T3_scale` (`decisions.md:7129`) gates a **scale** ratio at `1e-5` on the
`plane_Ey` slot only (`gates_101_20.py:221`, `:713`); this clause gates a **correlation** at 0.89 on `corr_e_y`. Those
are different statistics, so the id cannot be carried across: `T3` stays with the scale clause, unchanged, and this
clause is registered **fresh**, in the `§101.20.T5_*` family, as **`§101.20.T5_ey_corr`**. Overloading `T3_*` across
two statistics would repeat the `T1`/`T2` collision already recorded at `decisions.md:7268` (`T1`/`T2` collide with
window lengths at `:4854`, `8926*dt` / `8928*dt`) — which is the concrete reason not to do it, not a matter of taste.

**0.89 is the looser of the two correlation bars, and that is deliberate.** Since v2.1 the sibling clause
`§101.20.T5_ez_corr` (§3.6) sits at `0.91` (`CORR_EZ_VV_MIN`, `c1_audit.py:255`). The pair invites the reading "0.89
and 0.91, so one is a typo or one is a tightening that was not carried across" — it is neither. The two numbers differ
because *everything* behind them differs: the statistic (`corr_e_y` against the analytic in-plane reference vs
`corr_ez_vv` against the corrected vertical reference), the population, and the spread (`S = 0.017931395224757` here
vs `S_good = 0.0132433711770793` there). Neither is derived from, rounded from, or reused from the other, and the
in-plane bar is not supposed to be the tighter one.

### 3.4 `T4_amp` — relative amplitude of the vertical component

| field | value |
|---|---|
| statement | **none exists.** `decisions.md:7258` reserves the criterion as *"the placed route's component ratio within X per cent of the analytic ratio on the same lattice, X from the resolution study"* and **proposes no X** |
| quantity | `R = Σ(e_z²) / Σ(e_y²)` on the placed blocks after the common normalisation (`s10118_basis.py:371-373`; `modalport_ownership.md:190`), invariant under the common scale |
| threshold | **none.** The placeholder bands `R <= 1e-2` / `0.1 <= R <= 10` are **withdrawn** (`decisions.md:7256-7258`); `R_CIRC = 1.0847420002436303` is a diagnostic only (`:7262`), `R_FLUX = 0.9687210847256866` is demoted to a cross-check (`:7264`) |
| recorded value | `2.72e6 / 2.64e6 / 2.54e6` (`modalport_ownership.md:190`) — with the caveat at `:198` that name, comment and sampling disagree |
| analytic ratio (v2.1) | **`R_analytic = Σ A_ez² / Σ A_ey² = 3.036149093425e+02 / 1.080440832223e+02 = 2.810102138752`** (per-sample `2.832912603875`, amplitude ratio `√R = 1.676336`) — computed in `docs/design/t4_amp_ratio.md` from the banked arrays |
| failing witness | not applicable — there is no threshold for a measurement to miss |
| can pass | yes on both sides now — `R_analytic` and a PMC `R_extracted` both exist — but with no `X` there is still no clause to pass |
| can fail | **no** — the extracted ratio now exists, but with no threshold there is nothing for a measurement to miss; see §6.1 |
| status | **design-only, and must stay so**; `T4_amp` appears in no `.py` file in the tree. **Both sides cleared in v2.1**: numerator and PMC extracted ratio now exist; the threshold does not |

The blocker **was** not a missing tolerance but a **missing numerator**. `decisions.md:7950-7956` (§5.2): the
`0.0272` ratio on record is *longitudinal*-over-in-plane, `e_z_vv` appears nowhere in it, and *"What the true
vertical-over-in-plane energy ratio is has not been computed."* Until that ratio is measured on the same lattice,
any X would be a number with nothing to compare to — which is exactly the defect that got the old bands withdrawn.

**v2.1: both halves of the ratio now exist, and the clause still cannot ship.** `docs/design/t4_amp_ratio.md` forms what
`decisions.md:7950-7956` said had not been computed, on already-banked arrays: `R_analytic = 2.810102138752` (above). What
is missing is no longer *data*: `R_extracted` **is** banked in both spectra, and on the PMC leg (j = [738], the identified
column) it is `4.0489791163982565`, which against `R_analytic = 2.8101021387524523` is `1.441×`. The PEC leg's ratio is
`R = 4.163656524825077` at its identified column `699` (`1.482×`); what `pecbox_spectrum.npz` *banks* is `70.635018555128326`,
the last *scanned* column (`704`, the failing witness, `beta = 86.93931629`) — a wrong-column artefact, not the leg's value, whose
attribution to `704` is inference from `j` beside `ok` (`c1_audit.py:207-210`), not a per-column bank. Only the PMC figure is *scored*. `TOLFLUX_planes`' pooled `3.439935` (per-sample `3.467858`, per station `3.101484 … 3.620866`) is an
FDTD tone capture of a different quantity, **not** substitutable: it would place the analytic mode `18.3 %` below the
extraction and invite an `X` calibrated on it. So the defect changes shape again: `T4_amp` no longer lacks a measurement, it
lacks a **threshold** — a rule for how far `1.441×` may sit from `1`. That is a choice, not a datum, and it is unmade. One
more non-use of `0.0272`: `2.810102 / 0.0272240 = 103.2` is arithmetic, since `0.0272` is longitudinal-over-in-plane and
`e_z_vv` appears nowhere in it (`decisions.md:7950-7956`).

### 3.5 `§101.20.T5_fringe_excess` — the fringe excess-energy clause

| field | value |
|---|---|
| statement | the fringe band's share of the modal deficit is at most **`2.0x`** the geometric mean of its share of the analytic energy and its share of the extracted energy |
| quantity | `ex_fringe = D_R / sqrt(A_R · E_R)` on the region `1.5 < |y−10| <= 3.1` (mm), from the deficit decomposition at `decisions.md:7958-7972`: `D_R` is the region's share of `1 − corr`, `A_R` / `E_R` its shares of the analytic and the extracted energy |
| provenance | the **statistic** is the record's, not this note's (`decisions.md:7958-7972`; restated `docs/design/t4_amp_ratio.md:31-33`). The **bar is new** and derived below; no threshold for this statistic exists anywhere in the tree |
| recorded measurements | `PMC col738`: `0.570 / sqrt(0.1474 × 0.2716) = **2.849**` from `D = 0.570`, `A = 0.1474`, `E = 0.2716`, local corr `+0.8628`. `PEC col699`: `**2.89**`, `57.9 %` of the deficit, local corr `+0.8653` (`decisions.md:7958-7972`; `reports/2026-10-27_16-16-34_…:77-91`) |
| threshold | **`2.0`**, derived: `1 + (ex_min − 1)/2 = 1.9245` (PMC) / `1.9450` (PEC), rounded **up** on the `0.1` grid → `2.0` |
| failing witness | **the two recorded legs themselves**: `2.849` and `2.89`, i.e. **`1.42x`** and **`1.45x`** the bar. This is the only v2 clause whose witness is already in the record and already failing |
| can pass | yes — a region carrying its deficit in proportion to its energy scores `1.0`, and the in-plane field's own fringe sits at `0.85–0.91` on this statistic (`decisions.md:7974`), so the bar is not vacuous in the sense of being unreachable from below |
| can fail | **yes, and it does**, on both recorded legs. The two legs are different solvers (PMC / PEC) and their excesses differ by `1.4 %` — roughly forty times less than the margin to the bar, so the red verdict is not a near-threshold artefact of one run |
| status | **new, design-only; registered in §9, implemented nowhere.** No `.py` file computes this statistic; `T5_fringe` in its old correlation form is **withdrawn** (§6.2) |

**The statistic changed; the number did not survive the change.** v2's `T5_fringe` gated the fringe's *local
correlation* at `0.86`. The threshold was the smaller of its two problems. A correlation bar set near the fringe's own
value reports green on the known fault: the fringe correlates at `+0.8628` **while carrying `2.85x` its share of the
energy**, which is exactly what `decisions.md:7970` identified as the defect. So what moved is the statistic, and
`0.86` is neither re-used nor re-derived — on this statistic a `0.86` bar is not even dimensionally expressible,
because the excess has a baseline at `1.0` and no ceiling.

**A correction to v2's own wording.** v2 called `2.85x` *"2.85x its share of the analytic energy"*. It is not. `2.85`
is measured against the **geometric mean** of the analytic- and extracted-energy shares
(`.scratch/d22_t3_regions.py:104-105`, read-out `:195-197`; `docs/design/t4_amp_ratio.md:33`). Against the analytic
share alone it is `0.570/0.1474 = 3.867`; against the extracted share alone `0.570/0.2716 = 2.099`. The three readings
sit `42 %`, `93 %` and `5 %` above a `2.0` bar, so the verdict survives the mislabel — but only one of the three
is the statistic on record, and a threshold justified on the wrong denominator would have been justified by a number
nobody measured.

**Where `2.0` comes from.** The statistic's neutral value is `1.0`: a region whose deficit share equals the geometric
mean of its energy shares is losing field in proportion to the field it has (`docs/design/t4_amp_ratio.md:33`). The
defect is therefore a **multiple of a baseline**, not a bound on a spread, and the `L − k·S` convention that
serves the two correlation clauses is not available here for a reason §6.3 states: it produces a *lower* bound,
which is the wrong direction for a clause that has to reject the population it was read off. Taken instead as an
interval from the `1.0` baseline to the lower of the two measurements, the midpoint is `1 + (2.849 − 1)/2 =
1.9245` (PMC) and `1 + (2.89 − 1)/2 = 1.9450` (PEC); rounded **up** on the `0.1` grid that is `2.0`. The rejected
alternative, `ex/2 = 1.425`, halves one measurement instead of taking the midpoint of the interval from the baseline:
it would pass a region at `1.5x` its share, which is not "in proportion to the field", and it has no baseline in it at
all. Witness margins: `2.849/2.0 = 1.42x`, `2.89/2.0 = 1.45x`.

**The verdict does not depend on `2.0`, and that is the honest way to state it.** Any bar in `(1.0, 2.849)` is red on
both recorded legs; any bar at or above `2.849` is green on both. `2.0` is the midpoint-rounded member of that open
interval, and its status is *a stated policy inside an interval whose every member gives the same verdict on the
record* — not a value recovered from the data. The only bar that would make this clause **pass** is one set at or
above its own measurement, which is bar-fitting; the record has already paid for that once (§1).

**What is still missing — the same gap as §6.2.** The decomposition exists for the two legs that pass every
other clause (`PMC col738`, `PEC col699`). `PEC col704`, the leg that fails both correlation bars, has **no fringe
decomposition computed**. So the clause is red on the healthiest measurements in the record and unmeasured on the one
leg whose failure it was built to explain, and two readings follow that the record cannot separate: (i) the vertical
field has a concentrated edge defect on *both* meshes and *both* solvers, which is what `decisions.md:7972` says in
words, and the clause is reporting it; (ii) the bar is too tight and rejects a field the rest of the register accepts.
Reading (i) is favoured by the `1.4 %` PMC/PEC agreement and by the geometry: the band is defined by the
inequality `1.5 < |y−10| <= 3.1` mm (the `13 %`-of-the-modelled-y-extent figure that used to be quoted here is
withdrawn — it has no denominator that reproduces, see `decisions.md`), carries `57–58 %` of the deficit at
`15 %` of the analytic energy, peak deficit density sits
`0.4–0.8 mm` **outside** each strip edge, the first cell outside the edge already carries `3 %` of the deficit at
excess `0.87`, and the first `0.80 mm` accumulates `0.5169` at `0.0209/mm`. That is an edge-localised error profile,
not a mesh artefact. But (i) is a reading, not a measurement, and a fringe decomposition of `PEC col704` is the
measurement that would settle it. Until then the clause ships **red**, and a clause that ships red is not the same
thing as a clause that has been validated (§8).

**Why this statistic and not something simpler.** Because it separates the two defects the record contrasted at
`decisions.md:7972`: *"the in-plane field's 8 % deficit is a distributed amplitude error; the vertical field's 6.5 %
deficit is a concentrated edge error. Those are different defects and they are now separately visible."* One number,
two verdicts, out of arrays that are already banked. One flag, not resolved here: on the in-plane field the same
statistic rises to `2.1–2.4` in the outermost cell of the domain (`decisions.md:7974`). That cell lies outside the
`1.5 < |y−10| <= 3.1` band this clause gates, so it enters no population above — but it would fail a `2.0`
bar, and whether it belongs in some clause's population is an open question this note does not answer.

### 3.6 `§101.20.T5_ez_corr` — the vertical-field correlation bar

| field | value |
|---|---|
| statement | `|corr(A_ez, e_z_vv)| >= 0.91` |
| quantity | `corr_ez_vv`, the **same-component** vertical correlation: analytic `A_ez` against the solver's own vertical transverse field (`c1_audit.py:687-695`). **Not** `corr_ez_superseded_longitudinal`, the mis-paired number the legacy `0.30` screen still uses (§2.4) |
| threshold | `CORR_EZ_VV_MIN = 0.91`, `c1_audit.py:255`; derived `T = L − k·S_good`, `k = 2`, round **up** to `0.01`: `S_good = 0.948530101525844 − 0.9352867303487647 = 0.0132433711770793`, `T = 0.9352867303487647 − 0.0264867423541586 = 0.9087999879946061 → 0.91` |
| provenance | `docs/design/corr_ez_vv_threshold.md` §4 (derivation) and §9 (the cross-reference to the in-plane bar) |
| population | the three passing legs: `31x17 PMC` `0.935286730348765` (col 738), `41x22 PMC` `0.948530101525844` (col 1318), `31x17 PEC` `0.936929717079781` (col 699) |
| failing witness | `31x17 PEC col704`, `|corr_ez_vv| = 0.083134346` → **62.436 spreads below** the bar |
| margins | passing legs at `+1.909`, `+2.909`, `+2.033` spreads above it. The round-up to `0.91` cost `0.0012000120053939 = 0.0906·S_good`, and **no banked leg lies in `[0.9087999879946061, 0.91)`**, so on this population the rounding costs nothing |
| can pass | yes — all three population legs do |
| can fail | yes — with a witness `62` spreads wide, not a near-threshold artefact |
| status | **in force**, not a proposal: criterion at `c1_audit.py:724-726`, second use site `tools/host/c1-audit/pecbox_variant.py:511-513` |

**This block is a registration, not a decision.** The statistic, the population and the bar all pre-date this note and
are in force in code; v2.1 adds the id so that the register carries one row per gated quantity. Nothing about the gate
changes because it is named, which is why it is not one of the five clauses §6 counts.

**Why one family name and two ids.** `T5_ey_corr` (§3.3) and `T5_ez_corr` are the same construction applied to
two different fields: a lower bound set `k = 2` spreads below the weakest passing leg, rounded up to the last digit.
Reading them as one family is what makes `0.89` against `0.91` legible instead of suspicious (§3.3, last
paragraph): the in-plane bar is the looser of the two because its spread is the larger one (`0.0179` against
`0.0132`), and neither number is rounded from the other.

**The trap this block exists to prevent.** The legacy spread `F = 1.5657e-4` is the spread of the **superseded**
statistic, not of this one. Applied here it gives `0.9352867303487647 − 2 × 1.5657e-4 = 0.9349735821273027
→ 0.94`, a bar that would **reject its own population**, starting with the leg it was derived from. There is no
conversion from `F` to an `S_good` on this metric; `S_good/F = 84.5821` compares two numbers measured on different
statistics and nothing more. That is the whole reason this clause carries its own derivation and its own id rather
than a tightened `0.30`.

### 3.7 `T6_fit_route` — two fit routes over one eigen-solution agree

| field | value |
|---|---|
| statement | `|beta_fit_2 − beta_eigen| / beta_eigen <= 0.005` — two *routes to a fit* of the **same** eigen-solution, on the same lattice |
| quantity | a second fit of one eigenvalue vs the eigenvalue: `beta_eigen = 312.7827646322591`, second fit `314.03158662735785` (`TOLFLUX.json:beta`) |
| threshold | `T2_TOL = 0.005` (`gates_101_20.py:166`) — the same bar `T2_agree` is scored against, deliberately reused |
| measured gap | **`0.399261768 %`** — inside the tolerance, margin **`1.252311×`** |
| failing witness | **none, on `n = 1`** — one measurement exists (`0.399261768 %`); one pass is not a population |
| can pass | yes, and it does: `0.399261768 %` against `0.5 %` |
| can fail | yes in principle — it is a real inequality with a measured margin of only 25 %, not a tautology |
| status | **registered, no implementation**, and none is claimed: `T6_fit_route` appears in no `.py` file in the tree |

**This is a route-sensitivity check, and it is not evidence of solver accuracy.** It asks one narrow question: do two
fitting routes over the *same* eigen-solution, on the *same* lattice, land within `0.5 %` of each other? Its subject is
the **fit**, not the field. It is **not** a cross-solver test, **not** an FDTD comparison, and **not** a check by an
independent solver — every number in the table comes from one solver's output and one banked eigenvector, and a pass
says only that the extraction route is not what moves `beta`. It says nothing about whether `beta` is right. The
margin is **thin** — 25 % of headroom over the bar — so a pass here is not comfort; it is the absence of one named
failure mode, and it must not be described as comfortable. The failure on the other route is `T2_agree`'s (§3.2).

---

## 4. Record wins over brief

| # | the brief says | the record says | ruling for v2 |
|---|---|---|---|
| 1 | `T4_amp` has a band (`R <= 1e-2` / `0.1 <= R <= 10`) | both bands **withdrawn**: *"derived from nothing, present in no implementation"*; criterion reserved with **no X proposed** (`decisions.md:7256-7258`) | **the bands are not reinstated at any value.** `T4_amp` ships with no threshold |
| 2 | `T3_ey`'s derived bar rests on a four-leg population | the derivation in the record is over the **two PMC mesh legs** (`corr_ez_vv_threshold.md:303-307`); the four-leg variant gives 0.86 and depends on a leg whose attribution is disputed | adopt **0.89**, two-leg — **done in v2.1**, `CORR_EY_MIN` at `c1_audit.py:234` (§3.3); the `0.86` wider-population variant is held pending attribution |
| 3 | `T5_fringe` threshold `0.86` | the `0.86` has **no lineage in the record at all**: it was a design proposal made in the brief, formed by rounding the observed `+0.8628` down to `0.86`. It is not a transcribed record number, not derived, and was never adopted. The only `0.86` strings in the tree are unrelated (a `0.86 deg` standing-wave bound, `decisions.md:30` / `:191`; a *"backward ratio of 0.86"* tied to SWR ≈ 13, `:2660`) | **`[untraced]`** — not adopted, and not re-derived. The clause was re-specified on a different statistic (§3.5), where `0.86` is not dimensionally expressible. See §5 |
| 4 | `T3` is named `T3_ey` | registered as **`§101.20.T3_scale`** (`decisions.md:7129`); implemented as `T3_ey_slot` (`gates_101_20.py:713`) | adopt a **fresh** id, `§101.20.T5_ey_corr` (§3.3). v2's “rename of `T3_ey`” is **withdrawn**: `T3` keeps `§101.20.T3_scale`, a different statistic |
| 5 | `T5_fringe` extends the registered set | `T4_amp` is a **reserved criterion only** — it carries no clause registration and no code (`decisions.md:7256-7258`, `:7268`); `T5_fringe` is registered nowhere | `T5_fringe_excess` (§3.5) is **new**, and the registration it needs is supplied in §9 (`§101.20.T5_fringe_excess`, *registered, no implementation*), which is authoritative here; `T5_ez_corr` (§3.6) is a **registration** of a bar already in force (`§101.20.T5_ez_corr`) |
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
| **`0.86`** | `T5_fringe` threshold | **`[untraced]` — origin known, lineage absent.** It was **proposed in the brief that prompted this note**, formed by rounding the observed fringe measurement `+0.8628` down to `0.86`. It is *not* a transcribed record number, it is *not* derived, and it was never adopted. No `0.86` threshold exists in any `.py` or `.md`; every `0.86` string in the tree is unrelated: `0.86 deg` (standing-wave bound, `decisions.md:30`, `:191`) and `"backward ratio of 0.86"` with SWR ≈ 13 (`:2660`) | **not adopted** — and now not adoptable: the fringe clause's statistic is an excess ratio with a `1.0` baseline (§3.5), on which `0.86` is not expressible. Worth knowing anyway: the *same two digits* also fall out of an **unrelated** construction — `0.912343044811209 − 2 × 0.026359135224690 = 0.859624774361829 → 0.86`, the `k=2` round-up rule on the **wider `|corr_e_y|` population** (§3.3). That is a **coincidence between two unrelated constructions**, not an origin story for either: someone will land on `0.86` again, and it will not mean the fringe clause justified it |
| **`X` in `T4_amp`** | "within X per cent of the analytic ratio" | **no X is proposed anywhere** (`decisions.md:7258`) | none available; clause cannot ship |
| **`0.161983870` vs `0.197856`** | per-column `corr_ez` oracle | **contested**: `docs/design/zfree_shape.md:84` and `:417` record `0.161983870`; `decisions.md:7308` records `0.197856` (31x17) and `0.199096` (41x22); the mismatch is *"pre-existing"* and deliberately not reconciled (`reports/2026-10-27_16-16-34_…:176`) | neither value may be used as a threshold or a population member. Marked **contested** |
| **`0.119317007`** | `e_z` baseline | **settled, not contested**: it is the **41x22 baseline code-path `corr_e_z`, column 1318** (`decisions.md:7998-8016`; repr `-0.11931700650207343`). The earlier "31x17 legal-operator baseline" attribution was a paraphrase error at `decisions.md:7982`, repeated uncorrected at `zfree_shape.md:473`; the residual defect is a **label** (baseline code path vs legal operator), not a mesh (`:8012`) | usable as a *measurement*, never as a threshold input: it is an `e_z` quantity and it is the **mis-paired** statistic. It enters no `T5_ey_corr` population (§3.3), which is `e_y`, and none for `T5_ez_corr` (§3.6), whose statistic is the *corrected* vertical pairing `corr_ez_vv` — not this mis-paired number |
| **`0.0272`** | vertical-over-in-plane ratio | it is **longitudinal**-over-in-plane; `e_z_vv` appears nowhere in it (`decisions.md:7950-7956`) | not a `T4_amp` input |

---

## 6. Self-audit: which v2 clauses still cannot fail

This is the section the rule exists to produce. Applied honestly, **one of the five v2 clauses cannot fail**
(`T4_amp`, §6.1), **one ships red on the recorded population** (`§101.20.T5_fringe_excess`, §6.2), and
`T2_agree`'s state is determined but adverse (§6.4).

### 6.1 `T4_amp` — no threshold, no witness; the numerator now exists

`decisions.md:7258` reserves the criterion and proposes no X; the placeholder bands stay withdrawn. The missing
element is now a **threshold**, not a datum. The PMC leg gives `R_extracted = 4.0489791163982565` against
`R_analytic = 2.8101021387524523` — `1.441×`, a `44.09 %` relative error — and no rule says how far `1.441×` may sit
from `1.0`. With no inequality to score there is nothing for a measurement to miss, so by §1 corollary (1) this
clause cannot select. **Verdict: still cannot fail — on the threshold, not the datum. Do not ship.**

### 6.2 `§101.20.T5_fringe_excess` — red on the record, on purpose

The v2 form of this clause — a fringe **correlation** bar at `0.86` — could not fail: both recorded fringe
correlations sat *above* it (`0.8628`, `0.8653`, by `0.0028` and `0.0053`), the bar had no lineage beyond the brief that
proposed it (§5), and the one leg that would have been an interesting witness (`PEC col704`) had no fringe
decomposition at all. That form is withdrawn (§3.5).

The replacement passes the rule in the direction the record actually supplies:

* **It fails today.** Both recorded legs are red — `2.849` and `2.89` against `2.0`, margins `1.42x` and `1.45x`.
  No worse mesh and no future run is needed to see the clause select.
* **The verdict is not a bar artefact.** Any threshold in `(1.0, 2.849)` gives the same reading on both legs, so `2.0`
  is not load-bearing; and the two legs come from different solvers and agree to `1.4 %`.
* **The statistic is the one the record singled out.** `decisions.md:7970` located the vertical field's defect at the
  strip edges and quantified it as an *excess*, not as a decorrelation. Gating the excess gates the finding.

**What it still cannot do, stated plainly.** It has no measurement on the leg that fails everything else: `PEC col704`
carries no fringe decomposition, so the clause is red on the two *passing* legs and silent on the failing one. Two
readings survive that (§3.5), and the measurement that would separate them — a decomposition of `PEC col704`
— has not been made. What the clause does buy is a falsifiable claim about the *geometry* rather than a report on a
mesh: if `PEC col704`'s decomposition comes out **below** `2.0`, the `2.0` bar is wrong and this clause must be
re-derived, not re-rounded.

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
applied mechanically.** Any bar set on a small spread needs its own derivation and its own stated rounding rule,
not this one.

**The §3.5 bar takes that advice.** `T5_fringe_excess` is deliberately *not* an `L − k·S` bound: its spread is
`2.89 − 2.849 = 0.041` in excess units, so the convention would give `2.849 − 2 × 0.041 = 2.767 → 2.8` and
**pass both legs** — green on the known fault, which is the exact failure this clause exists to avoid. It is instead
a multiple of a stated baseline (`1.0`) on a stated rounding grid (`0.1`), and it rejects rather than admits its own
population. The two bar families are not interchangeable, and choosing between them is choosing whether a clause is
supposed to *admit* its population or *catch* it.

### 6.4 `T2_agree` — determined, and it fails on one of two fits

The 4.52 % gap against a `0.005` tolerance is a factor of nine, and it is no longer a puzzle about *pairing*: the fit
behind it is `326.9107654423116` against an eigenvalue of `312.7827646322591`, and a second fit
(`TOLFLUX.json`, `314.03158662735785`) sits `0.40 %` above the same eigenvalue. The clause therefore **can pass and can
fail on real numbers** — it just does both, depending on which fit it is handed. Verdict: **not passing, deferred**;
not inert, not undetermined. What stays undetermined is which fit is the scored one (`:50` of
`docs/design/t4_amp_ratio.md`; `decisions.md:7680`), and until that is settled the honest statement of the clause's
state is "fails on one fit, passes on the other" — which is itself the finding: a **4.1 % spread between two fits of
one eigenvalue is eight times the tolerance being enforced**, so the tolerance is finer than the thing it measures.
Items for the owner: (i) name the scored fit; (ii) fix the `(0,)` read (`emfit/studies.py:3242-3246`); (iii) either
justify `0.005` against a 4.1 % inter-fit spread or widen it and say what the wider bar is anchored to.

### 6.5 What survives clean

* `§101.20.T5_ey_corr` at **0.89** — derived, population stated, and with a wide-margin failing witness (`PEC col704`,
  `|corr_e_y| = 0.426`). **Can fail.**
* `§101.20.T5_ez_corr` (`corr_ez_vv`) at **0.91** — derived, population stated, failing witness at 62.4 spreads below the bar
  (`c1_audit.py:237-254`). **Can fail.**
* `REPRO_RTOL = 1e-6` — falsifiable, and exercised in history by the `0.1462 → 0.1192` drift
  (`c1_audit.py:257-261`). **Can fail.**
* `T1_stab` at `0.005` — can fail in principle; the bar needs a derivation or a re-base trigger, and the
  `basis='mixed'` branch needs to evaluate rather than raise (`:486-493`).

---

## 7. Sites: where each clause lives, or would live

| clause | statistic is computed at | threshold lives at (or would) | status |
|---|---|---|---|
| `T1_stab` | `tools/gates_101_20.py:465` | `tools/gates_101_20.py:132` (`T1_TOL = 0.005`) | implemented, behind the solve flag (`:15`) |
| `T2_agree` | `tools/gates_101_20.py:544` | `tools/gates_101_20.py:166` (`T2_TOL = 0.005`) | implemented; reachability defect at `:572-576` |
| `§101.20.T3_scale` | `tools/gates_101_20.py:713` (`T3_ey_slot`) | `tools/gates_101_20.py:221` (`T3_TOL = 1e-5`) | implemented |
| `§101.20.T5_ey_corr` | `c1_audit.py:679-694`, `:694` | `tools/host/c1-audit/c1_audit.py:234` (`CORR_EY_MIN = 0.89`) | **in force**, not design-only — adopted in this block (§3.3); the same constant is also the floor of the superseded legacy screen at `:728-730` |
| `§101.20.T5_ez_corr` (`corr_ez_vv`) | `c1_audit.py:724-726` (criterion), arrays at `:824-825` | `tools/host/c1-audit/c1_audit.py:255` (`CORR_EZ_VV_MIN = 0.91`) | in force (§3.6); second use site `tools/host/c1-audit/pecbox_variant.py:511-513` |
| `corr_e_y` (legacy) | `c1_audit.py:728-730` | `c1_audit.py:234` (`CORR_EY_MIN` — `0.90` when §2 was written, `0.89` in v2.1) | in force, superseded in value by §3.3 |
| `corr_ez` (legacy, non-selecting) | `c1_audit.py:728-730` | `c1_audit.py:235` (`CORR_EZ_MAX = 0.30`) | in force, **non-selecting** (§1(a)); recorded at `decisions.md:7938` |
| `REPRO` | `c1_audit.py:977-985` | `c1_audit.py:262` (`REPRO_RTOL = 1e-6`) | in force |
| `T4_amp` | `s10118_basis.py:371-373` (R); no gate site | nowhere | deferred; **not registered**, no code (`decisions.md:7268`) |
| `§101.20.T5_fringe_excess` (`ex_R > 2.0` fails) | deficit decomposition only, ad hoc, `decisions.md:7958-7972` | **nowhere** — no implementation in code | **registered in this block** (§3.5); registered on measured evidence, with no executable behind it, so it cannot fail as a build |

---

## 8. What is not claimed

None of `T1_stab`, `T2_agree`, `T3_ey_slot` has been run as part of this note (they require
`--i-understand-this-needs-a-solve`, `gates_101_20.py:15`). No tolerance in this note has been validated by a new
solve. The 0.89 in §3.3 is arithmetic on two banked numbers, not a measurement. `T4_amp` is deferred and
**not registered**, with no implementation — but what it lacks has narrowed to a **threshold**: the PMC leg now
gives `R_extracted = 4.0489791163982565`, `1.441×` `R_analytic` (§3.4); how far from `1.0` that may sit is a policy
choice still unmade. `T5_fringe_excess` is **registered** (§3.5, §9) with **no executable**, and §6's advice that
both should stay unimplemented in their present form speaks to their implementation status only, and not to
whether they are registered.

Two further gaps belong here, because both are the kind that get mistaken for a measurement later.

* **`CORR_EY_MIN = 0.89` is in code, but no gate run was done.** The constant at `c1_audit.py:234` moved from `0.90`
  to `0.89` (§3.3) with no gate run behind the change. The banked npz artefacts carried `criterion = [0.90, 0.30]`
  and `criterion_ez_vv = [0.90, 0.90]` when this was written, and nothing in the tree compared those stored arrays
  against the constants meant to have written them; both banks were re-banked in this block and now carry
  `criterion = [0.89, 0.30]` and `criterion_ez_vv = [0.89, 0.91]`, matching the live `CORR_EY_MIN = 0.89`,
  `CORR_EZ_MAX = 0.30` and `CORR_EZ_VV_MIN = 0.91` in `c1_audit.py`, so this particular gap is **closed**. No
  recorded verdict flips — the passing legs sit at 0.92 / 0.94 and the witness at 0.43, all clear of either
  value — and while the stored arrays and the live constants disagreed on paper, that disagreement was not a
  measurement of anything. It was a gap of exactly the kind that gets read as one later.
* **The `§101.20.T5_fringe_excess` red is a reading of the record, not a failing build.** No gate computes `ex_R`;
  the `2.849` (31x17 PMC) and `2.89` (31x17 PEC, col 699) values in §3.5 come from the region decomposition that
  produced the band census, not from a gate run. The clause is registered on measured evidence with no executable
  behind it yet, which is what its `nowhere` row in §7 is saying.
* **Reading `pecbox_spectrum.npz` for the PEC column gives the PMC answer, and the PEC ratio is not the banked one.**
  `bank_col` there is `738` (c1_audit.py's `BANKED` column, inherited through the path redirect) while this file's columns
  are `699` and `704`; and `R_extracted` there is `70.635018555128326`, the last *scanned* column (`704`, the failing
  witness), not the identified `699`, whose ratio is `4.163656524825077` and is in no npz (§10.9). The banked scalar is
  therefore not quotable for PEC; `c1_spectrum.npz` is unaffected because it scans `(738,)` alone, so its `R_extracted = 4.0489791163982565` is the identified column's.

---

## 9. Registered clause list

Seven entries, no more. Everything else in §§2–3 is an audit of what v1 already had, not a registration.

| id | asserts | status | lives |
|---|---|---|---|
| `§101.20.T1_stab` | stability of the propagation `beta` under drop-nearest-station | in force | `tools/gates_101_20.py:465` (`def T1_stab`), tol `:132` (`T1_TOL = 0.005`), behind the solve flag (`:15`) |
| `§101.20.T2_agree` | two estimates of `beta` agree within `T2_TOL = 0.005` | **deferred** — it can fail and it does: the scored fit sits `4.52 %` (`9.03×` the tolerance) away (§3.2), pending adjudication between the two candidate fits, and its `(,)`-shape `beta` defect at `:572-576` has to be fixed before a verdict means anything | `tools/gates_101_20.py:544-560`, tol `:166` |
| `§101.20.T3_scale` | scale ratio `1e-5` on the `plane_Ey` slot only | in force, unchanged | `tools/gates_101_20.py:713` (`def T3_ey_slot`), tol `:221` (`T3_TOL = 1e-5`) |
| `§101.20.T5_ez_corr` | `|corr_ez_vv| >= 0.91` | in force | `tools/host/c1-audit/c1_audit.py:193` (`CORR_EZ_VV_MIN`), criterion `:575-577` |
| `§101.20.T5_ey_corr` | `|corr_e_y| >= 0.89` | in force | `tools/host/c1-audit/c1_audit.py:172` (`CORR_EY_MIN`), screen `:575-581` |
| `§101.20.T5_fringe_excess` | `ex_R > 2.0` fails | registered, no implementation | nowhere |
| `§101.20.T6_fit_route` | two fit routes over one eigen-solution agree within `T2_TOL = 0.005` (`0.399261768 %`, margin `1.252311×`) | registered, no implementation | nowhere |

The organising rule is in the names: **mode-selection tests live under `T5_*`** — they ask which column the solver
is allowed to select — while the physics tests keep the names they already had, `T1_stab`, `T2_agree` and
`T3_scale`. `T3_scale`'s id is retained deliberately, not by inertia: it gates a **scale** ratio on `plane_Ey` at
`1e-5`, not a correlation, and the older citations (`decisions.md:7129`, `:7254`) still resolve to it. The
correlation clause v2 wanted to call `T3_ey` is therefore a new registration under a new id rather than a rename,
which is why `§101.20.T3_scale` and `§101.20.T5_ey_corr` both appear above.

---

## 10. Gate state update (v2.2) — listed, not patched

**This section supersedes nothing above it, and edits nothing above it.** The v2.1 header revision block (`:3-22`), the `## 0. Status and scope` table (`:39-45`), `### 3.2 T2_agree` (`:216-226`) and `### 3.4 T4_amp` (`:280-292`) stand byte-for-byte as they are; no line at or before `:630` is inserted, deleted, reflowed or replaced.

**Why the update cannot go where a revision note normally goes.** `docs/design/t4_amp_ratio.md` §9.5 and §9.7, both committed, cite this file at `docs/design/m3c_gate_v2.md:630` for the sentence `Seven entries, no more.` (§9, `:628-640`). Writing the update into the header block, the §0 table or §3.4 would move that line, and the citation is to a line number, not to a heading: two committed citations would be silently falsified.

**So the change is listed here, at the tail.** This file states at its head that it is not append-only and that its changes are *"listed, not silently patched"* (`:3`). Listing the change at the tail is that same discipline applied from the other end; the alternative was a silent patch of a line-frozen head, which is the one thing the head forbids.

**Recorded changes, numbered.** (1) `T4_amp`'s status is restated: bar registered, clause still unimplemented, measurement recorded as FAIL (§10.2). (2) `T2_agree` is recorded as FAIL on the scored fit at `9.03×` `T2_TOL` (§10.3), a second and independent red from the same run. (3) The new mesh-sensitivity evidence is recorded, with the knob identified (§10.4). (4) The solver ceiling is named as the current physical blocker, with a pointer to the sparse design pass that is not yet a result (§10.5). (5) The extraction is exonerated, so the miss is not a bookkeeping bug (§10.6). (6) No gate-table row is added, removed or renumbered, and no verdict is flipped (§10.1, §10.7). (7) The two `CORR_EY_MIN` / `CORR_EZ_VV_MIN` line citations in §10.7 are corrected, and the 27-line drift that invalidated them in the v2.1 header and §9 is recorded rather than patched (§10.8).

### 10.1 The gate verdict is unchanged: FAIL

**The overall v2 gate verdict remains FAIL.** No clause was flipped to PASS, deleted or weakened by anything in this section, and no gate was run to produce it. The registered list still holds seven rows: `Seven entries, no more.` at `:630` is still literally true after this append, and `:632-640` still carries exactly `T1_stab`, `T2_agree`, `T3_scale`, `T5_ez_corr`, `T5_ey_corr`, `T5_fringe_excess` and `T6_fit_route`. Everything below is a status and evidence update against those rows, not a re-registration.

### 10.2 `T4_amp` — bar registered, clause still unimplemented, measurement FAIL

**The status moves from the design-only language of §3.4 (`:292`) to three separate facts.** The bar is **registered**: `±10 %` on the relative amplitude ratio, adopted and locked in `docs/design/t4_amp_ratio.md` §9.1-§9.6. The clause is **still not implemented** as executable gate code: `T4_amp` appears in no `.py` file in the tree, and §9.4 of that note remains unimplemented. And the measurement against the registered bar is a recorded **FAIL**.

**The FAIL, in the registered quantity.** Scored quantity `Q = R_extracted / R_analytic = 1.440865461991999`, i.e. **44.086546199199894 %** away from the analytic value `R_analytic = 2.8101021387524523`. The `±10 %` band on `R_extracted` is `[2.52909192487721, 3.09111235262770]`; the measured `R_extracted = 4.0489791163982565` sits **4.408654619919989×** the `±10 %` half-width outside it.

**A 4.4× overshoot is not a near miss.** The measurement is more than four half-widths beyond the edge of the band, so no correction of the size exonerated in §10.6 can reach it. §9.6's pre-registered revisit clause has **not** been invoked: the band was registered before this measurement and stands as registered.

### 10.3 `T2_agree` — also FAIL, at `9.03×` tolerance

**A second clause fails on the same run.** `beta_fit = 326.9107654423116` against `beta_eigen = 312.7827646322591` is a relative disagreement of **4.516873 %** — **`9.03×`** `T2_TOL = 0.005` (`tools/gates_101_20.py:166`), as tabulated at §3.2 (`:223`).

**It is not the amplitude-ratio miss in disguise.** `Q` is a cross-section energy ratio formed from two field sums (§3.4, `:285`); `beta` is a global weighted propagation constant, and across the whole `N = 6 … 22` mesh sweep of §10.4 it moves only **1.3 %** (314.73 → 310.64). A quantity that moves 1.3 % under that refinement cannot carry a 4.4× ratio error, so the two reds are separate and both stand.

### 10.4 What the new mesh evidence says about where the miss lives

| knob swept | settings | `R_extracted` (dimensionless) | successive increments (%) | reads as |
|---|---|---|---|---|
| strip band | 12 / 18 / 24 / 36 | 4.0489791164 / 4.0463369445 / 4.0514540972 / 4.0493407985 | +0.0653 / −0.1263 / +0.0522 | flat — strip refinement is not the knob |
| air band | `N =` 6 / 9 / 12 / 15 / 18 / 22 | 4.4382495593902 / 4.0489791163983 / 3.7124820337398 / 3.5036000135 / 3.4384391291194 / 3.2761300897590 | −8.7708 / −8.3107 / −5.6265 / −1.8598 / −4.7204 | monotone — the air band is the knob, and the ratio is still far from 2.81 at every reachable `N` |
| z band | 12 / 6 / 8 | 4.1029404210 | — | the wrong way — away from `R_analytic`, not toward it |

**The strip band does not move it.** Strip band 12 / 18 / 24 / 36 gives `4.0489791164 / 4.0463369445 / 4.0514540972 / 4.0493407985`, i.e. changes of `+0.0653 / −0.1263 / +0.0522 %`, verdict **NO**: refining the strip band does not move the ratio.

**The air band does, and slowly.** `N = 6 / 9 / 12 / 15 / 18 / 22` gives `4.4382495593902 / 4.0489791163983 / 3.7124820337398 / 3.5036000135 / 3.4384391291194 / 3.2761300897590`, successive decrements `−8.7708 / −8.3107 / −5.6265 / −1.8598 / −4.7204 %`, while `beta` moves only 1.3 % (314.73 → 310.64).

**Moving the z band instead goes the wrong way.** z band 12 / 6 / 8 gives `4.1029404210`, further from `R_analytic`, not closer.

All three sweeps are recorded at `docs/design/t4_amp_ratio.md` §9.7 and §9.8; the readings here are those numbers, not new ones.

### 10.5 The current physical blocker is the solver ceiling, not the operator

**The mesh ceiling is `N = 25` at `h = 0.34 mm`.** Free edges scale as `48*nx − 44` with `nx = 2N + 13`, and the dense solve is capped by `_MIXED_DENSE_MAX = 3000`; at `N = 25` the free-edge count already sits just below that cap, so the next `N` in the air-band sweep crosses it. The next data point §10.4's argument needs is therefore unreachable by the current solver: the blocker is a linear-algebra limit, not a modelling choice about the operator.

**`docs/design/sparse_eigenmode.md` is a design pass only — unanchored until implemented and gated.** At the 201×77 mesh it measures `splu` fill-in of 8,352,700 nonzeros (`0.00228` of the dense `n²`, about 100.2 MB), a 0.38 s factorisation and 12.82 ms per shift-invert apply, against 16.7 GB and roughly 41 days for the dense QZ path. **None of those numbers is a result about `R`**, and none is a gate result: they measure a solver that is not in the tree behind any clause.

### 10.6 The extraction is exonerated

**The FAIL is not a bookkeeping artefact.** `docs/design/t4_amp_ratio.md` §10 establishes four things about `R_extracted`: it has one definition, at `tools/host/c1-audit/c1_audit.py:738`, inside the single `np.savez(` call at `:703`; no weight or area element is missing from it, with trapezoid weighting worth only `+0.0223 %` / `+0.0175 %`; the numbers reproduce bit-exactly from the banked payloads; and de-staggering both operands onto one lattice bounds the lattice asymmetry at 1.18 % / 0.30 %.

**What that means for the gate.** Every correction measured there is at most 1.18 %, against a 44.086546199199894 % miss, so the gap cannot be closed by correcting the extraction. It must be closed by refinement — which is exactly the step §10.5 says the dense solver cannot deliver.

### 10.7 What this section does not do

* No gate-table row was added, removed or renumbered: `:632-640` is unchanged and `:630` is still literally true.
* No verdict was flipped to PASS; no clause was deleted or weakened.
* No tolerance changed: `T1_TOL = 0.005` (`tools/gates_101_20.py:132`), `T2_TOL = 0.005` (`:166`), `T3_TOL = 1e-5` (`:221`), `CORR_EY_MIN = 0.89` (`tools/host/c1-audit/c1_audit.py:234`) and `CORR_EZ_VV_MIN = 0.91` (`:255`) all stand, as does the `±10 %` amplitude band registered in `docs/design/t4_amp_ratio.md` §9.1-§9.6.
* No solve, no gate run and no `.py` edit accompanied this section; every number in it is quoted from an already-banked artefact or is arithmetic on those numbers.
* `docs/design/t4_amp_ratio.md` §9.6's revisit clause remains uninvoked, and §9.4 remains unimplemented.

### 10.8 Citation drift in the two constants this section relies on

**The drift, measured.** The v2.1 header cites `tools/host/c1-audit/c1_audit.py:172` for `CORR_EY_MIN` at `:14`; the `§101.20.T5_ez_corr` and `§101.20.T5_ey_corr` rows of §9 cite `:193` for `CORR_EZ_VV_MIN` and `:172` for `CORR_EY_MIN` at `:637-638`. Each was correct when written and each is now stale by exactly 27 lines — `grep -n` puts `CORR_EY_MIN = 0.89` at `:199` and `CORR_EZ_VV_MIN = 0.91` at `:220`. The same stale pair appears at `:14`, `:166`, `:170`, `:240`, `:261`, `:273`, `:388`, `:442`, `:584-586` and `:607`, none of which is edited. **Superseded by §11.** The `+27` arithmetic on this line is itself a stale snapshot: `grep -n` on the current tree puts `CORR_EY_MIN = 0.89` at `:234` and `CORR_EZ_VV_MIN = 0.91` at `:255`, i.e. `+62` each, because the code file grew again above the constants after this paragraph was written. Every citation this line lists as “none of which is edited” — `:14`, `:166`, `:170`, `:240`, `:261`, `:273`, `:388`, `:442`, `:584-586`, `:607` — has since been edited in place, within-line; §11 is the listing, with the symbol → old → new table and the hashes that prove nothing else moved.

**Why it drifted, and that it is not an authoring error.** The file grew above the constants, twice: the `C1_STRIP_CELLS` knob first, then the `C1_Y_AIR_CELLS` / `C1_Z_CELLS` knobs, whose commit inserts 6 lines above `CORR_EY_MIN` (its diff offsets jump to `+6` from `@@ -104,6 +104,12 @@` onward). 172 + 21 + 6 = 199 and 193 + 21 + 6 = 220. The `+27` is measured from current `grep -n`; the `+6` is attributable to the mesh-knob commit. Citations written after those commits — `R_extracted` at `:738` and the `np.savez(` call at `:703`, both relied on in §10.6 — are current.

**What was and was not edited.** The two citations in §10.7 are corrected. The header citation at `:14` and the §9 rows at `:637-638` are deliberately left as-is. A same-line-count replacement at `:14` would not move `:630`, so it is mechanically safe — and it is still not made, because this document's rule is that changes are listed rather than silently patched, and §10.8 is the listing. **Superseded in part by §11.** The header citation at `:14` has since been edited in place (`172` → `234`, within-line, no change to the line count), so the sentence above that `:14` is left as-is no longer describes the file. The §9 rows at `:637-638` remain unedited on purpose: §9 is the registered clause list and this repair confines itself to prose that describes the code — §11 carries their corrected numbers instead.

### 10.9 The PEC ratio on the record, re-read

**The leg has a quotable ratio after all, and it is not the banked one.** `c1_audit.py` now selects the column rather than taking the last one scanned, and with the selection it records the PEC leg's quotient at its identified column: `R = 4.163656524825077` on column `699` (`ok` `True`, `corr_ey = 0.91234304`, `corr_ez_vv = 0.93692972`, against the `0.89` / `0.91` criterion). Against `R_analytic = 2.8101021387524523` that is `4.163656524825077 / 2.8101021387524523 = 1.4816744442867605`, i.e. `1.482×`, an error of `48.167 %` against the `±10 %` band — so the PEC leg read at its own column fails the bar too, marginally worse than the PMC leg's `1.441×`. The PEC leg is excluded from scoring for provenance and for leg count, not because re-reading it rescues anything.

The two legs at their own identified columns therefore sit `4.163656524825077 / 4.0489791163982565 = 1.0283225487536798` apart, `2.8 %` — not the `17.445142719817547×` that the banked scalars suggest. The 17× is a carrier-versus-non-carrier comparison, and it is retained only as the diagnostic of how far a column selection can move the number.

**The artefact still holds the wrong column.** `out/pecbox_spectrum.npz` reads `R_extracted = 70.635018555128326`, the last *scanned* column, `704`, and it was deliberately not overwritten when the selection was fixed (`c1_audit.py:210-213`): the banked capture is evidence of the defect and is left alone. So a reader who opens the npz still sees the artefact. `R_by_col` (`c1_audit.py:862`) and the per-column `R_extracted` (`:888`) exist only on a re-run, and `:999`'s `REPRO` message states what the re-run is expected to print — `4.163656524825077`, not `70.635`. Until that re-run, the correct PEC ratio lives in the script's own record and in `docs/design/t4_amp_ratio.md` §2, not in any npz.

**What this supersedes.** §3.4's "only the PMC figure is quotable" and §8's "Neither is quotable for PEC" were true of the *banked scalars* and are too strong about the legs: the PEC leg's ratio is on record at its identified column, and what is unquotable is `70.635018555128326`. Both sentences are left as written and are corrected here, in the same way §10.8 is left and superseded rather than rewritten.

**Why no column index is the identifier.** The first-banked capture names column `738` where a fresh solve of the identical rung-0 mesh names `732`, with `R` agreeing to `8e-13` — the mode is the same, the index is not (see `docs/design/t4_amp_ratio.md` §12.1). The PEC box names `699`. So `699`, `704`, `732` and `738` are all environment-dependent readings of one mode, and identifying the mode by its column index is exactly the mistake that produced `70.635`. The mode is identified by `beta_sq` and by `R`; a ratio is quoted with both.

### 10.10 The refinement ladder: status

**Where the ladder stands.** The full dense ladder, rungs 0–4, is running on the host in one **anchored** pass (`tools/host/sparse-probe/high_res_run.sh --include-rung4`). Rungs 0–3 have written their captures (`out/rung0_*` 22:38, `out/rung1_*` 22:40, `out/rung2_*` 22:46, `out/rung3_*` 23:08); rung 4's directory exists but holds only `env.json` and `run.log`. This section does not tabulate rungs 2–4: their numbers belong to the report of the completed pass, and quoting them from a partial directory would be exactly the kind of half-read number §10.8 exists to prevent.

**An earlier pass was unanchored, and its verdict is void.** `out/summary_HIGHRES.txt` comes from that pass, and its own step 1 reads "rung 0 did not run: the ladder is unanchored and nothing below applies" — yet the same report went on to print `T4_amp: FAIL` from the rung-1 operand (`R_extracted = 3.780331990015745`, `Q = 1.345264977341`). A pass whose control never ran is a pass whose lower rungs do not apply; the FAIL line is not a verdict and is not to be cited as one. Its rung directories were parked under `out/prev/` rather than deleted, so the two passes stay distinguishable by path.

**The harness now refuses that shape of run.** Commit `a72530f` makes an unanchored pass refuse outright (`tools/host/sparse-probe/high_res_run.py:966`, "the ladder would be UNANCHORED"), and a pass that reaches the verdict step without a rung-0 anchor writes `T4_amp: NOT EVALUATED` instead of a verdict (`:1126-1127`, emitted at `:1139`). Nothing in this section's gate verdict changes: `T4_amp` is still FAIL on the banked PMC measurement (§10.1–§10.2), and the ladder is a diagnostic of *why*, not a re-scoring.

**Invariants kept by this append.** The repair above (§10.9, §8, §3.4) was made line-count-neutral, so `m3c_gate_v2.md:630` — "Seven entries, no more. Everything else in §2–§3 is an audit of what v1 already had, not a registration.", the citation target of `docs/design/t4_amp_ratio.md` §9.5 and §9.7 — is still at line 630 and still reads exactly that. This append sits entirely below line 630 and moves no line at or above it: the prefix through line 630 is fixed, the file grew only by the text you are reading. The head-630 *prefix hash* did change, from `a03c78d43fd8077df2588281d00a97103e9115ecdc2b3be37326cad789583203` to `e60a0929…`, for the same reason §11 records the previous link in that chain: the repaired lines `:302-305` and `:620-624` are inside the prefix, and leaving them wrong would be the only way to keep it.

## 11. Citation repair: witness chain

**What this section is.** §10.8 recorded a drift rather than patching it. This section *is* the patch, listed the same way §10 lists its own changes: every line it touched, what the citation said, what it says now, and the mechanical evidence that nothing else moved. The `CORR_EY_MIN` / `CORR_EZ_VV_MIN` citations in §10.7 were already correct and are not touched again here.

**The drift is per-symbol, not one number.** `tools/host/c1-audit/c1_audit.py` is 1015 lines today. The constants sit at the following `grep -n` positions, and the offsets against the citations this document carried are not uniform — so no single `+N` could ever have repaired them:

| symbol | cited in this document as | location today | offset |
|---|---|---|---|
| `ANCHOR_CORR_EY` | `c1_audit.py:151` | `c1_audit.py:191` | `+40` |
| `ANCHOR_CORR_EZ` | `c1_audit.py:152` | `c1_audit.py:192` | `+40` |
| `CORR_EY_MIN` derivation comment block | `c1_audit.py:155-171` (17 lines), also cited as `c1_audit.py:175-191` | `c1_audit.py:216-233` (18 lines) | head `+61`, tail `+62` |
| `CORR_EY_MIN = 0.89` | `c1_audit.py:172`, and `:199` in §10.8's own measurement | `c1_audit.py:234` | `+62` |
| `CORR_EZ_MAX = 0.30` | `c1_audit.py:173` | `c1_audit.py:235` | `+62` |
| `CORR_EZ_VV_MIN` derivation comment block | `c1_audit.py:175-191` (17 lines), also cited as `c1_audit.py:195-199` at its tail | `c1_audit.py:237-254` (18 lines) | head `+62`, tail `+63` |
| `CORR_EZ_VV_MIN = 0.91` | `c1_audit.py:193`, and `:220` in §10.8's own measurement | `c1_audit.py:255` | `+62` |
| `REPRO_RTOL = 1e-6` | `c1_audit.py:182` (§2.5) and `c1_audit.py:200` (§9 table) | `c1_audit.py:262` | `+80` and `+62` |

Two details in that table are worth stating rather than smoothing over. The two derivation comment blocks each grew by one line (17 → 18), so their head and tail offsets differ by one; and `REPRO_RTOL` was cited at two different old numbers `18` apart, which is itself the signature of two different snapshots of the file being quoted inside one document.

**Code regions, resolved by symbol.** These are not constants, so they are resolved by what the code does, not by arithmetic:

| region (durable) | cited in this document as | location today |
|---|---|---|
| `corr_e_y` construction: `e_y = E_t[:, :, 0] * CELL`, then `cy = corr(A_ey, e_y)` | `c1_audit.py:430-450`, corr call at `:538-539` | `c1_audit.py:679-694`, corr call at `:694` |
| `corr_ez_vv` construction: `e_z_vv = E_tz[:, :, 1] * CELL`, then `cz_vv = corr(A_ez, e_z_vv)` | `c1_audit.py:546-548` | `c1_audit.py:687-695` |
| corrected criterion `ok_arr` (`\|corr_e_y\| >= CORR_EY_MIN and \|corr_ez_vv\| >= CORR_EZ_VV_MIN`) | `c1_audit.py:575-577`, and `:575-581` where it was pooled with the legacy screen | `c1_audit.py:724-726`; pooled with the legacy screen, `:724-730` |
| legacy criterion `ok_arr_legacy` (`\|corr_e_y\| >= CORR_EY_MIN and \|corr_ez\| <= CORR_EZ_MAX`) | `c1_audit.py:579-581` | `c1_audit.py:728-730` |
| npz payload arrays `corr_ey` / `corr_ez_vv` | `c1_audit.py:651-652` | `c1_audit.py:824-825` |
| `REPRO` recompute loop over both anchors | `c1_audit.py:740-751` | `c1_audit.py:977-985` |

The `corr_e_y` region is the clearest case for why the whole repair had to be done by symbol: `430-450` is 21 lines and `679-694` is 16, because the block was refactored, not merely pushed down. No offset maps one onto the other.

**What was edited, and that nothing else moved.** Twenty-seven lines were edited, listed here so that the change is auditable without a diff: `:14`, `:15`, `:73`, `:74`, `:166`, `:170`, `:174`, `:180`, `:181`, `:182`, `:233`, `:240`, `:261`, `:273`, `:387`, `:388`, `:395`, `:442`, `:569`, `:571`, `:584`, `:585`, `:586`, `:587`, `:588`, `:607`, `:711`. Every edit is **within-line**: the old citation string was replaced by the new one and not one character was added to or removed from any other part of the line. No line was inserted, deleted, split, joined or reflowed. The newline count is **721 before and 721 after**; the file still splits into 722 elements. The edit script matched each old string **exactly once on its designated line** and refused to write at all on any mismatch — the dry run and the write both reported zero problematic matches, and the post-write diff enumerated exactly the 27 lines above.

**The line-630 guarantee, and the one hash that did change.** Line 630 is byte-identical before and after: `Seven entries, no more. Everything else in §§2–3 is an audit of what v1 already had, not a registration.`, sha256 of that line plus its newline `0d7cf7485cc954e931ae43f68ca1858322d92709f03319b3e79e2db7cee643b8`. That is the citation target of `docs/design/t4_amp_ratio.md` §9.5 and §9.7, and it still resolves to the same sentence.

The head-630 prefix hash did **not** survive, and it is recorded here rather than quietly dropped: prefix sha256 `39bb7a7155f43859a46510468f63ee36052ed578c5ad9ac1388214c1a8ff39bb` before, `a03c78d43fd8077df2588281d00a97103e9115ecdc2b3be37326cad789583203` after. Ten of the 27 edited lines (`:14`, `:15`, `:73`, `:74`, `:166`, `:170`, `:174`, `:180`, `:181`, `:182`) lie inside that prefix, so the prefix hash had to change; a repair that leaves the citations in the head wrong would be the only way to keep it. The invariant this repair actually keeps is **line-630 identity plus unchanged line count**, both verified directly, and that is what the committed citations depend on. Whole-file sha256, for completeness: `447802cb3fd16de70c0fe09c3aa707c523c0841509432f4c1e50574136220909` before, `05d7fcf1bcecb1a242350c4469ff94c4156fbc21314eaaddbac83d84d9a3539f` after.

**§10.8's own measurement is superseded here, not deleted.** §10.8 puts the drift at `+27`, reading `CORR_EY_MIN` at `:199` and `CORR_EZ_VV_MIN` at `:220`. Today `grep -n` puts them at `:234` and `:255`. The gap is not a contradiction: the code file grew again above those constants after §10.8 was written, so the `+27` reading was true of a snapshot that is now two snapshots old. The numbers in this section are the ones that resolve today.

**Deliberately left stale.** Listed, so that "stale" is a recorded decision and not an oversight:

* §6.5 (`:573`) resolves its `basis='mixed'` branch as `` `:486-493` `` — a bare range with no file name, and not a `c1_audit.py` citation; it lies outside the scope of this repair and is not re-resolved here.
* §10.6 (`:703`, and the restatement at `:719`) cites `R_extracted` at `c1_audit.py:738` and the `np.savez(` call at `:703`. §10.8 called those two *current*; they have since drifted with the same file growth and now resolve to `c1_audit.py:766` and `c1_audit.py:816`. The doc lines are left as written and the correct numbers are here.
* §9's registered table, rows at doc lines `:637-638`, still cites `c1_audit.py:193` / `:172` for the thresholds and `:575-577` / `:575-581` for the screens. Correct today: `c1_audit.py:255` / `:234` and `:724-726` / `:728-730`. Left unedited on purpose — §9 is the *registered* clause list, this repair confines itself to prose that describes the code, and §10.8 already names those two rows as stale. A second, contradicting patch trail is worse than one honest list.
* §10.8 itself (`:717`) is left as written for the same reason — it is the record of what was believed, and what supersedes it is a clause appended to the end of that same line, not a rewrite of it.

**Line numbers are volatile; symbols are durable.** Every citation this document makes into `c1_audit.py` should be resolved by the symbol (`grep -n '^CORR_EY_MIN *='`), never by the number printed beside it. The numbers in this section are correct as of this append and will drift again the next time the file grows above them; the symbols will not. That is why both tables above are keyed by symbol and by code region, and why the four items above are listed rather than silently normalised.

**The chain this append completes.** Re-measured on the working tree when this note was written, with the same method as every link above:

* **Prefix link, resolved rather than restated.** head-630 prefix sha256 is `e60a092946615f54ab481cb5515fe64bbf66d8bced2a963a13384017ac81a56a` — the `e60a0929…` that the closing append to §10 asserts, checked against the file instead of taken on trust. The link before it, `a03c78d43fd8077df2588281d00a97103e9115ecdc2b3be37326cad789583203`, is the *after* value recorded in this section above, so the prefix chain here reads `39bb7a71…` → `a03c78d4…` (§11's repair) → `e60a0929…` (§10's closing append).
* **Whole-file sha256 before this note:** `8cb9d55d0e977e8194578375ce4d38698df4e75947ba18a4a6a874fc20d21183`, 84,603 bytes, 792 lines. That is not the `05d7fcf1…` *after* value recorded above, and the gap is not a contradiction: the file moved once more when the closing append to §10 was written — the same edit that moved the prefix from `a03c78d4…` to `e60a0929…`. A file cannot contain the hash of its own post-edit self, so the whole-file hash *after* this note is reported in the change report and not here; every hash in this bullet is a *before* value and is reproducible.
* **Line 630 is still line 630.** It still reads `Seven entries, no more. Everything else in §2–§3 is an audit of what v1 already had, not a registration.`, own sha256 `0d7cf7485cc954e931ae43f68ca1858322d92709f03319b3e79e2db7cee643b8`, and the head-630 prefix hash is unchanged by this append (`e60a0929…` before and after): this note sits entirely below line 630 and moved nothing at or above it. The load-bearing invariant of the whole chain — line-630 identity plus a fixed prefix — is the one that held.
