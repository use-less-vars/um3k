# Dispatch 59V — acceptance criteria for the visualisation layer

**Status: FROZEN.** This file is Phase A output. It was written before any Phase B
artefact exists: at freeze time `viz/` contained only this file. Phase B must not
edit it. If a criterion turns out to be wrong or unachievable, Phase B records the
deviation in `viz/deviations.md` (naming the criterion id, what was attempted, and
why) and leaves this file byte-identical.

Authority for every tier in this file is `docs/design/soundness.md` (§2 vocabulary,
§5.2 "Asserted, not citable", §7.2 "the fifteen withdrawn rows"). Nothing here
invents a tier.

---

## §0 Fence (normative)

1. **Writes** are permitted only inside `viz/` (including subdirectories).
   Forbidden: `emfit/`, `tools/`, `tests/`, `docs/`, `decisions.md`,
   `component_map.md`, `.scratch/`, `out/`, `tmp_job2/`. Close-out check:
   `git status --porcelain` lists nothing outside `viz/`.
2. **Reads** are unrestricted inside the repository (source text and solver
   artefacts). Nothing outside the repository is read or written.
3. **No new physics.** No quantity may be computed that the solver does not emit.
   Permitted: reshaping a stored array onto its documented grid axes
   (`e_z_node` (527,) -> (31,17) on `xs`, `zs`), indexing, type coercion,
   and *display-only* transforms (log colour scaling, symlog, clipping) which must
   be declared per-image in a sidecar `display_transforms` list and named in the
   panel's own caption. Forbidden without a declared display transform: filtering,
   smoothing, interpolating, differentiating, integrating, normalising, fitting,
   unwrapping, extrapolating.
4. **No derived numbers may be printed as if solver-emitted.** Any number shown on
   a panel is either a stored value (to its stored precision) or is listed in the
   sidecar `display_transforms` / `derived_labels` with its definition.
5. **No installs, no network.** Available: numpy 2.5.4, matplotlib 3.11.2,
   scipy 1.18.1, PIL 13.0.0, stdlib. Absent and not to be added: pyvista, plotly,
   vtk, pandas, h5py.
6. **The visualiser is allowed to break.** A panel whose artefact is missing or
   empty must render an explicit *refusal panel* that names the missing artefact
   and the symbol that would have to emit it. It must never be repaired by
   changing `emfit/`, `tools/` or `tests/`. A silent blank, a zero-filled array or
   a substituted constant is a FAIL, not a degradation.
7. **No new claims.** The visualiser adds no tier, promotes no tier, and never
   states or implies that a number is quotable. A row's tier is a ceiling.

---

## §1 What Phase B builds (scope of the artefact under test)

A static-image viewer over artefacts that already exist. Concretely:

* `viz/render.py` — one deterministic entry point, `python3 viz/render.py`,
  writing images into `viz/out/`.
* `viz/tiers.py` (or an equivalent data table) — the **single** source of tier
  assignments used by every panel: quantity -> tier -> `tier_source`
  (file + line, or a soundness.md section). No panel may hard-code a tier.
* `viz/out/*.png` (or `.svg`) plus one `<name>.json` sidecar per image.
* `viz/README.md` — how to run, what each panel is, and the tier legend including
  the one-sentence warning required by A12.
* Panels, minimum set:
  1. 2-D mixed-mode profile, `e_z_node` -> (31,17) on `xs`,`zs`
     (`.scratch/s10118_mixed_mode.npz`).
  2. Signed `e_z` plane (`.scratch/e_z_signed_41x22.npz`, `e_z_plane` (201,76)).
  3. Mesh / free-dof figure rebuilt from `emfit.mode2d.box_mesh` (no solve).
  4. Plane-stack slice view (`.scratch/host/m3a-smoke/plane_record.npz`,
     `plane_Ez` (9,201,76) as nine slices).
  5. A scalar strip for the stored mixed-mode scalars
     (`beta`, `eps_eff`, `residual`, `n_dof`, `n_pec`, `k0`, `freq`), each badged.
  6. A **refusal panel** for every row of §4 whose data does not exist on disk
     (S-parameters, 3-D volume, time-domain field history). The absence itself is
     rendered, not omitted.

---

## §2 Acceptance criteria (falsifiable; PASS/FAIL; checkable by reading files)

| id | criterion |
|----|-----------|
| A1 | All writes under `viz/`: `git status --porcelain` lists no path outside `viz/`. |
| A2 | >= 5 image files under `viz/out/`, each > 10 kB, each opening with `PIL.Image.open()` without error. |
| A3 | Every image's caption names its source file **and** the stored key(s) it displays, in the form `<key> <- <path>`. |
| A4 | Every image carries >= 1 tier badge, and the badge family letter is legible verbatim (`E1`,`E2`,`E3`,`E4`,`E5`,`X`,`UNKNOWN`) in the image or in its sidecar. |
| A5 | Per image, a sidecar `viz/out/<name>.json` exists with keys: `source_path`, `keys`, `shape`, `dtype`, `tier`, `tier_source`, `display_transforms`, `derived_labels`. |
| A6 | No printed number is solver-unemitted: every number on a panel appears either as a stored value or in `display_transforms` / `derived_labels` with a definition. |
| A7 | The E5 encoding survives a greyscale, 50 %-scale screenshot: text `E5 — NOT CITABLE` + a colour-independent texture + the value struck through. Checked on the S-parameter refusal panel **and** on the "S-parameters quotable (C4)" panel. |
| A8 | A refusal panel exists for each §4 row marked "NO" and states the missing artefact and the emitting symbol. |
| A9 | Determinism: `python3 viz/render.py` twice yields byte-identical files (no timestamps in names, PNG metadata disabled or pinned). |
| A10 | No core file touched: after a run, no file outside `viz/` has a changed mtime. |
| A13 | Harness note: `git` is **not present inside the analysis container** (`/bin/sh: git: not found`), so A1/A10 are checked either from the host or, inside the container, by `find . -newer viz/acceptance.md -not -path './viz/*' -not -path './.git/*'` returning empty. |
| A11 | Dependencies unchanged: imports restricted to numpy / matplotlib / PIL / stdlib. |
| A12 | `viz/README.md` contains, verbatim: "E5 values are not citable; X values are withdrawn; UNKNOWN means the ledger does not say enough to classify." |

---

## §3 Tier vocabulary (quoted from `docs/design/soundness.md` §2, lines 47–54) and the badge encoding

Verbatim, in the ledger's own words:

* **E1 Proven** — mathematical argument, no numerical dependence.
* **E2 Verified** — measured against an *independent* analytic reference,
  convergence rate demonstrated, at least 3 resolutions reported.
* **E3 Characterised** — measured against some reference but with incomplete
  convergence evidence; OR a heuristic or selection rule with measured behaviour
  and no derivation.
* **E4 Calibrated** — agrees with an external tool or external measurement, with no
  internal error analysis.
* **E5 Asserted** — believed, stated, or derived on paper but not measured.
  **Not citable.**
* **X Withdrawn** — the document itself retracts, supersedes, or contradicts the
  claim elsewhere.
* **UNKNOWN** — the document does not say enough to classify it.

Supporting facts Phase B inherits, not negotiable:
the vocabulary is renamed from `T1`..`T5` because `T1`..`T7` are live gate clause
ids (`T1_stab`, `T2_agree`, `T3_scale`, `T4_amp`, `T5_ez_corr`, `T5_ey_corr`,
`T5_fringe_excess`, `T6_fit_route`). Ledger histogram: **37 E1, 0 E2, 58 E3,
3 E4, 28 E5, 15 X, 2 UNKNOWN = 143 rows**. A row's tier is a **ceiling**;
promotion requires a named measurement or argument, never emphasis.
45 of 143 rows (28 E5 + 15 X + 2 UNKNOWN, 31.5 %) are never quotable.
`E2 = 0`: there is no row in the ledger that is citable *by measurement*.
The ledger's own disclaimers hold: "This document does not claim the code is fit
for any safety-critical purpose"; "A ledger entry is never a substitute for
running the thing."

### 3.1 Badge encoding (three redundant channels; colour is optional, never primary)

Every displayed quantity carries all three of:

**Channel 1 — glyph + word (readable text).**
`E1 PROVEN` · `E2 VERIFIED` · `E3 CHARACTERISED` · `E4 CALIBRATED` ·
`E5 NOT CITABLE` · `X WITHDRAWN` · `UNKNOWN`.

**Channel 2 — texture / line-style (survives greyscale, blur, and thumbnail).**

| tier | frame | field texture | value rendering |
|------|-------|---------------|-----------------|
| E1 | single solid 1.5 pt rule | none (white) | normal |
| E2 | single solid 1.5 pt rule | none (white) | normal |
| E3 | single thin 0.75 pt rule | none | normal, 0.9x size |
| E4 | single thin 0.75 pt rule | none | normal, 0.9x size |
| E5 | **double rule** (2 pt, 2 pt gap) | **45° diagonal hatch, 0.5 pt** | **struck through** with a 1.5 pt overstrike, 0.75x size |
| X | cross-hatch border | **cross-hatch (45°+135°)** | value replaced by an **opaque redaction block**; the number remains faintly legible under it |
| UNKNOWN | dotted rule | 50 % grey "?" tiling | value replaced by a boxed `?` |

**Channel 3 — a fixed sentence.** Every panel that carries any badge prints,
verbatim: *"A tier is a ceiling: it can be lowered by new evidence, not raised by
emphasis. E5 is assertion, not measurement; it must not be quoted."*
Any panel containing an E5 or X quantity additionally prints, verbatim:
*"This panel contains values that are not citable."*

**Colour (4th, redundant only):** E5 red, X magenta, UNKNOWN grey, E1–E4 blue.
Removing all colour must leave the classification recoverable — that is A7.

**Test of the design:** convert a rendered panel to `L` mode, downscale to 50 %,
and view at a glance. An E5 field must be distinguishable from an E1 field with no
knowledge of the vocabulary, because it is the only thing on the panel that is
hatched *and* doubled-framed *and* struck through.

---

## §4 Survey of what exists on disk today (Phase A, measured)

"Tier" names the ledger row the tier must be copied from. Where no row is named,
Phase B must copy the row verbatim into `tier_source`; **if the ledger has no row
for the quantity, the tier is `UNKNOWN`** — never a guess, never a promotion.

| # | quantity | emitting symbol / path | on disk today? | format | tier source |
|---|----------|------------------------|----------------|--------|-------------|
| 1 | 2-D mixed-mode profile `e_z_node` (527,) -> (31,17) on `xs`(31),`zs`(17) | `.scratch/s10118_mixed_mode.npz` <- `emfit.mode2d.solve_modes_mixed` | **YES** | npz float64 | ledger C3 (`1927 x 1927` nonsingularity); the profile itself -> UNKNOWN unless C3 covers it |
| 2 | same profile, finer mesh | `.scratch/s10118_mode_41x22.npz` (same key set) | **YES** | npz | as row 1 |
| 3 | signed `e_z` plane (201,76) + `n_neg`/`n_pos`/`n_zero` | `.scratch/e_z_signed_41x22.npz` | **YES** | npz float64 | no ledger row identified -> **UNKNOWN**; gate clause `T5_ez_corr` is the live relevant clause, not a tier |
| 4 | mode scalars `beta`, `beta_sq`, `eps_eff`, `E_strip_t`, `residual`, `n_dof`, `n_pec`, `k0`, `K0`, `freq`, `sigma`, `col` | same npz as row 1 | **YES** | npz scalars | C3 for the residual/nonsingularity statement |
| 5 | `curl_ratio_raw` (1444,), `candidates` (1,4), `e_t` (1486,), `free_e` (1444,), `free_n` (483,), `z_free` (483,) | same npz as row 1 | **YES** | npz | C19 (`T4_amp`, recorded **FAIL 44.09 %**) -> E3 per the ledger; the FAIL must be shown on the panel |
| 6 | nine station planes `plane_Ey` (9,200,77), `plane_Ez` (9,201,76), `plane_Hy` (9,201,76), `plane_Hz` (9,200,77), `plane_station_x` (9,), `plane_f`, `plane_dt`, `plane_n_samples`, `plane_convention` (str), `plane_capture` (str) | `.scratch/host/m3a-smoke/plane_record.npz` <- `emfit.evolve` capture path | **YES** (8.8 MB) | npz complex128 | no ledger row identified -> **UNKNOWN** |
| 7 | 18 further plane records of the same schema, e.g. `A1_planes.npz` (600 kB) | `.scratch/logs/*_planes.npz` | **YES** (schema same; `plane_*` keys not individually verified for all 18) | npz | **UNKNOWN** |
| 8 | **S-parameters carried by those plane records**: `f`, `v`, `i`, `z0`, `beta`, `s11_measured`, `s11_port`, `s21`, `s21_power`, `passivity`, `passivity_power`, `refused` | keys exist in the same npz | **NO — present but empty**: `f` (0,), `v` (0,9), `i` (0,9), `s11_*`/`s21*`/`passivity*` (0,) | npz, zero-length | **E5** — ledger C4 "the S-parameters are quotable", scope "none: nothing about quotability is measured", evidence D09, F14, G04, G06, each a recorded FAIL |
| 9 | S-parameter *code paths* (no data) | `emfit.ports.travelling_waves`, `.reflection`, `.transmission`, fit path; `emfit.studies.line_s21(a1,x1,a2,x2,beta) -> (s21, raw)`; result fields `s11_measured`, `s11_port`, `s21`, `s21_raw`, `s21_planes`, `passivity` | code **YES**, output **NO** (needs a solve) | python | **E5** (C4), plus recorded FAILs `T2_agree` 9.03x tol, `T4_amp` 44.09 % |
| 10 | 3-D field volume (E/H on all edges/faces) | `emfit.evolve.FITStepper.e` / `.h`, reachable only in-process via `run(callback=...)`; `run(nsteps, probe, source, callback)` returns 1-D probe samples or `None` | **NO** — never written as a volume | none | **UNKNOWN** |
| 11 | 1-D time-domain trace `ts`, `a1`, `a2` (2161,) | `tmp_job2/traces.npz` | **YES** | npz float64 | **UNKNOWN** — provenance unclear (scratch dir, no run log alongside) |
| 12 | convergence spectrum + table per mesh row | `out/mesh_study/{yair06,yair12,yair15,yair18,yair22,z12_6_8}/{c1_spectrum.npz,c1_table.txt}`; `tools/host/sparse-probe/out/rung4_s36_a22_z20-10-10/{c1_spectrum.npz (739 MB),c1_table.txt,env.json,run.log}` | **YES** | npz / txt | **UNKNOWN** unless a ledger row names the study |
| 13 | mesh / geometry | `emfit.mode2d.box_mesh(lx,ly,nx,ny)`, `structured_mesh`, `mesh_from_grid`, `Mesh2D(nodes,tris,grid_axes)`, `pec_edge_mask`, `pec_node_mask`; `emfit.board.MicrostripBoard`, `cropped_to_strip`, `to_cell_counts`; `emfit.kicad`, `emfit.raster`, `emfit.gerber` | **NO stored mesh** (the mixed npz stores only `xs`/`zs` axes and `free_e`/`free_n` indices) — rebuildable in-process, no solve | python | **UNKNOWN** |

Measured, not assumed: free-edge counts from mesh + PEC masks only (no solve) —
box 16x10 = 506, 20x12 = 752, 22x13 = 893, 24x14 = 1046, 26x15 = 1211,
28x16 = 1388, 32x18 = 1778 free edges. `emfit.mode2d._MIXED_DENSE_MAX = 3000` is
the only binding limit; there is no lower bound blocking a small mesh, and
`dense=False` raises `NotImplementedError` ("iterative path pending").

---

## §5 Out of scope for 59V

* Any new solve, any new sweep, any fit. Phase B renders only what §4 marks YES.
* Interactive rendering, web pages, notebooks, animations. Static images only.
* A 3-D engine: none is installed and none may be added; a plane *stack* is the
  maximum representation available.
* Creating, improving or re-tiering any ledger row; editing `docs/`.
* Error bars, envelopes or uncertainty estimates that the solver does not emit.
* Any statement that a number is quotable, validated, or fit for a purpose.
* Repairing the core. If the viewer breaks, it reports the break.

---

## §6 What could not be established without running a solve

1. Whether `solve_modes_mixed` produces a sane profile on any mesh besides the
   cached s10118 pair — no other output exists on disk.
2. Whether the mixed-mode residual converges with refinement. Cached data shows one
   residual per mesh; a rate needs >= 3 resolutions, so **E2 is not reachable from
   what is on disk** (consistent with the ledger's `E2 = 0`).
3. **Any S-parameter value at all.** The only plane record carries empty
   S-parameter arrays; `line_s21` needs a solve. The panels for S-parameters are
   therefore refusal panels by construction, badged E5.
4. Whether the nine plane slices are self-consistent, and what frequency they are
   at: `plane_f`, `plane_dt` are stored scalars, but the sweep arrays (`f`, `v`,
   `i`, `z0`, `beta`) are empty — so the slices cannot be cross-labelled against a
   frequency axis; the panel must show `plane_f` as stored and refuse the rest.
5. The 3-D field shape at any instant: no volume artefact exists, and `run()`
   returns probe samples only. Only a stack of 2-D planes is available.
6. The time-domain field history (probe-only by design).
7. The provenance and physical meaning of `tmp_job2/traces.npz`.
8. The cost of the dense QZ near the 3000-free-edge cap (counts were measured;
   run time was not).
9. Whether the 18 `.scratch/logs/*_planes.npz` records actually contain populated
   `plane_*` arrays — only the schema and the empty scalar arrays were verified.
