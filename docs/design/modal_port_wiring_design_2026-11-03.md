# Modal launch wiring — design 2026-11-03

Status: decision document, condensed 2026-11-03. The measurement it rests on, the derivation, the
line-number table and the full patch text are in
`docs/design/modal_port_wiring_measurement_2026-11-03.md`; that record is the authority for every number
quoted here, and nothing below is a second measurement.

## Why this matters

The port excitation in `microstrip_wave` is a uniform top-hat. Two lines, and they are the whole source
model: `current[port_edges] = drive_now` (pulse) and the ramped sinusoid (cw), both broadcasting **one
scalar over every edge in `port_edges`** — the vertical `E_z` edges of the strip column `j0..j1`, cells
`0..k_strip-1`. Nothing in the source carries a per-edge weight and no knob can add one. The module says
so itself, in `microstrip_wave`'s own docstring (quoted in
`docs/design/modal_port_recon_2026-11-03.md`):

> The port is a lumped current source on the ``E_z`` edges that span the substrate across the whole
> strip width at the port plane, ramped on over the warm-up ...

Zeroed at the top of every step and re-prescribed each step, so the current is **hard prescribed**: the
launch shape is a free choice the physics does not make for us, and the only question is whether the
shape we choose is the line's mode. A flat top-hat is not quite that mode — it has a discontinuity at
the strip edges, so it launches the discrete mode *plus* higher-order and fringing content. The open
question this design exists to answer is **how much of the measured `|s21|` bracket is that launch
artefact rather than the line**. `launch="modal"` builds the alternative and lets a host run answer it.

## The finding this design is written against

Sampling the placed `E_z` on exactly the edges `port_edges` names, on the build_A cross-section
(`n_sub=4`, `n_strip=8`, `n_clean=96`, `n_air=12`, `n_top=6`, `n_pml=6`, 0.4 mm cell, `213 x 23` nodes,
`k_strip=4`, y-nodes `j0..j1 = 102..110`, `j_centre=106`), the 36 launch weights — 9 y-nodes x 4
substrate z-cells — deviate from a uniform top-hat by **41.1089 %** (`max|w/mean - 1|`) with spread
44.4068 %, and are symmetric about `j_centre=106` to machine precision (max mirror residual 1.6e-15).
That is a mode shape, not noise. The deviation **shrinks** as the cheap box refines (1.0924 %, 0.7697 %,
0.5185 %, 0.2720 %, 0.0488 % at `n_sub` 2, 3, 4, 6, 16), so it is a coarse-cell, strip-edge effect and
not a converged quantity — which is why the non-uniformity test runs on the build_A cross-section, not
on a cheap box. Measured, not inferred; the tables are in the measurement record.

## What the flag does and does not change

`launch="lumped"` (default) multiplies the drive by the Python float `1.0` — exact in IEEE-754, cannot
promote dtype — so a lumped run returns the same bits it returns today. There is **one code path, not
two**: the factor is always applied, so the lumped arm cannot drift away from the modal arm.

`launch="modal"` scales that same scalar by the sampled weights, normalised to a **unit peak** (`weights
/ max|weights|`). The normalisation is deliberate and scale-free: the system is linear and `s21` is a
ratio estimator, so scaling the source cannot move `|s21|`. Two consequences, both load-bearing:

* The bracket table below cannot be moved by the choice of normalisation. If `|s21|` moves, the *shape*
  moved it.
* **Absolute quantities must not be compared across launches.** Poynting flux, the power-balance row,
  `|E|` maps and every other non-ratio number scale with the peak of the launch. A modal run is for
  comparing ratios only.

Caveat B, stated once: **this is a projection, not the discrete mode.** `port_edges` is only the
vertical `E_z` edges of the strip column, so the launch carries the mode's `E_z` and none of its `E_y`
fringing, which lives on edges the port column does not include. A true discrete-mode launch would need
a surface current on the strip. What the flag buys is the mode's *shape on the edges the source actually
drives* — exactly the degree of freedom the uniform top-hat lacks.

## The outcome brackets

The number the host run produces has a reading waiting for it:

| change in `\|s21\|` at plane 51 | what it would mean |
| --- | --- |
| **sub-1 %** | The launch shape is not the explanation. A uniform top-hat and a true mode profile differ at the port, so a sub-1 % move would itself be the finding: it would say the 41.1 % comes from somewhere other than the launch shape, and the launch-artefact hypothesis is dead. That is a clean and useful result, not a null one. |
| **1-5 %** | The mechanism is real but too small to carry 41.1 % on its own. It becomes a gap analysis: whatever remains after the launch-shape correction has to be attributed to something else, and that something else is then the main term. |
| **above 5 %** | The launch shape is a first-order contributor and the earlier A-series numbers were priced against a contaminated incident wave. This is the highest-value outcome, because it re-prices work already done rather than only work still to come. |

*Brackets as agreed in review; the wording here is the implementer's distillation of that agreement, not
a quotation.* Note the table has **three rows, not four**: the pre-split text has three, no "no move"
band was ever written down, and `sub-1 %` is the row that carries that reading.

Two directional guesses, quoted verbatim, kept because they predate the number and one was refuted:

[GUESS, owner, refuted 2026-11-03] "modal -> toward 0.6553, because launch evanescent content was inflating 0.76." Refuted: plane 51 is downstream of the launch's decay length; the launch shape barely enters |s21| there.

[GUESS, worker, 55/45 sub-1%] "the move is sub-1%; if not, |s21| goes slightly UP because the s21 denominator is estimated from the same contaminated field -- a less-matched launch biases the denominator down, ratio rises. Unmeasured which way it lands."

Why they are kept and why they are not graded: the bracket table is the falsifiable object — each row
states in advance what a measured move would mean — while the guesses are probability sketches and
neither is gradeable. Both go in the record; neither is graded.

## The four tests

One class appended to `tests/test_studies.py`:

1. **Bit-identity of the default.** `microstrip_wave(**kwargs)` and `microstrip_wave(**kwargs,
   launch="lumped")` agree **exactly** — `np.array_equal` on `v_stations`, `v_port`, `i_ground_full`,
   `i_ground_truncated`, and `abs(s21)` — because the factor is the float `1.0` on one code path. If it
   ever needs `approx`, the exactness claim above has been lost.
2. **The launch weights are not a uniform top-hat.** No FDTD: the public `build_mode_plane` on the
   build_A cross-section with a 4-node x span, asserting 36 weights, all finite, no zeros, **one sign**
   (`np.all(weights >= 0.0) or np.all(weights <= 0.0)`), and deviation > 10 % — a tenth of the measured
   41.1089 %, so a regression guard, not a bracket on the physics. Symmetry **is** asserted too:
   `np.allclose(weights_2d, weights_2d[::-1, :], rtol=1e-10, atol=0.0)` on the nine rows, against the
   1.6e-15 residual measured on this box, because a sheared profile would mean the sampled block and the
   mode window disagree about which row is the centre — a placement fault that would corrupt the launch
   while still clearing the 10 % deviation floor, so the floor alone would not catch it.
3. **An unknown launch is refused by name.** `launch="tem"` raises `ValueError` whose message contains
   both `"lumped"` and `"modal"`, so a typo cannot fall through to the scalar broadcast.
4. **The CLI carries the flag from argv to the record.** `--dry-run` under a monkeypatched
   `build_kwargs` shows `--launch modal` reaching `args.launch`, `build_kwargs()["launch"]` and
   `describe_kwargs()["launch"]`, and the default leg showing `"lumped"`.

## What NOT to change

* **`ModalPort` stays out.** It owns a station-plane readout, not a source; nothing in
  `emfit/modal_harness.py` or `emfit/studies.py` imports it, and reaching one weight vector through it
  would put a class with its own geometry between the run and its own port column.
* **No re-implementation of placement.** The profile solve, the y-window and z placement and the PML/air
  zero-padding are `build_mode_plane`'s and `plane_mode`'s job, and they are what the published modal
  numbers were produced with. No `plane_window`, no `iy_shift`/`k_shift`, no offsets of our own. A
  placement detail that looks wrong is fixed in `emfit/modal.py` in a separate design, not compensated
  for here.
* **No full-plane `e_profile`.** A launch lives on the port column, not on a station plane. A full-plane
  array would invite whole-plane injection, which drives the y PML columns and the air cap; those form a
  radiating aperture, the PML absorbs what they radiate, and `|s21|` would then be measuring absorption
  rather than transmission.
* **The module-scope import is settled — do it in this change.** `from .modal_harness import
  build_mode_plane` at the top of `emfit/studies.py`, not inside `microstrip_wave`. The cycle check was
  run: no `emfit` module imports `studies`, and the only genuine cycle is `studies`' own deferred `from
  .demos import DEMOS`, untouched. Import only the name that is used — a second import of `plane_mode`
  would be a dead import.
* **`check=False`**, which is `build_mode_plane`'s default: it skips five internal self-consistency
  identities — energy computed two ways, `c_prime` vs `capacitance_per_length`, an `eps_eff`/`Z0` round
  trip, the strip-column vertical drop, and `0.5*Re(v_mode conj(i_mode))` vs 1 W — each at rtol 1e-12.
  `check=True` **passes** on the build_A box, so the default is a cost choice, not a bypass of a check
  that would fail.
* **The twin needs no code.** `twin_kwargs_from` is `dict(kwargs)` with three keys moved, so `launch` is
  copied with the mesh and the twin runs the launch the loaded run ran; two launches would make the
  `s21` normalisation a comparison of two excitations.
* **Untouched symbols.** `port_edges`, the captures, the geometry dict, `_slice_index`, and
  `run_build_A`'s `--with-twin` path and `--dry-run` printing.

## What comes next

* **All 36 weights are negative, so the modal launch is pi-flipped with respect to the lumped launch**
  on every edge it drives. `|s21|` is sign-invariant, so this has no consequence for the measurement
  this design exists to make: no bracket row, test or budget above depends on the sign.
* It does have consequences ahead. Anything phase-aware — AC-7, and visualisation of the launch itself —
  needs a definite sign, so **normalise the sign of `e_z` at the mode level** (`plane_mode` /
  `build_mode_plane`) before any future phase work. Not in this change: the placed mode feeds the
  station capture too, so its sign touches numbers the published record already contains.
* The host run then reports the measured `|s21|` move at plane 51 and the bracket row it lands in.
  Nothing here predicts the size of that move; that is what the run is for.

The numbers, the derivation, the line-number table, the full patch text and the pre-split prose kept
verbatim: `docs/design/modal_port_wiring_measurement_2026-11-03.md`.
