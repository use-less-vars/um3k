# Flux-projection extraction: design and three-bracket prediction

Date: 2026-11-03. Status: design/specification only. No run performed, nothing graded,
no gate re-priced. ASCII only by construction.

## 1. The question, and why it is now load-bearing

The current extraction takes a two-column average of the field at each probe plane and
calls the result the forward-wave amplitude. For a uniform loaded line, |s21| must be
exactly plane-independent downstream of the evanescent region. It is not: 0.7628473102840976
at plane 51 falls to 0.724568753 at plane 65, and it is still falling between the last two
planes (-0.004564 over 2 planes). Either the evanescent region extends further than assumed,
or the measurement carries a plane-dependent bias.

The flux-projection study is therefore now the load-bearing test of whether the current
extraction can measure T at all. It is no longer merely a good idea: every downstream
verdict that leans on the extraction inherits this ambiguity until the test is run.

## 2. The 63/65 refutation: the old model cannot be leaned on

H1 fit, quoted from `gap_analysis_2026-11-03.md` section H1: `mag(Delta) = A + B*exp(-C*Delta)`
with `Delta = plane - 51`, where A = 0.732349452526682 +/- 0.00288036 is "the asymptote,
mag(infinity)", B = 0.037084500417724 +/- 0.00216249 is "3.71 % of the plane-51 magnitude" and
C = 0.203186317916544 +/- 0.03890627 is "per plane; poorly constrained". The two continuation
values in the bullets below, mag(12) = 0.735585 and mag(14) = 0.734505, are that same analysis's
H1 continuation of this fit at planes 63 and 65, not a new fit.

- prediction at plane 63: 0.735585; measured 0.729132484
- prediction at plane 65: 0.734505; measured 0.724568753

Both measurements sit below the fitted asymptote, which cannot happen if the asymptote is a
lower bound and the decay is monotone from a value above it. The single exponential is
refuted.

Deltas per 2 planes from 51 to 65: -0.011058, -0.005634, -0.004279, -0.004044, -0.004350,
-0.004564. They flatten rather than continue shrinking, which is the shape that broke the fit.

Three readings, all still live:

(i) Very slow exponential with a decay length longer than the 14-plane window. The PML starts
at plane 66, so this geometry cannot measure further out; a longer domain would be needed.

(ii) Linear-like decay, which is physically odd for a passive linear system but is what the
last four deltas look like.

(iii) Half a beat cycle from a backward wave, expected period ~34 planes: 2*beta*cell = 10.6
deg/plane, so 360/10.6 = 34 planes. The monotone fall across 51-65 is consistent with the
down-half of one beat. The previous analysis was not designed to rule (iii) out.

Determinism check: reading the two-wave port-de-embedded field, |s11| = 0.32556486641109117
is the same across the three solves (both new artefacts and the plane-51 anchor
`build_A_50ohm_v3_beta2wave.json`). The old-schema `sweepN51`-`sweepN59` files carry a
different quantity in `s11.magnitude` (0.03379343163562476 at plane 51) and must not be
compared to it. So the load and its reflection are unchanged between solves and the bias is
not in the load; the plane dependence lives in the forward extraction, which is what this
study targets.

## 3. Thesis: the mismatch is a projection mismatch

The launch is modal: it injects the mode's own transverse profile. The extraction is a
uniform two-column average that does not know the shape of that profile. When the field at a
plane is a superposition of the forward mode and a decaying residual, the average mixes the
two with weights set by the profile rather than by the mode, so the measured amplitude
depends on the plane even when the true modal amplitude does not.

A correct extraction projects the field onto the mode's own eigenprofile and reads the
complex modal amplitude. By orthogonality that number is blind to residual content, so it
should be plane-independent downstream of the launch - which is exactly the property the
two-column average fails.

## 4. The revised three-bracket prediction

This replaces the earlier "3-10 pp / sub-1 pp" pair, which depended on the single-exponential
model now refuted.

| projected \|s21\| at planes 51/55/63/65 | reading |
| --- | --- |
| ~0.6553, within +/-1 %, plane-independent | Extraction was the issue. The two-column average under-measures the true mode by ~10 pp at every plane. The anchor is correct. Flux projection closes AC-3's structure question. Highest-value outcome. |
| ~0.73, still plane-dependent | Extraction is fine; the physics has extra modes. The 0.73 is a real over-anchor reading that neither the lumped anchor nor the two-column average explains. The next study is mode decomposition, not projection. |
| plane-independent at a value != 0.6553 | Both extraction and anchor are wrong in correlated ways. The value tells us what the true T is; the anchor was being compared against the wrong target. |

These brackets are cleaner than the originals because the primary prediction is
plane-independence, which tests extraction correctness without depending on a model we now
know is wrong.

## 5. Hypothesis 4 - load-cut fringing (named, not tested)

Hypothesis 4 is named here and is NOT tested by this study; no number is attached to it. The
load is a cut (open or matched termination) whose fringing field sits within a few cells of
the probe plane, so the two-column average can read fringing as forward amplitude.

That is a mechanism for a plane-dependent, load-specific bias. It is also the reason the
brackets in section 4 are stated as plane-independence rather than as a specific value: if
fringing matters, the projected number will move with the load, and only the
plane-independence part of the prediction survives cleanly.

## 6. Extraction sites

- emfit/studies.py lines 2964-2968 - the cut probe's two-column average. Column 50 is the
  load's own column, 51 is its neighbour.
- emfit/ports.py - the mode/eigenprofile machinery the projection would use.

The projection replaces the average at that site. Nothing else in the pipeline needs to move
for the study to be decisive; the solve, the probe planes and the anchors all stay as they are.

## 7. Cost and limits

The solves already exist (nx72 mesh, 335808 cells, planes 51-65 all outside the PML which
starts at 66), so the first pass is a post-processing of banked fields plus one code change at
the site in section 6. No new FDTD run is strictly required for the first pass.

What it would NOT settle: it does not settle which of the three readings in section 2 is
right (a longer domain or a beat-aware fit would be needed for that), and it does not test
hypothesis 4.

## 8. Explicit non-claims

- No run was performed for this document.
- Nothing was graded.
- No gate, threshold, tolerance or AC bar was re-priced.
- Hypothesis 4 is named and untested; no number is attached to it.
- The three brackets in section 4 are predictions, not pre-registered gates.
- Nothing here authorises a run.
