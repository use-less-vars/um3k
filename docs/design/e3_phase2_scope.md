# E3 phase 2 — scope

**Status: SCOPE ONLY.** This document states what phase 2 of E3 covers, what it
must not touch, and which preconditions have to be true before any of it can be
claimed. It contains no code, no CMake edit and no benchmark: nothing below is a
measurement made for this document, and no number here is new. Every claim
carries the `file:line` it was read from in this container on 2026-11-12, and
git history is not available here (`.git` is empty), so anything that depends on
a commit is recorded as *cited*, not as verified.

E3 itself stays **UNVERIFIED**. `docs/design/defect_register.md:821` says so in
DR-42's own Gates line ("This entry does not move E3, which stays UNVERIFIED"),
and `docs/design/EM_SOLVER_LEDGER.md:28` grades E3 UNVERIFIED. A scope document
cannot move a verdict, and this one does not try.

## 1. What phase 2 is

Phase 1 built the kernel and proved it matches the Python reference on the cases
it was built for. Phase 2 is the three things phase 1 deliberately left out,
in this order, because each one is only meaningful if the one before it holds:

1. **A ULP bound on the reduction path.** Parity is currently asserted
   bit-for-bit on whole steps. A step-level identity is a strong claim about a
   small grid and says nothing about the row-dot reductions on a large one,
   where summation order changes with the number of threads.
2. **Thread pinning inside the kernel entry point**, not in the environment.
   Today a caller that inherits an ambient team gets a default-team kernel; the
   ambient team is the whole subject of DR-42.
3. **A performance statement at target mesh size with the thread count pinned
   and stated.** Not a ratio against Python on a 133-edge grid, and not a
   container figure quoted as a host measurement.

## 2. What already exists (and is not to be rebuilt)

- **Tier 1, the bit-parity suite:** `tests/test_cpp_parity.py` — 10 test
  functions (`:218`, `:234`, `:419`, `:437`, `:549` and five more), 13 collected
  tests: 3 on the v1 golden and 10 on the v2 full-physics golden, the 10 being 7
  functions one of which — `:497` — is parametrised over four single-branch
  ablations (`README.md:88-93`). It skips rather than passes when `emfit_core` is not
  importable, and says why (`tests/test_cpp_parity.py:3-8`).
- **The flag line the parity was measured with:** `-O2 -fno-fast-math
  -ffp-contract=off -fopenmp` (`src/CMakeLists.txt:55`). The rationale is at
  `src/CMakeLists.txt:20-26`: `-ffast-math`/`-fassociative-math` reassociate,
  and GCC's default `-ffp-contract=fast` fuses `a*b + c` into one FMA where the
  reference rounds twice. **That is measured, not feared:** an `-mfma` build
  (contraction on) emits 3 `vfmadd` instructions and fails 8 of the 13 tests at
  max |diff| **2.3e-13**; with `-ffp-contract=off` it emits 0 FMAs and all 13
  pass bit-for-bit (`src/CMakeLists.txt:24-26`;
  `docs/design/GEN12_HANDOFF_TRAPS.md:461`, `:469`, `:489`). `-O2` is kept
  because that is the configuration the parity was actually measured in.
- **A rebuild command that matches it:** `tests/test_cpp_parity.py:82-89`
  (`/usr/bin/g++ -O2 -fno-fast-math -ffp-contract=off -fopenmp -std=c++17
  -shared -fPIC ...`), with the note that the `.so` must live inside the
  workspace because `/tmp` is `noexec` (`:80-81`).
- **`-mfma` is on no build line.** It appears only in prose explaining why it
  must not be added: `src/CMakeLists.txt:24`,
  `docs/design/GEN12_HANDOFF_TRAPS.md:467`,
  `docs/design/cpp-kernel-status-2026-11-09.md:376`, `:451`, `README.md:132`.

## 3. What does not exist

Each of these is absent on disk, checked in this container, not merely
unmentioned:

- **The ULP-bound suite on reductions.** `tests/test_cpp_parity_reduction.py`
  does **not** exist. Tier 1 is whole-step bit parity; there is no file that
  bounds a reduction by an ULP count, and none that varies the thread count and
  bounds the spread. Phase 2 item 1 is therefore new work and has no scaffold.
- **Thread pinning at the kernel entry point.** `emfit/_env.py:44-70`
  (`pin_threads`) sets `OPENBLAS_NUM_THREADS`, `OMP_NUM_THREADS`,
  `MKL_NUM_THREADS` and `NUMEXPR_NUM_THREADS` — `emfit/_env.py:35-40` — when
  they are unset, and is called from `emfit/__init__.py:35`, `:37`, `:39`. That
  is **environment-variable hygiene, and it only fires if the caller imported
  `emfit` first.** There is no `sched_setaffinity`, no `omp_set_num_threads`
  call in the binding, and no `cpu_count`/`taskset` anywhere in `emfit/`,
  `scripts/`, `tests/` or `evidence/termination/run_build_A.py` (zero greps).
  A caller that loads the `.so` directly, or that sets `OMP_NUM_THREADS=12`
  itself, still gets 12 threads.
- **Any performance statement that phase 2 could inherit.** See §4.

## 4. Preconditions, stated as things that must be true before a claim is made

1. **The flags are read from the build, not from a document.** Any figure must
   name the `target_compile_options` line it was built under
   (`src/CMakeLists.txt:55`) or the `g++` command (`tests/test_cpp_parity.py:83`)
   — and those two must agree before either is quoted.
2. **The thread count is pinned by the kernel and stated on the figure.** DR-42
   is OPEN (`docs/design/defect_register.md:783`, status `:787`): 3.71 us per
   call at one thread, 291 us on the default team, against 8.84 us for the
   Python step (`docs/design/defect_register.md:805-809`), and the ladder is
   monotonically worse with more threads — 3.8 / 19.6 / 54.3 / 145.6 / 351.5 us
   at 1 / 2 / 4 / 8 / 12 threads (`docs/design/defect_register.md:811`). No
   figure may be quoted without its thread count until that is repaired.
3. **A speed figure is arithmetically checked before it is quoted.**
   `artifacts/ladder_engine_host_timing.json` states `speedup` 1.81, and its own
   `checks.speedup` says "ARITHMETIC: 49.62 / 27.44 = 1.808, reported as 1.81" —
   that one holds. Its `thread_count` is `{"value": 1, "status":
   "OPERATOR-ATTESTED", ...}`: an inference from `pin_threads`, not a
   measurement, and it must be carried as such.
4. **A container figure is not a host figure.** E8's build and the parity run
   are `[CONTAINER]`; `docs/design/GEN12_HANDOFF.md:91` states the rule ("No
   `[CONTAINER]` figure may be quoted as a measurement"). `README.md:50-52` is
   the same distinction on the build claim, marked OPERATOR-REPORTED.
5. **Nothing in phase 2 may weaken a tier-1 test.** The `-mfma` measurement at
   2.3e-13 is the reason: 8 of 13 tests fail on a single rounding change, so a
   test relaxed "to make a new build pass" would be the one thing that could
   hide a real regression.

## 5. Contradictions on the record — four, all resolved 2026-11-12

Four inconsistencies were found while collecting the citations above. Each was
written down so phase 2 would start from the disputed pair rather than from
whichever half it happened to read first, and every original sentence is kept
verbatim so the pair stays legible. All four were re-checked on 2026-11-12 and
each now carries a `RESOLVED 2026-11-12` paragraph naming what was measured and
what remains unsupported. One premise in the original text is now known to be
false — §5.2's "`.git` in this container is 0 bytes" — and it is corrected in its
resolution rather than edited out of the paragraph above it.

1. **The build command contradicts the build file, in one sentence.**
   `docs/design/GEN12_HANDOFF.md:93` gives `g++ -O3 -fopenmp -std=c++17
   -shared -fPIC -Wall -Wextra` (citing `cpp-kernel-status-2026-11-09.md:15-28`)
   **and, in the same sentence,** "src/CMakeLists.txt:55 pins `-O2
   -fno-fast-math -ffp-contract=off -fopenmp`". The two are different builds:
   `-O3` with contraction at its default is exactly the configuration
   `src/CMakeLists.txt:24-26` measured as failing 8 of 13. Which command
   produced the "zero warnings" claim is not determinable from the line.

   **RESOLVED 2026-11-12 — the binary settles it, and the answer is `-O2`.**
   The question "which command produced this `.so`" is answerable from the build
   tree that produced it. `artifacts/cpp_build_e3/CMakeFiles/emfit_core.dir/flags.make:9`
   records the compile line that was used: `CXX_FLAGS = -O3 -DNDEBUG -std=c++17
   -fPIC -fvisibility=hidden -O2 -fno-fast-math -ffp-contract=off -fopenmp
   -flto=auto -fno-fat-lto-objects -fopenmp`. The `-O3` comes from
   `CMAKE_CXX_FLAGS_RELEASE` (`artifacts/cpp_build_e3/CMakeCache.txt:51`; build
   type `Release`, Unix Makefiles, CMake 4.4.4) and the `-O2` from
   `src/CMakeLists.txt:55`. The later flag wins, so the effective optimisation
   level is **`-O2`**, and the half of `docs/design/GEN12_HANDOFF.md:93` that
   pins `-O2 -fno-fast-math -ffp-contract=off -fopenmp` is the half that
   describes the binary; the `g++ -O3 -fopenmp -std=c++17 -shared -fPIC -Wall
   -Wextra` half describes a command that was not used. This is also a
   byte-identity question, not a provenance one: the extension that is actually
   installed and dispatched, under `.venv/lib/python3.12/site-packages/`, is
   188,416 bytes with sha256 `1365c7aa…` and is byte-identical to the `.so`
   left in `artifacts/cpp_build_e3/`. That build used `g++` 14.2.0 with LTO on
   (`-flto=auto`), and carries no `-mfma`, no `-march=`, no `-ffast-math` — none
   of those three appears anywhere in this tree. The claim the original
   sentence was asked to support is still unsupported, but now for a measured
   reason: neither `-Wall` nor `-Wextra` is on the recorded compile line, so
   "zero warnings" does not describe this build either.
2. **Commit `6cbb89d` cannot be checked.** It is cited at
   `docs/design/defect_register.md:791` as the commit whose mechanism claim DR-42
   withdraws, and `.git` in this container is 0 bytes, so neither its diff nor
   its existence is verifiable here. The register's statement about it stands as
   the record's own; this scope document adds nothing to it.

   **RESOLVED 2026-11-12 — it checks out, and checking it removes the "cannot be
   checked" caveat.** The premise above is stale: the commit is readable now.
   `6cbb89d` is `6cbb89dbcf323b70634d2cd64441ae38557b5e28`, Thu Nov 12 08:30:29
   2026 +0000, "perf(e3): run FITStepper.step on the C++ kernel (Phase 1)".
   `[MEASURED]` Its diff adds `_load_kernel`, `_KERNEL`, `_ACTIVE_STEP` and
   `_KernelPlan` together with the dispatch inside `FITStepper.step`; adds
   `KERNEL_ABI = 1` and `KERNEL_NAME` to `src/bindings.cpp`; changes
   `src/CMakeLists.txt` from `-O3 -fopenmp` to `-O2 -fno-fast-math
   -ffp-contract=off -fopenmp`; adds `tests/test_cpp_dispatch.py` (5 tests); and
   moves `tests/test_cpp_parity.py`'s BUILD_COMMANDS from `-O3` to `-O2`. So it
   is the commit that put the kernel on the call path, which is what its subject
   says, and it is the origin of the flag line §5.1 is about. The message also
   carries one claim that was true when it was written and false eleven minutes
   later: it says the installed extension "predates the marker" and is therefore
   refused. That was true at 08:30:29 — the `.so` in `build/` carries no
   `KERNEL_ABI` and is a GCC 13.3 build — and stopped being true at 08:41:06,
   when the installed extension was replaced by the ABI-1 build. What the
   dispatcher does today is measured, not assumed: `emfit.engine_report()`
   returns `{'step_engine': 'cpp', 'kernel_abi': 1, 'kernel_name':
   'emfit_core.fit_leapfrog'}`, and the module-level `_ACTIVE_STEP` is `'cpp'`.
   Both the commit's sentence and the pre-08:41 state are preserved in the
   record; a reader only has to know which time each was true.
3. **"2.15x slower" is an arithmetic mismatch, and it is also the wrong
   direction.** `artifacts/ladder_engine_host_timing.json` marks the claim
   `"status": "ARITHMETIC MISMATCH - 2.15 does not follow from any pair of the
   published container figures"` and recomputes two admissible ratios:
   **2.12** (58.04084487300133 / 27.44 = 2.115) and **1.57**
   (43.200629351020325 / 27.44 = 1.575). The two arms are 1.34x apart from each
   other, so "the container" is not one number at all; the second correction
   entry marks the same claim "NOT SUPPORTED for python" and recomputes
   50.11570404301165 / 49.6 = **1.01**.

   **RESOLVED 2026-11-12 — the banked file's own standing consequence is
   adopted, and this document quotes no single figure for the penalty.**
   `artifacts/ladder_engine_host_timing.json` carries a `corrections` block
   (lines 51-83) with two entries. The first reads, verbatim: `"claim":
   "container is 2.15x slower for cpp"`, `"status": "ARITHMETIC MISMATCH - 2.15
   does not follow from any pair of the published container figures"`, then
   `"why_two_arms"`: "1.34x apart, so the container side of this comparison is
   only resolved to roughly +/-34%", and `"standing_consequence"`: "The
   container-vs-host cpp penalty is therefore somewhere between 1.57x and 2.12x
   on the published numbers. Nobody should quote a single figure for it until
   the same thread pinning is applied to both sides." The second entry marks the
   general form of the claim `"NOT SUPPORTED for python"` and recomputes
   50.11570404301165 / 49.6 = 1.01. Two consequences bind phase 2. First,
   quoting one container-vs-host number is forbidden by the banked file itself,
   not merely by this document's preference. Second, any future comparison must
   pin threads identically on both sides, and it does not yet: the host arm's
   thread count is OPERATOR-ATTESTED at 1, while the container arm is measured
   under a `cpu.max 50000/100000` cgroup (`docs/design/defect_register.md:813`),
   so the two arms are not the same experiment.
4. **The ledger says no speed figure exists; DR-42 has three.** E3's row reads
   "No speed figure exists for the kernel" and "about 50x *slower* at the golden
   grid size" with 5,926 / 49,252 / 124,111 / 353,937 ns per call at 1 / 2 / 4 /
   8 threads (`docs/design/EM_SOLVER_LEDGER.md:28`), while
   `docs/design/defect_register.md:805-809` records 3.71 us / 291 us / 8.84 us on
   the same grid. Both cannot be the same grid and the same build; the ledger row
   predates DR-42's re-measurement, but neither page says so.

   **RESOLVED 2026-11-12 — two different grids, therefore no contradiction; the
   self-contradiction is inside the ledger row.** The sentence "Both cannot be
   the same grid and the same build" is correct, and it is the whole answer:
   they are not the same grid. `docs/design/defect_register.md:805-809` measures
   the kernel step in isolation on the **golden grid** (133 edges, 392 nonzeros)
   in a container on 2026-11-12; `docs/design/EM_SOLVER_LEDGER.md:28` speaks
   about a **board-shaped mesh**, and says so itself four sentences later: "the
   verdict stays UNVERIFIED — no speed figure at a board-shaped mesh exists. The
   only figure measured is a bit-identity check plus a 1.76x wall clock on a
   560-edge toy; that is a weak upper bound and must not be quoted as a
   board-size claim." So "No speed figure exists for the kernel" is a statement
   about board-shaped meshes, qualified inside the same cell, and a
   microbenchmark on a 133-edge grid does not contradict it. What is genuinely
   wrong is also inside that cell: it denies a speed figure exists while
   printing 5,926 / 49,252 / 124,111 / 353,937 ns per call as one. That is the
   ledger's defect to fix and `§6` keeps E3's verdict out of scope here; all this
   document records is that the two pages are not in conflict.

## 6. Out of scope for phase 2

- **Changing the flag line to buy speed.** `-O3`, `-ffast-math`, `-march=native`
  and `-mfma` are all out: each moves a rounding, and 2.3e-13 is enough to fail
  8 of 13 (`src/CMakeLists.txt:24-26`). Phase 2 may *measure* an alternative
  build; it may not adopt one without a tier-1 result to go with it.
- **Moving E3's verdict.** DR-42 and `EM_SOLVER_LEDGER.md:28` own that, and
  both stay as they are until a pinned-thread figure at target mesh size exists.
- **Any edit to `src/`, `src/CMakeLists.txt`, `tests/test_cpp_parity.py` or the
  goldens.** Phase 2 is additive: new files, new bounds, no rewritten tier 1.
- **A benchmark harness in this document.** No timing was run for it, and a
  scope document that shipped numbers would be the defect DR-42 is about.

## 7. How to check this document

Each citation above is a `file:line` in this tree, readable without a compiler:
`sed -n '20,30p;50,58p' src/CMakeLists.txt`, `sed -n '783,821p'
docs/design/defect_register.md`, `sed -n '33,72p' emfit/_env.py`,
`python3 -c "import json;d=json.load(open('artifacts/ladder_engine_host_timing.json'));print(d['corrections'])"`.
The one claim that cannot be checked here is the operator host's build
(`README.md:50-52`); it is marked as cited rather than verified and is not
load-bearing for the scope. The commit identity `6cbb89d` (§5.2) was checked on
2026-11-12 and is no longer on that list. The flag line can be re-read without a
compiler: `sed -n '9p' artifacts/cpp_build_e3/CMakeFiles/emfit_core.dir/flags.make`.
