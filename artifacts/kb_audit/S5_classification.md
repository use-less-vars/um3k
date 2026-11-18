# S5 — Classification of the 170 in-scope documents

Companion machine-readable table: `S5_classification.tsv` (170 rows, one per in-scope
file). Columns: `path, bytes, class, action, budget_counted_bytes, counted_basis,
has_status_header, cited_in, cites_out, rationale`.

Classes are **lifecycle** classes (what may be read as current truth), not topics.
The budget is a separate axis: `budget_counted_bytes` is the part of a file that a
naive "read the mandatory set" policy would actually pay for.

## 1. Totals

| class | files | raw B | % of 4,308,072 | budget-counted B | has status header | cited_in==0 |
|---|---|---|---|---|---|---|
| CORE | 3 | 47,132 | 1.1% | 47,132 | 0/3 | 0 |
| REGISTRY | 8 | 595,728 | 13.8% | 13,370 | 0/8 | 0 |
| WORK | 9 | 337,402 | 7.8% | 0 | 1/9 | 0 |
| UNCERTAIN | 5 | 37,718 | 0.9% | 0 | 1/5 | 1 |
| REFERENCE | 60 | 1,118,991 | 26.0% | 0 | 9/60 | 5 |
| ARCHIVE | 85 | 2,171,101 | 50.4% | 0 | 16/85 | 3 |
| **total** | **170** | **4,308,072** | 100% | **60,502** | **27/170** | **9** |

`raw` sums to exactly 4,308,072 B = the text scope established in S2, so the table
partitions the scope with no file dropped and no file counted twice.

Header rate is 27/170 = **15.9%**, and it is worst exactly where it matters most:
0/3 CORE and 0/8 REGISTRY. The two classes that a reader is supposed to trust are
the only two with no staleness marker anywhere.

## 2. What each class means, and the action attached

`action` is the migration verb, deliberately not a move:

- **CORE (3) — `DISTIL`.** The three files a session must read to be useful. They are
  47,132 B of prose. That is already 7,132 B over a 40,000 B budget *before* a single
  registry header is added, so CORE cannot be "moved as-is" — it has to be rewritten
  as distillation. Copying them into `CORE/` reproduces the current failure.
- **REGISTRY (8) — `HEADER`.** Append-only ledgers (`defect_register.md` 165,357 B,
  `dispatch_log.md` 215,587 B, `soundness.md` 71,318 B, `EM_SOLVER_LEDGER.md` 47,690 B).
  The body must never be read whole; only a written header is counted, and the body
  stays addressable. This is the one class where "big file" is not a defect.
- **WORK (9) — `KEEP-WORK`.** Living plans: `graded_meshing_plan.md`,
  `roadmap.md`, `GEN13_HANDOFF.md`, `cpp_full_loop_plan.md`, `OUTLINE.md` (36,705 B).
  These are allowed to be current-but-rough; they are consumed through a generated
  `WORK/current.md`, never dumped into context.
- **UNCERTAIN (5) — `PARK`.** Five files whose evidence does not decide the class
  (`pml_notes.md`, two `s11_refit_from_phasors` variants, `modal_solver_paths.md`,
  `e13_antenna_scope.md`). Parked under REFERENCE with a TODO owner rather than
  guessing. `e13_antenna_scope.md` is also a true orphan.
- **REFERENCE (60) — `KEEP-REF`.** Slow-changing specs, theory memos, audits and
  closed investigations. Contains the single most cited document in the corpus,
  `absorbing_termination_scope.md` with **77 inbound** citations.
- **ARCHIVE (85) — `MOVE-ARCHIVE`.** Acceptance records, preregistrations, closed
  handoffs, forensics. **50.4% of all bytes.** Frozen and read-only once moved.

## 3. The number that changes the plan: ARCHIVE is load-bearing

**82 of the 85 archive-class files have `cited_in > 0`, totalling 330 inbound
citations.** Archiving is therefore not a de-risking move — it is a *relocation* of
330 live links. The two largest historical artefacts, `dispatch_log.md` and
`defect_register.md` (34 inbound each), are REGISTRY, and `t4_amp_ratio.md` (17),
`m3c_gate_v2.md` (10), `deflation_v2_preregistration.md` (10),
`complex_load_analysis_2026-11-04.md` (11), `anchor_audit_2026-11-05.md` (11) are
ARCHIVE. A move that is not accompanied by a redirect map breaks all of them at once
(see S7 step 8).

## 4. DELETE: zero proposed

**No file is proposed for deletion.** This is a deliberate, stated choice, not an
omission:

- the repo has a DR-44 precedent for *retaining* superseded artefacts;
- every "useless" document here is an experiment record, and experiment records are
  what the corpus exists to preserve;
- there is no git in this container, so deleting is irreversible *and* unauditable —
  a delete proposal I cannot show a recovery path for should not be made.

The only candidates a careless audit would call deletable are the **six true orphans**
(both `cited_in == 0` and `cites_out == 0`):

| file | class | why it is kept anyway |
|---|---|---|
| `d583_straight_guide_preregistration.md` | ARCHIVE | a preregistration whose experiment is not otherwise recorded |
| `d585_h_ladder.md` | ARCHIVE | result ladder with no inbound link — the only copy |
| `3d_ntff_te_query.md` | REFERENCE | paired query/spec with `3d_ntff_te_spec.md`; the spec is cited |
| `nedelec_solver_review.md` | REFERENCE | review of a solver still in use |
| `flux_projection_verification_2026-11-03.md` | REFERENCE | verification record for a live claim |
| `e13_antenna_scope.md` | UNCERTAIN | sole document for that scope |

Three further files have `cited_in == 0` but do cite others, so they are not orphans:
`TRAME_HAZARDS.md` (which matters — it is the only non-onboarding file that names a
ghost token as existing, S3c), `e3_phase2_closure.md`, `2026-11-05_toolchain_install.md`.

## 5. Sensitivity of the budget number

`budget_counted_bytes` for REGISTRY is measured as *bytes before the first `## `
heading, capped at 4,000*. The cap is doing real work and is reported honestly:

| registry file | pre-H2 bytes | counted |
|---|---|---|
| `component_map.md` | 1,844 | 1,844 |
| `defect_register.md` | 888 | 888 |
| `pipeline_map.md` | 744 | 744 |
| `03_KNOWN_BUGS.md` | 716 | 716 |
| `soundness.md` | 703 | 703 |
| `EM_SOLVER_LEDGER.md` | 475 | 475 |
| `dispatch_log.md` | **196,401** | 4,000 (capped) |
| `STATE.json` | 12,838 (no H2) | 4,000 (capped) |

Two files have no usable header to extract: `dispatch_log.md` has no `## ` structure
until byte 196,401 (one log entry is 7,508 B on a single line), and `STATE.json` is
JSON with no headings at all. For those two the count must be a **newly written**
~600 B summary, not an extraction. Using the honest written-header estimate instead
of the 4,000 cap gives a REGISTRY total of ~6,570 B rather than 13,370 B.

Both numbers support the same conclusion. As-is budget-counted total =
47,132 (CORE, undistilled) + 13,370 (headers) = **60,502 B**, i.e. **51% over** the
40,000 B budget; optimistically 47,132 + 6,570 = **53,702 B**, still **34% over**.
A pure reorganisation of today's files cannot reach 40,000 B. Only distillation can
(see S6 for the 30,000 B target and S7 for the order of work).

A second sensitivity: a naive "first 25 lines" header rule would report
`dispatch_log.md` at 52,067 B of header, because its long log entries fall inside the
first 25 lines. Line-count is not a proxy for header size; heading-structure is.

## 6. Cross-references

- S3 (staleness) supplies the 7 headerless Grade-A/B stale files that the
  `has_status_header` column alone cannot find.
- S3b supplies the 13 supersession banners → the ARCHIVE index table.
- S3c supplies the ghost refutation set → REGISTRY/ghosts.md.
- S4 supplies the two silent-carrier families (graded 69/73, material/topology 74/82)
  that must be pinned to `graded_meshing_plan.md` / `emfit/materials.py`; note that
  `graded_meshing_plan.md` lands in **WORK**, which is why the citation rule in S7
  cannot simply point at CORE.
