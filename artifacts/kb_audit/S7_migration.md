# S7 — Migration plan and standing tests

Everything below is a **proposal**. Nothing in this audit created, moved, renamed or
edited a file: all output is new files under `artifacts/kb_audit/`. The plan is written
to be executable by someone with write access, and ordered so that the first ten steps
are safe to stop after.

## 1. Constraints that shape the order

1. **No git here.** No history to fall back on, no revert, and no way to prove an
   archive move preserved content. Hence: create before move, and never move in step 1.
2. **A move is a broken-link event.** 1,010 citations across 313 tokens already fail to
   resolve (S2), and 330 inbound citations point into archive-class files (S5). Renaming
   into `docs/kb/` invalidates every one of them at once. Any move must ship with a
   redirect map in the same commit (step 8) — or must not happen.
3. **The one artifact everyone needs is missing, not stale.** `docs/design/decisions.md`
   is referenced 585 times across 63 files and does not exist (S3c); `PREREG.md` /
   `NOTE.md` account for another 86 refs. Creating files, not moving them, is the
   highest-value work available.
4. **Nothing may be deleted.** Zero delete proposals (S5 §4).

## 2. Minimum viable migration — 10 steps

Each step is independently verifiable and leaves the corpus no worse than it found it.

| # | Action | Touches | New bytes | Risk if skipped |
|---|---|---|---|---|
| 1 | Create `docs/kb/README.md` + the four `CORE/` files as **pure distillations** (write new prose; copy nothing) | 0 existing files | ~25,800 (counted) | the whole plan; and every later step inherits the 78,110 B pack |
| 2 | Create `REGISTRY/decisions.md` by harvesting the 585 reference contexts + the S3b banners — this *reconstructs* the file links already point at | 0 existing files | ~1,400 | the dangling-successor defect stays, and 585 links stay wrong |
| 3 | Create `REGISTRY/defects.md`: header (open rows, ~1,600 B) + pointer to `defect_register.md`; **do not split rows yet** | 0 existing files | ~1,600 | duplicating a 165,357 B ledger creates a second truth |
| 4 | Create `REGISTRY/ghosts.md` from `STATE.json:193-210` + G-1..G-3 of `03_KNOWN_BUGS.md:300-350`, with the rule "asserting is a defect, mentioning is not" | 0 existing files | ~1,200 | the refutations stay buried in 18 kB of onboarding prose |
| 5 | Create `WORK/current.md` as a **generated** pointer (source: `GEN13_HANDOFF.md` + `graded_meshing_plan.md` + open rows of `defect_register.md`) | 0 existing files | ~1,200 | it becomes the 4th stale roadmap |
| 6 | Fix status headers on the 8 Grade-A/B files of S3: **add** one to the 3 that have none (`roadmap-next-2026-11-08.md`, `onboarding/00_README.md`, `defect_register.md`) and **correct** the 5 whose header is contradicted by their own body (A-1..A-5) | 8 existing files, header lines only | ~0 | the 5 known-wrong files keep asserting known-false status |
| 7 | Give the 48 S3b files a real `SUPERSEDED-BY:` banner (they mention supersession in prose: 177 lines, but only 13 styled banners exist, across 6 files: `pairing_rule_preregistration.md` ×5, `d58_13_strip_width_decisions_block.md` ×3, `figures/README.md` ×2, `zfree_shape.md`, `t4_s13_draft.md`, `cpp-kernel-status-2026-11-09.md`) | 48 existing files, header lines only | ~48 × 120 = ~5,800 (in ARCHIVE/REFERENCE, uncounted) | supersession stays a word, not a fact |
| 8 | Ship the **redirect map** (`old path → new path`) as one file, so the 1,010 citations keep resolving before anything moves | 1 new file | ~40,000 (generated, uncounted) | step 10 and every later move breaks the corpus silently |
| 9 | Generate `WORK/STATE.json` as a ≤3 kB digest of today's 12,838 B snapshot, outside the counted budget | 1 new file | ≤3,000 | 12,838 B of unclaimed budget, per S6 D2 |
| 10 | Wire the standing tests (§4) in **read-only, report-only** mode | 1 script | ~0 | the corpus re-rots with no signal |

Steps 1–5 create files and touch nothing: this is the whole "decisions.md is missing"
recovery, and it is what a first session should do. Steps 6–7 are header-only edits to
existing files (the only edits in the plan). Step 8 must precede any move. Step 9 is
housekeeping; step 10 makes the rest self-checking.

## 3. Full cleanup (order of a month, not of a day)

1. Move the 85 ARCHIVE files, **with step 8's redirect map already merged**, and add
   `ARCHIVE/INDEX.md` (`file → superseded-by`, ~85 rows; S3b's 13 banners + 48 files are
   the seed).
2. Move the 60 REFERENCE files; give each a `verified:` date and a named owner — 26.0%
   of the corpus and 295 inbound citations currently have neither (S6 D5).
3. Rewrite `01_ARCHITECTURE.md` (17,079 B) and `02_PHYSICS_ROADMAP.md` (16,634 B) into
   `CORE/` as distillation; retire `00_README.md` into `README.md`.
4. Fix S4's two silent-carrier families: graded facts (69/73 restated without citation)
   must cite `graded_meshing_plan.md`; material/topology facts (74/82) must cite
   `emfit/materials.py`.
5. Retire `roadmap-next-2026-11-08.md` (Grade-A stale) and `OUTLINE.md` (36,705 B,
   competing entry point) into ARCHIVE, with the redirect map updated.
6. Resolve the 5 UNCERTAIN files (S5) to a class with a named owner; resolve the 6 true
   orphans or give each an explicit inbound link.
7. Only then: delete nothing, and re-run the standing tests as blocking.

## 4. Standing tests

Run read-only, no network, no writing. Each check names what it fails on **today**
(measured, so the check is falsifiable from the start) and its realistic false positive.

| # | Check | Fails today on | False positive to guard against |
|---|---|---|---|
| T1 | every in-scope file has a status header | 143 of 170 (27/170 = 15.9% pass) | `.json`/`.png`/index `README.md` have no prose header; ARCHIVE files that legitimately carry `SUPERSEDED` inline. Scope the check to `.md`, allow an explicit `n/a:` prefix. |
| T2 | every ARCHIVE file names its successor | all of them (no ARCHIVE exists yet; only 74 lines in 48 files name a successor) | an artifact superseded by *code* or by a *deletion decision*, not by a document — allow `SUPERSEDED-BY: none (code)` with a reason. |
| T3 | CORE total ≤ 40,000 B | yes: 47,132 B if the 3 CORE files are moved as-is; 78,110 B for today's actual pack (+95.3%) | a legitimate CORE file growing mid-migration; measuring bytes on disk vs rendered text; counting `STATE.json` into the budget (it must be out of scope). |
| T4 | `STATE.json` regenerates with no diff on re-run | cannot fail today — nothing regenerates it, so the check is green but **vacuous** | volatile keys (timestamps, ordering, absolute paths) will make it red forever for the wrong reason: compare after normalising declared-volatile keys. |
| T5 | no dangling citations | yes: 1,010 citations / 313 tokens | intentional external targets — upstream paths, `emfit/*.py` code paths, URLs, `api/` references. Allow-list *code* and *URL* citations; do **not** allow-list `docs/…` (that is exactly how `decisions.md` went missing). |
| T6 | no document asserts a ghost | **passes** (0 of 170; S3c) | quoting a ghost in order to refute it — `03_KNOWN_BUGS.md:300-350` does precisely this. The check must be "asserts as present fact", never "mentions the token"; `TRAME_HAZARDS.md` merely cites test line numbers. |
| T7 | every `SUPERSEDED-BY:` target exists | yes: `docs/design/decisions.md` (585 refs), `PREREG.md` / `NOTE.md` (86 refs) | a banner naming an external doc or a code symbol; a banner naming a *section* (`§10.8`) rather than a file. Resolve sections against the target file before failing. |
| T8 | restatements of graded/material facts cite their home | yes: graded 69/73 silent, material/topology 74/82 silent (S4) | a document stating a genuine CORE invariant that never lived in `graded_meshing_plan.md`; a document restating a *refuted* value in order to refute it. Require the citation only for factual values, not for the refutations themselves. |

T6 passing and T7 failing is the single most important signal in this audit: the corpus
does not hallucinate symbols, it **loses the documents its own banners promise**. A
migration that only adds ghosts/decisions registries as *new* files would leave T7 red.
