# GEN12 handoff — file 4 of 4: the state of the tree

Labels follow `GEN12_HANDOFF.md:5`: `[READ]` read this session; `[MEASURED]` from a tool call
this session; `[UNVERIFIED — carried from the brief]` not re-checked; `CONFLICT` two in-tree
statements disagree, both recorded. **Nothing was executed** (§6).

## 1. Where the tree is

| item | value |
| --- | --- |
| HEAD | **not stated as a bare claim.** HEAD **was** `5317ce5` (`docs(handoff): correct the log citation counts and record the final tree state`) when this line was written; the commit carrying this line is `5317ce5`'s child. The reading this row first recorded — `af635b6f7c8ea79b2c00ab7419f5a3a4f5ceeab0` `[MEASURED]`, `docs(design): DR-43 is closed, not pending -- correct the scope doc's framing` — is twelve commits stale and is kept only as the measurement taken then, not as a description of the tree now. |
| HEAD author / date | `ThoughtMachine Agent <agent@thoughtmachine.local>` / Thu Nov 12 17:37:15 2026 +0000 `[MEASURED]` |
| branches | `master` checked out; `wip/animate`, `wip/fixes`, `wip/m2`, `wip/m3b`, `wip/ports`, `wip/seam`, `wip/seam2` (8) `[MEASURED]` |
| tracked modifications | none modified, staged or deleted |
| untracked entries | 44 `[MEASURED]` (as first read; `scripts/`, created in this pass, is not counted) |
| read at | this session, at HEAD above |

Lineage, newest first; no per-commit dates read, so **none below HEAD is stated**. Rows 1–12 were added in the pass that found the drift: the table had stopped at `af635b6` with **twelve** commits above it, and none of the twelve was present, so twelve rows were missing; the seven rows that were already here renumber 13–19. Hashes and subjects are as `git log` recorded them.

| # | commit | subject |
| --- | --- | --- |
| 1 | `5317ce5` | docs(handoff): correct the log citation counts and record the final tree state |
| 2 | `d4daf26` | evidence: commit the remaining control runs and the extended-plane B run |
| 3 | `b0956a8` | docs(evidence): relocate cited logs to a resolvable path |
| 4 | `7c72553` | docs(handoff): record validated timing, test coverage of the plane default, and the reversed log decision |
| 5 | `f254970` | test(solver): pin the ix_load + 1 extraction plane default (DR-43 residual 1) |
| 6 | `4c5c683` | evidence(vis): commit the visualiser run records instead of ignoring them |
| 7 | `c79e38e` | evidence: bank the row-10 decisions (showcase, board_poc, diode and stub artefacts) |
| 8 | `69c91a5` | chore(gitignore): ignore the root state.json (visualiser player state) |
| 9 | `a0ffd5c` | docs(handoff): close known-unknowns, record DR-43 as FIXED-TESTED |
| 10 | `8a3eb6e` | evidence(e3): bank host timing artefact (1.81x speedup) |
| 11 | `b5cf134` | fix(register): DR-44 (untracked file overwrite) and date reconciliation |
| 12 | `bd2d9b9` | docs(handoff): GEN12 onboarding package (main + wars + traps + state) |
| 13 | `af635b6` | docs(design): DR-43 is closed, not pending |
| 14 | `95ca1c1` | docs(design): scope for DR-43 S21 extraction repair |
| 15 | `1f93518` | fix(artifacts): the third thread-labelled ratio also compared two pinned runs |
| 16 | `af42368` | fix(docs): withdraw 42d319d's thread-effect claim; record the spread it really shows |
| 17 | `14093c7` | fix(evolve): a kernel on disk that cannot be imported is an error, not a fallback |
| 18 | `42d319d` | evidence(e3): second speedup data point, OpenMP thread probe, scaling summary |
| 19 | `b8b2b6a` | evidence(e3): C-arm re-run carries engine provenance; physics bit-identical |

Earlier, newest first: `c1c8276` fix(e3) engine provenance, stale-claim corrections, DR-42
cross-ref; `6cbb89d` perf(e3) FITStepper.step on the C++ kernel (Phase 1); `1921a5d`
docs(ledger) E13, parked; `be803fd` docs(register) re-date DR-41/DR-42 to 2026-11-12;
`fec3c51` docs(design) TE query for S2P convolution; `a69ed43` fix(solver) correct S21
extraction path (the repair); `8ba20ef` the second repair, paired with `a69ed43` in the register.

Untracked, 44 `[MEASURED]`: `artifacts/` (32); `docs/design/` (7 — four `GEN12_HANDOFF*` incl.
`.superseded`, `c2b_shapes.pdf`, `c2b_shapes.png`, `mispaired_metric_before.png`);
`docs/report/figures/c2b_mode_shape_corrected.png`; dirs `evidence/board_poc/`,
`evidence/showcase/`, `evidence/termination/figures/` (not listed); `state.json`.

`CONFLICT — FOUND, THEN RESOLVED; DR-45` — document dates against HEAD's date. Recorded as it stood (2026-11-14 written, 2026-11-12 available) and then corrected; the correction is DR-45 in `defect_register.md`. Two independent checks settled the direction: no commit in the repository is dated 2026-11-13 or later, so text dated 2026-11-14 cannot have existed when the 2026-11-12 commit record was made; and commit `be803fd` had already made this same correction once, re-dating DR-41 and DR-42 from 2026-11-14 to 2026-11-12. `artifacts/ladder_engine_scaling.json` independently records `assembled_utc` 2026-11-12T14:53:20Z.

| document | carried | resolution |
| --- | --- | --- |
| ledger E3 `:28` | "AMENDMENT 2026-11-14" | re-dated to 2026-11-12, with a correction sentence naming DR-45 and the evidence; no figure, verdict or status changed |
| ledger E5 `:30` | four occurrences, "AMENDMENT 2026-11-14" / "measured in this container on 2026-11-14" among them | re-dated to 2026-11-12, same note and same evidence |
| `session_open_gen11.md` | "Written 2026-11-14, at HEAD `3848d46`" | date re-dated to 2026-11-12; the `3848d46` base is a separate staleness — it resolves but is not HEAD — and is left as it stood |

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
| E3 | `:28` | C++ performance | UNVERIFIED | 2026-11-12 amendment (label re-dated from 2026-11-14 — DR-45; the retraction it records is unchanged) SUPERSEDES the ladder (50x / 5,926 ns withdrawn); re-measure 3.8/19.6/54.3/145.6/351.5 µs at 1/2/4/8/12 threads, "shape reproduces, magnitudes do not"; NOTE 2026-11-12: kernel on the call path (`6cbb89d`); only 1.76x on the 560-edge toy, a weak bound; **the ledger lags the host figure** |
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

**Correction — the 0.49 % figure belongs to the p51 phasors comparison, not to `build_A_50ohm.json`.** Prose in this package attributed the certified 0.49 % to `build_A_50ohm.json`, and that prose named the wrong artefact: **the prose was wrong, not the data.** Re-read from the files with `json.load` in this pass — `evidence/termination/build_A_50ohm_p51_phasors.json` `s11.magnitude` = 0.32556486641109117, i.e. −0.4890 % against the referee `0.327164553`; that is the 0.49 % being certified, and it is the Run B / p51 phasors artefact. `evidence/termination/build_A_50ohm.json` `s11.magnitude` = 0.32586326001662264, i.e. −0.3977 % (≈0.40 %), not 0.49 %. No figure in either artefact changed; only the citation was wrong, and it is corrected here so it cannot be repeated.

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

## 8a. Outcomes recorded for the eight questions above, 2026-11-12 (appended; the table above is unchanged)

The eight questions carried into this session, keyed by their row number in §8. Rows 6 and 9 were not among them and remain open. Nothing above this line was edited; this section is an append.

**Row 1 — the five-run host timing artefact is not banked.** OUTCOME: CLOSED as RECORDED, not as verified. Now banked in `artifacts/ladder_engine_host_timing.json` (commit `8a3eb6e`, "evidence(e3): bank host timing artefact (1.81x speedup)"): five runs per engine on structure C (`mesh_cells` 289168, 2400 steps, cell 0.4 mm) — cpp mean 27.44 s ± 0.37 (28.04, 27.47, 27.15, 27.51, 27.01), python mean 49.6 s ± 9.0 (48.4, 44.4, 42.2, 47.6, 65.5), `speedup` 1.81 (the file's own arithmetic check: 49.62 / 27.44 = 1.808). The numbers are operator-reported and the file says so in its own `provenance`: the `raw_files` are `/tmp/timing_py_*.json` and `/tmp/timing_cpp_*.json`, `raw_files_in_repo` is false, and the `manner` is "hand-copied from the operator's report; not regenerated by any script in this repository". They can be re-read, not re-derived. Ledger E3 carries the same NOTE and stays UNVERIFIED.

**Row 2 — whether the operator host runs went through the package (hence one thread).** OUTCOME: OPERATOR-ATTESTED, not measured. `emfit/_env.py:44-70` (`pin_threads`) sets `OMP_NUM_THREADS="1"` when the variable is unset, and `emfit/__init__.py:33-37` calls it at package import, so if the timed runs imported the package they ran one thread — the timing file's own `thread_count.basis` states this as an inference from the code path, not a measurement. No artefact in this repository records a thread count, and `artifacts/ladder_engine_scaling.json` states the empty search itself: each of its seven runs carries a `threads` block with `recorded_in_artefact` false and `artefact_keys_matching_thread_or_omp` set to `[]`.

**Row 3 — no many-thread kernel figure exists, so DR-42's ~33x exposure is unquantified.** OUTCOME: OPEN. DR-42's roughly 33x stays unreproduced: nothing in the seven committed runs either reproduces or bounds it — the largest ratio in `artifacts/ladder_engine_scaling.json` is 1.3877 (its `what_this_file_does_not_say` says so in those words) and no run in that file varies the thread count at all. The experiment that would settle it is named there too, in `corrections[0]` (id `C1`, field `standing_consequence`): `pin_threads` leaves a non-empty `OMP_NUM_THREADS` alone, so either run with `OMP_NUM_THREADS>1` and confirm the value reached libgomp, or probe the bare `.so` without importing `emfit`. The same field fixes the resolution any such claim must meet: repeated-run spread is about ±34 % at structure C (1.3435) and about ±16 % on the 51832-cell ladder rung (1.1595), so no timing from that file can support a claim smaller than that.

**Row 4 — DR-43 residual 1, the default plane.** OUTCOME: OPEN RESIDUAL 1, and documented as such in `docs/design/dr43_s21_extraction_scope.md`. This is a policy question, not a code question: no document in the repository records the decision either way. The default lives in `evidence/termination/run_build_A.py:1830` (`else ix_load + 1`), which the `--s21-plane-col` flag does not disturb (comment at `:1826-1828`: "the default expression is untouched, so a flag-off call still lands on ix_load + 1"). What the default lands on is gated: `tests/test_studies.py:1577` (`test_s21_plane_may_sit_downstream_of_the_cut_never_upstream`, through `:1635`) allows the extraction plane at or past the cut and refuses one upstream of it. What is NOT gated is the choice itself — a search of `tests/` for `s21_plane_col` and `ix_load + 1` returns nothing, so the driver's default expression is pinned by no test. The intent stays unrecorded.

**Row 5 — DR-43 residual 2, the ratio-of-ratios estimator.** OUTCOME: OPEN RESIDUAL 2. The remedy is a NAME, not a computation: the value needs its own `s21_provenance` field alongside `s21.planes_m`, on the pattern `evidence/termination/grade_2b.py:201` already uses (`planes = dig(doc, "s21.planes_m")` — the loader requires the plane list and treats a missing key as a problem). Separately, the withholding reason string `SPAN_S21_UNMEASURED` (`emfit/studies.py:129-139`) describes only the span fallback (branch (c), `emfit/studies.py:4137-4153`); it is simply the wrong reason for branch (b), the ratio of ratios at `:4121-4136`, which is a real transmission between two station planes.

**Row 6 — not among the eight.** Left as written (seven smaller DR-43 unknowns at `dr43_s21_extraction_scope.md:160-168`).

**Row 7 — diode field coupling never exercised by `tests/test_diode.py`.** OUTCOME: a run EXISTS; test coverage does NOT — both halves recorded. The run: `artifacts/build_D_diode.json` is present in the working tree and `evidence/termination/netlists/load_diode.json` is tracked; commit `fa671b1` ("docs(evidence): plot the diode cut's load V(t)/I(t) against the linear control") added `evidence/termination/plot_load_trace.py` (341 lines, the only file in that commit), which reads `artifacts/load_trace_A.npz` / `load_trace_D.npz` and writes `artifacts/rectification_D.png` — the figure is in the tree but was not added by that commit. The test: the gap is now stated at the top of the test file itself, `tests/test_diode.py:17`: "Nothing here reaches into the field coupling: `SpicePort` gained only a pass-through `max_iter`, and the diode is exercised on the standalone network where an exact answer is available." The row's `[UNVERIFIED — carried from the brief]` concern was coverage, and the file's own docstring states its absence; what does not exist is a test that drives the coupling term.

**Row 8 — whether any referee artefact was regenerated after DR-41 was fixed.** OUTCOME: YES. `evidence/referee/s11_extraction.json` was last touched by `89aa2f1` ("evidence: raw time-domain records behind the E12 referee result"), and its own contents rule out the pre-fix launch: it records `port1_api` "mslport" — the post-fix MSLPort port — with `s11_abs` 0.3271645531273824 (`:94`, `:99`; `s11_ref50_abs` carries the same value at `:112`). That commit's provenance, read off the artefact rather than off a document, is the dated record of which run E12's number came from.

**Row 9 — not among the eight.** Left as written (how many test files have ever run in one sweep).

**Row 10 — which untracked paths are wanted and which are junk.** OUTCOME: a DECISION, not a fact; recorded here as a recommendation for the operator to accept or reject. Recommended: commit `evidence/showcase/`, `evidence/board_poc/` and `evidence/termination/figures/` — three untracked evidence directories with content; leave `.scratch/` alone (working files, ~400 of them at its top level); and for the loose `*.log` files at the repository root, extract what matters into a note and then delete them rather than committing them. Separately, `artifacts/` also holds around thirty untracked test artefacts (`build_B_100ohm.json`, `build_C_plain_cut*.json`, `build_C_stub*.json`, `box_sweep_z0.*`, `passivity_sweep_A*.json`, `e3_*.tsv`, `sliding_window_refit.*`, `smoke_A/B.json` and others); whether any of those is evidence rather than scratch output is a second decision, not this one.

**Status of DR-43 after these eight.** DR-43 is FIXED-TESTED in the register's own words (`docs/design/defect_register.md:828`; heading `:824`): the writer publishes |S21| only when an estimator names the plane it was taken on, writes the eight `s21` numeric keys as null with an unchanged key set when it does not, and the gate reports `NOT_ASSESSABLE` with a null `power_sum` instead of summing a ratio. Rows 4 and 5 above are its two open residues, and the register keeps one further gap of its own open (pre-DR-43 artefacts carry no `s21.measured`/provenance key, so absent and null are indistinguishable). This note does not claim the suite is green: DR-39 (see §3 above) records 49 test files / 584 tests against a best recorded sweep short of both.

## 8b. What changed after 8a, 2026-11-12 (operator decisions banked)

Six items, each keyed to the row or question above that it touches. Nothing above this line was edited; this section is an append.

**Item 1 — the timing artefact is now machine-validated; one caveat in row 1 is discharged, row 1 itself is unchanged.** Both ladder JSONs were parsed, not eyeballed, inside the already-running container `sweep` (python 3.12.15, workdir `/workspace`; no new container, 6 of 6 in use): `python3 -m json.tool artifacts/ladder_engine_host_timing.json` exit 0, the same command on `artifacts/ladder_engine_scaling.json` exit 0, and `json.load()` on each exit 0. That discharges the inspection-only caveat carried in commit `8a3eb6e` for well-formedness and for nothing else. Row 1 of §8a stands unchanged in substance: the `/tmp` raw files behind the 1.81x are not in the repository, so the figure remains recorded, not reproducible — validity checked, provenance still not. A naming trap cost a round trip and is recorded so it does not cost a second one: `artifacts/ladder_engine_scaling.json` (27,602 B, pre-existing, tracked) is NOT the file whose validity was in doubt; `artifacts/ladder_engine_host_timing.json` (5,204 B, added in `8a3eb6e`) is. Row 3 depends on the scaling artefact and the artefact cannot settle it: `recorded_in_artefact` is false in all seven of `runs[i].threads`; `launch_omp_num_threads` reads `unset (inherited)` for runs 0, 1, 2, 4 and 5 and `1` for runs 3 and 6; and `cpu_count_recorded_in_artefact` is 12 for runs 0–3 and null for runs 4–6. The file does not record the thread count it ran at, which is precisely why row 3 cannot be closed from it.

**Item 2 — row 4's coverage gap is now pinned by a test, and residual 1 stays OPEN.** `tests/test_extraction_plane_default.py` (110 lines, 3 tests, commit `f254970`) is the first test in this repository to constrain `run_build_A.py`'s S21 plane when no `--s21-plane` is passed. It imports `run_build_A` and calls `build_kwargs`, so it is behavioural rather than a source-text tripwire: with default Run A arguments `cell_m` is 0.4 mm, `ix_load` resolves to 50, `S21_PLANE` is still the literal `'cut'`, and `build_kwargs` returns `s21_plane == ix_load + 1 == 51`; `s21_plane_index=7` resolves to 7 and `s21_plane_col=53` resolves to 53, which shows the default branch is only the flag-off path. Non-vacuity was shown by this repository's own method: mutating `run_build_A.py:1830` to `else ix_load + 2` fails exactly this test with `assert 52 == (50 + 1)`; restoring the line returned sha256 `1eccee126e358f948838010df76dc638a4c89ad45c0eb66c0b1aeb871e5cce27`, identical to pre-mutation, and the file then reported `3 passed in 0.06s`. `run_build_A.py` is at HEAD content and carries no mutation. What changed is narrow: **residual 1 remains OPEN** — the driver still performs no extraction and the default is still `ix_load + 1`; it is simply no longer a default that NO test constrains. Two limits belong with it. It asserts nothing about any artefact's `s21.planes_m`, because every candidate artefact is pre-DR-43 and none is demonstrably a default-plane run, so such an assertion would pin a fixture rather than the driver. And the Run A argument namespace is restated in a helper because the parser is built inside `main()`, with `assert ix_load == 50` as the staleness tripwire — a parser factory in `main()` would remove the restatement and is a real follow-up, not done. The tree moves from 49 test files to 50, and nothing here claims a green suite (DR-39).

**Item 3 — the untracked evidence is banked, and one row-10 decision was reversed.** Commits `69c91a5` (.gitignore), `c79e38e` (evidence), `4c5c683` (vis run records) and `f254970` (the test) carry it. `c79e38e` commits 21 files: `evidence/showcase/` (8 PNGs), `evidence/board_poc/` (6 files), `evidence/termination/figures/` (3 PNGs), `artifacts/build_D_diode.json` (21,200 B), `artifacts/rectification_D.png` (104,084 B), `artifacts/build_C_stub.json` (22,734 B) and `artifacts/build_C_stub_pulse.json` (22,225 B). Row 7's gap closes on the artefact side — `fa671b1` committed the plotting code while the data it plots stayed untracked, and both halves are in the tree now — but row 7's other half stands untouched, namely that `tests/test_diode.py:17` says itself that nothing reaches the field coupling. THE REVERSAL, stated as a reversal: the decision to add an `artifacts/vis_*.json` ignore rule was rejected because the repository contradicts it twice — `docs/design/visualizer_architecture.md:121` says `.gitignore` has NO `artifacts/` rule and that the `vis_run_*.json` records are what is committed beside the field dumps (`:128`, `:134`), and `server/poc_app.py:102` hardcodes `artifacts/vis_run_B_100ohm.json`; ignoring them would ship a committed hardcoded path that no fresh clone could resolve, so `4c5c683` commits all three records instead. The reversal condition, recorded so the decision is not reopened by drift: if the opposite is ever preferred it takes `git rm --cached` on all three, the ignore rule, AND an amendment to `visualizer_architecture.md:121` — the doc change is mandatory, not optional. KEPT: `/state.json` stays ignored, root-anchored because a bare rule would also swallow `build/wavedude_state.json` (12,449 B, and no code depends on it). NOT ADDED: any `artifacts/*.npz` rule, since the blanket `*.npz` rule with its `!tests/data/*.npz` exemption already covers it.

**Item 4 — the root `*.log` deletion was NOT carried out, the finding is larger than the deletion, and the decision the finding left open is now closed by relocation.** Five root logs plus one hidden file were found at the root: `attribution.log` (1,176 B, 19 lines), `mode_plot.log` (2,577 B, 36), `pecbox.log` (13,618 B, 178), `result.log` (5,250 B, 64), `result2.log` (7,303 B, 87) and `.pytest_full.log` (2,191 B, hidden and not matched by the `*.log` glob). None was deleted, because committed material cites them BY LINE NUMBER. The audit, restated with the corrections a re-check forced: `mode_plot.log` 79 times — `docs/design/zfree_diagnosis.md` 71, `decisions.md` 5 (two of them on one line, at `:7769`), `docs/design/zfree_shape.md` 2, `d52b_claim_inventory.md` 1 — plus the occurrence in `EM_SOLVER_LEDGER.md:34`, which is a tree-state observation and not a citation (it names the file as loose at the root and quotes none of its lines); `pecbox.log` 14 times, every one of them in `tests/test_mode2d.py`, at lines 4, 9, 19 (twice), 22, 67, 72, 154, 158, 159, 175, 198, 235 and 236, two of the fourteen inside string literals rather than at a citation (the assert f-string at `:175` and the `xfail` reason at `:235`); `attribution.log` once (`README.md:131`); `result.log` not at all once the five citations this item first recorded are read properly — `RESUME.md:58`, `:201`, `:215` and `decisions.md:1504` point at `.scratch/host/poynting-7.8333/result.log`, a different file (13,204 B, mtime 2026-10-21 19:44) from the root `result.log` (5,250 B, 2026-10-26 23:59), so the root file has no citation to keep resolvable and those five were left bare rather than rewritten; and `result2.log` cited by nothing either, the count of 1 this item first recorded not surviving a re-search. The finding is larger than the deletion: `*.log` is already an entry in `.gitignore`, so every one of those cited files was invisible to git and absent from any fresh clone — committed documentation cited evidence the repository refused to contain, and a test file cited line numbers into one of them. Deleting them would have destroyed the only copy of what those documents describe, which is the exact loss DR-44 exists to record, while changing nothing about repository state. The decision this left open — stated with both options and neither taken, force-add the cited logs or treat the citations as unverifiable and annotate them — is now CLOSED, and closed by relocation, which was neither of the two options. All five cited logs are in `evidence/logs/` at byte-identical sizes (`attribution.log` 1,176 B, `mode_plot.log` 2,577 B, `pecbox.log` 13,618 B, `result.log` 5,250 B, `result2.log` 7,303 B); `.gitignore` gained `!evidence/logs/*.log` immediately after the `*.log` rule, with a comment saying why; and every citation that pointed at a root log was rewritten to the new path with its `:line` suffix preserved, so it resolves to the same line of the same bytes. Nothing was force-added and no citation was annotated as unverifiable. `.pytest_full.log` (2,191 B) stays at the root deliberately: it is hidden, matched by no glob, and cited by nothing, so no citation depends on it and no rule would carry it. This supersedes the recommendation in row 10 of §8a, which was made before the reference audit: the audit found those logs cited by line number 79 (`mode_plot.log`), 14 (`pecbox.log`) and 1 (`attribution.log`) times from committed material, including `tests/test_mode2d.py`, so the recommendation is withdrawn rather than merely unexecuted — and the withdrawal does not rest on the counts, it rests on the citations.

**Item 5 — a schema finding that widens a known gap.** All six of the build JSONs that were candidates for commit were parsed and every one is PRE-DR-43: 19 `s21` keys, no `measured`, no `provenance` — three of them went in with `c79e38e` (`artifacts/build_D_diode.json`, `artifacts/build_C_stub.json`, `artifacts/build_C_stub_pulse.json`) and the other three have since followed (Item 6) — `artifacts/build_C_plain_cut.json`, `artifacts/build_C_plain_cut_pulse.json` and `artifacts/build_B_100ohm.json`, the last committed under the corrected name `artifacts/build_B_100ohm_plane_extended.json` with its bytes unchanged — so all six are tracked now, and which commit carried which file changes nothing about the schema finding. The files and sizes: `artifacts/build_D_diode.json` 21,200 B, `artifacts/build_C_stub.json` 22,734 B, `artifacts/build_C_stub_pulse.json` 22,225 B, `artifacts/build_C_plain_cut.json` 19,442 B, `artifacts/build_C_plain_cut_pulse.json` 19,287 B and `artifacts/build_B_100ohm.json` 18,465 B. The register's own "Known gap — open, not closed by this entry" therefore applies to more files than it named, and banking these runs makes none of them evidence about which plane an S21 was taken on. A duplicate-check finding belongs beside that: `artifacts/build_B_100ohm.json` (18,465 B; committed as `artifacts/build_B_100ohm_plane_extended.json`) is NOT a duplicate of the tracked `evidence/termination/build_B_100ohm.json` (10,083 B) — different sha256, 7 extra `s21` keys, `planes_m [0.0104, 0.02]` against `[0.0032, 0.02]`. It is a separate run at a different extraction plane. It was left untracked until it could be labelled, because committing it as `build_B_100ohm.json` would have read as a duplicate of the B arm while actually being a third plane point; that label now exists and the file is committed under it (Item 6). `build_C_plain_cut.json` and `build_C_plain_cut_pulse.json` were not in the decision either and were left for a further one, which Item 6 also records.

**Item 6 — the remaining build JSONs are committed, one of them under a corrected name.** The two control runs went in as they stood: `artifacts/build_C_plain_cut.json` (19,442 B) and `artifacts/build_C_plain_cut_pulse.json` (19,287 B), which closes the untracked half of Item 5. The third did not go in as it stood: `artifacts/build_B_100ohm.json` (18,465 B) was committed as `artifacts/build_B_100ohm_plane_extended.json`, bytes unchanged, because the file is a separate run from the tracked `evidence/termination/build_B_100ohm.json` (10,083 B) and the two carry different extraction planes — `planes_m [0.0104, 0.02]` here against `[0.0032, 0.02]` there, different sha256 and 7 more `s21` keys — so the bare `build_B_100ohm.json` name would have read as a duplicate of the B arm rather than as a third plane point. Renaming the artefact repairs the record, not the producer: `evidence/termination/run_build_A.py:621` still defaults structure B's output path to `artifacts/build_B_100ohm.json`, and that default was left alone deliberately, because editing a committed evidence generator to agree with a repository-hygiene rename would change a run's identity in order to fix a filename. This item therefore RECORDS the mismatch rather than repairing it — a fresh structure-B run still lands under the unlabelled name and would need the same rename — and the repair, if it is wanted, is a label in the artefact or a parameterised output path, not a `git mv` performed twice. Nothing here moves a schema finding: all of these files, like the three in Item 5, are PRE-DR-43 — 19 `s21` keys, no `measured`, no `provenance`.

