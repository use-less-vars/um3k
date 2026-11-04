# Independent anchor cross-check: QUCS / Kirschning-Jansen-Koster gap model (dispatch 8a)

**Status: BLOCKED at stages B-E.** Stage A is complete; the technical engineer's section-2 formulas
are **not in the tree**, and this dispatch is forbidden to reconstruct them from memory or to
substitute another gap model. No |S11| or |S21| is predicted here, and all four brackets are
**NOT GRADEABLE**. Read section 2 before quoting any number from this file.

Date 2026-11-05. Dispatch `independent-anchor-qucs-2026-11-04`. Read-only: this doc plus one row in
`docs/design/dispatch_log.md`. No code change, no host run, no artefact edit, no commit.

## 1. What was asked

Evaluate the TE's independent anchor - a QUCS model of the termination as a resistive through-element
shunted by a gap capacitance `CS`, flanked by two gap pi-sections carrying `CP1`, `CP2` - against the
modelled geometry of `evidence/termination/build_A_50ohm_p51_phasors.json`, convert ABCD to S with a
**real** modal `Zref`, and grade four pre-registered brackets. The whole of it rests on the TE's
section 2, which types out `CS = 500*h*exp(-1.86*s/h)*Q1*[...]` and quotes `Q1..Q5`, `Qo1..Qo5`
only by name. **The transcription in the dispatch is incomplete**: the boxed `CS` factor after `Q1`
is elided and none of `Q1..Q5`, `Qo1..Qo5` is written out. Those quantities are the Kirschning-Jansen-
Koster gap-model coefficients; they cannot be recovered by arithmetic and were not guessed.

## 2. Search for the TE's section-2 text - NOT FOUND

Patterns searched (case-insensitive): `QUCS`, `Kirschning`, `Koster`, `Jansen`, `CP1`, `CP2`,
`exp(-1.86`, `Qo1`, `500*h`, and the compound `Kirschning.?Jansen.?Koster`.

Corpus searched: the whole workspace for `*.md`, `*.txt`, `*.py`, `*.json`, with `.venv` and `.scratch`
excluded (`-I`, the two big data dirs excluded because a full `grep -r` times out on 2.4 GB of `.npz`);
plus a targeted pass over `docs/` and every top-level `*.md`. There is no `notes/` directory in the
tree (top level is `docs emfit evidence examples kicad_support_project out reports schemas
study-out temp tests tmp_job2 tools viz`), so the "any `notes/`" arm of the search is empty by
construction.

**Result: zero hits for `QUCS`, for `Koster`, for `CP1`/`CP2`, for `Qo1`, for `exp(-1.86` and for
`500*h`.** The only `Kirschning`/`Jansen` hits in the tree are the **dispersion** closures
(`tools/d585_modal.py` `kirschning_jansen_peff`, `docs/design/box_sweep_preregistration.md`,
`decisions.md:9247`, `:9319`): an effective-permittivity correction, not the gap model, sharing only
an author's name. `emfit/ports.py` and `emfit/studies.py` use the word "gap" solely for the port feed
gap (the `Probe`/`edge_path_voltage` column from ground to strip), which is a measurement path and not
a capacitance model.

**Consequence, per the dispatch: stop after Stage A.** Stages B-E below are marked `BLOCKED`. A gap
model written out from memory would be indistinguishable from a fabricated anchor, which is the exact
failure this cross-check exists to avoid.

## 3. Stage A - the termination actually modelled in `build_A`

### 3.1 One gap or two? **ONE.**

Deciding keys, quoted with values:

- `/geometry/loads[0]` = `{"column": 50, "kind": "series_r", "n_edges": 9, "value": 50.0, "x": 0.02}` -
  **one** load record, one column, one resistor, at `x = 20.0 mm`. Its span is one node column of `n_edges = 9` **longitudinal (`E_x`)** edges running across the strip
  width. *Corrected 2026-11-05: this line originally read "9 vertical edges", which the construction
  probe in the addendum refutes; the wording is shown rather than silently replaced.*
- `/ac/AC-6/achieved` = `{"load_column": 50, "load_kind": "series_r", "load_plane_index": 50,
  "load_position_mm": 20.0, "load_value": 50.0, "load_units": "ohm", "plane_offset_from_load": 1,
  "s21_plane_index": 51, "last_clean_plane": 65}`.
- `/geometry/` carries **57 keys and none of them is a `gap`**: there is no gap length, gap width or
  pad extent anywhere in the record. The smallest length the model can express is `cell = 0.0004` m.

Verdict: a **single** series resistor across a **single** gap, one cell wide. The TE's assumed 0.4 mm
gap is therefore consistent with the model at the resolution available (`0.4 mm = 1 cell`), but the
artefact does not *state* 0.4 mm - it states a column and a kind, and the length is inferred from the
mesh. There is no second gap and no resistive **pad**, so the TE's section-1 cascade of two pi-sections
is **not** required; one pi-section (B) plus the R||CS bridge (C) would have been the right topology.
That is a Stage-B/C design note only - it does not unblock them.

### 3.2 Geometry, artefact versus TE assumption

| quantity | artefact key and value | TE assumption | agree? |
|---|---|---|---|
| strip width W | `/geometry/w` = 0.0032 m (`n_strip` 8 x `cell` 0.4 mm) | 3.2 mm | **yes, exact** |
| substrate height h | `/geometry/h` = 0.0016 m (`n_sub` 4) | 1.6 mm | **yes, exact** |
| relative permittivity | `/geometry/eps_r` = 4.4 | 4.4 | **yes, exact** |
| gap length s | not a key; one column = `cell` = 0.0004 m | 0.4 mm | consistent, inferred |
| frequency | `/geometry/f_hz` = 5827786408.327286 (5.827786408 GHz) | same tone | yes |
| cell / mesh | `cell` 0.0004 m; `grid` [72, 212, 22]; `cells` 335808 | - | - |
| extraction plane | `s21_plane_index` 51, load `column` 50, offset 1 cell | - | - |
| steps | `nsteps` 2400, `n_warm` 600, `n_pml` 6 | - | - |
| measured S | `/s11/magnitude` = 0.32556486641109117, `/s21/magnitude` = 0.7644184907560716 | - | - |

The three geometry assumptions the TE's numbers rest on (`h`, `W`, `eps_r`) reproduce **exactly**, so
had section 2 been available the two-column table would have had identical columns on those rows. The
only real discrepancy in Stage A is that the gap is implicit in the mesh rather than a stated parameter.

### 3.3 Reference impedance for Stage D - the required one is ABSENT

Stage D demands a **real** modal `Z0` from `mode_profile`, and explicitly not the complex station-fit
`Z0`. This artefact has **no `mode_profile` block at all**. The four `Z0` candidates on the record are:

| source | value | status for Stage D |
|---|---|---|
| `line.z0` | 42.43786214405251 - j15.727993189312496 | port V/I, complex - not it |
| `run.station_fit.z0` | 47.364066848187235 + j1.6449807931078728 | **explicitly excluded by the TE** |
| `summary_line` `z0_model` | 48.098655 (real) | quasi-static Hammerstad-Jensen closed form, not a modal solve |
| TE's `Z0 = 47.54` | appears in no artefact | an assumption, not a measurement |

So even with section 2 in hand, Stage D would have to be run at a labelled substitute (`48.098655` real,
the only real number on the record) and flagged as such. Recorded here so the next dispatch does not
have to rediscover it.

## 4. Stages B-E: BLOCKED

- **Stage B - `CS`, `CP1`, `CP2`: BLOCKED.** `CS = 500*h*exp(-1.86*s/h)*Q1*[...]` cannot be evaluated:
  the bracketed factor and `Q1..Q5` are not written out in the dispatch and appear nowhere in the tree.
  `CP1 = C1*(Q2+Q3)/(Q2+1)` and `CP2 = C2*(Q2+Q4)/(Q2+1)` are unevaluable for the same reason, and
  `C1`, `C2` via the open-end `dl` (`C_end = sqrt(eps_eff)/(c0*ZL)*dl`) would be a free choice of `dl`
  with no TE-defined value to anchor it.
- **Stage C - ABCD: BLOCKED.** `Y_B = 1/R + j*w*CS` and `Y_P = j*w*CP1 = j*w*CP2` need `CS`, `CP1`, `CP2`.
  The element matrices were **not** assembled; nothing was substituted for them.
- **Stage D - ABCD to S at real `Zref`: BLOCKED.** No network to convert, and (section 3.3) no real
  modal `Z0` on the record either.
- **Stage E - prediction against the anchor table: BLOCKED.** No prediction exists; the four anchor
  rows (series-R 0.34465/0.65535, complex-load 0.307/0.724, measured 0.32556/0.76442, TE preliminary
  0.349/0.658) are carried here only as the table the prediction would have been graded against.

## 5. Brackets - all four NOT GRADEABLE

- **Q1 (reproduction of the TE preliminary numbers):** NOT GRADEABLE (stages B-E blocked). No |S11|,
  no |S21|, so `|S11|` in [0.335, 0.355] and `|S21|` in [0.648, 0.668] cannot be tested.
- **Q2 (own computation more than 5 % from the TE preliminary):** NOT GRADEABLE (stages B-E blocked).
- **Q3 (model failure: negative capacitance, out-of-range formula, non-physical result):** NOT GRADEABLE
  (stages B-E blocked). No capacitance was computed, so none can be non-physical. This must not be read
  as "the model did not fail" - it was never run.
- **Q4 (falsifier: |S11| above 0.34465 or |S21| below 0.65535 by more than 3 %):** NOT GRADEABLE
  (stages B-E blocked). Nothing was tested, so the falsifier did not fire and did not fail to fire.

## 6. What would unblock this

The TE's section 2 in full, pasted into the tree or into a dispatch: the boxed `CS` expression with its
bracket, the five `Q` coefficients and the five `Qo` coefficients, plus the `dl` definition for the
open-end capacitance. With those, Stages B-E are arithmetic over keys already quoted in section 3.2 and
need no new run. A second, independent route would be to ask for the QUCS netlist itself; a netlist
naming the components would pin `CS`/`CP1`/`CP2` without any transcription at all.

## 7. Files touched

- `docs/design/independent_anchor_qucs_2026-11-04.md` (this file, new).
- `docs/design/dispatch_log.md` (one row, inserted after line 28, before `## Deferred`).

No other write. No artefact, source file, test or register touched; nothing re-graded; nothing re-run.

## Addendum, 2026-11-05 — two probes, run to test whether this dispatch's premise survives

Two probes were run after the text above was written, to test the suspicion that this block rests on a mis-read load rather than on the missing section 2. Both are read-only (no host run, no artefact edit). Neither supplies a prediction, so **nothing above is re-graded or renumbered**.

**A.1 The load-topology suspicion is refuted.** `series_r` stamps `cc.idx_ex(np.array([ix_load]), j_points, k_strip).ravel()`, clears `pec[edges] = False` and adds `sigma[edges] += 1/(edges.size*R)` (`emfit/studies.py`:2883-2886). Re-run at the artefact's own grid (72, 212, 22; `cell` 4e-4 m; `n_strip` 8; `n_sub` 4; R 50; x = 0.02 m) this is **9 edges**, indices 247300, 247323, ... 247484, `i` = 50, `j` = 102-110, `k` = 4, midpoints x = 20.2 mm, y = 41.0 ... 44.2 mm, z = 1.8 mm, each branch 0.400 mm long: one parallel bank across the full 3.2 mm strip on one column, and **R_eff = 50.000 ohm exactly**, the identity `tests/test_studies.py`:1490 asserts. It is not a point, not smeared over a gap, and not on the wrong edge family - the family follows `load.kind` alone, x (longitudinal) and not z, so section 3.1's "vertical edges" was corrected in place above, disclosed where it stood.

**A.2 Three facts that change how the comparison must be made.** (i) The break occupies `x` in [20.0, 20.4] mm, so the element's terminals are the node planes at 20.0 and 20.4 mm and it sits half a cell downstream of the nominal 20.000 mm; `s21_plane = "cut"` measures on the **upstream** face (`emfit/studies.py`:2918, `cut_index = column`), so a model that places `R` at exactly 20.000 mm with its reference plane after the element is off by that half cell. (ii) The load is a per-edge **siemens** value, not a conductivity (`emfit/evolve.py`:8-10, `:42`), so `R` stays 50.000 ohm under mesh refinement while the break length and its fringing capacitance both change. (iii) The two halves' end faces are **equipotential plates** at x = 20.0 and 20.4 mm - and that is exactly what makes the break **capacitive**: `emfit/board.py`:86-91 warns the cut's own capacitance is "a few hundred ohms of reactance at a few gigahertz, which is not small". `CS` is therefore a real term in this structure, not a modelling artefact; what the pinned `E_y` edges (`emfit/studies.py`:2859-2861) exclude is the halves shorting to each other along the rails, not the gap capacitance. This is DR-32's surviving conclusion - 50 ohm in parallel with a few tenths of a picofarad, not a pure series R - now sourced from the code rather than from the refuted design note.

**A.3 There is no gap-length parameter.** `/geometry/` carries 57 keys and not one is a `gap`; the smallest expressible length is `cell` = 0.4 mm. A gap sweep would be a geometry rebuild, not a keyword.

**A.4 Electrostatic capability: no 3-D solver installed, but a tested 2-D one is already in the tree.** Of 25 named candidates (scikit-fem, sfepy, gmsh, pygmsh, meshio, dolfin, dolfinx, firedrake, bempp, devito, meep, openems, palace, pyamg, pypardiso, scikit-umfpack, pyvista, scikit-rf, qucs, ngspice, spicelib, ahkab, lcapy, numba, numexpr) **every one is absent**; the environment is numpy 2.5.4 / scipy 1.18.1 / sympy 1.14.0, with `spsolve` and `splu` importable, and PyPI egress does work (`pip download --no-deps sympy` exited 0 and installed nothing). The tree already contains a finished, tested **2-D** Laplace capacitance solver: `emfit/quasistatic.py`, `capacitance_per_length` at `:276`, `K = G @ diags(m) @ G.T` at `:265`, `spsolve` at `:270`, with ten tests in `tests/test_quasistatic.py` passing. It is strictly two-dimensional - exactly one periodic axis, one cell thick - so it returns C per metre for a cross-section and cannot produce the cut capacitance itself. **`CS` is therefore unmeasured.** Two routes, neither taken here: a 3-D Laplace solve on the existing structured grid (a few hundred lines; `spsolve` or `cg` is sufficient at 72x212x22), validated against `emfit/quasistatic.py` on an **unbroken** section where a 2-D answer already exists; or installing a mesh-based FEM package, which buys little, because a structured grid, a per-edge index map and a PEC mask all already exist. The one primitive genuinely missing is a per-conductor **node** labelling for the Dirichlet set, which for a single two-plate capacitance is the two node planes named in A.2(i) and is therefore trivial here.

**A.5 Brackets unchanged.** Q1-Q4 remain **NOT GRADEABLE**, on section 4's reasons: no |S11|, no |S21|, no capacitance, nothing tested.
