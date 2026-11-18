---
status: current
layer: registry
pinned_commit: 36c71d3eaaecf9ee04857dac2d68b04ba5ab97ef
pinned_at: 2026-11-18
byte_budget: 16384
last_verified: 2026-11-18
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
| KB-1 | the section below | LIVE | `tests/test_kb_integrity.py` |
| KB-2 | the section below | LIVE | `docs/kb/PROCEDURE.md` section 6 |
| KB-3 | the section below | LIVE | `docs/kb/PROCEDURE.md` section 6 |
| KB-4 | the section below | LIVE | `server/poc_app.py` |

## KB-1 — a fabricated `pinned_commit` is a failed header

**Decision.** `pinned_commit` is 40 lowercase hex written by
`scripts/repin_kb.py`, or `null` in the bootstrap state only
(`PINS.newest_commit_date` null *and* the header's own `status` `current` —
PROCEDURE section 3). A placeholder that *looks* like a sha is not a placeholder:
it occupies the key that names committed content, so it is a candidate pin, and
A1 rejects it as neither 40 lowercase hex nor null. The rule fired for the first
time against the very commit that introduced it.

**Defects.** During the b2 pass 3 the tree carried
`pinned_commit: 3f7c1a2b...` in a header — a value dressed as a placeholder while
sitting in the provenance key. Its leading characters are hex, so a reader
skimming the header reads a commit; the gate read "neither 40 lowercase hex nor
null" and went red. Nothing else in the tree would have caught it: A2 compares a
digest it is handed and cannot see that the value is invented, and A10 asks only
whether whatever it is given is an ancestor of HEAD. The procedure caught its
own first commit, which is what it exists to do — a rule that has never rejected
anything has never been tested.

reverted_by: <unknown - not recoverable; pass-3 record not in this session>

No commit is named there: the pass-3 record that would name it is not in this
session [UNCITED]
why: the revert was observed with the tree already clean, and the pass-3 transcript does not carry the commit it reverted, so any sha written here would be a guess dressed as provenance.

**Rejected.** Keeping the value and calling it a placeholder in a body line,
which leaves the header lying to every reader who never reaches the body.
Rounding it up to a plausible 40-hex string, which converts one visible failure
into an invisible one. Loosening A1 to accept a truncated sha prefix, so that a
fabrication can stand wherever a commit belongs.

**Mutation-proof.** The fault was injected on purpose, caught by the assertion
that now documents it, and reverted: re-running the gate against the fabricated
header reproduces the red. The transcript of that pass is
`docs/kb/ARCHIVE/superseded/kb_mutation_transcript_pass1.txt`.

## KB-2 — a pin covers a canonical form; A10 keys on a commit hash

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

## KB-3 — a pin is a computed digest, never a quoted one

**Decision.** `PINS.files[].sha256` is written by `scripts/repin_kb.py` from
`git show HEAD:<path>` and by nothing else. A2 checks it twice (HEAD blob and
working tree, both in canonical form) and now also checks **coverage**: every
markdown file under `docs/kb` plus `tests/COLLECTED.txt` must appear in
`PINS.files[]`, so a file that was never listed is red instead of silently
unpinned. The pin set is a ratchet, it only grows; `tests/COLLECTED.txt` gets a
`test_manifest` cap in `PINS.budgets` and A3 enforces it.

**Defects.** The Stage 1b pass found `PINS.files[]` carrying four entries whose
`sha256` was `null` on all four while five files needed pins —
`docs/kb/CORE/00_invariants.md` was absent from the list entirely. The tree had
never been re-pinned, so every digest that could be quoted from it was a
fabrication, and the old A2 could not see the missing file at all: it iterated
the entries present. A hand-typed or copied digest is the same failure one step
later, and it is exactly what a canonical-form comparison catches and a review
does not.

**Rejected.** Trusting a digest a report quotes, ``pinned at abc123`` style,
without recomputing it. Letting A2 iterate only over the entries present, which
is how a file escapes pinning by never being added. Hand-editing `PINS.json` to
match a self-computed hash, which PROCEDURE section 11 already names as no
escape hatch.

## KB-4 — `server/poc_app.py::run_web` is proposed for deletion

**Decision.** The single-structure Trame page `run_web` (`server/poc_app.py:5922`)
is marked `[proposed-delete]` in its docstring. `main()` dispatches every web path
to `run_web_vis` (`:13404`, `:13450`); nothing calls `run_web`, so it is
unreachable legacy kept only because other comments still cite its line numbers.
Deletion is proposed, not taken: it needs an owner ruling, and the citations that
name it rewired first.

**Defects.** Dead code that is quoted as "the shipped behaviour" is worse than
dead code. A dozen comments in `poc_app.py` cite `run_web`'s line numbers as the
authority for `run_web_vis`'s behaviour, so a reader cannot tell which page is
live, and the legacy page keeps absorbing edits meant for the shell.

**Rejected.** Deleting it in the same pass that marks it, which would leave those
citations pointing at nothing in the commit that was supposed to clarify them.

## Settled entries moved to `decisions_archive.md`

`EV-4` (evidence), `KN-5` (knowledge) and `PB-4` (the executed PROCEDURE.md /
RUNBOOK.md split) are settled entries, not live work, so they now live verbatim
in `docs/kb/REGISTRY/decisions_archive.md` under the same ids. That file holds
their full text; this paragraph is the pointer to it, not a summary of it.

### PB-3 [proposed] - split tests/COLLECTED.txt when it crosses the warn tier
- Trigger: docs/kb/PINS.json test_manifest byte size crosses warn 122,880 B (fail tier is 153,600 B; crossing warn prints a warning and never fails).
- Action: split tests/ into tests/solver/, tests/ui/, tests/cross/, each with its own pinned manifest.
- Gate: `pytest --collect-only -q | wc -l` equals the sum of the three manifests' row counts.
- Not now: a large diff for a low-information change, and it must not interleave with the P2 poc_app split.
- Owner: whoever lands P2.

### P0-boot [proposed] - boot to a page that has something on it
- Problem: default boot loads DEFAULT_STRUCTURE build_A_50ohm, whose evidence file is a legacy single-plane dump with no time axis and no geometry keys, so the first screen prints "geometry: not drawn" and "no timeline on this page". The only volume-carrying artefact in the tree is artifacts/reference_sim_volume.npz (46 keys, 40 MB, schema emfit.vis/2), and it is not referenced by structures.json (3 entries, two of them record-only with null paths).
- Proposal: make the reference volume the boot example - either as a fourth structures.json entry marked example, or through an explicit --input default - so a new user sees a rendered volume and a timeline on first load.
- Blocker: the volume is gitignored (*.npz) and absent from HEAD:artifacts, so the wiring cannot land before the artefact does. The ruling to ship it once, with the regeneration script scripts/run_reference_sim.py, is recorded; the commit needs an explicit gitignore exception for that single path, because the agent's git tool surface has no force-add.
- Not yet done because it must not interleave with the Stage 1b repin or the P2 split.

### TI-1 [proposed] - test_poc_mode_picker is order-dependent
- Symptom: test_poc_mode_picker fails when run in a batch with the other poc test files and passes when run alone. Observed while fixing the three viewer defects; not caused by those edits, and it reproduces on an unmodified checkout.
- Class: test isolation, not product behaviour. Something in the batch mutates module-level state the test depends on.
- Not fixed now: it is a rabbit hole with no product behaviour attached. Log it and fix it when the P2 split gives the poc tests their own fixtures.
- Owner: whoever lands P2.
