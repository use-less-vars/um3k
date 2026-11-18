# S3b — Supersession: line-level anatomy of every "superseded" statement

**Why this is separate from S3.** S3 asks "is this file's *content* still true?"
(this audit's S3_stale.md proves 8 such cases against the code and the
registers). S3b asks a different and much cheaper question: "where does the KB
*say* something is superseded, and does that statement carry a successor?"
A supersession note is a self-declared stale marker, so it is the one place the
KB annotates its own dead text — and the only place we can audit at scale
without reading the physics. This section counts those notes and sorts them by
whether they are usable.

## Reconciliation with S2 (resolved — S2 stands, no correction)

S2 reported `SUPERSEDED 187 / STALE 153 / ARCHIVED 10` across the marker block.
I could not reproduce those at first and suspected drift; the convention turned
out to be exact. All three reproduce as **case-insensitive, word-boundary
occurrence** counts restricted to the **170-file text inventory**:

| Marker | S2 | `\bX\b`, ci, 170 files | ci, all docs | Bare substring, 170 files |
|---|---:|---:|---:|---:|
| superseded | 187 | **187** | 202 | 199 |
| stale | 153 | **153** | 169 | 168 |
| archived | 10 | **10** | 10 | 10 |
| deprecated | 0 | 0 | 0 | 0 |
| obsolete | 0 | 0 | 0 | 0 |

So S2 is an **occurrence** census and S3b is its **line-level complement** over
the same corpus under the same convention. They are consistent; the numbers
differ only because 177 lines carry 187 occurrences (`superseded` clusters —
banner blocks restate the word on adjacent lines). Marker-file union, any of the
five markers, `*.md` only: **77 files**.

`DEPRECATED` and `OBSOLETE` are zero everywhere. The KB uses one word for this
concept, which is why this census is trustworthy: there is no synonym pool
hiding additional markers.

## Aggregate

| Measure | Count |
|---|---:|
| Files carrying >= 1 "superseded" (any case) | 48 |
| Lines carrying >= 1 "superseded" | 177 |
| Whole-file bytes behind those lines | 2,220,547 |
| Lines that **name a successor** (`.md`, `docs/`, `§n`, `Lnnn`, `line nnn`) | 74 |
| Styled document/region **status banners** | 13 |
| Lines that are neither banner nor successor-naming | 94 |

The headline: **74 of 177** supersession lines (42 %) tell a reader where to go
next. The remaining 103 do not — 13 of them are banners that at least mark the
region, and **94 are bare uses of the word** with no navigational value at all.
Uppercase `SUPERSEDED` (the styled/all-caps form that signals a deliberate
status marker) occurs only **27** times, so the loud, findable markers are a
small minority of the vocabulary.

## The 13 status banners (all of them)

| File | Line(s) |
|---|---|
| `pairing_rule_preregistration.md` | 554, 866, 912, 929, 963 |
| `d58_13_strip_width_decisions_block.md` | 11, 18, 156 |
| `zfree_shape.md` | 3 |
| `figures/README.md` | 45, 135 |
| `t4_s13_draft.md` | 1 |
| `cpp-kernel-status-2026-11-09.md` | 192 |

All 13 sit in **6 files**, and `pairing_rule_preregistration.md` alone holds 5.
This is the actionable core: 13 banners is a small enough set to bring to a
uniform shape (region marker + named successor + date), and doing so would fix
the worst of the annotation debt in a handful of edits. Note that
`pairing_rule_preregistration.md`, `figures/README.md` and `zfree_shape.md`
score 0-2 on the "names a successor" column precisely because their banners name
successors *in prose* ("§6.1/R7/§4.4", old line numbers 327-337 and 760-761,
`decisions.md` [2026-10-27 SUPERSESSION PASS] anchor) rather than in `§`/`.md`
token form — so the column under-counts these three and they are better than
they look.

## The 94 non-findings (why the raw count overstates the problem)

Most of the 94 are not supersession statements at all:

- **Identifiers.** `corr_ez_superseded_longitudinal` appears 11 times across 6
  files (`README` 2, `corr_ez_vv_threshold` 2, `d58_extraction_acceptance` 1,
  `m3c_gate_v2` 2, `t4_amp_ratio` 1, `zfree_shape` 3). A column name is not a
  claim that anything is superseded.
- **Filenames.** `build_A_50ohm.superseded.json` — the marker is in the path,
  not in prose.
- **Negations.** e.g. `e3_baseline_benchmark.md:5` "nothing ... is superseded".
  The line asserts the *absence* of supersession; a keyword census counts it as
  a hit and an LLM skimming for "superseded" would misread it. This is the
  single most important caveat on all three of S2's numbers.
- **Verb uses** inside methodology prose ("the earlier value is superseded by
  ...") that describe a past event rather than marking live text.

Filtered for these, the genuine annotation population is ~83 lines (74 naming +
13 banners, less overlap), not 177.

## Per-file table (48 files, sorted by supersession lines)

`succ` = lines naming a successor; `ban` = status banners; `named in-file` =
successor actually named where not token-detectable.

| File | Bytes | Lines | Succ | Ban | Successor named in-file |
|---|---:|---:|---:|---:|---|
| m3c_gate_v2.md | 105,260 | 17 | 9 | — | §10.8, §9, §101.20 |
| figures/README.md | 11,963 | 13 | 0 | 2 | (in prose) |
| pairing_rule_preregistration.md | 113,536 | 11 | 2 | 5 | §6.1, R7, §4.4; old lines 327-337, 760-761 |
| soundness.md | 71,318 | 10 | 4 | — | m3c_gate_v2, zfree_shape, t4_amp_ratio |
| dispatch_log.md | 215,587 | 8 | 7 | — | defect_register, §5, EM_SOLVER_LEDGER |
| dispatch_log_archive_2026-Q4.md | 201,130 | 8 | 8 | — | decisions.md, PREREG.md, evidence/strip_width/ERRATA_001.md |
| defect_register.md | 165,357 | 8 | 2 | — | EM_SOLVER_LEDGER, e3_dr42_closure_benchmark, e3_baseline_benchmark |
| GEN12_HANDOFF_STATE.md | 48,880 | 8 | 2 | — | NOTE.md, README.md, GEN12_HANDOFF_TRAPS.md |
| normalization_scheme.md | 29,130 | 8 | 8 | — | §101.21, decisions.md |
| corr_ez_vv_threshold.md | 21,355 | 8 | 3 | — | decisions.md, zfree_shape, §1 |
| zfree_shape.md | 61,234 | 5 | 0 | 1 | decisions.md (2026-10-27 pass) |
| E11_residual_preregistration.md | 46,763 | 5 | 0 | — | — (verb uses; `:13` names the value 6.52 %, not a doc) |
| d58_13_strip_width_decisions_block.md | 30,805 | 5 | 5 | 3 | §9, §8, §1 |
| t4_amp_ratio.md | 114,323 | 4 | 0 | — | — |
| d52b_claim_inventory.md | 62,375 | 4 | 2 | — | decisions.md, t4_s13_draft, §13.8 |
| absorbing_termination_scope.md | 38,408 | 4 | 2 | — | decisions.md |
| port_normalisation_audit.md | 28,515 | 4 | 3 | — | anchor_audit_2026-11-05, §6, z0_quasistatic_ladder |
| anchor_audit_2026-11-05.md | 15,617 | 4 | 1 | — | §4 |
| d43b_acceptance.md | 4,034 | 4 | 0 | — | — |
| zfree_diagnosis.md | 128,464 | 3 | 0 | — | — |
| d58_extraction_acceptance.md | 66,569 | 3 | 0 | — | — |
| t4b_t4c_preregistration.md | 50,890 | 2 | 1 | — | §3.5, §4 |
| EM_SOLVER_LEDGER.md | 47,690 | 2 | 1 | — | GEN12_HANDOFF, e3_baseline_benchmark, cpp-kernel-status |
| component_map.md | 42,705 | 2 | 1 | — | decisions.md |
| d58_acceptance.md | 24,410 | 2 | 0 | — | — |
| session_open_gen8.md | 16,340 | 2 | 2 | — | dispatch_log, defect_register |
| session_close_gen8.md | 12,146 | 2 | 2 | — | dispatch_log |
| 57c_closeout, deflation_v2_preregistration, z0_quasistatic_ladder, HISTORY, session_close_gen6, cpp-kernel-status, GEN12_HANDOFF_TRAPS, GEN12_HANDOFF, openems_referee_spec, e3_baseline_benchmark, session_close_gen7, d44_acceptance, t4_s13_draft, anchor_note_extraction, load_integration_verification, s11_phase_investigation, preservation_gate_preregistration_a35, z0_provenance_and_twin, theory_round2_memo, s11_port_forensics, direct_vi_forensics | — | 1 each | 0-1 | 1-2 | mostly §-refs |

The 21 one-line files are collapsed because none of them carries an actionable
pattern; two of them do carry one banner each (`t4_s13_draft.md:1`,
`cpp-kernel-status-2026-11-09.md:192`) and are listed in the banner table above.

## The filename-level supersession

`GEN12_HANDOFF_TRAPS.superseded.md` (20,973 B, mtime 11-12) is superseded in its
**name only**: the body header still reads "Sixteen traps" and never says so.
Successor is `GEN12_HANDOFF_TRAPS.md`. This is the inverse of the 94 non-findings
— here the marker carries information but is invisible to any grep of content,
which is why a content-only census cannot see it. It is the one case in the
corpus where the filename is the sole supersession record.

## What this measurement supports

1. A 13-banner cleanup is cheap and well-scoped (6 files).
2. `m3c_gate_v2.md` (17 lines, 9 successors) is the KB's most supersession-aware
   document and the model for the banner shape.
3. 94 of 177 lines are noise, including a negation that reads as a false
   positive — so **no keyword count of "superseded" should be used as a staleness
   proxy** without line-level inspection. S2's three numbers are correct as
   occurrence counts and must not be read as 187/153/10 dead documents.

## Method and limits

Counts are `ripgrep`-equivalent scans over `docs/` with case-insensitive matching;
"names a successor" was decided by regex for `.md`, `docs/`, `§`, `L...`/`line
nnn` forms and then read manually for the banner files, where successor naming is
prose-like and the regex under-counts (three files noted above). Byte figures are
whole-file. No content was edited and no file was renamed.

<!-- generated by KB audit chunk 2; sources: filesystem walk + targeted greps + reads; mtime used as last-touch proxy except where an in-content date is quoted; no git history available -->
