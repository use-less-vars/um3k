# The passivity bound at the station planes: mechanism on the available evidence, reproduction outstanding

2026-11-09

## Status, in plain words

The warning being chased was a passivity report of the form `|S11|^2 + |S21|^2 = 0.251886 + 1.092917 = 1.344803`. Two things came out of today's work.

The first is that the specific number 1.344803 cannot have been produced by the command it was attributed to. The assert that emits that message lives in the `microstrip` study path (`emfit/studies.py:4599`, inside `_run_microstrip`), and `run_build_A.py` never goes through that path. The number's parameters are unknown, and no banked artefact reproduces it.

The second is a mechanism, identified from code and from three artefacts, that explains sums above 1 at the planes we do use: at extraction planes at or near a load, the transmitted magnitude is inflated by the wave split at the load's own cross-section. That is an inference from three artefacts, not a reproduction.

The honest status is **UNRESOLVED**: mechanism identified on the available evidence, reproduction outstanding. Nothing in this document says the passivity warning is resolved, fixed, or closed, and it should not be cited that way.

## 1. What was actually run, and what the script can and cannot do

The requested command was

```
python3 evidence/termination/run_build_A.py --s21-plane-col 51 --nsteps 4800 --mem-ceiling-mb 480 \
    --out evidence/termination/build_A_p51_n4800.json
```

`--nsteps` did not exist on that script before today. Its step count was the literal `2400` in the kwargs dictionary at `evidence/termination/run_build_A.py:510`. The flag was added today (integer, default 2400, documented in the parser), so the default behaviour of the script is byte-identical to what it was; the flag is the only way to move the step count and it moves nothing else. The command above was then run with `--nsteps 4800` and, because that finished inside the pre-set budget, again with `--nsteps 9600`.

The measured values at the plane-51 column are:

| nsteps | \|S11\| | \|S21\| | \|S11\|^2+\|S21\|^2 | wall |
|---|---|---|---|---|
| 2400 | 0.32586326001662264 | 0.7617054231929281 | 0.6863820159501787 | 80.0 s |
| 4800 | 0.3269916220080929 | 0.7633934713495123 | 0.6896931129625421 | 151.4 s |
| 9600 | 0.32700073686627196 | 0.7626004925210631 | 0.6884889931044529 | 296.5 s |

All three are well below 1. The full record, with the raw output lines, is in `evidence/termination/build_A_convergence_p51.txt`; the artefacts are `evidence/termination/build_A_p51_n4800.json` and `build_A_p51_n9600.json`.

`|S11|` settles by 4800 steps (the 4800 to 9600 change is 9.1e-6). `|S21|` does not: it moves 0.7617054 to 0.7633935 to 0.7626005, non-monotonically, so no limit is established from three points. Whether more steps would settle it is unknown, but it would not change the conclusion below, because none of these sums is anywhere near 1.

## 2. Reachability: the assert cannot speak for build_A

The passivity assert is at `emfit/studies.py:4599` and prints

```
passivity bound violated between the station planes:
|S11|^2 + |S21|^2 = {:.6f} + {:.6f} = {:.6f} ...
```

It sits inside `_run_microstrip` (function head `emfit/studies.py:4336`). That function is registered as the `microstrip` study at `emfit/studies.py:5707` (`run=_run_microstrip`) and is dispatched only from `emfit/cli.py:243` and `emfit/webapp.py:425`.

`run_build_A.py` does not go through the study registry. It imports `emfit.studies` and calls `microstrip_wave(...)` directly; the call is visible in the run log as `res = studies.microstrip_wave(**loaded_kwargs,`. It therefore cannot emit that message at all, at any step count, for any flag values.

So the triple 1.344803 did not come from build_A. Attributing it to the plane-51 command was wrong, and reproducing it under that command is not possible even in principle.

## 3. The triple itself

`0.251886 + 1.092917 = 1.344803`, equivalently `|S11| = 0.501884`, `|S21| = 1.045427`.

That triple appears in no file in the tree (a full-tree grep, including `.scratch/` and `.thoughtmachine/`, returns zero hits), and none of the 73 banked JSON records carrying s11/s21 values matches either addend to 1e-6. The scan, the quoted assert, the reachability list and the study parameter surface are recorded in `evidence/termination/passivity_triple_scan.txt`.

The parameters that produced 1.344803 are therefore **unknown**. This is not a rounding or transcription problem that can be argued away: a record with `|S11| = 0.501884` does not exist in the evidence set.

One caveat worth recording here rather than discovering later: squaring the two six-decimal magnitudes gives `0.501884^2 + 1.045427^2 = 1.3448051617850003`, which is 2 in the last place above the stated 1.344803. The stated total is consistent with full-precision magnitudes that print as those six decimals, so the target magnitudes are known to about six decimals and no better. Any bisection should aim at the printed values, not at a five-micro-unit-exact product.

## 4. The frame verdict: where each magnitude is referred

`result` at the assert (`emfit/studies.py:4595`) is the `MicrostripWave` instance returned by `microstrip_wave(...)` (`emfit/studies.py:4408-4426`), dataclass declared at `emfit/studies.py:1402` and constructed at `:4050`.

**`result.gamma`** - declared `gamma: complex` at `emfit/studies.py:1608`, set at `:4064` as `gamma=complex(fit_two.gamma),`. It is B/A of the two-wave station fit, referred to `z = 0` of the fit span, which is the first station plane; the docstring at `:1452-1454` calls it "the reflection coefficient at ``z = 0`` ... abs(gamma) is the standing-wave diagnostic". The separately reported `gamma_port` (`:4069`) and `gamma_plane` (`:4089`) are different fields, and the assert uses `gamma`.

**`result.s21`** - declared `s21: complex` at `emfit/studies.py:1615`, set at `:4071`, with its plane pair in `s21_planes` (`:1617`, `:4073`). Two branches:

- `s21_plane` unset: `s21_planes = (station_x[0], station_x[-1])` (`emfit/studies.py:3685`) and `s21` is `a2/a1` between the two station planes. Same cross-section pair as `gamma`; this is the case the assert was written for.
- `s21_plane` set (resolution at `emfit/studies.py:2965-2990`): `s21_planes = (x_port, x_cut)` with `x_cut = ix_extract * cell`, and `s21 = raw_s21 / reference.forward_ratio(x_port, x_cut)` (`emfit/studies.py:3352`) or `line_s21(...)` (`emfit/studies.py:1242`, called at `:3354`). The transmission is now measured from the port plane to the cut column.

The artefacts confirm this is the live path, not a reading of dead code. `build_A_50ohm.json` records `s21.planes_m = [0.0032, 0.0204]` - port plane at 3.2 mm, cut column 51 at 20.4 mm - while the station fit spans 0.0104-0.0200 m. `build_A_p51_n4800.json` records `s21.plane_index: 51`, `s21.deembed_distance_m: 0.0072`, and for s11 the basis string "gamma_port, the reflection moved to the port plane (`emfit/studies.py:3266`, declared at `:1607`). Plane-independent: it does not move when the extraction plane moves."

So yes: **when the extraction plane is named, `result.s21` moves to that plane while the reflection stays referred to the port/station origin.** The two magnitudes in the sum are referred to different cross-sections.

**Verdict: DIFFERENT FRAMES whenever `--s21-plane-col`, `--s21-plane-index` or `s21_plane` is set; SAME FRAME only on the station-span branch.**

What that implies: the sum of squares at `emfit/studies.py:4599` is not a passivity test at a site where the extraction plane has been named. Power conservation compares a reflection and a transmission referred to the *same* cross-section; adding `|gamma|^2` at the station origin to a port-to-cut transfer ratio measures nothing physical. No step count, mesh refinement or convergence sweep can make that sum valid, and the convergence table in section 1 is consistent with that: the sum is stable, small, and unrelated to the recorded >1 values.

**The `emfit/modal.py:746` case is different and is not this defect.** There, `passivity = float(np.abs(s11) ** 2 + np.abs(s21) ** 2)` combines that module's own s11 (near station, at `reference_distance`) with its own s21 (near-pair split propagated to the far end, `emfit/modal.py:742-746`). One author, one pair, one frame. Its tolerance is `passivity_tolerance = 1e-9` (`emfit/modal.py:633`) and its `passive` property follows from that. It should not be lumped in with the study-path assert.

## 5. Plane 50 versus plane 51: the load's own column

This is the evidence the mechanism rests on. Three artefacts, one configuration apart, all 50 ohm:

| artefact | \|S11\| | \|S21\| | sum | note |
|---|---|---|---|---|
| tracked `evidence/termination/build_A_50ohm.json` at commit f7c7dc1 (2026-11-01) | 0.21961548616463294 | 1.1051853963312406 | 1.2696657220271694 | geometry ny=206, y_extent 38.8 mm, n_strip=2, cells 280984, `s21_plane` "cut" |
| `evidence/termination/build_A_50ohm_p50_plane.json` | 0.325863 | 1.106043 | 1.329518 | extraction moved to plane 50 |
| today's plane-51 run | 0.32586326001662264 | 0.7617054231929281 | 0.6863820159501787 | `--s21-plane-col 51` |

The observation, stated plainly: **extraction at the load's own column yields `|S21|` just above 1.10, and moving the plane one column past the load drops it to 0.76.** A 45 percent drop from one column of mesh is not physics moving. It is the wave split at the load's own cross-section counting the load's own scattered field as part of the transmitted wave: the measurement plane sits on the lumped element, the recorded "forward" amplitude there contains the element's near field, and the ratio is inflated accordingly. Move one column downstream and the split is clean again.

This is the leading explanation for the recorded sums above 1 at load-adjacent planes. It is an inference from three artefacts, coherent with the code path in section 4 but not yet a demonstration: in particular it does **not** reproduce 1.344803, and it does not by itself explain the magnitude 1.61 seen at 100 ohm.

A bookkeeping note so the tracked artefact is not misread: the working-tree copy of `evidence/termination/build_A_50ohm.json` has since been overwritten by a plane-51 run recording `|S11| 0.325863`, `|S21| 0.761705`, sum 0.686382, with `meta.command_line` naming `--s21-plane-col 51`. The first row of the table above is the committed file at f7c7dc1, not the working-tree copy.

## 6. The records that already exceed 1

Fourteen banked records carry a sum above 1, so this is not a single anomaly. Highest first:

| record | sum | \|S11\| | \|S21\| |
|---|---|---|---|
| build_B_100ohm_v3c | 1.612203 | 0.473884 | 1.177980 |
| build_B_100ohm_v2 | 1.587879 | - | - |
| build_B_100ohm_v3d | 1.581855 | - | - |
| build_B_100ohm | 1.434874 | - | - |
| build_A_50ohm_cal | 1.373574 | - | - |
| build_A_50ohm_v3 | 1.366211 | - | - |
| build_A_50ohm_v3b_s11fix | 1.363411 | - | - |
| build_A_50ohm_v2 | 1.351245 | - | - |
| build_A_50ohm_p50_plane | 1.329518 | 0.325863 | 1.106043 |
| gate_gate_build_A_p50 | 1.329518 | - | - |
| build_E_50ohm_v2 | 1.146537 | - | - |
| build_E_50ohm_v3d | 1.118872 | - | - |
| build_E_50ohm_v3c | 1.108757 | - | - |
| build_E_50ohm | 1.082300 | - | - |

The pattern is that `|S21| > 1` clusters at planes at or near a load, which is where the section 5 mechanism bites. The dashes are records whose individual addends were not transcribed here; the sums were read from their artefacts during the scan that produced `evidence/termination/passivity_triple_scan.txt`, and no number in this table is estimated.

None of these is 1.344803, and none of them is claimed to be explained quantitatively yet.

## 7. What changed in code today, and what deliberately did not

Changed: one flag on `evidence/termination/run_build_A.py` - `--nsteps` (integer, default 2400), plus the comment naming it at the point of use, with `"nsteps": 2400` replaced by `"nsteps": int(args.nsteps)`. Nothing else in the script was touched, and the default path is unchanged.

Deliberately not changed: the assert at `emfit/studies.py:4599` was left exactly as it is.

The reason is that a frame verdict is a statement about what the numbers mean, not a measurement of what is wrong. A guard that refuses to let a non-passive pair through is doing its job when the pair is genuinely non-passive, and there are fourteen records above 1 whose provenance is not settled. Downgrading a physics guard on the strength of a code reading would remove the only detector we have for a real passivity failure, before we know whether one is happening.

What measurement would justify changing it: a run on the **station-span branch** (`s21_plane` blank, so both magnitudes are referred to the same cross-section) whose sum exceeds 1 by more than the step-count spread measured in section 1 (about 1e-3 in the sum), together with a demonstration that the excess does not shrink with mesh refinement. If such a run exists, the guard is reporting a real failure and the fix belongs in the physics, not in the assert. If instead every >1 sum is accompanied by a named extraction plane, the frame verdict explains them and the assert should be narrowed with a comment naming both frames - but only once that has been *measured* on a load-adjacent case, not assumed from the code path.

## 8. What would settle this

To reproduce 1.344803, the run needed is the one path that can emit the message: the `microstrip` study (`emfit/studies.py:5707`, via `emfit/cli.py:243`, or the web app at `emfit/webapp.py:425`), with

- a load placed **between** the station planes, and
- `s21_plane` left **blank**, so both magnitudes come from the station span,

then bisect the knobs recorded in the study's parameter surface (`emfit/studies.py:5621-5655`: `nsteps` default `MS_NSTEPS` 2400, `f0`, `npml`, `load_kind` default "none", `load_at_mm` default 15.2, `load_value` default 100.0, `s21_plane` default "") until the recorded magnitudes reach `|S11| = 0.501884` and `|S21| = 1.045427`.

Two honest cautions about that sweep. Six of the seven knobs are continuous or wide, so a blind bisection over them is a search in a large space; the productive order is the one suggested by section 5 - start with `load_value` and `load_at_mm` near the values that put a load at or just inside the station span, because that is where `|S21| > 1` is actually recorded, and treat `nsteps` as the last knob, since section 1 shows it moves the sum by at most about 4e-3. And if the sweep reaches the station-span branch at a load-adjacent plane and the sum is still above 1, the outcome is not a reproduction but a real passivity finding, which is a different (and more serious) document.

Until such a run exists, the status of this item is **UNRESOLVED**: the mechanism is identified on the available evidence, the reproduction is outstanding, and the passivity warning must not be recorded as resolved, fixed or explained away.
