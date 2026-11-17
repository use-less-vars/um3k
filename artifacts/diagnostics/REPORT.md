# Diagnostic: artifacts/reference_sim_volume.npz vs the Trame viewer

Data: schema `emfit.vis/2`, `nt=2400` steps, `dt=7.6263e-13 s`, `cell=0.4 mm`,
`nx,ny,nz = 62,212,22`, `x in [0,24.4] mm`, `j_cut=106 (y=42.4 mm)`,
`e_abs_volume (24,62,212,22)`, `e_abs_volume_stride=100`,
`e_abs_volume_step_index = 1,101,...,2301`, `frame_index = 1..2400 (stride 1)`,
`v_measured = 1.3821e8 m/s (reliable=1)`, `v_analytic = 1.5814e8 m/s`.

## Verdicts

**A. "24 volume frames instead of 2400" - NOT data loss; it is a declared cadence whose
aliasing is invisible to the user.**
- The file declares the cadence twice: `e_abs_volume_stride = 100` and
  `e_abs_volume_step_index = [1,101,201,...,2301]` (writer:
  `evidence/termination/run_build_A.py:1076-1085, 1170-1174, 1606, 1619`).
- The viewer reads the cadence (`poc_app.py:643-650`) and then uses it **nowhere**:
  no label, no legend, no state field. `_animation_block` (`poc_app.py:3287-3345`)
  emits `frames: 24` and no `steps_between`/cadence.
- The frame label is `frame {index+1} / {frames}` (`_frame_label`, `poc_app.py:426-437`),
  fed by `_volume_player_plan`/`_synced_frame_counts` (`:9059-9133`) and set at `:11356`.
  So the UI says "frame 3 / 24" plus a separate sim time - a user reasonably reads
  "3 of 24 time samples of 2400 steps", i.e. ~1/8 of the run, when it is step 301/2400.
- Physically the cadence is far too coarse to animate transport: `v*dt = 0.10540 mm/step`
  -> **10.54 mm per volume frame across a 24.4 mm domain (43%)**. The packet crosses the
  16.8 mm port->load distance in ~159 steps = **1.6 volume frames**. Anything seen
  "moving" in the 24-frame player is temporally aliased.
- Measured global argmax of `|e_abs_volume|` per volume frame jumps non-monotonically:
  k0 step 1: 0.0 | k1 101: 1.1 V/m @x=3.2 | k2 201: 158.7 @5.6 | k3 301: 119.9 @17.2 |
  k4 401: 32.9 @12.4 | k5 501: 52.5 @3.2 | k6 601: 23.0 @15.6 | k7 701: 24.7 @20.0 |
  k8 801: 16.0 @3.2 | k9 901: 4.4 @14.4 | k10 1001: 8.9 @20.0 | k11 1101: 3.2 @3.2 |
  k12 1201: 0.93 @7.2 | k13 1301: 1.4 @20.0 (full table `volume_max_track.json`).
  Peak position k3->k4 = 17.2 -> 12.4 mm (**-4.8 mm/frame**, i.e. backwards), because the
  dominant lobe is the standing/reflected structure, not the travelling front.

**B. Frames 3/4/12 are degenerate for a "peak displacement" measurement - correct, and
this is a measurement error in the review, not a viewer bug.** In the *plane* series
(`ez_ycut`, `frame_index=1..2400`) frames 3/4/12 are turn-on:
max |Ez| = 1.90e-13 / 2.95e-13 / 8.43e-12 V/m (global max is 149.89 V/m at frame 330,
1-based). Any peak tracker there gives 0 or noise. In the *volume* series the same
indices are steps 301/401/1201 and are energetic (119.9 / 32.9 / 0.93 V/m) - the two
"frame 3"s refer to **different time bases**, which is exactly the defect in A.

**C. No transposition.** Array layouts, viewer grids and `ravel(order="F")` agree:
`ez_ycut (t,x,z)`, `ez_xcut_* (t,y,z)`, `e_abs_volume (t,x,y,z)`.
`_volume_frame_grid` (`poc_app.py:9467-9538`) sets `dimensions=(62,212,22)`, `spacing=cell`,
`origin=(0,0,0)` and flattens with `order="F"` (x fastest = VTK point order) - correct;
`_vis_grid` (`:6888-6938`) uses `(62,1,22)` with `origin y = j_cut*cell = 42.4 mm` and
`(1,212,22)` with `origin x = xcut_near/far` - correct. No `swapaxes`/`transpose` in any
render path. The volume uses the node grid origin `(0,0,0)`, deliberately not the
half-cell colocated anchor - a half-cell (0.2 mm) offset, documented in the code, not a
transposition.

**D. Linear vs log: two different, differently-scaled colour mappings - REAL but titled.**
- `PLANE_BAR_TITLE = "Ez (Linear)"` (`poc_app.py:4951`), `VOLUME_BAR_TITLE = "|E| (Log)"`
  (`:4952`), `VOLUME_BAR_TITLE_LINEAR = "|E| (Linear)"` (`:4955`), bars hand-placed at
  `(0.02,0.28)` / `(0.88,0.28)` (`:4958-4961`).
- Volume is drawn log over a **global 60 dB** window `(peak*1e-3, peak)` computed over the
  whole 24-frame volume, not per frame: `_volume_abs_global_clim` (`:9135-9163`),
  `_volume_clim_for` (`:9443-9464`), used at `:11098/:11109`; `add_volume(... log_scale=True)`
  at `:5092-5099`, with a guarded retry without `log_scale` on the *same* clim at `:5108-5116`.
  Per-frame mode exists but is off by default (`VOLUME_CLIM_PER_FRAME`, `:9173-9179`).
- The plane bar is linear over `0..p99.5` of every stored plane frame
  (`COLOR_PERCENTILE=99.5`, `:181`, `_vis_colour_limit` `:377-402`). Cut sheets are log over
  their own `(peak/1000, peak)` (`_cut_sheet_clim` `:4210-4235`) with only a corner sentence
  (`_cut_clim_text` `:4238-4259`).
- Consequence: the same field appears with a linear colour table and a 60 dB log table, and
  the volume/plane comments (`:5085-5090`) note the colocated volume is ~2053x smaller in V/m
  than the cut planes. Both bars say "V/m", so cross-reading the two is misleading - but the
  titles do declare linear vs log. The genuine defect is the **global** (not per-frame) log
  window: a 60 dB span fixed by the run-wide peak makes the volume "breathe" as the packet
  decays (per-frame p99.5 collapses from 93 V/m at frame 240 to 0.005 V/m at frame 2399).

## Support: is the field itself coherent (so the alias is a sampling issue, not a solver bug)?

Peak-track displacement between consecutive stored *plane* frames, frames 132-378 (the
travelling packet): median **0.1056 mm/step** = `v_measured*dt` (0.10540) to within 0.2%;
mean 0.0826, IQR 0.0056..0.1142 (the low quartile is peak-flatness, not motion).
Cross-correlation of the x-profiles (x idx 12..52, parabolic sub-sample, corr 0.994-0.997):
0.0787 mm/step (160-339), 0.0826 (200-319), 0.0877 (200-259); -0.0025 after 340 (reflected).
Centroid of `|profile|^2` (idx 3..59): median 0.0897 mm/step, IQR 0.0585..0.1150; windows
150-199 0.0808, 200-259 0.0957, 260-319 0.1172, 320-379 0.0546. Peak position over the whole
span 3.25 -> 19.95 mm in 246 steps = 0.0679 mm/step (the packet disperses/spreads, so the
"front" advances slower than the phase). Frame energy `sum|Ez|^2`: 2.35e5 (f200), 2.38e4 (400),
1.01e4 (600), 1.32e3 (800), 3.36e2 (1000), ..., 3.98e-3 (2200).

**Conclusion:** the field is physically coherent (motion = 0.08-0.11 mm/step ~ v_measured),
the 24-frame volume is an honestly declared stride-100 dump, and the review's symptoms are
produced by (i) the undeclared 100-step cadence / index-vs-step "frame N" label, and (ii) a
run-global 60 dB log window. Reviewer hypothesis of data loss or transposition is refuted.

## Figures
PNG rendering could not be completed in this sandbox: every matplotlib process
(`Agg`, dpi 80-90, one figure per process, 2-3 axes, both at 512 MB and 1 GB) was killed
with SIGTERM before `savefig`. Scripts are committed and re-runnable where matplotlib works:
`mk1.py` (frames 3/4/12 shared linear scale), `mk2.py` (per-frame p99.5 scale),
`mk3.py` (volume k=3 vs k=4, x-z at y=42.4 mm, shared scale).
Numbers behind them are inlined above and in `d1_out.txt`, `d2_centroid.py` output,
`volume_max_track.json`.
