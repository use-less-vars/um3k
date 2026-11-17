# UNDERSTANDING — the `emfit` repository, for someone who has just arrived

*Every claim below carries a `path:line`. All line numbers were verified against the tree as it
stands now (not against a handoff document — the two disagree by ~170 lines because `poc_app.py`
has grown; when prose and a cited line disagree, **the line wins**). Anything I could not verify
is marked `UNVERIFIED`.*

---

## 1. What this is, who it is for, and what "CMEX" means

**What.** `emfit` is a **Finite Integral Technique (FIT) solver for computational
electromagnetics**, plus a browser viewer for the fields it produces. `README.md:1-14`: it
integrates the time-domain Maxwell equations on a structured, non-uniform grid using the FIT/FDTD
operator pairs (discrete curl matrices on a dual grid, material matrices), in pure Python +
NumPy/SciPy, with an optional C++ kernel for the inner loop (`./build/cpp/emfit_core*.so`, built by
hand per `README.md:20-30`, and parity-tested against frozen Python goldens at tolerance **zero**).
`README.md` also states the house rule that makes the repository unusual: *"a research instrument:
every number it produces is traceable to a recorded artefact."*

**Who for.** The operator brief is `Intro.txt` (~27 KB): an EE who wants EM-field simulation tools
for PCB work, taught FIT by his own professor (Thomas Weiland, who invented FIT — hence the
preference over FEM). The brief's own engineer memos reframe the goal sharply: the product is
*"layout-to-S-parameter and field-visualization engine for PCBs"*; ports and KiCad import are the
product; solver perfectionism is to be resisted — *"your current solver is ahead of your product"*,
*"A tool that simulates one microstrip correctly is worth more than a tool that simulates a cavity
perfectly and a PCB not at all."* The operator manages lightly and wants to *"see and feel something
works."* Secondary goals in the brief (HF/antenna solver, leapfrog, maybe parareal, a LaTeX research
document) are goals, not current state.

**What "CMEX" means.** `CMEX.kicad_pcb` (445,613 B, 6,083 lines, mtime 2023-09-24) is a **real
8-layer KiCad board** that is used as the **KiCad-parser fixture** and is explicitly **not** a
simulation target. `Intro.txt` §11 says so in as many words: at 174,720 cells / 549,319 edges /
14,331 steps it is unaffordable, and at 1 mm resolution the copper pours cover the board to within
a cell, so it meshes as "eight solid plates"; *"Use it for netlist and stackup parsing only."*
Form census (`decisions.md:597`): 891 `fp_line`, 583 `segment`, 81 `via`, 388 `pad`, 81 `footprint`,
12 `gr_rect`, 4 `zone`, 93 nets, 1.6 mm stackup; the only occurrence of the substring "arc" in the
file is inside a property value (a distributor URL) — i.e. the file has no arcs to parse. The
companion fixture is `kicad_support_project/kicad_support_project.kicad_pcb` (44,710 B: 4
`gr_line` on Edge.Cuts, 66 `fp_line`, 58 `segment`, 12 `pad`, 3 `footprint`, 2 `zone`, 0 via) plus
seven gerbers.

> **No document anywhere in the tree expands the acronym "CMEX".** It is a commercial-style board
> name. Treat the expansion as `UNVERIFIED`; do not invent one.

---

## 2. The physical object, and what this code does *to* it

**The object being solved.** A **microstrip line**: a copper strip of width `w` on a dielectric
substrate of thickness `h` and permittivity `eps_r`, over a ground plane, driven by a pulsed/Ricker
source at one port ("port p1") and terminated at the far end ("p2") by a load — for the reference
case a 50 Ω `series_r` (`scripts/run_reference_sim.py:1-30`). The default mesh is
**62 × 212 × 22 = 289,168 cells at 0.4 mm**, which is 24.8 × 84.8 × 8.8 mm
(`artifacts/reference_sim_volume.npz`, `--dump-state` block `field_dump.extent_domain_mm`). The
`Ez` component is the one stored: a wave travelling along `y` on the strip, in a quasi-TEM mode whose
propagation constant `beta` is fitted from the fields rather than assumed.

**Solver, consumer, or plotter? — all three, and it is important to keep them apart:**

| role | verdict | evidence |
|---|---|---|
| **Solver** | **yes, and it is in-repo** | `emfit/evolve.py` (`cfl_dt:74`, `FITStepper:83`, `step:186`, `energy:210`, `RickerSource:272`, `Leapfrog:304`), `emfit/maxwell.py` (`FITSystem:30`), `emfit/pml.py` (`PML:402`), `emfit/raster.py` (board → mesh), `emfit/mode2d.py` (`solve_modes:906`, an actual 2-D generalized eigenproblem), `emfit/ports.py` (1918 lines: `fit_beta:861`, `fit_line:1058`, `StationFit:1290`), `emfit/eigen.py` (dense cavity pencil), `emfit/studies.py` (336 KB of study drivers), `emfit/microstrip.py` (Hammerstad–Jensen closed form — an **analytic reference**, not a solver: `Z0_QS=95.453370`, `eps_eff_QS=3.049914164`, `Z0=92.698533` at t = 35 µm), `emfit/mie.py` (exact 2-D Mie series — again a reference, "not a solver"). 45 modules, ~1.42 MB. |
| **Consumer of an external EM solver** | **no — nothing is wired** | `grep -rn openems` over 439 `*.py` and all of `docs/` = **0 matches** (`docs/design/pipeline_map.md` §2, §3(iii)). openEMS exists only as an *intended referee* (`docs/design/openems_referee_spec_2026-11-10.md`, ledger E12). What the repo *does* consume is (a) KiCad geometry (`emfit/kicad.py`, `gerber.py`, `netlist.py`) and (b) its **own** recorded artefacts (`evidence/**/*.json`, `artifacts/*.npz`). |
| **Plotter / deriv** | **yes — S-parameters and pictures come out of its own fields** | S-params: `emfit/ports.py` (`edge_path_voltage:79`, `plate_current:395`, `station_poynting:470`, `travelling_waves:681`, `reflection:727`, `transmission:745`, `fit_beta:861`, `fit_line:1058`) + `emfit/modal.py` (`modal_station_phasors:372`, `modal_sparams:685`). Pictures: `server/poc_app.py` (13,465 lines) + `server/um3k_panels.py`, with matplotlib PNG charts at `poc_app.py:2063`, `:2317`, `:2448` and PyVista 3-D at e.g. `:4660` (`pv.Plotter(off_screen=True)`) and `:8509`/`:8791` (`pv.ImageData`, `pv.PolyData`). |

**"Characteristic mode" — a phrase to be careful with.** The string "characteristic mode" does
**not occur anywhere** in the tree (`grep -r "characteristic mode"` over `*.py`/`*.md`/`*.json` =
0 matches). What this repository calls a *mode* is one of two different things, neither of which is
Characteristic Mode Analysis (CMA):

1. a **transverse eigenmode of a port cross-section** — a 2-D generalized eigenproblem with `beta`
   as the eigenvalue (`emfit/mode2d.py:906 solve_modes`, `assemble:431`, `assemble_mixed:503`;
   `emfit/mode_profile.py:535 microstrip_mode_profile`; `emfit/modal.py:267 plane_mode`), used for
   modal launch / de-embedding; and
2. a **cavity eigenmode** `f_mnp` of a closed PEC box (`emfit/eigen.py`; `emfit/studies.py:455
   _run_cavity`), used as an analytic gate.

---

## 3. The pipeline, stage by stage (input → output, code, and whether it is real)

```
 (1) GEOMETRY                (2) MESH                 (3) OPERATORS
 board + stackup     ──▶  structured grid     ──▶  curl matrices C, Ĉ ;
 (analytic mm)            (node coords)            material matrices M_eps, M_mu
 emfit/board.py           emfit/raster.py          emfit/maxwell.py
 MicrostripBoard          build_grid:316-330       FITSystem:30
 REAL                     REAL                     REAL
      │                        │                        │
      └────────────────────────┴───────────┬────────────┘
                                           ▼
 (4) TIME STEPPING          (5) BOUNDARY            (6) RECORDER → npz
 leapfrog update on          PML on x,y (20 cells,     |E| planes every step,
 E and H, Ricker pulse       2nd order, target 1e-4)   |E| volume every
 emfit/evolve.py             + Mur 1st order ABC       volume_stride frames
 cfl_dt:74 FITStepper:83     emfit/pml.py:402          run_build_A.py
 step:186                    emfit/abc.py              _VisRecorder:1052
 REAL                        REAL                      REAL
                                           │
                                           ▼
 (7) DUMP FILE  artifacts/reference_sim_volume.npz  46 keys, 40,407,762 B,
     schema "emfit.vis/2"  REAL  ◀── the artefact every downstream stage eats
                                           │
              ┌────────────────────────────┼───────────────────────────────┐
              ▼                            ▼                               ▼
 (8) S-PARAMS (offline,        (9) VIEWER LOAD              (10) PAGE / UI
     SEPARATE run)              poc_app.load_any_dump:725    run_web_vis:9894
 ports.fit_beta:861 /           → load_vis:520 (16 mandatory  (3-col: um3k_panels
 fit_line:1058 /                keys) or load_dump:203       build_left_panel:16 /
 StationFit:1290                REAL                          center:50 / right:307)
 → evidence/…_phasors.json                                   REAL, UI UNTESTED
 REAL CODE, RECORD IS          (11) PLAYER  two clocks        (12) CHARTS
 UNVALIDATED and from a        _volume_player_plan:9007      matplotlib → PNG data-URI
 DIFFERENT mesh                pure function, 21 tests       :2063 / :2317 / :2448
                                                             REAL
              │                            │
              ▼                            ▼
 (13) FAR FIELD  emfit/ntff.py,     (14) job.v1 SCHEMA        (15) openEMS
      --surface-dump (schema          schemas/emfit.job.v1      REFEREE
      "emfit.surface-dump/1")         .schema.json + tools/     does not exist
      SCAFFOLD: no shipped            host/validate-job-schema.py
      surface dump exists             SCHEMA ONLY, NO LOADER
```

Per-stage detail, with the **input**, **output**, **code** and **real-vs-placeholder** verdict:

| # | stage | input | output | code (`file:line`) | real / placeholder |
|---|---|---|---|---|---|
| 1 | geometry | board params (mm) or a `.kicad_pcb` | `MicrostripBoard` in **metres** (single mm→m site, `TOL=1e-12`) | `emfit/board.py` (`MicrostripBoard`, `_snap` raises at `:545-551`); `emfit/kicad.py` (`load_board`) | **real** (CMEX parses; it is never meshed) |
| 2 | mesh | board | `Grid` — frozen node coordinates, `widths=np.diff` | `emfit/raster.py:316-330`, `:57-62`; `emfit/grid.py`; for the reference arm `evidence/termination/run_build_A.py:967 vis_geometry` | **real** |
| 3 | FIT operators | grid | sparse `C`, `Ĉ`, material matrices | `emfit/maxwell.py:30` | **real** |
| 4 | time stepping | operators + source | `E,H` per step; CFL `dt` | `emfit/evolve.py:74` (`cfl_dt`), `:83`, `:186`, `:272` (Ricker), `:304` (leapfrog); optional C++ kernel `src/emfit_core.cpp` + `src/bindings.cpp` | **real** (energy conservation gated in a *closed box* only — see REALITY_CHECK) |
| 5 | boundary | grid | absorbing x,y faces; PEC/PMC elsewhere | `emfit/pml.py:402` (`PML`, `AbsorbedWork:211`), `emfit/abc.py` (`Mur1Boundary`) | **real** and gated (`tests/test_pml.py`, `test_pml_audit.py`, `test_abc.py`) |
| 6 | recorder | `FITStepper` | the npz payload (planes + optional volume + optional load trace) | `evidence/termination/run_build_A.py:1052` (`_VisRecorder`), `:1151` (`__call__`), `:1188` (`payload`); volume gate `:1076-1085`, frame rule `:1170-1174`; budgets `:886 _vis_plan_stride`, `:945 _vis_volume_budget_check` | **real** |
| 7 | dump file | recorder | `*.npz` with `schema="emfit.vis/2"` | producer: `scripts/run_reference_sim.py` (drives stage 1-6, writes `artifacts/reference_sim_volume.npz` + `artifacts/reference_sim_run.json`) | **real** — 40 MB artefact, committed to the working tree |
| 8 | S-parameters | fields at stations / modal basis | `evidence/termination/build_A_50ohm_p51_phasors.json` (`s11_two_wave=0.32556486641109117`, `validation_status="UNVALIDATED"`) | `emfit/ports.py:861`, `:1058`, `:1290`; `emfit/modal.py:685` | **real code, unvalidated record, and from a different mesh than the shipped dump** (72×212×22 vs 62×212×22 — the viewer flags this as `mismatch.flag=true`) |
| 9 | viewer load | any npz | a page dict `{path, info, planes, multifreq, record, structure_id, is_vis}` | `server/poc_app.py:725` (`load_any_dump`) → `:520` (`load_vis`, 16 mandatory keys) **or** `:203` (`load_dump`, legacy) | **real**, with three npz dialects (see §4) |
| 10 | page / UI | page dict | the served page | `run_web_vis:9894` (modern, 3-column) vs `run_web:5922` (legacy, 853 lines); panels `server/um3k_panels.py:16/50/307`; `PageContext` at `server/um3k_context.py:160`, built at `poc_app.py:10324` | **real**, but no test lets trame dispatch, so UI *behaviour* is untested |
| 11 | player | `info` | one coherent moment of volume + plane | `poc_app.py:9007 _volume_player_plan`, helpers `_volume_frame_for_step`, `_monotonic_axis`, `_synced_frame_counts` | **real and the best-tested subsystem** (pure function; 21 tests in `tests/test_animation_volume.py`, all pass) |
| 12 | charts | multifreq JSON / port record / load trace | base64 PNG data-URI | `poc_app.py:2063`, `:2317`, `:2448` (each fenced by `try/except` → "chart render skipped") | **real** |
| 13 | far field | Huygens surface archive (`--surface-dump`) | far-field pattern | `emfit/ntff.py`, `emfit/huygens.py`, `huygens_fields.py`, `nearfield.py`, `antenna.py`; refuse-by-name at `poc_app.py:725-807` | **scaffold in practice**: no shipped npz carries the surface keys, so the tab cannot render on any artefact in the tree |
| 14 | job schema | `schemas/examples/microstrip_stub.job.json` | a *validated file*, not a run | `tools/host/validate-job-schema.py` + `schemas/emfit.job.v1.schema.json` | **scaffold**: `grep 'schema\|job.json\|load_job'` over `emfit/*.py` = 1 unrelated hit (`kicad.py:664`). There is no job loader. |
| 15 | external cross-check | — | — | `docs/design/openems_referee_spec_2026-11-10.md` (ledger E12) | **absent** |

---

## 4. The data contract: what an npz must carry

The viewer dispatches on the npz `schema` key and nothing else (`poc_app.py:725 load_any_dump`).
There are **three dialects in the tree and only one of them animates**:

| dialect | discriminator | loader | page you get |
|---|---|---|---|
| `emfit.vis/2` (current) and `emfit.wavedude/1`, `emfit.wavedude/2` (legacy schemas, read by the same loader) | `schema` in `VIS_SCHEMAS` (`poc_app.py:158-161`, `VIS_FORMAT="um3k"`) | `load_vis:520` | modern `run_web_vis` 3-column page |
| **legacy plane dump** | *no* `schema` key at all, carries `plane_ez` | `load_dump:203` | legacy `run_web` single page (`:5922`) |
| `emfit.surface-dump/1` (Huygens archive) | `schema == SURFACE_DUMP_SCHEMA`, or the 18-key signature with no `plane_ez` | `emfit.ntff.load_surface_dump` validates it, then the viewer **refuses it by name** (`poc_app.py:790-807`) | none — "nothing in this viewer draws surface currents" |

**Mandatory keys for `emfit.vis/2`** (`poc_app.py:520-560`; missing any one ⇒ `SystemExit(2)`):

| key | shape / type | meaning |
|---|---|---|
| `schema` | str | must be one of `VIS_SCHEMAS` |
| `ez_ycut` | `(nt, nx, nz)` float | x–z sheet at one fixed y — the **plane clock** |
| `ez_xcut_near`, `ez_xcut_far` | `(nt_x, ny, nz)` float, equal shapes | y–z sheets at two fixed x — written every `dump_stride * 10` steps |
| `t_ns` | `(nt,)` float | frame time; **index only with that plane's own `frame_index`** |
| `frame_index`, `frame_index_xcut` | `(nt,)`, `(nt_x,)` int | the two planes' step indices |
| `x_mm`, `y_mm`, `z_mm` | `(nx,)`, `(ny,)`, `(nz,)` | node coordinates |
| `nx`, `ny`, `nz`, `nt`, `nt_x` | int | counts, checked against every array above |
| `dt_s`, `cell_m` | float | time step and cell size |

**Optional blocks** (absent ⇒ `None`/NaN, and the UI prints "not recorded"; it never invents a value):

| key | why it matters |
|---|---|
| `engine`, `created_utc` | provenance text |
| `structure_id`, `load_ohm` | which arm / what termination. **Absent from a version-1 dump** — absent means *not recorded*, not "guess from geometry". The readout text reads these from the **dump**, never from the registry (`_structure_readout_text:862`) |
| `j_cut` | the y **sample index** the x-z sheet came from (`_npz_int_or_none`) |
| `dump_stride`, `nsteps` | defaults 1 / 0 |
| `f_ref_hz`, `f_pulse_hz` | the CW reference and the pulse band edge |
| `xcut_near_mm`, `xcut_far_mm`, `port_x_mm`, `load_x_mm`, `substrate_h_mm`, `strip_w_mm`, `eps_r` | geometry the overlays draw |
| `v_analytic_m_s`, `v_measured_m_s`, `t_traverse_ns`, `v_measured_reliable`, `velocity_note` | the velocity readout; the dump marks its own fit good/bad and the page repeats that verdict |
| `e_abs_volume` + `e_abs_volume_step_index` (**atomic**, `poc_app.py:630-644`, validated `:690-710`) | the **volume clock**: `(n, nx, ny, nz)` plus the step index of each frame. Half a volume is treated as *no* volume: "half a volume says nothing about which steps its frames are" |
| `e_abs_volume_stride` | frame cadence in *frames*, not steps |
| `load_t_ns`, `load_v`, `load_i`, `load_netlist_json` (+ `load_ohm`) | the load's own V(t)/I(t) trace; all-or-nothing, lengths must agree, "refusing to truncate to the shorter array" (`poc_app.py:470-527`) |

**Which shipped file is richest?** `artifacts/reference_sim_volume.npz` — **46 keys, 40,407,762 B,
`schema="emfit.vis/2"`, `ez_ycut (2400, 62, 22)` + `e_abs_volume (24, 62, 212, 22)` at
`e_abs_volume_stride=100`, plus the load trace and the netlist JSON.** It is the *only* shipped file
that carries the volume block, i.e. the only one on which the 3-D scrubber and the two-clock player
have anything to play.

Runner-ups (measured, `np.load(...).files`):

| file | keys | planes | volume | what it lacks |
|---|---|---|---|---|
| `artifacts/reference_sim_volume.npz` | **46** | 2400 × (+240 ×2) | **24** | nothing |
| `artifacts/live_run.npz` | 43 | 2400 × (+240 ×2) | — | `e_abs_volume*` |
| `artifacts/vis_dump_B_100ohm.npz`, `artifacts/vis_dump_selftest.npz` | 38 | 300 / — | — | volume; selftest is schema `wavedude/2` |
| `artifacts/vis_dump_1500.npz` | 36 | 1500 | — | volume; schema `wavedude/1`; no `structure_id`/`load_ohm` |
| `artifacts/smoke_A.npz`, `smoke_B.npz`, `_probe_dump.npz` | 36 | small | — | volume |
| `evidence/termination/build_A_50ohm_p51_ghostwave_fields.npz` | **11** (`e,h,plane_ez,plane_hy,plane_ey,plane_hz,nstep,nx,ny,nz,cell_m`) | 9 stations, complex | — | **not a vis dump at all**: dialect 2, no `schema` — and this is the *only* field dump the structure registry points at |

---

## 5. A user session, step by step — including exactly where it dead-ends

All commands were run from the repo root. (In this sandbox the repo `.venv` is a Python-3.12
tree while `python3` is 3.13, so the working invocation adds
`PYTHONPATH=.venv/lib/python3.12/site-packages:.`; on the operator's machine plain `python3` works.)

1. **Type the obvious command.** `python3 server/poc_app.py`. It boots, prints
   `[poc_app] serving on http://127.0.0.1:8080` (`DEFAULT_HOST`/`DEFAULT_PORT` at
   `poc_app.py:140`/`:143`), and `curl` returns the trame shell.
2. **Notice what page you got.** `--dump-state` on the same default invocation reports
   `format: "legacy"`, `schema: "emfit.poc-state/1"`, `animation: null`, input
   `evidence/termination/build_A_50ohm_p51_ghostwave_fields.npz`. So **the default boot opens the
   legacy 853-line single page** (`run_web:5922`), *not* the 3-column `run_web_vis:9894` UI that all
   the design documents describe. Cause: the registry's only field dump is a legacy plane dump
   (11 keys, §4), and `load_any_dump` dispatches on that.
   → **DEAD END #1: the app a newcomer runs is not the app the docs describe.**
3. **Look at the structure selector.** `structures.json` has exactly three entries and its own note
   says "There is exactly one published field dump in the tree". `build_A_50ohm_100ohm` and
   `build_A_series_R` are `"record only"`: no dump on disk, so selecting them is refused with
   `--structure <id> is record only: this registry entry has S-parameters recorded but no field
   dump on disk … the entry opens as its BOARD page and nothing else` (`poc_app.py:1452`). The
   `_structure_is_record_only` test is a filesystem check, never a hand-maintained flag (`:1422`).
   → **DEAD END #2: two thirds of the registry cannot be opened.**
4. **Read the S-parameters of the one entry that opens.** The CLI already warned:
   `no multi-frequency sweep in …/evidence/termination (tried no candidate for this arm, none of
   which is a readable file); the |S11|/|S21| panel will say so`.
   → **DEAD END #3: on the default page the S-Params panel says "No sweep file found".**
5. **Get to the modern UI.** The documented route is the one command `scripts/run_reference_sim.py`
   prints (`:84`): `python3 server/poc_app.py --input artifacts/reference_sim_volume.npz`.
   (`--input` wins over `--structure`, `poc_app.py:1415-1460`.) This works — I ran it: HTTP 200,
   1,383-byte shell, and the boot log announces
   `animation: 24 frames on ez_ycut, 24 on each x-cut, played at 24 fps` (`poc_app.py:13258-13260`)
   and `each frame's sim time is rebuilt from its own plane's frame index`.
   → This is the **happy path**, and it exists *only* because someone wrote a script that knows the
   four coupled flags; the GUI cannot produce a volume dump itself.
6. **Scrub.** The player now has a **plane clock** (2,400 stored `ez_ycut` frames) and a **volume
   clock** (24 `e_abs_volume` frames at stride 100). `_volume_player_plan:9007` maps one coherent
   moment: its invariants are `steps == volume steps`, `frames == len(steps)`,
   `state.frame_max == len(steps)-1`, `plane[0] == 0`, `axis[index] == steps[position]`, and the last
   frame must land on the last captured plane. The readout shows the **plane** frame's time
   (`sim time: t = … ns`). Tick the volume, and the volume walks 0→1→2…
7. **Look at the right-hand DATA tabs** (`RIGHT_TABS` at `um3k_panels.py:240-262`; five tabs:
   S-Params, Far Field, Confidence, Modes, Circuit).
   → **DEAD END #4: the Far Field tab cannot render on any artefact in the tree** — it needs a
   `--surface-dump` Huygens archive and no shipped npz is one; the viewer refuses such a file *by
   name* if you supply one and there is none to supply.
8. **Read the S-params of the page you are now on.** The chart appears — but the page's own state
   says `mismatch.flag = true`, `"Field dump is 62x212x22 but the S-parameter record is 72x212x22;
   they come from different runs … and are not the same solve."`, `validation_status =
   "UNVALIDATED"`, and the chart title spells it out: *"… (S-params run B; field run A)"*. The
   multi-frequency sweep is picked up from `evidence/termination/build_A_50ohm_multifreq_summary.json`
   (`5 rows kept, 0 skipped`).
   → **DEAD END #5 (the honest one): the picture and the S-parameters on screen are two runs.** The
   app tells you so instead of hiding it — that is a design decision, not a bug.
9. **Press Solve.** The 4 SETUP cards / 7 controls (`_emit_solve_controls:12197-12460`) do start a
   real solve. But the page context is built **once** (`poc_app.py:10324`) and is not rebuilt after
   `apply_page`, so `solve_disabled` is recomputed from new `nt` against *stale* `available` flags
   (`:12812`); `state.page_source_text` is written only at `:10309` and not in the `_rebuild_sheets`
   refresh (`:11375`), so the left-column header names the **previous** file after a live solve.
   → **DEAD END #6: the first thing a newcomer does after "it works" (solve again) is the least
   trustworthy path in the UI.**
10. **Try to take something away.** There is no export: `grep -n "Export\|export" server/um3k_panels.py`
    = 0, and `grep -n "download\|to_csv\|savefig" server/poc_app.py` finds only three
    `fig.savefig(buffer, …)` calls into memory. The only machine-readable output is the CLI
    diagnostic `--dump-state FILE.json` (`poc_app.py`, `STATE_SCHEMA_VIS="emfit.poc-state/3"`).
    → **DEAD END #7: no CSV, no PNG download, no S-param file out of the GUI.**
11. **Try the board.** Nothing in the GUI can open `CMEX.kicad_pcb` as a structure: it is not in
    `structures.json`, and per `Intro.txt` §11 it must not be meshed (1 mm ⇒ "eight solid plates").
    → **DEAD END #8: the file that gives the repo its most recognisable name is a parser test
    fixture, reachable only through `emfit/kicad.py`/`netlist.py`, never through the app.**

---

## 6. Glossary

| term | meaning *in this repository* |
|---|---|
| **FIT** | Finite Integral Technique — Maxwell's equations in integral form on a dual grid; the discrete curl operators `C`, `Ĉ` and material matrices are the whole method. Chosen over FEM because the operator's professor invented it (`Intro.txt`). |
| **FDTD** | the time-domain marching form used to advance the FIT state (leapfrog); `emfit/evolve.py`. |
| **arm A / B / C / D** | the four termination builds of the microstrip study: A = 50 Ω `series_r` (the *reference*), plus 100 Ω, stub, diode variants (`evidence/termination/run_build_A.py`; `artifacts/vis_dump_B_100ohm.npz`, `build_C_stub*`, `build_D_diode`). |
| **plane clock / volume clock** | the two different frame rates in one dump: planes are written every step (`nt=2400`), the |E| volume every `volume_stride` plane-frames (`24` at stride 100). The player maps between them; using one plane's frame number to index the other's `t_ns` "would read an instant up to ten times too early and never raise" (`load_vis` docstring). |
| **vis dump / `emfit.vis/2`** | the modern npz that animates: 16 mandatory keys (§4). |
| **legacy plane dump** | an npz with no `schema` and a `plane_ez` key; read by `load_dump:203`, served by the legacy `run_web:5922` page. **This is what the default boot opens.** |
| **Huygens surface dump** | `emfit.surface-dump/1` archive of surface currents/normals/`dA` that `emfit/ntff.py` can integrate to a far field; validated, then refused by the viewer (no renderer). None shipped. |
| **record** | the JSON study record beside a dump (`*_p51_ghostwave.json`, `*_phasors.json`, `*_multifreq_summary.json`); feeds the Confidence / S-Params / Circuit tabs. |
| **registry** | `structures.json` at repo root (`STRUCTURES_FILE`, `poc_app.py:139`): "an entry exists there only where an artefact exists on disk"; a case with no dump is *record only* and cannot be opened (`_structure_is_record_only:1422`). |
| **bare BOARD page** | the all-NaN page `_bare_board_page:3691` for an entry with no artefact: every unknown is `NaN`, never a constant, because draw sites test `isfinite()` — "a zero draws a board at the origin, a plausible default draws a WRONG board that looks right". |
| **station** | one x sample across the line where `V`, `I` and the Poynting flux are taken (`ports.StationFit:1290`); the shipped legacy dump carries 9 stations at 1.2 mm spacing. |
| **beta fit** | fitting the travelling-wave propagation constant from the station fields (`ports.fit_beta:861`, `BetaFit:772`); its own bias is 1.4618 rad/m = 0.3767 % = 2.278° over the 9.6 mm arm (`docs/design/pipeline_map.md`). |
| **DR-45 / DR-47 / DR-44** | the numbered discipline records: DR-45 no artefact may carry a date later than the newest commit (quote a commit hash); DR-47 the silent-failure class where a deleted call left `_start_watch → _watch_solve → _poll_solve → apply_page` unreachable with no exception and no failing test; DR-44 49,352 B of untracked docs were overwritten in place — read before writing, check `git status` for tracked-ness. |
| **claim labels** | four kinds that are never merged: VERIFIED-BY-RUN / FIXED-TESTED / closed / measured (`README.md` "Status and conventions"). |
| **CMEX** | the 8-layer KiCad board used as the KiCad parser fixture; **name not expanded anywhere in the tree**; not a simulation target (`Intro.txt` §11). |
