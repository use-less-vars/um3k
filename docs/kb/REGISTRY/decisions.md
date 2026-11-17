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
the schema, the rules, and zero rows — and a zero-row index is honest, while a
guessed one is not.

| id | row | status | pointer |
|---|---|---|---|
