# docs/ — inventory, coupling and currency

KB audit, chunk 1 (Phases 1–2). **Read-only**: no file outside `artifacts/kb_audit/` was created,
modified, moved or deleted, and nothing was staged or committed.

## Scope and how to read the columns

* `docs/` holds **218 files / 12,753,536 B**. The per-file tables below cover the **text inventory**
  only (`*.md *.txt *.json *.yaml *.yml *.csv`): **170 files / 4,308,072 B**.
* **Excluded from the tables by scope** (they are not inventory documents): the 21 `.tex` paper
  sources, 16 `.png`, 8 `.pdf`, 1 `.gif`, `docs/report/main.log`, and one
  `docs/infra/Dockerfile.runtime.proposed` — **48 files / 8,445,464 B**, totalled separately under
  *Non-text files under `docs/`* below. That is **66 %** of the tree's bytes: the 5.7 MB figure the
  tree is usually described by is the text half only.
* `status` = the file's own front-most `Status:` line, trimmed. `&mdash;` = **no status header**:
  **143 of 170 files (84.1 %)**, so 27 (15.9 %) carry one.
* `in/out` = distinct files citing it / distinct files it cites (170 docs + 103 scanned code files).
  Basename matching, so `in` counts *files*, not links, and a hub score is a lower bound.
* `mtime` = filesystem mtime, used as the last-touch proxy. `last_commit` exists only in
  `inventory.tsv`; it is filled for the 41 hub/core/marked/orphan files audited by hand and blank
  elsewhere. The git read surface exposes no commit **dates**, so mtime is the date proxy throughout.

## `docs/` root — 5 text files, 105,059 B

| path | bytes | status | mtime | in/out | what it is |
|---|---:|---|---|---:|---|
| `HISTORY.md` | 31,091 | &mdash; | 2026-10-26 01:41 | 2/4 | narrative history of the machine written for a human reader |
| `OUTLINE.md` | 36,705 | &mdash; | 2026-10-28 04:57 | 5/12 | single-page repo orientation: what works, what does not, milestones, traps (36.7 kB, 92 % of the 40 kB core budget) |
| `architecture.md` | 6,660 | &mdash; | 2026-10-19 22:36 | 1/0 | module-level architecture of the solver package |
| `pml_notes.md` | 4,076 | &mdash; | 2026-10-19 14:53 | 1/0 | PML derivation notes (layer thickness as a wavelength law) |
| `roadmap.md` | 26,527 | &mdash; | 2026-11-13 23:59 | 9/4 | live milestone/roadmap tracker |

**Subtotal `docs/`: 5 files, 105,059 B**  (2.4 % of the 4,308,072 B text inventory)

## `docs/prereg/` — 1 text file, 4,536 B

| path | bytes | status | mtime | in/out | what it is |
|---|---:|---|---|---:|---|
| `d585_h_ladder.md` | 4,536 | &mdash; | 2026-10-30 00:33 | 0/0 | D58.5 H-ladder preregistration (ORPHAN; only file in docs/prereg/) |

**Subtotal `docs/prereg/`: 1 files, 4,536 B**  (0.1 % of the 4,308,072 B text inventory)

## `docs/infra/` — 1 text file, 3,542 B

| path | bytes | status | mtime | in/out | what it is |
|---|---:|---|---|---:|---|
| `2026-11-05_toolchain_install.md` | 3,542 | &mdash; | 2026-11-05 09:45 | 0/1 | Two machines are involved. Nothing in this document was installed by the agent: |

**Subtotal `docs/infra/`: 1 files, 3,542 B**  (0.1 % of the 4,308,072 B text inventory)

## `docs/design/` — 161 text files, 4,182,211 B

| path | bytes | status | mtime | in/out | what it is |
|---|---:|---|---|---:|---|
| `3d_ntff_te_query.md` | 3,514 | OPEN enquiry against commit `27df752`. Not a decision, a plan or... | 2026-11-14 02:42 | 0/0 | open enquiry: TE query for the 3-D NTFF far-field transform (ORPHAN) |
| `3d_ntff_te_spec.md` | 1,001 | &mdash; | 2026-11-14 02:59 | 1/0 | Verbatim record of the Theory Engineer dispatch received for E13. Do not edit |
| `57c_acceptance.md` | 10,118 | FROZEN at write time, before any code was read for this dispatch. | 2026-10-29 14:27 | 1/1 | **Dispatch:** 57c (replaces 57b Task 2 / T3b). |
| `57c_closeout.md` | 44,565 | &mdash; | 2026-10-29 15:08 | 1/3 | **Dispatch:** 57c. **Companion, frozen first:** `docs/design/57c_acceptance.md`, committed at `0bca5f6`, 116 lines, sha256 `7c3... |
| `E11_residual_preregistration.md` | 46,763 | PREREGISTERED (no results yet). Closes when exit criteria met. | 2026-11-09 16:36 | 5/6 | E11 residual preregistration; header says "no results yet" but the 2026-11-10 amendment records the -6.517281 % measurement |
| `EM_SOLVER_LEDGER.md` | 47,690 | &mdash; | 2026-11-13 01:29 | 22/21 | ledger of EM solver runs and the claims they support |
| `GEN12_HANDOFF.md` | 27,138 | &mdash; | 2026-11-12 18:34 | 10/12 | generation-12 handoff: open questions, E11 target, traps |
| `GEN12_HANDOFF_STATE.md` | 48,880 | `evidence/{box_sweep,h_refine,matrix_audit,referee,referee_run2,r... | 2026-11-12 23:46 | 2/33 | handoff state snapshot (evidence paths, per-item status) |
| `GEN12_HANDOFF_TRAPS.md` | 28,240 | &mdash; | 2026-11-12 18:08 | 2/5 | live traps list (16 traps) |
| `GEN12_HANDOFF_TRAPS.superseded.md` | 20,973 | &mdash; | 2026-11-12 18:02 | 2/5 | superseded traps list (13 traps), kept as a historical record beside the live file |
| `GEN12_HANDOFF_WARS.md` | 32,951 | &mdash; | 2026-11-12 18:34 | 4/11 | **File 2 of 4.** File 1 (`docs/design/GEN12_HANDOFF.md`, 27,076 B) is the *state of the world*: what is true, what is banked, w... |
| `GEN13_HANDOFF.md` | 4,691 | &mdash; | 2026-11-14 20:44 | 2/0 | **From: EM-Solver Engineer (Gen 12)** |
| `TE_query_s2p_convolution.md` | 18,766 | OPEN enquiry against commit `a69ed43`. Not a decision, a plan or... | 2026-11-12 06:51 | 3/8 | Status: OPEN enquiry against commit `a69ed43`. Not a decision, a plan or a gate; no code |
| `TRAME_HAZARDS.md` | 8,054 | &mdash; | 2026-11-16 21:38 | 0/2 | Five places where this UI stack gives a confident, plausible, wrong answer. Companions: `UM3K_UI_ARCHITECTURE.md` |
| `UM3K_UI_ARCHITECTURE.md` | 40,707 | &mdash; | 2026-11-15 04:28 | 4/3 | This document describes the web UI in `server/poc_app.py`, states what is measurably wrong with its |
| `absorbing_termination_scope.md` | 38,408 | &mdash; | 2026-10-31 22:32 | 77/5 | absorbing-boundary/termination criteria and modal-path taxonomy; most-cited file in the tree |
| `ac4_wiring_scope_2026-11-02.md` | 9,007 | &mdash; | 2026-11-02 20:41 | 1/4 | **Slug** `ac4-wiring-scope-2026-11-02`. **Status: reads, plus arithmetic over one live grading run. No edit.** |
| `anchor_audit_2026-11-05.md` | 15,617 | &mdash; | 2026-11-05 23:06 | 11/5 | Dispatch `anchor-audit-2026-11-05`. Read-only provenance audit. **No host execution, no openEMS run, no new |
| `anchor_note_extraction_2026-11-04.md` | 14,093 | &mdash; | 2026-11-04 21:03 | 2/2 | Extracts the 'anchor does not describe the structure' note from the 6 records identified in `residual_vs_configuration_survey_2... |
| `anchor_preregistration.md` | 51,809 | PRE-REGISTRATION. Written and frozen before any measurement is ta... | 2026-10-28 17:20 | 9/0 | Status: PRE-REGISTRATION. Written and frozen before any measurement is taken. |
| `beta_dispersion_comparison_2026-11-07.md` | 7,979 | &mdash; | 2026-11-07 04:12 | 2/1 | Dispatch `beta-dispersion-comparison-2026-11-07`. Read-only analysis of beta values already banked on |
| `beta_drift_analysis_2026-11-05.md` | 13,022 | &mdash; | 2026-11-05 18:14 | 2/0 | **Date** 2026-11-05 (session date) · **Type** read-only analysis, one doc written, **no code change, no run, no evidence edit,... |
| `beta_refit_test_2026-11-05.md` | 27,654 | &mdash; | 2026-11-05 23:04 | 8/5 | Dispatch `beta-refit-test-2026-11-05`. **Read-only analysis of phasors already banked on disk.** |
| `box_sweep_preregistration.md` | 18,672 | &mdash; | 2026-10-31 00:53 | 7/1 | **Status: FROZEN before any sweep run.** Written and frozen at 2026-10-31T00:52Z, before the first graded |
| `c2b_preregistration.md` | 17,556 | &mdash; | 2026-10-27 03:41 | 7/1 | `C2b` is written against a change in `corr_e_z`, and `corr_e_z` has no measured noise floor: nobody has run the same statistic... |
| `c2b_step0_plan.md` | 5,899 | &mdash; | 2026-10-27 03:45 | 2/2 | 1. **What Step 0 measures.** The response of `\|corr_e_z\|` to refinement of the strip-edge cell size only. |
| `closed_form_with_two_wave_beta_2026-11-02.md` | 10,797 | analysis on recorded artefacts. Nothing re-run, no artefact modif... | 2026-11-02 22:22 | 9/1 | **Status:** analysis on recorded artefacts. Nothing re-run, no artefact modified. |
| `complex_load_analysis_2026-11-04.md` | 12,515 | &mdash; | 2026-11-03 23:40 | 11/0 | complex-load ratio test and pi-network bounds |
| `component_map.md` | 42,705 | &mdash; | 2026-10-30 23:50 | 5/19 | component/pipeline map of the codebase |
| `core_contract.md` | 30,313 | design only. Nothing here has been implemented, and nothing here... | 2026-10-27 13:33 | 5/1 | Status: design only. Nothing here has been implemented, and nothing here authorises a run. There is no |
| `corr_ez_vv_threshold.md` | 21,355 | &mdash; | 2026-10-27 15:48 | 4/2 | corr_ez_vv threshold 0.90 -> 0.91 with its derivation |
| `cpp-kernel-spec-2026-11-09.md` | 43,852 | proposal. Nothing here has been implemented or measured except wh... | 2026-11-08 14:26 | 2/0 | 2026-11-09 |
| `cpp-kernel-status-2026-11-09.md` | 28,957 | &mdash; | 2026-11-08 17:35 | 10/0 | **The C++ compiles and runs, in two independent builds.** The earlier version of |
| `cpp_full_loop_plan.md` | 40,269 | &mdash; | 2026-11-11 12:20 | 1/3 | **Status.** Planning document, proposal only. No code is changed by this dispatch, no |
| `cpp_solver_arch.md` | 43,294 | &mdash; | 2026-10-29 02:15 | 10/4 | **New document.** Authored at Dispatch 42. There was no `docs/design/cpp_solver_arch.md` in the tree before this pass and none... |
| `cross_check_script_2026-11-05.md` | 41,542 | &mdash; | 2026-11-05 23:05 | 2/2 | **Status: PRE-REGISTRATION. No script exists yet (`cross_check.py` is the next dispatch). No openEMS run has been performed for... |
| `d43b_acceptance.md` | 4,034 | &mdash; | 2026-10-28 15:34 | 2/1 | Contract artifact written before any edit, per Dispatch 43b Step 1. If anything in the |
| `d43b_extraction_audit.md` | 44,064 | &mdash; | 2026-10-29 11:48 | 4/5 | Read-only audit. Contract artifact written after the reads, before any other edit. |
| `d44_acceptance.md` | 16,054 | &mdash; | 2026-10-28 16:12 | 2/4 | **New document.** Authored at Dispatch 44, Task 1, and written before any other file was touched in that dispatch. It is the ar... |
| `d45_acceptance.md` | 9,247 | &mdash; | 2026-10-28 16:40 | 1/4 | **New document.** Authored at Dispatch 45, Task 1, and written before any other file was touched in that dispatch. It is the ar... |
| `d45_anchor_results.md` | 14,823 | &mdash; | 2026-10-28 17:50 | 8/1 | The run produced NO verdict. It terminated because the pre-registered driven path cannot return the physical modes at the finer... |
| `d45_negative_control_addendum.md` | 7,569 | &mdash; | 2026-10-28 19:42 | 1/1 | Dated 2026-10-28. Written and committed before the run whose readings it governs. |
| `d46_acceptance.md` | 1,747 | &mdash; | 2026-10-28 17:54 | 3/1 | These criteria are frozen before the pre-registration and before any implementation, and they are transcribed from the dispatch... |
| `d47_acceptance.md` | 5,941 | &mdash; | 2026-10-28 19:16 | 3/5 | These criteria are frozen before any deflated ladder measurement in this dispatch. Every number below is transcribed from a doc... |
| `d47_results.md` | 32,402 | result 1 matches on all seven measurable rows and result 2 holds at | 2026-10-28 20:19 | 3/4 | Status: result 1 matches on all seven measurable rows and result 2 holds at |
| `d48_acceptance.md` | 10,315 | &mdash; | 2026-10-28 21:05 | 3/6 | Frozen before measurement. Written and committed before any candidate set was |
| `d48_results.md` | 20,955 | &mdash; | 2026-10-28 21:31 | 1/6 | Measured under the rule frozen in `docs/design/d48_acceptance.md` (commit |
| `d49_acceptance.md` | 16,258 | &mdash; | 2026-10-28 21:41 | 1/6 | Dated 2026-10-28. Frozen on commit: the commit that first contains this file is |
| `d50_acceptance.md` | 5,091 | &mdash; | 2026-10-28 23:12 | 1/1 | Frozen before any file in this dispatch is edited. Source: the dispatch 50 brief as given by the supervisor. Where this file an... |
| `d51_acceptance.md` | 4,028 | &mdash; | 2026-10-28 23:50 | 1/1 | Frozen before any edit. If the tree contradicts this brief, the artifact wins; |
| `d52_acceptance.md` | 8,364 | NOT FROZEN. This file records what dispatch 52 must deliver and h... | 2026-10-29 01:16 | 3/1 | Status: NOT FROZEN. This file records what dispatch 52 must deliver and how it will be |
| `d52b_acceptance.md` | 14,430 | front-most fence of the dispatch. Nothing below is negotiable. | 2026-10-29 02:06 | 2/17 | **Written:** first action of dispatch 52b, before any other artefact. |
| `d52b_claim_inventory.md` | 62,375 | &mdash; | 2026-11-12 22:19 | 6/17 | **What this is.** The raw claim inventory taken by the single evidence sweep commissioned |
| `d53_acceptance.md` | 28,715 | front-most fence of the dispatch. Nothing below is negotiable. | 2026-10-29 03:33 | 1/9 | **Written:** first action of dispatch 53, before any other artefact. |
| `d54_acceptance.md` | 19,305 | &mdash; | 2026-10-29 03:50 | 4/6 | **Written.** This file is the first action of dispatch 54, taken before any other artefact of it. |
| `d57_acceptance.md` | 6,006 | &mdash; | 2026-10-29 12:07 | 3/4 | **Frozen before execution.** Recorded from the dispatch as issued. No criterion may be edited once |
| `d583_straight_guide_preregistration.md` | 38,608 | &mdash; | 2026-10-29 22:50 | 0/0 | D58.3 straight-guide preregistration (ORPHAN: nothing cites it, it cites nothing) |
| `d58_13_strip_width_decisions_block.md` | 30,805 | &mdash; | 2026-10-31 04:08 | 4/0 | Per `evidence/strip_width/PREREG.md` §12 (L314-315): *"No `decisions.md` write is claimed by this |
| `d58_acceptance.md` | 24,410 | &mdash; | 2026-10-29 15:28 | 4/11 | **Written.** This file is the first action of dispatch 58, taken before any other artefact of it. At the moment of writing, `do... |
| `d58_closeout.md` | 21,592 | &mdash; | 2026-10-29 16:49 | 1/6 | Provenance tags: [ARTIFACT] read from a file in this repository; [MEASURED] computed by a run validated against a banked number... |
| `d58_extraction_acceptance.md` | 66,569 | &mdash; | 2026-10-29 21:53 | 2/6 | **Frozen before any code for dispatch 58 is read.** This file is the contract. Where this file and a later artifact disagree, t... |
| `defect_register.md` | 165,357 | &mdash; | 2026-11-13 22:41 | 34/27 | DR-nn defect register (DR-47 is the latest row) |
| `deflation_preregistration.md` | 45,634 | living document. This file records a solver change and the check... | 2026-10-28 21:55 | 7/4 | Status: living document. This file records a solver change and the check that the change must pass. It is amended only by the d... |
| `deflation_v2_preregistration.md` | 38,773 | &mdash; | 2026-10-28 21:21 | 10/6 | deflation v2 preregistration, frozen before the run it governs |
| `direct_vi_forensics_2026-11-08.md` | 5,120 | &mdash; | 2026-11-08 03:38 | 3/2 | Does the FDTD engine actually contain a reflection at the termination, measured with no free |
| `dispatch_log.md` | 215,587 | &mdash; | 2026-11-09 22:01 | 34/56 | append-only dispatch log; largest file in docs/ (215 kB) |
| `dispatch_log_archive_2026-Q4.md` | 201,130 | &mdash; | 2026-11-04 15:17 | 3/29 | archived pre-2026-11-04 dispatch rows (201 kB), successor file is dispatch_log.md |
| `dr43_s21_extraction_scope.md` | 25,875 | &mdash; | 2026-11-12 17:37 | 3/6 | **CORRECTION (added after review).** DR-43 as registered is **FIXED-TESTED** — severity HIGH, opened 2026-11-12, closed at `doc... |
| `e13_antenna_scope.md` | 15,291 | scope only. No implementation exists, no code is proposed here, a... | 2026-11-13 23:42 | 0/0 | E13 antenna work: scope only (ORPHAN) |
| `e3_baseline_benchmark.md` | 20,942 | measurement record. No verdict is moved here, no build is recomme... | 2026-11-13 01:05 | 3/3 | **Dispatch:** S5a, commit 2 of 2. |
| `e3_dr42_closure_benchmark.md` | 13,607 | &mdash; | 2026-11-13 02:46 | 2/3 | **What this document is.** It records a host measurement taken by the operator on 2026-11-13, outside this container, and the f... |
| `e3_phase2_closure.md` | 9,911 | &mdash; | 2026-11-13 18:03 | 0/5 | **Status: CLOSED, 2026-11-13.** Scope: does the E3 speedup survive a change of optimisation level, of link-time optimisation, a... |
| `e3_phase2_scope.md` | 17,112 | &mdash; | 2026-11-13 00:29 | 3/7 | **Status: SCOPE ONLY.** This document states what phase 2 of E3 covers, what it |
| `extraction_three_layer_audit_2026-11-04.md` | 36,496 | &mdash; | 2026-11-04 23:16 | 1/0 | *"The TE's three-layer audit (Q3 response). The anchor note's reasoning is refuted (DR-32) — six records carry the pre-2026-11-... |
| `flux_projection_design_2026-11-03.md` | 13,021 | &mdash; | 2026-11-03 16:54 | 2/2 | Date: 2026-11-03. Status: design/specification only. No run performed, nothing graded, |
| `flux_projection_verification_2026-11-03.md` | 4,371 | &mdash; | 2026-11-03 14:18 | 0/0 | current-channel renormaliser verification, sign hazard found before code (ORPHAN) |
| `flux_renorm_analysis_2026-11-03.md` | 6,221 | &mdash; | 2026-11-04 15:06 | 2/1 | Scope: dispatch `flux-renorm-2026-11-03`. Read-only: no `.py` edited, no test changed, no simulation run. |
| `gap_analysis_2026-11-03.md` | 14,434 | &mdash; | 2026-11-03 13:27 | 3/1 | **Status: analysis of record, read-only.** No solve was run, no `.py` file was edited, no committed artefact was modified; `emf... |
| `ghost_wave_analysis_2026-11-08.md` | 16,118 | &mdash; | 2026-11-08 00:43 | 4/1 | **Dispatch:** `ghost-wave-data-analysis-2026-11-08` |
| `ghost_wave_forensics_2026-11-07.md` | 10,249 | &mdash; | 2026-11-07 19:56 | 2/0 | **2026-11-07 · dispatch `field-dump-and-ghost-wave-2026-11-07` · status: instrumentation only, the run has NOT been executed** |
| `graded_meshing_plan.md` | 33,854 | DESIGN ONLY. No file under `emfit/` was edited for this document... | 2026-11-16 22:03 | 4/2 | **Status:** DESIGN ONLY. No file under `emfit/` was edited for this document and no |
| `independent_anchor_qucs_2026-11-04.md` | 14,114 | &mdash; | 2026-11-04 23:56 | 1/2 | **Status: BLOCKED at stages B-E.** Stage A is complete; the technical engineer's section-2 formulas |
| `job_schema.md` | 18,584 | &mdash; | 2026-10-28 13:18 | 6/0 | **Design only.** Nothing in this document is implemented in `emfit/`. There is no job |
| `latex_structure.md` | 26,587 | &mdash; | 2026-10-26 12:49 | 2/21 | The reader is a numerically literate engineer who is taking this pipeline over: comfortable with Maxwell's |
| `lessons_learned_emfit.md` | 7,318 | &mdash; | 2026-11-08 17:35 | 2/6 | Six things this project got wrong, written for an engineer joining cold. Each |
| `lessons_learned_emfit_addendum.md` | 8,988 | &mdash; | 2026-11-11 04:17 | 4/1 | Companion to `lessons_learned_emfit.md` (L1–L6), which is unchanged. |
| `load_definition_forensics_2026-11-07.md` | 13,032 | &mdash; | 2026-11-07 04:49 | 2/0 | **Dispatch:** `load-definition-forensics-2026-11-07` -- **Date:** 2026-11-07 -- **Status:** read-only. No FDTD run. No `emfit/`... |
| `load_integration_verification_2026-11-07.md` | 13,850 | &mdash; | 2026-11-07 06:21 | 1/0 | **Date:** 2026-11-07 |
| `m3c_gate_v2.md` | 105,260 | &mdash; | 2026-10-28 07:10 | 10/6 | M3c gate v2; closing status v2.3, mode solver CLOSED |
| `modal_port_recon_2026-11-03.md` | 7,512 | &mdash; | 2026-11-03 00:29 | 1/0 | Where a modal launch would replace the lumped launch in `microstrip_wave`, and whether that |
| `modal_port_wiring_design_2026-11-03.md` | 11,329 | decision document, condensed 2026-11-03. The measurement it rests... | 2026-11-03 02:49 | 2/2 | Status: decision document, condensed 2026-11-03. The measurement it rests on, the derivation, the |
| `modal_port_wiring_measurement_2026-11-03.md` | 37,978 | measurement record, split out of `modal_port_wiring_design_2026-1... | 2026-11-03 03:04 | 1/1 | Status: measurement record, split out of `modal_port_wiring_design_2026-11-03.md` on |
| `modal_solver_paths.md` | 6,336 | &mdash; | 2026-10-31 22:39 | 3/1 | Provenance tags, in the form this repository already uses |
| `modalport_ownership.md` | 32,405 | &mdash; | 2026-10-27 01:44 | 7/0 | Evidence base: `emfit/` as it stands in the repo, `.scratch/logs/s10118_basis.py` (465 lines), `.scratch/logs/s10118_mesh_study... |
| `multifreq_beta_test_2026-11-07.md` | 26,597 | &mdash; | 2026-11-07 02:13 | 3/3 | *Dated 2026-11-07. Dispatch id `multifreq-beta-test-2026-11-07`, **re-issued after a workspace bounce**: |
| `multifreq_twin_2026-11-07.md` | 5,889 | &mdash; | 2026-11-07 03:27 | 1/2 | **Question.** The loaded sweep (build_A_50ohm, 5 bins, 3.64--8.74 GHz) put `beta_fit` about 3.9 % above `beta_model` on average... |
| `near_field_subset_refit_2026-11-04.md` | 10,420 | &mdash; | 2026-11-04 19:11 | 2/5 | Read-only, banked data: one arithmetic pass over `/s11/station_phasors` of `evidence/termination/build_A_50ohm_p51_phasors.json... |
| `nedelec_solver_review.md` | 31,142 | &mdash; | 2026-10-31 16:50 | 0/0 | theory-engineer review of the Nedelec solver (ORPHAN, 31 kB) |
| `normalization_scheme.md` | 29,130 | &mdash; | 2026-10-26 18:52 | 6/0 | normalisation scheme note; SUPERSEDED 2026-10-26 at L142 |
| `onboarding/00_README.md` | 13,419 | &mdash; | 2026-11-16 23:08 | 3/11 | onboarding entry point: reading order and rules of engagement |
| `onboarding/01_ARCHITECTURE.md` | 17,079 | &mdash; | 2026-11-16 23:06 | 3/4 | onboarding: architecture primer |
| `onboarding/02_PHYSICS_ROADMAP.md` | 16,634 | &mdash; | 2026-11-16 23:05 | 2/5 | onboarding: physics roadmap |
| `onboarding/03_KNOWN_BUGS.md` | 18,140 | &mdash; | 2026-11-16 22:56 | 4/8 | onboarding: known-bugs digest |
| `onboarding/STATE.json` | 12,838 | &mdash; | 2026-11-16 23:06 | 1/12 | onboarding: machine-readable state snapshot (head commit, artefact paths) |
| `openems_referee_spec_2026-11-10.md` | 24,608 | &mdash; | 2026-11-09 22:00 | 1/0 | **Date:** 2026-11-10 |
| `order_p_preregistration.md` | 40,404 | &mdash; | 2026-10-29 13:20 | 5/2 | **Status: FROZEN.** Registered before any run of the study it governs. Bar first, number |
| `pairing_rule_preregistration.md` | 113,536 | &mdash; | 2026-10-30 23:50 | 8/9 | pairing-rule preregistration, revision 3 supersedes revision 2 in place |
| `passivity-resolution-2026-11-09.md` | 14,978 | &mdash; | 2026-11-08 14:20 | 4/0 | 2026-11-09 |
| `passivity_ceiling_2026-11-02.md` | 4,550 | established by arithmetic on committed artefacts. No solve, no fi... | 2026-11-02 18:04 | 2/0 | **Status:** established by arithmetic on committed artefacts. No solve, no fit, no tuning. |
| `physics_invariant_layer.md` | 39,218 | &mdash; | 2026-10-28 16:46 | 4/3 | **New document.** 2026-10-28. Specifies a layer of physics invariants for |
| `pipeline_map.md` | 22,093 | &mdash; | 2026-10-30 23:40 | 2/2 | **Scope.** Every stage between "a job description" and "a quotable S-parameter", mapped |
| `port_normalisation_audit_2026-11-05.md` | 28,515 | &mdash; | 2026-11-06 00:16 | 1/4 | *Dated 2026-11-05. Stage A1 of a measurement-side audit. **This file's skeleton and the frozen |
| `pre_termination_prep_report_2026-11-02.md` | 13,186 | &mdash; | 2026-11-02 22:34 | 1/4 | Dispatch `pre-termination-prep-2026-11-02`, run as three workers plus independent verification passes. **Nothing is committed a... |
| `preservation_gate_geometry_a15_freeze.md` | 4,286 | &mdash; | 2026-10-28 23:40 | 1/0 | **Status: FROZEN.** This file, together with the commit that introduces |
| `preservation_gate_preregistration.md` | 13,118 | &mdash; | 2026-10-28 23:17 | 7/2 | **Status: frozen.** This file was written and committed before any run of the geometry it governs. It may not be amended after... |
| `preservation_gate_preregistration_a35.md` | 10,948 | &mdash; | 2026-10-28 23:56 | 2/1 | Dispatch 51, task 2. Frozen before any discrete solve at `eps_r = 3.5`. |
| `preservation_gate_results_a35.md` | 19,490 | &mdash; | 2026-10-29 00:09 | 6/0 | **Verdicts of record.** The registered A-3.5 run over levels 1-3 issued `STOPPED` at level 1 and no verdict on any falsifier. T... |
| `residual_vs_configuration_survey_2026-11-04.md` | 15,269 | complete, read-only. Nothing was run, edited or re-graded to prod... | 2026-11-04 20:36 | 2/7 | **Status:** complete, read-only. Nothing was run, edited or re-graded to produce it. Population: every |
| `roadmap-next-2026-11-08.md` | 29,038 | &mdash; | 2026-11-08 07:32 | 9/2 | New document. Design only. Nothing described here is implemented: there is no Touchstone |
| `s11_beta_test_brief_2026-11-04.md` | 2,615 | &mdash; | 2026-11-04 11:21 | 1/2 | One host run that separates `beta_one` from `beta_two_wave` in the recorded s11 phase by differential measurement. Read-only: *... |
| `s11_distance_and_magnitude_2026-11-04.md` | 9,323 | hypothesis, unresolved. Read-only. No code changed. No run perfor... | 2026-11-04 13:32 | 3/1 | Read-only dispatch `s11-distance-and-magnitude-2026-11-04`. Sources: the two artefacts, and the code |
| `s11_estimator_fix_2026-11-04.md` | 2,740 | pre-registered fix, not yet run. One line changed. No FDTD run pe... | 2026-11-04 12:15 | 1/3 | `emfit/studies.py:3387`, inside `microstrip_wave` (def at :2467), one line: |
| `s11_frame_pin_2026-11-04.md` | 4,215 | frame F2. Read-only. No code changed. No run performed. | 2026-11-04 11:21 | 4/3 | Read-only. No code changed, no run performed. |
| `s11_one_wave_vs_two_wave_2026-11-02.md` | 22,063 | &mdash; | 2026-11-03 13:07 | 3/1 | **Slug** `s11-one-wave-vs-two-wave-2026-11-02`. **Status: reads, arithmetic over banked artefacts, one |
| `s11_phase_investigation_2026-11-04.md` | 11,351 | hypothesis unconfirmed. No code changed. No run performed. DR-24.... | 2026-11-04 10:42 | 5/2 | Framing: this is an estimator audit, not a sign hunt. The premise "what single sign flip produces a 188.7535 deg offset" is FAL... |
| `s11_port_forensics_2026-11-07.md` | 8,778 | &mdash; | 2026-11-07 04:24 | 5/1 | Dispatch `s11-port-forensics-2026-11-07`. Read-only analysis of station phasors already banked on |
| `s11_refit_from_phasors_2026-11-04.md` | 3,974 | &mdash; | 2026-11-04 14:06 | 1/0 | - Dispatch `s11-refit-from-phasors-2026-11-04`, 2026-11-04. |
| `s11_refit_from_phasors_2026-11-04b.md` | 8,041 | &mdash; | 2026-11-04 15:14 | 5/1 | - Dispatch `s11-refit-from-phasors-2026-11-04b`, 2026-11-04. **Read-only**: one doc + one log row. |
| `session_close_gen10.md` | 6,869 | **validation complete — the independent referee agrees with the i... | 2026-11-11 04:41 | 1/1 | Date: 2026-11-13 |
| `session_close_gen5.md` | 12,961 | &mdash; | 2026-10-31 00:03 | 7/1 | Provenance tags: **[M]** measured in this repository in this pass, with the artefact cited beside |
| `session_close_gen6.md` | 29,804 | &mdash; | 2026-10-31 18:50 | 6/3 | Provenance tags: **[M]** measured in this repository against a named artefact; **[L]** read from the |
| `session_close_gen7.md` | 20,794 | &mdash; | 2026-10-31 23:25 | 4/5 | **Date:** 2026-11-01. **HEAD at write:** `ce16cdf` — "docs(design): write the modal-path taxonomy down and close the phase gap... |
| `session_close_gen8.md` | 12,146 | &mdash; | 2026-11-04 17:05 | 2/11 | **Date:** 2026-11-04. **HEAD at write:** `52986ff` — "dispatch_log: record that DR-19 is OPEN with its trail in the archive" [L... |
| `session_open_gen11.md` | 11,979 | &mdash; | 2026-11-12 18:35 | 7/4 | **Written 2026-11-12, at HEAD `3848d46`. Reader: the incoming engineer; read this FIRST, then `session_close_gen10` (the sessio... |
| `session_open_gen7.md` | 19,932 | &mdash; | 2026-11-01 15:59 | 3/7 | **Written 2026-11-02, at HEAD after `bca8d3b` + `e324089`. Reader: the incoming engineer; read this FIRST, then `session_close_... |
| `session_open_gen8.md` | 16,340 | &mdash; | 2026-11-04 17:05 | 3/9 | **Written 2026-11-04, at HEAD `52986ff`. Reader: the incoming engineer; read this FIRST, then `session_close_gen8` if it exists... |
| `soundness.md` | 71,318 | &mdash; | 2026-10-30 23:44 | 7/21 | soundness argument and checklist for the solver claims |
| `sparse_eigenmode.md` | 44,001 | &mdash; | 2026-10-29 11:47 | 14/0 | sparse eigenmode (eigsh/pencil) documentation |
| `spatial_collocation_audit_2026-11-04.md` | 6,921 | &mdash; | 2026-11-04 18:42 | 4/2 | Read-only (tree reading + one arithmetic pass). No source change, no run, no commit. Line numbers HEAD, `emfit/studies.py` unle... |
| `spice_adapter_scope.md` | 33,538 | &mdash; | 2026-11-11 12:21 | 4/2 | **Status.** Proposal. No implementation, no solver and no code change accompanies this |
| `strip_termination_design_2026-11-02.md` | 9,466 | proposal, not applied. No source edited, no solve run. | 2026-11-02 23:48 | 3/1 | **Status:** proposal, not applied. No source edited, no solve run. |
| `strip_termination_refuted_2026-11-03.md` | 6,756 | &mdash; | 2026-11-02 23:51 | 5/3 | **Status: negative result.** The D1 change was applied, exercised and reverted before commit. `emfit/studies.py` is byte-identi... |
| `strip_termination_worker_report_2026-11-03.md` | 7,274 | &mdash; | 2026-11-02 23:21 | 1/1 | **Status: STOP CONDITION HIT at Phase B1.3. The D1 fix was applied, verified, then REVERTED.** |
| `strip_width_reconcile_2026-11-01.md` | 18,231 | &mdash; | 2026-11-01 04:22 | 2/4 | **Slug** `strip-width-reconcile-2026-11-01`. **Status: reads only.** No code changed, no run |
| `t4_amp_ratio.md` | 114,323 | &mdash; | 2026-10-29 11:47 | 17/5 | T4 amplitude-ratio gate: rung 4 measured, ladder non-monotone, T4_amp FAIL at 44.09 % |
| `t4_s13_draft.md` | 14,528 | &mdash; | 2026-10-28 02:01 | 3/1 | SUPERSEDED 2026-10-28, retained for provenance; successor is t4_amp_ratio.md |
| `t4b_t4c_preregistration.md` | 50,890 | &mdash; | 2026-10-28 15:34 | 6/2 | Pre-registration only. No solve, no gate run, no field reconstruction. Every figure below is a reading |
| `termination_build_plan.md` | 24,371 | &mdash; | 2026-10-31 23:58 | 2/7 | **Status.** Plan only. No code was written, no solver run was performed, no gate was re-priced, no |
| `theory_round2_memo.md` | 9,781 | &mdash; | 2026-10-31 23:58 | 4/2 | **What this file is.** Verbatim "round-2" memo from one theory-engineer worker instance, 2026-10-31, unedited below this header... |
| `upstream-extraction-2026-11-08.md` | 11,569 | &mdash; | 2026-11-08 04:15 | 5/3 | Why must the s11 extraction plane sit at or upstream of the load, what does the code now |
| `visual_engine_arch.md` | 49,924 | &mdash; | 2026-10-28 15:18 | 7/3 | **New document, authored at Dispatch 42.** It is not a revision of anything, it replaces nothing and it supersedes nothing. No... |
| `visualizer_architecture.md` | 11,659 | &mdash; | 2026-11-11 04:41 | 8/2 | visualiser (vis) architecture after the wavedude -> vis rename |
| `voltage_integration_and_reflection_2026-11-08.md` | 8,963 | &mdash; | 2026-11-08 01:10 | 3/1 | Date: 2026-11-08. Supersedes two claims in |
| `wave_convention_audit_2026-11-05.md` | 7,740 | &mdash; | 2026-11-04 17:45 | 2/1 | Read-only (tree reading + one arithmetic pass). Question: can the pipeline's wave convention produce the common ~1.05–1.06 fact... |
| `web_ui_architecture_2026-11-08.md` | 7,052 | &mdash; | 2026-11-08 02:04 | 3/0 | This is a design note for a proof of concept, not a description of a shipped feature. The single goal is an |
| `z0_current_and_split_2026-11-05.md` | 6,960 | &mdash; | 2026-11-04 17:44 | 5/6 | Read-only analysis of `evidence/termination/`. **No source change, no run performed, no artefact re-graded,** |
| `z0_provenance_and_twin_2026-11-04.md` | 9,893 | &mdash; | 2026-11-04 18:14 | 5/2 | Read-only analysis of `emfit/` and `evidence/termination/`. No source change, no FDTD run, no commit. Line numbers are HEAD, `e... |
| `z0_quasistatic_ladder_2026-11-05.md` | 36,435 | &mdash; | 2026-11-06 00:00 | 5/4 | Read-only analysis. No source change, no host run, no commit. One new doc (this file) plus one row in |
| `z_eff_analysis_2026-11-03.md` | 7,001 | &mdash; | 2026-11-03 20:11 | 2/0 | Question: what impedance does the `series_r` stamp (`emfit/studies.py:2789-2793`, `emfit/evolve.py:6-18`) present |
| `zfree_diagnosis.md` | 128,464 | &mdash; | 2026-11-12 22:19 | 6/6 | diagnosis of the z-free-space behaviour (128 kB) |
| `zfree_shape.md` | 61,234 | &mdash; | 2026-11-12 22:19 | 7/4 | SUPERSEDED (L3): metric compared the vertical component; successor is corr_ez_vv_threshold.md (L27) |

**Subtotal `docs/design/`: 161 files, 4,182,211 B**  (97.1 % of the 4,308,072 B text inventory)

## `docs/report/` — 1 text file, 761 B

| path | bytes | status | mtime | in/out | what it is |
|---|---:|---|---|---:|---|
| `figures/README.md` | 761 | &mdash; | 2026-10-27 15:58 | 18/4 | figure index for the paper figures; the only .md file under docs/report/ |

**Subtotal `docs/report/`: 1 files, 761 B**  (0.0 % of the 4,308,072 B text inventory)

## `docs/figures/` — 1 text file, 11,963 B

| path | bytes | status | mtime | in/out | what it is |
|---|---:|---|---|---:|---|
| `README.md` | 11,963 | &mdash; | 2026-10-28 12:52 | 19/12 | figure index for docs/figures/ (15 marker hits) |

**Subtotal `docs/figures/`: 1 files, 11,963 B**  (0.3 % of the 4,308,072 B text inventory)

**Grand total, text inventory: 170 files, 4,308,072 B. Grand total, all of `docs/`: 218 files, 12,753,536 B.**

## Non-text files under `docs/` (out of table scope, totalled here)

| extension | files | bytes | what it is |
|---|---:|---:|---|
| `.png` | 16 | 5,253,688 | figures and mode-shape images |
| `.pdf` | 8 | 2,378,254 | compiled paper + figure PDFs |
| `.tex` | 21 | 499,716 | paper sources: `main.tex`, `tikzstyles.tex`, 19 `sec_*.tex` |
| `.gif` | 1 | 280,689 | one animated figure |
| `.log` | 1 | 30,370 | LaTeX build log |
| `.proposed` | 1 | 2,747 |  |
| **total** | **48** | **8,445,464** | |

Read this table as a warning: `docs/figures` (3,875,632 B) and `docs/report` (2,981,413 B) are 54 % of
`docs/` and almost entirely out of scope for a `*.md`-only pass. `docs/report` holds exactly **one**
markdown file (`figures/README.md`, 761 B); the paper itself is 21 `.tex` files, so a text-only reader
sees 761 B of a 2.98 MB directory.

### Hubs

Ranked by `cited_in`: the number of distinct files that name the file. 77 means 77 separate
documents break or dangle if it moves — that is what makes a file load-bearing, not its size.

| path | bytes | in | out | what it is |
|---|---:|---:|---:|---|
| `docs/design/absorbing_termination_scope.md` | 38,408 | **77** | 5 | absorbing-boundary/termination criteria and modal-path taxonomy; most-cited file in the tree |
| `docs/design/defect_register.md` | 165,357 | **34** | 27 | DR-nn defect register (DR-47 is the latest row) |
| `docs/design/dispatch_log.md` | 215,587 | **34** | 56 | append-only dispatch log; largest file in docs/ (215 kB) |
| `docs/design/EM_SOLVER_LEDGER.md` | 47,690 | **22** | 21 | ledger of EM solver runs and the claims they support |
| `docs/figures/README.md` | 11,963 | **19** | 12 | figure index for docs/figures/ (15 marker hits) |
| `docs/report/figures/README.md` | 761 | **18** | 4 | figure index for the paper figures; the only .md file under docs/report/ |
| `docs/design/t4_amp_ratio.md` | 114,323 | **17** | 5 | T4 amplitude-ratio gate: rung 4 measured, ladder non-monotone, T4_amp FAIL at 44.09 % |
| `docs/design/sparse_eigenmode.md` | 44,001 | **14** | 0 | sparse eigenmode (eigsh/pencil) documentation |
| `docs/design/anchor_audit_2026-11-05.md` | 15,617 | **11** | 5 | Dispatch `anchor-audit-2026-11-05`. Read-only provenance audit. **No host execution, no openEMS run, no new |
| `docs/design/complex_load_analysis_2026-11-04.md` | 12,515 | **11** | 0 | complex-load ratio test and pi-network bounds |
| `docs/design/GEN12_HANDOFF.md` | 27,138 | **10** | 12 | generation-12 handoff: open questions, E11 target, traps |
| `docs/design/cpp-kernel-status-2026-11-09.md` | 28,957 | **10** | 0 | **The C++ compiles and runs, in two independent builds.** The earlier version of |
| `docs/design/cpp_solver_arch.md` | 43,294 | **10** | 4 | **New document.** Authored at Dispatch 42. There was no `docs/design/cpp_solver_arch.md` in the tree before this pass and none... |
| `docs/design/deflation_v2_preregistration.md` | 38,773 | **10** | 6 | deflation v2 preregistration, frozen before the run it governs |
| `docs/design/m3c_gate_v2.md` | 105,260 | **10** | 6 | M3c gate v2; closing status v2.3, mode solver CLOSED |
| `docs/design/anchor_preregistration.md` | 51,809 | **9** | 0 | Status: PRE-REGISTRATION. Written and frozen before any measurement is taken. |
| `docs/design/closed_form_with_two_wave_beta_2026-11-02.md` | 10,797 | **9** | 1 | **Status:** analysis on recorded artefacts. Nothing re-run, no artefact modified. |
| `docs/design/roadmap-next-2026-11-08.md` | 29,038 | **9** | 2 | New document. Design only. Nothing described here is implemented: there is no Touchstone |
| `docs/roadmap.md` | 26,527 | **9** | 4 | live milestone/roadmap tracker |
| `docs/design/beta_refit_test_2026-11-05.md` | 27,654 | **8** | 5 | Dispatch `beta-refit-test-2026-11-05`. **Read-only analysis of phasors already banked on disk.** |
| `docs/design/d45_anchor_results.md` | 14,823 | **8** | 1 | The run produced NO verdict. It terminated because the pre-registered driven path cannot return the physical modes at the finer... |
| `docs/design/pairing_rule_preregistration.md` | 113,536 | **8** | 9 | pairing-rule preregistration, revision 3 supersedes revision 2 in place |
| `docs/design/visualizer_architecture.md` | 11,659 | **8** | 2 | visualiser (vis) architecture after the wavedude -> vis rename |
| `docs/design/box_sweep_preregistration.md` | 18,672 | **7** | 1 | **Status: FROZEN before any sweep run.** Written and frozen at 2026-10-31T00:52Z, before the first graded |
| `docs/design/c2b_preregistration.md` | 17,556 | **7** | 1 | `C2b` is written against a change in `corr_e_z`, and `corr_e_z` has no measured noise floor: nobody has run the same statistic... |
| `docs/design/deflation_preregistration.md` | 45,634 | **7** | 4 | Status: living document. This file records a solver change and the check that the change must pass. It is amended only by the d... |
| `docs/design/modalport_ownership.md` | 32,405 | **7** | 0 | Evidence base: `emfit/` as it stands in the repo, `.scratch/logs/s10118_basis.py` (465 lines), `.scratch/logs/s10118_mesh_study... |
| `docs/design/preservation_gate_preregistration.md` | 13,118 | **7** | 2 | **Status: frozen.** This file was written and committed before any run of the geometry it governs. It may not be amended after... |
| `docs/design/session_close_gen5.md` | 12,961 | **7** | 1 | Provenance tags: **[M]** measured in this repository in this pass, with the artefact cited beside |
| `docs/design/session_open_gen11.md` | 11,979 | **7** | 4 | **Written 2026-11-12, at HEAD `3848d46`. Reader: the incoming engineer; read this FIRST, then `session_close_gen10` (the sessio... |
| `docs/design/soundness.md` | 71,318 | **7** | 21 | soundness argument and checklist for the solver claims |
| `docs/design/visual_engine_arch.md` | 49,924 | **7** | 3 | **New document, authored at Dispatch 42.** It is not a revision of anything, it replaces nothing and it supersedes nothing. No... |
| `docs/design/zfree_shape.md` | 61,234 | **7** | 4 | SUPERSEDED (L3): metric compared the vertical component; successor is corr_ez_vv_threshold.md (L27) |
| `docs/design/d52b_claim_inventory.md` | 62,375 | **6** | 17 | **What this is.** The raw claim inventory taken by the single evidence sweep commissioned |
| `docs/design/job_schema.md` | 18,584 | **6** | 0 | **Design only.** Nothing in this document is implemented in `emfit/`. There is no job |
| `docs/design/normalization_scheme.md` | 29,130 | **6** | 0 | normalisation scheme note; SUPERSEDED 2026-10-26 at L142 |
| `docs/design/preservation_gate_results_a35.md` | 19,490 | **6** | 0 | **Verdicts of record.** The registered A-3.5 run over levels 1-3 issued `STOPPED` at level 1 and no verdict on any falsifier. T... |
| `docs/design/session_close_gen6.md` | 29,804 | **6** | 3 | Provenance tags: **[M]** measured in this repository against a named artefact; **[L]** read from the |
| `docs/design/t4b_t4c_preregistration.md` | 50,890 | **6** | 2 | Pre-registration only. No solve, no gate run, no field reconstruction. Every figure below is a reading |
| `docs/design/zfree_diagnosis.md` | 128,464 | **6** | 6 | diagnosis of the z-free-space behaviour (128 kB) |

Next tier (in 3–5): `OUTLINE.md` (5), `E11_residual_preregistration.md` (5), `component_map.md` (5), `core_contract.md` (5), `order_p_preregistration.md` (5), `s11_phase_investigation_2026-11-04.md` (5), `s11_port_forensics_2026-11-07.md` (5), `s11_refit_from_phasors_2026-11-04b.md` (5), `strip_termination_refuted_2026-11-03.md` (5), `upstream-extraction-2026-11-08.md` (5), `z0_current_and_split_2026-11-05.md` (5), `z0_provenance_and_twin_2026-11-04.md` (5), `z0_quasistatic_ladder_2026-11-05.md` (5), `GEN12_HANDOFF_WARS.md` (4), `UM3K_UI_ARCHITECTURE.md` (4), `corr_ez_vv_threshold.md` (4), `d43b_extraction_audit.md` (4), `d54_acceptance.md` (4), `d58_13_strip_width_decisions_block.md` (4), `d58_acceptance.md` (4), `ghost_wave_analysis_2026-11-08.md` (4), `graded_meshing_plan.md` (4), `lessons_learned_emfit_addendum.md` (4), `passivity-resolution-2026-11-09.md` (4), `physics_invariant_layer.md` (4), `s11_frame_pin_2026-11-04.md` (4), `session_close_gen7.md` (4), `spatial_collocation_audit_2026-11-04.md` (4).

Four observations the ranking forces:

1. `absorbing_termination_scope.md` is cited by **77** files while citing 5 — a CORE candidate that no
   other single document substitutes for.
2. `dispatch_log.md` (34/56) and `defect_register.md` (34/27) are cited as *authority* by a third of the
   tree, yet both are append-only journals, not specifications: they are read as registries and they
   behave as logs.
3. The two `figures/README.md` files score 19 and 18 inbound while holding ~15 marker hits each —
   heavily referenced and visibly stale at the same time.
4. `docs/OUTLINE.md` (5/12), `docs/HISTORY.md` (2/4) and `docs/architecture.md` (1/0) are the natural
   CORE candidates by intent and are almost uncited by the tree: the orientation layer is not wired in.

### Orphans

No inbound citation and no outbound citation: **6 files, 97,462 B.** Orphan is not a verdict — a leaf
record (a preregistration, a review) can be an orphan because nothing needed to point at it. It does mean
nothing in the tree depends on these files, so moving or deleting one cannot break a citation.

| path | bytes | mtime | what it is |
|---|---:|---|---|
| `docs/design/d583_straight_guide_preregistration.md` | 38,608 | 2026-10-29 22:50 | D58.3 straight-guide preregistration (ORPHAN: nothing cites it, it cites nothing) |
| `docs/design/nedelec_solver_review.md` | 31,142 | 2026-10-31 16:50 | theory-engineer review of the Nedelec solver (ORPHAN, 31 kB) |
| `docs/design/e13_antenna_scope.md` | 15,291 | 2026-11-13 23:42 | E13 antenna work: scope only (ORPHAN) |
| `docs/prereg/d585_h_ladder.md` | 4,536 | 2026-10-30 00:33 | D58.5 H-ladder preregistration (ORPHAN; only file in docs/prereg/) |
| `docs/design/flux_projection_verification_2026-11-03.md` | 4,371 | 2026-11-03 14:18 | current-channel renormaliser verification, sign hazard found before code (ORPHAN) |
| `docs/design/3d_ntff_te_query.md` | 3,514 | 2026-11-14 02:42 | open enquiry: TE query for the 3-D NTFF far-field transform (ORPHAN) |

### Dangling citations

Citation-shaped tokens that resolve to **no file on disk** from the citing file's directory, `docs/`,
or the repo root: **1010 hits / 313 distinct tokens.**

| class | hits | distinct tokens | reading |
|---|---:|---:|---|
| doc (`.md`/`.tex`) | 251 | 84 | a reader following the reference finds nothing |
| figure (`.png`/`.pdf`/`.gif`) | 14 | 12 | an image referenced by a document that is not in the tree |
| artefact (`.json`/`.txt`/`.npz` …) | 745 | 217 | an evidence dump or scratch output cited but never committed |

**Doc-class, tokens with 2+ hits** (84 distinct doc-class tokens in total; the other 60 occur once each):

| token | hits | first example |
|---|---:|---|
| `PREREG.md` | 48 | `docs/design/E11_residual_preregistration.md:112` |
| `SUMMARY.md` | 24 | `docs/design/E11_residual_preregistration.md:113` |
| `ERRATA_004.md` | 17 | `docs/design/dispatch_log_archive_2026-Q4.md:31` |
| `ERRATA_003.md` | 11 | `docs/design/d58_13_strip_width_decisions_block.md:302` |
| `NOTE.md` | 9 | `docs/design/GEN12_HANDOFF_STATE.md:164` |
| `docs/defect_register.md` | 8 | `docs/design/GEN12_HANDOFF_STATE.md:253` |
| `README_mode_profile.md` | 5 | `docs/design/component_map.md:30` |
| `main.tex` | 5 | `docs/roadmap.md:323` |
| `thoughtmachine/knowledge/personal/lessons_learned.md` | 5 | `docs/design/defect_register.md:903` |
| `_decisions_block.md` | 4 | `docs/design/d58_13_strip_width_decisions_block.md:4` |
| `d80_96.md` | 4 | `docs/design/absorbing_termination_scope.md:308` |
| `d94_96.md` | 4 | `docs/design/absorbing_termination_scope.md:308` |
| `docs/design/decisions.md` | 4 | `docs/design/57c_acceptance.md:16` |
| `rung_c_errata/ERRATA_001.md` | 4 | `docs/design/dispatch_log_archive_2026-Q4.md:31` |
| `ERRATA_001.md` | 3 | `docs/design/dispatch_log_archive_2026-Q4.md:29` |
| `ERRATA_002.md` | 3 | `docs/design/dispatch_log.md:143` |
| `_acceptance.md` | 3 | `docs/design/component_map.md:97` |
| `lessons_learned_orchestration.md` | 3 | `docs/design/session_close_gen8.md:59` |
| `scratch/d47/number_sheet.md` | 3 | `docs/design/d47_results.md:43` |
| `scratch/dispatch41_task2_prereg.md` | 3 | `docs/design/d52b_claim_inventory.md:135` |
| `strip_width/ERRATA_001.md` | 3 | `docs/design/dispatch_log_archive_2026-Q4.md:31` |
| `EM_SOLVER_LEDGER.md` | 2 | `docs/design/onboarding/03_KNOWN_BUGS.md:159` |
| `ERRATA_005.md` | 2 | `docs/design/dispatch_log_archive_2026-Q4.md:33` |
| `_preregistration.md` | 2 | `docs/design/d52b_acceptance.md:192` |
| `docs/design/preservation_gate_results_a15.md` | 2 | `docs/design/d51_acceptance.md:14` |
| `docs/design/theory_consultations.md` | 2 | `docs/design/dispatch_log_archive_2026-Q4.md:47` |
| `evidence/strip_width/ERRATA_00N.md` | 2 | `docs/design/d58_13_strip_width_decisions_block.md:165` |
| `lessons_learned.md` | 2 | `docs/design/dispatch_log.md:20` |
| `scratch/dispatch40_facts.md` | 2 | `docs/design/d43b_extraction_audit.md:175` |
| `scratch/r1_writeup.md` | 2 | `docs/design/beta_dispersion_comparison_2026-11-07.md:72` |
| `sec_energy.tex` | 2 | `docs/design/latex_structure.md:38` |
| `sec_modes.tex` | 2 | `docs/figures/README.md:7` |
| `strip_width/ERRATA_002.md` | 2 | `docs/design/dispatch_log_archive_2026-Q4.md:31` |
| `thoughtmachine/gen12_factsheet.md` | 2 | `docs/design/defect_register.md:903` |
| `thoughtmachine/knowledge/personal/task_tracker.md` | 2 | `docs/design/dispatch_log_archive_2026-Q4.md:37` |
| `workspace/decisions.md` | 2 | `docs/design/d52_acceptance.md:114` |

The doc-class list is dominated by three shapes, and only the first is a plain broken link:

* **Uncommitted evidence trees.** `PREREG.md` ×48 — e.g.
  `docs/design/E11_residual_preregistration.md:112` cites `evidence/strip_width/…/PREREG.md` and the whole
  `evidence/strip_width/` directory is absent. `SUMMARY.md` ×24, `ERRATA_004.md` ×17, `ERRATA_003.md`×11,
  `NOTE.md` ×9 are the same failure: the docs route a reader into evidence that was never committed.
* **Mis-pathed internal links.** `docs/defect_register.md` ×8 — the real file is
  `docs/design/defect_register.md`, i.e. the link omits the folder. `docs/design/decisions.md` ×4
  (the real decision log is `decisions.md` at the repo root).
* **References outside `docs/`.** `thoughtmachine/knowledge/personal/lessons_learned.md` ×5,
  `workspace/decisions.md`, `scratch/d47/number_sheet.md` ×3 — citations to paths that only existed in the
  authoring environment.

**Artefact-class by leading directory of the token:**

| prefix | hits |
|---|---:|
| `(bare filename)` | 564 |
| `scratch/` | 118 |
| `out/` | 29 |
| `evidence/` | 7 |
| `artifacts/` | 5 |
| `tmp/` | 5 |
| `smoke_A/` | 2 |
| `board_poc/` | 2 |
| `out_mesh/` | 2 |
| `amend1/` | 2 |

564 bare filenames plus 118 under `scratch/`, 29 under `out/`, 7 under `evidence/`, 5 under `artifacts/`,
5 under `tmp/`: the documentation references run outputs that were never committed. This is the largest
of the three classes by an order of magnitude and it is a property of the workflow, not of any one file.

**Figure-class** (12 distinct): `figures/NAME.png` ×2, `rcs-pattern.png` ×2, `abc_duct.png` ×1, `cavity_field_z.png` ×1, `energy_drift.png` ×1, `ez_3d_station4.png` ×1, `ez_envelope.png` ×1, `ez_slice_station4.png` ×1, `main.pdf` ×1, `rectification_D.png` ×1, `scatter-sequence.png` ×1, `scatter-snapshot.png` ×1.

Totals for the chunk-3 worksheets: 251 doc-class hits / 84 tokens, 14 figure-class / 12, 745
artefact-class / 217.

<!-- generated by KB audit chunk 1; sources: filesystem walk + greps; mtime used as last-touch proxy except where last_commit is filled -->
