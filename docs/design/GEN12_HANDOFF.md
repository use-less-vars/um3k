# GEN12 HANDOFF

Written for the agent that takes this repository next. Every claim carries a pointer: `file:line`, a commit, or a provenance label.

**Provenance labels.** `[HOST]` — measured on the operator's machine, quotable if the artefact path and date are given. `[ARTEFACT <path>]` — quotable to the precision printed in that file. `[CONTAINER]` — quotable for what it printed, never for timing: the sandbox is capped at `cpu.max 50000/100000` = 0.5 CPU (cpp-kernel-status-2026-11-09.md §5). `[PAST]` — a previous session's own text; it is not evidence and re-grades on touch. `[DERIVED]` — computed by me from quotable inputs, arithmetic shown. `[UNVERIFIED — carried from the brief]` — appears in this session's brief; not found in the repo in that form.

---

## 1. TL;DR

**Works.**
- Field solver: `|S11|` = 0.3255648664110912 at 5827786408.327286 Hz vs openEMS referee 0.327164553 = **+0.4914 %** (E12, `[ARTEFACT evidence/referee/s11_extraction.json]`, EM_SOLVER_LEDGER.md:37).
- Circuit solver + co-simulation: MNA in `emfit/spice.py` with `SpicePort` (95be122); `Diode` is "the one nonlinear device" (spice.py:141, class :288) and is gated by tests/test_spice.py:338/352/369/383/435 at 1e-14…1e-24. The **E5** row is still UNVERIFIED (:30) — the gate is algebraic, not physical (§2b).
- C++ kernel is on the call path (6cbb89d): `evolve.py FITStepper.step` → `emfit_core.fit_leapfrog`, `engine_report()`, tests/test_cpp_dispatch.py, tests/test_cpp_parity.py; S21 bit-identical 0.6361234402945529 across arms. On the host the operator measured **1.81x** (five runs, mean 27.44 s vs ~49.6 s Python, single-thread both arms) — operator-reported, unbanked as an artefact (§2e).
- UI: E7 VERIFIED (:32); `python3 server/poc_app.py`; operator ran the 7-step playback checklist on host 2026-11-11 `[HOST]`; 5e0758e fixed the play loop, 7d53f65 added the regression test.

**Does not work.**
- No 3-D antenna far-field / pattern / gain / directivity post-processor: "no antenna gain is computed anywhere in `emfit/`" (:38).
- No banked kernel artefact: the 1.81x is operator-reported and was not reproduced here, and no many-thread figure exists (§2e). The ledger row still says no speed figure exists — it lags the measurement.
- No citable suite pass: `build/full_suite.log` shows 100 % EXIT=0, but 582 tests collected against 584 (DR-39).
- No transistor: "transistor"/"BJT" do not occur in `emfit/spice.py`.

**In flight.**
- E3 Phase 2: authorised, not started — and there is a standing requirement of a written scope first, which I did not find; confirm.
- DR-43 residuals: defect FIXED-TESTED (defect_register.md:824-830); two open questions remain (docs/design/dr43_s21_extraction_scope.md).
- E13: parked (1921a5d).

**Do these first, in order.**
1. Read EM_SOLVER_LEDGER.md:20-42 and the DR-37/39/42/43 blocks in defect_register.md. The ledger row is the grade; design docs are the argument (§4.14).
2. `git log --oneline -8` — the last eleven are af635b6, 95ca1c1, 1f93518, af42368, 14093c7, 42d319d, b8b2b6a, c1c8276, 6cbb89d, 1921a5d, be803fd, newest first, and af635b6 says "DR-43 is closed, not pending". Commit subjects carry state changes the docs have not caught up with.
3. Use `--force-python` (or `EMFIT_FORCE_PYTHON=1`) when you want the Python engine: 14093c7 makes an extension that exists on disk but fails to import an **error**, not a fallback (contract and message: evolve.py:239-241, raise :268, repair named at :261-267 as `PYTHONPATH=.venv/lib/python3.12/site-packages`). Same flag on tools/host_ladder.py and evidence/termination/run_build_A.py.
4. Never measure by running the engine in the container (§2e, §4.1-4.2).
5. Read evidence/termination/NOTE.md before quoting any percentage — the two-anchor rule (§4.11).

---

## 2. WHERE WE ARE

### 2a. Field solver (FIT/FDTD, 50 Ω lumped ports)

**STATE** — E12 VERIFIED, +0.4914 % from the referee (EM_SOLVER_LEDGER.md:37). **CONFIDENCE** — high for `|S11|` at that one frequency, 50 Ω model of record.

**CAVEAT**
- The agreement consumes most of its bound: the error 1.5997e-3 is 2.98x the referee floor `bias_floor.floor_gamma0` = 5.363610948678204e-4, i.e. 99.4 % of the 3x bound. "Must not be described as well inside" (ledger).
- The field-impedance alternative is demoted, not deleted: beta = 165.245862+1835.847243j, |Z_ref| = 28.494912, `mode_fit_ratio` 11.109793 against tol 0.01, `mode_fit_ok` false; the field-normalised `|S11|` is 0.496975 = +52 % from the lumped-port number. Use 50 Ω.
- S21 is out of scope for this validation: port 2 is terminated in its lumped load.
- Residuals: −4.90 % against the DR-37 *correct-width* anchor 48.0237405 (w = 3.2 mm, E10); +5.5 % against the twin anchor 0.34465, which is **RETRACTED** as non-independent. Ladder `Z1` 49.9015 belongs to w = 3.0 mm only (DR-37, severity HIGH).
- E11 is open. Target after the 2026-11-10 amendment: 6.52 % (fine mesh, two-wave) / 6.42 % (one-wave); the coarse 4.90 % is superseded. H5 NOT FIRED, H4/H2 no-fire, mesh term 0.5523 pp wrong-signed, H1 routed to the operator. Pre-registration: docs/design/E11_residual_preregistration.md.

### 2b. Circuit solver (MNA, `emfit/spice.py`)

**STATE** — VERIFIED linear MNA + one nonlinear device; **E5 UNVERIFIED** (:30). **CONFIDENCE** — high on implementation correctness, low on physical authority.

**CAVEAT**
- `Diode` (spice.py:141, class :288) is Shockley + gmin (:288-326), `_EXP_CLAMP` 100.0 :210, `_RELTOL` 1e-9 / `_VNTOL` 1e-12 :207-208. Gated by tests/test_diode.py and tests/test_coupling_diode.py.
- The Newton loop sits inside the timestep and re-stamps only the junction; the linear path is untouched (:145-148). Non-convergence **raises** `DiodeConvergenceError` — it never returns the last iterate (:149-150). There is no operating-point solve and `initial_state` is all zeros (:151-152). gmin makes a reverse-biased junction emit −isat rather than open (:322-326).
- E5 is UNVERIFIED because Test A is an algebraic identity: `e^T j_port = v_p^T i_p` is a tautology for any invertible `W_E`. It tests bookkeeping, not physics (docs/design/spice_adapter_scope.md, 0fe1a71, 537 lines; in-repo MNA chosen over ngspice — no ngspice in the container).

### 2c. Co-simulation (`SpicePort`, terminations)

**STATE** — works as wiring: `SpicePort` joins the FIT step to the MNA solve, 95be122; `terminations.py` (414 lines) + `TerminalPort` bf747bd. **CONFIDENCE** — medium: the interface is exercised, the *physical* meaning of the port impedance in a diode-loaded circuit is not established.

**CAVEAT** — the coupling inherits the circuit solver's limits wholesale: the Newton loop runs inside the FIT timestep over the junction only (§2b), there is no operating point, and the only gate is the algebraic identity of Test A, so a plausible-looking coupled waveform is not evidence that the port model is right. Treat any co-simulation result as `[UNVERIFIED]` until E5 has a physical gate.

### 2d. UI (`server/poc_app.py`)

**STATE** — E7 VERIFIED (:32), operator 7-step playback on host 2026-11-11. **CONFIDENCE** — high for the operator path, zero for anything I claim from the container.

**CAVEAT**
- The container cannot render: no EGL/OSMesa/Xvfb, and the only real `Plotter.render()` segfaults. Container visual claims are unquotable.
- `.venv/bin/python` is broken **only** in the container (`pyvenv.cfg` says 3.12.3, image is 3.12.15); the dependencies are live at `.venv/lib/python3.12/site-packages`.
- server/poc_app.py:49-55 still says the Trame web path is UNTESTED — stale against the operator run; treat the docstring as the older statement.
- Polish gaps: smooth shading, no wireframe overlay, no scalar bar on the x-cut, x-cut fixed at two recorded samples.

### 2e. C++ kernel speed — the honest statement

**STATE** — a host figure exists and it is the headline; the ledger has not caught up. **CONFIDENCE** — medium: the number is operator-reported and unbanked, the build itself is verified.

**The figure.** The operator ran the C++ kernel on the host five times: 28.04 / 27.47 / 27.15 / 27.51 / 27.01 s — mean 27.44 s, σ 0.37 s (±1.3 %). Python on the host averaged ~49.6 s with ±18 % spread. Speedup **1.81x** `[ARITHMETIC: 49.6 / 27.44 = 1.808]`. The outgoing engineer's prose used 1.85x; that does not follow from their own table — use 1.81x.

**Provenance, in the same breath.** OPERATOR-REPORTED, pasted in conversation on the handoff date. It is not banked as an artefact in this repo and we did not reproduce it. The missing thing is the raw five-run artefact: ask the operator for it and bank it. Until it is banked this figure is quotable only with the words "operator-reported" attached.

**Why it is believable anyway — the useful part.** Our container measured the same C++ configuration twice at 58.0408 s and 43.2006 s (`[ARTEFACT artifacts/ladder_engine_scaling.json]`, 42d319d). Two identical runs differing by 1.34x is instability, not merely slowness, and both sit above the host's 27.44 s — up to 2.12x above it `[ARITHMETIC: 58.0408 / 27.44 = 2.115]`. Container Python at 50.1157 s is within about 1 % of host Python at 49.6 s. So the container distortion is specific to the C++ kernel, not to timing in general.

**Thread count — what makes the figure defensible.** `emfit/_env.py:44-70 pin_threads`, called at `emfit/__init__.py:33-37` before numpy is imported, pins `OMP_NUM_THREADS` to 1 at package import, so ours was a one-thread comparison in both arms. 1.81x is therefore single-thread-versus-single-thread — exactly the pinned-thread statement DR-42 demands on any kernel figure. Two open questions follow: confirm the operator's host runs also went through the package (hence also one thread), and note that a many-thread figure is still unmeasured and must not be inferred from this one.

**What the container measured, labelled as such.** The container numbers go the other way, and that is the reason the rule below exists: structure C (289 168 cells, whole process) cpp 58.0408 s vs py 50.1157 s — cpp 1.16x **slower** `[CONTAINER]`; ladder rung 51 832 cells, FDTD phase py/cpp 1.3877x `[CONTAINER]`. Both arms are pinned to one thread by `pin_threads`, so the ratios that once looked like thread effects (58.0408/43.2006 = **1.3435**, 7.2474/6.2544 = **1.1588**) are repeat spread — the same-config repeat is 1.1595. Resolution limit ±34 % at structure C, ±16 % on the rung. cpp with `OMP_NUM_THREADS=1` 43.2006 s = 0.862x; cpp_t1/py 1.1616x `[CONTAINER]`; all from 42d319d (`[ARTEFACT artifacts/build_C_stub_{cpp,cpp_t1,pyengine}.json]`, `[ARTEFACT artifacts/ladder_engine_scaling.json]`), n = 1 per arm. Renamed `*_omp_env_set_vs_unset_both_pinned_*`, `corrections[] C1` in af42368; DR-42's 33x is UNREPRODUCED (no run ever reached the kernel with an inherited team). None of these container readings says anything about the kernel's speed on a host.

**Ledger lag, stated as a fact.** EM_SOLVER_LEDGER.md:28 still reads that no speed figure exists and that E3 stays UNVERIFIED. The ledger has not caught up with the host measurement; the operator is updating it. Do not write "E3 verified" — write that the row lags by one measured figure. The row's AMENDMENT 2026-11-14 withdrew the 50x / 5,926 ns ladder (3.8 / 19.6 / 54.3 / 145.6 / 351.5 µs at 1/2/4/8/12 threads, "shape reproduces, magnitudes do not, so no ladder number may be carried forward") because those were taken under an ambient unpinned team — the DR-42 trap. The "1.76x wall clock on a 560-edge toy" is called there "a weak upper bound and must not be quoted as a board-size claim".

**The rule.** No `[CONTAINER]` figure may be quoted as a measurement. A `[HOST]` figure is quotable with its provenance and its thread count attached.

Implementation facts that stand (build facts `[ARTEFACT cpp-kernel-status-2026-11-09.md:15-28]`, grid numbers `[CONTAINER]`): `g++ -O3 -fopenmp -std=c++17 -shared -fPIC -Wall -Wextra`, pybind11 3.1.0, zero warnings (cpp-kernel-status-2026-11-09.md:15-28); src/CMakeLists.txt:55 pins `-O2 -fno-fast-math -ffp-contract=off -fopenmp`; five `#pragma omp parallel for schedule(static)` at emfit_core.cpp:83,92,103,114,130; GIL released in src/bindings.cpp. On the golden grid (4x3x2 = 133 edges / 98 faces / 392 nonzeros) the pragmas are ~50x **slower** (1 thread 5,926 ns/call; 2 → 49,252; 4 → 124,111; 8 → 353,937; `OMP_WAIT_POLICY=passive`, `GOMP_SPINCOUNT=0`, `OMP_PROC_BIND=close` do not rescue it). Parallel reduction reorders `row_dot` and forfeits bit-parity (:462-470, "no speed figure either way"). E8's `pip install -e .` is OPERATOR-REPORTED only — no scikit-build-core, ninja or network in the container.

### 2f. Mode solver / near field (2-D TMz)

**STATE** — 2-D TMz scattering only: `emfit/nearfield.py kirchhoff_amplitude:456`, `scattering_width:530`, calibration gate :564 against an analytic cylindrical wave; `emfit/mie.py` as analytic reference; tests/test_nearfield.py, tests/test_mie.py; mode2d.py 99 KB, modal.py 39 KB. **CONFIDENCE** — medium for plane-wave scattering, none for a driven antenna. **CAVEAT** — 3-D is absent; nothing here generalises to a radiating structure without the near-to-far transform that does not exist (§5.4).

---

## 3. HOW THE MACHINE RUNS

Three roles.

- **Agent (you).** No instrument. 0.5 CPU, no network, no display. You read source, write code, run tests, propose measurements. You cannot observe physics.
- **Operator.** Host machine, 12+ cores, real display. Runs what you ask, pastes back transcripts and artefacts.
- **TE.** Judgement, limited budget. Decides scope and direction; is not a debugger and not a validator of your arithmetic.

The loop: **agent proposes → operator runs → operator pastes verbatim → agent interprets and commits**, the artefact and the claim in the same commit. Nothing enters the record without passing through the operator's hands.

**Cost of skipping it.** You get a number of plausible size and quote it as a measurement. 42d319d published 1.3435 (structure C, 58.0408 vs 43.2006) and 1.1588 (ladder, 7.2474 vs 6.2544) as OpenMP thread effects. af42368 read `emfit/_env.py:44-70` and `emfit/__init__.py:33-37` — "Thread pinning must run before anything imports numpy: BLAS reads its thread count once" — and found both arms pinned to one thread, so there was no team to differ. A measurement, refuted by two file reads at zero cost. That is the shape of the mistake this document exists to prevent.

"2.12x" = 58.0408 / 27.44 = 2.115 `[ARITHMETIC]`: the container's slowest C++ run over the operator's host mean, i.e. a measure of *container distortion*, not of kernel speed. Both inputs are named — `artifacts/ladder_engine_scaling.json` and the operator's five-run paste (§2e). (Two unrelated 2.12-shaped numbers exist in the repo — preservation_gate_preregistration.md:53 / preservation_gate_results_a35.md:63, 2.126525e-4 on a grid-refinement column, and normalization_scheme.md:287 `v_ratio` = 2.12 — neither is this.)

---

## 4. THE RULES

1. Every number carries a provenance class, and `[CONTAINER]` never carries timing. Incident: the 0.5 CPU cap; the golden grid, where the same pragmas are ~50x slower than serial.
2. Container timing is not a host measurement — not even Python timings taken with the kernel loaded. The distortion is kernel-specific: container Python is within ~1 % of host Python, container C++ up to 2.12x off. Incident: §2e.
3. Every kernel figure carries its thread count; here the default is one. Incident: `pin_threads` runs before numpy, so the process is single-threaded whether you asked or not (af42368; DR-42 THIRD AMENDMENT 2026-11-12) — which is exactly what lets 1.81x be stated as one-thread-versus-one-thread.
4. A ratio between two pinned runs is repeat spread, not an effect. Incident: 1.3435 vs a same-config repeat of 1.1595, ±34 % / ±16 % resolution.
5. Silent failure is the enemy; a kernel on disk that cannot import is an error, not a fallback. Incident: 14093c7, contract at evolve.py:231-268.
6. The ledger and the defect register are append-only; never `git commit --amend` a graded statement away. Incident: DR-42 THIRD AMENDMENT + `corrections[] C1`.
7. Never overwrite a banked artefact — use a non-colliding `--out`. Incident: openEMS bind-mount files land root-owned (docker/openems/README.md:115-118), and "a solve started over leftover state is not a fresh observation".
8. A fabricated or reconstructed artefact is worse than none. Incident: `git_rev` is null in every referee run record — DR-28, still open.
9. Verify a failure reproduces before patching it. Incident: the stale SOLVE FAILED; DR-39's 582 vs 584.
10. A claim you cannot resolve to `file:line`, a commit or a label does not go in a document. Incident: roadmap-next-2026-11-08.md:85-86 — "the field that would have kept 0.245 out of a quotation".
11. Never mix anchors; the anchor travels with the number. Incident: −4.90 % against the correct-width anchor vs +5.5 % against a retracted twin (evidence/termination/NOTE.md).
12. Quote how much of a bound you consumed, not just that you passed. Incident: 2.98x of 3x = 99.4 %.
13. Absence is a finding, and it needs the search stated. Incident: "no antenna gain is computed anywhere in `emfit/`" (:38) is only usable because the search is written down.
14. When documents disagree, the ledger row is the grade and the design doc is the argument — never average them. Incident: the E3 row vs 42d319d; poc_app.py:49-55 stale against the operator run.


---

## 5. CURRENT WORKSTREAMS

### 5.1 E3 Phase 2 — kernel speed, done properly

Authorised, **not started**. Phase 1 landed in 6cbb89d (kernel on the call path), b8b2b6a (engine provenance recorded in the C-arm re-run) and c1c8276 (stale claim corrections).

A host figure now exists (1.81x, operator-reported, single-thread both arms, §2e), so the work is no longer to find a number but to bank it: the raw five-run artefact, confirmation that the operator's runs also went through the package (hence one thread), and either a many-thread run or an explicit decision that single-thread is the claim. "Done" still means **one** number that survives §4: large mesh, n ≥ 3, thread count printed, both arms pinned, timer scope stated — FDTD phase vs whole process differ by ~1.4x here and *flip the sign* (1.3877x vs 1.16x slower, §2e). Still blocked by the bit-parity decision recorded at cpp-kernel-status-2026-11-09.md:462-470: the parallel reduction reorders `row_dot`, and parity vs speed has not been chosen. Confirm whether a written scope exists before writing code; the standing requirement is a scope first.

### 5.2 DR-43 residuals

The defect is FIXED-TESTED (defect_register.md:824-830; fixes a69ed43 + 8ba20ef, INFERRED from subject lines), and af635b6 corrected the docs ("DR-43 is closed, not pending"). tests/test_studies.py:1577-1635 pins the nan that started it.

Two questions stay open (docs/design/dr43_s21_extraction_scope.md):
- **Residual 1 — driver default plane policy.** evidence/termination/run_build_A.py:1829-1830 defaults to `ix_load+1`; whether the driver should choose an S21 plane at all, or require the user to name one, is undecided.
- **Residual 2 — branch (b) withholds a ratio-of-ratios** for want of a name: studies.py:4109-4120 (cut branch), :4121-4136 (ratio-of-ratios), :4137-4153 (span fallback), `SPAN_S21_UNMEASURED` :129-139. Seven smaller unknowns sit under "### Remaining smaller unknowns" in the same scope document.

Both Campaigns below are blocked on these decisions.

### 5.3 Campaigns A / B — multi-plane storage and Touchstone export

The operator calls these Campaign A (multi-plane storage) and Campaign B (Touchstone .s2p export); the labels are conversational and appear nowhere in `docs/`. Both are **DESIGN ONLY**. roadmap-next-2026-11-08.md:5-7: "Nothing described here is implemented: there is no Touchstone writer, no export command in `emfit/cli.py`, no run manifest."

The design as written:
- API: `emfit/export.py` — `s_parameters(record)` and `write_touchstone(sp, path, *, z0=50.0, ports=None)` (:56-61).
- Options, one line each (:63-67): the actual reference impedance, ascending frequency, and .s2p column order S11 S21 S12 S22 — "the one place a wrong choice silently transposes a model".
- First thin slice: :99-102.
- `--manifest` must not be optional: Touchstone cannot say "this number is fit-derived" (:115-117).
- Plane validity stops at `res.geometry` (:119-127): `emfit/cli.py:197-200` prints no geometry field, no study registers `s21_plane` as a `Param` (run_build_A.py has `--s21-plane-index` / `--s21-plane-col`), and the geometry copy floats every scalar — `s11_at_plane_valid` reads back as 0.0/1.0 and `invalid_reason` vanishes when it is `None`.

Deferred until the DR-43 residuals are decided.

### 5.4 E13 — antenna demonstration

UNVERIFIED, PARKED (1921a5d, :38), behind E3 and E5. Board A: Yagi / patch at 2.4 GHz, 8-10 dBi. Board B: monopole / meandered IFA, ~0 dBi. ESP32-class MCU. "A few dB is the target, not a result."

Chain: DR-43 residuals → E3 complete → automatic meshing at board scale → 3-D near-to-far (neither of the last two exists) → E13. The NOTE 2026-11-12 corrects dependency (i) — the kernel is now on the call path — but does not reopen the parking, because dependency (iii) governs.

---

## 6. THE OPERATOR

**Do**
- Give one command block, with the working directory and an explicit `--out` that cannot collide with an earlier artefact.
- Say what output you expect and what it decides; a run whose result cannot change a decision should not happen.
- State the thread environment you are assuming — `OMP_NUM_THREADS`, and that `pin_threads` will pin anyway.
- Ask for the verbatim transcript, not the number: the number alone is unquotable.
- Batch independent commands into one message; the operator's time is the scarce resource.
- Ask for the artefact path *and* its date.
- Believe the failure, doubt your command — before asking for a re-run.
- Flag cheap (seconds) vs overnight, so the operator can schedule.

**Don't**
- Don't ask the operator to judge credibility; that is your job and TE's.
- Don't ask the operator to debug your implementation.
- Don't ask for the engine to be run in the container.
- Don't ask for a run you already lost the output of — you lost it, that is your error to record.
- Don't quote a host number without its artefact path and date.
- Don't send a chain of small dependent steps you could have merged into one block.

---

## 7. YOURSELF

**Do**
- Read the ledger row before the design doc before the code.
- Prefer the cheap oracle: two `file:` reads beat a measurement (§3).
- Commit claim + provenance + artefact together, or do not commit the claim.
- Grade your own output, including the parts that make you look bad.
- Annotate supersession in place — never delete the older statement.
- Check the tally, not the exit code (DR-39: 582 of 584 with EXIT=0).

**Don't**
- Don't prefer a numerical coincidence to the source. **af42368, three lines:** I published 1.3435 as an OpenMP thread effect; `emfit/_env.py:44-70` pins both arms to one thread; a same-config repeat is 1.1595, which is the size of the "effect". A coincidence of magnitude is not evidence of mechanism.
- Don't carry numbers across a tree change; re-measure, or re-label.
- Don't upgrade a grade because two documents agree — they may share one origin.
- Don't fix a stale failure; reproduce it first.
- Don't add a fourth way: `--force-python`, `EMFIT_FORCE_PYTHON=1` and the engine argument are one contract (evolve.py:231-268).
- Don't quote a `[PAST]` statement as evidence — including your own, from an earlier turn. Touching the subject re-grades it.

---

## 8. TE

- Ask a scoped question with the answer space stated: what decision, between which options.
- Pre-compute both bases so the question is arithmetic, not research: +0.4914 % in-house vs +0.4890 % against the referee `[DERIVED — from 0.3255648664110912 / 0.327164553 and the referee artefact]`.
- State what you ruled out: H4/H2 no-fire, H5 NOT FIRED, mesh term 0.5523 pp wrong-signed.
- Never ask TE to debug an implementation.
- Ask for a decision, not for validation of one you have already taken.
- Say what would change your mind.
- One question per message.
- Accept "no" as a bracket — it narrows the space even when it settles nothing.

---

## 9. WHAT TO READ NEXT

1. EM_SOLVER_LEDGER.md — :28-38 and the amendments at :40. The grades.
2. defect_register.md — DR-37 (w = 3.2 mm, HIGH), DR-39, DR-42, DR-43, DR-28.
3. cpp-kernel-status-2026-11-09.md §5 and :462-470 — 0.5 CPU, bit-parity.
4. docs/design/dr43_s21_extraction_scope.md — the two open residuals.
5. evidence/termination/NOTE.md — the two-anchor rule.
6. roadmap-next-2026-11-08.md — export/manifest design, explicitly unimplemented.
7. docs/design/spice_adapter_scope.md — why MNA in-repo, why E5 is unverified.
8. `emfit/evolve.py:159-270` — the engine provenance contract and `--force-python`.

### Where the mass is (navigation, not reading list)

The repository is 386 files / 7.0 MB. `tests/` holds 62 modules — tests/test_poc_playback.py 123.6 KB, tests/test_studies.py 117.2 KB. In `emfit/`: studies.py 327 KB, mode2d.py 99.0 KB, ports.py 81.9 KB, spice.py 64.8 KB, nearfield.py 38.2 KB. server/poc_app.py is 345.6 KB; docs/design holds ~130 `.md`. Read none of these end to end: go to the `file:line` above and stop.

### What we still do not know

1. **The many-thread speedup at board size.** Single-thread is measured on the host (1.81x, operator-reported); nothing above one thread exists, and this figure must not be scaled up. Resolve: bank the operator's five-run artefact, then a large-mesh run with the thread count printed and both arms pinned (§5.1).
2. **Whether parallel reduction is worth the loss of bit-parity.** Resolve: a TE decision at cpp-kernel-status-2026-11-09.md:462-470, then a paired run.
3. **What DR-42's 33x actually was.** Resolve: a run that reaches the kernel *with an inherited thread team* and prints `omp_get_num_threads()`.
4. **The 6.52 % E11 residual partition.** Resolve: H1 routing with the operator, per docs/design/E11_residual_preregistration.md.
5. **What branch (b) is a ratio of.** Resolve: a name for the quantity (studies.py:4121-4136), or an explicit decision to withhold it.
6. **Whether the driver should guess an S21 plane.** Resolve: residual 1 above — policy decision on run_build_A.py:1829-1830.
7. **Whether the suite is green.** Resolve: the two missing tests (582 vs 584), DR-39.
8. **Whether `SpicePort` is physically right.** Resolve: a gate that is not an algebraic identity — Test A is a tautology (§2b).
9. **Whether the 2-D TMz near-field transform generalises to 3-D.** Resolve: gate it against a half-wave dipole, 2.15 dBi.
10. **Why `git_rev` is null in every referee record.** Resolve: DR-28 — record the revision at solve time, or state that provenance stops at the file.

