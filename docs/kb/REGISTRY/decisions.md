---
status: current
layer: registry
pinned_commit: null
pinned_at: 2026-11-17
byte_budget: 12288
last_verified: 2026-11-17
reads_when: when a citation names a decision id, or a row must be added or marked SUPERSEDED
supersedes: null
superseded_by: null
---

# REGISTRY/decisions.md — the index that replaces a phantom

`docs/design/decisions.md` **does not exist** and is cited 585 times across 63
files; 7+ banners name it as the successor to older logs. This file is the
reconstruction: an *index* of the decision record, not a second copy of it. The
authority stays in `docs/design/dispatch_log.md` and
`docs/design/decision_register.md`; nothing is moved.

## How to read it

| column | meaning |
|---|---|
| `id` | the decision id as the source spells it (no renumbering — the corpus cites these strings) |
| `row` | the row/section in the source that carries it |
| `status` | `LIVE`, `SUPERSEDED <successor id>`, or `closed` |
| `pointer` | the path a reader must open to see the actual text |

## Append-only rules

1. Rows are **added**, never rewritten. A superseded decision keeps its row and
   gains `SUPERSEDED <successor id>`; deleting the row would silently break the
   585 citations this file exists to serve.
2. A row's `pointer` must be a tracked path at HEAD; `measured`-style blob
   evidence is not required here because the pointer *is* the evidence.
3. This file is exempt from nothing: it is in `REGISTRY/`, so A1 applies.

## Status of this index

Reconstruction is Stage 3 work (`scripts/generate_open_defects.py` produces the
defects half from `docs/design/defect_register.md`). Until then this file holds
the schema, the rules, and only the rows decided inside `docs/kb` itself — the
`docs/design/`-derived rows still pending generation, because a guessed row is
worse than no row.

`pointer` names the KB file that carries the reasoning for a decision taken
inside this tree, since no `docs/design/` row backs it.

| id | row | status | pointer |
|---|---|---|---|
| KB-1 | the section below | LIVE | `docs/kb/PROCEDURE.md` section 6 |

## KB-1 — a pin covers a canonical form; A10 keys on a commit hash

**Decision.** `PINS.files[].sha256` is the sha256 of a file's canonical form —
its bytes with the values of exactly `pinned_commit`, `pinned_at` and
`last_verified` replaced by `<canonical>`, every other byte as written
(`scripts/kb_canonical.py`, imported by both `scripts/repin_kb.py` and A2).
`PINS.newest_commit` is the full 40-character HEAD sha at re-pin time; A10
requires it to be an ancestor of HEAD, inside 14 days on its own committer date,
at pin..HEAD distance under 20, failing at 50. `newest_commit_date` is written
and asserted by nothing.

**Defects.** A2 demanded `sha256(HEAD blob)` and `sha256(working bytes)` equal
one pin while `repin` rewrote three front-matter values in the working tree:
dirty tree failed the working side, committing moved the HEAD blob and failed
the HEAD side, re-pinning was dirty again — no fixed point. And A10 demanded
`newest_commit_date` string-match `git log -1 --format=%cI HEAD`, satisfiable
only while `repin`'s output was uncommitted, while A4 demands
`git status --porcelain -- docs/kb` empty: at most one could be green.

**Rejected.** Re-pinning after the header patch, which stays dirty and breaks
A4. Trusting only the HEAD blob, which lets a dirty-tree edit through. Dropping
header files from `PINS.files[]`, which gives up pinning on exactly the files
most likely to be hand-edited. Keying A10 on the date string, unsatisfiable
alongside A4 as above.
