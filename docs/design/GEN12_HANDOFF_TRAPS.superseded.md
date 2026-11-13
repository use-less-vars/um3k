# GEN12 handoff — traps

Sixteen traps, each one a place where this system will tell you something
confident and wrong if you do not check it. Read the NAME and SYMPTOM lines
first; they are the part you will recognise at speed. Every MECHANISM cites a
file and a line so you can go and look instead of believing this document.
Citations marked `[brief, not re-read]` are places to look, not evidence — I did
not open them this session. If a trap fires in a way these notes do not describe,
the code is the authority and this file is a rumour.

---

## A. Planes and geometry — where the numbers come from

### (i) The extraction plane is not where the physics is

**NAME.** S21 sampled at the load's own column.

**SYMPTOM.** |S21| comes back above 1.1 for a structure everyone agrees is
lossy. Passivity fires, or worse, is waived as "numerical". Impedance looks
plausible but the fit residual stays stubbornly bad. The number changes by a
factor of ~1.5 if you move one column, and nobody can say which column is right.

**MECHANISM.** `evidence/termination/run_build_A.py:1805-1810` — when the plane
flag is absent, the probe is taken at `S21_PLANE = <load's own column>`. The
comment there records the measured consequence: |S21| **1.106–1.134** at that
column versus **0.760–0.807** one column downstream, a ratio of **1.45–1.49**.
`:1823-1830` derives `ix_load` from the load position and `cell_m`, and sets
`col = (... else ix_load + 1)`; `:1831-1835` explicitly refuses an upstream
plane. So the *default* is a column where the load has not yet done its work —
a wave still in the middle of meeting the discontinuity.

**WHAT TO DO.** Never accept an S21 number without the plane it was taken at.
If you are comparing against anything historical, establish which column *that*
number used before you decide yours is wrong. Move the plane deliberately, note
the column index in the same record as the magnitude, and expect ~1.5× to appear
the moment you look one cell to the right.

**HOW YOU WOULD KNOW YOU GOT IT WRONG.** |S21| > 1 in a lossy geometry, and
passivity records that carry `NOT_ASSESSABLE` rather than `FAIL`. A "fix" that
improves S21 by 40% without any change to the mesh, the material or the
frequency is not a fix; it is a column change.

### (ii) The reflection coefficient that has nothing to reflect from

**NAME.** S11 quoted at a plane that cannot have one.

**SYMPTOM.** An S11 value appears for a column where the only thing downstream is
the matched load itself. It looks like an ordinary reflection number — 0.3, 0.4 —
and it is meaningless, because at that plane there is nothing for a wave to
reflect *from*.

**MECHANISM.** `emfit/studies.py:4049-4051` states the rule in the library's own
words: *"a reflection coefficient belongs to a plane the wave still has something
to reflect FROM"* — and the load's own column, by construction, does not. The
surrounding block `:4041-4048` carries `s21_provenance` and
`s21_unmeasured_reason`, which is where a study is supposed to say *why* a plane
could not be referred. The brief pointed at `studies.py:4059-4076`; the comment
block actually starts at `:4049`. Same content, off by ten lines — see the
closing notes.

**WHAT TO DO.** Report S11 only at planes upstream of the discontinuity, and
report the distance. When a study cannot produce a plane-referred S11, let it say
so via `s21_unmeasured_reason` instead of substituting the unphysical value.
Silence is a result; a fabricated reflection coefficient is not.

**HOW YOU WOULD KNOW YOU GOT IT WRONG.** You have an S11 and an S21 taken at the
same index, in a geometry with a single termination, and no one can say which
side of the discontinuity the wave was on. That configuration cannot produce both.

### (iii) The fallback span that is not the cut plane

**NAME.** Span-derived S21 standing in for the measured plane.

**SYMPTOM.** S21 has a provenance you did not intend: a station span of **1.02**
where the cut plane wanted **0.76**. The number looks smooth, slightly
optimistic, and is untraceable to any deliberate choice.

**MECHANISM.** `emfit/studies.py:129-137` defines `SPAN_S21_UNMEASURED`, and
`:4137-4153` is the fallback that cites a station span when the measurement plane
is unavailable. The gap is real: 1.02 versus 0.76. This is logged as **DR-43**.

**WHAT TO DO.** If a result depends on S21, make the study assert its provenance
rather than inherit one. When you see `SPAN_S21_UNMEASURED` in a record, treat
every downstream number as provisional until the plane is re-established.

**HOW YOU WOULD KNOW YOU GOT IT WRONG.** The same study run twice gives S21
differing in the second digit with no intervening change, because one run found
the plane and the other fell back to the span.

### (iv) Row and column agree, and that is the only thing that agrees

**NAME.** The AC-6 `indices_agree` check.

**SYMPTOM.** `indices_agree` is true, so the extraction is declared consistent —
but the two numbers being compared are both wrong in the same direction, because
they were both taken at the same misidentified index.

**MECHANISM.** `run_build_A.py:2700-2712` (AC-6) compares indices and reports
agreement. It is an agreement check, not a correctness check — it cannot tell you
that `ix_load` was derived correctly at `:1823-1830`, only that two consumers used
the same value.

**WHAT TO DO.** Use `indices_agree` as a cheap tripwire for internal drift, never
as evidence about the physics. Pair it with an absolute check (|S21| ≤ 1 at the
stated plane).

**HOW YOU WOULD KNOW YOU GOT IT WRONG.** Everything agrees, every check is green,
and trap (i) or (iii) is active underneath. Green plus unphysical means the check
is agreeing about the wrong quantity.

---

## B. What a "pass" is worth

### (v) Passivity that was never assessed

**NAME.** `NOT_ASSESSABLE` read as a pass.

**SYMPTOM.** A validation report shows no passivity failure. It also shows no
passivity result. The downstream reader takes the absence of FAIL as success, and
the number is published.

**MECHANISM.** `run_build_A.py:2154` defines `PASSIVITY_NOT_ASSESSABLE`
(literal `"NOT_ASSESSABLE"`), and `:2157` defines `S11_STATUS_UNVALIDATED`.
`passivity_guard()` at `:2160` has two distinct null branches: `:2189-2191` and
`:2264-2268`, the second of which *returns* `PASSIVITY_NOT_ASSESSABLE` outright.
There is a genuine third state, and it is not a synonym for either neighbour.

**WHAT TO DO.** Carry the tri-state through verbatim — PASS / FAIL / NOT
ASSESSABLE — in every artefact and in every sentence you write about them. If you
must summarise, say "passivity was not assessable at this plane", never "passivity
did not fail".

**HOW YOU WOULD KNOW YOU GOT IT WRONG.** A sentence of yours contains the word
"passive" and the record it came from contains `NOT_ASSESSABLE`.

### (vi) The power sum that raises nothing

**NAME.** `FAIL_PASSIVITY` is a string, not an exception.

**SYMPTOM.** |S11|² + |S21|² comes out above 1 and the run continues happily to
completion, writing a full report. Nothing aborts, nothing turns red in your
terminal unless you are reading the right field.

**MECHANISM.** `run_build_A.py:2192-2195`:
`power_sum = float(s11_mag)**2 + float(s21_mag)**2`, `failed = power_sum > 1.0 + tol`,
`"status": "**FAIL_PASSIVITY**" if failed else None`. The failure is recorded as
a *value* in a record. Wiring of that record happens at `:3630-3638`
(`s21_measurement` / `published_s21_magnitude` / `passivity_record`). A pipeline
that only checks exit codes will never see it.

**WHAT TO DO.** Treat `passivity_record` as a required input: assert on the
string, do not assume the process would have stopped. Note also the tolerance —
`1.0 + tol` means a marginally unphysical result can legitimately come back PASS;
if you are publishing a number whose passivity margin matters, go and read `tol`
in that run rather than assuming zero.

**HOW YOU WOULD KNOW YOU GOT IT WRONG.** Exit code 0, full artefact directory,
and `"**FAIL_PASSIVITY**"` sitting in a JSON field you never read.

### (vii) The bound that was 99.4% consumed

**NAME.** "Well inside the bound."

**SYMPTOM.** A metric is described as comfortable, adequate, within tolerance —
and the underlying number is 2.98× the numerical floor and **99.4% of the 3×
bound**. Nothing has any headroom left, and the adjective said the opposite.

**MECHANISM.** The E12 record: S11 offset **1.5997e-3**, floor
**5.363610948678204e-4** at `s11_extraction.json:15`, ratio **2.9825×**, i.e.
**99.4%** of the 3× bound. `EM_SOLVER_LEDGER.md:37` states the consequence in the
ledger's own words — it *"must not be described as 'well inside'"*. The
supporting arithmetic is in `NOTE.md:1-45`.

**WHAT TO DO.** Quote the fraction consumed, not the verdict. "2.98× floor, 99.4%
of the 3× bound" survives a review; "well inside" does not. If a future run
improves the number, re-derive the fraction — the bound may have moved too.

**HOW YOU WOULD KNOW YOU GOT IT WRONG.** You wrote a margin word ("comfortably",
"well inside", "plenty") and no ratio. Or the ratio you quoted belongs to the
previous mesh.

### (viii) The console says three things and the report says two

**NAME.** Divergent tri-state surfaces.

**SYMPTOM.** The console line and the JSON disagree about whether S11 was
validated. Both came from the same run. The reader trusts whichever they saw
first.

**MECHANISM.** `run_build_A.py:3839-3844` composes `validation_status`, and
`:3979-3990` renders the console tri-state separately. The app-side copies of
these guards live in `poc_app.py` (around `:7357-7365`, `:7788-7800`, `:6625` per
the brief — `[brief, not re-read]`; treat those line numbers as a place to look,
not as a citation). Three surfaces, three chances to collapse a tri-state into a
boolean.

**WHAT TO DO.** When you quote a validation status, quote the field you actually
read and name it. If you are changing a guard, change all its surfaces in the
same commit and diff the console against the JSON afterwards.

**HOW YOU WOULD KNOW YOU GOT IT WRONG.** You cannot produce the JSON field that
backs the console line you just quoted.

---

## C. The kernel and the interpreter

### (ix) The kernel that was silently not there

**NAME.** Pure-Python fallback wearing the kernel's clothes.

**SYMPTOM.** Evolve/fit timings jump by an order of magnitude. Results shift in
the fourth digit. Nothing in the output says "no kernel".

**MECHANISM.** `emfit/evolve.py:155` `_KERNEL_ABI = 1`; `:156` `_KERNEL_NAME`;
`:159` `_FORCE_PYTHON_ENV = "EMFIT_FORCE_PYTHON"`; `:165-168` `_python_forced()`.
The `_load_kernel` docstring at `:230-241` names *"exactly three honest reasons"*
a load may legitimately fall back. Crucially, `:269-273`: an **ABI mismatch
returns `None`** — the kernel is withdrawn silently, because at that point the
extension is present but unusable. `force_python()` at `:276-293` sets the env
var and withdraws the kernel deliberately.

**WHAT TO DO.** Before you believe any timing or fourth-digit comparison, record
which kernel ran. If ABI mismatched, rebuild the extension; do not proceed and
hope. If you are deliberately forcing Python, say so in the record.

**HOW YOU WOULD KNOW YOU GOT IT WRONG.** You cannot state from the artefacts
whether the kernel was used, and you are comparing timings.

### (x) The extension on disk that fails to import

**NAME.** The one case that *does* raise.

**SYMPTOM.** A loud error demanding `.venv` site-packages on `PYTHONPATH` or
`--force-python`, from a machine where the `.so` is plainly present.

**MECHANISM.** Same docstring, `emfit/evolve.py:230-241`: *"What is not silent any
more: an extension file that is ON DISK and fails to import"* — and `:260-268`
raises with a message that tells you to put `.venv` site-packages on `PYTHONPATH`
or pass `--force-python`. This is the *designed* behaviour, not a regression.

**WHAT TO DO.** Do what the message says. Do not delete the `.so` to make the
error go away — that converts a loud, correct failure into trap (ix), a silent
one.

**HOW YOU WOULD KNOW YOU GOT IT WRONG.** You removed or renamed the extension to
get the run to start.

### (xi) `.venv/bin/python` is broken and looks fine

**NAME.** The interpreter that cannot see its own site-packages.

**SYMPTOM.** `.venv/bin/python` starts, prints a version, and then cannot import
anything installed in `.venv/lib/python3.12/site-packages`. Package errors that
make no sense: the package is listed by pip, the directory exists, the interpreter
cannot see it.

**MECHANISM.** `pyvenv.cfg` points at `/usr/bin/python3.12`, which is **3.12.3**,
while the image provides **3.12.15**. The patch-level split means the interpreter
cannot reach `.venv/lib/python3.12/site-packages` as its own. The system
interpreter with an explicit `PYTHONPATH` pointing at that directory works. Only
`Plotter.render()` still segfaults on that path.

**WHAT TO DO.** Use the system interpreter plus `PYTHONPATH=.venv/lib/python3.12/site-packages`
for anything that needs the venv packages, and keep `Plotter.render()` out of any
run whose exit code matters. Do not "fix" `pyvenv.cfg` casually — it is the
reproduction path for this image.

**HOW YOU WOULD KNOW YOU GOT IT WRONG.** `.venv/bin/python -c "import <pkg>"` fails
while `python3 -c "import <pkg>"` with the `PYTHONPATH` set succeeds, and you
concluded the package was not installed.

---

## D. The record

### (xii) The number that lives in one prose cell

**NAME.** A printed figure with no field behind it.

**SYMPTOM.** A value is quoted, cited, and relied upon across documents, and its
only home is a sentence inside a ledger row. No JSON field computes it. The next
person "verifies" it by reading the same sentence.

**MECHANISM.** `+0.4914` appears exactly once as a printed figure:
`EM_SOLVER_LEDGER.md:37` — *"+0.4914 percent - inside half a percent"*. It is
consistent with the pair printed elsewhere (`0.3271645531273824` referee /
`0.32556486641109117` in-house, `NOTE.md:1-45`), but the referee-basis
**+0.4890** has to be *derived*: `NOTE.md:12-19` says so in as many words — *"derived
— no field in either JSON prints it"* (also session_open_gen11 §2). Two bases, one
printed, one derived, and the derived one is the one that matches the referee
anchor.

**WHAT TO DO.** When you quote the offset, quote the basis with it, and if you
need the referee basis, show the derivation next to the number. Any new artefact
should carry a *cell with its inputs beside it* rather than another prose
sentence — that was the fix E12 asked for, and it has not been done.

**HOW YOU WOULD KNOW YOU GOT IT WRONG.** You are citing `+0.4890` to a file:line
that prints it. No such line exists.

### (xiii) The retracted anchor

**NAME.** 0.34465, the twin anchor that was withdrawn.

**SYMPTOM.** A −5.54% deviation is reported against an anchor that no longer
exists. The number is real; the comparison is not.

**MECHANISM.** The twin anchor **0.34465** = `50/(2*47.53662+50)` was **RETRACTED**
(`anchor_audit_2026-11-05.md:90-95`, and again `:166-168`). The −5.54% figure
against it survives at `build_A_50ohm_p51_phasors.json:385`, which is why people
keep finding it. The live anchor is DR-37's **0.3423544**, which gives **−4.90%**
instead. The 5.5 percent is therefore *a different comparison, against a retracted
anchor* — not a larger error in the same measurement.

**WHAT TO DO.** Always state which anchor. If you see −5.54%, you are looking at a
pre-retraction artefact; translate it to the live anchor rather than re-explaining
it. Never average the two, and never quote both as if they bracket the truth.

**HOW YOU WOULD KNOW YOU GOT IT WRONG.** A document contains 0.34465 without the
word "retracted" within a line of it.

### (xiv) The suite log that belongs to nobody

**NAME.** Unattributed test evidence, 582 vs 584.

**SYMPTOM.** A green test log is cited as proof. It was produced by a tree nobody
can name, and it collected 582 tests where the current tree collects 584.

**MECHANISM.** `build/full_suite.log` carries no attribution, and the collected
count disagrees with the live tree — recorded as **DR-39**
(`defect_register.md:723` `[brief, not re-read]`). The two missing tests are the
whole point: they are absent from the log, not absent from the tree.

**WHAT TO DO.** Regenerate the log from a tree you can name (commit + dirty
state), and diff the collected count against the previous one before you trust
green. If you cannot attribute a log, do not cite it — say "an unattributed log
exists".

**HOW YOU WOULD KNOW YOU GOT IT WRONG.** You cited a test count you did not
personally see collected, or you reported the suite as passing while the
collection count differed from the tree you ran.

---

## E. The harness

### (xv) `git` is not installed in the container

**NAME.** The reproducibility step that cannot run.

**SYMPTOM.** Any instruction of the form "commit, then run, then compare" fails at
step one with a missing binary. Scripts that shell out to `git` for a revision
stamp fail inside the sandbox and succeed on a host, so the failure looks
machine-specific and intermittent.

**MECHANISM.** `git` is **not installed** in the container image. Verified
directly — the binary is absent, not merely unconfigured. The E9 row of the ledger
is about exactly this class of problem.

**WHAT TO DO.** Do not put `git` in a critical path. Where a revision stamp is
needed, take it from the artefacts (paths, timestamps, file hashes) or from the
host, and record *which* of the two you used. If a procedure genuinely requires
git, mark it host-only in the handoff.

**HOW YOU WOULD KNOW YOU GOT IT WRONG.** Your instructions say "just commit first"
and the container answers `git: not found`.

### (xvi) `pytest` from the wrong root

**NAME.** Collection differences that are cwd differences.

**SYMPTOM.** A different number of tests collected than the README's count, or
import errors for local packages, with nothing wrong in the code.

**MECHANISM.** The README carries a specific pytest invocation `[brief, not
re-read]` — invocation and working directory both matter: conftest discovery,
`rootdir`, and `sys.path` insertion all depend on where you stand. Run from a
subdirectory and you collect a different tree. The 582-vs-584 discrepancy in trap
(xiv) is the same shape of problem, which is why these two are taught together.

**WHAT TO DO.** Run the suite exactly as the README states, from the repository
root, and record the command and the collected count with the result. If you are
deviating (different root, `-k`, plugin flags), say so — a filtered run is not the
suite.

**HOW YOU WOULD KNOW YOU GOT IT WRONG.** Your collected count differs from the
README's and your command line differs too, and you fixed the count by editing the
command rather than by finding the missing tests.

---

## If you only remember five

1. **Ask which plane.** Every |S21| and every S11 is a number *at a column*
   (`run_build_A.py:1805-1810`, `emfit/studies.py:4049-4051`). A factor of 1.5
   lives in that question, and a meaningless reflection coefficient hides behind it.
2. **Never read "not assessable" as "passed."** The tri-state exists because a
   gap would otherwise be reported as silence (`run_build_A.py:2154-2168`). Carry
   all three states through in your own prose, not just in the JSON.
3. **99.4% is not "well inside".** 2.98× the floor, 99.4% of the 3× bound; the
   ledger says it must not be described as comfortable (`EM_SOLVER_LEDGER.md:37`).
   Quote the ratio, not the verdict.
4. **Name the anchor.** 0.34465 is retracted; 0.3423544 is live; −5.54% and
   −4.90% are the same measurement against different references
   (`anchor_audit_2026-11-05.md:90-95`).
5. **Two interpreters, one kernel, three surfaces.** `.venv/bin/python` cannot see
   its own site-packages; an ABI mismatch withdraws the kernel without a word
   (`emfit/evolve.py:269-273`); console, JSON and app can each collapse the
   tri-state independently. Record what ran, not what you expected to run.

---

## Closing notes on citations

- `emfit/studies.py:4059-4076` (as given in the brief) does not check out. The
  comment block on when a reflection coefficient is meaningful actually starts at
  `emfit/studies.py:4049`; the surrounding provenance fields are `:4041-4048`.
- Not re-read this session, cited as places to look rather than as evidence:
  `poc_app.py:7357-7365`, `:7788-7800`, `:6625`; the pytest command in the README;
  `defect_register.md:723` (DR-39) and `:783-821` (DR-42); `RESUME.md` (dated
  2026-10-21). Verify before quoting any of them precisely.
- `docker/openems/README.md:115-118` records a cleanup hazard and
  `infra/openems/reference/ports.py:408-416` records a refusal
  (`CSX.AddLumpedElement`) — both read, neither is a trap in the sense of this
  document, which is why they are here and not above.
