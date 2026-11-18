# S6 — Critique of the proposed structure, and a budgeted revision

The principal proposed a five-way split (CORE / WORK / REGISTRY / REFERENCE / ARCHIVE
under a new `docs/kb/`, with a `current.md` pointer, CORE under 40 kB). This section
judges that draft against the measurements in S2–S5. Critique only: **no file here is
created, moved or edited**, per the read-only mandate.

## 1. What the draft gets right

1. **Separating lifecycle from topic.** The corpus's failure is not "too many files",
   it is that current truth and historical record sit in the same directory with the
   same authority. The draft's five classes name exactly that distinction.
2. **CORE < 40 kB as one context window.** The right unit: a session must be able to
   load everything it is obliged to trust. Today's mandatory pack is 78,110 B
   (S5/S2) and is *95.3% over* that line, so the target is real work, not a rename.
3. **Decisions and ghosts as registries, not prose.** S3c shows zero of 170 files
   asserts a ghost as fact, yet the refutations live inside 18 kB of onboarding prose
   that nobody re-reads. A registry is the correct home.
4. **Handoffs to ARCHIVE.** `GEN12_HANDOFF*` (5 files, incl. a
   `GEN12_HANDOFF_TRAPS.superseded.md`) are the clearest case in the corpus.
5. **A single pointer as the entry point.** `OUTLINE.md` (36,705 B) and
   `00_README.md` currently both claim to orient a newcomer; one pointer, not two.

## 2. Where the draft is naive or silent

### D1 — `REGISTRY/decisions.md` is not a new file; it is a missing one
The draft treats the decision registry as a greenfield artefact. It is not.
`docs/design/decisions.md` **does not exist** (S3c: `find -iname "*decision*"` returns
only `d58_13_strip_width_decisions_block.md`), yet it is referenced **585 times across
63 files**, and at least 7 supersession banners in S3b name it as the *successor*. The
same holds for `PREREG.md` / `NOTE.md` (86 refs). So:
- the registry's *specification has already been written* by those banners — it is a
  reconstruction task with a dictated interface, not a design task;
- the draft's REFERENCE/ has no home for a dangling target and no check that a
  `SUPERSEDED-BY` target exists at all. A dangling successor is a worse defect than a
  ghost: a ghost claim can be refuted, a dangling successor makes a *correct* banner
  unusable.
- Consequence for the budget: `decisions.md` 1,400 B is a *summary of an artefact that
  must first be rebuilt* from 585 citation contexts. That is the single largest hidden
  cost in the draft.

### D2 — The draft has no home and no byte for `STATE.json`
`STATE.json` is 12,838 B of generated state. It does not fit in 40,000 B alongside a
22 kB CORE: 22,000 + 12,838 = 34,838 B leaves 5,162 B for README, all registry headers
and every working note. Either `STATE.json` leaves the counted set or the draft's
arithmetic fails by 2,838 B the moment it is honest about its own inventory.
Recommendation: `WORK/STATE.json`, **generated**, explicitly *outside* the counted
budget, allowed to rot, plus a ≤3 kB digest of it inside `WORK/current.md`. A generated
file that is allowed to rot is safe; a hand-maintained 12,838 B file pretending to be
authoritative is exactly the `roadmap-next-2026-11-08.md` failure mode (S3).

### D3 — The draft loses the 1,010 dangling citations
S2/S5: 1,010 citations across 313 tokens already fail to resolve. The draft deletes no
paths — but it **renames everything** into `docs/kb/`, which invalidates every citation
at once, converting a 1,010-link problem into a ~4,300-link problem. Its only answer is
"ARCHIVE needs an index", which is the same problem one level down and at larger scale.
A redirect map (old path → new path) must ship **in the same commit** as any move, or
the move must not happen. This is why S7's minimum-viable plan creates files first and
moves nothing.

### D4 — `WORK/current.md` has no specified source of truth
The draft asserts the pointer without saying what generates it. Left to prose, it
becomes the **fourth** roadmap: `roadmap.md`, `roadmap-next-2026-11-08.md` (already
Grade-A stale, S3) and `OUTLINE.md` are the first three. It must be *generated* from
`GEN13_HANDOFF.md` + `graded_meshing_plan.md` + the open rows of `defect_register.md`,
and the generation must be deterministic enough that a re-run produces no diff (S7).

### D5 — `REFERENCE/` (60 files, 1,118,991 B) has no owner and no freshness rule
REFERENCE is 26.0% of the corpus and contains the most-cited document in it
(`absorbing_termination_scope.md`, 77 inbound). Nothing in the draft forces any of the
60 to remain true. It also drops S4's two dangerous families — graded facts restated
without citation (69/73 silent) and material/topology facts (74/82 silent) — with no
rule that a restatement must cite its home. Worse, the natural home for the graded
family, `graded_meshing_plan.md`, classifies as **WORK** (S5), so a citation rule that
points only at CORE would miss it.

### D6 — ARCHIVE has no git here, so "we can always look it up later" is false
There is no git in this container. Forensics after an archive move ride on file content
and one index. The draft should therefore mandate `ARCHIVE/INDEX.md` with an explicit
`file → superseded-by` row per archived artefact; S3b already supplies 13 banners and
48 affected files, so the table is ~85 rows of mostly mechanical work.

## 3. Revised budgeted structure

Same five classes (they are right). Bytes are the **counted** budget; everything else
is 0 by construction.

| path | bytes | what it is |
|---|---|---|
| `docs/kb/README.md` | 2,600 | orientation: the five classes, the budget rule, the index, "read this much" |
| `docs/kb/WORK/current.md` | 1,200 | generated pointer: where we are now (≤3 kB digest of STATE.json) |
| `docs/kb/CORE/01_VISION.md` | 4,200 | what the project is, what "done" means |
| `docs/kb/CORE/02_SYSTEM.md` | 7,500 | architecture as it *is*, with module→file map |
| `docs/kb/CORE/03_INVARIANTS.md` | 4,800 | physics/numeric invariants that must never be violated |
| `docs/kb/CORE/04_INTERFACES.md` | 5,500 | contracts: job schema, port ownership, data formats |
| `docs/kb/REGISTRY/defects.md` | 1,600 | header + open rows + pointer to `defect_register.md` |
| `docs/kb/REGISTRY/decisions.md` | 1,400 | header + decisions reconstructed from the 585 refs |
| `docs/kb/REGISTRY/ghosts.md` | 1,200 | refuted claims G-1..G-3 + rule "asserting ≠ mentioning" |
| **counted total** | **30,000** | **75% of the 40,000 B line → 10,000 B headroom** |

Uncounted but owned:

| path | files | bytes | rule |
|---|---|---|---|
| `WORK/` (plans, handoffs, `STATE.json`) | 9 + 1 | 337,402 + 12,838 | living; refreshed or retired each session; `STATE.json` generated |
| `REFERENCE/` | 60 | 1,118,991 | slow-changing; must carry a `verified:` date; read on demand only |
| `ARCHIVE/` | 85 | 2,171,101 | frozen; `INDEX.md` + `superseded-by` on every row |

Read profiles, to make the budget checkable rather than aspirational:

- **A. Orientation** — README + current.md = 3,800 B (today: 78,110 B).
- **B. Normal session** — A + all four CORE files = 25,800 B.
- **C. Session touching defects or a refuted claim** — B + `REGISTRY/*` = 30,000 B.
- All three are under 40,000 B with headroom; none requires an uncounted file.

The 30,000 B target is 25% under the line on purpose: CORE is the one thing that
legitimately grows, and a budget with no slack is a budget that gets violated quietly.

## 4. What the revision does not change

The five class names, the `docs/kb/` root, the CORE<40 kB rule, the "handoffs to
ARCHIVE" call, and the `current.md` idea are all kept. The revision adds a missing
owner for `REFERENCE/`, a home for `STATE.json`, a redirect obligation, a generator
contract for `current.md`, an `ARCHIVE/INDEX.md`, and it re-frames `decisions.md` from
"new file" to "reconstruct the file 585 links already point at".
