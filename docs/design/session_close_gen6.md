# Session close, generation 6 — three failures of a number's warrant, and two things the ladder arithmetic does not license

Provenance tags: **[M]** measured in this repository against a named artefact; **[L]** read from the
project's own record and cited there; **[R]** relayed from the supervisor seat, unverified, not graded;
**[UNVERIFIED]** believed here with no means to check. Every number below carries one. A number with
no tag should be read as a hypothesis and not as an input — this document is written by the seat
generation 5 described, so it is placed under that seat's rule instead of above it.

STEP 0, recorded because the first thing a generation gets wrong is whether its job is new: a glob of
`**/session_close_gen*` over the workspace returns **exactly one** file, `docs/design/session_close_gen5.md`
[M]. There is no gen6 and no gen7 before this one. That fact is used once in §1 as orientation and once in
§2.1 as the finding itself.

## 1. What this pass did

No FDTD run, nothing re-graded, no gate re-priced, no file under `evidence/` or `tools/` written. It read
the rung-C record against the artefacts it cites and wrote down three places where the prose and the
artefact disagree, in the form that makes the disagreement checkable next time.

## 2. Task A — three failures, not three wrong numbers: one structural, one arithmetic, one provenance

Two rules are quoted here and the order is not decorative. The first is generation 5's, and this document
is an application of it, not an improvement on it [L, `docs/design/session_close_gen5.md` §2 L74–80]:

> **Physics reasoning is yours.** Reasoning from Maxwell's equations about what a result must look like,
> what a discrepancy implies, which of two explanations is dimensionally or variationally admissible —
> that is within this seat's competence and should be trusted as such. **Project-state claims must be
> relayed or verified.** What is in a file, who calls a function, how many lines it has, whether a test
> exists, which module imports which — none of that can be reasoned to, and none of it may be asserted
> without a tag that says where it came from.

The second is what this generation adds to it, and it is carried character for character rather than
paraphrased, because two of the three clauses below are only visible once it is written down:

> Physics reasoning is mine; project-state claims must be relayed or verified. A reading built on numbers
> with mixed provenance inherits the weakest tag. When I cannot name a source, the number is [R] by
> default, and so is any claim resting on it.

The four movements are the same in all three cases and they are the whole method: what he said, what the
artefact says, how it was caught, what changed in the record. A correction that stops after the second
movement is an argument, not a repair.

### 2.1 A container that does not exist: the Gen-7 session close — structural

- **What he said.** "Record it in the Gen-7 session close" [R].
- **What the artefact says.** The STEP 0 glob over `**/session_close_gen*` returns **exactly one** path,
  `docs/design/session_close_gen5.md`, and no other generation [M]. The instruction named a document that
  has never existed. Nothing about the phrase "the Gen-7 session close" reads as a claim about a file
  rather than a name for one, which is what makes this different in kind from a stale number: a stale
  number looks like a number.
- **How it was caught.** By running the glob instead of complying. That is the whole tell. A search was
  cheaper than a write, and only the cheaper action could have found it; the instruction was not
  internally inconsistent, so no amount of re-reading it would have surfaced the gap, and a seat that
  trusted the brief would have written the same paragraph into nothing and reported it done.
- **What changed in the record.** Nothing — and this is the only one of the three where that is the
  honest answer, because nothing *could* be written to a document that does not exist. The finding went
  into the nearest real container instead: this file, generation 6, continuing from 5. The numbering is a
  record of the substitution, not of the instruction [L, this document's title and STEP 0].

The clause this violates is "**Project-state claims must be relayed or verified**": that a Gen-7 close
exists and is available to be edited is a project-state claim, and it arrived in the imperative mood,
which is the one mood in which a claim does not look like a claim.

Name it precisely, because generation 5 already has the sentence for it [L, `session_close_gen5.md` §2
L86–90]: "The worst instance deserves to be stated plainly, without softening. It is fabricating a
*cause* for an observed anomaly instead of saying 'I don't know'. An observation with a wrong explanation
is worse than an observation with none, because the explanation terminates the search: nobody
investigates further into a quantity that has already been explained." Substitute an *entity* for a
*cause* and this is the same failure one level up: not an explanation of an observation, but a container
for a finding, named rather than checked. Generation 5's reason transfers exactly — a document that the
record already refers to by name is a document nobody thinks to look for.

**This is the worst of the three, and the reason is an asymmetry in what the errors leave behind.** An
arithmetic slip is caught by recomputation, which anyone can run against numbers that are printed; a
fabricated entity is caught only if someone thinks to search for a file that no index ever named. The
error leaves no residue to check, because the thing that would have held the residue does not exist.

### 2.2 An arithmetic slip: the middle FDTD order `0.59` — arithmetic

- **What he said.** The ladder's FDTD orders are `1.22 / 0.59 / 1.28` [R].
- **What the artefact says.** Pairwise orders from the graded rows: A→B `1.2185`, B→C `1.3532`, A→C
  `1.2744` [L, `evidence/rung_c/SUMMARY.md` L64–67]; EIG `0.8016 / 0.7415 / 0.7767` [L, same table].
  `1.22` ↔ `1.2185` and `1.28` ↔ `1.2744` are traceable to a rounding. `0.59` reproduces from **no**
  pairing of the three rungs, and the pairing that occupies the middle position in a displayed triple,
  B→C, is `1.3532` [M, recomputed from the table].
- **How it was caught.** By computing all three pairs before writing anything, not by asking whether
  `0.59` was plausible. It is not plausible — a sub-linear order sits below every other order on the row
  — but plausibility is an argument and the check is the recomputation.
- **What changed in the record.** `0.59` is recorded as `[R]` and explicitly **not** as a result [L,
  `SUMMARY.md` §3.1 L81–95, §11(b) L295–299; `decisions.md` §156(d)]. The verdict does not move, and the
  reason is worth stating: all three real orders are above `1` and none is `2.0`, so E2 is not achieved
  on the true triple either [L, §156]. A fabricated number was quarantined, not repaired — it is still
  in the record, wearing a tag, where a later reader can find it.

The clause this violates is "**When I cannot name a source, the number is [R] by default**": `0.59` could
not be traced to any pairing of the three banked rows, and a number that traces to no pairing cannot be
the result of one.

### 2.3 A provenance claim: "both solvers are at their instrument floors" — provenance

- **What he said.** "Both solvers are at their instrument floors" [R] — carried in the chat layer as `[M]`.
- **What the artefact says, first number.** The claim rests on `0.377 pp`, described as the extraction
  bias from the `2|Gamma|/d_probe` term. A search for that literal string across `docs/`, `evidence/` and
  the ledger finds it **only inside sentences that quarantine it** — `evidence/rung_c/SUMMARY.md` §5
  L115–117 and §11(b) L295–299, `ERRATA_004.md` §E.2 L161–163, `decisions.md` §156(f) L9876 and the
  closing lists of §153 and §156 — and in no artefact, no JSON field and no log line [M, searched this
  pass]. The empty search is the finding, and the record states it itself: "no artefact, log, JSON field
  or prose source behind it" [L, `SUMMARY.md` §11(b) L298].
- **The same number one rounding step away, found by searching differently.** `0.377` is not sourceless,
  and the record's "no provenance at all" is a *string* verdict rather than an arithmetic one.
  `decisions.md` **§143** L9235–9242 derives it: `delta_beta ~ 2*|Gamma| / d_probe = 2 * 0.00701664 /
  0.0096 = 1.4618 rad/m`, "i.e. **0.3767 % of beta**", marked "**Hand-computed; recompute as
  `2*b_over_a/0.0096` before quoting**" [L; repeated as the one-wave fit's own bias at
  `docs/design/pipeline_map.md` L64]. So the floor's FDTD half has a *derivation* at one digit's distance
  and no *measurement* at any distance, and the difference between `0.3767` and `0.377` is exactly the
  difference between a search that finds something and a search that reports an empty tree. That is this
  document's own failure mode appearing in the record it is describing: a grep for the wrong string looks
  identical to an empty tree.
- **What the artefact says, second number.** `0.72 pp` does have a source — the transverse-box error at
  the base box, `≈ +0.72` pp [M, `evidence/box_sweep/SUMMARY.md` §8.1 L178], re-cited `[L]` at
  `evidence/rung_c/SUMMARY.md` §5 L118–120 and `decisions.md` §156(m) L9931. What has no source is the
  **transfer**: rung C's own objection says it is an error the sweep *removed*, "not a residual known to
  survive at `lat 8 / lid 1`" [L, `SUMMARY.md` §5 L122–124; `decisions.md` §156(f)], while
  `evidence/strip_width/SUMMARY.md` L162–164 uses it as a live cap on EIG's approach *because* the box was
  held fixed at `lat 8 / lid 1` throughout, "so nothing in this sweep reduced it" [L, and that page marks
  the whole reading as a hypothesis it does not test, L168–170]. Two in-tree `[L]`s want different things
  from one `[M]`, and no measurement in this tree adjudicates them.
- **The record was correct and the chat layer was not.** `decisions.md` §156(m) tags both floors as
  magnitudes and neither as a measurement, and calls the whole thing a HYPOTHESIS; §156(o) prints "0.373
  pp is what this instrument can do. It is the wall. It is not a solver failure. It is a floor." **as
  prose, expressly not attributed to a measurement** [L]. The defect is nothing but confidence exceeding
  provenance: the sentence came back up one tag stronger than the record wrote it.
- **Distinct from §2.1 and §2.2.** Nothing was fabricated here and nothing was miscalculated; the number
  may even be right, and §143's derivation is an argument that it is roughly the right size. What failed
  is that a reader could not check it — and unlike §2.2's three pairwise recomputations, the check does not
  exist as a command, because a floor hypothesis has no artefact to recompute against.

The clause this violates is "**A reading built on numbers with mixed provenance inherits the weakest
tag**": "both solvers are at their instrument floors" is a reading over one number with a derivation and
no measurement and one number with a measurement of something else, so the reading is `[R]` — and so is
every claim downstream of it, including the claim that a remainder is *irreducible to a floor* rather than
a piece of a still-falling curve.

### 2.4 A further instance, demoted: eight stations that are nine

Kept and demoted, because it is the same class as §2.2 and not the same weight: nothing downstream of it
moved a verdict, and both halves were arithmetic the prose did to itself rather than a claim about the
tree.

- **What he said.** "the `9.6 mm` station span and the `8` stations" [L, `SUMMARY.md` L237].
- **What the artefact says.** `n_stations: 9` in the row itself [M, `evidence/rung_c/h020.json`,
  `rungs[0].n_stations`]; `MS_X_FIRST, MS_X_LAST = 10.4e-3, 20.0e-3` and `MS_N_STATIONS = 9` [L,
  `emfit/studies.py` L1176–1180]. `20.0 − 10.4 = 9.6 mm` at `1.2 mm` spacing is **eight intervals and
  nine stations** [L, `SUMMARY.md` L219–223].
- **How it was caught.** By reading the row's own field against the prose in the same document, not by
  re-deriving the geometry. The number `8` was correct and the noun was wrong: it counts intervals.
- **What changed in the record.** `SUMMARY.md` L237 is corrected in §11(a) [L, `ERRATA_004.md` §E.1].
  The recommendation's substance is unaffected because the wrap modulus `2π/span = 654.498 rad/m` is a
  function of the span and not of the count [L, `decisions.md` §152.13(g), recomputed there]. What the
  repair would need — a shorter span, more stations — has no CLI knob; arm length, `x_first`, `x_last`
  and `n_stations` are not exposed [L, `SUMMARY.md` L219–223].
- **Second instance, same class, recorded because two examples make the class and one makes an
  anecdote.** The banked non-converged residual band is quoted as `0.93`–`0.99`; the six numbers are
  `0.9559803168921627`, `0.9374781042952944`, `0.9523820823233484`, `0.9327792913828687`,
  `0.9650183697692649`, `0.9221065847163377`, and the smallest lies outside the stated band, which is
  `0.92`–`0.99` [M, `ERRATA_004.md` §C.3–C.4]. A band that excludes one of the numbers it describes has
  the same defect as the station count: the arithmetic was done and the last step was not checked
  against the set it was done over.

**The transferable form of the three cases** — mine, not generation 5's words: the check is a command,
not a plausibility argument, and each case needed a *different* command. §2.1 needed a glob, §2.2 needed
three pairwise divisions, §2.3 needed a grep and then a second grep for the number as it would have been
written. In all three the cheap command was available, and in the first it was the difference between a
finding and a fabrication.

## 3. Task B — two things the record is entitled to say, and one word it is not

### 3.1 The hash chain moved twice

Stated at its true strength, and stated with the chain itself because the argument is about specific
links. Three links, not two: `tools/host_ladder.py` at
`1cd1a3eee4e76cd8e3672decafc35145eaf761c3cde1a900feca87f8087abeb9` / `1106` lines [L,
`evidence/rung_c_errata/PREREG.md` §13 L251–254] → `519365eb4623bd6a1456258565d23dea5aba94af464d02d4d2f8e8752910d57c`
/ `1261` lines [L, `rung_c_errata/ERRATA_001.md` §2] →
`0d7191973fe7babf53463205a1da968befcca205e725027ed83dc0267b190c9b` / `1395` lines [L, `decisions.md`
§156(c); `ERRATA_004.md` §B.2]. Link 2 was argued **in advance, in the file whose clause it superseded**;
link 3 is argued by no document on the rung-C side, and the strip-width erratum that covers it does not own
the clause it leaves unmet [L, `ERRATA_004.md` §B.6].

**How it was caught.** Not by re-measuring the hash. By asking the record which document it says owns the
clause, and finding that the answer for link 3 sits outside the fence the clause protects [L, §B.6]. The
check that would have settled it cheaply — `sha256sum tools/host_ladder.py`, one command — was available
to the automated seat and was not the step that found the gap.

**What changed in the record.** G3 is recorded as **FAIL in letter, a second time** [L, `ERRATA_004.md`
§B.6; `decisions.md` §156(c)], and what carries "same instrument" moved off the hash onto three things that
are not a measurement: ordering by mtime (`PREREG.md` `01:55` → `ERRATA_001.md` `02:05` →
`tools/host_ladder.py` `02:55` → `h020.json` `04:57`), the byte-identical `d585_modal.py` and
`studies.py`, and `sigma_retries = 0` with one attempt at `sigma_mult 0.76`, i.e. the moved region was
exercised at exactly the point the frozen tool tried first [L, §B.3–B.5].

Gradeability is therefore an **argument's** property here and not a measurement's, and the honest status of
the rung-C row is "graded under an argument that the tree does not adjudicate" [L, `ERRATA_004.md` §B.8,
closing section]. The alternative reading — G3 admits no amendment, so rung C is ungradeable and the
verdict is unsettled rather than DISCRETISATION IMPLICATED — is recorded and **not** defeated [L, §B.8].
What may not be said is that the guard passed, or that the argument is as good as the measurement would
have been had the hash not moved: link 2 and link 3 differ in exactly that respect and the difference is on
the record [L, §B.6].

**The smaller provenance defect, disclosed because a later reader would assume it was closed.** The
`py_compile` and `--help` post-edit checks exist only for step `1106 → 1261` [L, `ERRATA_001.md` §2] and
were never re-run for `1261 → 1395` [L/M, `ERRATA_004.md` §B.7; `decisions.md` §156(e)]. Link 3 has no
smoke test in this tree. It is not claimed broken; it is claimed unchecked, and "absent" is written down
rather than read as "fine".

### 3.2 The closed form is a local fit, not a law

The form, as recorded: `sigma_mult(n_strip) = 0.76 + 0.015 * (n_strip − 2)` with `sigma_retries =
n_strip − 2` [L, `decisions.md` §152.11 L9755–9765], fitted from three strip-width arms whose
`sigma_used_per_rung` values step by a constant `3015.4047615` [L, §152.11].

**It is a local fit, not a law.** It reproduces the accepted multiplier at `n_strip = 3 / 4 / 5` on the
strip-width arms at `h = 0.4` [L, `docs/design/dispatch_log.md` row `strip-width-closeout-2026-10-31`
item (iii); `decisions.md` §152.11]. It predicts the accepted multiplier **nowhere else**, and rung C is
the counter-example that settles the point:

- `n_strip = 4` by the tool's own pinning rule at `0.8 mm` strip and `0.2 mm` cell [M, `h020.json`
  `rungs[0].n_strip`];
- the form predicts `0.79`; the row accepted `0.76` on the **first** attempt, `sigma_retries = 0`, one
  entry in `meta.sigma_attempts` [M, `h020.json` `sigma_mult_used`, `sigma_retries`];
- the reason is in the artefact: the multiplier follows the **residual**, not the width [L,
  `h020.json` `meta.sigma_ladder_note`].

Two further reasons the word "law" is not available even as an interpolation of the shipped ladder:
`SIGMA_LADDER = (0.76, 0.775, 0.79, 0.805, 0.82, 0.85)` [M, `h020.json` `meta.sigma_ladder`] **omits**
`0.835` (the form's `n_strip = 7`) and reaches `0.85` (`n_strip = 8`) by a `0.045` jump against four
`0.015` steps [L, dispatch row `strip-width-closeout-2026-10-31` item (iii)]; and the arms that fitted it
sit at `h = 0.4` while rung C is `h = 0.2`, outside the domain in which the `sigma_retries == n_strip − 2`
half of the claim was observed [L, `SUMMARY.md` §11(c) L301–305].

What it may be used for: describing what the ladder did on five strip-width arms, and expecting `0.76`
to be tried first. What it may not be used for: predicting an unrun width, or checking a row. The cost
of quoting it as a law is specific and not rhetorical — a law with a counter-example at `n_strip = 4`
invites either deleting the counter-example or re-tuning the ladder to preserve the law, and both
destroy the instrument that produced the banked rows.

## 4. What this pass did not do

- No coherence pass over the record; generation 5 left this undone and it is still undone.
- No run, no re-grade, no re-priced gate, and no retro-run of the missing `1261 → 1395` smoke test.
- No arbiter between the two readings of G3, and none invented.
- No repair of the `0.377` / `0.3767` provenance gap in the record that carries it: `decisions.md` §143 and
  `SUMMARY.md` §11(b) still disagree about whether the number has a source, and this pass writes nothing
  under `evidence/` and does not edit `decisions.md`.
- One divergence found and **not** repaired, because this pass writes nothing under `evidence/`: the
  `rung-c-errata-2026-10-31` dispatch row attributes the third link to `evidence/strip_width/ERRATA_001.md`
  §2 [L, `docs/design/dispatch_log.md` L23], while `ERRATA_004.md` §B.2 and `decisions.md` §156(c) both
  say link 3 is covered by `strip_width/ERRATA_002.md` §1.3/§2 and `ERRATA_003.md` §(b) and that link 2
  is the one covered by `rung_c_errata/ERRATA_001.md` §3 [L]. `strip_width/ERRATA_001.md` is the twin
  filed against the strip-width PREREG for the **same two metadata edits** [L, `rung_c_errata/ERRATA_001.md`
  §1], i.e. it is the *first* link's document. The row is not edited here; the discrepancy is recorded.
*Forward corrections to earlier sessions are collected in section 6.*

## 5. What to distrust about this document

- It is the sixth close written by the seat that generation 5 diagnosed, and the diagnosis is about this
  seat's characteristic failure, not about a predecessor's.
- The cases in §2 are **the ones I noticed**, not a census. Generation 5's own taxonomy warned that its
  counts were a self-kept lower bound [L, `session_close_gen5.md` §7]; these are not even counted.
- Every `[M]` here is a **read** of an artefact, not a re-derivation. I ran no `sha256sum`: the three
  hashes in §3.1 are `[L]` from the errata and from `decisions.md`, so §3.1 inherits whatever those carry.
- The searches in §2.3 are **string** searches, and §2.3 is the paragraph least entitled to forget it: the
  `0.377` occlusion was produced by exactly such a search. A number can be present under another rounding
  and a grep will not say so.
- `[L]` means "a document in this tree says so", which is exactly the class that has already decayed
  twice this session — §4 is one `[L]` contradicting another `[L]`, and I have no measurement that
  settles it.
- One concrete defect inside the provenance document itself, offered as evidence for the line above
  rather than as a flourish: `ERRATA_004.md` §A.4 quotes `meta.git_rev = '3092129843d79939579684d1af59b393ce0b3'`,
  which is **37** hex characters, while the artefact carries `3092129843d79939580779684d1af59b393ce0b3`,
  **40** [M, `evidence/rung_c/h020.json` `meta.git_rev`]. The erratum's argument does not rest on that
  string — it rests on mtimes and on the artefact's fields — but a document arguing provenance has
  mis-transcribed a provenance field, and a reader who checks one number in it will find that one.
- The joint most likely to be wrong in §3.2 is not the counter-example, which is two field reads, but the
  word "domain": `h = 0.4` versus `h = 0.2` is read from `SUMMARY.md` §11(c), not measured, and if that
  reading is wrong then the counter-example is stronger than I have claimed, not weaker.

## 6. Forward corrections to earlier sessions

### 6.1 Corrections

- The eigensolver is not what costs the wall: at `h = 0.4` mm the measured split is `t_eigs` 0.10 s against `t_fdtd` 14.49 s, i.e. 0.7 % of wall time, and the `~94 %` modal-solve share with `4.2 s` at 37k dof has no producer anywhere in this tree (earlier claim at `decisions.md:9951`, where it is quoted and marked UNATTRIBUTED).
- `assemble()`'s "symmetric by construction" is now a measurement and not an assertion: every assembled block of the d585 anchor pencil is exactly symmetric on two meshes (relative asymmetry `0.0`), and the one quantity that is not, `B = m1 - c D c^T`, is asymmetric only at `3.6e-15` (h080) / `8.6e-15` (h040) relative, i.e. pure LU round-off and no structural defect; artefacts under `evidence/matrix_audit/`, commit `3018720` (earlier claim at `emfit/mode2d.py:438`, "All three are real symmetric").
- The 37k-dof-class mixed pencil has no sparse route and no caller that would find one: `mode2d.py:1940` sets `use_dense` against `_MIXED_DENSE_MAX = 3000` (`:185`) and `:1941-1946` raises `NotImplementedError`, while `tools/host_ladder.py` carries its own local `eigs` rather than calling `mode2d`'s solvers (earlier claim at `decisions.md:9951`).
- The ker A vs ker M inversion is UNTESTED, not refuted: the reduced pencil eliminates the algebraic block by construction, so settling it needs the 2x2 block pencil at `mode2d.py:2034-2039` assembled and probed directly, which has not been done (earlier statement at `decisions.md:9959`).

### 6.2 Checked, not asserted in this tree

- Refinement ladder over `h = 1.2 / 1.6 / 2.0` mm: no earlier assertion located — 5 hits for "refinement series|refinement study|ladder over", 1 hit for `h = 1.2` (the correction itself, `decisions.md:9955`), 1 hit for `117-dof`. All three spacings in fact give the identical 117-dof mesh (`nz_sub` 1, cell 1.6 mm, `7 x 4`), so a ladder over them is not a refinement and cannot carry a convergence claim; recorded at `decisions.md:9955`, not re-derived here.
- Grader basis-point printing convention (a printed value 100x the `pp` threshold): zero hits — "basis point" 0, "grader" 0, `1e4`/`10000` 13 (none a printing convention), `90.2` 9 (all inside longer numerals such as `390.25`), `bp` 18 (all binary-file noise). Every definition in this tree is percent-based, `d = 100*(beta/ref - 1)` in pp: `evidence/strip_width/EIG_strip_width.json:30`, `evidence/rung_c/SUMMARY.md:10`.
- `evidence/rung_c/PREREG.md`: zero hits for `rung_c/PREREG`, and that directory holds only `SUMMARY.md` and `h020.json`; the 19 citations of a rung-C pre-registration in this tree point at `evidence/rung_c_errata/PREREG.md`, which exists (19 193 B).
