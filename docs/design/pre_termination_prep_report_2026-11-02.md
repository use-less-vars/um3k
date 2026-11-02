# Pre-termination prep - report (2026-11-02)

Dispatch `pre-termination-prep-2026-11-02`, run as three workers plus independent verification passes. **Nothing is committed and nothing is staged.** Two deliverables were written, one was written and then disputed (D2), one code change sits in the working tree, and one task (Q4) turned out to be already done in HEAD.

## 1. Delivered

| # | file | lines | bytes | status |
|---|---|---|---|---|
| D1 | `docs/design/strip_termination_design_2026-11-02.md` | 81 | 8973 | untracked |
| D2 | `docs/design/closed_form_with_two_wave_beta_2026-11-02.md` | 66 | 10797 | untracked, conclusion amended 2026-11-02 (2.2 refuted the original; section 4 replaced) |
| D3 | `docs/design/ac4_wiring_scope_2026-11-02.md` | 137 | 9007 | untracked |
| D4 | `evidence/termination/run_build_A.py` | +37/-0 net | - | modified, unstaged, `py_compile` OK |
| D4 | `tests/test_studies.py` | +141/-0 | - | modified, unstaged, 3 tests pass |
| D5 | - | - | - | not run, reason in 4 |

All four are inside the 150-line budget. Nothing under `emfit/` is modified; no pre-existing artefact JSON is modified.

## 2. Key findings

### 2.1 D1 - the strip fix is two tokens, one new local, one guard

The strip is built at `emfit/studies.py:2706` (`x_cells = np.arange(ix_port, nx)`) and `:2709` (`x_points = np.arange(ix_port, nx + 1)`), stamped at `:2712` (`pec |= strip`). The cited range `studies.py:2704-2712` is **verified correct**. `studies.py` contains **no occurrence of `nx - n_pml`**, and `inside_xmax_pml` lives only in `evidence/termination/run_build_A.py`, not in the solver.

The fix is `nx` to `nx_clean` on those two lines plus one new line defining `nx_clean = nx - n_pml`, one hunk `@@ -2703,9 +2703,10 @@`. `ex` needs `nx_clean` and `ey` needs `nx_clean + 1` because one is cell-indexed and the other node-indexed; moving only one opens a one-cell slot line in the PEC. Only one existing guard must change: `:2728` (`if not ix_port < ix_load < nx:`) becomes `nx_clean`, and a new downstream cap guard belongs beside `:2793-2801`. `_slice_index` (`:3680`, called `:2695`) is z-only and untouched. Every `ix_extract` consumer (`:2904-2907`, `:2965-2967`, `:3324`, `:3332`, `:3604`, `:3608`, `:3669`) takes the index as given, so **the fix needs no change outside `2680-2810`** - the STOP condition in the brief did not fire.

### 2.2 D2 - the closed form is fitted, not validated, and the wall verdict is not supported

The note reproduces the required sanity check exactly: arm D at L = 12 cells, `beta_model`, Z0 = 47.53662 gives **0.75934209** against the target 0.7593421 (delta -9.7e-9). Every handed figure for arm A was confirmed from the JSON leaf: nx 72, load column 50, `beta_two_wave` 231.55331672912826, `line.beta` 286.35930483082825, `beta_model` 223.35306683909533, `s21.magnitude` 0.7628473102840976, `s11.magnitude` 0.32556486641109117.

| arm | L variant | beta variant | predicted | measured | rel error |
|---|---|---|---|---|---|
| A | wall, 22 cells (8.80 mm) | beta_model | 0.8234808 | 0.7628473 | +7.948 % |
| A | wall, 22 cells | beta_two_wave | 0.7784291 | 0.7628473 | +2.043 % |
| A | PML front, 16 cells (6.40 mm) | beta_model | 0.9695966 | 0.7628473 | +27.102 % |
| A | PML front, 16 cells | beta_two_wave | 0.9875963 | 0.7628473 | +29.462 % |
| D | wall, 12 cells (4.80 mm) | beta_model | 0.7593421 | 0.7600910 | **-0.098 %** |
| D | wall, 12 cells | beta_two_wave (proxy) | 0.7830278 | 0.7600910 | +3.018 % |
| D | PML front, 6 cells (2.40 mm) | beta_model | 0.5445227 | 0.7600910 | -28.361 % |
| D | PML front, 6 cells | beta_two_wave (proxy) | 0.5491054 | 0.7600910 | -27.758 % |
| A | wall, 22 cells | line.beta 286.359305 | 0.5660185 | 0.7628473 | -25.802 % |
| D | wall, 12 cells | line.beta 286.868689 | 0.9452945 | 0.7600910 | +24.366 % |

Z0 = 47.53662 throughout, stated in the note. Sensitivity so the substitution is not smuggled: with D's own |z0| = 45.670215 the D/wall/12 row moves to 0.7505703 (-1.253 %); with A's |z0| = 45.258611, A/wall/22 moves to 0.8162189 (+6.996 %). No conclusion inverts.

**The note's conclusion - that the data select the wall - is NOT supported and must not be carried forward as a finding.** Its own table refutes it. Arm A has L = 22 to the wall and arm D has L = 12, an 8.3 % difference in predicted |s21| (0.8235 against 0.7593), yet the two arms **measure the same value**: 0.7628473 and 0.7600910, 0.36 % apart. A model that predicts 8.3 % and observes 0.36 % is not selecting anything. The -0.098 % on D is a single-point coincidence of L; the same model form is 7.9 % out on A at the same beta and the same nominal cross-section. The correct statement is the weaker one: **the closed form's L-dependence is absent from the data, so the wall-versus-PML question stays open until the structure is terminated** - which is dispatch 2, and which the note's own implication section already allows as the alternative reading.

The sweep cross-check is sound and lands plainly: the closed form predicts a **single, N-independent** number for a fixed L (flat 0.8234808), while the measured series falls 3.3 % across planes 51-59; feeding L = N - 50 makes the prediction **rise 28 %** as the measurement falls. The closed form cannot trace the sweep, and the note says so.

### 2.3 D3 - no Gamma arithmetic is false; the grader has a Gamma model and no Gamma measurement

The AC-4 block is at `evidence/termination/grade_2b.py:326-341` (`bar_source` `:333`, `achieved` `:334` = None, `pass` `:335` = None, `closable_in_run_a` `:336` = False, status `:337-340`). Gamma arithmetic **does** exist: `:493` computes `gamma_model = abs(100.0 - zc) / (100.0 + zc)`, published with its basis at `:503-504`; `GAMMA_REL_TOL` is at `:46` and its only consumer is the `:561` echo. So the prior row's claim that there is no Gamma arithmetic in the grader at all is **false in the model half**; the accurate form is **a Gamma model and no Gamma measurement**. The value is hardcoded to R = 100 and never compared to an achieved Gamma.

Two independent reasons the pass bit must stay unwired. (a) Today n_unmatched = 1: at the arm's own zc the terminating form puts R = 50 inside tolerance, so both 50-ohm arms read matched and only R = 100 at 0.359440 is unmatched - AC-4 needs two. (b) The bar cannot pass a correct answer: the 3 % tolerance is **narrower than the A-versus-E spread on the same 50-ohm load, which is 9.6 %**, and the two candidate model forms differ by 43.2 % at R = 100, 14x the tolerance. The same DR-16 argument applies - a pass bit that cannot be exercised is a prohibition, not a safety check.

For the achieved Gamma the note selects `s11.magnitude` (`run_build_A.py:1458`) and rejects two alternatives with numbers: `s11_at_plane.magnitude` (`:1485`) has a floor of 0.0463-0.0490 across R = 25/50/100/200 and reads 0.049 against 0.355 on the same load, so it measures the plane rather than the load and would put E within 2.4 % of the series model - a pass for the wrong reason; `magnitude_one_wave_station_fit` (`:1459`) is 25-29 % low with beta biased +27 to +36 %.

### 2.4 D4 - Q3 landed; Q4 was already in HEAD

Q3 is real and additive: `run_reference` at `run_build_A.py:497-525`, one call site at `:1353`, which is after the single assignment of `loaded_kwargs` at `:1200` (verified by AST, not by eye). Exactly one new key, `run.reference`, six unsuffixed leaves, `None` when no reference. No existing key or line altered, `py_compile` clean.

**Q4 needed no work.** `s21.deembed_distance_m` already exists in HEAD at `run_build_A.py:1453`, null-guarded; `s11.deembed_distance_m` is at `:1461` and is **not** guarded, so a None `deembed_distance` would raise `TypeError` there - unreachable only because the attribute is always a float. The real asymmetry is the reverse of the one the brief assumed: s21 is the safe one. The direction to fix later is s11, not s21.

Tests: 141 lines appended after `:1664` as class `TestAc4ReferenceAndDeembedWriterFields`, three methods, **3 passed / 39 deselected in 4.10 s**; each also passes standalone by node id. The whole file was not run. **Caveat: the tests do not exercise the writer end-to-end** - one tests the helper, two test the upstream `deembed_distance` attribute; no test reads the emitted `run.reference` or `s21.deembed_distance_m` key from a produced artefact.

## 3. D4 diff status

Unstaged in the working tree, both files, no branch, no git write of any kind, `py_compile` OK, 3 new tests pass. **Not committed - owner approval is outstanding.** Its limit: `run.reference` is `None` on every artefact that exists today, because no arm supplies a reference, so the new field cannot be validated against a banked file.

## 4. D5 result

**Not run, and it is redundant.** A load-free reference for this exact geometry is already banked: `build_A_50ohm_twin_p51_twin.json` and `build_A_50ohm_v3c_twin.json` are nx = 72, `line.beta` 231.087, `s21.magnitude` 0.997965, z0 49.426 + 16.3328j. The new `beta_two_wave` 231.5533 sits **0.20 %** above that reference, which confirms the dispatch-1 claim from a second artefact. Spending two solves in a 0.5-core container to record a number that is already on disk, for a geometry that dispatch 2 is about to invalidate, is not worth the reap risk.

## 5. STOP conditions hit

None of the three fired as written. Two brief-level defects were found and reported instead of halted on:

- **The five sweep numbers were attributed to the wrong file series.** 0.762847 / 0.751789 / 0.746155 / 0.741876 / 0.737832 are `build_A_50ohm_sweepN51..59` (nx = 72) and appear **nowhere** in `build_A_50ohm_v3b_c51..59` (nx = 62), whose values are 0.760091 / 0.748936 / 0.743462 / **0.668116** / **0.0546054**. Confirmed against every artefact.
- **The `v3b_c57` and `v3b_c59` rows are unusable, and that is a real finding.** On nx = 62 with n_pml = 6 the clean boundary is plane 55, so planes 57 and 59 extract **inside the PML** - 0.668 and 0.0546 are not transmission through a stub, they are a field being absorbed. Any five-point sweep taken from the `v3b_c` series is three points of physics and two points of PML.

## 6. Surprises

1. **The same solve is banked under three names.** `build_A_50ohm_p51_noref.json`, `build_A_50ohm_sweepN51.json` and `build_A_50ohm_through_p51.json` are field-identical (0.762847, 0.0337934, beta 286.359). `build_A_50ohm_v3_beta2wave.json` reproduces the same s21 to the digit, which is a clean determinism check - but it also means the dispatch-1 run is one solve wearing four filenames, not four independent samples.
2. **`line.beta_two_wave` exists in exactly one artefact out of 38.** The data gap named in the previous closeout is now closed for one arm and open for every other, and no two-wave beta can be read from the twins - which are precisely the load-free records that define the reference.
3. **`s11_at_plane` is absent from 20 of 38 artefacts, and in the older ones the at-plane value is stored under `s11` instead.** `s11.magnitude` therefore means three different quantities across the file set; a grader reading it across a mixed set compares them silently. This is a live hazard for the AC-4 wiring, not a historical curiosity.
4. **`s21_plane_requested` is the string `"cut"` in five files** (`cal`, `B_v3c`, `B_v3d`, `E_v3c`, `E_v3d`) and `null` in every twin. A grader that does arithmetic on that field will fail on four of the five.
5. **`geometry.loads` is absent from 20 of 38 files** (everything pre-v3c), so the load column cannot be read from those arms at all. Where it is present the column is **not constant**: 50 for A (nx = 72) and B (nx = 62), **75 for E** (nx = 87). Any load-column constant in a grader is wrong for E.
6. **Two of the session's own record entries are wrong, caught by this dispatch.** The AC-4 grading stub was attributed to `run_build_A.py:862-866`; it lives in `evidence/termination/grade_2b.py:326-341`. And the claim that DR-17 is already reserved was an overstatement: no register entry exists - the number is only a **forward reference** in `session_open_gen7.md` section 2's decision table, cited as the defect that would open if AC-3 passes and AC-3b fails.

## 7. Owed before dispatch 2

- **Approve or revert the `run_build_A.py` Q3 edit** (verifier verdict: keep - additive, parses, tests pass, one call site after the assignment).
- **Decide the D2 wording.** As written the note concludes that the data select the wall; as shown in 2.2 that conclusion is refuted by its own table. Either the note is amended before commit or it is committed with the disputed paragraph struck.
- **Fix the dispatch row's item (D)** before it is pasted: the relative errors are 2.043 % and 7.948 %, not 1.9 % and 7.4 %, and the row should record that the fit is one point rather than a validation.
- **The DR-17 sentence.** No DR-17 is opened or reserved should read: no DR-17 is opened, and no register entry exists; the number is a forward reference in the Gen-7 decision table that has never been allocated. DR-18 is already committed for the AC-6 vacuity, so voiding 17 leaves a deliberate hole between 16 and 18 - acceptable, and preferable to renumbering a committed register entry.
