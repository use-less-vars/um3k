# S4 — Duplicated knowledge: which restatements are exposed to drift

**Scope.** Nine candidate "one fact, many places" families, each measured
exhaustively by grep over `docs/` (plus `server/`, `emfit/`, `evidence/` where
the canonical home is code). For every carrier I recorded three things: the hit
count, the *whole-file* byte weight, and whether the carrier **cites** its
canonical source at that same line. A carrier that cites is a pointer and can
follow the source if it changes. A carrier that does **not** cite is a silent
restatement: it is a copy that will not be updated when the source moves.
Silent copies are the drift surface.

`byte` is always whole-file size, so it measures *how much text sits behind the
copy*, not the copy itself.

Family summary, ranked by silent (uncited) carrier count:

| # | Family | Carriers | Hits | Silent | Verdict |
|---|--------|---------:|-----:|-------:|---------|
| F5 | `graded\|grading` | 73 | 496 | **69** | dangerous |
| F6 | `eps_r\|EPS_R\|topology\|material_id\|substrate` | 82 | 449 | **74** | dangerous |
| F1 | `emfit.vis/2` literal | 6 | 9 | 0 | safe |
| F2 | `VIS_SCHEMA` symbol | 5 | 11 | 0 | safe |
| F3 | wavedude/poc-state endpoints | 7 | 28 | 0 | safe |
| F4 | NTFF | 4 | 11 | 0 | safe |
| F7 | copied `\| DR-nn` rows | 3 | 21 | 0 | safe |
| F8 | E11 result numbers | 2 | 13 | 0 | safe |
| F9 | mode-naming rule | — | — | — | **withdrawn** |

The shape is the finding: the two families with dozens of carriers are exactly
the two where almost nobody cites, and the six well-cited families are small.
Citation discipline here tracks *whether the source is code*, not how many
writers touch the fact.

## F1 — `emfit.vis/2` schema literal (6 carriers, 9 hits, 113,842 B) — SAFE

Canonical source: `server/poc_app.py:149` (`VIS_SCHEMA = "emfit.vis/2"`),
`:159` (`VIS_SCHEMAS`), loader at `:560` / `:751`.

| Carrier | Bytes | Hits | Cites source |
|---|---:|---:|:--:|
| onboarding/01_ARCHITECTURE.md | 17,079 | 2 | yes |
| onboarding/STATE.json | 12,838 | 2 | yes |
| visualizer_architecture.md | 11,659 | 2 | yes |
| UM3K_UI_ARCHITECTURE.md | 40,707 | 1 | yes |
| onboarding/00_README.md | 13,419 | 1 | yes |
| onboarding/03_KNOWN_BUGS.md | 18,140 | 1 | yes |

All six name `server/poc_app.py`, so a schema bump has six pointers to follow.
The real duplication is inside the tree, not the docs: the same literal is
hard-coded at `evidence/termination/run_build_A.py:536`, `:1532`, `:1735`.
That is a code-to-code copy, outside this audit's remit but worth flagging —
the docs are cleaner than the code here.

## F2 — `VIS_SCHEMA` symbol (5 carriers, 11 hits, 95,702 B) — SAFE

| Carrier | Bytes | Hits | Cites source |
|---|---:|---:|:--:|
| onboarding/00_README.md | 13,419 | 3 | yes |
| onboarding/STATE.json | 12,838 | 3 | yes |
| UM3K_UI_ARCHITECTURE.md | 40,707 | 2 | yes |
| onboarding/01_ARCHITECTURE.md | 17,079 | 2 | yes |
| visualizer_architecture.md | 11,659 | 1 | yes |

Symbol-level references, all anchored to `poc_app.py`. Same 5 files as F1 minus
`03_KNOWN_BUGS.md`, which quotes the literal but not the symbol. No action.

## F3 — wavedude / poc-state endpoints (7 carriers, 28 hits, 130,476 B) — SAFE

| Carrier | Bytes | Hits | Cites source |
|---|---:|---:|:--:|
| onboarding/01_ARCHITECTURE.md | 17,079 | 8 | yes |
| onboarding/03_KNOWN_BUGS.md | 18,140 | 5 | yes |
| onboarding/00_README.md | 13,419 | 4 | yes |
| onboarding/02_PHYSICS_ROADMAP.md | 16,634 | 4 | yes |
| onboarding/STATE.json | 12,838 | 4 | yes |
| UM3K_UI_ARCHITECTURE.md | 40,707 | 2 | yes |
| visualizer_architecture.md | 11,659 | 1 | yes |

Highest hit density of any safe family (28 hits across 7 files), but every
occurrence is attributed to the server. This is the pattern the F5/F6 writers
should copy.

## F4 — NTFF (4 carriers, 11 hits, 37,677 B) — SAFE

`emfit/ntff.py` exists and is 54,646 B, so the fact has a live home.

| Carrier | Bytes | Hits | Cites source |
|---|---:|---:|:--:|
| 3d_ntff_te_query.md | 3,514 | 5 | yes |
| GEN13_HANDOFF.md | 4,691 | 3 | yes |
| onboarding/02_PHYSICS_ROADMAP.md | 16,634 | 2 | yes |
| onboarding/STATE.json | 12,838 | 1 | yes |

All four cite `emfit/ntff.py`. Note the interaction with S3: `e13_antenna_scope.md`
still claims NTFF has "no implementation" — that is a stale *claim*, not a
duplicate, which is why it sits in S3 and not here.

## F5 — `graded` / `grading` (73 carriers, 496 hits, 2,770,915 B) — DANGEROUS

Only 4 files cite, and they are the four onboarding-pack files
(`00_README.md`, `01_ARCHITECTURE.md`, `02_PHYSICS_ROADMAP.md` 16,634 B/22 hits,
`STATE.json`). The other **69 carriers are silent**.

| Silent carrier | Bytes | Hits |
|---|---:|---:|
| dispatch_log_archive_2026-Q4.md | 201,130 | 89 |
| defect_register.md | 165,357 | 46 |
| dispatch_log.md | 215,587 | 39 |
| box_sweep_preregistration.md | 18,672 | 24 |
| session_open_gen7.md | 19,932 | 23 |
| strip_width_reconcile.md | 18,231 | 17 |
| d583.md | 38,608 | 11 |
| zfree_diagnosis.md | 128,464 | 11 |

Home: `graded_meshing_plan.md` (33,854 B, 43 hits). The aggravating factor is
that the home is **still design only** — there is no `emfit/graded*` and no
`emfit/mesh*` module. So 2.77 MB of prose describes a capability that has no
code authority to be checked against, and 69 of 73 descriptions do not point at
the plan. When the plan changes, only the onboarding pack will follow.

## F6 — `eps_r` / `EPS_R` / `topology` / `material_id` / `substrate` (82 carriers, 449 hits, 3,059,384 B) — DANGEROUS

8 cite, 74 silent. Home is **code** (`emfit/materials.py`, `emfit/copper.py`),
which makes the silent majority worse than F5: a real authority exists and is
mostly not referenced.

Citing: `zfree_diagnosis.md` 128,464/25, `dispatch_log.md` 215,587/18,
`component_map.md` 42,705/10, `load_definition_forensics.md` 13,032/8,
`roadmap` 26,527/5, `OUTLINE` 36,705/3, `absorbing_termination_scope.md`
38,408/1, `pml_notes.md` 4,076/1.

| Silent carrier | Bytes | Hits |
|---|---:|---:|
| anchor_preregistration.md | 51,809 | 41 |
| deflation_preregistration.md | 45,634 | 20 |
| d58_extraction_acceptance.md | 66,569 | 18 |
| d583.md | 38,608 | 17 |
| d58_closeout.md | 21,592 | 16 |
| deflation_v2_preregistration.md | 38,773 | 15 |
| cross_check_script.md | 41,542 | 13 |
| d43b_acceptance.md | 44,064 | 13 |
| pairing_rule_preregistration.md | 113,536 | 13 |
| soundness.md | 71,318 | 10 |

Sharpest single case: `anchor_preregistration.md` has the most hits of any file
in the family (41) and cites **neither** `emfit/materials.py` **nor**
`EM_SOLVER_LEDGER.md`. A pre-registration that restates the material
definitions 41 times without naming their home is the one most likely to be
frozen against a stale definition — and pre-registrations are precisely the
documents that must not silently track a moving target.

## F7 — copied `| DR-nn` register rows (3 carriers, 21 hits, 78,371 B) — SAFE

| Carrier | Bytes | Hits | Cites source |
|---|---:|---:|:--:|
| onboarding/03_KNOWN_BUGS.md | 18,140 | 8 | yes |
| GEN12_HANDOFF_STATE.md | 48,880 | 7 | yes |
| s11_phase_investigation.md | 11,351 | 6 | yes |

These are literal table rows duplicated out of `defect_register.md`, the worst
structural kind of copy — but all three name the register, so they at least
declare their origin. Also checked: there is no parallel `| D-nn` row anywhere,
so there is no second numbering scheme to reconcile. Note that
`s11_phase_investigation.md` is simultaneously the S3 stale offender on DR-24..29
(both the copy and the claim are wrong there): duplication and staleness landed
in the same file.

## F8 — E11 result numbers (6.517281 / 4.904143 / 6.415728) (2 carriers, 13 hits, 262,350 B) — SAFE

`E11_residual_preregistration.md` (46,763 B, 9 hits) is the home;
`dispatch_log.md` (215,587 B, 4 hits) cites it. Zero silent carriers. Full
numeric literals, so any drift here would be instantly visible anyway.

## F9 — mode-naming rule — WITHDRAWN (not a duplicate family)

I opened this as a candidate and it does not survive. The only thing resembling
a shared convention is `onboarding/00_README.md:225`, "## 7. The naming rules you
can break the build with" — **one** carrier, **one** hit, 13,419 B. The `TE`/`TM`
tokens resolve to 3 hits total (`OUTLINE` 2, `d52b_claim_inventory` 1) and they
are unrelated physics statements, not shared vocabulary. There is no stated rule
and no identifiable canonical home, so there is nothing to be a duplicate *of*.
Reporting it as a non-finding rather than a duplication risk.

## Cross-check against existing register entries

`docs/design/soundness.md` already carries doc-defect entries of exactly this
kind: E16 (`zfree_shape` banner-vs-body), G05 (`t4_amp_ratio`'s "205-line draft
as a pre-registration"), and a `:311` entry on the superseded `m3c_gate_v2`
§6.1 sentence. Two consequences worth carrying into the report:

1. Duplication and staleness are already being logged as defects in this KB, so
   F5/F6 are instances of a recognised failure mode, not a new class of problem.
2. Those entries live in a *design* document. Whatever home is created for
   F5/F6 findings should match that precedence, since `soundness.md` is where
   the KB's own defect discipline already lives.

## Method and limits

Counts are lexical: F5 and F6 are token families, so a hit is a mention and not
proof of a restated fact. Byte totals are whole-file, deliberately, as a proxy
for "how much prose is unreachable from the source". Citation was judged
line-local, so a file that cites its source elsewhere but restates without
naming it is counted silent — the conservative direction. Nothing was fixed.

<!-- generated by KB audit chunk 2; sources: filesystem walk + targeted greps + reads; mtime used as last-touch proxy except where an in-content date is quoted; no git history available -->
