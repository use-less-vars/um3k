# Flux-projection extraction: design and five-bracket prediction

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

(Note: the printed coefficient set in this paragraph does not reproduce its own
quoted residual vector - see the section H1 erratum in
gap_analysis_2026-11-03.md. The re-fit of record is A ~= 0.7332, B ~= 0.0296,
C ~= 0.211, RMS ~ 5.2e-4. The derived mag(12)/mag(14) values above are
unaffected at the 2e-4 level either way, so no conclusion in this document
depends on which set is used.)
(Separately, the section 6 mechanism description was corrected on 2026-11-03 - see
section 6-A. Sections 4 and 8 are unaffected.)

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

## 4. The revised five-bracket prediction

This replaces the earlier "3-10 pp / sub-1 pp" pair and the three-bracket table that stood
here; both depended on the single-exponential model now refuted.

Why the shape matters as well as the level. If the two-column average under-measures the true
mode by a multiplicative factor alpha that is constant across planes, projection removes alpha
but preserves the curve shape: the slope stays. If alpha is plane-dependent - more
under-measurement at plane 51 than at plane 65, because the field is more purely modal at 65 -
projection removes both the bias and some of the slope. The slope is therefore a second
observable, and it separates a constant extraction bias from one that varies with the plane.

| projected `\|s21\|` | reading |
|---|---|
| **Flat (within +/-0.5% across planes) at 0.6553 +/-1%** | extraction was the issue; anchor correct; AC-3 testable |
| **Flat at a value != 0.6553** | extraction was the issue; anchor needs correction |
| **Preserves the slope** | extraction bias is multiplicative-constant; slope is real physics (mode evolution, not reflection) |
| **Preserves the slope at a different level** | both effects; constant shift = extraction, residual slope = physics |
| **Projection raises a runtime error** | projection design bug - stop |

Flatness is the primary prediction because it tests extraction correctness without depending on
a model we now know is wrong; the slope is what says whether the residual is physics.

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
- emfit/studies.py - `build_mode_plane`, already imported there, supplies the mode's
  transverse profile. The projection is a bare dot product, sum(E*mode)/sum(mode*mode),
  over the same column the average already reads.
- emfit/ports.py is NOT used. Its travelling_waves / reflection / transmission helpers
  decompose *plane* fields; the projection decomposes a *column* field. Different
  operation, different object.
- If implementation finds ports.py necessary, the design is wrong and the work stops.

The projection replaces the average at that site. Nothing else in the pipeline needs to move
for the study to be decisive; the solve, the probe planes and the anchors all stay as they are.

### 6-A. Errata, 2026-11-03 (commit-10c)
Sites quoted from emfit/studies.py at HEAD d3a96b9; sections 4 and 8 stand unchanged.
(a) Site. 2964-2968 is the modal-launch sampling block (mode_plane.e_z over the strip rows,
size-checked against port_edges), not the cut probe. The probe is 3025-3036 (blame 5dca4a3b,
2026-11-01); the column is built at 2912-2913, column_path(cc, ix_extract, j_centre, 0,
k_strip): 4 E_z edges, k = 0..3, one y row. (b) Mechanism. No (E[ix-1]+E[ix])/2 exists in the
probe, and the channels are not the same quantity. 3030 cut_signals[0] =
edge_path_voltage(stepper.e, cut_column): one scalar path sum over those 4 edges, no averaging.
3031-3035 cut_signals[1] = 0.5*(plate_current at ix_extract-1 + plate_current at ix_extract):
the real two-column average, acting on an H-derived current, not on E. The station currents at
3021-3023 repeat it. An E-profile projection cannot reproduce an H-derived average. (c) s21
chain. 3139-3140 v_cut = cut_spec[0], i_cut = -cut_spec[1]; 3409-3412 a_cut, b_cut = 0.5*(v_cut
+/- Zc*i_cut)*exp(+/-gamma*x_cut); 3418-3419 s21 = a_cut/a_port divided by
reference.forward_ratio; 3415 gamma_plane = b_cut/a_cut also reaches the result. No V-only,
I-only or V/I expression exists on the path, so a one-channel projection returns a hybrid
amplitude filtered in an uncontrolled proportion. Both channels take the same filter, or the
study does not measure what it claims. (d) Narrative. "Under-measures by a constant factor
alpha" is withdrawn as a mechanism description. The average is a top-hat reporting a value
between the mode's peak and its mean, in a proportion set by the field's shape at the plane; the
direction of that bias is what the projection measures, not something asserted in advance here.
Removing residual moves |s21| down, toward the 0.6553 anchor, so bracket 1 stays reachable. The
section 4 brackets are behavioural and survive this correction unchanged.

## 7. Cost and limits

The solves already exist (nx72 mesh, 335808 cells, planes 51-65 all outside the PML which
starts at 66), and the mesh and probe planes do not change. Whether the first pass can
post-process banked artefacts depends on whether they retain the plane field, which this
document does not establish; if they do not, the projection is computed in-solve and the first
pass costs one run per plane, measured elsewhere at 41.9 s wall and 340.8 MB peak RSS.

What it would NOT settle: it does not settle which of the three readings in section 2 is
right (a longer domain or a beat-aware fit would be needed for that), and it does not test
hypothesis 4.

## 8. Explicit non-claims

- No run was performed for this document.
- Nothing was graded.
- No gate, threshold, tolerance or AC bar was re-priced.
- Hypothesis 4 is named and untested; no number is attached to it.
- The brackets in section 4 are pre-registered and frozen as of commit-10b (2026-11-03), binding on the interpretation of any authorised run.
- Nothing here authorises a run.

**The brackets in section 4 are pre-registered and frozen as of commit-10b
(2026-11-03). They are binding on the interpretation of any flux-projection
run that the dispatch authorises: whichever bracket fires, the analysis must
be written in terms of that bracket, not a new one. The design does not
itself authorise the run - the dispatch row in dispatch_log.md does, and it
cites these brackets.**
