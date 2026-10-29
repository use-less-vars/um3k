# Dispatch 54 -- Acceptance criteria: instrument the artefact, resolve the committed contradiction, update the ledger

**Written.** This file is the first action of dispatch 54, taken before any other artefact of it.

**Status.** It is the front-most fence of dispatch 54. Nothing below it is negotiable: a later document may narrow a requirement here, but it may not widen one, and any narrowing lands as an appended reconciliation in this file rather than as a silent exception elsewhere.

**Coexists with.** `docs/design/d53_acceptance.md` and the d52 and d52b acceptance files beside it. This dispatch edits none of the three and does not supersede any of them; where they and this file overlap, both stand and the stricter one governs.

## 0. What this file is, and the label it cannot carry

The brief for this dispatch arrives with no line numbers and no numeric claims, by design: it is a description of work, not a citation of evidence. That design has a cost. Every figure in the brief -- the pairing tolerance, the two committed values of the second order's rate, the eleven dropped diagnostics, the demoted ledger rows, the stitched A-3.5 datum -- arrived as a relayed claim. This file's first job is to convert each relayed claim into a verified one or into a named gap, and to do it before the work it authorises starts, because a relayed number that is wrong is more expensive after a build than before one.

The consequence is stated plainly so that no later document inherits the opposite impression: **the dispatch's own brief is not citable.** Where this file cites a number it cites the tree, at a path and a line; the brief appears nowhere in the reference list and appears in the prose only as the reason a number was looked for. A reader who wants to check a figure here should be able to do it without the brief, and if the brief is the only place a figure exists, the figure is a gap and is labelled one.

Three tags carry the standings of the claims below. **CONFIRMED** means a tree line says it and the line is quoted; it is the only tag that may be cited downstream. **CONTRADICTED** means two tree lines disagree; the file says which line is defective and on what arithmetic, and an unresolved instance of this tag blocks the requirement it sits under. **NOT-FOUND** means the search was run and returned nothing; it is a claim about the search, not about the world, and it expires the moment a line is produced.

## 1. Fences

1. No gate run. Nothing in this dispatch executes `tools/host/anchor/preservation_gate.py`, its a35 driver, or any ladder.
2. No solver LOGIC changes in `emfit/`. Diagnostics only: values may be computed and stored, no selection, tolerance or convergence rule may move.
3. Do not modify `preservation_gate.py`'s existing criteria. Fields may be added; `ORDER_LO`, `ORDER_HI`, `PAIR_TOL` and every comparison that reads them stay byte-identical.
4. `decisions.md` is append-only.
5. Task 4 ends the dispatch.
6. Do not freeze the pairing rule.

The second and third fences bite hardest, and they bite together. The additive-only fence is precisely what makes Task 1 safe: four new fields cannot move a verdict if no criterion can read them, and the field selection is two closed literal dictionaries, so "cannot be read" is checkable by inspection rather than argued. A dispatch that added a diagnostic and touched a threshold in the same commit would destroy the evidence that the diagnostic is inert, and the record would have no way to tell a field that merely recorded from a field that decided.

## 2. Task 1 -- the four fields

Each field is stated as three questions: what exists today, what must be added, and whether the addition changes a verdict or only records one. The third answer is short and the same for all four: **none of them may change a verdict.** For the first three that is a consequence -- they write values nothing reads. For the fourth it is a fence rather than a consequence: AT-1's overlap is a mandatory non-verdict diagnostic, exactly as `residual_eps_mu` is today, reported and never gated.

### Field 1 -- per-level deflated set (AT-3)

**Exists.** The deflated eigenvalue set is computed per level, and eleven diagnostics describing it are already computed and then dropped: `z_dim_closed_form`, `column_region`, `columns_v1`, `columns_added`, `z_dim_v2`, `region_contrast`, `region_rows`, `z_dim_closed_form_v2`, `n_dof`, `n_columns` and `residual_grad`, all at `emfit/mode2d.py:1579-1599`. The gate's per-level record keeps four of them, at `tools/host/anchor/preservation_gate.py:294-310`.

**Must be added.** The eleven, plus the removed eigenvalues themselves. This is narrower than "build the diagnostics": the work is a changed write, not new mathematics.

**Verdict.** Records only, and the fence in section 1 is what guarantees it.

### Field 2 -- per-candidate residuals (AT-5)

**Exists.** The residual is computed per candidate at `emfit/mode2d.py:994` and discarded at `:1025` and `:1029`; only the chosen candidate's value survives.

**Must be added.** The per-candidate value carried through `candidate_records` (`emfit/mode2d.py:798`), so that a root paired to a non-chosen candidate can still be scored.

**Verdict.** Records only.

### Field 3 -- per-root verdicts (AT-6)

**Exists.** Nothing. `root_verdicts` has no code anywhere in the tree -- not a function, not a key, not a test; it exists in the prereg's prose only.

**Must be added.** The whole concept: a per-root outcome that says, for each frozen root, which condition it met and which it did not.

**Verdict.** Records only -- and this is the one of the four that is a new concept rather than a changed write, which is why it carries the most design risk and the least arithmetic.

### Field 4 -- cross-level overlap in the B inner product (AT-1)

**Exists.** Not found: no stored field, no callable, nothing under that name or its neighbours.

**Must be added.** The overlap between consecutive levels' subspaces, measured in the B inner product, stored per level.

**Verdict.** Records only, by fence: mandatory, reported, never gated, in the manner of `residual_eps_mu`.

### The whole of the field selection

There is no named whitelist to edit. The gate's field selection is two closed literal dictionaries -- the per-level record at `tools/host/anchor/preservation_gate.py:294-310` and the top-level payload at `:637-660` -- and nothing else validates the schema. So "add a field" means editing two dictionaries and the writer that fills them, and it means nothing else; there is no third place where a field can be silently admitted or silently refused. The schema is already nested lists, so an additive per-level array needs no schema change either.

## 3. Task 2 -- the two committed conflicts, with the answers pre-registered

Both questions were put to the tree before the work was specified, and both answers are registered here so that an executor cannot mistake a closed question for an open one and spend a task re-deriving it.

### (a) Contrast

**RESOLVED AND DEFINITIONAL.** `docs/design/pairing_rule_preregistration.md:81` defines the geometry column as `contrast` -- `c = eps_r - 1` -- reinforced at `docs/design/preservation_gate_results_a35.md:5` and `docs/design/preservation_gate_preregistration_a35.md:9`. Contrast 2.5 therefore IS `eps_r` 3.5, and no geometry in this line is ambiguous. The older `docs/design/preservation_gate_preregistration.md` contains no occurrence of the word contrast at all -- silent, not contradictory, and a document that does not use a term cannot misuse it. The label question is already scoped by the prereg itself at `:1271-1276`, which records the discrepancy and states that nothing depends on the answer except the label.

The requirement is one line of definitional note at the point of first use, and it is a requirement because a definitional identity is the cheapest possible repair and the most expensive thing to leave implicit. If the convention is used anywhere to mean `eps_r` itself, that use is errata and is corrected, not interpreted.

### (b) The second order's rate

**SETTLED BY ARITHMETIC.** `2.0087` stands at `docs/design/pairing_rule_preregistration.md:54`; `2.0089` stands at `docs/design/preservation_gate_results_a35.md:64` and at `decisions.md:8620`. The two committed residual digits decide it: `log2(1.264530e-04 / 3.141941e-05) = 2.008873`. The 2.0089 copies are right and the 2.0087 copy is defective. The discrepancy is already noted at `decisions.md:8697`, `docs/design/soundness.md:678-679` and `docs/design/d53_acceptance.md:357-358`, so this task does not discover it; it closes it.

**The requirement.** The errata must name a CITABLE source for those two residual digits. The run log `.scratch/d51/pg_a20.log:20` agrees with 2.0089, but `.scratch` is gitignored and is therefore corroboration only, never a citable source. If the two residual digits exist only under `.scratch`, the number stays flagged and is not silently corrected. That distinction is the point of the requirement: an errata that cites an uncommitted log has replaced one uncitable number with another, and has done it invisibly.

## 4. Task 3 -- the prereg revision

Three paragraphs are required, and then one more that reconnaissance forces.

**(i) The distinction the revision turns on.** An absolute-distance tolerance -- a fixed band in relative `beta`, applied at every rung and every contrast -- is what section 3.1 rejects, and it rejects it correctly: it cannot be chosen without fitting the case it must gate, and at the width that works it is inert. A ratio-consistency band is a different object: it asks whether successive errors contract at a rate the scheme's order already implies, and its width comes from the order band rather than from a datum. AT-7 is admissible where the absolute tolerance was not. The revision must say this in as many words, and must say that the fix replaces absolute-distance pairing with ratio-consistency pairing. That is the substantive change of the task; everything else in the revision is wording.

**(ii) AT-7's datum is provisional and its composition is stated.** The datum is composed from two runs. The revision must carry it as provisional, with a stated confirmation-or-amendment rule for the first single-run datum that arrives: what will be recomputed, against which record, and what happens to the band if the single-run value falls outside it.

**(iii) Keep the derivation on the ratios.** The derivation must not be re-derived from a datum that does not exist. Ratios are the object; the constant behind them is not a constant of the rule and is not proposed as one.

**The finding reconnaissance forces, which this task must absorb.** `7.09799e-02` is a PAIRING DISTANCE, not an `e_k`: it is the order-4 root's nearest-candidate distance on the level-1 mesh, at `.scratch/d51/pg_a35.log:39` and `docs/design/preservation_gate_results_a35.md:32`. And the three levels do not come from one process -- the registered run STOPPED at level 1 (`.scratch/d51/pg_a35.log:41-42`) and a supplementary run covers levels 2-3 only (`.scratch/d51/pg_a35_l23.log:47`), which the results document states outright: `no single run ever produced A-3.5 at all three levels` (`preservation_gate_results_a35.md:81`). So the level-1 member of the ratio `e_2/e_1` is not the same kind of quantity as the level-2 and level-3 members. The revision must either restate the derivation on a quantity that exists at all three levels, or state that the level-1 anchor is a pairing distance and show that the band still holds under that reading. What it may not do is present the result as a formula that is merely provisional; a formula whose first term is a different kind of object is not provisional, it is unsupported.

## 5. Task 4 -- the ledger

`docs/design/soundness.md:207-208` states the rule that governs the whole task: a row's tier is a ceiling, no claim rises above the rows it rests on, and a claim resting on two rows takes the weaker. A17 and A18 are demoted at `docs/design/pairing_rule_preregistration.md:477-482` and again at `:972`. The consequences are concrete and there are only two of them:

- Claim C1 keeps rows A01, A19 and A20 and loses A18 -- three of four.
- Claim C9 has no surviving evidential row. Only B08 remains, and `docs/design/soundness.md:226` already flags the harness that produced it as suspect.

Neither claim can remain E3 as written. The report must state, per claim, which rows it lost and what tier it lands on, and a claim that cannot survive its lost rows is marked **Withdrawn** rather than degraded to a lower grade -- a degraded claim invites a later reader to treat it as weak evidence, which is exactly what it is not. A ledger whose rows outlive their evidence is the failure the ledger exists to prevent, which is why this task is not bookkeeping.

## 6. Reconnaissance table

| fact | citation |
|---|---|
| contrast defined as `c = eps_r - 1` | `docs/design/pairing_rule_preregistration.md:81` |
| same convention, results document | `docs/design/preservation_gate_results_a35.md:5` |
| same convention, a35 prereg | `docs/design/preservation_gate_preregistration_a35.md:9` |
| label question already scoped | `docs/design/pairing_rule_preregistration.md:1271-1276` |
| `p_2 = 2.0087` | `docs/design/pairing_rule_preregistration.md:54` |
| `p_2 = 2.0089` | `docs/design/preservation_gate_results_a35.md:64` |
| `p_2 = 2.0089`, prose | `decisions.md:8620` |
| defect already noted, three places | `decisions.md:8697`; `docs/design/soundness.md:678-679`; `docs/design/d53_acceptance.md:357-358` |
| agreement, corroboration only, gitignored | `.scratch/d51/pg_a20.log:20` |
| per-level record dictionary | `tools/host/anchor/preservation_gate.py:294-310` |
| top-level payload dictionary | `tools/host/anchor/preservation_gate.py:637-660` |
| eleven dropped diagnostics | `emfit/mode2d.py:1579-1599` |
| per-candidate residual computed | `emfit/mode2d.py:994` |
| per-candidate residual discarded | `emfit/mode2d.py:1025`; `emfit/mode2d.py:1029` |
| `root_verdicts` exists in prose only | `docs/design/pairing_rule_preregistration.md`; no code in the tree |
| tier is a ceiling | `docs/design/soundness.md:207-208` |
| A17 and A18 demoted | `docs/design/pairing_rule_preregistration.md:477-482`; `:972` |
| B08 harness suspect, C9's only survivor | `docs/design/soundness.md:226` |
| no single run at all three levels | `docs/design/preservation_gate_results_a35.md:81` |
| registered run STOPPED at level 1 | `.scratch/d51/pg_a35.log:41-42` |
| supplementary run, levels 2-3 only | `.scratch/d51/pg_a35_l23.log:47` |
| `7.09799e-02` is a pairing distance | `.scratch/d51/pg_a35.log:39`; `docs/design/preservation_gate_results_a35.md:32` |
| `C_k = 2.977113e5 / 3.134437e5 / 3.174860e5` | `docs/design/pairing_rule_preregistration.md:1255-1258` |
| window bounds `0.20306` / `0.30779` and `0.04123` / `0.09473` | `docs/design/pairing_rule_preregistration.md:1260-1262` |
| recorded ratios `0.26321` and `0.06665` | `docs/design/pairing_rule_preregistration.md:1261-1262` |
| margins `1.296` / `1.169` / `1.616` / `1.421` | `docs/design/pairing_rule_preregistration.md:1261-1263` |
| margins `3.549` and `1.25` | `docs/design/pairing_rule_preregistration.md:126`; `:129` |
| `1.231`, and no line gives 1.23x | `docs/design/pairing_rule_preregistration.md:1264` |
| orders `2.0068` / `2.0378` / `2.0337` | `pairing_rule_preregistration.md:53-55`; `preservation_gate_results_a35.md:63-65`; `decisions.md:8620` |
| log2 ratios `2.038` / `2.009` / `2.034` / `2.008` | `docs/design/pairing_rule_preregistration.md:1236` |
| mislabelled `error ratio` | `docs/design/pairing_rule_preregistration.md:1236` |
| order band `1.7` to `2.3` | `tools/host/anchor/preservation_gate.py:64-65` |
| frozen pairing tolerance `2e-2` | `tools/host/anchor/preservation_gate.py:63` |

## 7. Where the tree departs from the brief

1. **Contrast is definitional, not a conflict.** The brief called it an open conflict; `pairing_rule_preregistration.md:81` defines it, and two further documents use the same convention. Consequence: Task 2(a) is one line of note, not an investigation.
2. **The second order's rate is settled by arithmetic.** `log2(1.264530e-04 / 3.141941e-05) = 2.008873`. Consequence: Task 2(b) needs an errata with a citable source, not a run.
3. **There is no named whitelist.** "The whitelist" in the brief names two literal dictionaries, at `preservation_gate.py:294-310` and `:637-660`. Consequence: "add a field" is two dictionary edits plus the writer, and the inertness argument is an inspection, not a test.
4. **`7.09799e-02` is a pairing distance, not an `e_k`** (`.scratch/d51/pg_a35.log:39`; `preservation_gate_results_a35.md:32`), and the three levels come from two processes (`preservation_gate_results_a35.md:81`). Consequence: AT-7's feasibility argument is an argument about a distance the pairing rule would have to accept, not about an error the scheme produces -- which changes what the band is a band on. **This is the sharpest departure, and the only one that can invalidate the derivation rather than its wording.**
5. **No line in the tree gives `1.23x`.** The figure at `pairing_rule_preregistration.md:1264` is `1.231`. Consequence: quote it as 1.231 or do not quote it.
6. **`prereg:1236` mislabels `p_k` as an `error ratio`.** The quantities `2.038` / `2.009` / `2.034` / `2.008` are base-two logarithms of the ratios, as the same document defines them at `:354` and `:671`. Consequence: the errata carries this too, or the next reader recomputes a ratio and gets 4.
7. **AT-3's diagnostics already exist.** Eleven of them are computed at `emfit/mode2d.py:1579-1599`. Consequence: Field 1 is a changed write, which narrows Task 1 and lowers its risk.

## 8. What done means

1. This file exists, unedited since its first write except by appended reconciliation.
2. Four fields are recorded in the artefact: per-level deflated set, per-candidate residuals, per-root verdicts, cross-level overlap.
3. The verdict question is answered per field, in the report, in the negative, and the additive-only fence is shown to hold by inspection of the two dictionaries.
4. Both Task 2 questions are closed, each either with a citable source or with an explicit flag saying what is missing -- an explicit flag closes the task and a silence does not.
5. The prereg revision carries the three required paragraphs and the absorption of the pairing-distance finding.
6. `docs/design/soundness.md` records the row-level movement: which claim lost which row, what tier it lands on, and which claim is Withdrawn.
7. A close-out sentence states, explicitly, whether any of the seven attacks moved from closed in the rule to `in force` -- and if none did, the sentence says none did.

## 9. Provenance

This file was written on dispatch 54, before any other artefact of dispatch 54 existed, and it is not edited afterwards except by an appended reconciliation that names what it changes and why. Section 6 is the part that makes the rest auditable: a claim in sections 0-5 without a row there is a relayed claim and is not citable, whatever its confidence.

This file gates dispatch 54 in the same way that `docs/design/d53_acceptance.md` and its two predecessors gated theirs.
