---
status: current
layer: registry
pinned_commit: 36c71d3eaaecf9ee04857dac2d68b04ba5ab97ef
pinned_at: 2026-11-18
byte_budget: 5120
last_verified: 2026-11-18
reads_when: when a citation or a commit message names EV-4, KN-5 or PB-4, or a settled entry must be quoted
supersedes: null
superseded_by: null
---

# REGISTRY/decisions_archive.md - settled decisions, moved verbatim

`docs/kb/REGISTRY/decisions.md` is the live register: the entries a session reads
to know what is decided **now**. This file is the other half of that split. It
holds the entries that are settled and no longer part of live work - evidence
recorded once, knowledge that fixed a reading, a decision that was executed and
closed. They were moved here **verbatim**: same ids, same headings, same bullets,
same wording. Nothing was rewritten, summarised or dropped, so a citation that
names one of these ids still resolves, and the text it reaches is byte-for-byte
the text it reached before the move.

What is here is neither stale nor superseded: every entry is still true. It is
merely no longer something a session has to read to do the current work - and a
register that grows past its own `byte_budget` stops being read at all.

| id | what it settled |
|---|---|
| EV-4 | reconstruction from a summary invents specifics: the pattern and its mitigation |
| KN-5 | the pass-1 mutation transcript records a refusal and keeps its label |
| PB-4 | the PROCEDURE.md / RUNBOOK.md split, executed |

## Rules

1. Entries arrive here by a split of `decisions.md`, moved verbatim, never by
   being rewritten in place. Ids do not change.
2. An entry returns to `decisions.md` only if it becomes live work again, and it
   returns verbatim, carrying the same id.
3. New decisions are written in `decisions.md`, never here. This file grows only
   by a move, so a row here is a row that was already paid for.

## Moved entries

### EV-4 [evidence] - reconstruction-from-summary produces invented specifics
- Observed four times in one Stage 1 session: (i) pass 3 fabricated a sha and disguised it as a placeholder; (ii) pass 1 invented a single 102,400 B cap where the ruled design was a warn/fail pair; (iii) pass 1 replaced the null-ratchet rule with a different rule that would have passed inspection; (iv) the Stage 1b worker reconstructed its own scope from working document 1e93abc2529d rather than from the brief.
- Pattern: context compaction -> reconstruction from a summary -> invention of specifics the summary never carried.
- Mitigation: the host, not the worker, runs the mutation script; and every Stage 2 brief carries the full verbatim text of the claim it is about, never a summary. Any number that appears only in a summary is unwitnessed.

### KN-5 [knowledge] - the pass-1 transcript is a refusal record
- docs/kb/ARCHIVE/superseded/kb_mutation_transcript_pass1.txt records the gate REFUSING a bad mutation. It is not superseded evidence and it is not a successful run. Leave the label as-is; relabelling it SUPERSEDED would destroy the only record of the refusal.

### PB-4 - PROCEDURE.md split into PROCEDURE.md + RUNBOOK.md
- Trigger: PROCEDURE.md sat at 20,459 B of a 20,480 B budget (21 B slack). The slack is a signal, not a rounding error: the file had no room for the next substantive edit, so the next substantive edit was the split itself.
- Executed: the Stage 1b host runbook lives in docs/kb/RUNBOOK.md; PROCEDURE.md keeps a pointer only. Exact byte counts are stated in the commit that landed the split.
- repin_kb.py globs docs/kb/**/*.md, so RUNBOOK.md joins the pin set with no code change.
