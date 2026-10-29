# Dispatch 53 — Acceptance criteria: close the cheap attacks, keep the gate unfrozen

**Written:** first action of dispatch 53, before any other artefact.
**Status:** front-most fence of the dispatch. Nothing below is negotiable.
**Coexists with:** `docs/design/d52_acceptance.md` (dispatch 52, first pass) and
`docs/design/d52b_acceptance.md` (dispatch 52b). Neither is edited by this dispatch.

---

## 0. What this file is, and the two labels it uses

This file fixes what dispatch 53 must deliver, before anything it governs exists. It is not
edited afterwards except by an appended reconciliation.

Two labels, and no third:

- **`[BRIEF]`** — content the brief fixes: names, numbers, rule statements, fences, and any
  passage given below in double quotation marks. Those are the supervisor's words.
- **`[BRIEF-SUMMARY]`** — content the brief fixes in substance but which the writer holds in
  structured (bullet) form. Faithful to the criteria it states; not character-exact to the
  prose.

**What this file does not claim.** The brief reached the writer of this file through a context
compaction. Nothing below is therefore labelled `[VERBATIM]`, and this file does not claim to
reproduce the brief character for character. It is authoritative **in substance**, and the loss
of exactness is stated here rather than concealed: a requirement dressed as a quotation is the
defect class the ledger exists to record — a specific that reads as verified while being
ambiguous. The loss is **disagreement 1** in section 7 and is reported at close-out, as the
brief requires of every disagreement.

**The line this dispatch starts from `[BRIEF]`.** `docs/design/soundness.md` section 9(d) says of
itself: "the nine original errors were all specifics, and this is 143 specifics whose tier
assignments nobody has checked — one level up, not one level out" [quoted from
`soundness.md:545-548`]. The supervisor's reading of that line is the frame for this dispatch: it
is "the correct thing for an engineer to write about their own work", and "It's a map of what we
don't know. Maps of ignorance are the useful kind."

---

## 1. Fences `[BRIEF]`

> **Fences:** no gate run; no `emfit/` edits; do not modify the frozen A-1.5 module or
> `preservation_gate.py`; `decisions.md` append-only; Task 3 ends the dispatch; do not freeze the
> pairing rule.

> **If the tree contradicts this brief, the artifact wins — report before editing.**

> **No line numbers in this brief by design.**

The third fence is why every citation in this file is to a **tree** location and never to a brief
location. The second fence is the one that binds hardest: where this file and the tree disagree,
the tree is quoted and the disagreement is written out in section 7, before any edit is made.

Provenance tags on every number below, as in the two predecessor acceptance files:
`[VERIFIED this session]` for what was read or measured while writing this file, `[RELAYED]` for
what is carried from the record, `[USER]` for the dispatch's own instruction. Untagged means
`RELAYED`.

---

## 2. Task 1 — one block appended to `decisions.md` `[BRIEF-SUMMARY]`

Nine items, in the order the brief gives them. Each is a required clause. A block that omits one
is not the deliverable, and a block that merges two is not either — items 3, 4 and 5 exist
precisely because merging them is how the previous dispatch went wrong.

1. **The six rulings of the previous dispatch, all accepted.** Acceptance is recorded, and the
   rulings are **enumerated by name**. An acceptance of rulings that are not named is not
   checkable, and this file does not accept it as compliance. The names come from the brief's own
   list, not from reconstruction.
2. **The `T`→`E` rename, with its collision evidence.** The brief calls the catch "a better catch
   than it looks" `[BRIEF]`. The evidence goes in with it: `T4_amp` is a recorded **FAIL** and
   `T4c` a recorded **PASS** in `docs/design/m3c_gate_v2.md`, so "Two T4s would have been a
   citation trap within a week." `[BRIEF]`
3. **"One void, two vacuous", with the three repair classes named separately** `[BRIEF]`:
   - a **vacuous** clause returns a constant regardless of the data — the `0.886463` falsifier at
     `decisions.md:8626` — and is **re-derived**;
   - a **mis-specified** clause fires on a discretisation artefact — the contrast-2.5
     pairing/annihilation branch at `decisions.md:8616` — and gets a **discriminator**;
   - a **void** clause is unsatisfiable at any permitted order — Amendment 3's widened
     preservation clause at `decisions.md:8596` — and is **rewritten**.

   The count is one void and two vacuous, and the reason the classes are kept apart is that they
   need different repairs. "Three void clauses" is the phrase being corrected, so it must not
   reappear as a summary of this item.
4. **The supervisor's tenth verified error:** that the clause count was given as three void
   clauses when it is one void and two vacuous. Recorded as the supervisor's error, in the
   supervisor's numbering, and not softened into a difference of wording.
5. **The supervisor's eleventh verified error:** that three of the five named attacks were
   reported as already closed by pre-existing findings when one was. The one is attack (4), a pass
   achieved by comparing a run against itself, closed by section 10 finding 11 — `E_FLOOR` and
   `rho = +inf` make the exact degenerate form FAILED-TO-MEASURE with nothing in section 11
   contributing. On the record at `pairing_rule_preregistration.md:520` (`CLOSED (pre-existing)`)
   and `decisions.md:8671` `[VERIFIED this session]`.
6. **The "E2 is not a null category" correction, stated against ledger section 9** `[BRIEF]`.
   The correction stands on the A-run evidence alone: orders `2.0068 / 2.0378 / 2.0337`, three
   resolutions, all inside the band `[1.7, 2.3]`, citable at
   `preservation_gate_preregistration.md:53-55`, `preservation_gate_results_a35.md:63-65` and
   `decisions.md:8620` `[VERIFIED this session]`. The A-1.5 pair `1.9819 / 1.9955` is
   **corroborative and non-citable**: it occurs nowhere in `docs/` or `decisions.md`, only in
   gitignored `.scratch/d50/pg_a15.json:775-776` and `.scratch/d50/pg_a15.log:20`, and its own
   inputs `4.303256e-04 / 1.089382e-04 / 2.731929e-05` appear nowhere in the tree either
   `[VERIFIED this session]`. Under this project's own standing rule — an artefact the auditor
   cannot read does not support the claim it is offered for, the defect already recorded against
   inventory row `A32` — the pair is corroborative and not citable, and it is recorded with its
   `.scratch` paths rather than dropped. **The correction is not weakened by this:** it is carried
   by the part of the evidence that is on the record. The framing is the supervisor's, verbatim:
   "we can say we measured it, and we cannot yet say the measuring instrument is trustworthy.
   Those are different statements and only the first one was ever true." `[BRIEF]`
7. **The refusal to freeze the pairing rule**, on the reason that **seven of seven** constructed
   attacks are open. The governing count is seven rows, `AT-1` to `AT-7`, at
   `pairing_rule_preregistration.md:525-531` `[VERIFIED this session]`; the four places that say
   "six" are stale — see disagreement 4.
8. **The escaped-pipe hazard, recorded as "a hazard note for every future audit"** `[BRIEF]`. The
   substance: five inventory rows (`A13`, `A23`, `G04`, `G06`, `G14`) carry an escaped pipe in the
   claim cell, so their tier sits in the sixth pipe-delimited field; an `awk` on the fourth field
   reports `E3` 54 and `E5` 27 against the true 58 and 28, and a total of 138 against 143
   `[RELAYED: d52b_acceptance.md section 7.5]`.

---

## 3. Task 2 — close the three cheap attacks `[BRIEF-SUMMARY]`

The three are **AT-2**, **AT-6** and **AT-4**. Each is closed in
`pairing_rule_preregistration.md` section 11 **and in the rule itself**, because a row that says
"closed" while the rule is unchanged is a bookkeeping entry and not a repair.

**Out of scope here `[BRIEF]`:** AT-1, AT-3, AT-5 and AT-7 are not attempted in this task. They
need measurements or plumbing and belong to their own dispatch (Task 3 specifies them; it does not
implement them).

### 3.1 AT-2 — the sort key

Requirements:

- Pin one canonical sort key explicitly in the rule, and in the record, so that two records of one
  physical case are comparable.
- State what happens at the `k_candidates` cut, as a pre-registered quantity rather than as an
  implementation default.
- Close it, or state precisely why it cannot close.

One correction that must be carried in the closure, because the brief's phrasing presupposes
something the rule does not contain: **there is no sort-key clause and no truncation clause in
R1-R6 at all.** Section 4 never mentions ordering; the only occurrence of `k_candidates = 16` is
`pairing_rule_preregistration.md:63` `[VERIFIED this session]`. So AT-2 is an **addition**, not a
revision of an existing clause, and the closure must say so — see disagreement 6.

### 3.2 AT-6 — the total order

Requirements:

- Replace the total order with **per-root independent verdicts**, so that one root's instrument
  failure cannot mask another root's physics failure.
- State the run-level aggregation rule, and state what happens when roots disagree.

The thing being replaced is the order printed at `pairing_rule_preregistration.md:330`:
`FAILED-TO-MEASURE` > `UNTRACKED-AT-COARSE` > `STOPPED` > `FAIL` > `PASS`, defended at lines
331-336, and qualified at line 337 by the sentence "Every per-root outcome is written to the
record, so a token that loses precedence is not lost." `[VERIFIED this session]` The closure must
say whether that sentence, which is a promise about the record, is now to be enforced as a
requirement on the artefact or withdrawn as untrue of the current artefact.

### 3.3 AT-4 — self-reference

Requirements `[BRIEF]`:

> "the reference ladder must come from the analytic routine or an external tool, never from the
> solver's own converged output"

and the closure must state **how the gate detects a violation**. The brief calls this "the
highest-value two lines in the dispatch" and "the one that should keep you up at night" `[BRIEF]`.

Two constraints on the answer, both from the tree:

- `preservation_gate.py` is frozen, so detection cannot be implemented inside it. The closure must
  say where the check runs instead — a provenance field on the reference ladder registered by the
  schema that registers the run, plus a stated failure mode when the field is absent.
- The exact degenerate form is already caught, by section 10 finding 11, and only the perturbed
  form survives: a self-generated ladder carrying a small non-zero perturbation reports PASS today
  (`pairing_rule_preregistration.md:529`, `decisions.md:8671`) `[VERIFIED this session]`. A
  closure that claims to have closed the exact form has closed nothing new.

---

## 4. Task 3 — specify the remaining four, do not implement `[BRIEF-SUMMARY]`

The brief names **four** attacks and supplies specification bullets for **three**: AT-1, AT-3 and
AT-7. AT-5's bullet is **absent from the brief**. This file requires all four to be specified and
records AT-5 as the brief's own gap — it does not invent a specification for it, and it does not
let the gap pass silently (section 4.4).

Each specification must state the measurement or artefact field, where it lives, and what the gate
does when it is missing. A specification whose measure does not exist in the tree must **say it
does not exist and name what must be built**; it must not describe the measure as though it were
being wired up.

### 4.1 AT-1 — mode identity across levels `[BRIEF-SUMMARY]`

Required: what cross-level mode-identity measurement distinguishes a **consistent swap** from a
**correct assignment**, and at what bar. The brief's candidate is "eigenvector overlap between
levels in the `B` inner product", which it says "we already compute for `residual_eps_mu`".

**That premise is wrong, and the specification must say so** `[VERIFIED this session]`:

- `residual_eps_mu` is `||(M_eps - M_mu) Z||`, a subspace residual of the deflation operator
  (`emfit/mode2d.py:1499`, computed at `:1592`). It is not an eigenvector overlap, it is not
  cross-level, and it involves no `B` inner product.
- The gate does not compute any overlap: it only carries `residual_eps_mu` through from the solve
  record (`tools/host/anchor/preservation_gate.py:305`, `:308`, `:362-372`).
- Ledger claim `C21` (`soundness.md:238`, E3) says identity "is by overlap, not against an
  analytic mode", with scope "the sizes compared" — it is a claim about in-process reproduction at
  fixed size, not a cross-level overlap with a stated bar, and at E3 it is not citable as a
  measure that exists.

So the required output is: a stated bar for `abs(v_k . v_k+1)` per track per level, a statement
of what must be built to produce it, and — following the precedent already in this project — that
it be a **mandatory but non-verdict diagnostic**, exactly as `residual_eps_mu` is mandatory at
every level and explicitly never a pass condition (`pairing_rule_preregistration.md:84-88`,
`d50_acceptance.md:37`) `[VERIFIED this session]`. A new bar that decides a verdict is a new
tolerance, and this dispatch does not introduce one.

### 4.2 AT-3 — a level where the deflation subspace changed `[BRIEF-SUMMARY]`

Required: what the gate must read from the deflated set to detect a changed subspace, and **where
that information currently lives**.

The answer to the second half, from the tree `[VERIFIED this session]`:

- It does not live in the artefact at all. Nothing in R1-R6 reads the deflated set
  (`pairing_rule_preregistration.md:527`), and `spectrum_short` counts only the level-3 real betas
  against the number of roots.
- The deflated set exists only inside the deflation call (`emfit.mode2d.solve_modes_deflated_v2`,
  named at `pairing_rule_preregistration.md:64`) and is not written per level into any record the
  gate reads.

So the specification is a **new artefact field**, not a rule change: the deflated eigenvalue set
per level, recorded, plus the refusal token for a track whose level-`L` candidate lies inside a
coarser level's deflated set. The specification must also state the case where the set changes and
no track is affected — AT-3's PASS case — because that is the case the current rule reports as
PASS.

### 4.3 AT-7 — the `h`-dependent tolerance `[BRIEF-SUMMARY]`

Required `[BRIEF-SUMMARY]`: the `h`-dependent tolerance derived from the scheme order, with its
feasibility argument. "Do not choose a constant" `[BRIEF]`. State the derivation, the expected
level-1 error at `eps_r = 3.5`, and whether the rule clears it.

This specification must be written **against section 3.1 of the same pre-registration, which
rejected exactly this repair on arithmetic** `[VERIFIED this session]`:

- Pairing all four reference roots on the level-1 rung at contrast 2.5 needs a level-1 tolerance
  above `7.09799e-02`, the order-4 level-1 distance, which is `3.549 x` the frozen `2e-2`
  (`pairing_rule_preregistration.md:120`).
- The largest level-1 distance observed at contrast 1.0 or below is `8.88015e-03`; ten times it,
  `8.9e-2`, clears the required `7.098e-2` by only `1.25 x` — a fit to the datum it must
  accommodate (`pairing_rule_preregistration.md:122-124`).
- At that width the level-1 test is inert: it exceeds every level-1 distance at contrasts 0.5 and
  1.0 by ten times, so no coarse-rung annihilation could be detected.

The specification must therefore either (a) derive a tolerance whose value is **not** governed by
the A-3.5 datum and show the arithmetic, or (b) state that section 3.1's rejection is overturned
and on what new argument. It may not re-propose the rejected form without engaging the numbers
that rejected it. This is disagreement 8.

### 4.4 AT-5 — the specification the brief does not govern `[BRIEF: gap]`

The brief names AT-5 among the four to be specified and supplies no bullet for it. The
specification is **required** by this file and **ungoverned** by the brief: the executor must
write it, using the tree's own statement of the attack, and must report that it did so without a
brief bullet.

The tree's statement, for the executor to specify against (`pairing_rule_preregistration.md:530`)
`[VERIFIED this session]`: annihilation misreported through the `STOPPED` and
`UNTRACKED-AT-COARSE` precedence — a genuine loss of a mode at contrast `<= 2.5`, and separately a
coarse-rung solver failure that loses the mode at level 1 only. The gate reports `STOPPED` (exit 3,
"annihilation suspected") for the first and `UNTRACKED-AT-COARSE` (exit 4) for the second, and
both tokens assert a cause the rule cannot establish: the frozen gate's `STOPPED` at contrast 2.5
was itself a discretisation artefact with no physical event.

AT-5 and AT-7 are the **two halves of one dispatched theme**: section 11.1 row (5) is marked
`NOT DISTINGUISHABLE` and routes its residue to AT-7
(`pairing_rule_preregistration.md:521`) `[VERIFIED this session]`. The two specifications must
therefore be consistent, and a specification pair that closes one and leaves the other
indistinguishable is the defect restated.

---

## 5. Close-out `[BRIEF-SUMMARY]`

The close-out reports:

1. the commit;
2. **which attacks closed**, by id, and how each was verified without running the gate;
3. **which attacks remain open**, by id, with the reason;
4. the AT-1 and AT-7 specifications, in enough detail that a reader can see whether they are
   buildable;
5. **every disagreement with the brief**, including the three pre-registered here — the labels
   (section 7, disagreement 1), the attack count (disagreement 4) and the AT-5 gap (section 4.4);
6. an explicit statement of whether the rule is **now closer to freezable**, or whether the
   remaining four are **harder than they looked**. This is a required judgement, not a summary: a
   dispatch that closes three cheap attacks and discovers the other four are expensive must say
   that plainly rather than report four rows of "specified".

---

## 6. Reconnaissance, taken before writing this file `[VERIFIED this session]`

| fact | value |
|---|---|
| `docs/design/d53_acceptance.md` before this file | ABSENT; no `d53*` in `docs/design/` |
| `docs/design/pairing_rule_preregistration.md` | 554 L, 44 860 B, sha256 `60cefdd39e8d364fffc28fd67b64de6678d2cd3f3b43ea6f844cc1d6b3c3468e` |
| `docs/design/soundness.md` | 654 L, 56 975 B, sha256 `4c861fbbd0c7814edeaaee9dbbc67e83bc81b54c659e3b53dcfb87baea5c5f5c` |
| `docs/design/d52b_claim_inventory.md` | 331 L, sha256 `79dfd535c95be0283ca6df99bf3d06e4cc579b89f9254b5eb3185a33b7cff0c1` |
| `docs/design/d52b_acceptance.md`, the model for this file | 268 L, 14 430 B |
| newest file in `docs/design` at the time of writing | `pairing_rule_preregistration.md`; nothing newer than it |
| attack rows in the rule's section 11 | seven, `AT-1` to `AT-7`, at lines 525-531 |
| attacked themes in section 11.1 | five, at lines 517-521, statuses `OPENED` x3, `CLOSED`, `NOT DISTINGUISHABLE` |
| sort-key clause in the rule | none; `k_candidates = 16` occurs once, at line 63 |
| truncation clause in the rule | none |
| cross-level eigenvector overlap in the tree | does not exist; appears only as a recommendation (line 525, 535, `decisions.md:8674`) |
| deflated set in the artefact | not recorded at any level |
| `residual_eps_mu` | `\|\|(M_eps - M_mu) Z\|\|`, computed in `emfit/mode2d.py:1592`, carried by the gate and never gated |

Two inherited fences from `d52_acceptance.md`, which this dispatch does not restate and does not
relax: the geometry-A and A-1.5 PASSes are **contrast-contingent** (`d52_acceptance.md:31`), and
if the new rule changes either prior verdict that must be reported under the symmetry clause
(`d52_acceptance.md:77`). The corrected triple — A `8.88015e-03`, A-1.5 `8.25001e-03`, A-3.5
`2.23535e-02` — is **not** monotone in contrast `[RELAYED]`, and no arithmetic in this dispatch
may be built on the assumption that it is.

---

## 7. Where this file departs from the brief, and where the tree departs from both

Reported here, before the work, because the brief's own rule is that the artifact wins and the
disagreement is stated rather than smoothed.

**1. This file is not character-exact, and does not pretend to be.** Stated in section 0. The
brief reached the writer through a context compaction, so `[BRIEF]` marks the supervisor's words
that were carried forward intact and `[BRIEF-SUMMARY]` marks criteria held in structured form.
Nothing is labelled `[VERBATIM]`.

**2. Which of the five order numbers are on the record.** Three of the five are on the record in
three places each — `2.0068`, `2.0378`, `2.0337` at `preservation_gate_preregistration.md:53-55`,
`preservation_gate_results_a35.md:63-65` and `decisions.md:8620`. Two are on no record at all:
`1.9819` and `1.9955` occur nowhere in `docs/` or `decisions.md`, only in gitignored
`.scratch/d50/pg_a15.json:775-776` and `.scratch/d50/pg_a15.log:20`, and their own inputs
`4.303256e-04 / 1.089382e-04 / 2.731929e-05` appear nowhere in the tree, so they cannot be
reproduced from it either. They are geometry **A-1.5**'s order-2 `p_1/p_2`; A-1.5's aggregated
residuals *are* committed (`preservation_gate_results_a35.md:77-79`: `1.521622e-2`, `7.311272e-3`,
`3.585053e-3`), but those give the base-5 exponents `0.8903` and `0.8863`, not these two numbers,
so the committed table does not back them. **The ruling this changes:** the "E2 is not a null
category" correction stands on the A-run evidence alone, which is committed, three resolutions,
all inside band; the A-1.5 pair is corroborative and non-citable and is carried in the record with
its `.scratch` paths. The correction is not weakened by this and the pair is not dropped.

**3. The same quantity is committed with two values.** Order 2's `p_2` is `2.0087` at
`preservation_gate_preregistration.md:54` and `2.0089` at `preservation_gate_results_a35.md:64`
and `decisions.md:8620` `[VERIFIED this session]`. Nothing in this dispatch depends on which is
right, and nothing may cite "the observed order" without naming the file it came from.

**4. The attack count is stale in four places, and the governing count is seven.** The rule says
"Of the six, AT-4 is the one..." (`pairing_rule_preregistration.md:549`), and the dispatch record
says "six attacks" at `decisions.md:8667`, `:8676` and `:8679` — while section 11 holds **seven**
rows, `AT-1` to `AT-7`, and the section 11 preamble accounts for the provenance of AT-1 to AT-6
only `[VERIFIED this session]`. AT-7 was appended without the counts being updated. Dispatch 53
names AT-7, so the count that governs is seven, and the four "six" statements are recorded as
stale rather than followed.

**5. AT-5 and AT-7 are the two halves of dispatched theme (5), and the brief supplies a bullet for
only one.** Section 11.1 row (5) is `NOT DISTINGUISHABLE` and routes its residue to AT-7. The
brief names AT-5 in Task 3 and gives no bullet for it; section 4.4 records that as the brief's own
gap and requires the specification anyway.

**6. AT-2's phrasing presupposes a clause that does not exist.** The brief asks that the sort key
be "pinned explicitly in the rule". There is no sort-key clause and no truncation clause in the
rule at all: section 4 never mentions ordering, and `k_candidates = 16` appears once, at line 63.
AT-2 is an **addition** to the rule, not a revision of it, and the closure must say so.

**7. AT-1's premise is not true of the tree.** The brief says the eigenvector overlap in the `B`
inner product is something "we already compute for `residual_eps_mu`". `residual_eps_mu` is
`||(M_eps - M_mu) Z||`, a subspace residual, not an overlap; the gate computes no overlap of any
kind and only carries the residual through from the solve record. The measure must be built, and
the specification must say so.

**8. AT-7 re-opens a branch the same document rejected on arithmetic.** Section 3.1 rejects the
`h`-dependent tolerance because a constant that must clear `7.09799e-02` at level 1 is a fit to
the datum it must accommodate (`3.549 x` the frozen `2e-2`, clearing by `1.25 x` at `8.9e-2`).
AT-7's specification must either beat that arithmetic or overturn the rejection explicitly. This
is the sharpest disagreement in the dispatch, because the brief's Task 3 bullet and the rule's
section 3.1 cannot both stand as written.

**9. AT-3's required information does not live anywhere yet.** The deflated set is not recorded
per level in any artefact the gate reads; it exists only inside the deflation call. The
specification is therefore a new artefact field, and the closure must not describe it as reading
something that is already written.

**10. Escaped pipes.** Any table row written under this dispatch that carries a pipe inside a cell
must escape it, for the reason recorded at item 8 of Task 1: the count of a pipe-delimited table
is wrong the moment one cell carries an unescaped pipe.

---

## 8. What done means for this dispatch

1. `docs/design/d53_acceptance.md` — this file — exists and is not edited afterwards except by an
   appended reconciliation.
2. `decisions.md` carries one appended block with all nine Task 1 clauses, the six rulings
   enumerated by name, and nothing above the append altered.
3. `pairing_rule_preregistration.md` records AT-2, AT-6 and AT-4 as closed **in the rule as well
   as in the table**, with the rule text changed for AT-2 and AT-6 and the detection point named
   for AT-4; and the three closures state the constraint that each was an addition, not a
   revision.
4. AT-1, AT-3, AT-5 and AT-7 each have a specification in Task 3's document, each stating its
   measure, where it lives, what must be built if it does not exist, and what the gate does when
   it is absent — including AT-5, specified without a brief bullet.
5. No gate run, no test run, no solver run, no build: this dispatch changes text and formats only,
   and every closure that would need a measurement says so instead of claiming one.
6. Close-out states every disagreement in section 7, and answers the freezable-or-harder question
   in one sentence that a reader can disagree with.

No gate run. No `emfit/` edits. No change to the frozen A-1.5 module or `preservation_gate.py`. No
freeze of the pairing rule. `decisions.md` appended to, never rewritten.

## Reconciliation (dispatch 53, appended)

Two defects in this document, found while executing it and recorded here rather than rewritten in
place, by this document's own rule that amendments are appended.

1. The section listing what this dispatch had to verify says "Nine items" and then enumerates
   eight. The count is wrong; the list is right. Eight is the number.
2. A citation in the closure table records `CLOSED (pre-existing)` at `decisions.md:8671`. The
   phrase is at `decisions.md:8668`, and 8671 does not carry it. The line numbers quoted elsewhere
   in this document were checked against an 8726-line file after the dispatch-53 append, not
   before it.

Neither defect moves a verdict, and both are transcription errors in a document whose subject is
the cost of untraced transcription, which is why they are here rather than quietly fixed.

3. Added in a second reconciliation, and it amends the count in the paragraph above rather than only
   adding to it: disagreement 4 in section 7 places the stale "six" at `decisions.md:8667`, `:8676`
   and `:8679`. All three are wrong. The file was 8674 lines when this document was written, so
   8676 and 8679 did not exist at all, and after the dispatch-53 append the three stale phrases sit
   at 8662, 8670 and 8674. This document therefore carries three transcription defects, not two.

4. The count in item 7 of the brief list, "the four places that say `six`", cannot be resolved from
   the tree as it now stands. Three of the four are the `decisions.md` lines corrected in item 3
   above. The fourth is quoted in section 7 as `pairing_rule_preregistration.md:549`, a citation
   made against the 554-line version of that file; at line 549 the present 1297-line file has a
   blank line, so that citation moved when the file grew and has not been re-located. The verified
   count is three, all in `decisions.md`. The word "four" is left standing rather than corrected,
   because this document is append-only and because a count that cannot be checked is the kind of
   thing this document exists to keep rather than to tidy away.
