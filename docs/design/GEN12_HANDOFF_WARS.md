# GEN 12 HANDOFF — THE WARS

**File 2 of 4.** File 1 (`docs/design/GEN12_HANDOFF.md`, 27,076 B) is the *state of the world*: what is true, what is banked, what is unverified, and the fourteen operating rules in §4. This file is the *history of how those rules got there*. Every rule in File 1 §4 was bought with a specific mistake, and each chapter below is one of those mistakes, reconstructed from the repository rather than from memory.

**Read order.** File 1 first. Come back here when you are about to trust a number.

## How to read this file

**Fixed shape, five parts, in order.** **(a) THE SETUP** — the world as it looked at the time, present tense, no hindsight. **(b) WHAT WAS ACTUALLY TRUE** — the mechanism, with `file:line` or a commit hash for every claim. **(c) WHAT IT COST** — wall-clock, artefacts, and what became void; recorded even when embarrassing, especially then. **(d) THE RULE IT BOUGHT** — exactly one sentence, then the cross-reference to the numbered rule in File 1 §4. **(e) WHERE THE EVIDENCE LIVES** — exact paths and line ranges. If a claim in this file has no pointer in part (e), it is not evidence and must not be repeated.

**Statuses** are the ledger's vocabulary verbatim, because inventing a parallel one is how vocabularies rot (`docs/design/EM_SOLVER_LEDGER.md:15-20`): `VERIFIED`, `OPERATOR-REPORTED`, `UNVERIFIED`, `RETRACTED`. A claim not in the first two is a claim to be checked, not a settled fact.

**Provenance classes.** `[HOST]` — measured on the operator's machine, quotable **with** its thread count. `[CONTAINER]` — measured in the Docker sandbox, never quotable as a measurement, never carries timing.

**One honesty note.** Six chapters, six incidents, five cleanly documented. Chapter 6 exists in the shape the brief asked for but not in the repository in the form the brief assumes; it is marked `INFERRED` throughout and states what is absent. That is Rule 13 applied to itself.

---

## Chapter 1 — E12: the agreement that exists in one prose cell and nowhere else

### (a) THE SETUP

December 2026. A microstrip line is solved twice — once by the in-house FDTD solver, once by openEMS acting as an external referee — and the claim to be checked is a single magnitude, `|S11|` at the reference frequency, against a declared 50 Ω reference.

Two artefacts are on disk. The openEMS side has `evidence/referee/s11_extraction.json`: `port1_api` = `mslport` (`:94`), `s11_abs` = 0.3271645531273824 (`:99`), artefact target 0.3255648664110912 (`:101`). The in-house side has the extraction the referee is meant to corroborate. At this moment 0.327164553 is simply *the referee's answer*: a solver a stranger built, reading probe files nobody has audited, on a geometry whose build script has already been wrong twice about what it was modelling.

The ledger is open at `docs/design/EM_SOLVER_LEDGER.md:37`, row E12, marked `VERIFIED` — because an artefact exists. That is the entire standard: flip a status only on an artefact, never delete a `RETRACTED` row (`:44-48`), and *"A row is a claim to be checked, not a settled fact."*

### (b) WHAT WAS ACTUALLY TRUE

The agreement is real and much closer to its edge than its prose. Five things are true at once.

**It consumes 99.4 % of its own bound.** The differential is 1.5997e-3 against `bias_floor.floor_gamma0` = 5.363610948678204e-4 — 2.98× the floor, recorded as 2.9825 at `evidence/termination/NOTE.md:25` and 0.9942 at `:26`. `NOTE.md:28` states the consequence in the imperative: *"Do not describe this agreement as 'well inside' anything."* A document that spends its margin in its adjective has nothing left for the next run.

**One of the two derived forms is printed, in one prose cell, and that is the whole of its home.** `EM_SOLVER_LEDGER.md:37` prints `+0.4914 percent` and calls it "inside half a percent". The referee-basis `+0.4890 percent` is *derived*: `NOTE.md:12-19` captions its table "derived — no field in either JSON prints it", and `session_open_gen11.md` §2 repeats it.

**A headline number needs a cell with its inputs beside it; this one has none.** It is not a field in any file. Reproducing it means pairing `s11_abs` 0.3271645531273824 (`s11_extraction.json:99`) with `s11_artefact_target` 0.3255648664110912 (`:101`, copied from `build_A_50ohm_p51_phasors.json:286`), and the twin exists only as a table caption (`NOTE.md:12-19`). Four files, no arithmetic. That dispersal — not absence — is why it reads as "derived, stated in no file": no cell both prints it and shows the operands it came from.

**The honest rule, stated plainly, because it is easy to overstate in either direction.** A headline number needs to exist in an artefact, with its inputs, computable by a stranger. This one does not — and it is also *not absent from the record*: it is written once, in prose, in a ledger cell, and once derived in a session note. The failure is dispersal, not silence. A reader who opens `evidence/referee/s11_extraction.json` sees 0.3271645531273824 and has to know to find 0.3255648664110912 in the artefact it cross-checks (`:101`), in order to get a percentage that only a prose cell states. That is why the outgoing engineer honestly believed it was "derived, stated in no file" and why the belief survived into the first draft of this chapter: the chain is real, it is just scattered across a prose cell, two artefacts and a session note, so no single file you open will show it to you.

**The 5.5 percent is a different comparison, against a retracted anchor.** 5.5 % *does* appear at `EM_SOLVER_LEDGER.md:37` — the gap against the twin-derived series-R anchor 0.34465 = 50/(2·47.53662+50), where 47.53662 is the twin's own fitted `zc`, so the anchor is not independent of the solver it grades (E1, RETRACTED). Against the DR-37 correct-width anchor 0.3423544 = 50/(2·48.0237405+50) the same reflections read **−4.90 percent**; after the 2026-11-10 amendment the live family is **6.52 / 6.42 percent** (fine mesh, 2-wave / 1-wave, `:40`). Three numbers, three bases, none substitutable.

**The number was never re-derived after the defect was written up.** A git question: `s11_extraction.json` has one commit of record, `89aa2f1` (Tue Nov 10 20:20:34 2026), behind `6fb5ec4` ("… EMPTY GEOMETRY"), `fc81c09` ("13:1 decimated ports"), `99492eb` ("|S11| = 1.0003, port looks OPEN"); the probe headers read `openEMS 5fecbb5 @Tue Nov 10 20:00:17 2026`. DR-41 opens 2026-11-12 (`defect_register.md:766`) — two days later. The artefact *is* the post-fix read (`port1_api` `mslport`; component-first probes, pointers in (e)) — but **nothing re-ran the solve after DR-41 was written up.** E12 is one solve, one plane, one tone, produced before the defect had a name.

### (c) WHAT IT COST

No wall-clock worth recording — the cost was *vocabulary*. A `VERIFIED` row rests on an artefact whose margin is 99.4 % consumed, whose derivation no file performs, and which no one has re-derived since the defect was fixed. Every later document wanting to say "the referee agrees" must do the arithmetic by hand.

Also a live cleanup hazard: `docker/openems/README.md:115-118` records the referee image leaves state behind between runs, so a naïve re-run reproduces neither the number nor a clean one until the image is cleaned. The remedy is known and unexecuted: run in a cleaned container and bank a *new* artefact (`--out` non-colliding, Rule 7).

### (d) THE RULE IT BOUGHT

A number may travel only with the anchor it was measured against and the derivation that produced it, because an agreement quoted without its margin is not an agreement but a claim about one.

→ **Rule 11** (the anchor travels with the number). Cross-referenced: **Rule 12** (a quoted bound is a consumed bound), **Rule 14** (the ledger row is the grade; the design doc the argument), **Rule 7** (never overwrite a banked artefact).

### (e) WHERE THE EVIDENCE LIVES

`docs/design/EM_SOLVER_LEDGER.md:15-20`, `:37`, `:44-48`. `evidence/referee/s11_extraction.json:94`, `:99`, `:101` (+ `bias_floor.floor_gamma0`, `s11_ref50_abs`, `zref_ref50_ohm`). `evidence/termination/NOTE.md:3-8`, `:12-19`, `:19`, `:23`, `:25`, `:26`, `:28`, `:32-40`. `docs/design/session_open_gen11.md` §2. `docs/defect_register.md:760-781` (DR-41; scope note `:775`). `infra/openems/reference/ports.py:107-109`, `:119`, `:349`, `:375`, `:390`, `:408-416`. `evidence/termination/build_A_referee.py:388`, `:1012`, `:1213-1215`, `:1721-1722`, `:1732-1735`, `:1806-1812`; probe files `evidence/referee/{port_ut_1A,port_ut_1B,port_ut_1C,port_it_1A,port_it_1B,port_it_2,port_ut_2,et,ht}`. `git log` → `89aa2f1` ← `6fb5ec4` ← `fc81c09` ← `99492eb`. `docker/openems/README.md:115-118`; `evidence/referee_run2/` @ `db162d6` (replication, not source). `docs/design/lessons_learned_emfit_addendum.md:7`, `:11`.

---

## Chapter 2 — The load stub that was accused of breaking passivity

### (a) THE SETUP

The termination study needs a load, and whether the far end presents a clean 50 Ω, a stub, or an open decides every number downstream. Arm C carries a stub; arm A is a plain cut, the trivial control nobody has to think about.

Two quantities come back from every run and are read together: `|S11|` and `|S21|` — reflected and transmitted parts of the same incident wave, whose squares should sum to one in a passive structure. The harness enforces it: sum above 1 beyond tolerance and the run is stamped `FAIL_PASSIVITY`.

The sweep is running, and the arm failing is **the plain cut**. The stub arm's numbers are strange — `|S11|` 0.856, `|S21|` 0.636 — but stranger is that the honest control, with no load structure at all, returns `|S21|` = 1.02 on a 50 Ω series resistor. A stub is a discontinuity, a discontinuity radiates, energy that leaves the line must show up somewhere, and the passivity gate is exactly the instrument for it. The hypothesis writes itself: **the stub is leaking, and the gate caught it.**

### (b) WHAT WAS ACTUALLY TRUE

Four runs settle it (`evidence/termination/netlists/load_stub.md:236-245`). Two arms × two excitations, same mesh, same everything:

| arm | excite | \|S11\| | cross-check | \|S21\| (arg) | Σ\|S\|² | verdict | time |
|---|---|---|---|---|---|---|---|
| plain cut | CW | 0.32586326 | 0.32613492 | 0.76170542 (5.7752°) | 0.68638202 | ok | 38.94 s |
| stub (C) | CW | 0.85595644 | 0.85562154 | 0.63612344 (47.5181°) | 1.13731446 | FAIL_PASSIVITY | 49.35 s |
| stub (C) | pulse | 0.69988671 | 0.70128913 | 1.02457909 (2.8588°) | 1.53960372 | FAIL_PASSIVITY | 48.1 s |
| plain cut | pulse | 0.32723831 | 0.32753812 | 1.02173670 (3.1127°) | 1.15103078 | FAIL_PASSIVITY | 41.09 s |

The bottom row is the refutation: the plain cut — no discontinuity, 50 Ω series resistor, nothing to radiate — violates passivity *harder* than the stub (1.151 vs 1.137). A defect that fires harder on the control than on the suspect is not a property of the suspect.

What is actually true: the harness's `|S21|` was not an `|S21|`. The 1.02173670 in row 4 (and the 1.020459 its CW twin would report) is a **station-span amplitude ratio** — forward wave at the last station over forward wave at the first — de-embedded at the run's own beta and never plane-referenced. Summing it against a plane-referenced `|S11|` adds two numbers from two different measurements. That is DR-43 (Chapter 3). The narrow point here: **the stub was exonerated because the control failed harder**, and the numbers that "convicted" it were computed wrongly for both arms.

### (c) WHAT IT COST

Four runs at ~39–49 s each on the CW/pulse pairs, plus the reading time of a table nobody trusted. The real cost was the *shape*: the gate fired on a passive structure and the first move was to investigate the arm under suspicion rather than the gate. Every hour spent asking "is the stub leaking?" was spent on a question the control arm had already answered.

The second cost is permanent and recorded rather than repaired: the pre-DR-43 artefacts (`build_A_50ohm.json`, `build_E_50ohm.json`, `build_B_100ohm.json`) carry no `s21.measured` or provenance key, so "absent because the schema predates the field" and "null because the quantity was unmeasured" are indistinguishable in the files termination grading actually reads (`defect_register.md:863`).

### (d) THE RULE IT BOUGHT

Before you investigate the suspect, run the control — a defect that fires harder on the control than on the suspect is a defect in the instrument.

→ **Rule 9** (reproduce before patching). Cross-referenced: **Rule 10** (`file:line`), **Rule 13** (absence is a finding — the pre-schema artefacts).

### (e) WHERE THE EVIDENCE LIVES

`evidence/termination/netlists/load_stub.md:236-245` (the table, verbatim above), `:200-222`, `:224-235`, `:248-260`. The same numbers re-appear as DR-43 evidence rows 1, 2 and 6 in `docs/defect_register.md:836-843`; the sweep artefact is `artifacts/passivity_sweep_A2.json`. Chapter 3 for the defect itself; `docs/design/dr43_s21_extraction_scope.md:119-121` for the two estimators side by side.

---

## Chapter 3 — DR-43: the |S21| that was not an |S21|

### (a) THE SETUP

There are three ways to compute a transmission magnitude and only one is what the field means by `|S21|`. The extraction library offers all three, selected by what the caller passes: a **cut plane** (sample the fields on an explicit plane — the only branch that records which plane it used); a **ratio of ratios** (one de-embedded ratio divided by a reference ratio); and a **span fallback** (forward wave at the last station over forward wave at the first, de-embedded by the line's own β). All three write the same field of the same record. Downstream, a passivity gate squares whatever is there, adds `|S11|`², and compares the sum to 1. The gate cannot know which branch produced its input, because the branch does not have to say.

The sweep is being run in the **default** configuration — no plane named — which means branch three. A transmission of 1.02 on a matched line looks explainable: mesh dispersion, split impedance, the impedance the writer used versus nominal 50 Ω. Every one of those explanations is available and every one is wrong.

This is the part that matters: **the failure is not a wrong number, it is a wrong verdict, and it fires on the default path.** A run that names its plane is fine; a run that does not publishes a ratio in an S-parameter's field and has it summed against an unrelated magnitude.

### (b) WHAT WAS ACTUALLY TRUE

`docs/defect_register.md:824` — status `FIXED-TESTED` (`:828`), severity `HIGH` (`:829`), opened 2026-11-12 (`:830`). The severity line states the scope: "a *wrong verdict*, not just a wrong number … fired on every run that did not name a plane, i.e. on the default path".

**The three branches** (`:832`): (a) cut at `run_build_A.py:4109-4120`, the only branch writing `s21_provenance`, at `:4119`; (b) ratio-of-ratios at `:4121-4136` (behind a 0.549464 test at `tests/test_studies.py:954`), writing no provenance and "coarser than the branch deserves … lacks a name rather than a meaning"; (c) span fallback at `:4137-4153` — `forward_wave_amplitude[-1] / forward_wave_amplitude[0]`, de-embedded at the run's own β, not plane-referenced, "not an S21", published anyway.

**Evidence table** (`:836-843`, from `artifacts/passivity_sweep_A2.json`) — arm A, microstrip, 50 Ω `series_r` at 20.0 mm, one mesh, cell 0.4 mm:

| nsteps | excite | plane | \|S11\| | \|S21\| | Σ | verdict |
|---|---|---|---|---|---|---|
| 2400 | pulse | none | 0.327238 | 1.021737 | 1.151030784 | FAIL |
| 2400 | cw | none | 0.325863 | 1.020459 | 1.147522965 | FAIL |
| 1200 | pulse | none | 0.327700 | 1.010565 | 1.128628182 | FAIL |
| 4800 | pulse | none | 0.327219 | 1.021712 | 1.150968772 | FAIL |
| 9600 | pulse | none | 0.327219 | 1.021712 | 1.150968768 | FAIL |
| 2400 | cw | 51 | 0.325863 | 0.761705 | 0.686382016 | ok |

What the rows say (`:847-851`): rows 4 and 5 agree to 4e-9 across a 2× step, so it is not truncation; CW reproduces the violation at 99.7 % of the pulse value (row 2), so it is not pulse bandwidth; and the plane row shows the defect in one flag — `|S11|` identical to six digits, `|S21|` 1.020459 → 0.761705, sum 1.147523 → 0.686382.

**The geometry that is *not* the cause** (`:847-851`), which is where three days would otherwise go: probe span 9.6 mm (stations 10.4…20.0 mm, 9 stations, 1.2 mm pitch); load 50 Ω `series_r` at 20.0 mm; cut plane 20.4 mm = `cell_m` 0.0004 × `s21_plane_index` 51, with `s21.planes_m` = `[0.0032, 0.0204]`; provenance `cut_plane@20.400mm`. Neither `geometry.station_fit_span_m` = 0.0084 (impedance-fit window, 8 stations 10.4–18.8 mm) nor `s21.deembed_distance_m` = 0.0072 (port → first station) is the span. Arm E is a different configuration (load 30.0 mm, plane index 75 → 30.0 mm); its `|S21|` = 1.013186295836005 in `build_E_50ohm.json` is not a replication of arm A.

**The consequence** (`:859`) voids work: the diode arm's `|S21|` 0.93472 read "passive, ok" only because its `|S11|` was 0.146 — the sum stayed under 1 for the wrong reason. "Any claim resting on that arm's S-parameters is void." Its rectification result survives, because it is computed from V(t)/I(t) and never touches the S-parameters.

**What closed it** (`:861`): provenance attaches only to a finite number; `SPAN_S21_UNMEASURED` (`studies.py:129-135`) states the refusal in words, naming both estimators (1.02 span vs 0.76 cut plane); the writer decides before publishing, in `run_build_A.py:2216-2314` (`s21_measurement → published_s21_magnitude → passivity_record → published_s21_block`); a gate without a published magnitude returns `PASSIVITY_NOT_ASSESSABLE` with null `power_sum`; `grade_2b` warns, `grade_ac7` is unscored; `PASSIVITY_TOL` stays 4.0e-9 and **nothing is clipped**.

**The revert measurement** (`:861`) is what makes `FIXED-TESTED` testable rather than a mood: on 2026-11-12, disabling `run_build_A.py:2251` fails `tests/test_writer_station_phasors.py:289` (`assert 1.021737 is None`); disabling `:2264` fails `:306` (`assert None == 'NOT_ASSESSABLE'`); each gives 1 failed / 12 passed, and 13 passed with the guards.

**Two residuals are recorded, not repaired.** `dr43_s21_extraction_scope.md:148-152` — the default plane policy: the tests pin the nan, which makes it "a decided behaviour that no document states a decision for". `:154-158` — the ratio-of-ratios branch is withheld "for want of a name": it needs a provenance string and `s21.planes_m` per `grade_2b.py:201`, and `SPAN_S21_UNMEASURED`'s reason string is "true of branch (c) … and false here". The artefact gap is `defect_register.md:863` (Chapter 2).

One other gate exists and must not be confused with this one: `studies.py:2117` sums the same two magnitudes against `_BIN_PASSIVITY_SLACK = 1e-6` (`:1923-1925`) and at `:2145-2150` merely logs "BUG: passivity exceeds 1, not clamped" — looser by three orders, reporting rather than refusing. Not the same gate (`docs/design/TE_query_s2p_convolution.md:174-176`).

### (c) WHAT IT COST

Every S-parameter claim resting on the diode arm, plus confidence in every sweep row taken without an explicit plane. The *repair* was small — one guard function, one provenance string, three tests, a status field — which is the usual ratio and the reason Rule 9 exists. The residual is documentation debt with a long tail: `TE_query_s2p_convolution.md`'s DR-43 pointers (`:814-819`, `:824-833`, `:838`) belong to an older register revision and now land in the wrong place; `dr43_s21_extraction_scope.md:5` lists two stale pointers in its own brief; three pre-schema artefacts remain permanently ambiguous.

### (d) THE RULE IT BOUGHT

A derived number must carry the name of the estimator that produced it, because two numbers that are easy to read as one measurement will eventually be summed as one measurement.

→ **Rule 5** (silent failure is the enemy). Cross-referenced: **Rule 6** (the register is append-only — DR-43 amended the gate, never rewrote it), **Rule 10** (`file:line`), **Rule 13** (absence is a finding), **Rule 14** (the row is the grade).

### (e) WHERE THE EVIDENCE LIVES

`docs/defect_register.md:824-866` — `:824` heading, `:826` id, `:827` title, `:828` status, `:829` severity, `:830` opened, `:832` mechanism, `:836-843` evidence table, `:847-851` bullets, `:853-857` refuted causes, `:859` consequence, `:861` closure + revert, `:863` known gap, `:865` gates. `run_build_A.py:2148`, `:2160`, `:2170-2191`, `:2192-2195`, `:2216-2314`, `:2251`, `:2264`, `:3403`, `:4109-4120`, `:4119`, `:4121-4136`, `:4137-4153`. `studies.py:129-135`, `:1693-1698`, `:1923-1925`, `:2117`, `:2145-2150`, `:4047-4048`, `:4119`, `:4142-4148`, `:4300`, `:4445`. `tests/test_writer_station_phasors.py:289`, `:306` + the three named tests; `tests/test_studies.py:954`, `:1577-1635`. `docs/design/dr43_s21_extraction_scope.md:3`, `:5`, `:17`, `:21-25`, `:110-113`, `:115`, `:119-121`, `:123`, `:148-152`, `:154-158`; `docs/design/TE_query_s2p_convolution.md:70-74`, `:174-176`, `:248-250`. Commits `8ba20ef`, `a69ed43`, `28cb5a1`. Artefacts `artifacts/passivity_sweep_A2.json`, `build_A_50ohm.json`, `build_E_50ohm.json`, `build_B_100ohm.json`.

---

## Chapter 4 — The container that measured the kernel differently

### (a) THE SETUP

There is a compiled kernel and there is a Python interpreter, and the question is how much faster the compiled one is. `emfit_core` is a small C++ extension for the inner loop; the Python implementation is a plain NumPy step. Same machine, same arguments, both wrapped behind the same interface.

The openEMS referee work has to run in Docker anyway, so the measurement is taken there: convenient, fixed environment, and a container is supposed to be the reproducible option. The C++ arm returns in about a minute; the Python arm returns in about a minute. Both numbers go into a JSON with everything else.

### (b) WHAT WAS ACTUALLY TRUE

Four truths had to be separated before any figure was quotable.

**The `[HOST]` figure, and the one that does not follow from it.** `OPERATOR-REPORTED`: five runs at 28.04 / 27.47 / 27.15 / 27.51 / 27.01 s, mean 27.44 s, σ 0.37 s (±1.3 %), against Python at ≈49.6 s ±18 %. The ratio is **1.81×** — `49.6 / 27.44 = 1.808`. The outgoing engineer's prose used 1.85×, which does not follow from their own table; File 1 §2e instructs the reader to use 1.81×. The five runs were pasted in conversation, were never banked, and have never been reproduced. File 1's action item is specific: obtain the raw five-run artefact and bank it.

**The `[CONTAINER]` figure, and why it is not quotable.** `artifacts/ladder_engine_scaling.json` @ `42d319d`: the *same* C++ configuration, run twice, took **58.0408 s and 43.2006 s**. Two identical runs differing by 1.34× is not a measurement, it is an instability; the upper reading is up to 2.12× the host's 27.44 s (`58.0408 / 27.44 = 2.115`). Container Python came in at 50.1157 s — within ~1 % of host Python — so the distortion is not a uniform sandbox slowdown but **kernel-specific**, which is exactly how a container artefact misleads: the arm under measurement is affected and the control is not.

**The thread question, which is the whole question.** `emfit/_env.py:44-70` defines `pin_threads`; `emfit/__init__.py:33-37` calls it before anything imports NumPy — "Thread pinning must run before anything imports numpy: BLAS reads its thread count once, when the shared library is loaded" — and it sets `OMP_NUM_THREADS=1`. Both arms of the 1.81× comparison therefore ran at **one thread**, and the statement DR-42 requires is *single-thread-vs-single-thread*, not "the C++ kernel is 1.81× faster", which would imply a parallel configuration nobody has measured. Two questions stay open: whether the operator's host runs went through the package at all, and what a many-thread figure is — unmeasured, and not to be inferred from anything in the tree.

**What the container readings do and do not support** (`n = 1` per arm): structure C, 289,168 cells — C++ 58.0408 s vs Python 50.1157 s, so the compiled kernel reads **1.16× slower**; ladder rung, 51,832 cells — Python/C++ 1.3877×. Resolution limit is ±34 % at structure C and ±16 % on the rung, so neither ratio separates from noise (Chapter 5). DR-42's ~33× stays `UNREPRODUCED`.

**The ledger lag.** `EM_SOLVER_LEDGER.md:28` still says no speed figure exists and E3 stays `UNVERIFIED`; the operator is updating it. Do not write "E3 verified". The row's 2026-11-14 amendment withdrew the 5,926 ns ladder on this ground — 3.8 / 19.6 / 54.3 / 145.6 / 351.5 µs at 1/2/4/8/12 threads, "shape reproduces, magnitudes do not, so no ladder number may be carried forward" — and the 1.76× on a 560-edge toy is "a weak upper bound and must not be quoted as a board-size claim".

### (c) WHAT IT COST

A speed claim that cannot be quoted, an artefact renamed, a correction entry added, and an unknown number of summaries that read "faster" out of a `[CONTAINER]` JSON. The specific damage is the 2.12× distortion: comparing 58.0408 s against the host's 27.44 s says the sandbox is slow; comparing 43.2006 s against 27.44 s says it is fine. Both readings are the same configuration.

### (d) THE RULE IT BOUGHT

Container timing is not a host measurement — a `[CONTAINER]` figure may describe behaviour but never be quoted as a performance measurement, and a `[HOST]` figure is quotable only with its provenance and its thread count attached.

→ **Rule 2** (container timing is not a host measurement). Cross-referenced: **Rule 1** (provenance class), **Rule 3** (every kernel figure carries a thread count), **Rule 4** (a ratio between two pinned runs is repeat spread).

### (e) WHERE THE EVIDENCE LIVES

`docs/design/GEN12_HANDOFF.md` §2e (the 1.81× / 27.44 s / ±1.3 % text and the "use 1.81×" instruction). `artifacts/ladder_engine_scaling.json` @ `42d319d` — 58.0408, 43.2006, 7.2474, 6.2544, 1.1595; `:57` the empty thread-key search. `emfit/_env.py:44-70`; `emfit/__init__.py:33-37`. `docs/defect_register.md:783-821`; `docs/design/cpp-kernel-status-2026-11-09.md` §5. `docs/design/EM_SOLVER_LEDGER.md:28`. `tests/test_cpp_parity.py`.

---

## Chapter 5 — The thread ratio that compared two pinned runs

### (a) THE SETUP

The kernel is slow, the register says so, and the explanation on offer is thread contention: the compiled kernel launches a default OpenMP team that oversubscribes a small workload, while the Python path does not. If that is true the fix is one environment variable and the payoff is a factor of tens.

The evidence is already in the tree — two ratios from two structures, consistent with the story. Structure C: 58.0408 against 43.2006 s = **1.3435×**, read as "default team versus `OMP_NUM_THREADS=1`". The smaller ladder rung: 7.2474 against 6.2544 s = **1.1588×**, the same effect at smaller size. Two structures, same mechanism, same direction is the shape of a confirmed hypothesis, and the commit message says so: the 58.04 s run is attributable to the default team. The argument is complete and internally consistent. It has one unexamined premise.

### (b) WHAT WAS ACTUALLY TRUE

Both arms were pinned. `emfit/_env.py:44-70` defines `pin_threads` and `emfit/__init__.py:33-37` calls it — deliberately before anything imports NumPy, because "BLAS reads its thread count once, when the shared library is loaded" — setting `OMP_NUM_THREADS=1`. Every run through the package starts at one thread. The "default team" arm never existed; there was no team to differ.

`42d319d` published both ratios as thread effects. `af42368` withdrew them after two file reads: the mechanism sentence was removed from the message, artefacts renamed `*_omp_env_set_vs_unset_both_pinned_*`, `corrections[] C1` added. `1f93518` is the *second* retraction — "fix(artifacts): the third thread-labelled ratio also compared two pinned runs" — because after the first retraction a third ratio turned out to be the same mistake. That is the characteristic failure mode of a wrong mental model: it has more instances than you have found.

What the ratios measure is repeat spread on a pinned configuration. The recorded same-config repeat is **1.1595**, so the ladder's "thread effect" of 1.1588 is indistinguishable from a re-run of identical settings. The register-side copy is `defect_register.md:799`, DR-42's THIRD AMENDMENT (2026-11-12): these are not thread measurements, the mechanism sentence is withdrawn, 1.3435 and 1.1588 are repetition spread, resolution at structure C is ±34 %, and the ~33× stays `UNREPRODUCED` — for a new reason, namely that no run has ever reached the kernel with an inherited team.

### (c) WHAT IT COST

Two retractions, one artefact rename, one commit-message correction, one register amendment — all for a hypothesis two file reads refuted at zero cost. File 1 §3: *"A measurement, refuted by two file reads at zero cost. That is the shape of the mistake this document exists to prevent."* The delayed cost is worse: the ~33× is still open, still `HIGH`, and now carries an explanation that was believed and withdrawn, which makes the next person's job harder rather than easier.

### (d) THE RULE IT BOUGHT

A ratio between two runs of the same pinned configuration is repeat spread, not an effect, and must be compared against the repeat spread before it is given a cause.

→ **Rule 4** (a ratio between two pinned runs is repeat spread). Cross-referenced: **Rule 3** (every kernel figure carries a thread count), **Rule 6** (the register is amended, never rewritten), **Rule 9** (reproduce before patching — here, reproduce before explaining).

### (e) WHERE THE EVIDENCE LIVES

Commits `42d319d` (publication), `af42368` (withdrawal, `corrections[] C1`, rename), `1f93518` (second retraction). `docs/defect_register.md:799`, with `:791` and `:793`. `emfit/_env.py:44-70`; `emfit/__init__.py:33-37`. `artifacts/ladder_engine_scaling.json` (58.0408, 43.2006, 7.2474, 6.2544, 1.1595). `docs/design/GEN12_HANDOFF.md` §3.

---

## Chapter 6 — The visualiser rename that left no record

**Status: `INFERRED` throughout.** This is the chapter the brief asked for and the repository does not contain in the form the brief assumes. Read it as Rule 13 worked through, not as history.

### (a) THE SETUP

The visualiser has been renamed. Old files on disk carry the old name; new code writes the new one. The loader is said to accept both, so old artefacts keep working and new ones get the new schema. Nobody revisits it, because the loader accepts both.

### (b) WHAT WAS ACTUALLY TRUE

The rename left **one** relic and no incident record. The relic is a string literal: `docs/design/visualizer_architecture.md:96` documents that the format discriminator `_is_vis(info)` tests `info["format"] == "wavedude"`, and states the stored-data spelling is kept deliberately, with the reader at `server/poc_app.py:202-204` and the writer-side spelling at `:220-222`. That is the only occurrence in `docs/`, and the name does not occur at all among the 39 files of `emfit/`.

The rest is absent. There is **no `emfit/vis/` package** — `emfit/` has no subdirectories and the visualiser module is `emfit/viz.py` (13.5 KB). There is **no `emfit.wavedude` module path and no import shim**, so the brief's claim that "legacy `emfit.wavedude` paths are still accepted" is unsupported: what is accepted is a JSON field value, not a module path. The only legacy *branch* is the plane-dump loader (`server/poc_app.py:366`), a data-format branch rather than a package alias.

### (c) WHAT IT COST

Nothing recoverable, honestly: no artefact voided, no measurement withdrawn, no row retracted. The cost is documentation — a newcomer reading the loader finds `"wavedude"`, has no commit to look at, and the reason lives in one line of one design doc.

### (d) THE RULE IT BOUGHT

When a claim in the tree has no artefact behind it, write down that it is absent and why you looked, because an unrecorded absence is indistinguishable from a thing you forgot to check.

→ **Rule 13** (absence is a finding). Cross-referenced: **Rule 6** (nothing was ever in the register, so nothing had to be amended — the ordinary case, which is why it is worth stating).

### (e) WHERE THE EVIDENCE LIVES

`docs/design/visualizer_architecture.md:96`. `server/poc_app.py:94-95`, `:202-204`, `:207-208`, `:220-222`, `:247-257`, `:366`. `run_build_A.py:461-462`. `emfit/viz.py`; `emfit/` (39 files, no subdirectories, no `vis/`). **Absent:** any `emfit.wavedude` module or shim; any commit, defect entry or ledger row recording the rename.

*File 2 of 2. File 1: `docs/design/GEN12_HANDOFF.md`. Ledger: `docs/design/EM_SOLVER_LEDGER.md`. Register: `docs/defect_register.md`.*
