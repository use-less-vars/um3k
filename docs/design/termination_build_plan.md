# Termination build 2a -- the implementation plan for the absorbing termination (A1 / A2 / A3)

**Status.** Plan only. No code was written, no solver run was performed, no gate was re-priced, no
number was moved, `PREREG.md` is untouched. Every figure below is either read out of the tree at
the line cited, quoted from a banked record, or marked as a ruling; one number is marked
`ESTIMATE` and one `UNVERIFIED` and neither is used as if it were measured.

**Provenance tags.** `[M]` read or measured in this tree (source, grep, or the one arithmetic
probe in §3); `[L]` quoted from the decision ledger or a banked evidence record; `[R]` a ruling,
convention or bar set by the owner or by the scoping document, not a measurement;
`[UNVERIFIED]` not checkable from the tree.

**The brief was checked before this plan was written.** Three claims were tested against the
artefacts and all three hold: the scoping document exists at 593 lines / 38,408 B and carries the
five disagreements (§2), the three edits A1/A2/A3 (§3, L116-156) and the seven pre-registered
criteria AC-1..AC-7 (§5, L222-275) exactly as the brief describes [M]; the two commits named in
the brief are the last two on the branch and they are the gen7 catalogue and the AC-7 pass over
this same document [M]; and the working tree is clean apart from the six untracked artefacts that
§6 (L308-311) keeps uncommitted [M]. **No contradiction was found, so the build proceeds** - the
report of that check is §4's call-site census, which is the one claim in the brief that had not
already been verified line by line.

---

1. **What this build delivers, and what it does not.** Three edits, one of them compositional, and
   nothing else - the scoping document's §3 (L118: *"Three edits, one of them compositional.
   Nothing else."*) [L]:
   - **A1** - build the load plane's conductance as a non-negative conductance per primal edge,
     in the same form as the conductivity (`emfit/materials.py:290-292`, `_sigma_diag`: *"Edge-wise
     conductance `sigma * A~_e / L_e` [S]"* [M]), and **add** it to the conductivity-derived vector
     that `m_sigma` already accepts (`emfit/evolve.py:92-96`) [M]. Addition, not a second material
     matrix: the object handed to the stepper is still one `(n_edges,)` diagonal.
   - **A2** - the plane is a transverse **cut**, not "somewhere convenient" (`decisions.md:421`)
     [L]. This is a precondition of R3, not a detail of it.
   - **A3** - S-parameters are extracted from the **same** plane that carries the load. This is a
     **replacement** of the two-half fit, not a repair of it: `decisions.md:433` says *"The fix is
     to replace the two-half fit with a single plane at the cut, not to repair the halves."* [L]
   It does **not** deliver: a matched source (`emfit/modalport.py:323` is a *soft source*, `:19`
   needs a reflection-free window) [M]; a new boundary condition (the PML at `emfit/pml.py` and
   the Mur boundary at `emfit/abc.py:149` stay where they are) [M]; a new material matrix; or any
   change to the mesh, the cell counts or the excitation. **Option B, an equivalent current
   source, is not an alternative to A1** - a matched terminator has to absorb incident energy
   while a source injects it (scope L143-149) [R].

2. **The code change, file by file - shape only, no line count claimed.** A1 is one construction
   function on the materials side, returning `sigma * A~_e / L_e` on the edge set of one
   transverse plane and zero elsewhere, handed to the **existing** `m_sigma` argument; nothing
   else writes that vector (risk 4, scope L381-386) [R]. A2 is one plane-selection parameter
   threaded through the study so that the plane is the cut and cannot be retyped at the call site
   [R]. A3 is one replacement extraction path - the load plane's index and the extraction plane's
   index are the same variable, which is what makes AC-6 (L260) a dictionary key rather than a
   reconciliation [R]. The scoping document's own estimate of size is *"One construction function,
   one plane-selection parameter threaded through the study, one replacement extraction path. This
   is an estimate of shape, not of effort"* (L154-156) [L] - and no line count is claimed here
   either.

3. **The stepper branch, measured rather than assumed.** AC-1 (L222) is the only silent failure
   mode in the change, and it turns on two facts that this plan checked directly rather than
   inferring. The constructor guards on `np.any(ms)` (`emfit/evolve.py:152`), so an **all-zero**
   vector is already dropped to `None`-equivalent and the lossless branch at `:197-198` is taken
   [M]. Reproduced as arithmetic, five lines against the logic at `:143-157` and `:197-200`, with
   `n = 4`, `dt = 1e-12`, `m_eps = 1.558e-14` [M]:

   | argument | `loss_den is None` | `m_sigma` stored | `e_out` from the same `e0`, `ce` |
   |---|---|---|---|
   | `m_sigma=None` | `True` | `None` | `[0.12573022, -0.13210486, 0.64042265, 0.10490012]` |
   | `m_sigma=np.zeros(4)` | `True` | `None` | `[0.12573022, -0.13210486, 0.64042265, 0.10490012]` |

   `np.array_equal` on the two outputs is `True`, `max|diff| = 0.0` [M]; numpy 2.5.4 [M]. The
   probe is arithmetic on the branch, not a solve: it reproduces the guard and the update
   expression and nothing else, and it does **not** stand in for AC-1's real requirement, which is
   that every number in the existing evidence set be unchanged **to the last stored digit**
   (L224-225) [R].

4. **Call-site census - the AC-1 exposure, and where it actually is.** Seventeen `FITStepper`
   constructions exist in the tree; **exactly three of them can pass an array at all**, the other
   fourteen never mention `m_sigma` [M]:

   | site | argument | branch taken today |
   |---|---|---|
   | `emfit/evolve.py:316` (`Leapfrog`, adapter) | `m_sigma=system.M_sigma.diag` - an array, always | lossless whenever the material conductivity is zero, because `np.any` is `False` [M] |
   | `emfit/studies.py:2649-2651` | `stepper_kwargs = {} if m_sigma is None else {"m_sigma": m_sigma}`, with `m_sigma` set at `:2607` (`None`) and `:2633` (`sigma if np.any(sigma) else None`) | the **only** lossy call site in the package; already normalises an all-zero vector to `None` [M] |
   | `tests/test_evolve_loads.py:147-151` | `None` omits the kwarg; the `:143` branch passes explicit zeros | both branches asserted at `:230-233` (`loss_den is None` twice, then `is not None` when armed) [M] |
   | `emfit/scatter.py:367`, `emfit/studies.py:487`, `emfit/studies.py:678` | omitted | lossless [M] |
   | `tests/test_d583_harness.py:72`, `test_port_parallel_plate.py:186`, `test_energy.py:56`, `:223`, `test_periodic.py:39`, `test_modalport.py:425`, `test_pml_audit.py:99`, `test_pml.py:215`, `:282`, `test_abc.py:86` | omitted | lossless [M] |

   Docstring examples at `emfit/pml.py:98` and `emfit/abc.py:99` are prose, not call sites [M].
   Outside `emfit/evolve.py:143-157` and `:197-204`, the only code that touches `loss_num` /
   `loss_den` is `tests/test_evolve_loads.py:230-233`, which only reads them [M]; nothing assigns
   them from outside the constructor, so there is no existing route that bypasses the `:152` guard
   [M].

   **What that means for AC-1.** Handing a zero vector to a site that used to pass `None` is
   **not** an AC-1 risk, and §3 is why: the guard drops it before any arithmetic is selected [M].
   The exposure is the other three cases, and all three are loud or fenced rather than silent:
   (a) a **nonzero** conductance on a plane when no load was specified - this is risk 3 (scope
   L375-379) and it moves history while every toleranced test still passes, which is exactly why
   AC-1 is exact equality rather than a tolerance [R]; (b) a wrongly shaped vector - a `ValueError`
   naming the expected edge count (`evolve.py:149-151`) [M], loud; (c) new code that assigns
   `loss_num` / `loss_den` directly, bypassing the guard - no such code exists today [M] and the
   fence in §8 forbids it [R]. The census therefore adds no new AC-1 hazard to the ones the
   scoping document already lists, and it does not contradict the brief.

5. **Build order is the rung order, and each rung has a stop rule.** R1 (`tests/test_evolve_loads.py`
   extended to a real-grid transverse cut) keeps the file's **existing** tolerances rather than
   tightening them: `s21` to 1 %, `s11` to 2 %, absorbed fraction to 2 %, assembled conductance to
   `1e-12` absolute, which is a comparison against `diag(Sigma)` and not against a run (scope
   L175-180) [R]. R2 replaces a terminal, not adds one: the same geometry, source and mesh with the
   far PML replaced by a matched load at the cut, required to reproduce the recorded `S11`
   `3.618e-4` and `|S21|` `1.000000583` (`tests/test_port_parallel_plate.py:277`) to the §6 bars,
   with the oblique case at `:334` still landing on Fresnel `-1/3` within the 3 % recorded at
   `:337-339` [L]. R3 is the end-to-end batch: matched, two mismatched, and the **open control**
   that is known-bad today (`|s21| > 1`, `beta` standard error `57`, `decisions.md:433`) [L].
   **Attribution rules, from the source and not invented here** (scope L206-211) [L]: R1 failing
   means the conductance is wrong; R2 failing with R1 passing means the load is in the wrong place
   or a second boundary condition was added beside it; R3 failing with R1 and R2 passing means the
   extraction is still not the same plane as the load - the only informative failure of the three
   [R]. R3 is last because it is the only rung that spends the wall budget (scope L352-354) [R].

6. **The bars are the ones already pre-registered, and they are not re-stated here as fresh
   rulings.** AC-1 `L222` (bit-for-bit losslessness, exact equality), AC-2 `L231` (no widening of
   any existing tolerance), AC-3 `L235` (`|S11| <= 1.0e-3` **and** `| |S21| - 1 | <= 1.0e-3`),
   AC-4 `L246` (>= 2 unmatched loads, `|Gamma|` within 3 % of `|R - Zc| / (R + Zc)`), AC-5 `L251`
   (no `|s21| > 1 + 1e-5`, and the open control's `beta` standard error at least 3x smaller than
   the `57` on record against a PML reference in the same batch), AC-6 `L260` (run JSON carries
   load value, units, plane index **and** the index of the plane the S-parameters came from),
   AC-7 `L266` (`beta_FDTD = -d(arg S21)/dL` from two line lengths against `beta_modal` from
   `emfit.mode_profile`, `|diff| / beta_modal <= 1.0e-3`), plus the falsifier of last resort at
   `L272` [L]. Three rulings bind how the verdict is written [R]: **ruling 1** (`L498`) - AC-3
   stays at `1.0e-3` and the verdict states the pass or fail **beside the achieved `|S11|`**, so a
   result sitting on the floor and one just inside the bar are visibly different outcomes;
   **ruling 2** (`L510`) - the `1400` s gate is **per run**, and the `2.86x` reading of a batch sum
   is withdrawn by the document itself, so no gate revision is made or needed; **ruling 3**
   (`L520`) - 25 and 50 Ohm are graded against AC-3, and 100 Ohm is **exploratory**, reported
   against the band `[0.30, 0.37]` because sub-cell discretisation already moves that arm
   `9.04 %` low (`decisions.md:421`) [L]. Three citation corrections bind any restatement of these
   bars, and are carried forward deliberately: `3.618e-4` is recorded at
   `tests/test_port_parallel_plate.py:277`, not `:270`; `5.8e-7` is **not** a recorded floor but the
   arithmetic remainder of `1.000000583`, so AC-5's tripwire is anchored 17x above a remainder and
   is the weaker instrument for it; and the `1400` s clause is per run (scope L531-538) [L].

7. **Cost and gate.** No run in this line of work is larger than a run already recorded, because
   the load is a plane inside the existing box (scope L329-331) [R]. Banked per-run figures [L]:
   cells `415072` at h = 0.4 mm and `3271744` at h = 0.2 mm; grid `68 x 218 x 28` and
   `134 x 436 x 56`; step `7.626299478123987e-13` s and `3.813149739061944e-13` s; steps `2400`
   and `4800`; `wall_fdtd_s` `232.00763625791296` and `1335.5644034249708`
   (`evidence/h_refine/h040.json:105,124,134,148`; `evidence/rung_c/h020.json:135,154,164,191`).
   Against the per-run `1400` s gate that is `0.166` and `1.048` of the budget - the h = 0.2 run
   passes with 64 s of headroom, and three of them are `4006.7` s of **session** time, about 67
   minutes, which is a scheduling cost and not a gate comparison (ruling 2, `L510-518`) [L].
   **Memory is an `ESTIMATE`, arithmetic and not measurement**: order 10 MB per array at h = 0.4 and
   about 78 MB at h = 0.2, i.e. order 0.24 GB for three arrays at h = 0.2, and no JSON in
   `evidence/` records a memory figure, so the estimate must be replaced by a measured number in
   AC-6's record before it is quoted anywhere (scope L342-350) [L]. **Re-runs on failure:** AC-1 to
   AC-5 can all fail at R1 or R2, which are in-process and cost seconds; R3 is the only rung that
   spends the wall budget (scope L352-354) [R].

8. **Fences, and what makes this build stop.** Untouched by name: `emfit/mode2d.py`, `emfit/pml.py`
   (808 lines), `emfit/abc.py` (348 lines), the mesh and cell counts
   (`emfit/studies.py:2556-2559`, `emfit/grid.py:113-114`), `emfit/board.py:566 to_cell_counts`,
   the excitation (`emfit/modalport.py:323`, `:19`), the append-only ledger, `d5854a` entry `[2]`,
   and the six untracked artefacts (`d80_96.md`, `d94_96.md`, `docs/design/c2b_shapes.pdf`,
   `docs/design/c2b_shapes.png`, `docs/design/mispaired_metric_before.png`,
   `docs/report/figures/c2b_mode_shape_corrected.png`) - scope §6, L279-311 [R]. The write fence
   for **this** dispatch is narrower still: this file, one row in `docs/design/dispatch_log.md`,
   and one paragraph appended to `docs/design/theory_round2_memo.md` item 8 [R]. Two stop rules,
   both pre-registered elsewhere and both binding here: **a bar that fails is recorded, not moved**
   (AC-2, `L231`), and **if a matched load leaves `|S11|` where it was - unmoved at `3.618e-4`, no
   better - then termination was never the extraction floor, the premise is wrong, and the response
   is to record that and stop rather than to go looking for a smaller number by another route**
   (falsifier of last resort, `L272-275`) [L]. One known defect is recorded and **not** repaired
   here: `tests/test_port_parallel_plate.py:339-340` carries a docstring with a word missing; the
   3 % it describes is real and asserted at `:358` and `:360` (scope L540-545) [L].
