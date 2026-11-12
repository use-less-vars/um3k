# GEN12 handoff — file 4 of 4: the state of the tree

Labels follow `GEN12_HANDOFF.md:5`: `[READ]` read this session; `[MEASURED]` from a tool call
this session; `[UNVERIFIED — carried from the brief]` not re-checked; `CONFLICT` two in-tree
statements disagree, both recorded. **Nothing was executed** (§6).

## 1. Where the tree is

| item | value |
| --- | --- |
| HEAD | `af635b6f7c8ea79b2c00ab7419f5a3a4f5ceeab0` `[MEASURED]` — `docs(design): DR-43 is closed, not pending -- correct the scope doc's framing` |
| HEAD author / date | `ThoughtMachine Agent <agent@thoughtmachine.local>` / Thu Nov 12 17:37:15 2026 +0000 `[MEASURED]` |
| branches | `master` checked out; `wip/animate`, `wip/fixes`, `wip/m2`, `wip/m3b`, `wip/ports`, `wip/seam`, `wip/seam2` (8) `[MEASURED]` |
| tracked modifications | none modified, staged or deleted |
| untracked entries | 44 `[MEASURED]` |
| read at | this session, at HEAD above |

Lineage, newest first; no per-commit dates read, so **none below HEAD is stated**.

| # | commit | subject |
| --- | --- | --- |
| 1 | `af635b6` | docs(design): DR-43 is closed, not pending |
| 2 | `95ca1c1` | docs(design): scope for DR-43 S21 extraction repair |
| 3 | `1f93518` | fix(artifacts): the third thread-labelled ratio also compared two pinned runs |
| 4 | `af42368` | fix(docs): withdraw 42d319d's thread-effect claim; record the spread it really shows |
| 5 | `14093c7` | fix(evolve): a kernel on disk that cannot be imported is an error, not a fallback |
| 6 | `42d319d` | evidence(e3): second speedup data point, OpenMP thread probe, scaling summary |
| 7 | `b8b2b6a` | evidence(e3): C-arm re-run carries engine provenance; physics bit-identical |

Earlier, newest first: `c1c8276` fix(e3) engine provenance, stale-claim corrections, DR-42
cross-ref; `6cbb89d` perf(e3) FITStepper.step on the C++ kernel (Phase 1); `1921a5d`
docs(ledger) E13, parked; `be803fd` docs(register) re-date DR-41/DR-42 to 2026-11-12;
`fec3c51` docs(design) TE query for S2P convolution; `a69ed43` fix(solver) correct S21
extraction path (the repair); `8ba20ef` the second repair, paired with `a69ed43` in the register.

Untracked, 44 `[MEASURED]`: `artifacts/` (32); `docs/design/` (7 — four `GEN12_HANDOFF*` incl.
`.superseded`, `c2b_shapes.pdf`, `c2b_shapes.png`, `mispaired_metric_before.png`);
`docs/report/figures/c2b_mode_shape_corrected.png`; dirs `evidence/board_poc/`,
`evidence/showcase/`, `evidence/termination/figures/` (not listed); `state.json`.

`CONFLICT` — document dates against HEAD's date:

| document | says | contradicts |
| --- | --- | --- |
| ledger E3 `:28` | "AMENDMENT 2026-11-14" | HEAD author date 2026-11-12 17:37; no later-dated commit reachable |
| ledger E5 `:30` | "measured in this container on 2026-11-14" | same |
| `session_open_gen11.md` | "Written 2026-11-14, at HEAD `3848d46`" | `3848d46` resolves but is not HEAD; file mtime 2026-11-11 05:40 |

## 2. Session and continuity record

Complete glob `**/session_*.md` = 8 files, all in `docs/design/` `[MEASURED]`:

| gen | open | close |
| --- | --- | --- |
| 5 | — | `session_close_gen5.md` (2026-10-31) |
| 6 | — | `session_close_gen6.md` (2026-10-31) |
| 7 | `session_open_gen7.md` (2026-11-01 16:59) | `session_close_gen7.md` (2026-11-01) |
| 8 | `session_open_gen8.md` (2026-11-04 18:05) | `session_close_gen8.md` |
| 9 | — | — |
| 10 | — | `session_close_gen10.md` (text date 2026-11-13, mtime 2026-11-11 05:41) |
| 11 | `session_open_gen11.md` (mtime 2026-11-11 05:40) | — |
| 12 | — | — |

Gaps: gen9 neither record; gen10 close-only; gen11 open but **never closed**; gen12 neither —
glob `*gen12*` returns only the four uppercase `GEN12_HANDOFF*` files.

`session_close_gen10.md`: "Date: 2026-11-13 / Status: validation complete — the independent
referee agrees with the in-house extraction to 0.49 percent; the physics-debug phase is
closed." §1 "The anchor collapse": 0.34465 circular and retracted, with a second circular
anchor 0.345475 behind it.

`RESUME.md` (root, 321 lines): "Position as of 2026-10-21, ~19:45 UTC", HEAD `ab948ba`,
"396 passed in 301.58s" — ~3 weeks / ~30 commits stale (§7 row 1). `dispatch_log.md` (mtime
2026-11-09 23:01, 215,587 B), newest history channel; archive `_2026-Q4.md`.

## 3. Defect register (`docs/design/defect_register.md`)

128,329 B, mtime 2026-11-12 16:02 `[MEASURED]`. Header 1–6 `[READ]`: "records defects DR-14
onward"; DR-1…DR-13 sit outside the tree — not a gap; nothing here renumbers, summarises
or supersedes an outside DR. 30 `## **DR-N**` headings, 28 distinct entries; DR-17 and DR-30
never appear; DR-16 update `:262`, DR-19 update `:338`, DR-15 `:278` RESERVED, never opened.

Flagged rows — heading / status / severity lines:

| DR | heading | status | severity text |
| --- | --- | --- | --- |
| DR-19 | `:302` | `:306` OPEN | `:307` "HIGH (record integrity; gates AC-3)" — `s11` and load-plane `s11_at_plane` describe incompatible reflections in one artefact |
| DR-36 | `:615` | `:619` OPEN | `:620` "MEDIUM — moves no verdict by itself, not a numerical error: 50.088 correctly computed, 'converged' attached to it is not" — box-limited rung Z0 = 50.088 Ω at the 20 mm box, cited as converged |
| DR-37 | `:643` | `:647` OPEN | `:648` "HIGH — moved a verdict: wrong-width solve agreed with wrong width's closed form to 0.16%" — production geometry solved at 3.0 mm, not 3.2 mm |
| DR-39 | `:696` | `:700` OPEN | `:701` "HIGH — timeout inside a solve indistinguishable from hang and from failure; defeats the verification channel" |
| DR-41 | `:760` | `:764` FIXED-TESTED | `:765` "HIGH — wrong number without raising" — openEMS `MSLPort` silently dropped its launch primitive; probe files named the other way round |
| DR-42 | `:783` | `:787` OPEN | `:788` "HIGH — would turn the E3 rewrite into a ~33x regression if the thread team were left unpinned; no kernel figure without a thread count" |
| DR-43 | `:824` | `:828` FIXED-TESTED | `:829` "HIGH — wrong verdict, not just a wrong number"; opened `:830` 2026-11-12 |

DR-39's test-config half `[READ]`: `pyproject.toml:62` `addopts = "-q"`; a second `-q` makes
`-qq`, killing the summary line and `--collect-only` ids (`:706`); timeout 300 s inherited;
`:711` records 49 `tests/test_*.py`, 584 tests at `-o addopts=""`.

DR-41 closure `:764`: both halves fixed in `docker/openems/build_A_referee.py` plus
a host run (`evidence/referee/s11_extraction.json`: `port1_api` "mslport", `s11_abs`
0.3271645531273824), recorded E12 VERIFIED at `EM_SOLVER_LEDGER.md:37`.

DR-42: amendments at `:791` (first, 2026-11-12), `:793` (SECOND), `:799` (THIRD, 2026-11-12).
Third: "the 'thread' ratios in 42d319d are not thread measurements; that commit's mechanism
claim is WITHDRAWN; DR-42 stays OPEN" — 1.3435/1.1588 are repeat spread; resolution limit
±34 % structure C.

DR-43 `:828`, `:861`: the writer publishes |S21| only when an estimator names the plane
(`s21_provenance` is the licence); otherwise it writes eight `s21` keys as null and the
gate reports NOT_ASSESSABLE with null `power_sum`. `:861` "What closes it — done, not
proposed" has (a)–(g), incl. |S21| 0.761705, span ratio 1.021737, revert detectors
(`run_build_A.py:2251` → `tests/test_writer_station_phasors.py:289` `AssertionError: assert
1.021737 is None`; `:2264` → `:306` `assert None == 'NOT_ASSESSABLE'`; 13
passed). Gap `:863`: pre-DR-43 artefacts (`build_A_50ohm.json`, `build_E_50ohm.json`,
`build_B_100ohm.json`) carry no `s21.measured`/provenance key, so absent and null are
indistinguishable.

Method, `:791`: "registers are amended, never rewritten" — blocks appended as
AMENDMENT / SECOND / THIRD AMENDMENT.

DR-19 update `:338–344`: "DR-19 REMAINS OPEN"; vs anchor 48.0237405 (E10) 4.8–4.9 % coarse,
−3.10 % dispersive beta, fine mesh 6.52 % / 6.42 %; family SUPERSEDED by the 2026-11-10
amendment (`dispatch substrate-shift-2026-11-10`); AC-3 UNGRADABLE.

## 4. Ledger (`docs/design/EM_SOLVER_LEDGER.md`)

34,243 B, mtime 2026-11-12 14:53 `[MEASURED]`; 13 rows at lines 26–38.

| row | line | claim area | status | load-bearing content |
| --- | --- | --- | --- | --- |
| E1 | `:26` | Port validation | RETRACTED (5.45 % claim) / UNVERIFIED (residual) | 0.34465 anchor non-independent; two runs are not two estimators; against 0.3423544 −4.90/−4.81/−4.82/−4.74 %, dispersive one-wave −3.10 %; open items (a)–(e) |
| E2 | `:27` | Passivity | UNVERIFIED | 1.344803 in no banked artefact; 0.6863820159501787 at 2400 steps (0.6896931129625421 at 4800, 0.6884889931044529 at 9600); eleven claims retracted |
| E3 | `:28` | C++ performance | UNVERIFIED | 2026-11-14 amendment SUPERSEDES the ladder (50x / 5,926 ns withdrawn); re-measure 3.8/19.6/54.3/145.6/351.5 µs at 1/2/4/8/12 threads, "shape reproduces, magnitudes do not"; NOTE 2026-11-12: kernel on the call path (`6cbb89d`); only 1.76x on the 560-edge toy, a weak bound; **the ledger lags the host figure** |
| E4 | `:29` | Frequency coverage | VERIFIED (partial) | k = 5, 7, 8, 10, 12; 728.4733 MHz spacing; k = 12 `beta_ambiguous` |
| E5 | `:30` | Co-simulation | UNVERIFIED (Test A = algebraic identity) | `terminations.py` 414 lines; `tests/test_terminations.py` 605 lines / 11 tests; `spice.py` landed `95be122`; Test A is a tautology for any invertible W_E |
| E6 | `:31` | Subgridding | UNVERIFIED | research only, no code |
| E7 | `:32` | Web UI | VERIFIED (launcher and rendered UI) | five deps present; `.venv/bin/python` broken; container cannot render (no EGL/OSMesa/Xvfb); operator 7-step host run 2026-11-11 |
| E8 | `:33` | Build reproducibility | OPERATOR-REPORTED (pip) / VERIFIED (g++) | g++ verified; pip path not exercisable (no scikit-build-core, ninja, network) |
| E9 | `:34` | Repository hygiene | UNVERIFIED (no commit state readable) | "git is not installed in this container, so untracked-vs-ignored cannot be checked from here"; unattributed `build/full_suite.log` tallies 582 vs 584 |
| E10 | `:35` | Anchor width | VERIFIED (w = 3.2 mm) | Z0 48.0237405, A = 0.3423544; the ladder Z1 rung at 3.0 mm must not be used |
| E11 | `:36` | Residual vs the independent Z0 | UNVERIFIED | preregistered 2026-11-09; H4 no-fire, H5 ruled NOT FIRED, H2 no-fire; mesh term 0.5523 pp of 4.90 pp, wrong-signed; H1 routing with operator; 4.8 % coarse, fine-mesh target 6.52 % / 6.42 % |
| E12 | `:37` | Independent referee | VERIFIED | \|S11\| 0.327164553 vs artefact 0.3255648664110912 → +0.4914 % in-house / +0.4890 % referee basis; Δ 1.5997e-3 = 2.98x floor (5.363610948678204e-4), 99.4 % of the 3x-floor bound consumed, "must not be described as 'well inside'"; `feed_R` refused; S21 out of scope |
| E13 | `:38` | Antenna campaign | UNVERIFIED (parked) | dependency (i) superseded by the 2026-11-12 NOTE; dependency (iii), the absent 3-D far-field/gain post-processor, governs |

Two-anchor rule, `evidence/termination/NOTE.md` (101 lines) `[READ]`:

| anchor | value | derivation | status |
| --- | --- | --- | --- |
| series-R **twin** anchor | 0.34465 | `50/(2*47.53662+50)`, 47.53662 the twin's *fitted* zc (`build_A_50ohm_twin_p51.json:312`; hard-coded `run_build_A.py:138-140`) | **RETRACTED** as non-independent (`anchor_audit_2026-11-05.md:90-95`, `:166-168`) |
| correct-width anchor (E10) | 0.3423544 | `A = 50/(2*Z0+50)`, Z0 = 48.0237405 (`build_A_50ohm.superseded.json`: `anchor.z0_ohm`, `anchor.formula`, `anchor.derived_anchor_s11`) | not twin-derived |

NOTE.md's rule: a `*twin*.json` record may never be cited as "the referee agrees", as "an
independent anchor" or validation; \|Δ\|/floor 2.9825, \|Δ\|/(3·floor) 0.9942; residuals
−5.54 % (retracted) and −4.90 % (correct width) must not be mixed.

## 5. Artefact families

Counts from listings `[MEASURED]`; tracked = absent from the untracked list.

| family | count | load-bearing members |
| --- | --- | --- |
| `evidence/termination/` | 126 files, 13.8 MB, 3 subdirs (`figures/`, `netlists/`, `twin_multifreq/`) | `build_A_50ohm.json` 18.2 KB (2026-11-12), `build_A_50ohm.superseded.json` 4.0 KB (2026-11-09), `build_A_50ohm_p51_phasors.json` 17.8 KB, ~60 `build_A` variants, `grade_2b.py`, `run_build_A.py` 212.2 KB, `run_multifreq.py`, `NOTE.md`, `README.md`, `passivity_triple_scan.txt`, A/B/E `.log` |
| `evidence/referee/` | 9 | `et`, `ht`, `port_it_1A/1B/2`, `port_ut_1A/1B/1C/2` (≈14–75 KB, 2026-11-10) + `s11_extraction.json` 3,188 B |
| `evidence/referee_run2/` | 8 | same probe set, **no** `s11_extraction.json`; 2026-11-11; ledger attributes it to `db162d6` |
| `evidence/box_sweep/` | 8 | 7 JSON (`lat1-lid1/2/4`, `lat2-lid1`, `lat4-lid1`, `lat8-lid1`, `lat8-lid4`) + `SUMMARY.md` 16,610 B (2026-10-31) |
| `evidence/h_refine/` | 7 | `analyse.py`, `h0267.json`/`.log`, `h040.json`/`.log`, `PREREG.md`, `SUMMARY.md` (2026-10-31) |
| `evidence/matrix_audit/` | 10 | `d585_clearance1.0_modal.json`, `h040.json`, `h080.json`, `k0squared_classify.md`, `ker_pencil.md`, `ker_pencil_harness.py`, `mesh_ladder.md`, `README.md`, `stage1/stage3_k0sq_classify.py` |
| `evidence/strip_width/` | 12 | `EIG_strip_width.json`, `_make_EIG_strip_width.py`, `ERRATA_001/002/003.md`, `PREREG.md`, `SUMMARY.md`, `W08.json`, `W08n.json`, `W12.json`, `W16.json`, `W20.json` |
| `evidence/rung_c/` | 2 | `h020.json`, `SUMMARY.md` 27,719 B (`evidence/rung_c_errata/` not listed) |
| `evidence/t4/` | 6 | `ladder_convergence.json`, `rung4_dense_anchor.json`, `rung4_routeC_{peak_rss,report}.json`, `rung4_routeC_run.log`, `rung4_routeC_run_run1.log` |
| `evidence/` top level | 13 dirs + 7 files | 13 = the nine above + `board_poc`, `rung_c_errata`, `showcase`, `viz`; files: `bank_quasistatic_z0_ladder.py`, `e11_h4_box_limit_2026-11-09.json`, `e11_h5_beta_discipline_2026-11-09.json`, `quasistatic_z0_ladder_w3.{0,2}mm.json`, `stations_n18.json`, `stations_n18_summary.md` |
| `artifacts/` | 55 entries (52 files, 3 subdirs), 37.0 MB | `cpp_build_e3/`, `e3_kernel_live_logs/`, `e3_logs/`; `build_C_stub_cpp{,_t1,_pyengine}.json`, `build_C_plain_cut*.json`, `build_D_diode.json`, `ladder_engine_scaling.json` 27.0 KB, `omp_default/t1.json`, `e3_sweep.tsv`, `e3_kernel_live.tsv`, `smoke_A/B.json`, `passivity_sweep_A*`, `vis_run_*`, `live_run.npz` 15.7 MB, `load_trace_{A,D}.npz`, `rectification_D.png` |

Status: `evidence/{box_sweep,h_refine,matrix_audit,referee,referee_run2,rung_c,strip_width,
t4,termination}` tracked; `artifacts/` mostly untracked (32 of 55);
`evidence/board_poc/`, `evidence/showcase/`, `evidence/termination/figures/` untracked.

## 6. Environment

Execution `[MEASURED]`: **UNAVAILABLE** — "Workspace container limit reached (6/6 consuming
container(s)); remove an existing container with ContainerRemoveTool to free a slot". No host
shell either: no test run, timing, thread probe, render or fresh artefact.

| item | value | tag |
| --- | --- | --- |
| CPU allocation | cgroup `cpu.max` 50000/100000 = 0.5 CPU | `[READ]` `cpp-kernel-status-2026-11-09.md` §5 via `GEN12_HANDOFF.md:5` |
| memory limit | not recorded anywhere found; `d58_13_strip_width_decisions_block.md:189` uses the word in an unrelated API sense | UNVERIFIED |
| git | absent inside the container (`[READ]` E9 `:34`); `git_read` works host-side, reporting `execution_mode: containerized` `[MEASURED]` | mixed |
| `.venv/bin/python` | broken in container only — `pyvenv.cfg` 3.12.3 vs image 3.12.15; working interpreter is system `python3.12` with `PYTHONPATH=.venv/lib/python3.12/site-packages` | `[READ]` E7 `:32`, `GEN12_HANDOFF.md:71` |
| rendering | no EGL/OSMesa/Xvfb; only a real `Plotter.render()` segfaults | `[READ]` |
| pytest invocation | `python3 -m pytest "$f" -o addopts="" -q` under a timeout | `[READ]` `GEN12_HANDOFF_TRAPS.md:103-105` |
| test tree | 49 `tests/test_*.py`, 584 tests, zero collection errors | `[READ]` DR-39 `:711` |
| best recorded sweep | 43 of 46 files completed; 3 stalled on `pytest-timeout` in a scipy CSR matvec, never on an assertion | `[READ]` `dispatch_log.md:57` |
| host kernel timing (operator) | 28.04/27.47/27.15/27.51/27.01 s; mean 27.44 s, σ 0.37 s (±1.3 %); python ≈49.6 s ±18 %; 1.81x — OPERATOR-REPORTED, **not banked**; outgoing prose said 1.85x, unsupported | `[READ]` `GEN12_HANDOFF.md` §2e |

Unsettled: whether those runs went through the package (hence one thread); no many-thread
kernel figure exists.

## 7. Stale and superseded statements

| # | statement as it stands | what the tree says now | sources |
| --- | --- | --- | --- |
| 1 | "Position as of 2026-10-21", HEAD `ab948ba`, "396 passed in 301.58s" | HEAD `af635b6`; 584 tests collected | `RESUME.md` vs DR-39 `:711` |
| 2 | E3 records no usable speed figure | operator host run reports 1.81x; the ledger lags one figure | E3 `:28` vs `GEN12_HANDOFF.md` §2e |
| 3 | `studies.py:4146` cited as where the plane is placed | station-span comment now `:4137–4153`; the driver places it, `run_build_A.py:1829-1830` | `TE_query_s2p_convolution.md:251` vs HEAD message |
| 4 | `TE_query_s2p_convolution.md` cites DR-43 at `defect_register.md:814-819`, `:817`, `:822`, `:824-833`, `:838` (also `:245`, `:248`, `:251`, `:292`) | DR-43 heading `:824`, status `:828`, "what closes it" `:861` — shifted ~10 lines by appends | vs register |
| 5 | `GEN12_HANDOFF_WARS.md:197,229,261` cites `docs/defect_register.md` | file is `docs/design/defect_register.md`; and `:3` says "File 2 of 4" while `:261` says "File 2 of 2" | WARS vs path |
| 6 | `build_A_50ohm.superseded.json` (4.0 KB, 2026-11-09) is superseded | superseded in name only; carries `anchor.z0_ohm`/`anchor.formula`/`anchor.derived_anchor_s11` = 0.3423544, the anchor E10 uses | file vs E10 `:35` |
| 7 | twin anchor 0.34465 cited as an independent anchor | RETRACTED; correct-width anchor is 0.3423544 | NOTE.md §3, E1 `:26`, E10 `:35` |
| 8 | `42d319d` measured a thread effect (1.3435, 1.1588) | WITHDRAWN by `af42368`, retracted again by `1f93518` (the third thread-labelled ratio also compared two pinned runs); THIRD AMENDMENT `:799` | commits vs register |
| 9 | DR-42 parenthetical "not on any call path" | kernel on the call path since `6cbb89d` | register `:791`, E3 NOTE, E13 NOTE |
| 10 | `GEN12_HANDOFF_TRAPS.md` (28,240 B, 556 lines) is the traps file | `GEN12_HANDOFF_TRAPS.superseded.md` (20,973 B) sits beside it, untracked | `docs/design/` listing |
| 11 | `server/poc_app.py:49-55` docstring says the Trame path is UNTESTED | contradicts E7 VERIFIED (launcher and rendered UI) | `GEN12_HANDOFF.md` §2d vs E7 `:32` |

## 8. Open questions, with what closes each

| # | question | what closes it |
| --- | --- | --- |
| 1 | The five-run host timing artefact is not banked | bank the raw runs with engine provenance |
| 2 | Whether the operator host runs went through the package (hence one thread) | run through the package; print `engine_report()` and `omp_get_max_threads()` in the same record |
| 3 | No many-thread kernel figure exists, so DR-42's ~33x exposure is unquantified | measure at >1 thread and confirm the run reached libgomp |
| 4 | DR-43 residual 1 — the default plane is one where the library declines to report a reflection; no document records that decision | `dr43_s21_extraction_scope.md:148`: record the decision |
| 5 | DR-43 residual 2 — the ratio-of-ratios estimator (`studies.py:4121-4136`) withheld for want of a name; `:832` calls that "coarser than the branch deserves" | a provenance string plus `s21.planes_m`, per `grade_2b.py:201` |
| 6 | Seven smaller DR-43 unknowns at `dr43_s21_extraction_scope.md:160-168` (stale citation `studies.py:2979` vs `:3219-3229`, no "short" load kind, S21's scope under E12) | per that file, item by item |
| 7 | Diode field coupling never exercised by `tests/test_diode.py` | `[UNVERIFIED — carried from the brief]`; a test that drives the coupling term |
| 8 | Whether any referee artefact was regenerated after DR-41 was fixed | both directories post-date the fix (`referee/` 2026-11-10, `referee_run2/` 2026-11-11); a dated record naming which run E12's number came from |
| 9 | How many test files have ever run in one sweep | repo states 49 files / 584 tests, best recorded sweep 43 of 46; `CONFLICT` with the brief's "62 test files", which the tree does not support |
| 10 | Which untracked paths are wanted and which are junk | E9 `:34`: one decision per path; 44 untracked entries at HEAD |
