# GEN12 handoff — traps

Thirteen ways this system will tell you something confident and wrong. Companion
to `GEN12_HANDOFF.md` (the map) and `GEN12_HANDOFF_WARS.md` (the fights). Ordered
by **how likely you are to hit it in week one**, not by severity: the cheap ones
at the top each cost a day because they look like ordinary work.

Each entry has the same six fields, and `WHY IT HONESTLY HAPPENS` always cites
`file:line`, because a citation you can read beats a sentence you must believe.

**Scope, honestly.** The commands are *what to run*, not *what I ran*; the
citations are lines I read. Claims with no in-repo instance say **INFERRED** in
the heading; figures taken from a record say *(as recorded)*. Where these notes and
the code disagree, the code wins. See the last section for what is not claimed.

---

## Index, in week-one order

1. **Which python** — `.venv/bin/python` is not the interpreter that has the packages.
2. **One test file per process** — the suite does not fit in one invocation, and a timeout is not a failure.
3. **Container slot limit** — execution can be unavailable while file tools still work; never write "verified" for what was not run.
4. **Extraction plane past the load** — the default S21 plane is one column downstream, and S11 there has nothing to reflect from.
5. **Write-tool traps** — no amend, and writing to the path of an untracked file destroys it forever.
6. **No git in the container** — "I committed it" is unverifiable from inside; only the host-side git reader sees real state.
7. **Silent fallback** — a kernel that could not be imported used to record `step_engine="python"`; now it is an error with an explicit escape.
8. **Stale kernel / ABI mismatch** — an old `.so` makes `_load_kernel` return `None` and the run quietly becomes Python.
9. **The container times the kernel differently** — C++ is slow *and* unstable here; Python is not.
10. **Provenance and `step_engine`** — two artefacts differing in `step_engine` are not comparable, whatever folder they sit in.
11. **Stale failure messages (INFERRED)** — a verdict written on an older tree is not a verdict on yours.
12. **FP contract / bit identity** — `-ffp-contract=off` is the claim, and the ledger's build line does not reproduce it.
13. **Already-fixed traps** — three trame/Vuetify bugs with an in-tree why; do not tidy them back in.

---

## 1. Which python

**NAME.** You are running the wrong interpreter, and the venv is a decoy.

**SYMPTOM.** `ModuleNotFoundError: No module named 'numpy'` from
`.venv/bin/python`; or everything imports and your numbers disagree with the
banked artefacts by a hair; or you declare "no pyvista/trame here" — a broken venv
read as an absent package — and rewrite a working visualiser path.

**WHY IT HONESTLY HAPPENS.** `.venv/pyvenv.cfg`: `home = /usr/bin`,
`include-system-site-packages = false`, `version = 3.12.3`. The image ships
**3.12.15** (`defect_register.md:709`). The dependencies exist at
`.venv/lib/python3.12/site-packages` (pyvista 0.49.2, trame 4.0.0, vtk 9.7.2) and
import cleanly on the **system** interpreter with that directory on `PYTHONPATH`;
`.venv/bin/python`'s own `sys.path` never reaches them (ledger E7). An operator
reports `.venv/bin/python` printing **3.13.5** with no numpy, contradicting the
cfg — **OPERATOR-REPORTED**, not confirmed by me.

**WHAT TO DO.** Name the interpreter; never trust `python3` from a stale shell.

```bash
cat /workspace/.venv/pyvenv.cfg
PYTHONPATH=/workspace/.venv/lib/python3.12/site-packages \
  /usr/bin/python3.12 -c 'import sys,numpy;print(sys.version, numpy.__version__)'
python3 -m pytest --version     # which python3 does *this* shell give you
```

Importing a visualiser module is not rendering: `Plotter.render()` still
segfaults, and that is the only genuine absence in that area.

**HOW YOU'D KNOW YOU GOT IT WRONG.** The same script on "the same environment"
reports different library versions, or a `sys.path` dump lacks
`.venv/lib/python3.12/site-packages` while the import worked. A "the image lacks
X" sentence with no error behind it is a recorded false absence.

**COST IF MISSED.** Half a day rebuilding an environment that already exists — and
the false-absence version reaches a design document.

---

## 2. One test file per process

**NAME.** You believe a test result you did not actually get.

**SYMPTOM.** A run ends with no summary line and you read the absence as "probably
fine"; a timeout is recorded as a failing test; a count like "2 of 62 files green"
circulates as suite health; the whole invocation dies and you call the suite
broken.

**WHY IT HONESTLY HAPPENS.** `pyproject.toml:59-64` sets `pythonpath = ["."]`,
`testpaths = ["tests"]`, `addopts = "-q"`, `timeout = 300`, and there is **no
`timeout_method` anywhere** (no `setup.cfg`, `pytest.ini`, `tox.ini`,
`conftest.py`), so pytest-timeout stays on its default `signal`/SIGALRM
mechanism, which cannot interrupt a blocked C or sparse-matvec call.
`defect_register.md` DR-39 (`:696-723`) is the story:

- `:706` the `-q` collapse: `-qq` kills the summary line *and* collect-only ids.
- `:711` **49 `tests/test_*.py` files**; `pytest tests/ --collect-only -o addopts="" -q` collects **584 tests, zero collection errors** *(as recorded)*.
- `:712` 43 of 46 attempted ran clean, 3 stalled; `test_cpp_parity.py` and `test_step_extraction.py` need the extension on `PYTHONPATH` (earlier run: `20 passed`, *as recorded*); `test_demo_picker.py` is environmental, passing alone in 9.81 s.
- `:713` the stalled three: `test_studies.py`, `test_board.py`, `test_mode2d.py` — **unrun at the clock, not broken**.
- `:714`/`:717` every non-green result was a pytest-timeout inside a scipy sparse matvec, **never an assertion failure**, and in the report indistinguishable from a hang.
- `:723` gates: no "the suite is green"; no pass count without a summary line; a timeout is not evidence of a failing test.

**WHAT TO DO.** One file, one process (the cgroup is 512 MB; the suite does not
fit):

```bash
python3 -m pytest tests/ --collect-only -o addopts="" -q | tail -3    # inventory, cheap
for f in tests/test_*.py; do
  echo "=== $f"; timeout 400 python3 -m pytest "$f" -o addopts="" -q 2>&1 | tail -20
done
```

For the extension-dependent two, build first (trap 8), then run with
`PYTHONPATH=build/cpp`.

**HOW YOU'D KNOW YOU GOT IT WRONG.** A pass count with no summary line beside it,
or a "failure" that is a `Timeout` with no assertion text — the sentences DR-39:723
bars. A suite that "passed" in one invocation is a fluke, not a baseline.

**COST IF MISSED.** You report health you do not have, or you spend a day chasing
a "hanging test" that is a 300 s alarm inside a legitimate solve.

---

## 3. Container slot limit

**NAME.** The tools that would have verified your claim were unavailable, and you
wrote the claim anyway.

**SYMPTOM.** Execution refuses at the workspace container limit (6/6) and shell
commands do not run; then sentences appear — "confirmed by running", "verified with
`du -sh`" — for things never executed.

**WHY IT HONESTLY HAPPENS.** The workspace has a fixed number of container slots,
consumed by other work; when the pool is full execution is refused, not queued.
Nothing to debug — but it removes the verification path an engineer reaches for
without thinking, and the temptation is to write the sentence you *would* have
written.

**WHAT TO DO.** Use tools that need no container: `DirectoryTreeTool` with
`include_sizes=true`, `FileReadTool` with `start_line`/`end_line`, and host-side
`git_read`. Attach honest provenance to each claim — *"size from
`DirectoryTreeTool`, not `wc`; not executed"* — and if a claim only becomes true by
execution, do not make it.

**HOW YOU'D KNOW YOU GOT IT WRONG.** grep your output for "verified",
"confirmed", "ran", "checked"; per sentence, name the tool that produced it. If
the answer is "none, but it is obviously true", you have the trap.

**COST IF MISSED.** A number enters the record with a false verification story, and
provenance that is wrong is worse than provenance that is absent.

---

## 4. Extraction plane past the load

**NAME.** S21 sampled at the load's own column; S11 quoted where it cannot exist.

**SYMPTOM.** |S21| around 1.10–1.13 for a structure everyone agrees is lossy, so
passivity fires or is waived as "numerical". Or an S11 appears one column past the
load, looks like an ordinary reflection number (0.049 beside a real 0.326), and is
meaningless because the load is *behind* the probe.

**WHY IT HONESTLY HAPPENS.** `evidence/termination/run_build_A.py:1805-1820` is the
DEFAULT PLANE POLICY comment: with the flag absent the probe sits at `S21_PLANE`
"cut", the load's own node column, where recorded artefacts show |S21|
**1.106–1.134** against **0.760–0.807** one column downstream — ratio **1.45–1.49**.
`:1823-1825` derives `ix_load`; `:1829-1830` sets `col = ... else ix_load + 1`, so
**the default is one column downstream**; `:1831-1839` refuses an upstream column
with a `SystemExit`. Artefacts record `plane_from_default_policy=True`. The S11
half, in the library's words at
`emfit/studies.py:4049-4058`: *"A reflection coefficient belongs to a plane the
wave still has something to reflect FROM … One column past it the load is BEHIND
the probe … category error rather than a tolerance — it is what put
`s11_at_plane = 0.049` into a record beside `s11 = 0.326` (DR-19)."* `:4059-4076`
sets `s11_at_plane_valid = False`, reason `"plane_beyond_load"`, with a
`RuntimeWarning`; `:4041-4048` carries `s21_provenance` and `s21_unmeasured_reason`
(`SPAN_S21_UNMEASURED`).

**WHAT TO DO.** Never accept an S21 or S11 without its plane, and read the plane
out of the artefact, not the folder name.

```bash
grep -n "plane_from_default_policy\|ix_load + 1" evidence/termination/run_build_A.py
grep -n "plane_beyond_load\|s11_at_plane_valid\|SPAN_S21_UNMEASURED" emfit/studies.py
/usr/bin/python3.12 -c "import json,sys;d=json.load(open(sys.argv[1]));print({k:v for k,v in d.items() if 'plane' in k.lower() or 's21' in k.lower() or 's11' in k.lower()})" artifacts/<run>.json
```

Before "fixing" a magnitude, establish which column the historical number used: a
magnitude that moves ~1.5× with no change to mesh, material or frequency is a
column change, not an improvement.

**HOW YOU'D KNOW YOU GOT IT WRONG.** |S21| > 1 in a lossy geometry with passivity
`NOT_ASSESSABLE` instead of `FAIL`; an S11 whose plane index is at or past
`ix_load`; quoting `s11_at_plane` while `s11_at_plane_valid` is `False`. If the
flag is False the honest number is "not defined here", not the number that
printed.

**COST IF MISSED.** A passivity waiver that is a geometry mistake, or a "tuned"
structure whose gain is entirely in the probe — DR-19 reached a record once.

---

## 5. Write-tool traps

**NAME.** The edit that destroys instead of edits.

**SYMPTOM.** A file is 49 KB one minute and 3 KB the next. You "replaced a
section" and the untracked draft that lived there is gone — not in git (trap 6),
not in a backup, nowhere.

**WHY IT HONESTLY HAPPENS.** The edit surface is not git-backed: no amend, no
reflog, no undo — a `write` replaces the whole file at that path. If the target is
untracked (much of `docs/design/` and almost all of `artifacts/` is), the previous
version exists only as the bytes you just overwrote. This session lived it: a ~49 KB
untracked draft destroyed by writing to its own path.

**WHAT TO DO.** (1) Look before you overwrite: `DirectoryTreeTool` with
`include_sizes=true` says whether the path holds something, host-side `git status`
says whether it is tracked — big *and* untracked means evidence, not scratch space.
(2) Send state-destroying writes to a new path, or move the old one aside first
(this file was written over a different 21 KB untracked document at the same path,
which survived only as `GEN12_HANDOFF_TRAPS.superseded.md`).

```bash
git status --short docs/design      # host-side reader, not inside the container
```

**HOW YOU'D KNOW YOU GOT IT WRONG.** You cannot answer "what was at this path
before I wrote it?" without guessing.

**COST IF MISSED.** Irrecoverable work, often someone else's, found out three days
later. Related, ledger E9: decide deliberately per path — commit, ignore, delete —
and record the decision.

---

## 6. No git in the container

**NAME.** Repository state you cannot read from where you are standing.

**SYMPTOM.** `git status` inside execution returns "command not found". Or you
write "committed as `<sha>`" having never seen that sha from a tool that can read
the repository. Or you assume a file is tracked because it looks deliberate.

**WHY IT HONESTLY HAPPENS.** `docs/design/EM_SOLVER_LEDGER.md:34` (E9 row),
verbatim: *"`git` is not installed in this container, so untracked-vs-ignored
cannot be checked from here."* The same row records the cost: an unattributed
`build/full_suite.log` showing 582 against 584, which *"may not be cited as a pass
until it is tied to a tree state"*, and an undecided list — `artifacts/`,
`evidence/showcase/`, `infra/openems/reference/`, loose `*.log`, `.scratch/` (442
entries).

**WHAT TO DO.** Read state only with the host-side git reader:

```bash
git log --oneline -5
git status --short
git show --stat <sha>
```

Every assertion about tracking, commits or diffs comes from there; inside
execution, when you need to know, ask outward rather than inferring from `ls`.

**HOW YOU'D KNOW YOU GOT IT WRONG.** Any "I committed …" or "this is tracked"
sentence not traceable to a host-side git call. `14093c7`, `6cbb89d` and the rest
were read this session through the host-side reader, never from inside.

**COST IF MISSED.** You report a commit that does not exist, or overwrite the only
copy (trap 5 from the other side).

---

## 7. Silent fallback

**NAME.** The kernel was there and the process used Python anyway.

**SYMPTOM.** An artefact records `step_engine = "python"` while a perfectly good
`.so` sits beside it, so provenance is *wrong* rather than *absent*. Before commit
`14093c7` (*"a kernel on disk that cannot be imported is an error, not a
fallback"*) this was the normal failure mode.

**WHY IT HONESTLY HAPPENS — and how it is now handled.** `emfit/evolve.py:228` is
`_load_kernel`; docstring `:230-246` enumerates "exactly three honest reasons" for
the Python path and records that returning `None` *"let a process record
`step_engine='python'` while a perfectly good `.so` sat beside it"*. The honest
paths are explicit: `:248-249` (forced by the operator) and `:250-255` (import
failed **and** no candidate files); everything else raises — `:256-268` raises
`RuntimeError` listing the candidates and both ways out. The escape is a flag:
`EMFIT_FORCE_PYTHON=1` (`:159`, `:162`, `:165-168`), `--force-python` (`:235`,
`:266`), or `force_python()` (`:276-293`). `engine_report()` `:300-322` returns
`{"step_engine": "cpp"|"python", "kernel_abi", "kernel_name"}`.

**WHAT TO DO.** If you want Python, say so; if you want the kernel, prove it.

```bash
EMFIT_FORCE_PYTHON=1 /usr/bin/python3.12 -m <entrypoint> --force-python   # deliberate
/usr/bin/python3.12 -c 'from emfit.evolve import engine_report;print(engine_report())'
```

**HOW YOU'D KNOW YOU GOT IT WRONG.** `engine_report()["step_engine"] == "python"`
with no flag passed and a `.so` present: supposed to be impossible now, so it is a
bug to report, not a condition to work around. A `RuntimeError` from `_load_kernel`
is not "the kernel is broken" — it is the system refusing to guess; read the
candidate list it printed.

**COST IF MISSED.** Numbers with the wrong arithmetic attributed to them: every
comparison across that boundary is void, and the record still looks fine.

---

## 8. Stale kernel / ABI mismatch

**NAME.** An old `.so` from a build you no longer remember.

**SYMPTOM.** Trap 7's shape: the run is Python, or it is C++ and disagrees with
parity in the last digits; `_load_kernel` returns `None` for the honest reason
"ABI mismatch".

**WHY IT HONESTLY HAPPENS.** `emfit/evolve.py:155` sets `_KERNEL_ABI = 1`, which
"must equal `emfit_core.KERNEL_ABI` (`src/bindings.cpp`)"; `:271-273` returns
`None` on mismatch. `src/bindings.cpp:303-311` sets `m.attr("KERNEL_ABI") = 1` and
carries the rule: *"Bump `KERNEL_ABI` on ANY change to the floating-point contract
… so a stale `.so` can never be silently mixed."* It is a handshake about the
arithmetic, so a rebuild is not optional — and not `pip install -e .`: no
scikit-build-core here, and `/tmp` is `noexec`, so the `.so` must live **inside**
the workspace (`tests/test_cpp_parity.py:78-81`). Canonical build, `BUILD_COMMANDS`
`:82-89`:

```bash
/usr/bin/g++ -O2 -fno-fast-math -ffp-contract=off -fopenmp -std=c++17 -shared -fPIC -Wall -Wextra \
  -I/workspace/.venv/lib/python3.12/site-packages/pybind11/include \
  -I/usr/local/include/python3.12 -Isrc \
  src/bindings.cpp src/emfit_core.cpp \
  -o "build/cpp/emfit_core$(python3 -c "import sysconfig;print(sysconfig.get_config_var('EXT_SUFFIX'))")" \
  && PYTHONPATH=build/cpp python3 -m pytest tests/test_cpp_parity.py -v
```

**WHAT TO DO.** Rebuild with exactly that line, then confirm the handshake before
trusting any parity or timing number:

```bash
PYTHONPATH=build/cpp /usr/bin/python3.12 -c 'import emfit_core;print(emfit_core.KERNEL_ABI)'
/usr/bin/python3.12 -c 'from emfit.evolve import engine_report;print(engine_report())'
```

**HOW YOU'D KNOW YOU GOT IT WRONG.** `kernel_abi` is `None` where you believe the
kernel loaded, or the `.so` mtime predates the last edit to `src/emfit_core.cpp` or
`src/bindings.cpp`. A kernel "loaded" from a binary older than its source is the
archetype.

**COST IF MISSED.** Bit-identity claims measured against a binary that is not the
one you think it is — unfalsifiable afterwards; parity that "used to pass" says
nothing about today's `.so`.

---

## 9. The container times the kernel differently

**NAME.** Container wall-clock is not host wall-clock, and the C++ path is the one
that moves.

**SYMPTOM.** A C++ benchmark that is slow *and* unstable: two runs give 58.0408 s
and 43.2006 s and you cannot tell whether your change helped. The pure-Python path
looks fine and agrees with host within ~1%, which tempts you to blame the kernel.

**WHY IT HONESTLY HAPPENS.** Measured this session: container Python came within
~1% of host Python, but the container ran the C++ kernel at **58.0408 s and
43.2006 s** against a host mean of **27.44 s** — slower *and* unstable, **1.34×**
run-to-run. Cause: thread provisioning. `emfit/_env.py:35-40` defines `THREAD_VARS`
(OPENBLAS / OMP / MKL / NUMEXPR); `pin_threads` (`:44-70`) is the **first
statement** of `emfit/__init__.py:33-37`, before numpy is imported, because the
variables must be set before the libraries read them. Docstring `:11-15` records
the justification: **10.2 s → 0.27 s (~40×)** when the container advertised 12
cores but carried one core of quota. Only unset variables are touched (`:24-26`).

**WHAT TO DO.** Never quote a container wall-clock as a performance result. Time
the ratio against a repeat in the same session, record both, caption the container:

```bash
for i in 1 2; do /usr/bin/time -f "%e s" /usr/bin/python3.12 -m <entrypoint>; done
```

**HOW YOU'D KNOW YOU GOT IT WRONG.** Two runs of identical code differ by a third,
or a "regression" vanishes on re-run. A performance claim with one timing in it is
not yet a claim.

**COST IF MISSED.** An optimisation judged on noise: a day chasing a phantom
regression, or shipping a real one because the container was fast that run.

---

## 10. Provenance and `step_engine`

**NAME.** Two artefacts you are comparing came from different arithmetic.

**SYMPTOM.** A/B numbers that each look reproducible but disagree slightly, and
re-running does not reconcile them. Or a folder name (`cpp/`, `e3/`) treated as a
provenance label while the file itself says something else.

**WHY IT HONESTLY HAPPENS.** `engine_report()` (`emfit/evolve.py:300-322`) exists
for this; docstring `:301-307` records *"the identity of the arithmetic that
produced a number, so a banked artefact says which path generated it rather than
leaving a reader to infer it from the machine it was graded on"*. On the Python
path `kernel_abi` and `kernel_name` are `None`, which is meaningful, not missing.
Historically the kernel was on no call path at all: `defect_register.md:788`
(DR-42) says *"`emfit/` never imports it, see E3"* — **historical**: commit
`6cbb89d` put it on one. Artefacts either side of that commit can carry different
arithmetic under one description.

**WHAT TO DO.** Read provenance out of the artefact before comparing it:

```bash
/usr/bin/python3.12 -c "import json,sys;d=json.load(open(sys.argv[1]));print(d.get('step_engine'), d.get('kernel_abi'), d.get('kernel_name'))" artifacts/<run>.json
```

Two artefacts differing in `step_engine` — or one of which has no `step_engine` at
all — are **not comparable**; say so instead of quoting a delta. The ledger's E13
row is the model: name the field, the value, and the commit that changed it.

**HOW YOU'D KNOW YOU GOT IT WRONG.** A comparison where one side's `step_engine`
is unknown, or where prose ("this was the C++ run") stands in for a field in the
artefact.

**COST IF MISSED.** A cross-engine delta presented as a physics result — the
hardest error to unwind, because both numbers are individually correct.

---

## 11. Stale failure messages — **INFERRED**

**NAME.** A verdict written on an older tree, or on a run whose summary line was
never produced, believed as a verdict on yours.

**SYMPTOM.** A note says "test X fails" and X passes; a log ends in partial output
and the truncation is read as the outcome; a red result is inherited from a report
rather than reproduced.

**WHY IT HONESTLY HAPPENS.** **A generalisation, not an incident I located in the
repository — INFERRED.** What is not inferred is the family of evidence: DR-39
`:717` says a timeout *"is indistinguishable, in the report, from a hang and from a
failure"*; `build/full_suite.log` is unattributed (582 against 584) and ledger E9
(`EM_SOLVER_LEDGER.md:34`) says it *"may not be cited as a pass until it is tied to
a tree state"*; the `-qq` collapse (`defect_register.md:706`) lets a log end
without stating a result.

**WHAT TO DO.** A verdict is usable only with the command, the tree state (sha, or
an explicit "untracked working tree") and the summary line attached. If any is
missing, re-run the single file (trap 2) before repeating the claim — a minute
versus a day. Never upgrade "no summary line" into "passed".

**HOW YOU'D KNOW YOU GOT IT WRONG.** A claim about a test you cannot re-derive in
one command, or a quoted log whose last line is not a pytest summary and whose
caption nevertheless says "green".

**COST IF MISSED.** A day spent on a defect that was fixed, or a shipment around
one that is still live. The asymmetry is what makes the re-run worth it.

---

## 12. FP contract / bit identity

**NAME.** The bit-identity claim is about compiler flags, not about the algorithm.

**SYMPTOM.** Parity fails at max|diff| ≈ 2.3e-13 — tiny, "obviously numerical
noise" — so you relax the tolerance or rebuild with other flags and the failure
count moves. The kernel then stops reproducing banked artefacts bit-for-bit and
nobody can say when divergence started.

**WHY IT HONESTLY HAPPENS.** `src/CMakeLists.txt:19-28` records a measurement:
*"GCC's default -ffp-contract=fast fuses a*b + c into one FMA … an `-mfma` build
emits 3 vfmadd instructions and fails 8 of the 13 tests in
`tests/test_cpp_parity.py` at max|diff| 2.3e-13; with `-ffp-contract=off` it emits
0 FMAs and all 13 pass bit-for-bit … -O2 is the configuration the parity was
actually measured in, so the flag line below builds the thing that was tested
rather than a fresh, unmeasured -O3."* Flag line at `:55`; `src/bindings.cpp:300-301`:
*"the bit-identity depends on `-ffp-contract=off`, not on the algorithm alone."*

**The record is thin.** The ledger's E8 row (`EM_SOLVER_LEDGER.md:33`) records the
build line as `-O3 -fopenmp -std=c++17 -shared -fPIC -Wall -Wextra` — **no
`-ffp-contract`, and `-O3` where parity was measured at `-O2`** — so it does not
reproduce the parity claim. The truth is `CMakeLists.txt:19-28,55`,
`bindings.cpp:300-301`, `tests/test_cpp_parity.py:82-89`.

**WHAT TO DO.** Build with trap 8's `BUILD_COMMANDS` line exactly, then check the
binary has no fused operations and re-run parity:

```bash
objdump -d build/cpp/emfit_core*.so | grep -c vfmadd    # expect 0
PYTHONPATH=build/cpp python3 -m pytest tests/test_cpp_parity.py -o addopts="" -q
```

No `-O3`, no dropping `-fno-fast-math`, no `-march=native`.

**HOW YOU'D KNOW YOU GOT IT WRONG.** Parity "almost" passes, `objdump` counts
FMAs, or you changed the floating-point contract without bumping `KERNEL_ABI`
(trap 8). If you widened a tolerance to get green, you deleted the property the
kernel exists to provide.

**COST IF MISSED.** Bit-identical reproducibility is the only reason the kernel is
trusted. Losing it silently invalidates cross-artefact comparison programme-wide
and surfaces later as a disagreement nobody can resolve.

---

## 13. Already-fixed traps (each with an in-tree why)

**NAME.** Three UI bugs that were fixed, where the obvious tidy-up reinstates the
bug.

**SYMPTOM.** A keyboard shortcut stops working and the only trace is a log line
reading *"Trigger %s seems to be missing"*. Or a tab bar highlights and the pane
renders nothing. Or a frame slider moves and nothing redraws.

**WHY IT HONESTLY HAPPENS.** The code documents all three at the fix site.
(1) **`@ctrl.trigger`, not `@ctrl.set`** — `server/poc_app.py:7357-7365`: trame
resolves a browser call through `controller.trigger_fn(name)`, which knows only
`@ctrl.trigger` names; a `@ctrl.set` name gives `fn = None`, the log line, and a
silent no-op. Registration at `:7366`: `@ctrl.trigger("kbd_shortcut")`.
(2) **VTab needs a name on both sides** — `:7786-7804`: Vuetify group-item props
default to `value: null` with **no index fallback for VTab**, so bare
`VTab("label")`s all register `null` and `VTabsWindow` resolves its model to
`null` — a highlighted tab bar over an empty pane (the index alternative would
make tab state an invisible number). Fix at `:7805`:
`with tabs_cls(v_model=("tab", "s_params"))`. (3) **`v_model` writes state, it does
not call you** — `:6625-6634`: `v_model=("frame", 0)` only writes `state["frame"]`;
trame turns a callable into a server call only for **event** kwargs (`click=`,
`change=`), never `v_model`. The redraw hangs off `@state.change("frame")` at
`:6630`, guarded by `suppress_frame_listener` at `:6632-6633`.

**WHAT TO DO.** Confirm the fix is still there and leave the shape alone:

```bash
grep -n 'ctrl.trigger("kbd_shortcut")' server/poc_app.py
grep -n 'v_model=("tab"' server/poc_app.py
grep -n '@state.change("frame")' server/poc_app.py
```

**HOW YOU'D KNOW YOU GOT IT WRONG.** You "simplified" `@ctrl.trigger` to
`@ctrl.set` for symmetry, replaced the string `v_model` pair with an index, or moved
the redraw into a `v_model` callable. Each is a regression that fails silently —
none of the three raises, which is why each was fixed with a comment.

**COST IF MISSED.** A silently dead control, the expensive class of UI bug: the
evidence is a log line nobody reads and a screen that looks almost right.

---

## What this file does not claim

- Nothing here was executed end-to-end: container execution was refused at the
  workspace limit (6/6) for part of the session. Commands are what to run;
  citations are lines that were read.
- Trap 11 is generalised and marked INFERRED; no in-repo instance was located.
- Recorded figures are marked *(as recorded)*, including `defect_register.md:711-713`
  and the `20 passed` figure for the two extension-dependent files.
- "2 of 62 test files" is not in the record: it says **49 test files, 584 tests
  collected** (`defect_register.md:711`).
- The ledger's E8 build line does not reproduce the bit-identity claim (trap 12);
  that is a defect in the ledger, not in the kernel.
