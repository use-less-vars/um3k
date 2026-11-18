# S7 — Uncertainties, corrections to my own earlier claims, and limits of evidence

This file exists so the audit can be argued with. Where I was wrong earlier, the
correction is stated plainly rather than quietly fixed.

## 1. Correction to a claim I made in the chunk-2 pass

**What I said:** `00_README.md:138` misstates the size/count of `docs/` — "160 files,
5,702,497 B" against the actual figures under `docs/`.

**What is actually true:** line 138 is a table row,

```
| docs/design/ | 160 files, 5,702,497 B | [BRIEFING] |
```

so the subject is explicitly **`docs/design/`**, not all of `docs/` (which is 218 files
/ 12,753,536 B), and the row is **already tagged `[BRIEFING]`**, i.e. already marked
unverified. Actual `docs/design/` is 165 files / 5,780,607 B.

**The interesting part, which I had wrong for the wrong reason:** the delta is exactly
5 files / 78,110 B, which is precisely `docs/design/onboarding/`
(5,702,497 + 78,110 = 5,780,607 and 160 + 5 = 165). So the published number was measured
*before the onboarding pack existed*, and the pack **is** the delta — the file that
quotes the number is itself the reason it went stale. The defect is a stale, unverified
count, not a wrong folder. S3's B-2 categorisation of this line should be read with this
correction.

## 2. Claims I could not verify, and why

- **`last_commit` in `inventory.tsv`.** There is no git in this container, so I could not
  derive these; I inherited the column. I did not use it for any judgement. If it is
  wrong, nothing in S3–S7 changes, because every staleness finding rests on file content
  and mtime, not on commit history.
- **The 585 `decisions.md` references.** The *absence* is verified (`find -iname
  "*decision*"` returns only `d58_13_strip_width_decisions_block.md`, and no
  `docs/design/decisions.md` exists). The *count* is regex-derived and may include
  references to a planned path or a differently-rooted file of the same name. Even at
  half the count the finding stands, so I have not spent the runtime to disambiguate all
  585 by hand.
- **`STATE.json`'s own assertions.** It is tagged `[BRIEFING]` in the README's own
  vocabulary, and its `ghosts_rejected` list is the *source* of S3c's three ghosts. I
  tested the corpus against it; I did not independently verify that its list is complete.
  If it is incomplete, S3c's "zero asserting files" is a lower bound on cleanliness, not
  a proof.

## 3. What the tests in S3/S7 measure, and what they do not

- **S3c's ghost check is token-level.** I can show that no file *names* a ghost token in
  an asserting construction. I cannot show that no file **paraphrases** the ghost
  ("the mesh carries a quiver overlay") without using the token. The T6 result should be
  read as "no token-level assertion", which is a weaker claim than "no phantom belief".
  This is also why T6 must be phrased as *asserts as fact*, not *mentions* — the one file
  that quotes the ghosts (`03_KNOWN_BUGS.md:300-350`) is the file that refutes them.
- **Citation counts are token-based.** 1,010 dangling out of a larger set, across 313
  tokens. Tokenisation choices (`.md` suffix required, `docs/` prefix required, code
  paths excluded, backticked vs bare) move this number by tens of percent. The *order of
  magnitude* and the *direction* are robust; the exact figure is not. Same for the
  per-file `cites_out` / `cited_in` columns.
- **Grade A/B/C severities in S3 are automated.** They come from pattern rules
  (self-contradiction between header and body). I opened every Grade-A file; I did not
  open all 28 date-anomaly files or all 48 supersession-noun files. Grade-C findings are
  leads, not verified defects.
- **Bytes are bytes on disk.** No normalisation for line endings or encoding; all files
  are UTF-8 text, so the risk is small, but a `\r\n` file would inflate its own count.

## 4. Judgement calls a reviewer may want to overturn

- **The five UNCERTAIN files** (`pml_notes.md`, the two `s11_refit_from_phasors`
  variants, `modal_solver_paths.md`, `e13_antenna_scope.md`) are parked rather than
  classified. A domain owner would resolve them in minutes; I chose not to guess.
- **The REFERENCE/ARCHIVE boundary.** I put closed investigations (audits, forensics,
  comparisons) in REFERENCE and point-in-time records (acceptance, preregistration,
  handoff, session close) in ARCHIVE. A different but defensible rule is "anything whose
  claims are superseded goes to ARCHIVE" — that would move perhaps 15 files and would
  not change the budget, since neither class is counted.
- **82 of 85 ARCHIVE files are still cited.** That is a fact about the corpus, not a
  judgement, and it is the finding most likely to surprise a reader of the draft plan.
- **`graded_meshing_plan.md` is WORK, not CORE**, even though S4 wants every graded-fact
  restatement to cite it. If the principal prefers the citation rule to point only at
  CORE, then a distilled CORE file must absorb the graded facts first — that is a
  migration-order decision I have left open (S6 D5, S7 §3 step 4).

## 5. Scope correction carried forward

Earlier passes described the audit scope loosely as "docs/". The correct scope statement
is: **170 text files / 4,308,072 B** out of **218 files / 12,753,536 B** under `docs/`
(the difference is binary/non-prose assets such as figures). S5's `raw` column sums to
exactly 4,308,072 B, so the classification partitions the stated scope with nothing
dropped and nothing double-counted.
