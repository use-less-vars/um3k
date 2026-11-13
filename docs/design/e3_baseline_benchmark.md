# E3 baseline benchmark — five runs per arm in the container, and why 1.81x does not reproduce there

**Dispatch:** S5a, commit 2 of 2.
**Author:** agent, single writer for this file.
**Status:** measurement record. No verdict is moved here, no build is recommended, and nothing in `docs/design/e3_phase2_scope.md` §6 is superseded.
**Amendment rule:** later additions go in a dated Amendment section at the end. Nothing above is edited.
**Written:** `date -u` in container `sweep` returned `Fri Nov 13 00:58:33 UTC 2026` at write time. The container clock reads 2026-11-13; the operator's date for the surrounding work is 2026-11-12. Both are named so the two records can be joined; the discrepancy is the clock's.

## §1 Why this is its own file, and what it may not be used for

`docs/design/e3_phase2_scope.md:244-245` puts a benchmark harness out of scope for the phase-2 document with the reason attached: "A benchmark harness in this document. No timing was run for it, and a scope document that shipped numbers would be the defect DR-42 is about." The timings therefore live here, in a file whose only business is timings, and the scope document keeps pointing at the rule instead of at a number.

`e3_phase2_scope.md:240-241` reserves the verdict: "Moving E3's verdict. DR-42 and `EM_SOLVER_LEDGER.md:28` own that, and both stay as they are until a pinned-thread figure at target mesh size exists." This file does not move that verdict. It reports what one container measured in the condition DR-42 asks for (`OMP_NUM_THREADS=1`), and §6 says why that still does not settle the question.

The labelling rule is `docs/design/GEN12_HANDOFF.md:91`, quoted rather than paraphrased, because every timing below is on the wrong side of it:

> No `[CONTAINER]` figure may be quoted as a measurement. A `[HOST]` figure is quotable with its provenance and its thread count attached.

Tags used here: `[MEASURED]` a real invocation, located in §2.5; `[CONTAINER]` measured inside this container — orthogonal to `[MEASURED]`, and both apply to every timing in this file; `[ARTEFACT path:line]` read from a committed file; `[ARITHMETIC: …]` derived with the expression shown; `[INFERRED]` argument from tagged numbers.

## §2 What was run

### 2.1 The command

One process per invocation, strictly sequential, no two runs overlapping:

```
cd /workspace && PYTHONPATH=/workspace/.venv/lib/python3.12/site-packages \
  python3 evidence/termination/run_build_A.py --structure C --out /tmp/S5a_cpp_$i.json
```

The python arm adds `--force-python`. The pinned batches prefix the four thread variables at the value in §3 (`OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS`, `NUMEXPR_NUM_THREADS`).

The container also hosted the agent process that issued these commands. That process is not measured, its load is not controlled across batches, and §5.4 shows what that costs.

### 2.2 The grid and the physics are identical in all 23 runs

Every artefact reports the same grid: `label=C`, `cells=289168` (62x212x22, 0.4 mm), `nsteps=2400`, `dt=7.626299478123987e-13`, netlist `evidence/termination/netlists/load_stub.json` with the `series_r` termination replaced. All 23 exited 0, and `grep -c Traceback` is 0 in all 23 log files (7 lines each) — no run was cut short, so no wall time here is a fake fast one.

Physics is bit-identical across all 23: `s21['magnitude']` = 0.6361234402945529, `arg(s21)` = 47.5181°, `|s11|` = 8.559564e-01, one-wave-station fit 8.556215e-01, `cut_plane` = 51, passivity 1.137314464146 against tolerance 4.0e-09 giving `passivity_status=FAIL_PASSIVITY`. That passivity failure is the standing state of structure C. It is named here only so that it is not read as a regression caused by running the benchmark; nothing in this file investigates it, and no AC in this file is derived from it.

### 2.3 Was the kernel loaded — answered per run, from the artefact

`meta.step_engine` is `'cpp'` in all 13 cpp artefacts, with `meta.kernel_name` = `emfit_core.fit_leapfrog` and `meta.kernel_abi` = 1. It is `'python'` in all 10 python artefacts, with `kernel_name` and `kernel_abi` both null.

The engine is therefore recorded per run rather than asserted per batch, which matters because `--force-python` and a failed import look the same from the outside. The ABI gate that makes the record trustworthy is `emfit/evolve.py:271` (`getattr(kernel, "KERNEL_ABI", _KERNEL_ABI) != abi`), and the module actually imported was `/workspace/.venv/lib/python3.12/site-packages/emfit_core.cpython-312-x86_64-linux-gnu.so`, 188416 B, whose `readelf -d` NEEDED list carries `libgomp.so.1` and whose `ldd` resolves it to `/lib/x86_64-linux-gnu/libgomp.so.1` with no missing dependency `[MEASURED]`. That 188416-byte module is the one `docs/design/e3_phase2_scope.md:129-150` records as byte-identical to the `artifacts/cpp_build_e3` build.

So: the kernel was loaded in every cpp run, and OpenMP is linked in, not merely pragma-annotated.

### 2.4 The machine

`nproc` = 12 and `len(os.sched_getaffinity(0))` = 12, but `/sys/fs/cgroup/cpu.max` = `100000 100000`, i.e. a 1.0 CPU quota against a 12-vCPU view `[MEASURED]`. That ratio is not recorded for the earlier session's artefacts (`artifacts/ladder_engine_scaling.json` has no such field), so the two sessions' quotas cannot be compared.

### 2.5 The artefacts

`/tmp` is not committed. All 23 JSON files were written between 00:30:42Z and 00:57:58Z by the container clock, each with a sibling `.log`.

| batch | files | bytes | written (container clock) |
|---|---|---|---|
| A `cpp` | `/tmp/S5a_cpp_{1..5}.json` | 22867, 22866, 22864, 22868, 22868 | 00:30:42 – 00:33:41 |
| B `python` | `/tmp/S5a_py_{1..5}.json` | 22890, 22887, 22885, 22888, 22887 | 00:35:15 – 00:38:49 |
| C `cpp` pinned | `/tmp/S5a_cpp_pin_{1..5}.json` | 22874, 22873, 22873, 22874, 22872 | 00:40:59 – 00:43:34 |
| D `python` pinned | `/tmp/S5a_py_pin_{1..5}.json` | 22897, 22896, 22896, 22894, 22896 | 00:45:10 – 00:48:18 |
| E `cpp` 12 threads | `/tmp/S5a_cpp_omp12_{1..3}.json` | 22878, 22879, 22880 | 00:52:11 – 00:57:58 |

## §3 Four batches of five, and one stress arm of three

All times are `meta.wall_total_s` in seconds: the whole process, which is the quantity the host record (`artifacts/ladder_engine_host_timing.json:9-20`) also measures. `meta.wall_call_s` excludes import and setup and runs 0.48 s to 0.83 s lower; the two never cross, so the choice does not affect any figure in this file.

| batch | arm | four thread vars at exec | runs 1..5 (s) | mean | σ pop | σ sample | cv |
|---|---|---|---|---|---|---|---|
| A | cpp | unset, pinned at import (§4.1) | 39.508 44.116 41.998 49.918 42.566 | **43.621** | 3.480 | 3.891 | 8.0% |
| B | python | unset, pinned at import | 60.984 50.950 50.886 57.114 54.340 | **54.855** | 3.845 | 4.299 | 7.0% |
| C | cpp | all four = 1 | 37.709 38.146 38.491 37.869 39.223 | **38.288** | 0.538 | 0.601 | 1.4% |
| D | python | all four = 1 | 47.442 47.413 48.810 43.875 47.684 | **47.045** | 1.665 | 1.861 | 3.5% |
| E | cpp | all four = 12 (stress, n = 3) | 171.344 171.610 174.652 | **172.535** | 1.501 | 1.838 | 0.9% |

Batch E is a deliberate stress arm, not a baseline. It exists because §4 needs it; no ratio in §5 uses it except the one that measures the thread lever.

The three numbers a reader wants first, all `[CONTAINER]`: cpp at one thread **38.288 s** (σ 0.538), python at one thread **47.045 s** (σ 1.665), and their quotient **1.229**.

## §4 The thread count is a 4.5x lever, and every baseline run here used one thread

### 4.1 The pin

`emfit/_env.py:44-70 pin_threads` sets each of `OPENBLAS_NUM_THREADS`, `OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `NUMEXPR_NUM_THREADS` to `'1'` when it is unset, and `emfit/__init__.py:35-37` calls it as the first statement after the module docstring, before numpy is imported. `docs/design/GEN12_HANDOFF.md:85` already relies on this ("called at `emfit/__init__.py:33-37` before numpy is imported, pins `OMP_NUM_THREADS` to 1 at package import").

This session measured the mechanism rather than re-reading it `[MEASURED]`. In a fresh interpreter with all four variables removed: `import emfit` leaves `/proc/self/maps` free of libgomp while `os.environ['OMP_NUM_THREADS']` is already `'1'`; libgomp appears in the maps only after `import emfit.evolve`. Since libgomp reads `OMP_NUM_THREADS` in its library constructor, the order is what makes the pin real — the `putenv` precedes the `dlopen`. `emfit/__init__.py` imports no submodule other than `._env` (its only import line is 35), so this ordering holds on every path that goes through the package.

### 4.2 A withdrawal, dated

An earlier note in this session's planning assumed batch A had run under an unpinned OpenMP default team of 12 threads, which would have made A an invalid comparison against the host's operator-attested one thread. That assumption is withdrawn as of 2026-11-13T00:58Z, on two grounds: §4.1 shows the pin precedes libgomp in every batch, and §4.3 shows a 12-thread team costs a factor 4.51, not the factor 1.139 that separates A from C. The sentence is recorded rather than deleted because it changes what §5 is allowed to claim: the A-versus-C difference is not a thread effect and may not be explained away as one.

### 4.3 What a team actually costs

Three runs with all four variables set to 12: 171.344, 171.610, 174.652 s; mean 172.535, σ 1.501, σ sample 1.838. Against the pinned one-thread cpp arm, `[ARITHMETIC: 172.535247 / 38.287688 = 4.506]`; against the banked host cpp figure, `[ARITHMETIC: 172.535247 / 27.44 = 6.288]`. `peak_rss` is 359.0–359.6 MB, the same as the one-thread cpp runs (359.1 MB), so the cost is contention on the 1.0 CPU quota, not memory. Note that `peak_rss` tracks the engine and not the team — cpp is ~359 MB at both 1 and 12 threads, python ~314 MB — so it is not evidence either way about the team.

Two consequences. A thread count is worth a factor of 4.5 on this workload, which is larger than the 1.81 the record is arguing about; and any kernel figure that does not state its thread count is not a figure. `GEN12_HANDOFF.md:85` closed with "a many-thread figure is still unmeasured and must not be inferred from this one" — one now exists as `[CONTAINER]`, and it points the other way from a speedup.

## §5 The 1.81x, and what the container returns for the same quotient

### 5.1 1.81 is a host quotient, and it is arithmetic, not a measurement of the kernel

`artifacts/ladder_engine_host_timing.json:45-48` records `speedup` as VERIFIED with the basis "ARITHMETIC: 49.62 / 27.44 = 1.808, reported as 1.81", from the operator's five cpp runs (28.04, 27.47, 27.15, 27.51, 27.01; mean 27.44, std 0.37) and five python runs (48.4, 44.4, 42.2, 47.6, 65.5; mean 49.6, std 9.0) `[ARTEFACT artifacts/ladder_engine_host_timing.json:9-22]`. So "reproduce 1.81" can only mean: measure python mean over cpp mean, on one machine, at one thread count.

The host Python arm's own spread is worth stating before any comparison, because 1.81 is a ratio of means and the mean is the noisiest thing in it. Against the host cpp mean of 27.44, the operator's individual python runs give ratios of 1.538 to 2.387 `[ARITHMETIC: 42.2 / 27.44 = 1.538; 65.5 / 27.44 = 2.387]`; the artefact's own check records that spread as 18.6% of the mean (`artifacts/ladder_engine_host_timing.json:41-43`). Any 1.81-versus-something comparison has to survive that first.

### 5.2 The container's quotient, same two arms, one thread in both

| condition | python mean (s) | cpp mean (s) | quotient |
|---|---|---|---|
| pinned at import (batches A, B) | 54.855 | 43.621 | **1.258** `[ARITHMETIC: 54.854914 / 43.621061 = 1.2575]` |
| pinned at exec (batches C, D) | 47.045 | 38.288 | **1.229** `[ARITHMETIC: 47.044659 / 38.287688 = 1.2287]` |

Neither is 1.81. The gaps are 1.44x and 1.47x `[ARITHMETIC: 1.808 / 1.258 = 1.44; 1.808 / 1.229 = 1.47]`, which is not small next to the quantity being reproduced.

### 5.3 The gap is carried entirely by the cpp arm

Container over host, arm by arm, using the banked `mean_s` of 27.44 and 49.6 (the artefact's `corrections` also use 49.6; its `speedup` check uses the recomputed 49.62, and the 0.04% difference moves none of these figures):

| arm | condition | container (s) | / host | expression |
|---|---|---|---|---|
| cpp | pinned at import | 43.621 | **1.590** | `43.621061 / 27.44 = 1.5897` |
| cpp | pinned at exec | 38.288 | **1.395** | `38.287688 / 27.44 = 1.3953` |
| python | pinned at import | 54.855 | **1.106** | `54.854914 / 49.6 = 1.1059` |
| python | pinned at exec | 47.045 | **0.948** | `47.044659 / 49.6 = 0.9485` |

The quotient falls from 1.808 to 1.258 and to 1.229 because the cpp arm is penalised by 1.59x and 1.40x while the python arm is penalised by 1.11x and 0.95x: `[ARITHMETIC: 1.808 x (1.106 / 1.590) = 1.258]` and `[ARITHMETIC: 1.808 x (0.948 / 1.395) = 1.229]`. Python in the container is, in one condition, faster than the host figure it is being compared to. This is the same asymmetry `artifacts/ladder_engine_host_timing.json:71-80` records from the earlier session ("Python runs within 1% of the host figure inside the container, so the container penalty ... is specific to the cpp engine"), now measured on a second, independent set of runs.

### 5.4 The window did not close. It widened.

`artifacts/ladder_engine_host_timing.json:69` says, and this is the standing consequence the record has been carrying:

> The container-vs-host cpp penalty is therefore somewhere between 1.57x and 2.12x on the published numbers. Nobody should quote a single figure for it until the same thread pinning is applied to both sides.

The pinning condition has now been met on this side: every baseline run in §3 is one thread, established in §4.1 by measurement and not by inheritance. On the host side it remains attestation only — `artifacts/ladder_engine_host_timing.json:31-34` marks `thread_count` `OPERATOR-ATTESTED` and calls its own basis "an inference from that code path, not a measurement".

Meeting the condition on one side did not collapse the window. It widened it, because this session's pinned cpp runs land below its lower bound. Four in-container measurements of the same arm on the same grid, oldest first:

| container cpp (s) | source | / 27.44 |
|---|---|---|
| 58.040845 | `[ARTEFACT artifacts/ladder_engine_scaling.json:182]`, unpinned env, 42d319d | 2.115 |
| 43.200629 | `[ARTEFACT artifacts/ladder_engine_scaling.json:246]`, `OMP_NUM_THREADS=1`, 42d319d | 1.574 |
| 43.621 | this session, batch A | 1.590 |
| 38.288 | this session, batch C | 1.395 |

The span of those four is a factor of 1.52 `[ARITHMETIC: 58.040845 / 38.287688 = 1.516]`, so on this record the cpp container-vs-host ratio is resolved to about ±52% across sessions, not the ±34% that `why_two_arms` (`artifacts/ladder_engine_host_timing.json:68`) implies. The python arm is the stable one: 50.115704 `[ARTEFACT artifacts/ladder_engine_scaling.json:214]`, 54.855, 47.045, a span of 1.166 `[ARITHMETIC: 54.854914 / 47.044659 = 1.166]`.

The damning pair is the closest one in time. Batches A and C ran twenty minutes apart in one container, on one grid, with identical engine identity and bit-identical physics, under the thread condition §4.1 shows to be the same — and they differ by 1.139 `[ARITHMETIC: 43.621061 / 38.287688 = 1.139]`, which is 27 times the within-batch σ of the faster batch (0.538 s) `[ARITHMETIC: 43.621061 - 38.287688 = 5.333 s; 5.333 / 0.538 = 9.9]`. Nothing in the recorded state distinguishes them; the only uncontrolled variable is the unmeasured load of the agent process on a 1.0 CPU quota (§2.1).

So the honest uncertainty on any figure in §3 is not its own σ. Within one session, two batches of the same arm differ by 1.139; across sessions, four measurements of that arm span 1.52. That is the operative reason no single figure from this container may be quoted, and it is stronger than the standing one: it is not only the container-versus-host gap that is unresolved, it is the container.

## §6 What this file does not establish

- **It does not reproduce 1.81, and it does not refute it.** The check is one-sided: the host arm cannot be re-measured from inside this container, so what is shown is that the quotient is machine-relative, that this machine returns 1.229–1.258 for the same two arms at the same thread count, and that the difference is carried by a cpp-specific container penalty whose own value is unresolved between 1.395 and 2.115.
- **It does not move E3's verdict.** `e3_phase2_scope.md:240-241` keeps that with DR-42 and `EM_SOLVER_LEDGER.md:28`. A pinned-thread figure at target mesh size now exists as `[CONTAINER]` — batch C, structure C, 289168 cells, 2400 steps, 38.288 s — and by `docs/design/GEN12_HANDOFF.md:91` it is not quotable as a measurement, so it is not the figure the scope document is waiting for. Read this as an addition to the pressure on that row, not as its release.
- **It recommends no build change.** `e3_phase2_scope.md:236-239` keeps the flag line out of scope. What ran is `-O2 -fno-fast-math -ffp-contract=off -fopenmp` (`artifacts/cpp_build_e3/CMakeFiles/emfit_core.dir/flags.make:9`), and nothing here tests an alternative.
- **It says nothing about S5b.** No figure in this file carries a bearing on it.
- **It does not explain** the 1.139 between-batch drift, the 1.52 across-session span, or the cpp-specific container penalty. It measures them and stops.

## §7 How to check this document

Every timing in §3 is one `json.load` from an artefact that `/tmp` does not commit; regenerate with §2.1 (about 45 s per cpp run, 48 s per python run). The engine identity is readable per file:

```
for i in 1 2 3 4 5; do python3 -c "import json;m=json.load(open('/tmp/S5a_cpp_pin_$i.json'))['meta'];print(m['wall_total_s'], m['step_engine'], m['kernel_name'], m['kernel_abi'])"; done
```

The arithmetic in §3, §5.2, §5.3 and §5.4:

```
python3 - <<'PY'
import statistics as s
A=[39.50792578799883,44.11560855200514,41.9981267839903,49.917953958007274,42.565688226983184]
B=[60.983930321992375,50.950469098985195,50.88597217499046,57.114092364005046,54.3401067990053]
C=[37.70915479699033,38.14565726000001,38.49134734302061,37.86944498500088,39.22283516600146]
D=[47.442010433005635,47.41265824402217,48.809594532998744,43.87541679700371,47.6836144500121]
for n,v in (('A',A),('B',B),('C',C),('D',D)):
    print(n, round(s.mean(v),3), round(s.pstdev(v),3), round(s.stdev(v),3))
print('quotient pinned-at-import', round(s.mean(B)/s.mean(A),4))
print('quotient pinned-at-exec  ', round(s.mean(D)/s.mean(C),4))
print('container/host', [round(x,4) for x in (s.mean(A)/27.44, s.mean(C)/27.44, s.mean(B)/49.6, s.mean(D)/49.6)])
print('A vs C', round(s.mean(A)/s.mean(C),4))
print('span cpp', round(58.04084487300133/s.mean(C),4))
PY
```

The labels and the rule: `sed -n '91p' docs/design/GEN12_HANDOFF.md`, `sed -n '69p;85p' docs/design/GEN12_HANDOFF.md`, `sed -n '9p' artifacts/cpp_build_e3/CMakeFiles/emfit_core.dir/flags.make`, `sed -n '44,70p' emfit/_env.py`, `sed -n '240,245p' docs/design/e3_phase2_scope.md`.

The standing consequence and the banked host runs: `python3 -c "import json;d=json.load(open('artifacts/ladder_engine_host_timing.json'));print(d['corrections'][0]['standing_consequence']);print(d['engine'])"`.

## Amendment — Fri Nov 13 01:04:41 UTC 2026, one §7 recipe named the wrong file

§7 second recipe line reads `sed -n '69p;85p' docs/design/GEN12_HANDOFF.md`. The `69p` is attributed to the wrong file. `docs/design/GEN12_HANDOFF.md:69` is the single word `**CAVEAT**`, the heading line of the container-render caveat, and says nothing about the thread pin or about the penalty window. The line that recipe was meant to print is `artifacts/ladder_engine_host_timing.json:69`, the `standing_consequence` quoted in full in §5.4. Corrected, as two commands so that each line is labelled by the path it came from:

```
sed -n '85p' docs/design/GEN12_HANDOFF.md
sed -n '69p' artifacts/ladder_engine_host_timing.json
```

`91p` of the handoff, also named in §7, is correct and is the labelling rule quoted in §1. No figure moves: the standing consequence is already printed by the `python3 -c ...` one-liner at the end of §7 and quoted in full in §5.4. This amendment corrects a pointer, not a number.

One further precision, same date. The §4.1 quotation from `GEN12_HANDOFF.md:85` is an interior clause of that line, not the line in full: the line opens `**Thread count — what makes the figure defensible.**`, states that both arms were one thread, and ends with two open questions, the second of which §4.3 quotes from the same line. The clause appears inside the longer line exactly as quoted, and the handoff own citation of the pin (`emfit/__init__.py:33-37`) is left as the handoff wrote it, while §4.1 cites the same call site as `35-37`.
