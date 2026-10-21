# RESUME -- session state

Branch: `wip/ports`, on top of *"ports: a port plane can be placed on a pad"*, which sits on the pad-placement commit, which sits on master's decisions commit (`ffbb4a4`). No HEAD hash is written on this line on purpose: hashes here have gone stale twice. Describe the position by its subject and confirm it with `git log -1 --oneline`.
Base: master @ `ffbb4a4`. master already carries the ten delivered commits (tip `62d1684`) plus `ffbb4a4`, the decisions entry; `wip/ports` adds the port work on top, so master fast-forwards.
Working tree right now: the arc refusal and the `port` key in `board --json` are **uncommitted** -- `emfit/kicad.py`, `emfit/cli.py`, `tests/test_kicad.py`, `tests/test_cli.py`, `tests/test_board.py`. `Intro.txt` is also modified and is NOT ours -- never stage, edit or revert it. `docs/report/*.tex` and `docs/report/main.pdf` are committed and clean.

## To land the work

```
git checkout master
git merge --ff-only wip/ports
```

`wip/seam2` (`62d1684`) is already an ancestor of master, so do not merge it again. There is no `merge` and no `branch -f` in the agent's tool surface, so these two lines are yours to run.

## What the ten commits on master establish

Code (4 commits):

- `8440ae9` cli: a GIF is no longer filed as a figure, PNG only. Rationale: a GIF is not a
  citable figure, and the animation claim is split into "test" and "observation" in `ad336bd`.
- `d75b467` cli: `python -m emfit board PATH [--net NAME] [--eps-r EPS] [--json]`.
- `8e14dd5` gerber: `emfit/gerber.py` (364 lines) plus `tests/test_gerber.py` (8 tests), the
  plotted artwork checked against the board segment for segment.
- `962bffb` log: `decisions.md` gains 3 entries, 570 lines, 44 sections.

Report (5 commits):

- `ad336bd` module table 18 -> 25 rows, 6357 -> 14198 lines; the animation claim is split.
- `620706b` 14198 -> 14898 lines, tests 336 -> 348, `main.pdf` rebuilt.
- `1f8d4cc` new subsection "The same line imported from a layout" (`sec:msres-import`),
  `sec_microstrip_res.tex` 354 -> 435 lines, 8 paragraphs plus table `tab:ms-import`,
  16 quoted percentages recomputed and agreeing within 5e-5.
- `7865ad6` `sec_outlook.tex` 139 -> 146, M4 "planned" -> "in progress", first target
  "Not scored", +7.8 % eps_eff bias against a 4.3 % spread, sentence ending
  "...its patch half has not been started."
- `3b25817` `sec_intro.tex` 158 -> 165, "Layout import, in part." item: the port is a
  geometric plane, not a driven one, so no impedance is measured through it.

The ninth commit adds this file; the tenth is `ffbb4a4` on `decisions.md`. Every report commit
also commits the rebuilt `docs/report/main.pdf` (it is tracked).

## Decisions added at `ffbb4a4`

`decisions.md` is at the repo root (not under `docs/`); it is now 588 lines and 46 `##`
sections. Two entries were added:

- "KiCad is the model; Gerber is the ground truth." A layout is read as a model and the plotted
  artwork is what the model is checked against -- every importer oracle is artwork, not a
  re-read of the board file. The strongest argument against is recorded in the entry (the
  artwork is a superset of the model, so a wrong model can still agree) and it loses because a
  model error that survives an artwork oracle is a modelling choice, not an import error.
- "The eps_eff bias is systematic; its decomposition is the open question, and it is
  deliberately not being chased." +7.79 % on the reference box against +7.80 % on the coupon;
  three candidates are named and none is selected; the estimator spread is 4.3 %, so the bias
  is not an estimator artefact; +7.20 % is a trap (coupon measured against the reference
  closed form) and must not be quoted as the bias. The 62x44x22 box at 0.400 mm reads
  3.621781 = +8.31 % and is not the published record.

## What `wip/ports` adds: step 1 of 4 (`531c56c`)

- `emfit/kicad.py` 843 -> 944 lines, `tests/test_kicad.py` 640 -> 954 lines, 68 -> 75 tests.
  `Board.pads_in_board_frame()` returns `PlacedPad` records -- board-frame centre, size,
  rotation, net, copper layers, drill -- built from the footprint placement and the pad's
  footprint-local geometry. `LayerError` is raised for a pad on a layer the board does not
  have; `_footprint_side` and `_pad_copper_layers` are the helpers.
- `Board.pads` is unchanged and still footprint-local, so nothing that reads it moved.
  `emfit/gerber.py` and `tests/test_gerber.py` were not touched.
- The transform is x' = px + x*cos(t) + y*sin(t), y' = py + y*cos(t) - x*sin(t).
- The sign of the rotation is proved, not assumed. J1 sits at (4.5, 10, 90); its silkscreen
  chevron is footprint-local (-4.1, 0.5) -> (-3.6, 0) -> (-4.1, -0.5) and appears in
  `F_Silkscreen.gto` at (5.0, 14.1) -> (4.5, 13.6) -> (4.0, 14.1), i.e. with y negated. The
  opposite sign puts the chevron near y = 5.9, where there is nothing. The chevron is the only
  handedness oracle in the repository: every pad in the fixture is 90-degree-symmetric, so no
  pad can distinguish the two signs.
- Two oracles, exact rather than fitted, `PLACEMENT_TOL = 1e-6` mm (4.6 format resolution):
  12 placed F.Cu pads coincide one-for-one with the 12 `D03` flashes in `gerbers/*.gtl` (both
  directions consumed, so neither a missing pad nor an extra flash can pass), and the 10
  through-hole pads coincide one-for-one with the 10 plated holes in the Excellon drill file
  (T1C1.500 x2 at (4.5, -10) and (65.5, -10); T2C1.700 x8 at +/-2.54 / +/-3.04 around x = 4.5
  and x = 65.5).
- Fixture facts the port work needs: `kicad_support_project/kicad_support_project.kicad_pcb`
  is 70x20 mm, 2 copper layers, 58 track segments, 12 pads -- J1 5 pads at (4.5, 10, 90),
  R1 two SMD lands 0.54x0.64 roundrect with no drill, J2 5 pads at (65.5, 10, 270). Pad "1" of
  each SMA is 2.3x2.3 roundrect, drill 1.5, net RF_IN / RF_OUT; the four legs are 2.5 circles,
  drill 1.7, net GND. The gerbers and the Excellon file live in
  `kicad_support_project/gerbers/`, not beside the board file; F_Cu is `.gtl`, B_Cu is `.gbl`.

## What `wip/ports` adds: the port on a pad (`558a67a`)

- `emfit/board.py` gains `Port` -- `position` (where the plane crosses the line, from the
  outline's `xmin`), `y` (recorded, not used: the strip is modelled centred whatever the copper
  does), `net`, `reference`, `number`, `side`, each validated in `__post_init__` -- and
  `MicrostripBoard.port`; `from_kicad(..., port_pad=("J1", "1"))` places the port on that pad.
  `emfit/kicad.py` gains `Board.pad_at(reference, number)`, which refuses a reference or pad
  number that names more than one pad instead of resolving one by position.
- With the port on J1.1 the coupon's spec becomes the 2.0 mm run: `w 2.0` mm, `x_port 4.5` mm,
  `x_far 7.0` mm, `length 70` mm, `width 20` mm (`tests/test_board.py:227`). No command passes
  `port_pad` yet -- see the last bullet here.
- The port numbers now have a second importer behind them. The plotted `F_Cu` layer
  (`kicad_support_project/gerbers/kicad_support_project-F_Cu.gtl`) carries
  `Segment(x0=4.5, y0=-10.0, x1=7.0, y1=-10.0, width=2.0)` -- the 2.0 mm stroke from
  x = 4.500 mm to x = 7.000 mm on the through line -- and the same layer flashes the roundrect
  at (4.5, -10.0) mm, with y negated against the board frame, which is the coupon's J1.1 at
  (4.5, 10). Agreement is to `1e-6` mm after that sign flip, and it is a fact about the strip
  the port launches onto, not a fitted number.
- `spec.port` is now a key of the `board --json` object (`emfit/cli.py:360`): `null` when no pad
  names a port, otherwise `position_mm`, `y_mm`, `net`, `reference`, `number`, `side`. There is
  deliberately no CLI option that sets `port_pad`, so **no command can produce a port-bearing
  spec** -- `_cmd_board` calls `from_kicad` without it. That is the next gap;
  `tests/test_cli.py:168` pins the `null` so the key cannot quietly disappear.

## Importer step 3 is closed as a refusal: there are no arcs to support

- Counted before writing anything. Both board files have zero arc constructs: the coupon has 0
  `(arc`, 0 `(gr_arc`, 0 `(fp_arc` and not one occurrence of the substring `arc`;
  `CMEX.kicad_pcb` has the same three zeros, its single `arc` substring sitting inside a
  property value (a distributor URL). Form census, coupon: 4 `gr_line` (all Edge.Cuts), 66
  `fp_line`, 58 `segment`, 12 `pad`, 3 `footprint`, 2 `zone`, 0 `via`. CMEX: 891 `fp_line`,
  583 `segment`, 81 `via`, 388 `pad`, 81 `footprint`, 12 `gr_rect`, 4 `zone`. The second
  importer agrees from the artwork side: `GerberLayer.arcs` reads `arcs 0` on all seven files
  in `gerbers/`.
- An arc parser would have been dead weight, but skipping the check was not the same as leaving
  it harmless: `Board.tracks` is built from `(segment ...)` forms alone
  (`emfit/kicad.py:986`), so a board-level copper arc used to vanish without a word and the
  strip would have been measured off whatever straight segments remained. It is now refused
  (`emfit/kicad.py:992`) by count, layer and net, with the note that the caller has to cut a
  curved line into straight runs because the model downstream is one straight run. Pinned by
  `tests/test_kicad.py:648`, which carries its own positive control (the same file minus the
  arc loads and yields exactly one track).
- `Zone`'s docstring was wrong about the same shape and now matches `_parse_zone`: an arc inside
  a zone polygon contributes no vertex at all -- only `xy` children are read
  (`emfit/kicad.py:897`) -- not "its two endpoints only", and nothing is lost by that because a
  zone is recorded, not modelled.

## Outstanding: step 4 of the port work, and the crop it needs

- Step 4, S-parameters and a field slice on the imported coupon board. Acceptance: the imported
  coupon reproduces the hand-built study within the fit residual, and a port on an SMA pad runs
  end to end.
- It is blocked by the solver legitimately refusing the coupon, not by a bug, and with the port
  on J1.1 the refusal is sharper: the pad-derived spec has `x_far` = 7.0 mm inside a 70 mm
  outline, so `to_cell_counts` refuses it on its first check
  (`abs(x_far - length) > TOL * length`). The dominant-width `RF_IN` spec (x_far = 32.22 mm) is
  refused the same way, and `tests/test_board.py:184` asserts that refusal.
- Making a run possible therefore means cropping the outline to the strip. That crop is a
  deliberate, recorded choice to make and to report, not a repair: it changes the box, and the
  line modelled is the 2.0 mm run the port sits on, not the 29.8 mm feed. `supplied` is where a
  caller-supplied length has to be declared if the crop is not to be silent.

## Still true after step 1

- The back pour is measurable but not modelled: `gerbers/*.gbl` holds 3 `G36` regions
  (613/59/60 vertices), 10 flashes and 0 segments, bounding box (0.5005, -19.4995, 69.4995,
  -0.5005) against the Edge.Cuts box (0, 0, 70, 20) -- a uniform 0.5005 mm inset, consistent
  with `POUR_CLEARANCE = 0.5 +/- 0.01` in `tests/test_gerber.py`.
- KiCad writes Gerber with y negated relative to the board file, so board and artwork
  coordinates differ by a sign on one axis; `emfit/gerber.py:330-333` applies no sign flip in
  `read_gerber`. The pad oracle crosses that boundary on purpose and agrees to 1e-6 mm.
- `from_kicad` still ignores y (the strip is modelled centred and straight), `taper="dominant"`
  still collapses 28 track widths silently, `h` still counts mask and foil (1.6 mm against a
  1.51 mm core), and there is still no copper loss.

## Verified this session

- Fast selection, run **without** an extra `-q`: `pyproject.toml` already sets `addopts =
  "-q"`, so a second `-q` makes it `-qq` and suppresses pytest's summary line entirely.
  `python3 -m pytest tests/ -m "not slow"` -> `356 passed, 9 deselected in 20.58s`, exit 0;
  365 collected. `python3 -m pytest tests/test_kicad.py tests/test_board.py` ->
  `92 passed in 12.25s`, exit 0 (80 tests in `test_kicad.py`, 12 in `test_board.py`). The two
  new tests are the arc refusal (`tests/test_kicad.py:648`) and the `port` key
  (`tests/test_cli.py:168`).
- The full-suite figures below are from `62d1684` and were not re-run after `531c56c`: 348
  tests, 0 failures / 0 errors / 0 skipped, 284.024 s (junit `/tmp/full.xml`).
- Report build: exit 0, 64 pages, 0 undefined references or citations, 2 Overfull and 16
  Underfull box warnings. Overfull: `sec_eigen:93`, `sec_impl:100`. Underfull: `sec_impl` 48-48
  plus 15 in `sec_outlook` (29-29, 29-31, 33-36, 36-37 x3, 38-40, 40-40 x2, 40-43 x3, 43-44,
  44-48, 50-50). `sec_intro.tex` line 118 is wrapped at 85 + 77 characters; the split was
  measured against the same build with the 163-character line of `3b25817` left intact, which
  gives the same 2 Overfull and 16 Underfull, so the wrap is kept.
- `sec:msres-import` is defined once (`sec_microstrip_res.tex:323`) and referenced twice
  (`sec_outlook.tex:47`, `:68`).

## The coupon measurement

| Quantity | Reference box | Imported coupon | Change |
| --- | --- | --- | --- |
| grid cells | 66x52x26 | 124x87x44 | cell pitch 0.400 mm -> 0.200 mm |
| eps_eff | 3.60431 | 3.584698 | -0.54 % |
| beta | 231.886 rad/m | 231.253918 rad/m | -0.27 % |
| closed-form eps_eff (same cross-section) | 3.343938 | 3.325455 | w/h 2.0 -> 1.875 |
| closed-form beta | 223.353067 rad/m | 222.734924 rad/m | w/h 2.0 -> 1.875 |
| eps_eff bias vs its own closed form | +7.79 % | +7.80 % | this is the quotable agreement |
| beta bias vs its own closed form | +3.82 % | +3.82 % | this is the quotable agreement |
| z0 modulus (port plane) | 53.144 ohm | 57.0252 ohm | +7.3 % (not quotable) |
| alpha | not compared -- own normalisation (see `tab:ms-alpha`) | 3.1381406 +/- 0.0863021 Np/m | n/a |
| run time | 31.79 s | 120.27 s | 3.8x more work |

- Only the bias is quotable: eps_eff bias **+7.79 %** on the reference box against **+7.80 %**
  on the imported coupon, and beta bias **+3.82 %** on both. The agreement is between biases,
  not between impedances.
- Each bias divides a measurement by the closed-form estimate for that SAME cross-section. The
  eps_eff closed form depends on w/h, so the two differ: 3.343938 at w/h = 2.0 on the reference
  box, 3.325455 at w/h = 1.875 on the coupon. Dividing the coupon 3.584698 by the reference
  3.343938 gives +7.20 %, which is NOT the bias and must not be quoted as one.
- The `z0` modulus is not quotable and not comparable: the port is a geometric plane, not a
  driven one, and 57.0252 ohm is a reference reading only. The complex port impedance is
  z0 = 54.6240 + 16.3736j ohm, |z0| = 57.0252 ohm; the complex value is what the geometric-plane
  port yields, and a real part cannot be read off it.
- `alpha` normalisations are not comparable: the coupon alpha is 3.1381406 +/- 0.0863021 Np/m
  (`.scratch/coupon_cross_section.json`); `sec_microstrip_res.tex` publishes the reference box's
  attenuation in its own normalisation, so no like-for-like comparison was made and none should
  be inferred.
- Sources: `.scratch/coupon_cross_section.json`, `.scratch/coupon_cross_section.log`; the
  narrative is in the workspace knowledge base `lessons_learned.md`, heading "Coupon
  cross-section measured on a doubled box".
- Do not mix closed-form variants: the report quotes 48.686 ohm, and that run's own internal
  figure is 48.0987 ohm.
- `decisions.md:527` records a different default box, 62x44x22 at 0.400 mm (eps_eff
  3.621781, beta 232.446960). It is not the reference box; do not blend the two.

## The mesh-refusal contract

- `emfit/cli.py:324-328`: a path that cannot be read prints `cannot read {path}: {exc}` on
  stderr and returns `EXIT_USAGE` (2); every other outcome is 0.
- `emfit/cli.py:425`: a readable board the solver cannot represent prints
  `no microstrip spec: {refusal}` and returns 0 -- "A board the solver cannot represent is not
  an error" (`emfit/cli.py:317-322`); under `--json` the same sentence goes to stderr
  (`emfit/cli.py:373`) so stdout stays one JSON object.
- `emfit/board.py:379-386`: `abs(self.x_far - self.length) > TOL * self.length` raises "the
  strip ends at x_far = ... mm but the outline is ... mm long ... Crop the outline to the
  strip, or extend the net to the board edge."
- `emfit/board.py:400-417`: with `cell = h / n_sub`, any of `n_strip`, `n_clean`, `n_ref`,
  `n_line` that is not an exact integer raises "the mesh is cubic, so every dimension of the
  model has to be an integral number of cells ... these do not fit:", listing the fitting
  `n_sub` when `1..32` holds one and "no n_sub in 1..32 fits every dimension" otherwise.
- `emfit/board.py:295-298`, `:312-316`, `:320-323`: a board with no stackup thickness, no
  `eps_r`, or no Edge.Cuts outline is refused rather than defaulted -- "a wrong eps_r does not
  fail anywhere -- it just reports a different line".
- `emfit/board.py:241-251`, `:264-269`, `:275-283`: a `taper` other than `'raise'` or
  `'dominant'`, a net with no track segment, a net whose segments do not run along x, or more
  than one width under `taper='raise'` are each refused with the net named.

## The crop lands the far plane; the division is separate arithmetic

- Dominant-width line: `x_port 0.00865` -> `x_far 0.03222` = `23.57` mm of line over `h 1.6` mm,
  in a `70` mm outline. `n_line` is a whole number of cells only when `n_sub` is a multiple of
  `160` (`n_line = 2357 * n_sub / 160`); `n_ref` is the next binding dimension and needs a
  multiple of `32`.
- Smallest meshable spec for that box: `n_sub 160`, `0.01` mm cell, `n_strip 300`,
  `n_clean 838`, `n_ref 853`, `n_line 2357` -- all confirmed against `to_cell_counts`. At
  `n_sub 32` the same spec refuses: "no n_sub in 1..32 fits every dimension". Nothing is broken;
  a `23.57` mm line in a `70` mm outline simply does not divide into a cubic mesh small enough to
  search.
- Consequence for the published coupon study: `124 x 87 x 44` cells at `0.200` mm, `npml 12`
  (`decisions.md:527`) was hand-set, not derived from the import, and cannot be reproduced from
  it -- `87 = 2 * (12 + n_clean) + n_strip` needs `n_strip 15` (`w 3.0` mm) and `n_clean 24`, a
  `17.4` mm wide box, and `124 - 12` leaves `n_ref + n_line = 112` (`108` of line only if
  `n_ref 4`, i.e. `x_port 3.2` mm, which no document states -- that figure is arithmetic, not a
  quote). The import gives `w 2.0` mm on a `20` mm box, `x_port 4.5`, `x_far 7.0` mm, whose
  `n_ref` at `0.200` mm is `10.5`. State it as geometry: do not chase the old box, and do not
  change the published numbers.
- The cropped port-bearing spec (`net='RF_IN'`, `port_pad=('J1','1')`) does divide: `n_sub 16`,
  `n_pml 12`, `0.1` mm cell, `n_strip 20`, `n_clean 78`, `n_ref 33`, `n_line 25`. That is the spec
  the end-to-end run uses.

