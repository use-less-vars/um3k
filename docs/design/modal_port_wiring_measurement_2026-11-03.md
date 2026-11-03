# Modal launch wiring — measurement and derivation 2026-11-03

Status: measurement record, split out of `modal_port_wiring_design_2026-11-03.md` on
2026-11-03. **Nothing here was re-measured in the split.** Every number, table, quote and
diff hunk below is the pre-split text of that design document, moved by line range with a
script — not retyped and not paraphrased. The only edit made to moved text is the
line-number fix recorded under `## Line numbers, re-measured against the applied tree`.
The decisions, constraints, the bracket table, the four tests and the interface
statements stay in `docs/design/modal_port_wiring_design_2026-11-03.md`.

## What this record contains

* **The 41.1 % measurement, with its conditions.** `max|w/mean - 1|` = **41.1089 %** on the
  build_A cross-section (`n_sub=4`, `n_strip=8`, `n_clean=96`, `n_air=12`, `n_top=6`,
  `n_pml=6`, 0.4 mm cell, plane `213 x 23`, `k_strip=4`, y-nodes `j0..j1 = 102..110`,
  `j_centre=106`), spread `(max - min)/max|w|` = 44.4068 %. The figure is tied to that box
  and to that sampling — the edges `port_edges` names — and it is not a mesh-converged
  quantity: the `n_sub` table below shows it shrinking as the cheap box refines.
* **The 36 launch weights** — 9 y-nodes x 4 substrate z-cells: min `-1.878334752`, max
  `-3.378713882`, mean `-2.394401959`, all 36 negative, no zeros.
* **The profile structure.** Symmetric about `j_centre=106`: the `iy=102` and `iy=110`
  columns carry identical statistics (44.4068 %, 24.5599 %, 12.9 %, 7.31532 %, then
  5.69942 % at the centre), and the 36-weight vector's max mirror residual is quoted at
  **1.6e-15** — symmetric to machine precision. That is what makes the 41 % a *mode shape*
  rather than a tilt: a sheared profile (mirror residual of the order of the deviation
  itself) would have meant the launch weights carry a y-tilt the uniform top-hat does not,
  the 41 % would then be partly a shear, and the projection argument that the launch
  projects almost entirely onto the propagating mode would have needed re-deriving rather
  than quoting.
* **The z-variation** — 41.11 % at the outermost y-nodes, 3.037 % at the strip centre.
* **The edge/centre ordering inverts** between the two ends of the substrate stack: on the
  `iz=0` row `|w|` is largest at the strip centre (`-2.3265`) and smallest at the edges
  (`-1.8783`), while on `iz=3` it is the other way round (edges `-3.3787`, centre
  `-2.4671`). Per-row spread across the 9 y-nodes: 19.26 %, 15.77 %, 4.78 %, 26.98 %.
* **Why the bracket table was rewritten** — a bracket table is a falsifiable object: each
  row states in advance what a measured move would mean, so the number the host run produces
  has a reading waiting for it. A directional guess is a probability sketch and is not
  gradeable. Both go in the record; only the table is graded.
* **The directional-guess discussion in full** — the owner's guess (modal pulls `|s21|`
  toward the 0.6553 anchor, because launch evanescent content was inflating the 0.76), the
  refutation (plane 51 is downstream of the launch's decay length, so the launch shape
  barely enters `|s21|` there), and the worker's 55/45 tilt the other way.
* **Per-item reasoning** — the (b-i) argument for keeping the launch on the strip column
  rather than injecting across the plane, the cheap-box warnings, and the note-by-note
  reasoning carried inside the diff commentary.
* **The full verbatim diff**, three blocks — `emfit/studies.py`,
  `evidence/termination/run_build_A.py`, `tests/test_studies.py` — and the report-back list.
* **Appendix** — the pre-split decision prose kept verbatim, so that the split deletes
  nothing while the design doc states that material in condensed form.

## Heading map

Line numbers below are this record's. `source` is `docs/design/modal_port_wiring_design_2026-11-03.md`.

| line | heading | source |
| --- | --- | --- |
| 11 | `## What this record contains` | authored for the split |
| 51 | `## Heading map` | authored for the split |
| 76 | `## The 41.1 % measurement, and why the bracket table was rewritten` | source 22-75; heading supplied by the split, the block had none |
| 133 | `### A directional guess, tagged as a guess` | source 77-110, unchanged |
| 168 | `## The finding this design is written against` | source 112-154, unchanged |
| 212 | `## Line numbers, re-measured against the applied tree` | authored for the split; the measurement is of the applied tree, which the pre-split text predates |
| 242 | `## The diff` | source 241-564, identical except the three citation fixes |
| 249 | `### emfit/studies.py` | source 248, unchanged (inside `## The diff`) |
| 362 | `### evidence/termination/run_build_A.py` | source 361, unchanged |
| 417 | `### tests/test_studies.py` | source 416, unchanged |
| 543 | `## What to report back` | source 542-564, unchanged |
| 567 | `## Appendix — the pre-split decision prose, verbatim` | source 3-21 and 156-240, unchanged except the three citation fixes |

The appendix then reproduces four headings of the pre-split document
verbatim — `## Why this matters`, `## What changed from draft v1`,
`## Provenance and conformance`, `## What the flag does and does not change`.
They are quoted material, not sections of this record, and they are
listed here rather than in the table above.

## The 41.1 % measurement, and why the bracket table was rewritten

Draft v1's headline expectation was that a modal launch would reproduce the
published numbers to well inside the bracket, on the grounds that the present
excitation is *already uniform*. **That premise is false, and it is measured
false rather than argued false.** Sampling the placed `e_z` on exactly the
edges `port_edges` names, on the build_A cross-section (`n_sub=4`,
`n_strip=8`, `n_clean=96`, `n_air=12`, `n_top=6`, `n_pml=6`, 0.4 mm cell, plane
`nyn × nzn = 213 × 23`, `k_strip=4`, y-nodes `j0..j1 = 102..110`,
`j_centre=106`), the 36 weights — 9 y-nodes × 4 substrate z-cells — are:

* min `-1.878334752`, max `-3.378713882`, mean `-2.394401959`;
* spread `(max - min) / max|w|` = **44.4068 %**;
* peak deviation from a uniform top-hat, `max|w/mean - 1|` = **41.1089 %**;
* all 36 negative — one sign, no zeros.

That is a mode and not noise, and its structure says so: the column is
symmetric about `j_centre=106`, so the `iy=102` and `iy=110` columns carry
identical statistics (44.4068 %, 24.5599 %, 12.9 %, 7.31532 %, then 5.69942 % at
the centre); the z-variation is 41.11 % at the outermost y-nodes and only
3.037 % at the strip centre; and the edge/centre ordering **inverts** between
the two ends of the substrate stack — on the `iz=0` row `|w|` is largest at the
strip centre (`-2.3265`) and smallest at the edges (`-1.8783`), while on the
`iz=3` row it is the other way round (edges `-3.3787`, centre `-2.4671`).
Per-row spread across the 9 y-nodes: 19.26 %, 15.77 %, 4.78 %, 26.98 %.

The consequence for the bracket table is the opposite of what this section
originally promised. A modal launch is a genuinely different excitation — it
changes the drive on those edges by 41 % peak-to-mean — so *how much* `|s21|`
moves is now a real question rather than a foregone answer. Nobody may read a
large move as a mesh artefact: the launch changed by 41 %, so a move is the
launch doing something. The interesting outcome is the other one — a sub-1 %
move would itself be the finding, because it would say that a 41 % change in
the launch weights does not couple into `|s21|` at the measurement plane, i.e.
that the gap does not live in the launch shape at all.

The physical reason the *shape* matters at all is (b-i): the port column is
adjacent to structure the mode does not live in. An injection that spreads
across the whole plane would drive the y PML columns and the air cap above the
strip; those form a radiating aperture, the PML absorbs what they radiate, and
`|s21|` would then be measuring absorption rather than transmission — a number
that looks like a transmission coefficient and is not one. Keeping the launch
on the strip column, weighted by the mode, is what makes `|s21|` a
transmission measurement.

The outcome brackets, so the number the host run produces has a reading waiting
for it:

| change in `\|s21\|` at plane 51 | what it would mean |
| --- | --- |
| **sub-1 %** | The launch shape is not the explanation. A uniform top-hat and a true mode profile differ at the port, so a sub-1 % move would itself be the finding: it would say the 41.1 % comes from somewhere other than the launch shape, and the launch-artefact hypothesis is dead. That is a clean and useful result, not a null one. |
| **1-5 %** | The mechanism is real but too small to carry 41.1 % on its own. It becomes a gap analysis: whatever remains after the launch-shape correction has to be attributed to something else, and that something else is then the main term. |
| **above 5 %** | The launch shape is a first-order contributor and the earlier A-series numbers were priced against a contaminated incident wave. This is the highest-value outcome, because it re-prices work already done rather than only work still to come. |

*Brackets as agreed in review; the wording here is the implementer's
distillation of that agreement, not a quotation.*

### A directional guess, tagged as a guess

Not gradeable, and I would not defend it hard. My tilt is: **the move is
sub-1 %, and if it is not, `|s21|` goes slightly UP, not down.** Confidence
maybe 55/45.

Your intuition is that modal should pull `|s21|` down toward the 0.6553
anchor, because a modal launch injects less evanescent content and evanescent
content at plane 51 was inflating the 0.76. I think that argument has a hole,
and the hole is the reason I tilt the other way.

A uniform top-hat is not a random perturbation of the mode. It has the same
symmetry and the same sign on every edge of the column, so it projects almost
entirely onto the propagating mode and leaves only a small residue in the
higher-order ones. That residue is reactive: it stores energy at the port and
decays with distance. Plane 51 is a long way downstream. If the residue has
already decayed there, the launch shape barely enters `|s21|` at all, and the
sub-1 % bracket is the answer — in which case the gap is not a launch
artefact and this whole hypothesis is dead, which would be a clean and
useful result rather than a failed one.

The part that tilts me upward is the normalisation. The incident wave is
estimated from the same contaminated field the launch creates. A launch whose
overlap with the mode is less than one can bias that estimate down while the
transmitted amplitude at plane 51 is extracted from a field that is already
nearly pure mode. Bias the denominator down and the ratio goes up. Fixing the
shape fixes the bias — but whether the correction lands above or below
depends on which of the two extractions was more contaminated, and I have not
measured that.

So the honest statement is: this is a guess about which of two unquantified
mechanisms dominates, not a prediction. If it is wrong, the useful thing it
establishes is that the normalisation is not the mechanism, and that is worth
knowing.

## The finding this design is written against

Checked this session, on the module as it stands plus the house placement path
(`microstrip_mode_profile` → `plane_mode`), sampling exactly the edges
`port_edges` names:

* Cheap grid (`n_sub=1`, `n_strip=2`, `n_clean=1`, `n_air=1`, cell 1.6 mm,
  `nyn=9`, `nzn=3`, `j0..j1 = 3..5`, `j_centre=4`): the placed `e_z` on the
  port column is `[-9.378296592690226, -9.378296592690226,
  -9.378296592690226]` — flat, one value repeated. This is the **only** flat
  case and it is degenerate: `n_sub=1` means one z-cell, so the vertical
  profile has nowhere to vary and flatness there says nothing about the
  launch.
* build_A cross-section (`n_sub=4`, `n_strip=8`, `n_clean=96`, `n_air=12`,
  `n_top=6`, `n_pml=6`, 0.4 mm cell, `j0..j1 = 102..110`, `j_centre=106`,
  `nyn=213`, `nzn=23`): the profile solves (shape `(201, 16)`), `plane_mode`
  places it (shape `(213, 22)`), and the 36 sampled weights deviate from a
  uniform top-hat by **41.1089 %** (`max|w/mean - 1|`, spread
  `(max-min)/max|w|` = 44.4068 %). Measured, not inferred; the numbers and
  their structure are in the section above.

Deviation from uniform against `n_sub`, measured at the cheap box
(`n_strip=2`, `n_clean=1`, `n_air=1`, `n_pml=2`):

| `n_sub` | 1 | 2 | 3 | 4 | 6 | 16 |
|---|---|---|---|---|---|---|
| cell | 1.6 mm | 0.8 mm | 0.533 mm | 0.4 mm | 0.267 mm | 0.1 mm |
| `max\|w/mean - 1\|` | 0.0000 % | 1.0924 % | 0.7697 % | 0.5185 % | 0.2720 % | 0.0488 % |

Two warnings follow from that table. At *this* box the deviation **shrinks**
as the mesh refines — it is a coarse-cell, strip-edge effect and not a
converged quantity — and the only point above 1 % (`n_sub=2`, 1.0924 %) has a
margin thin enough that any later change to the box or to the profile solve
would eat it. So a cheap test asserting non-uniformity on this box is a trap:
it passes with 1 % of headroom at one `n_sub` and fails at the next one finer.

The deviation is a property of the **cross-section**, not of the x-extent and
not of the step count. The cheap test therefore keeps the build_A
cross-section — `n_sub=4`, `n_strip=8`, `n_clean=96`, `n_air=12`, `n_top=6`,
`n_pml=6`, which is `213 × 23` nodes — and shrinks only x: a short line, few
steps. The 41 % reproduces there for free, because the profile solve is a small
2-D quasistatic problem and only the FDTD is expensive; the cross-section test
below does exactly that and pays for no time stepping at all.

## Line numbers, re-measured against the applied tree

The pre-split text cited `emfit/studies.py:2932`, `:2935` and `:2846-2847`. Those
numbers predate the tree this record now describes, so the three citations the
argument actually turns on were re-measured with `grep -n` against the applied
tree on 2026-11-03 (`emfit/studies.py` 5492 lines,
`evidence/termination/run_build_A.py` 1571 lines, `tests/test_studies.py` 1915
lines):

| what the text cites | where it is in the applied tree |
| --- | --- |
| pulse injection, `current[port_edges] = drive_now * launch_profile` | `emfit/studies.py:2999` |
| cw injection, `current[port_edges] = float(drive) * ramp * np.sin(2.0 * np.pi * f0 * n * dt) * launch_profile` | `emfit/studies.py:3002` |
| `port_edges = np.unique(np.concatenate(` — the strip column `j0..j1`, cells `0..k_strip-1` | `emfit/studies.py:2852-2853` |

Where the moved text below reads `:2999`, `:3002` or `:2852-2853`, that is the
applied tree, and it is the only edit made to it.

Deliberately **not** remeasured: the `@@` anchors inside `## The diff`
(`@@ -2932 +2932 @@`, `@@ -2935 +2935 @@`, `@@ -2919 +2919,45 @@`,
`@@ -2382,2 +2382,7 @@`, `@@ -1071 +1071,13 @@`, and the rest). Those are
pre-split locators for a patch hunk — they say where a hunk belongs, not what
the tree says today — and the hunks are quoted as they were written. The same
goes for the incidental line references inside the diff commentary (`:2918`,
`:2908`, `:2586-2592`, `:3503-3516`, `:3680`; `:1065`, `:1066`, `:411`, `:540`,
`:438-469`, `:454-457`, `:1120-1143`; `:1802`, `:1158`, `:1670`, `:1459-1462`).
Re-measuring those moves every anchor in the patch at once, which is a different
job from this split; a reader who needs one of them should look it up rather
than trust it.

## The diff

Three edits, complete and self-consistent. Hunk headers are anchored on the
line numbers cited above; where an anchor is looser than a line number it is
because the exact text of a neighbouring line was not read, and the anchor is
chosen so the insertion point is unambiguous.

### emfit/studies.py

**(a) The import**, beside the other relative imports
(`emfit/studies.py:47-78`). `studies.py` needs one name, `build_mode_plane`,
which reaches `plane_mode` through the house placement path, so that single
import goes at module scope — the cycle check recorded above is what makes it
safe:

```diff
@@ -58,2 +58,3 @@ from .pml import PML, AbsorbedWork, cells_for_wavelength
 from .microstrip import COPPER_T, Microstrip
+from .modal_harness import build_mode_plane
 from .operators import CellComplex
```

**(b) The keyword-only parameter**, after `s21_plane` (`emfit/studies.py:2382`):

```diff
@@ -2382,2 +2382,7 @@ def microstrip_wave(
     s21_plane: str | int | None = None,
+    # The launch SHAPE, not a knob on the source: "lumped" broadcasts one
+    # scalar over the whole strip column and is what every artefact in this
+    # repository was recorded with; "modal" scales that same scalar by the
+    # placed microstrip mode's own E_z on that column (design 2026-11-03).
+    launch: str = "lumped",
 ) -> MicrostripWave:
```

**(c) The profile construction**, inserted between the allocations ending at
`drive_trace` (`:2918`) and the time loop (`for n in range(nsteps):`, `:2919`).
It must come after `current = np.zeros(cc.n_edges, dtype=float)` (`:2908`) and
after `port_edges` (`:2852-2853`), and it must precede the loop — the block
below is placed immediately before the loop so that no allocation is
interleaved with model construction, and so that `launch_profile` is in scope
for both injection sites:

```diff
@@ -2919 +2919,45 @@ def microstrip_wave(
+    # --- the launch shape (design 2026-11-03) ---------------------------
+    # "lumped" is one scalar over every port edge: this function has always
+    # driven the strip column that way, and the value is the Python float 1.0
+    # so the multiplies below are exact (IEEE-754 x * 1.0 == x, no dtype
+    # promotion) and a lumped run returns the same bits it returns today.
+    # There is ONE code path, not two: the factor is always applied, so the
+    # lumped arm cannot drift away from the modal arm, and the bit-identity
+    # test pins it with == rather than approx.
+    # "modal" scales those edges by the placed microstrip E_z on the same
+    # column, from the house placement path -- build_mode_plane()
+    # (emfit/modal_harness.py:67) over plane_mode() (emfit/modal.py:267) -- so
+    # this function holds no mode arithmetic and no offsets of its own.  Both
+    # names are imported at module scope; the design records the cycle check
+    # that makes that safe.
+    launch_shapes = ("lumped", "modal")
+    if launch not in launch_shapes:
+        raise ValueError(
+            f"launch={launch!r} is not a port-excitation shape this run can "
+            f"drive: the two are {list(launch_shapes)} -- 'lumped' (one scalar "
+            "over the whole strip column, the default) and 'modal' (that "
+            "scalar scaled by the placed microstrip E_z profile).")
+    launch_profile: float | np.ndarray = 1.0
+    if launch == "modal":
+        mode_plane = build_mode_plane(
+            cc, h=float(h), w=float(w), eps_r=float(eps_r),
+            n_sub=int(n_sub), k_strip=int(k_strip),
+            iy_strip_centre=int(j_centre), n_clean=int(n_clean),
+            n_air=int(n_air))
+        # port_edges is the same walk in the same order: the strip column
+        # j0..j1, cells 0..k_strip-1.  plane_mode zeroes every edge outside
+        # the mode's window (the y PML columns, the air cap), so the sample
+        # carries no launch outside the strip column by construction.
+        weights = mode_plane.e_z[np.arange(j0, j1 + 1), :int(k_strip)].ravel()
+        if weights.size != port_edges.size:
+            raise ValueError(
+                f"the modal launch sampled {weights.size} edges for a port "
+                f"that drives {port_edges.size}: the placed mode and the port "
+                "column disagree, and a launch cannot be part of one and not "
+                "the other.")
+        peak = float(np.max(np.abs(weights)))
+        if not np.all(np.isfinite(weights)) or peak <= 0.0:
+            raise ValueError(
+                "the placed mode has no launchable E_z on the port column "
+                f"(finite={bool(np.all(np.isfinite(weights)))}, peak={peak!r}): "
+                "a launch that is zero everywhere drives nothing, and |s21| "
+                "would then be a ratio of two runs that never started.")
+        launch_profile = weights / peak
     for n in range(nsteps):
```

**(d) The two injection sites**, each gaining the factor. `drive_now` is the
pulse's scalar, so `scalar * vector` is the right-shaped weight vector at
`:2999`; the cw drive is a scalar too, so `:3002` takes the factor on the end:

```diff
@@ -2932 +2932 @@ def microstrip_wave(
-            current[port_edges] = drive_now
+            current[port_edges] = drive_now * launch_profile
@@ -2935 +2935 @@ def microstrip_wave(
-            current[port_edges] = float(drive) * ramp * np.sin(2.0 * np.pi * f0 * n * dt)
+            current[port_edges] = float(drive) * ramp * np.sin(2.0 * np.pi * f0 * n * dt) * launch_profile
```

Notes on this diff:

* The validation is placed beside the code it protects, not in the coercion
  block at `:2586-2592`, so that the error a caller sees names the two shapes
  at the point where a wrong value would otherwise mis-drive one of them.
* Only `build_mode_plane` is imported. `plane_mode` is reached *through* it
  and is never called directly in `studies.py`, so importing it as well would be
  a dead import (F401). Do not add it back unless a hunk in this document starts
  calling it.
* Nothing else in `microstrip_wave` changes: `port_edges`, the captures, the
  geometry dict (`:3503-3516`) and `_slice_index` (`:3680`) are untouched.

### evidence/termination/run_build_A.py

Exactly three additive lines, no reflow, no other edit.

**The flag**, beside the other source/port flags (after the
`--s21-plane-index` block at `:1065`, before `--dry-run` at `:1066`; the hunk
below anchors on `args = ap.parse_args(argv)` at `:1071`, which is the
unambiguous "all flags are declared by here" point — put the block beside
`--s21-plane-index` if you prefer the order to read that way):

```diff
@@ -1071 +1071,13 @@ def main(
+    ap.add_argument("--launch", default="lumped",
+                    choices=("lumped", "modal"),
+                    help="port excitation shape: \"lumped\" (default) puts one "
+                         "scalar on every edge of the strip column and is what "
+                         "every record this script has written so far was "
+                         "driven with; \"modal\" scales those edges by the "
+                         "placed microstrip E_z profile, normalised to unit "
+                         "peak.  The twin takes the same value.  Design: "
+                         "docs/design/modal_port_wiring_design_2026-11-03.md.")
+
     args = ap.parse_args(argv)
```

**The call**, in `build_kwargs`'s dict literal, after `"excite": "cw",`
(`:410`):

```diff
@@ -410,2 +410,3 @@ def build_kwargs(
         "excite": "cw",
+        "launch": args.launch,
     }
```

**The record**, in `describe_kwargs`'s returned dict (`:538-562`):

```diff
@@ -538 +538,2 @@ def describe_kwargs(
     return {
+        "launch": kwargs.get("launch"),
```

Deliberately not changed, and this is the whole reason the diff is three lines:

* `twin_kwargs_from` (`:438-469`) needs nothing. It is `dict(kwargs)` with
  three keys moved, so `launch` is copied with the mesh and the twin runs the
  launch the loaded run ran — which is the only defensible pairing: two
  launches would make the `s21` normalisation a comparison of two excitations.
  Its docstring key list (`:454-457`) now omits `launch` and is stale prose;
  adding one word there is a follow-up, not part of this change.
* `main`'s `--with-twin` path and the `--dry-run` printing need no code: the
  twin's `kwargs` come from `twin_kwargs_from(build_kwargs(args))`, so the dry
  run prints the flag for both calls (`:1120-1143`).

### tests/test_studies.py

One class appended at the end of the file (currently ends at `:1802`). It uses
helpers already in the module — `_cheap_strip_kwargs` (`:1158`),
`_load_run_build_a` (`:1670`), `Grid`, `CellComplex`, `Load`, `np`, `pytest`,
`studies` — and two of the four tests cost nothing at all: the non-uniformity
test calls the public `build_mode_plane` directly on the build_A cross-section
with a short x span, so it steps nothing and pays for no FDTD. Only the
bit-identity test runs a line (40 steps, the same cheap line the last test in
the file already pays for).

```diff
@@ -1802,0 +1803,102 @@
+
+
+# ---------------------------------------------------------------------------
+# the launch shape flag: which port edges carry current, and the default that
+# must not move
+# ---------------------------------------------------------------------------
+class TestLaunchShapeFlag:
+    """``launch`` picks the port excitation; the size of the ``|s21|`` move it
+    causes is the open measurement this design exists to make, so no test here
+    asserts the move -- asserting it would be inventing the answer.
+    """
+
+    def _cheap_loaded_kwargs(self):
+        """The six-cell loaded line the last test in this file already runs."""
+        return _cheap_strip_kwargs(
+            n_sub=1, n_strip=2, n_line=6,
+            x_first=6.4e-3, x_last=11.2e-3, nsteps=40,
+            loads=(Load(8.0e-3, "series_r", 50.0),))
+
+    def test_the_absent_flag_is_the_uniform_top_hat_bit_for_bit(self):
+        """``launch`` defaults to the scalar broadcast, and the factor is 1.0.
+
+        The lumped arm multiplies the drive by the Python float 1.0, which is
+        exact in IEEE-754 and cannot promote dtype, and there is one code path
+        rather than two, so this is an equality and not a tolerance -- if it
+        ever needs ``approx``, the exactness claim in the design has been lost.
+        """
+        kwargs = self._cheap_loaded_kwargs()
+        absent = studies.microstrip_wave(**kwargs)
+        named = studies.microstrip_wave(**kwargs, launch="lumped")
+
+        for name in ("v_stations", "v_port", "i_ground_full",
+                     "i_ground_truncated"):
+            assert np.array_equal(np.asarray(getattr(absent, name)),
+                                  np.asarray(getattr(named, name))), name
+        assert abs(absent.s21) == abs(named.s21)
+
+    def test_the_launch_weights_are_not_a_uniform_top_hat(self):
+        """The launch shape is a mode on the build_A cross-section -- no run.
+
+        ``build_mode_plane`` is public and the profile solve is a small 2-D
+        quasistatic problem, so this costs no time stepping: build the build_A
+        cross-section with a 4-node x span and sample the column ``port_edges``
+        names.  Measured this session (design 2026-11-03): 36 weights, spread
+        ``(max - min) / max|w|`` = 44.4068 %, deviation ``max|w/mean - 1|`` =
+        41.1089 %, all one sign, no zeros.  The floor below is a tenth of that:
+        a regression guard, not a bracket on the physics.
+        """
+        from emfit.modal_harness import build_mode_plane
+
+        cell = 0.4e-3
+        grid = Grid.uniform(4, 213, 23, 4 * cell, 213 * cell, 23 * cell)
+        cc = CellComplex(grid)
+        j0, j1, k_strip = 102, 110, 4
+        mode_plane = build_mode_plane(
+            cc, h=1.6e-3, w=3.2e-3, eps_r=4.4, n_sub=4, k_strip=k_strip,
+            iy_strip_centre=106, n_clean=96, n_air=12)
+
+        weights = mode_plane.e_z[np.arange(j0, j1 + 1), :k_strip].ravel()
+        assert weights.size == 36, weights.size
+        assert np.all(np.isfinite(weights))
+        assert not np.any(weights == 0.0)
+        assert np.all(weights >= 0.0) or np.all(weights <= 0.0)  # one sign
+
+        deviation = float(np.max(np.abs(weights / weights.mean() - 1.0)))
+        assert deviation > 0.10, deviation
+
+    def test_an_unknown_launch_is_refused_by_name(self):
+        """A typo must not silently fall through to the scalar broadcast."""
+        with pytest.raises(ValueError) as caught:
+            studies.microstrip_wave(**self._cheap_loaded_kwargs(),
+                                    launch="tem")
+        text = str(caught.value)
+        assert "lumped" in text and "modal" in text
+
+    def test_the_build_a_cli_carries_the_flag_from_argv_to_the_record(
+            self, monkeypatch):
+        """``--launch`` reaches the record through ``build_kwargs``.
+
+        The dry run is the only place the arguments are visible without paying
+        for a solve, so this checks the flag end to end: argparse ->
+        ``build_kwargs`` -> ``describe_kwargs``, for the loaded call and for
+        the twin.
+        """
+        run_build_A = _load_run_build_a()
+        seen = {}
+        real = run_build_A.build_kwargs
+
+        def spy(args):
+            kwargs = real(args)
+            seen["args"] = args
+            seen["kwargs"] = kwargs
+            return kwargs
+
+        monkeypatch.setattr(run_build_A, "build_kwargs", spy)
+        assert run_build_A.main(["--dry-run", "--launch", "modal"]) == 0
+        assert seen["args"].launch == "modal"
+        assert seen["kwargs"]["launch"] == "modal"
+        assert run_build_A.describe_kwargs(seen["kwargs"])["launch"] == "modal"
+
+        assert run_build_A.main(["--dry-run"]) == 0
+        assert seen["args"].launch == "lumped"
+        assert seen["kwargs"]["launch"] == "lumped"
```

Two anchors in that diff are assumptions about the module and the script, and
each is cheap to check before writing the test. `Grid` and `CellComplex` must
already be module-scope imports of `tests/test_studies.py` — the load-column
test at `:1459-1462` builds `CellComplex(Grid.uniform(...))` that way, so they
are. And `--dry-run` must reach `build_kwargs` before it prints, or the spy
below never fires: if it does not, patch whatever `main` calls on the way to
the record instead, and say so in the report.

## What to report back

1. That the module-scope import worked: the design has decided it (the cycle
   check is recorded above), so the report only needs to confirm the single
   name imports from the top of `emfit/studies.py` without a cycle — one added
   import line in `studies.py` (`from .modal_harness import build_mode_plane`)
   and no second import to reconcile.
2. Nothing about the size of the `|s21|` move: that is what the modal run is
   for, and no number here predicts it. The flatness question is closed by
   measurement (44.4068 % spread, 41.1089 % deviation on the build_A
   cross-section), so report instead (i) whether the module-scope import
   worked, and (ii) the exact `launch` key as it appears in the artefact.
3. Whether `microstrip_mode_profile` solves both boxes the tests use. The
   cross-section test's box is the build_A one (`n_sub=4`, `n_strip=8`,
   `n_clean=96`, `n_air=12`: it solves a `(201, 16)` profile and `plane_mode`
   places it on `213 × 23`, so it does), and the bit-identity test's box is the
   cheap one (`n_sub=1`, `n_clean=1`, `n_air=1`: profile `(5, 2)` placed on
   `9 × 3`, shift 2 in y and 0 in z). If a future guard tightens the minimum
   box, widen `n_clean`/`n_air` together on both and keep the non-uniformity
   floor.
4. Bit-identity, stated as a measurement, not a belief: the lumped arm's
   `v_stations`/`v_port`/`i_ground_*` and `|s21|` against the same run on the
   pre-change module.

## Appendix — the pre-split decision prose, verbatim

`docs/design/modal_port_wiring_design_2026-11-03.md` states this material in
condensed form. It is reproduced here in full so that the split deletes nothing.
The only edit is the three line-number citations tabulated above.

## Why this matters

The port excitation in `microstrip_wave` is a uniform top-hat. Two lines, and
they are the whole source model:

* `emfit/studies.py:2999` — `current[port_edges] = drive_now` (pulse)
* `emfit/studies.py:3002` — `current[port_edges] = float(drive) * ramp * np.sin(2.0 * np.pi * f0 * n * dt)` (cw)

Both broadcast **one scalar over every edge in `port_edges`**
(`emfit/studies.py:2852-2853`, the vertical `e_z` edges of the strip column
`j0..j1`, cells `0..k_strip-1`). Nothing in the source carries a per-edge
weight, and no knob can add one.

That is acceptable only if the launched field is already the line's mode. It is
not, quite: a flat top-hat has a discontinuity at the strip edges, so it
launches the discrete mode *plus* a family of higher-order and fringing
content. The open question this design exists to answer is **how much of the
measured `|s21|` bracket is that launch artefact rather than the line**.

## What changed from draft v1

Draft v1 wired the launch through `emfit.modalport.ModalPort`
(`ModalPort.from_profile`, `emfit/modalport.py:189-191`) and hand-rolled the
full-plane `e_profile` plus its index offsets in `studies.py`. That is
withdrawn, for four reasons:

1. **`ModalPort` is dropped from the design (fact 8).** Nothing on the launch
   path needs it: it owns a station-plane readout, not a source. Neither
   `emfit/modal_harness.py` nor `emfit/studies.py` imports it, and adding the
   dependency to reach one weight vector would put a class with its own
   geometry between the run and its own port column.
2. **The hand-built full-plane `e_profile` is dropped.** It was the wrong
   object: a launch lives on the port column, not on a station plane, and a
   full-plane array would invite exactly the whole-plane injection that (b-i)
   above rules out.
3. **Per-family placement is delegated.** The profile solve, the y-window
   placement, the z placement and the PML/air zero-padding are
   `build_mode_plane`'s and `plane_mode`'s job, and are already written,
   already used by the modal station capture, and already the thing the
   published modal numbers were produced with. This design reimplements none
   of it and holds no offsets of its own — no `plane_window`, no
   `iy_shift/k_shift`, no `ModeProfile.plane_window` call.
4. **Relative imports.** `emfit/studies.py:47-78` imports relatively
   throughout, so the new import is `from .modal_harness import ...`, not
   `from emfit.modal_harness import ...`.

## Provenance and conformance

The chain this design leans on, unchanged and un-reimplemented:

* `build_mode_plane(cc, *, h, w, eps_r, n_sub, k_strip, iy_strip_centre, n_clean, n_air, check=False)` — `emfit/modal_harness.py:67-83`. Solves the profile with `microstrip_mode_profile`, places it with `plane_mode` on `cc.nyn × cc.nzn`, returns the `PlaneMode`.
* `plane_mode(profile, *, nyn, nzn, k_strip, iy_strip_centre, cell)` — `emfit/modal.py:267-312`. Allocates `np.zeros((nyn-1, nzn))` for `e_y`/`h_z` and `np.zeros((nyn, nzn-1))` for `e_z`/`h_y`, writes only the window's destination slices, and raises `ValueError` from `plane_window` when the placed mode does not fit. Everything outside the window — the y PML columns, the air cap above the strip — is therefore **exactly zero**.

So `mode_plane.e_z[j, k]` is the mode's own vertical field on the mesh's own
edge grid, already zero everywhere the mode does not live. The launch samples
it; nothing else.

Conformance requirements on the implementer:

* The arithmetic must be the two functions above and nothing else. If a
  placement detail looks wrong, it is fixed in `emfit/modal.py` in a separate
  design, not compensated for here.
* `check=False` is the default of `build_mode_plane` and is what this design
  calls with: `check=True` validates against the closed form, which is a
  development assertion, not something a run should fail on.
* **Import placement: module scope, and this is settled.** The two names are
  imported at the top of `emfit/studies.py` (diff ``(a)`` below), not inside
  `microstrip_wave`. The cycle check was run this session: no `emfit` module
  imports `studies` (regex over all 34 files, zero matches); the chain runs
  `modal_harness` → `modal` → {`materials`, `mode_profile`, `plane_phasor`,
  `ports`} and `mode_profile` → {`grid`, `materials`, `quasistatic`}, none of
  which reaches back; the only genuine cycle in the package is `studies`'
  own deferred `from .demos import DEMOS` at `:5373`, which is untouched.
  So this is **not a follow-up: do it in this change**, and
  `microstrip_wave` carries no function-local import. If the code ends up
  using only one of the two functions, import only that one.

## What the flag does and does not change

`launch="lumped"` (default) multiplies the drive by the Python float `1.0`.
That is exact in IEEE-754 and cannot promote dtype, so a lumped run returns the
same bits it returns today: the only textual change at the injection sites is
the ` * launch_profile` factor, and the tests pin the bit-identity.

`launch="modal"` scales the same scalar by the sampled weights, normalised to a
**unit peak** (`weights / max|weights|`). The normalisation is deliberate and
scale-free: the system is linear and `s21` is a ratio estimator, so scaling the
source cannot move `|s21|`. Two consequences, both load-bearing:

* The bracket table above cannot be moved by the choice of normalisation. If
  `|s21|` moves, the *shape* moved it.
* **Absolute quantities must not be compared across launches.** Poynting flux,
  the power-balance row, `|E|` maps and every other non-ratio number scale with
  the peak of the launch. A modal run is for comparing ratios only.

Caveat B, stated once and not to be argued away: **this is a projection, not
the discrete mode.** `port_edges` is only the vertical `e_z` edges of the strip
column (`emfit/studies.py:2852-2853`), so the launch carries the mode's `e_z`
and nothing of its `e_y` fringing — the fringing lives on edges the port column
does not include. A true discrete-mode launch would need a surface current on
the strip, not a weighted line of vertical edges. What this flag buys is the
mode's *shape on the edges the source actually drives*, which is exactly the
degree of freedom the uniform top-hat lacks.
