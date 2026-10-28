# Acceptance addendum: what Dispatch 45 delivers, and what it does not

## Status

**New document.** Authored at Dispatch 45, Task 1, and written before any other file was touched in that dispatch. It is the artefact the Dispatch 45 entry in `decisions.md` declares, and it is the contract against which that entry is read.

**One task executed, one task specified.** Task 1 is executed, and its three items are stated in section 2. Task 2 is specified in sections 3 to 5 and is not executed: at the close of Task 1 there is no anchor pre-registration, no code under `tools/host/anchor/`, and no anchor run. Specifying Task 2 here is not authorising it in this task, and nothing below may be cited as though a run had happened.

**No C++ and no solver change.** No `.cpp`, no header and no build is added anywhere in this dispatch. Nothing under `emfit/` is modified in Task 1.

**Citation discipline.** No citation in this document is a line number. Each resolves by content: a function or identifier name, a section heading, a table, or a filename. The reason is that line numbers drift when a document is edited, and this tree has already paid for that once.

## 1. The fences

1. **No edits under `emfit/` in Task 1.** The normalisation defect in the mixed path is ruled on, not fixed, and section 2 of the ledger entry states why the fix is deferred rather than taken now.
2. **No C++ implementation anywhere in this dispatch.** The port stays parked. See the forward pointer of the Dispatch 45 ledger entry.
3. **`decisions.md` is append only, one block per task.** Each append proves its prefix by hash immediately before and immediately after, and no block edits an earlier one.
4. **Two tasks, two commits, sequential.** Task 2 begins after Task 1's commit exists, and Task 2 ends the dispatch.
5. **Task C and Task D from earlier are not started.** They are not named, not scoped and not implied by anything here.
6. **No line numbers in any brief or artefact.** Every citation resolves by content.
7. **Provenance discipline.** Every number is tagged `[VERIFIED]`, `[RELAYED]` or `[USER]`. An untagged number is `[RELAYED]` and is checked before it is written down.

## 2. Task 1, the three items

1. **The normalisation ruling is appended to `decisions.md`.** The mode container's documented contract wins: the transverse field is normalised in the `B` inner product, as the container states. The mixed path's plain 2-norm normalisation is the defect. The invariant is not weakened to accommodate the path, and the refusal is itself the ruling. The same block records that the fix is a physics change rather than a bug fix, that it changes every scattering parameter the tool has produced, and that it therefore requires its own pre-registration and re-gating. It also records that the fourth row of the criterion table in `docs/design/cpp_solver_arch.md` is blocked behind that change.
2. **A B-orthogonality scope paragraph is added to `docs/design/physics_invariant_layer.md`, after verification and not before it.** The paragraph states the hypothesis, the degeneracy guard and what the guard has to test, the exclusion of defective pencils with its reason, whether the code's own pencil meets the symmetry hypothesis, and the route by which the claim was verified. A pointer is added from the passage in section 5 of that document that discusses row four, so the scope statement and the row cannot drift apart.
3. **The passivity withdrawal is recorded.** The result file carries no scattering-parameter keys, so the passivity figures are not citable as measured passivity. The rejection of that basis stands, and it rests on physical impossibility together with the divergence in `beta`. The withdrawal is conditional on the document currently presenting those figures as measured passivity, and the check is made before any edit to that file.

## 3. Task 2, the seven pre-registration sections, in order

Task 2 delivers three artefacts: `docs/design/anchor_preregistration.md`, written before any run; an implementation under `tools/host/anchor/`; and a results file. The pre-registration contains the seven sections below, in this order.

### 3.1 The geometry

A closed PEC box, parallel plates, partially filled with dielectric, fully specified. The mode family the solver's port corresponds to is identified by name. The argument is given for why the partially filled guide is the right canonical case and an open slab is not: the solver has PEC walls, and an open slab radiates, so it is not a case this solver can represent.

### 3.2 The analytic reference

The transcendental dispersion relation, stated. The root-finding method, named. The achieved precision of the reference root, which must be at least `1e-14` and computed independently of the finite element discretisation, with the root residual shown rather than asserted.

### 3.3 The expected order of accuracy

Derived from the element order and from the mixed formulation actually in use, with the derivation shown and the band pre-registered before any run. If the derivation is incomplete it is marked provisional rather than conventional.

### 3.4 Pass-fail criteria

An order band and an absolute error bound at the finest mesh, both falsifiable. A run that misses the band fails, and the failure is the finding. No band is moved after a run.

### 3.5 The spectrum, in order

The spectrum is compared in sequence and not only at the fundamental, with analytic counterparts matched by order. The reason is recorded: a basis change moves `beta`, and a swapped mode is invisible unless the spectrum is compared in sequence.

### 3.6 The negative control

A geometry perturbation that must move the answer. An anchor that passes unchanged when the geometry is perturbed is not connected to the solver.

### 3.7 What the anchor does not test

Stated explicitly, in the pre-registration, before any run.

## 4. The implementation requirements

1. The implementation calls the live reference solver. It does not mirror the solver's pencil by hand: a harness that re-derives the solver's own expression compares two copies of one convention, which is the harness defect the Dispatch 44 addendum records.
2. It sweeps at least three meshes and preferably four.
3. Per mesh it reports the mesh size, the computed `beta`, the analytic `beta`, the relative error, and the ratio of that error to the previous mesh's.
4. It reports the observed order against the pre-registered band, or reports a failure.
5. A mesh on which the residual guard fires is not a result and is not reported as a datum.
6. A failure is reported rather than tuned away. No threshold, mesh, band or comparison convention moves in response to a result.
7. **Deferred and named as future work.** Comparing the eigenvector profile against the analytic field. That is the second phase of the anchor and is out of scope for Task 2.

## 5. The close-out requirements

The dispatch closes with all of the following, recorded in the second ledger block:

1. The two commit SHAs.
2. The commands run.
3. The results table.
4. Whether the anchor passed or failed.
5. Any disagreement with the brief.
6. If it failed, what the failure means.

## 6. What this document does not decide

- It does not set the anchor's order band or error bound. Task 2 pre-registers both, before any run, and a band fixed after a number is seen is not a band.
- It does not perform the normalisation fix. The ruling is recorded and the fix is queued as its own gated physics change.
- It does not authorise the C++ port, and it sets no date for it.
- It does not reopen `T4b`, `T4c` or `T4_amp`, and it does not touch the errata in `docs/design/t4b_t4c_preregistration.md`.
- It does not authorise a run of anything. No anchor, no benchmark and no build is implied by this document having been written.
- It does not characterise the normalisation discrepancy as a solver defect in the sense of a wrong eigenvalue. What it rules is which contract governs the normalisation, not what the code's author intended.

## Provenance

`[VERIFIED]` means read directly from the named file during this session. `[RELAYED]` means carried from the Dispatch 45 brief or from another document without independent reading. Untagged statements are `[RELAYED]`.

- `[VERIFIED]` every statement in section 2 that describes what the Task 1 edit actually says, since each was written from the edit itself.
- `[VERIFIED]` the presence and wording of the normalisation discrepancy in `emfit/mode2d.py`, and the symmetry of the pencil the mixed path builds, both read from the file in this session and reported in section 2 of the Dispatch 45 ledger entry.
- `[VERIFIED]` the absence of scattering-parameter keys in the basis-comparison result file, checked by key name in this session.
- `[RELAYED]` every requirement in sections 3, 4 and 5. They are the Dispatch 45 brief's own text, restated, and no anchor artefact exists in the tree to check them against.
- `[RELAYED]` the passivity figure `2.0014`, the `5.46` per cent divergence in `beta`, and the free-edge and free-node counts of the basis-comparison mesh. They come from the Dispatch 44 addendum and from the result file, and they are quoted in the ledger entry rather than re-derived.
