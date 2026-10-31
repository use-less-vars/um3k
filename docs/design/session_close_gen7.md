# Session close — generation 7

**Date:** 2026-11-01. **HEAD at write:** `ce16cdf` — "docs(design): write the modal-path taxonomy down and close the phase gap in the termination criteria (AC-7)" [L, `git log`]. **Slug:** `session-close-gen7-2026-11-01`. **Tags:** [M] measured, [L] read from the tree, [R] recalled/reported, [UNVERIFIED].

This document is a follow-up to `docs/design/session_close_gen6.md` §6.3 (L303–L346 [L]), **not a replacement for it**. §6.3 remains the catalogue of record for generation 6's twenty-eight errors [L, §6.3 heading L303 and the table's own `28` at L323]: its class-count table is reproduced verbatim in §1 so a reader can see the baseline without opening a second file, but every individual entry, every catch narrative and every blockquote stays where it was written. Nothing here amends, corrects or supersedes §6.3, and §6.3 was not touched by this dispatch (sha256 `2a64c21e…` before and after [M]). Gen-6's numbering is **not extended**: what this session produced is recorded in §2 as a labelled **post-gen6 series**, named by substance, because the numbers `#29` onward in circulation are conversation tallies and not artefacts of this tree (§2 header, §2.6). §3 declares the numbering hazard that already exists in this repository, and §4 extends the class-count table without inventing a total.

No run was performed for this document. Nothing was re-graded, no gate was re-priced, no number moved, `PREREG.md` is untouched, and no file was written outside the two named in the dispatch row.

---

## 1. The twenty-eight, by class (verbatim from §6.3)

The block below is copied from `docs/design/session_close_gen6.md` §6.3, L311–L324, byte-for-byte inside the fence [L]. The `later entries` column carries bare `#N` **because that is how §6.3 wrote it**: every such number in this document is a **gen6-series** number (§3).

```
class                       n     later entries
Fabrication                 2
Arithmetic                  3     #28
Inverted inference          1
Unit conflation             2     #26
Timer-as-measurement        1
Path/citation               9
Parameter                   3     #24
Specification defect        4     #27
Premise                     3     #25
                          ---
                           28
```

Sum of the `n` column: `2+3+1+2+1+9+3+4+3 = 28` [M, recomputed here]. §6.3 L307 also records a second, rival count of 17 from an earlier worker self-report and distinguishes it rather than merging it [L]; it is noted and is not this document's baseline.

**Pointer, not restatement.** §6.3 describes five of the twenty-eight individually — gen6 `#24` (L328), `#25` (L330), `#26` (L332), `#27` (L334), `#28` (L336) [L]. Those paragraphs are not summarised, paraphrased or improved here. Read them at `docs/design/session_close_gen6.md` §6.3, L326–L336. The remaining twenty-three are carried in §6.3 only as class aggregates and have **no individual entry anywhere in this tree** [L] — that is a property of the gen6 record, carried forward unchanged, and not a gap this document fills by reconstruction.

---

## 2. The post-gen6 series

**Header note on numbering.** The numbers `#29`, `#30`, … are **conversation tallies by construction**: they were assigned by counting entries in a discussion, not by inserting rows into an artefact, and no file in this tree holds an entry archived under any of those numbers for this session (§2.6 states what was searched). They are therefore not used as labels here. Each entry is named by its substance, and each carries its own provenance line by line.

### 2.1 The `gates_101_20.py:481–493` false premise — "it only closes if the two numbers are signed oppositely"

- **What happened.** A claim that the T1 stability gate's quoted window sensitivities (`3.06 % / 2.99 %, span 6.24 %`) can only be mutually consistent if the two figures carry **opposite signs** was carried through three sessions of close-out discussion [R] as an open objection to the gate. On reading the range it cites, `L481–493` is the tail of the `T1_stab` docstring plus a `NotImplementedError` guard. It contains **no numeric comparison at all**.
- **Where the substance lives.** `tools/gates_101_20.py:481-493` [L, read]: docstring tail L481–484, closing `"""` L485, `if basis == "mixed":` L486, `raise NotImplementedError(` L487, message strings L488–493. The function's real comparison is at `tools/gates_101_20.py:527` — `shift = abs(beta_b - beta_a) / abs(beta_a) if beta_a else float("inf")` — tested at `:533` — `"pass": bool(shift <= float(tol))` [L]. **Both operands pass through `abs()`**; the test is `<=` on non-negative magnitudes. There is no sign question anywhere in this gate. `T1_TOL = 0.005` at `:132` [L].
- **Where the false premise is written down.** It is committed, not merely spoken: `docs/design/theory_round2_memo.md` item 8 states *"`3.06 - 2.99 = 0.07`, so a `6.24 %` span needs opposite signs"* citing `tools/gates_101_20.py:481-493`, and is **already tagged `[UNVERIFIED]` in that memo** [L]. The tree's own record flagged it as unverified at the moment it was committed, and it was carried anyway as though it were an open technical question.
- **Class.** Negative / inherited false premise (the class the dispatch labels "L29"; see 2.2).
- **What caught it.** Reading the cited range instead of the claim about it, and reading the comparison operator instead of the prose around it. No run, no test, no measurement.
- **A second defect in the same line, recorded and not repaired.** The premise does not close on its own terms either. `|3.06 − 2.99| = 0.07` [M] and `3.06 + 2.99 = 6.05` [M]; neither reproduces the quoted `6.24`. So the `6.24` is not reproducible from its own two figures under **either** sign convention, and "needs opposite signs" repairs the sign question without reaching the number. The tolerances are correct in code (`:132`); the percentages live only in comments at `:123`, `:124`, `:128`, `:483` and `:490` and in the exception message at `:490` [L]. Re-deriving `6.24` would be a measurement, and this dispatch performs none — the non-closure is recorded here as a live open item, not closed by argument.

### 2.2 The negative-existence class — four properties, and the rule that follows

- **What happened.** 2.1 is an instance of a class that has now occurred often enough to be named: a claim whose content is the **absence** of something — a comparison, a sign, a caller, a file — asserted in a form that reads like diligence and that nothing in the ordinary workflow contradicts.
- **The four properties.**
  1. **It reads as diligence.** The surface form is a check already performed: "it only closes if…" sounds like the writer did the arithmetic.
  2. **Cheap to write, expensive to disprove.** Writing it costs one sentence; disproving it costs opening the cited range, reading the operator, and re-deriving a figure — three acts against one.
  3. **It does not degrade.** An absence claim is not eroded by later work the way a stale number is: nothing subsequently computes the missing comparison, so nothing ever contradicts the claim. A wrong number eventually meets a right one; a wrong absence waits to be read.
  4. **Inherited rather than generated.** The 2.1 instance was not produced by this session; it was received and carried. The cost of an absence claim is paid by whoever inherits it, not only by whoever writes it.
- **The rule that follows.** **A negative existence claim must be re-checked at commit time, by reading the range it cites, regardless of who wrote it and regardless of how it is tagged.** Inheritance is not evidence. The rule binds this document's own claims as much as anyone else's: §2.6 exists because of it.
- **Where the substance lives.** The naming of the class is **conversation record, no tree citation** [R]. Its concrete instance is cited and checkable in 2.1 [L]. That asymmetry is the entry: the instance is `[L]`, the class is `[R]`.
- **No line in the committed tree carries the label as a name.** "L29" — the label the issuing dispatch uses for this class, and which §4 repeats — is **not present in the committed tree as a name**. Search: `grep -rn -F 'L29' --include=*.md .` returns **18 matching lines** — and the search is **self-inclusive**: this bullet matches itself, and the examples it quotes are themselves `L29`-prefixed strings, so **occurrence counts are deliberately not quoted here** (they would inflate with every example the sentence gives), and **every figure below counts lines, not occurrences**. By line: **1 is this bullet**; **2 are this document's own outside this bullet** (§2.1, §4); **1 is the issuing dispatch's row** (`docs/design/dispatch_log.md:31`, the row that records this document — it gained the string after the first version of this sentence was written, which is why the figure moved from 17 to 18); **3 are the name itself but sit in `.thoughtmachine/knowledge/personal/task_tracker.md` (`:479`, `:485`, `:491`), the agent knowledge store, which is not the committed tree**; and **11 are unrelated substrings**, every one a line-number fragment (`L295`, `L296`, `L2970`, `L2982`, `L2992`, `L295-299`, `L290-291`…). So **15 lines sit in the committed tree** and **18 workspace-wide** once the knowledge store's 3 are added. Consequence: the label is retained **only as the issuing dispatch's own shorthand** for the class; it is **not a citation** to any line or entry, and a reader looking for this class should search the **substance class name — "negative / inherited false premise"** — not the label. This is the rule above applied to 2.2's own label: the absence claim is stated together with the search that establishes it, at commit time, by the party who inherited the label.
- **Class.** A meta-class — it classifies the *warrant* of other claims rather than their content.
- **What caught it.** The same read that caught 2.1. The class was named afterwards, which is the normal order and is why absent-mindedly attributing it to foresight would be wrong.

### 2.3 The `max_dof` / engine-default correction — "works at 37k" was a target, not a measurement

- **What happened.** Two claims arrived together and both needed correcting: that the ladder tool "works at 37k", and that `max_dof=1400` is a ceiling on the modal tool. Both are scope errors of the same shape — a figure attached to the wrong subject.
- **Where the substance lives.**
  - `docs/design/dispatch_log.md:30` [L, read] — the correction of record: `tools/d585_modal.py` is a three-engine driver (`ENGINES` at `:366-367` — `arpack`, `deflated`, `mixed_dense`) with `ENGINE_DEF = "deflated"` as its default (`:369-370`), so `max_dof=1400` (`:648-649`, "dense-QZ budget on free edges (mixed_dense only)") scopes the **dense arm alone**; the ARPACK and deflated arms accept a `max_dof` keyword (`:253`, `:287`) and never read it.
  - `docs/design/modal_solver_paths.md:50` [L, read] — the same correction in the document a reader consults first, closing "…scopes the **dense arm alone** and is no ceiling on the tool".
  - The `37k` half: `docs/design/dispatch_log.md:29` [L, read] records that `37k`/`37000` appears **nowhere** in `tools/host_ladder.py`, so "the ladder works at 37k" is unverified and is more likely a misreading of the probe's *target* (`free_e ~ 30000`, `tools/host/sparse-probe/sparse_solver_test.py:8-10`).
  - **Correction to the dispatch that produced this document:** its brief places both halves at `dispatch_log.md:30`. In the artefact the `37k` finding is at **`:29`** and the `max_dof` finding at **`:30`**. Both lines were read individually [L]; the split is recorded here rather than silently repaired in the citation.
- **Class.** Target read as measurement (the `37k` half); parameter scope read wider than its code (the `max_dof` half). Kept as one entry because they were carried as one belief — that the tool had already been exercised at the scale the roadmap targets.
- **What caught it.** A grep for the literal `37k`/`37000` across the tool said to achieve it — zero hits [M] — and reading the driver's engine table and default rather than its flag list [L].

### 2.4 Worker-side brief errors — the memo `[R]`-count and the most-recent-row anchor

- **What happened.** Two defects were found **in a brief rather than in the work**: a claimed provenance-tag count for `docs/design/theory_round2_memo.md`, and an anchor to a "most recent row" that did not identify the row it meant.
- **Where the substance lives.** The corrected count is checkable: `docs/design/theory_round2_memo.md` carries `[R]` **4**, `[M]` **16**, `[L]` **1**, `[UNVERIFIED]` **1** across its 22 claims [M, counted by literal fixed-string occurrence over the whole file] — the same counts `docs/design/dispatch_log.md:30` records [L]. **The erroneous figure the brief gave is not recoverable from the tree: conversation record, no tree citation** [R]. The "most-recent-row" anchor likewise: **conversation record, no tree citation** [R] — `docs/design/dispatch_log.md` maintains no "most recent row" pointer to anchor to; it is a single table plus standing rules [L].
- **Class.** Plausible anchor — a reference that resolves to *something* plausible on inspection, so it survives the reader who does not follow it.
- **What caught it.** Instructing the worker to ground each claim in its own read rather than in the brief, so the brief stopped being treated as evidence. Both were caught **before any write**.

### 2.5 The telemetry-rule retraction — three points fitted a law, a fourth refuted it

- **What happened.** Three spawn observations (271 and 284 tool calls completing, 323 cut) were fitted as a rule: *call count orders the timeouts*. The next spawn refuted it — **338 tool calls in 113.9 s, status `final`, not cut** [L] — 15 calls past the alleged cut point, completing cleanly.
- **Where the substance lives.** `.thoughtmachine/knowledge/personal/lessons_learned.md:935` [L, read] carries the retraction and the refuting spawn; `:937` carries the cross-session data — cut at 891 calls / 540 s, cut at 323 / 200 s, completed at 338 / 240, 284 / 240, 271 / 240 and 150 s-class runs; fraction-of-budget does not separate them either (a 0.60 fraction cut, a 0.63 fraction completed) [L]. **Path caveat:** that file sits under `.thoughtmachine/`, the agent knowledge store. It resolves from the repo root but it is **not part of the committed tree** [L]. If a citation must resolve to a versioned artefact, this entry has none and should be read back as `[R]` — the caveat is stated rather than left for a reader to discover.
- **Class.** Premature generalisation.
- **The transferable line.** **The bar for writing a rule is higher than the bar for writing an observation.** An observation that is refuted is replaced by a better observation and costs nothing; a rule that is refuted has already been used to decide something. Observations survive refutation. Rules do not.
- **What caught it.** The fourth data point, which happened to contradict the fitted curve. Nothing sought the counter-example; it arrived. That is a weak catch, and it is why the **rule** is retracted and the observations are kept.

### 2.6 What is *not* in the tree (a negative result, re-checked at commit time)

By the rule in 2.2, this section's absence claims are stated together with what was searched:

- **No entry under `#29`–`#32` exists in any error catalogue in this repository.** `#29` occurs once, **prospectively**, at `docs/design/session_close_gen6.md:344` — "If the record shows it was asserted as cos^2, that becomes #29. No entry is made against an allegation the record does not show." [L]. `#30` occurs at `docs/design/d58_extraction_acceptance.md:159`, where it denotes the D58 brief's 3.6-vs-4.4 expectation and belongs to the **D58 series**, not the gen6 series [L]. `#31` occurs nowhere [M, zero hits]. `#32` occurs at `./.scratch/c5_price_reconciliation.md:107` as a price/decision item number, in a scratch file [L].
- **Consequence.** There is nothing to renumber and no gen7 entry inherits a `#N`. The post-gen6 series in §2 is named by substance because **no numeric series exists to extend** — a fact established here rather than assumed from the brief.

---

## 3. The numbering hazard

Three numbering series coexist in this repository, and **they are not distinguishable by their text form**. A bare `#N` is ambiguous.

| series | numbers | where it lives | verified instance |
|---|---|---|---|
| **gen6 supervisor series** (`#N`) | errors catalogued at a session close, generation 6 | `docs/design/session_close_gen6.md` §6.3, L303–L346 | `#24`–`#28` at L328–L336; `#28` also at L326 [L] |
| **D58 dispatch numbers** | the D58 brief's rows and expectations | `docs/design/dispatch_log.md`; `docs/design/d58_*.md` | `#30` at `docs/design/d58_extraction_acceptance.md:159` — the 3.6-vs-4.4 expectation, not an error [L] |
| **"Owner error `#N`"** | owner-side errors in the decision record | `decisions.md` — **repo root**, not `docs/design/` | `#41` (and `#40`) at `decisions.md:9165`; `#42` at `decisions.md:9203` [L, both lines read] |

**Rule.** Nothing downstream may key on `#N` alone. A citation must carry **the series and the document**: not "`#28`", but "gen6 `#28`, `session_close_gen6.md` §6.3 L336"; not "`#42`", but "owner error `#42`, `decisions.md` §140 L9203". This binds future greps, any mapping or errata table, and any write that quotes a number back.

**The hazard is live, not hypothetical.** Two of the three series render as bare `#N`, and the collision is already in the tree: gen6 `#29` is a *prospective error* (§2.6) while D58 `#30` is a *numeric expectation* — a reader who keys on the digits alone will order them as a sequence and will be wrong [L].

**Path correction to the dispatch that produced this document.** Its brief cites the third series at `docs/design/decisions.md:9165` and `:9203`. **`docs/design/decisions.md` does not exist** [L]. The file is `decisions.md` at the repository root; both cited line numbers resolve there and do contain what was claimed [L]. The corrected path is used throughout this document.

---

## 4. Extended class-count table

Gen6's classes with their counts **unchanged and quoted from §6.3** (L311–L324 [L]), plus the classes named in §2. Where a class is new, its count is **as recorded in Section 2** — that is, exactly as many entries as §2 actually exhibits and no more.

| class | gen6 n (§6.3, verbatim) | post-gen6 (§2) |
|---|---|---|
| Fabrication | 2 | — |
| Arithmetic | 3 | — |
| Inverted inference | 1 | — |
| Unit conflation | 2 | — |
| Timer-as-measurement | 1 | — |
| Path/citation | 9 | — |
| Parameter | 3 | — |
| Specification defect | 4 | — |
| Premise | 3 | — |
| **Negative / inherited false premise** ("L29") | not a §6.3 class | as recorded in §2 — **2.1** |
| **Target read as measurement** / parameter scope read wide | not a §6.3 class | as recorded in §2 — **2.3** |
| **Plausible anchor** (brief-side) | not a §6.3 class | as recorded in §2 — **2.4** |
| **Premature generalisation** | not a §6.3 class | as recorded in §2 — **2.5** |

**No total is given, deliberately.** Three reasons, recorded so the omission is not read as an oversight:

1. **The gen6 total is closed; the post-gen6 series is not.** `28` is a count over a catalogue that gen6 declared complete [L, §6.3 L303]. §2 is the record of a session still open, and a total taken now would be superseded by the next entry rather than corrected by it.
2. **The two columns are not commensurable.** The left column counts *errors in the session's output*. The right column counts *entries*, one of which (2.2) is a class rather than an instance, and one of which (2.4) is an error in a **brief** rather than in a product. Adding them would compare different kinds of thing.
3. **A summed figure is the defect gen6 already logged.** Gen6 `#28` is precisely "a total that the parts did not support", caught by recomputing the sum and *not* reconciled by redistributing entries to make it close (`session_close_gen6.md` §6.3, L326) [L]. Producing such a total here to tidy the table would repeat the catalogued error inside the catalogue that records it.

**One adjacency, stated rather than glossed.** The "negative / inherited false premise" class in 2.2 is next to §6.3's `Premise` class but is not the same class: gen6's `Premise` defect is a proposition that is **not well-posed** (`#25`, L330 [L]); this one is a proposition whose **truth was never tested** and whose form discourages testing. The separation is deliberate and the two are not merged.
