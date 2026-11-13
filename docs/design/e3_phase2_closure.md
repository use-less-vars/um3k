# E3 Phase 2 — closing the kernel flag question

**Status: CLOSED, 2026-11-13.** Scope: does the E3 speedup survive a change of optimisation level, of link-time optimisation, and of instruction-set targeting, and is the banked 27.44 s figure reproducible?

## 1. Summary

- **Parity is exact** under both `-O3` and `-flto=auto`: 13 of 13 in `tests/test_cpp_parity.py`, bit-for-bit, not `allclose`.
- **The speedup over the numpy stepper is 1.37x**, measured with both arms in one session on the operator's host: 34.74 s against 47.55 s (`docs/design/e3_dr42_closure_benchmark.md:13-17`).
- **The banked 27.44 s is retired as a target.** Its producing build is unidentified — no flags, no `argv`, no revision (`artifacts/ladder_engine_host_timing.json`) — and none of the six mechanisms examined in section 5 reproduces it.
- **No further flag work is warranted.** Phase 2 ends here; E13 (antennas) and DR-43 (S-parameter schema versioning) are next.

## 2. The arms built and tested

All three were built from these exact source bytes: `src/emfit_core.cpp` sha256 `fa6b00cf0437ddb489fdb21ed828a913d1841f64bae1d9dbc6c31a3d179dfd77`, `src/bindings.cpp` sha256 `45e60f6431c0f172cc8293ee84484c169dea54ef772d52a687650aa894984d3e`. Only the flag line differs.

| arm | distinguishing flags | size (bytes) | sha256 | 13-test parity |
|---|---|---|---|---|
| `o2` | `-O2` | 275640 | `86e42325154f5c640b63178b6207cef7c4394aa0383402048d1c0c2dd35ee719` | 13 passed, 0.37 s |
| `o3` | `-O3` | 268976 | `74f652c0d14d6b45afabeae0aa927921cdb0457b3797847942550bf73a2d5320` | 13 passed, 0.37 s |
| `o2lto` | `-O2` plus `-flto=auto -fno-fat-lto-objects` | 275472 | `be894876b3c14f43dda10cc882f0ba9d050301fd2a50dd94bdbfbc0fa96921fb` | 13 passed, 0.37 s |

The two command lines, reproduced here because `build/` is ignored by git (`.gitignore:11`) and so the provenance files under `build/phase2/` are not in the tree:

```
g++ -O2 -fno-fast-math -ffp-contract=off -fopenmp -std=c++17 -shared -fPIC -I.venv/lib/python3.12/site-packages/pybind11/include -I/usr/local/include/python3.12 src/emfit_core.cpp src/bindings.cpp -o build/phase2/o2/emfit_core.cpython-312-x86_64-linux-gnu.so
g++ -O2 -fno-fast-math -ffp-contract=off -fopenmp -std=c++17 -shared -fPIC -I.venv/lib/python3.12/site-packages/pybind11/include -I/usr/local/include/python3.12 -flto=auto -fno-fat-lto-objects src/emfit_core.cpp src/bindings.cpp -o build/phase2/o2lto/emfit_core.cpython-312-x86_64-linux-gnu.so
```

The `-O3` arm is the first line with `-O3` in place of `-O2`. Compiler `g++ (Debian 14.2.0-19) 14.2.0`, Python 3.12.15, pybind11 headers 3.1.0.

## 3. The parity gate

`tests/test_cpp_parity.py` is an exact gate, not a tolerance gate: the comparison is `np.testing.assert_array_equal` (`:210`) and the docstring says so in terms of "not `allclose`" (`:27`). The meta-test `test_bit_comparison_sees_a_one_ulp_difference` (`:549`) demonstrates that the comparison fires on a single ULP, so a pass is evidence and not a vacuum.

Result: `-O3` and `-flto=auto` both pass 13 of 13, bit-for-bit, at 0.37 s. **Neither moves the arithmetic.** Both are numerically admissible.

The admissible set is bounded on the other side too: `-mfma` is not in it. A contraction build emits three `vfmadd` instructions and fails 8 of the 13 tests (recorded in the message of commit `6cbb89d`, which is why `-ffp-contract=off` is in every flag line since).

## 4. Timing: what is defensible and what is not

### 4.1 Defensible — the same-session ratio

34.74 s against 47.55 s, five runs each, both arms in one session on the operator's host (2026-11-13, `docs/design/e3_dr42_closure_benchmark.md:13-17`): **1.37x**.

### 4.2 Not defensible — cross-session absolutes

The same `.venv` `-O3` binary, run in two sessions:

| session | the five runs (s) | mean (s) | sample sd (s) |
|---|---|---|---|
| 2026-11-13 | 30.6, 33.9, 31.2, 36.9, 41.3 | 34.78 | 4.42 |
| 2026-11-14 | 31.4, 33.2, 29.8, 30.0, 30.0 | 30.88 | 1.45 |

Identical bytes, 11.2 per cent apart (30.88 / 34.78 = 0.888). The host's day-to-day spread is larger than any compiler-flag effect measured in this phase.

This is why a 1.54x figure must not be recorded. 47.55 / 30.88 = 1.54 divides today's C++ arm by yesterday's Python arm. If the Python arm drifted with the machine — and there is no reason to think a numpy loop is immune when the kernel is not — then today's Python arm would have run at 47.55 x 0.888 = 42.22 s and the ratio would be 42.22 / 30.88 = 1.37x, unchanged. The ratio is invariant to machine drift; the absolute is not. Quoting 1.54x would repeat, in a new form, exactly the cross-session arithmetic that produced the 27.44 s ghost.

### 4.3 The container's contribution — not transferable

Per-step cost derived from two step counts in the container (200 and 800 steps, interleaved): `o2` 23.26 ms, `o3` 18.12 ms, `o2lto` 16.21 ms per step. The `-O3` figure (0.779x of `o2`) contradicts the host's measurement of the same flag on the same sources and is therefore reported as a failed control. The container's CPU quota is 1.0 (`cpu.max` measured as `100000 100000`) and its arms drift monotonically within a block. No container timing from this phase is used in any claim above.

## 5. The 27.44 s figure: six mechanisms examined

| # | mechanism | evidence | verdict |
|---|---|---|---|
| 1 | different workload (structure C against structure A) | the `--structure` letter selects only the termination; the mesh is hard-coded in `build_kwargs` (`evidence/termination/run_build_A.py:1668-1770`), so all four arms are 62 x 212 x 22 = 289168 cells with `nnz(curl) = 3546704`, measured, ratio 1.0000 | EXCLUDED |
| 2 | `-O3` against `-O2` | 34.78 s against 34.74 s on the host, five runs each | EXCLUDED |
| 3 | the ABI 2 thread pin | commit `0c8da31` changed only the five pragma clauses, an include and two accessors — no loop body, no allocation. The clause is evaluated once per region entry, and a step enters 3 to 5 regions, so 7200 to 12000 evaluations per 2400-step run. The 12-thread arm measured 34.6 s against 34.74 s | EXCLUDED |
| 4 | `-march=native` | absent from every build file, script and record in the tree; the archived CMake build resolves to `-march=x86-64` (`artifacts/cpp_build_e3/CMakeFiles/emfit_core.dir/flags.make:9`); forbidden by `docs/design/e3_phase2_scope.md:236` and `README.md:136` | NO EVIDENCE |
| 5 | link-time optimisation | the one recorded difference: the archived CMake line carries `-flto=auto -fno-fat-lto-objects` and every hand-built arm does not. Parity exact, but no host timing exists — the isolation attempt failed (section 6.1) | UNTESTED ON HOST |
| 6 | machine state | 11.2 per cent drift measured on identical bytes between two sessions; sufficient in magnitude to account for the whole gap | NOT EXCLUDED |

**Conclusion: 27.44 s is retired.** It is a historical artefact of an unidentified build on an unidentified machine state, not a target. The reproducible performance claim is the same-session 1.37x of section 4.1.

## 6. Method lessons recorded

### 6.1 The editable-install trap

`PYTHONPATH=<dir>` does not select a candidate `.so` when the project is installed editable: a PEP 660 finder (`_editable_skbc_emfit.py`) sits in `sys.meta_path`, which is consulted before `sys.path`. The symptom is a probe printing the site-packages path: the two arms then measure one binary and the comparison is void. Always print `emfit_core.__file__` before timing, and select an arm either by byte-verified swap in site-packages or by removing the finder for the run.

### 6.2 A within-session sigma cannot test a between-session gap

`docs/design/defect_register.md:801` derives "20 sigma" from 7.3 / 0.37, using the banked within-session spread to judge a gap between sessions. That inference is invalid, and it is the arithmetic that created the ghost.

### 6.3 Block ordering confounds

Arms must alternate. In the container run, three consecutive runs at one fixed step count gave 4.81, 5.80 and 6.73 s of call time — a monotone drift larger than the effect sought.

### 6.4 Provenance files under `build/` are not in the tree

`.gitignore:11` ignores `build/`, so both compile-command files are untracked. That is why the command lines are reproduced verbatim in section 2.

## 7. Decisions

- **7.1 Flags.** The working `.venv` kernel stays at `-O3`: parity is exact and no penalty was measured. **Action required:** `src/CMakeLists.txt:55` still records `-O2 -fno-fast-math -ffp-contract=off -fopenmp`, so the shipped binary's flags are not the recorded flags. DR-42 gate (e) requires that they agree. Resolve in its own commit by either rebuilding from the recorded line or changing the line to `-O3` and rerunning the 13 tests. Do not leave the mismatch in place. The shipped binary does not byte-match any arm in section 2 either: `.venv/lib/python3.12/site-packages/emfit_core.cpython-312-x86_64-linux-gnu.so` is 288696 bytes, sha256 `8145b7c834edb0d79bba9823ba40e3b371d73ae43e16c4e97ba32086dd2a6403`, built by the operator's host compiler, so its `-O3` is operator-attested and not recorded.
- **7.2 SIMD.** Not pursued. No `-march` or `-mavx` in any build; forbidden by the scope document; and `-mfma` demonstrably fails 8 of 13 parity tests, so the arithmetic risk is not worth an unmeasured gain.
- **7.3 LTO.** Not pursued. Parity is exact but no host timing exists, and the only measurement is a container slope whose control failed.
- **7.4** No document may cite 27.44 s as a performance target again.
- **7.5 Next.** E13 (antennas) and DR-43 (S-parameter schema versioning gap).

## 8. What would reopen this question

A host session with (a) arms selected by byte-verified `.so` swap and an `__file__` proof printed into the artefact, (b) the C++ and numpy arms interleaved in the same session, (c) five or more pairs, medians reported. That would settle LTO and give a drift-free ratio.
