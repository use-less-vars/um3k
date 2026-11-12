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

## 5. Contradictions on the record — recorded, not resolved here

Four inconsistencies were found while collecting the citations above. Each is
written down so phase 2 starts from the disputed pair rather than from whichever
half it happened to read first. **None is resolved by this document.**

1. **The build command contradicts the build file, in one sentence.**
   `docs/design/GEN12_HANDOFF.md:93` gives `g++ -O3 -fopenmp -std=c++17
   -shared -fPIC -Wall -Wextra` (citing `cpp-kernel-status-2026-11-09.md:15-28`)
   **and, in the same sentence,** "src/CMakeLists.txt:55 pins `-O2
   -fno-fast-math -ffp-contract=off -fopenmp`". The two are different builds:
   `-O3` with contraction at its default is exactly the configuration
   `src/CMakeLists.txt:24-26` measured as failing 8 of 13. Which command
   produced the "zero warnings" claim is not determinable from the line.
2. **Commit `6cbb89d` cannot be checked.** It is cited at
   `docs/design/defect_register.md:791` as the commit whose mechanism claim DR-42
   withdraws, and `.git` in this container is 0 bytes, so neither its diff nor
   its existence is verifiable here. The register's statement about it stands as
   the record's own; this scope document adds nothing to it.
3. **"2.15x slower" is an arithmetic mismatch, and it is also the wrong
   direction.** `artifacts/ladder_engine_host_timing.json` marks the claim
   `"status": "ARITHMETIC MISMATCH - 2.15 does not follow from any pair of the
   published container figures"` and recomputes two admissible ratios:
   **2.12** (58.04084487300133 / 27.44 = 2.115) and **1.57**
   (43.200629351020325 / 27.44 = 1.575). The two arms are 1.34x apart from each
   other, so "the container" is not one number at all; the second correction
   entry marks the same claim "NOT SUPPORTED for python" and recomputes
   50.11570404301165 / 49.6 = **1.01**.
4. **The ledger says no speed figure exists; DR-42 has three.** E3's row reads
   "No speed figure exists for the kernel" and "about 50x *slower* at the golden
   grid size" with 5,926 / 49,252 / 124,111 / 353,937 ns per call at 1 / 2 / 4 /
   8 threads (`docs/design/EM_SOLVER_LEDGER.md:28`), while
   `docs/design/defect_register.md:805-809` records 3.71 us / 291 us / 8.84 us on
   the same grid. Both cannot be the same grid and the same build; the ledger row
   predates DR-42's re-measurement, but neither page says so.

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
The two claims that cannot be checked here are the commit identity
(`6cbb89d`, §5.2) and the operator host's build (`README.md:50-52`); both are
marked as cited rather than verified, and neither is load-bearing for the scope.
