# Dispatch 58 -- Acceptance criteria: the component map, the state it assigns, and the staleness rule that keeps it checkable

**Written.** This file is the first action of dispatch 58, taken before any other artefact of it. At the moment of writing, `docs/design/component_map.md` does not exist (section 6, row 1: NOT-FOUND), and no inventory of this repository has ever been committed. Nothing below can therefore have been written backwards from a map.

**Status.** It is the front-most fence of dispatch 58. Nothing below it is negotiable: a later document may narrow a requirement here, but it may not widen one, and any narrowing lands as an appended reconciliation in this file rather than as a silent exception elsewhere.

**Coexists with.** `docs/design/d57_acceptance.md`, `docs/design/d54_acceptance.md` and their predecessors. This dispatch edits none of them and does not supersede any of them; where they and this file overlap, both stand and the stricter one governs.

## 0. What this file is, and the one place it refuses the house format

Every acceptance file in this line carries the same three things: a fence, a set of tasks stated so that a failure is observable, and a reconnaissance table that converts relayed claims into cited ones. This dispatch needs all three more than usual, because its subject -- "what is in this repository, and is it alive?" -- is the kind of question that invites prose in place of evidence. A component map whose entries cannot be falsified is a table of opinions, and an opinion about whether a module is "active" is exactly what a later reader will rely on instead of looking.

**The departure, and it is deliberate.** House format cites code as `path:line` (d54 does it throughout, and its reconnaissance table is a column of line numbers). The brief for dispatch 58 forbids line-number references to code. The two cannot both be obeyed, so this file takes the brief, and pays for it: **code is cited by path plus a symbol name plus a quoted token; documents are cited by path plus a section heading or a quoted token.** No line number appears anywhere in this file.

The cost is real and is not hidden. A reader cannot jump from a row here to a line in the tree. The benefit is that every citation in this file is a *grep*, and a grep survives a reformat, an insertion and a rebase, where a line number does not. It also happens to be the property the map itself will need: section 4's staleness rule is checkable only if rows carry greppable anchors, so this file is written in the same discipline it demands of the map. Where a citation here is weaker than a line number would have been -- the seven-term sweep in Task 1 is a count and a quote, not an exhaustive list -- the row says so.

**Three tags.** **CONFIRMED** means the tree says it and the token is quoted here; it is the only tag citable downstream. **CONTRADICTED** means two tree claims disagree; the file names the defective one and on what measurement, and an unresolved instance blocks the requirement it sits under. **NOT-FOUND** means the search was run and returned nothing; it is a claim about the search, not about the world, and it expires the moment a line is produced.

**Three provenances, which are this dispatch's addition.** Every repository claim below carries one. **MEASURED** -- a command was run this session and its output is the evidence. **READ** -- a file was opened and the token quoted. **RELAYED** -- the claim arrived in the brief, or in another document's prose, and was not independently re-measured; a RELAYED claim is not citable and does not enter the map as a state justification until a MEASURED or READ row replaces it. The distinction matters here more than in d54: a brief that says "the tools directory is a set of one-off probes" is a plausible sentence about a plausible repository, and two of the three top-level files under `tools/` turn out to say something sharper about themselves than the brief did.

## 1. Fences

1. **Writes.** This dispatch writes three files and only three: `docs/design/d58_acceptance.md`, `docs/design/component_map.md`, `decisions.md`. Nothing under `emfit/`, `tools/`, `tests/`, `viz/` -- nor any webapp, demo, schema, example or evidence path -- is edited, added or deleted.
2. **No execution that changes anything.** The inventory is read-only: directory listings, `grep`, byte and line counts, and `git log` per path. No solver run, no gate run, no ladder, no test run performed for the purpose of the map. Nothing in `tools/host/**/out*/` is regenerated.
3. **`decisions.md` is append-only.** The d58 entry lands at the end. No earlier block is edited, reflowed or renumbered, and no figure already in it is corrected in place.
4. **Seven untracked files are not touched**: `d80_96.md`, `d94_96.md`, `docs/design/order_p_preregistration.md`, `docs/design/c2b_shapes.pdf`, `docs/design/c2b_shapes.png`, `docs/design/mispaired_metric_before.png`, `docs/report/figures/c2b_mode_shape_corrected.png`. They are not read as evidence either: three of them are duplicates of committed prose, and a duplicate is not a source.
5. **Nothing is tidied.**
6. **The map is frozen at first write.** After it exists, it changes only by an appended correction row that names the row it corrects and the commit that made it stale.
7. **Task 5 ends the dispatch.**
8. **No state without a quote.** A component may not be labelled ACTIVE, SHELVED, DESIGNED-ONLY, DEAD, UNLANDED or UNKNOWN on the strength of its name, its age, or the orchestrator's memory. Field (d) of every row carries the token that decides it.

The fifth fence is the one that bites. This repository contains, at the time of writing, a stale test-count in a runner header, a duplicated evidence report whose two copies differ, a harness that exists only inside a gitignored worktree backup, and a decisions log whose newest block is three dispatches old. Every one of those is a repair someone could make in a minute, and every one of them would then be invisible to the map, because a map records what the tree is, and a tidied tree is a tree whose defects have no witness. A repair is a separate dispatch with its own fence and its own commit message; this dispatch's contribution is the record that the defect existed at the HEAD it measured.

The eighth fence is the one that keeps the map honest, and it is stated as a prohibition rather than as advice because the failure mode is silent: a table of forty rows in which ten states are "probably active" reads exactly like a table in which all forty are evidenced.

## 2. Task 1 -- the inventory sweep, and the seven fields a row must carry

One pass, read-only, over: `emfit/`, `tools/`, `docs/design/`, `tests/`, `examples/`, `schemas/`, `evidence/`, the top-level directory, and the webapp and demo entry points. Per component, seven fields, all mandatory:

- **(a) name** -- the component as a reader would look for it.
- **(b) what it is** -- one sentence, and one sentence only.
- **(c) path and key symbol** -- the exact path, plus the symbol (or module docstring) that identifies the thing the row is about. A path alone does not identify a component in a 5,000-line module.
- **(d) state, with quoted evidence** -- one of the six labels in fence 8, plus the token. A state whose evidence is a bare assertion fails this criterion and is downgraded to UNKNOWN with the missing fact named.
- **(e) why** -- the reasoning that connects (d)'s token to (d)'s label.
- **(f) un-shelving condition, or the words "not stated"** -- a SHELVED or DESIGNED-ONLY row must say what would revive it. If no document says, the row says "not stated" and does not invent one. Inventing a revival condition is the most likely way for this map to become a plan instead of a record, which is why the field permits the word "not stated" explicitly.
- **(g) modification time and the last commit subject that touched the path** -- measured, not assumed.

**(g) is measured with `git log -1 --format=%s -- <path>` per path**, because the working tree carries no git binary and because a per-path subject is the only part of this field that can disagree with the tree in a way a reader can re-check. The mtime is recorded as measured in this checkout and is labelled as such: it is a property of a working copy, not of the repository, and a fresh clone will not reproduce it.

**The state vocabulary is defined here, before the sweep, so that the sweep cannot define it in hindsight.**

- **ACTIVE** -- something exercises it: a test, a front end, or the command line entry point imports it, and the last subject that touched it describes work on it rather than its retirement.
- **SHELVED** -- it exists and works, and a document says its result was stopped, superseded in standing, or weaker than a claim made about it, while the code remains in place.
- **DESIGNED-ONLY** -- prose, preregistration or a decision names it; no implementation token exists in the tree.
- **DEAD** -- superseded and unreferenced by any live path.
- **UNLANDED** -- present in the working tree with no committed blob.
- **UNKNOWN** -- the sweep could not decide, and the row names the fact that is missing. UNKNOWN is a legitimate outcome and a hedge is not.

Task 1 is not allowed to promote a claim because it is convenient. The `reports/` directory, for instance, is full of dated narrative that would settle several states in one sentence each; it is *prose about* the tree, so a row may cite it as RELAYED corroboration but never as its deciding token.

## 3. Task 2 -- the map's row contract, and the header that dates it

`docs/design/component_map.md` is written from Task 1's rows, and it carries:

1. A header naming the commit it was measured at, and the date, stated as "measured at HEAD = <subject>, <date>". A map without this line cannot be audited for staleness as a whole, only row by row.
2. The seven fields of section 2 for every component, in the same order, one row per component, grouped by the directory the component lives in.
3. A section of FINDINGS -- defects, duplications, contradictions and absences discovered by the sweep, stated as findings. Findings are not repaired (fence 5) and are not softened: a finding that names a defect names the file, the token, and what would be true if the defect were not there.
4. An explicit statement of what the sweep did **not** cover. A map that implies completeness it does not have is worse than a map with a stated hole.

**Scope is the map, not the repository.** The map is a map of components, not a line-by-line account of every artefact: `out/`, `temp/`, `.scratch/`, `.venv/`, `.tools/` and the figure caches are out of scope as components and appear only where a finding requires them (the unlanded harness does). This sentence exists so that a later reader cannot read an omission as a denial that the thing exists.

## 4. Task 3 -- the staleness mechanism, which must not be a calendar

This is the requirement most likely to be satisfied on paper and violated in practice, so it is stated as a decision procedure with a named failure mode.

**The failure mode, named first.** A map with "reviewed: <date>" and a six-month cadence is a map that is *believed* for five months and *known to be false* for one, and in practice believed for all six. A review cadence is also unenforceable in this repository, whose only scheduling mechanism is a dispatch, and dispatches are not periodic.

**The mechanism.** Staleness is a computable property of a row, not a judgement about a row:

- **S1.** Every row records `path` and `last_commit_subject`, the latter measured at authoring time with `git log -1 --format=%s -- <path>`.
- **S2.** The map header records the HEAD commit it was measured at (section 3.1).
- **S3.** **A row is stale by definition** if, at the moment it is read, `git log -1 --format=%s -- <path>` differs from the recorded subject, or if `<path>` no longer exists. No reviewer, no threshold, no opinion: the comparison either matches or it does not.
- **S4.** Whole-map staleness is the count of rows satisfying S3. It is one command per row and it is scriptable; it requires no cache, no state file and no schema.
- **S5.** **There is no review cadence, and none may be added later.** The trigger for re-measurement is an event: a dispatch that touches a mapped path re-measures the rows for the paths it touches, and a reader who needs a row and finds it stale under S3 has the option of re-measuring that row rather than trusting it. The map is invalidated by commits and it says so itself; it is not maintained by anyone's memory of having maintained it.
- **S6.** The mechanism must be decidable **without re-reading the code**. If deciding a row's freshness requires opening the module and forming an opinion, the mechanism has failed and the row's field (d) was too weak to begin with. This is why field (c) requires a symbol and field (d) requires a token: they are the two things S3 cannot supply and a reader can.
- **S7.** Every row carries a **greppable anchor**: the quoted token from field (d), reproduced verbatim. S7 covers the case S3 cannot -- a history rewrite, rebase or amend that changes the commit graph while leaving the file text alone, where the subject matches and the file no longer does.

**Falsification of the mechanism, which is part of the deliverable.** The map must fail this test visibly if it is wrong: run S3 across all rows and check the header's "measured at HEAD" claim against the tree. If any row is stale at the moment of writing, the map is wrong and the acceptance file is where that gets said. The mechanism is accepted only if it is *demonstrated* on the map at least once -- one row re-measured, with the before and after subjects shown -- because a decision procedure described but never run is a paragraph, not a mechanism.

**What the mechanism does not claim.** It does not detect a component that has become ACTIVE while its path is untouched (a new front end importing it). That is a real gap and it is stated in the map's scope note rather than papered over: S3 detects edits to the thing described, not changes to the things that use it.

## 5. Task 4 -- the `decisions.md` entry, and what it may not contain

The entry is appended, dated, and says four things and no more:

1. That `docs/design/component_map.md` exists, what it covers, and the commit it was measured at.
2. The state assignments that could reasonably be disputed, with the quoted token that decides each. A map is only as good as its contested rows; the uncontested ones need no argument here.
3. The findings, listed as findings, with an explicit sentence that none of them was repaired (fence 5).
4. The staleness mechanism in one paragraph, with S3 quoted, so that a reader who never opens the map knows what makes it wrong.

It may not contain a plan. An entry that says what dispatch 59 *should* do with the findings converts a record into a backlog, and the next reader will not be able to tell which rows were measured and which were hoped for.

## 6. Reconnaissance table

Every row was established this session. Provenance is as defined in section 0.

| # | fact | citation | tag | provenance |
|---|---|---|---|---|
| 1 | no component map exists anywhere in the design directory | `docs/design/` listing contains no `component_map.md`; a case-sensitive grep for the string `component_map` across every `*.md` in the tree returns nothing | NOT-FOUND | MEASURED |
| 2 | the predecessor's task list forbids a task committing its own work | `docs/design/d57_acceptance.md`, section "Execution": "Only the orchestrator commits; no task stages or commits its own work." | CONFIRMED | READ |
| 3 | `decisions.md`'s newest block is three dispatches old | last heading in `decisions.md` is `## D54 ERRATA — p2 and contrast (dispatch 54)`; grep for `Dispatch 5[5-9]` and `dispatch 5[5-9]` returns no hit | CONFIRMED (absence) | MEASURED |
| 4 | the test runner's own header undercounts the suite | `tools/host/run-tests/run.sh` header: "#   The full suite (483 tests, 39 files) takes ~12 min."; `ls tests/test_*.py | wc -l` returns 42 | CONTRADICTED -- the header is defective | MEASURED |
| 5 | the suite is 42 files, flat, no subdirectories but `__pycache__` | `ls tests` | CONFIRMED | MEASURED |
| 6 | `emfit/` is 32 top-level modules | `find emfit -maxdepth 1 -name '*.py'` | CONFIRMED | MEASURED |
| 7 | the settledness tolerance is a module constant, not a magic number | `emfit/studies.py`, literal `MS_SETTLE_TOL = 0.01`, read by `tests/test_studies.py::test_microstrip_unsettled_record_is_labelled_not_reported` | CONFIRMED | READ |
| 8 | the deflation smoke declares itself non-evidence | `tools/host/deflation-smoke/smoke_deflated.py` docstring: "DEVELOPMENT ARTEFACT - plumbing check only, not a result." | CONFIRMED | READ |
| 9 | the mode solver line is closed by its own status document | `docs/design/m3c_gate_v2.md`, text "mode solver CLOSED" | CONFIRMED | READ |
| 10 | an m3b rung-8 harness exists in the tree and nothing committed answers to it | `.scratch/wt-m3b-diag/tools/host/m3b-rung8/run_m3b_test.py`; no committed counterpart (grep for `m3b-rung8` outside `.scratch` returns nothing) | CONFIRMED | MEASURED |
| 11 | the rung-4 evidence report exists twice and the copies differ | `evidence/t4/rung4_routeC_report.json` (14337 B, md5 `fdc3e2c...`) and `tools/host/sparse-probe/out_rung4/rung4_routeC_report.json` (14344 B, md5 `a477db2...`); the second has **no commit** (`git log` per path returns nothing) | CONFIRMED | MEASURED |
| 12 | the harness's own policy makes the `evidence/` copy the citable one | `tools/host/sparse-probe/.gitignore`: "The small text artefacts that make a result checkable are copied into evidence/ instead, so a checkout carries the provenance and not the binaries." | CONFIRMED | READ |
| 13 | `warmup` appears in the committed tree in one harness and nowhere else | `tools/host/m3a-smoke/board_run_cw_poynting.py`: `self._warmup_seen = False`, `mark("warmup")` | CONFIRMED | MEASURED |
| 14 | the log forbids the settledness claim in any tense | `decisions.md` section 73: "`M3a passed a settling check` is therefore not available to this log, in any tense and under any hedge." | CONFIRMED | READ |
| 15 | a soft source is documented as a launcher with an impedance, not a terminator | `emfit/modalport.py` docstring: "``inject`` writes a **soft source** on the profile.  It does not terminate the"; `docs/report/sec_howitworks.tex`: "a soft source has an impedance, and it does not absorb what" | CONFIRMED | READ |
| 16 | the board generator computes a clearance envelope | `kicad_support_project/generate_board.py`: `def envelope_width(x: float, pads) -> float:` | CONFIRMED | READ |
| 17 | `kicad_support_project` is duplicated into a gitignored worktree | top-level `kicad_support_project/` and `.scratch/wt-m3b-diag/kicad_support_project/` | CONFIRMED | MEASURED |
| 18 | the warm-up drive is a linear ramp in the studies code | `emfit/studies.py`: `ramp = min(1.0, (n + 1) / max(n_warm, 1))` | CONFIRMED | READ |
| 19 | the method forbids correcting a transient rather than discarding it | `docs/report/sec_method.tex`: `\subsection{Transients get a discard window, not a correction}` | CONFIRMED | READ |
| 20 | there is no runnable script at the repository root | `find . -maxdepth 1 -name '*.py'` returns 0 files; the root holds logs, documents and configuration only | CONFIRMED | MEASURED |
| 21 | the three top-level `tools/` scripts describe themselves as non-solves | `tools/destagger_ratio_101_20.py`: "READ-ONLY.  This script writes NO file"; `tools/corr_ez_101_20.py`: "Diagnosis only."; `tools/gates_101_20.py`: "RUNNABLE TODAY (no solve)" | CONFIRMED | READ |
| 22 | the seven-term sweep is a count per term over a stated include-set, not an exhaustive list | counts exclude `.scratch/`, `.tools/`, `.venv/` and `__pycache__`: `warmup` 5, `settling` 29, `settle` 276, `envelope` 52, `transient` 67, `ramp` 60, `soft source` 16 | CONFIRMED | MEASURED |
| 23 | the untracked-file list is exactly seven | `git status` on the working tree; seven paths, of which three are duplicate prose and four are images or PDFs | CONFIRMED | MEASURED |

Rows 4 and 11 are the two that argue for the sweep existing. Row 4 is a claim inside the tree about the tree, and it is wrong; row 11 is a duplication whose two copies differ by seven bytes and of which only one is committed. Neither is discoverable from a document, both are discovered in minutes from a listing, which is the whole case for a measured map over a remembered one.

## 7. Where the tree departs from what the brief implies

Recorded here rather than silently absorbed, in the manner of d54's section 7.

1. **The brief's own file count is wrong in the same direction as the runner's header.** The brief for this dispatch relayed 41 test files; the measurement is 42. The runner header says 39. Three different numbers for a quantity that one command settles, which is a fact about how the number travels rather than about the suite.
2. **`decisions.md` has no entry for dispatch 55, 56 or 57.** Its newest block is the dispatch 54 errata. This dispatch appends, so it does not repair the gap; a reader looking for what 55A and 57 decided will not find it there, and the map says so instead of implying a continuous record.
3. **The top-level `tools/` scripts are sharper about their own status than the brief was.** The brief described them as one-off diagnostics; two of the three state in their own docstrings that they run no solve and write no file. A description that is less precise than the artefact is a description that will be quoted instead of the artefact, which is why field (d) exists.
4. **An unlanded harness sits in a gitignored worktree and answers to a milestone label.** `m3b-rung8` has no committed file. Any map that enumerated the tree by directory would have counted `.scratch` as noise and lost it; the row exists because the sweep's scope note was written before the sweep.
5. **Two copies of the same-named evidence artefact, differing by seven bytes, one untracked.** The seven bytes are not the point; the point is that "the report" is not a single object in this tree, and a citation that says only "the rung-4 report" is ambiguous until it names a path.
6. **The map's own honest hole.** S3 does not detect a component whose users changed while its own path did not. That is stated in the map's scope note, not in a footnote, because the first reader to notice it will otherwise assume it was overlooked.

## 8. What done means

1. This file exists, unedited since its first write except by appended reconciliation.
2. `docs/design/component_map.md` exists, carries the measured-at-HEAD header, and gives the seven fields of section 2 for every component in its stated scope.
3. Every state in it is one of the six labels and carries a quoted token; no row is ACTIVE, SHELVED or DESIGNED-ONLY on assertion alone.
4. Every SHELVED and DESIGNED-ONLY row carries an un-shelving condition or the words "not stated".
5. The staleness mechanism is present, quotes S3, adds no calendar, and has been demonstrated once on a real row with the before and after subjects shown.
6. The map carries a FINDINGS section and a scope-and-holes section, and fence 5 holds: the diff of this dispatch touches exactly three paths.
7. `decisions.md` carries an appended d58 entry with the four contents of section 5 and no plan.
8. A close-out sentence states, explicitly, whether any finding was repaired. If none was, it says none was.

## 9. Provenance

This file was written on dispatch 58, before any other artefact of dispatch 58 existed, and it is not edited afterwards except by an appended reconciliation that names what it changes and why. Section 6 is the part that makes the rest auditable: a state in the map whose deciding token is not a row there, or a row here, is a relayed state and is not citable, whatever its confidence.

Section 0's departure from house format is the one thing in this file that a later reader should re-examine if a citation below proves impossible to follow. It was taken deliberately, for the reason given there, and it is recorded here rather than buried so that the choice is auditable instead of merely inherited.

This file gates dispatch 58 in the same way that `docs/design/d57_acceptance.md` and its predecessors gated theirs.
