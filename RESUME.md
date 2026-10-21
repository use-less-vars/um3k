# RESUME -- session state

## Checkpoint 2026-10-21 -- the standing wave is dead, the forward wave grows, CW is running

`decisions.md` section 64 has the tables and the argument; this is the state
it leaves.  Two readings died today, not one.  Section 63 refuted Im(z_c) --
forcing z_c real moves passivity by at most 0.0021, and in the wrong
direction, and the column that carries the whole excess, `P2/P1`, does not
contain z_c at all -- and section 64 refutes the reading that was standing
behind it, that the excess is a standing wave in the feed section.  The
forward/backward decomposition is post-processing on the existing pulse dump,
no new solve: `.scratch/m2/ab_decompose.py`, 0.49 s, A and B reconstructed
from the station voltages with the port reflection, x = station_x - x_port =
1.70 to 11.30 mm.  The result is unambiguous.  max |B|/|A| is 0.0312, and all
eleven accepted bins are A_RISING -- the forward wave grows monotonically
across the span, the forward share of the travelling power is 98.7 to 100 per
cent, and there is no backward wave for a standing pattern to be made of.
beta * span runs 1.407 to 3.013 rad, so the beat the old reading wanted was
not even a quarter period.

The old eps_eff is wrong and, more to the point, physically unavailable.  The
8.6 mm figure implies eps_eff 1.24 to 1.65 across the band, against 3.325
from the closed form and 3.56270 from the solver -- a factor of two, not a
rounding.  And 8.6 mm is a quarter guided wavelength only at 4.779 GHz, where
the profile is still monotone, so the one frequency at which the arithmetic
closes is the one frequency at which the standing-wave story is already
excluded.

What this opens is the opposite question from the one we were asking.  |A|
does not oscillate; it rises, monotonically, by 0.83 to 4.47 per cent over
9.6 mm.  Fitted as an exponential, the growth rate alpha is 8.6e-4 to 4.55e-3
per mm, and alpha/f^2 is near-constant at 6.4e-5 to 7.4e-5 across the band,
so alpha goes as f^2.  That is a shape, not an explanation: f^2 is what a
solve losing energy to its own grid would show, and it is also what a genuine
distributed loss in the feed would show, and the two have not been separated.

The CW twin is running, not finished.  `.scratch/m2/board_run_cw.py` is
solving 3.6667 GHz detached and a watcher queues 7.8333 GHz after it; dumps
`board_cw_3.6667GHz.npz` and `board_cw_7.8333GHz.npz` land with their logs
alongside.  They run one at a time, about 43 minutes each.  The mesh was
proven against the pulse run before either was let go: n_strip 30, n_clean
73, n_ref 75, n_line 235, cell 1e-4, 322 x 200 x 76, dt
1.906574869530972051e-13, relative mismatch 0.00e+00.  Expected convergence
is 7627 steps to 3.667196 GHz and 8034 steps to 7.833566 GHz.

Next after CW is the refinement test, not a repair.  Halve dt and re-measure
alpha on the same decomposition.  If alpha falls with dt it is numerical and
the story ends there; if it is invariant it is in the model and the story
gets harder.  Moving the reference plane is not the fix to reach for first --
the reference-plane move is the manoeuvre that produced the eps_eff that just
died, and reaching for it again before the refinement test would repeat the
error section 64 is about.

The lid test still holds.  Nothing measured on an imported board is quotable
yet, and the A-test was skipped.

## Checkpoint 2026-10-21 -- Im(z_c) is refuted, and term 2 is a flux-profile ripple

`decisions.md` section 63 has the table and the argument; this is the state it
leaves.  The pulse run that the checkpoint below was waiting on has returned:
`.scratch/m2/board_run_pw_dump.log`, `EXIT=0`, 3249.6 s of pulse solve, 11
accepted bins, dump `board_run_pw.npz` 13010 B.  Determinism against the
production record is exact -- max|diff| 0.000000e+00 on both passivity
columns -- so everything below is that result re-examined offline, not a new
variant.  It supersedes the classification test set out in the checkpoint
below, which the run has now answered.

The Im(z_c) hypothesis is refuted.  Re-doing the de-embedding on the same dump
with z_c forced real, magnitude kept, moves passivity by at most 0.0021 -- and
in the wrong direction: the real-z_c column sits above production at 11/11
bins, 1.68 % -> 1.77 % at 3.6667 GHz and 9.15 % -> 9.37 % at 7.8333 GHz.  The
column that carries the whole excess, `|S21_power|^2 = P2/P1 = Re(v2 conj i2)
/ Re(v1 conj i1)`, is identical under all three z_c conventions (1.0189 ->
1.0968), because z_c does not appear in it.

The two-term model is revised.  Term 1 is the boundary loss, and it still
dominates on the coupon, so the model was not wrong -- it was mis-attributed.
Term 2 is not de-embedding phase: it is a flux-profile term.  The metric is a
ratio of local Re(v conj i) at two planes, one of which sits about 1.7 mm from
the port in the unsettled region, so the ratio picks up an amplitude ripple
that grows with frequency.

The excess is a spatially distributed flux rise, not launch localisation.
P2/P1 does exceed the mean of steps 2-8 at 11/11 bins (+0.42 % to +2.48 %), but
the first step carries only 31.86 % to 39.06 % of the total excess against
12.5 % for a uniform rise, and re-referencing does not cure it: P9/P2 =
1.0128 ... 1.0610 and P9/P3 = 1.0090 ... 1.0379, both still greater than 1.
The profile is quantitatively consistent with one small standing wave -- a node
near the port, an antinode near station 8 above about 6.8 GHz, eps_eff ~ 1.28,
VSWR 1.018 to 1.097 -- but that reading is self-consistent and not proved.

Test order from here.  (1) A CW twin at two or three frequencies on the same
mesh: cheap frequency-domain solves, one at a time, inside the 4 GiB cap.  A
matching along-x envelope makes the effect linear mismatch and ripple; a flat
P9/P1 = 1 makes it a time-integration energy error in the pulse path.  (2) Then
the lid test as the loss control for term 1, which is what it always was, now
that there is no gain hypothesis left to excuse the board.  The A-test -- use
station 2 or 3 as the upstream reference -- is SKIPPED: already answered by the
station profile, where re-referencing removes only about a third of the excess.

No S-parameter on an imported board is quotable yet, now for a named reason
rather than an outstanding doubt.

## Checkpoint 2026-10-21 -- the anchor was never at the tone, and the board is running

HEAD is `6d7d4d2` on `master` ("Broadband single-span subsection; record the
anchor snap and the window control"), parent `020b935`.  The working tree is
clean apart from `Intro.txt` (` M`, not ours and never staged).  The new
subsection `sec:msres-broadband` sits at 403-578 of
`docs/report/sec_microstrip_res.tex`, which is now 612 lines: the eleven-bin
curve, the refusals, and the test that separates a boundary sink from a port
sink.  `decisions.md` is 1146 lines and section 59 is new.  Nothing in either
quotes a board S-parameter.

Section 59 carries two findings.  The first: the record-level scalars are not
read at the tone.  The accumulator is built at `studies.py` 2407 with the
frequency snapped at 2375, f0 = round(f_target*span)/span and span = n_acc*dt;
for a 2400-step record at dt 0.7626 ps the spacing is 0.5464 GHz, so a
5.830 GHz target lands on 6.010 GHz.  The printed beta 239.4598 with eps_eff
3.61420 inverts to 6.0102 GHz, while the cw tone returns beta 232.4470 at
5.8278 GHz.  Phase velocity agrees to 0.1 per cent, so the solve is right and
the label is wrong; gate2 never tests this.

The second: PULSE_WINDOW cannot move the record-level scalars at all, because
the weight is applied only to the array handed to the bin transform
(`studies.py` 2758-2815).  Last turn's byte-identical agreement was therefore
structural, not evidential.  The valid control is the same bin under both
weights, where the Hann variant returns |S21| 1.24903, |S11| 0.05479,
passivity 1.563072, residual 0.06883 against flat 0.99017, 0.00431, 0.980464,
0.00612.  The corroboration now in section 59: interpolating the eleven flat
bins to 6.010 GHz gives beta 239.38 against the printed 239.4598, residual
0.00663 against 0.00662, |S21| 0.99003 against 0.99000, |S11| 0.00449 against
0.00456.

The board run is going.  The 05:58:47 attempt was launched without setsid or
nohup and died when its exec session's container went away; it is preserved
byte for byte as `.scratch/m2/board_run_dead_0558.log`, 785 bytes.  The
relaunch is 07:02:02 UTC as PID 2038, verified alive at 99.6 per cent of one
core with RSS 2.83 GB from `/proc/2038/stat` utime and stime, +498 ticks in
5 s:

    setsid nohup bash -c 'PYTHONPATH=/workspace python3 -u .scratch/m2/board_run.py > .scratch/m2/board_run2.log 2>&1; echo EXIT=$? >> /workspace/.scratch/m2/board_run2.log'

Geometry is the lid run's, unchanged: 322x200x76 cells at 0.1 mm, nsteps 9600,
n_sub 16, n_air 48, n_top 12, n_pml 12, n_stations 9, net RF_IN, pad J1.1,
w 3.0 mm, x_port 8.7 mm, x_far 32.2 mm.  Pulse first, then the cw anchor;
figures to `.scratch/m2/figs_board`.  The log stays at 785 bytes until the
pulse returns -- the study prints nothing mid-solve -- so liveness has to be
read from `/proc`, never from the byte count.

The next action is a classification, stated as a test.  When the pulse
returns, read the per-bin passivity curve: flat, every bin sunk by roughly the
same fraction, names the boundary as the sink, exonerates the port and makes
the lid the fix; threshold-and-rise, flat below some frequency and falling
above it, names the port as the sink, and that is a design note only.  The
falsification read stands: nothing here is quotable as a board S-parameter
until passivity lands within 2 per cent of unity.

## Broadband sweep: built, gated, and the window was the fault

The pulse path is committed: one broadband record, transformed bin by bin, with
the per-bin power budget as the test at every frequency, and the cw run at
5.8278 GHz kept as its validation case.  The first gate attempt failed -- every
bin that survived the guards came back non-passive, passivity 1.524749 to
1.564827, |S21| 1.24903 at the bin nearest the tone, 12 of 25 bins flagged as
a passivity bug -- and the cause was the Hann time weighting.  With a flat
weight the bin nearest the tone agrees with the cw twin: |S21| 0.99017 against
0.98126, passivity 0.980464 against 0.962932, eps_eff 3.60970 against 3.62178,
0 BUG rows.  Gate 2 passes.  Eleven of the twenty-five spec'd bins are usable
and fourteen are refused with their reason printed on the row, by the
beta*span floor at the bottom and the pi branch limit at the top; that split
is the probe span and eps_eff, not the fix.  decisions.md section 56 has the
argument.  No broadband S-parameter is quotable yet: this is the coupon, not
the board.

The insight worth carrying: a taper on a closed transient is not
amplitude-neutral -- it multiplies the packet by a curve that is still moving
underneath it -- so the per-bin phasors stop being one mode, and the guards,
which are tests on the fitted beta, moved their own verdict with it (twelve
usable bins tapered against eleven flat).  The whole-record scalars were clean
throughout (|S21| 0.99000, |gamma| 0.00456, residual 0.00662), which is what
localised the fault to the per-bin read and cleared the solve, the reference
and the de-embedding in one step.

The next action is the board run at the lid geometry, nsteps=9600, broadband:
one run for the whole spectrum instead of a frequency loop.  What it is
expected to settle is whether the board's remaining deficit is flat across the
band or rises with it -- flat names a boundary, rising names the port.  That
is the experiment the proposal section below asked for, now runnable.
Section 55's numbers stay unquotable, and no pad-port S-parameter is quoted
until a run has no unaccounted sink.

## Checkpoint 2026-10-21 -- the lid, moved: 0.753 to 0.904, and still no quote

The pad-port run's sink was diagnosed as the top matched layer sitting 0.75
substrate heights above the strip, and the test was to raise it to 3.0 heights
and change nothing else.  It ran: 322x200x76 at 0.1000 mm, 4800 steps, about
1380 s.  Passivity went 0.753059 to 0.904486, |S21| per millimetre 0.0875 to
0.0310, eps_eff 3.79848 to 3.51062 against a closed form of 3.32545.  The lid
was a cause and three fifths of the deficit; a factor 4 in clearance bought a
factor 2.6, which no evanescent tail does, so a second term of about 9.5 per
cent of the power remains and is not the lid.  It is not quotable: two of the
three acceptance criteria failed (passivity 9.55 per cent short of 1, |S21|
2.7 times the gate-2 leakage instead of within 2), while the eps_eff criterion
passed.  decisions.md section 55 has the table and the argument.  The three
numbers from the first run -- 0.753, 0.0875 dB/mm, 3.798 -- remain unquotable
and are now joined by their replacements; nothing in this project quotes a
pad-port S-parameter until a run has no unaccounted sink.

The next experiment is one run at 6.0 substrate heights of lid with the
lateral extent untouched, about 35 to 40 minutes.  If the deficit keeps
falling the remainder is the boundary; if it flattens, the remainder is the
lumped source and the walls.  Until that runs, the milestone's quotable claim
is the mechanics -- a pad-named port on an imported KiCad board, end to end,
with S-parameters and two figures -- and not the numbers.

## The sweep, as a proposal -- not built

The band is the next milestone, and there are two ways to spend the wall clock
on it.  A frequency loop is what the study path already does, because f0 is
snapped to a DFT bin and everything after it -- the station fit, beta, the
S-parameters, the power budget -- is computed at that one bin, so a loop is a
loop rather than a change.  The price is one full run per point: at this
clearance that is 4800 steps over 3.7 million cells, about 1380 s, so nine
points come to roughly 3.5 hours and twenty to 7.7 hours, and every point
carries its own fit residual and its own passivity sum to inspect.  A pulse is
the other route: one run whose source is broadband instead of a CW ramp, with
the station records kept in time and transformed at every bin.  Its cost is
set by the lowest frequency to be resolved rather than by the number of
points -- 4800 steps covers one period at 5.83 GHz, so a 1 GHz floor is about
six periods and lands near 9000 to 10000 steps, call it 35 to 45 minutes for
the whole spectrum -- plus the records themselves, two components at nine
stations over the full time history, and a port that absorbs over the band and
not at one frequency.  What the path does not have today is any of that: no
choice of excitation, no wideband launch, and no metric computed at more than
one bin.

The argument for the pulse is not only the factor of five in wall clock.  The
per-bin power budget turns the whole spectrum into a test at every frequency,
and the sink becomes a function of frequency, which is the measurement that
separates the two candidates named in section 55: a boundary term is flat in
frequency, a leaky wave grows with it.  The proposal is therefore: build the
pulse path, keep the single-frequency run at 5.8278 GHz as its validation case
-- two independent routes to the same bin have to agree before either is
believed -- and quote a spectrum only after the passivity sum has been read at
every bin it produces.  None of this is built, and the frequency loop stays in
the record as the honest cost of not building it.

## Checkpoint 2026-10-21 -- milestone 2, falsification read

Checkpoint -- milestone 2 complete on `wip/m2`. The branch sits four commits above `master` (`8518f72`): `d69bde2` the `--port-pad` flag, `49bca14` the `nsteps` ceiling turned into a stated cost, `4eee73f` the `microstrip_board` study plus the `str` parameter kind, and a docs commit carrying this checkpoint and section 54 of `decisions.md`. Land it with `git checkout master && git merge --ff-only wip/m2`.

A port can now be placed on a pad and run end to end. `python3 -m emfit board PATH --net RF_IN --port-pad J1.1 --json` fills the board spec's `port` key with the reference, the pad number, the net and the pad's copper position; `--port-pad` without `--net` exits 2 with a named reason; a pad the board does not declare is named in the refusal and left unfixed. And `python3 -m emfit run microstrip_board --set board=... --set net=... --set port_pad=J1.1` reports `|S11|` at both the measured plane and the port plane, `|S21|` between the station planes, the mismatch as a VSWR, the passivity bound (named as a bound and explicitly not a losslessness check), both beta readings, and the station-span wrapping warning. Text parameters now render as text inputs in the web form, so the browser path can express a filename or `J1.1`.

The acceptance run (`n_sub=16`, `n_air=12`, `n_top=12`, `npml=12`, `nsteps=4800`, `f0=5.8278`, `crop=true`, pad `J1.1` on net `RF_IN`): 322 x 200 x 40 cells at 0.1000 mm in a 32.20 x 20.00 x 4.00 mm box, 4800 steps of which 3600 transformed, 720 s, two figures (line phasors and the mid-plane Ez slice). beta 238.050 rad/m from the one-wave fit against 222.735 closed form, `|gamma|` 0.02055, fit residual 0.05007, eps_eff 3.79848 against 3.32545, line Z0 50.617 ohm closed form against 53.6803 from the stations, `|S11|` 0.02018 = -33.90 dB at both planes (beta is real here, so moving the plane changes phase and nothing else), VSWR 1.0412:1, `|S21|` 0.867547 = -1.234 dB over 14.10 mm between the station planes, passivity sum 0.753059, ground-current full/strip ratio 1.000. Above 4000 steps the record warns on stderr that the mesh will take minutes, quoting only the two measured anchors and predicting no wall clock.

Deferred, and named. No comparison is drawn with the earlier direct coupon measurement: this box is 40 cells tall and that one 52, so the absorbing lid sits closer and `|S21|` is expected to fall--two runs that differ in the lid do not check each other. The `0.2 mm` coupon cell cannot exist (`8.5 mm / 0.2 mm - 12 = 30.5` cells, so `n_sub = 16` or `32` are the only offers), which makes 0.1 mm the cheapest real cell. A bad-pad refusal exits 0 like every other `no microstrip spec:` refusal.

Falsification read, corrected. What would have convicted the run: a launch row naming `J1.1` while the mesh still tracked the taper; `|S11|` differing in magnitude between the two planes; a full/strip ground-current ratio away from 1.000; an `|S21|` of exactly 1 (which would mean the two stations shared a plane). The passivity clause was half-right and is now three-way: above 1 is a bug, near 1 is what a lossless material expects, and far below 1 is an unaccounted sink that must be named before quoting. This run's 0.753 was read as the first when it was the third -- the sink was the top PML, 1.2 mm (0.75h) above the strip. The residual 0.05007 stands as the largest number in the run and is reported rather than explained away.

**Hazard worth keeping.** `.scratch/` is gitignored and `.scratch/study_run.py:11` writes
`open(".scratch/study_dump.txt", "w")` with a cwd-relative path, so re-running it from the repo root would
overwrite the evidence file with nothing visible in `git status`. Run such scripts from `/tmp/retime`.

**State.** History `master ffbb4a4` -> `a1cafd8` -> `6e65897` -> `d555b4d` -> `9763897` -> `329258e` on
`wip/ports` is milestone 1's chain; `master` now sits at `8518f72` and `wip/m2` carries the four milestone-2
commits above it. `Intro.txt` is modified in the working tree and is **not ours**: never stage, edit or revert it.
`git stash drop` is not available through this tool's surface (only push and pop), so the stale `stash@{0}`
has to be dropped by hand. Merge with `git checkout master && git merge --ff-only wip/m2`; `wip/seam2` is
never merged.


Branch: `wip/m2`, four commits above `master` (`8518f72`): `d69bde2` the `--port-pad` flag, `49bca14` the `nsteps` cost, `4eee73f` the `microstrip_board` study, and the docs commit carrying this checkpoint and `decisions.md` section 54. No HEAD hash is written on this line on purpose: hashes here have gone stale twice. Describe the position by its subject and confirm it with `git log -1 --oneline`.
Base: master @ `8518f72`. master already carries the ten delivered commits (tip `62d1684`), `ffbb4a4` the milestone-1 decisions entry and `8518f72` the milestone-2 order; `wip/m2` adds the port work and its docs on top, so master fast-forwards.
Working tree right now: clean apart from `Intro.txt` and the pending docs commit (`RESUME.md`, `decisions.md`). The arc refusal and the `port` key in `board --json` are **committed** (`ec88551`), as is the crop (`4ed5045`); nothing else of ours is outstanding in the tree. `Intro.txt` is modified and is NOT ours -- never stage, edit or revert it. `docs/report/*.tex` and `docs/report/main.pdf` are committed and clean.

## To land the work

```
git checkout master
git merge --ff-only wip/m2
```

`wip/seam2` (`62d1684`) is already an ancestor of master, so do not merge it again. There is no `merge` and no `branch -f` in the agent's tool surface, so these two lines are yours to run.

## What the ten commits on master establish

Code (4 commits):

- `8440ae9` cli: a GIF is no longer filed as a figure, PNG only. Rationale: a GIF is not a
  citable figure, and the animation claim is split into "test" and "observation" in `ad336bd`.
- `d75b467` cli: `python -m emfit board PATH [--net NAME] [--eps-r EPS] [--port-pad REF.NUM] [--json]`.
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

## Outstanding: step 4 of the port work, whose crop now exists

- Step 4, S-parameters and a field slice on the imported coupon board. Acceptance: the imported
  coupon reproduces the hand-built study within the fit residual, and a port on an SMA pad runs
  end to end -- but that first clause is arithmetically impossible for the imported coupon (see
  "The imported coupon is meshable but not measurable").
- It is not blocked by the solver: on the cropped port spec the mesh is built and the solve
  runs, and only the station fit declines (see "The imported coupon is meshable but not
  measurable"). Before the crop the refusal was sharper, and with the port on J1.1 it was
  sharper again: the pad-derived spec has `x_far` = 7.0 mm inside a 70 mm
  outline, so `to_cell_counts` refuses it on its first check
  (`abs(x_far - length) > TOL * length`). The dominant-width `RF_IN` spec (x_far = 32.22 mm) is
  refused the same way, and `tests/test_board.py:184` asserts that refusal.
- The crop now exists: `MicrostripBoard.cropped_to_strip` (`emfit/board.py:498`, commit
  `4ed5045`) moves the box to `x_far` and declares `'length'` in `supplied`, and it is recorded
  in `decisions.md` section 48, "The outline is cropped to the strip by the caller, and the crop
  declares itself". The cropped port spec then meshes at `n_sub 16`, `n_pml 12`: `n_strip 20`,
  `n_clean 78`, `n_ref 33`, `n_line 25`. It is not a repair but a recorded choice: it changes the
  box, and the line modelled is the 2.0 mm run the port sits on, not the 29.8 mm feed.

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

## The imported coupon is meshable but not measurable

- The port path was driven end to end through the API by `.scratch/run_port_coupon.py` (scratch, uncommitted; do not commit it, do not delete it). Its input was `MicrostripBoard.from_kicad(support, net='RF_IN', eps_r=4.4, port_pad=('J1', '1')).cropped_to_strip()`. It printed `x_port 0.0045000000000000005`, `x_far 0.007`, `length 0.007`, `w 0.002`, `supplied ('eps_r', 'length')`, `Port(position=0.0045000000000000005, y=0.01, net='RF_IN', reference='J1', number='1', side='front')`; then the counts `{'n_strip': 20, 'n_clean': 78, 'n_ref': 33, 'n_line': 25, 'cell': 0.0001}`; then a `70 x 200 x 52` mesh at a `0.1` mm cell with `nsteps 9600`, about `288` s of CPU, single-threaded.
- It then refused, and the refusal is right. `RuntimeWarning` at `emfit/studies.py:2167`: `sigma_beta (317.77195698611627) must be smaller than beta (282.2292282696173)`; then `ValueError: no station-impedance fit was formed on this record ... Run it with reference=...`.
- The geometry is why, not the code: the modelled line is `4.5` mm to `7.0` mm, so `2.5` mm, and the fitted stations span `5.0` to `6.5` mm, which is `0.067` of a guided wavelength at `beta 282` rad/m (a `22.3` mm wavelength). Nine stations across a tenth of a wavelength cannot pin a phase constant better than it is large, and `reference=` does not rescue it because it asks for a load-free run of the same `25` cells.
- So acceptance 2 of step 4 -- a port on an SMA pad runs end to end -- lands as: the port is placed, the spec is cropped and declared, the mesh is built, `9600` steps run, and the analysis declines to quote a beta. The chain is complete and the line is a tenth of a wavelength long.
- Acceptance 1 -- the imported coupon reproduces the hand-built study -- is arithmetically impossible and was never true of the published box. The arithmetic is in the section above and comes to a `17.4` mm substrate against the import's `width 0.02` m, and `21.6` mm of line against the import's `23.57` mm. The published coupon numbers stand for a hand-built box. No published number is changed and none is called wrong.
- The width that could be measured in principle, the dominant `w 3.0` mm run, needs `n_sub 160`, which is a `3222 x 2000 x 196` mesh and about `1.26e9` cells: not runnable here either. So the imported coupon has no measurable configuration at any mesh this code can build, and the `3.0` mm study stays hand-built.
- Gap closed in milestone 2: the CLI does have a path from a pad to a study. `--port-pad REF.NUM` with `--net` fills the board spec's `port` key, and the registered `microstrip_board` study runs that spec end to end, with `microstrip_wave_board` as its internal helper rather than an unregistered function; the older `microstrip` study still takes only `nsteps, f0, npml, load_kind, load_at_mm, load_value, eps_r, h_mm, strip_cells`, and `nsteps` is capped at `20000` and the record warns on stderr above `4000`: the `0.2` mm coupon needs `4800` steps (`120.27` s measured) and a `0.1` mm cell needs `9600`, so the ceiling now states a cost instead of refusing the request. So step 4 is a command, not a scratch script: `python3 -m emfit run microstrip_board --set board=... --set net=... --set port_pad=J1.1`, which is what the milestone-2 acceptance run used.
