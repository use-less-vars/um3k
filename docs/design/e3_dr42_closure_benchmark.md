# E3 — DR-42 closure benchmark: the post-pin kernel on the host

**What this document is.** It records a host measurement taken by the operator on 2026-11-13, outside this container, and the four things that measurement settles: the thread pin holds at the kernel entry, the provenance fields that make it auditable now exist, the banked 1.81x is not reproduced by the current build, and the reason for that gap is not geometry. It does not move E3's verdict in `docs/design/EM_SOLVER_LEDGER.md:28`, which stays `UNVERIFIED`. Its companion record is the FOURTH AMENDMENT of DR-42 in `docs/design/defect_register.md`; where the two disagree, the register governs and this document is wrong.

## 1. What was measured — three arms, one grid

[OPERATOR-HOST — not in tree] The three arms were run on the operator's host machine, not in this container, and their artefacts are operator-local: `/tmp/s5b/*.json` and `/tmp/s5b/*.log`. Nothing in this section can be reproduced from a clone of this repository. What can be reproduced is the build (§7), the parity suite (§3), and the code paths the provenance fields come from (§2).

All three arms run the same experiment: `evidence/termination/run_build_A.py`, structure A, `--nsteps 2400`, meshing to **289168 cells** at `cell_mm 0.4`. One cell count, one step count, one grid.

| arm | engine | `OMP_NUM_THREADS` | runs | wall per run (s) | mean (s) | sigma, sample (n-1) |
|---|---|---|---|---|---|---|
| cpp, pinned | `cpp` | `1` | 5 | 35.44, 34.72, 33.09, 34.25, 36.22 | **34.74** | **1.19** |
| python | `python` (`--force-python`) | `1` | 5 | 45.11, 44.65, 46.31, 54.08, 47.60 | **47.55** | **3.83** |
| cpp, 12-thread environment | `cpp` | `12` | **1** | 34.6 | 34.6, no sigma | — |

Ratio of the two five-run means: **47.55 / 34.74 = 1.37x**. The Python path is **36.9 %** slower than the pinned compiled path on this host, at this mesh. sigmas are the sample form throughout; the third arm has no spread because it is a single run, and it is reported as a single run rather than dressed up as a mean.

## 2. The provenance fields, as written

Commit `0c8da31` pinned the team. Commit `43558ef` recorded *which team was asked for*. The two meta blocks below are transcribed from the operator's artefacts, not summarised:

| field | `cpp_1.json` | `cpp12.json` |
|---|---|---|
| `step_engine` | `cpp` | `cpp` |
| `n_threads_kernel` | `1` | `1` |
| `n_threads_env` | `'1'` | `'12'` |
| `n_threads_env_requested` | `None` | `'12'` |

Read the two columns together and the distinction that commit `43558ef` exists to draw is visible in one comparison. `n_threads_env` is what the variable held **when the writer looked at it** — after `pin_threads` had run, so a variable that was absent has already become `'1'`. `n_threads_env_requested` is what the operator actually asked for, captured at `emfit/_env.py:48` before `pin_threads` overwrites anything. In `cpp_1.json` the two differ: the operator asked for nothing (`None`) and got one thread, which is the pin doing its job, and the artefact now says so instead of recording `'1'` and quietly calling that a request. In `cpp12.json` they agree: the operator asked for `12` and the writer's view is also `'12'`, because a non-empty value wins over the pin — the behaviour the THIRD AMENDMENT described from the code at `docs/design/defect_register.md:799`, and which this artefact now confirms from a run rather than from a reading.

`n_threads_kernel` reads `1` in both arms, and that is the correct reading rather than a defect: it is the size of the team the kernel was told to use, which is `1` because the pin sets it. The 12-thread arm is a 12-thread **environment**, not a 12-thread kernel (§6).

Both fields are written by the artefact's own writer (`evidence/termination/run_build_A.py:3357-3358`), so they travel with the number they qualify. This is gate (d) of the THIRD AMENDMENT discharged for this measurement: the engine and the thread count are both on the record, in the artefact, by the writer, not by the operator's memory.

## 3. How the pin was verified

Three mechanisms, in increasing order of how hard they would be to fake:

1. **The code.** `src/emfit_core.cpp:69` declares `static int g_num_threads = 1`; the five row-dot loops take their team from that value through `num_threads(get_num_threads())` at `:102`, `:111`, `:122`, `:133` and `:149`; and `emfit/evolve.py:292` calls the kernel's thread setter with `(1)` when it loads the kernel. With a team supplied per region, the runtime's default team is never consulted.
2. **The parity suite.** `pytest tests/test_cpp_parity.py` -> **13 passed**, not skipped, on this host: the kernel is reachable and agrees with the Python engine on the same grid. A skip here would have proved nothing — the pin is only interesting if the code it pins is the code that ran.
3. **The 12-thread arm.** `OMP_NUM_THREADS=12` with `n_threads_kernel: 1` produced **34.6 s** against the pinned arm's **34.74 s** mean, a 0.4 % difference and in the *faster* direction, well inside the pinned arm's own spread (sigma 1.19). Had the pin leaked, the environment's 12 would have reached libgomp and the arm would have been slower by a factor, not faster by a rounding.

On the size of that factor: this container measured an unpinned 12-thread arm at **4.506x** the pinned one-thread cost — `172.535247 / 38.287688` at `docs/design/e3_baseline_benchmark.md:96`, on a 1.0 CPU quota, asserted as `4.506x` in the S5a amendment of `docs/design/EM_SOLVER_LEDGER.md:28`. That multiplier is a container measurement of a different build on a smaller grid and does not transfer to the host as a number. What transfers is the sign and the order of magnitude: an inherited team is a large penalty, so 34.6 against 34.74 cannot be a leaked arm.

## 4. `label=A` against the banked `structure: "C"`

The operator's runs print `label=A cells=289168`. The banked host timing records `"structure": "C"` at `artifacts/ladder_engine_host_timing.json:4`. The labels differ and the meshes do not: `:5` records `mesh_cells 289168` and `:6` records `steps 2400` — the same two numbers the operator's runs report — with `cell_mm 0.4` at `:7`.

The physics agrees independently. One run's summary line reads

`label=A cells=289168 wall=35.2s |s21|=0.761705423 |s11|=3.258633e-01 cut_plane=51 passivity=0.686382015950`

and `|s21| = 0.761705423` agrees to nine digits with the plain-cut reference value `0.7617054231929281`, with `|s11| = 0.3258633` and passivity `0.686382015950` beside it. Two different meshes do not produce nine-digit agreement in a scattering parameter; the same 289168 cells were advanced 2400 steps in both cases. The timing comparison in §5 therefore compares like with like and is not confounded by geometry.

**Where the `"C"` label came from, and why it is not edited.** The banked artefact records no `argv`, no `command_line`, no `git_rev` and no build flags — its keys, dumped, contain none of those — so the `--structure` argument of the 2026-11-11 run behind it is not on the record. Its own `checks.mesh_cells.basis` says the label was verified against `ladder_engine_scaling.json`, which records structure C at 289168 cells: the label was **inferred from the cell count**, not read from the run. That is a documentation defect in the artefact, not a measurement defect — the mesh is pinned by the count, and the count is right. The artefact is not edited here, because rewriting a banked record's label after the fact destroys the provenance the label was there to carry. It is carried as an open item for Gen 13: qualify the label in place, or supersede the artefact with one that records its command line.

## 5. The 26.6 % gap against the banked cpp figure, and why 1.81x is not withdrawn

Banked, at `artifacts/ladder_engine_host_timing.json`: cpp **27.44 s** (sigma 0.37, `:16`) against Python **49.6 s** (`:10`), ratio **1.81** (`:22`). Today, same mesh, same steps: cpp **34.74 s** against Python **47.55 s**, ratio **1.37x**.

The compiled path is **26.6 %** slower than the banked figure. The Python path moved by **-4.1 %**, inside its own spread. The 7.3 s cpp gap is not noise: it is roughly 20 sigma of the banked arm's own spread and about 6 sigma against the two arms' pooled spread, and the Python arm run on the same machine in the same session is where it always was, so the host was not simply busy.

Three candidate explanations, in the order the evidence supports them:

1. **Build flags, `-O3` -> `-O2`. UNVERIFIED, and the leading candidate.** The kernel-experiment build recorded at `docs/design/EM_SOLVER_LEDGER.md:33` (E8) carries `-O3 -fopenmp -std=c++17 -shared -fPIC -Wall -Wextra`. The current CMake build carries `-O2 -fno-fast-math -ffp-contract=off -fopenmp` at `src/CMakeLists.txt:55`. A 26.6 % regression is the right order of magnitude for dropping `-O3` on a dense row-dot loop, and the two added flags are conservative in exactly the direction that costs speed. What would settle it is a rebuild at `-O3` and a re-run of the five-run arm. It cannot be settled from the banked artefact, because **the banked artefact records no flags at all** — the same provenance hole §4 describes, and the reason this paragraph says *candidate* and not *cause*.
2. **ABI 1 -> 2, the cost of the pin itself.** Order 1-3 %, unquantified here. A parallel region explicitly sized to one thread is not free, so the pinned kernel is expected to be marginally slower than the same arithmetic with no region to enter. 1-3 % is not 26.6 %: this candidate can sharpen the residual, not carry it.
3. **Grid or physics difference.** Excluded by §4.

**`1.81x` is not withdrawn, and `1.37x` does not supersede it.** They are measurements of different builds, taken weeks apart, answering different questions: 1.81x is how much faster the compiled kernel was than Python on 2026-11-11; 1.37x is how much faster it is today. Both are true. Neither is the maximum achievable speedup, and neither is an E3 verdict. What the pair establishes is the thing that matters for E3 and for the register's gate: the compiled/Python ratio is **a property of the build**, so a ratio quoted without its build flags beside it is not a fact about anything. That gate — THIRD AMENDMENT (d) at `docs/design/defect_register.md:799`, and the gate at `:797` before it — is precisely what this pair would violate if either number were quoted alone.

## 6. What this does not establish

- **E3's verdict does not move.** `docs/design/EM_SOLVER_LEDGER.md:28` is untouched by this document and by the two commits behind it; the E3 row still reads `UNVERIFIED`. Nothing here is a speedup claim for E3.
- **It does not establish the maximum achievable speedup.** One build, one mesh, one host, one Python arm. 1.37x is this build's number, and it is the second data point, not the ceiling.
- **It does not close the `-O3` question.** §5.1 is a candidate with a named experiment, not a result.
- **It does not establish anything about kernel scaling.** The 12-thread arm measures the numpy/Python threading and the whole-process behaviour of a run whose *environment* said 12. The kernel ran at one thread in all three arms, `n_threads_kernel: 1` in both artefacts that record it. No number in this document is a kernel scaling measurement, and none may be quoted as one.
- **It does not repair the banked artefact.** The missing flags and the inferred structure label are documentation items carried for Gen 13 (§4, §5.1).

What it does establish: the thread team is pinned at the kernel entry, structurally and empirically (§3); the provenance fields that make that auditable now exist and are written by the artefact itself (§2); and the current build's compiled/Python ratio on the host is **1.37x**, not 1.81x, with the gap attributed to the build rather than to the grid (§4, §5).

## 7. Rebuild confirmation

A number is only meaningful if a clean checkout produces the same kernel, so both build routes were checked on the host: `pip install -e .` yields ABI **2**, and the g++ fallback route yields ABI **2**. Both routes compile the same source with the same flags from `src/CMakeLists.txt:55`, so agreement is expected rather than surprising — what the check rules out is the failure mode where an installer picks up a stale extension and reports an old ABI against a new Python wrapper.

The same ABI is reproducible from source in a container, independently of the operator's host: a `g++ -O2 -fno-fast-math -ffp-contract=off -fopenmp -std=c++17 -shared -fPIC -Wall -Wextra` build of `src/bindings.cpp` and `src/emfit_core.cpp` with the flags of `src/CMakeLists.txt:55` reports `KERNEL_ABI = 2`, `KERNEL_NAME = emfit_core.fit_leapfrog` and `get_num_threads() = 1` at import, and `PYTHONPATH=build/cpp pytest tests/test_cpp_parity.py -o addopts="" -q` returns **13 passed** with no skips. The `PYTHONPATH` is load-bearing: the parity module does a bare `import emfit_core` and never touches `sys.path`, so a bare `pytest` in a container where the extension exists only under `build/cpp` reports 13 *skipped* - a path problem, not a code problem, and a skip is not a pass.

At run time, `emfit.evolve.engine_report()` returns

`{'step_engine': 'cpp', 'kernel_abi': 2, 'kernel_name': 'emfit_core.fit_leapfrog'}`

naming the engine, the ABI the dispatch compared, and the kernel entry the stepper called. Together with the meta fields of §2, a run now carries enough to be attributed after the fact: which engine, which kernel entry, which ABI, which thread team was requested, and which team was used.
