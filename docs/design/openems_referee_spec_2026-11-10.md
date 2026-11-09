# openEMS referee for termination build A — design record

**Date:** 2026-11-10
**Status of the model: AUTHORED, UNEXERCISED.** See §5. Nothing in this
document describes an executed simulation.
**Artefact under test:** `evidence/termination/build_A_50ohm_p51_phasors.json`
**Referee script:** `docker/openems/build_A_referee.py`
**Generator of the artefact:** `evidence/termination/run_build_A.py`,
library `emfit/studies.py`

The referee asks exactly one question: *does an independent FDTD engine, fed
the reference's own grid, stack and termination, also produce |S11| ≈ 0.33 at
5.827786408 GHz?* It is not a model of the physical DUT.

---

## 1. Geometry

The reference grid is uniform at **0.4 mm on all three axes**. This is not an
assumption; it is forced by the recorded bounding box, which is an exact
multiple of the cell in every direction:

| axis | cells | extent | check | recipe (from `emfit/studies.py`) |
|---|---|---|---|---|
| x (propagation) | `nx = 72` | **28.8 mm** | 72 × 0.4 = 28.8 | `n_pml6 + n_ref2 + n_line64` |
| y (transverse) | `ny = 212` | **84.8 mm** | 212 × 0.4 = 84.8 | `2*n_pml12 + n_strip8 + 2*n_clean96` |
| z (vertical) | `nz = 22` | **8.8 mm** | 22 × 0.4 = 8.8 | `n_sub4 + n_air12 + n_top6` |

Total `nx*ny*nz = 335 808` cells, matching the artefact's recorded cell count.

### 1.1 The `y_extent` trap — read this before touching the transverse domain

`geometry.y_extent = 0.04` in the artefact is **not a geometric extent**. It is
documented at `emfit/studies.py:1427` as *"Half-width used for the truncated
sum [m]"* — it is the ±20 mm window over which the `plate_current` integral is
evaluated. The physical transverse domain of the reference model is
**84.8 mm (212 cells)**.

**Modelling to 40 mm instead of 84.8 mm would be a factor-of-two error in
transverse domain size**, and would silently change the radiation/edge
behaviour of the strip. It is the single most likely way for a reimplementation
to go wrong, because the key name is suggestive and the number is plausible.

### 1.2 Cross-section and stack

| item | value |
|---|---|
| substrate | `eps_r = 4.4`, `h = 1.6 mm` (4 cells), spanning z = 0 → 1.6 mm |
| ground | z = 0 plane — a **PEC wall**, i.e. the `zmin` boundary *is* the ground |
| strip | `w = 3.2 mm` (8 cells), PEC sheet at `z = 1.6 mm` (`k_strip = 4`) |
| strip placement | `j_centre = 106`, `n_strip = 8` → y ∈ [40.8, 44.0] mm, centred in 84.8 mm |
| air above strip | 1.6 → 6.4 mm (`n_air = 12`) |
| lid absorber | 6.4 → 8.8 mm (`n_top = 6`) |

### 1.3 Longitudinal landmarks

| landmark | index | x |
|---|---|---|
| launch port | `ix_port = 8` | **3.2 mm** |
| load cell start | `column = 50` | **20.0 mm** |
| load cell end / extraction plane | `s21_plane_index = 51` | **20.4 mm** |
| port → load span | — | **16.8 mm** |

---

## 2. The load structure

The reference termination is recorded as

```json
{"column": 50, "kind": "series_r", "n_edges": 9, "value": 50.0, "x": 0.02}
```

and built at `emfit/studies.py:2925-2931`:

1. select the **E_x** edges at one column: `idx_ex([ix_load], j_points, k_strip)`;
2. un-pin them from PEC (`pec[edges] = False`);
3. give each a conductivity `sigma[edges] += 1/(edges.size * value)`.

With `edges.size = 9` and `value = 50`, each of the 9 parallel E_x edges
carries `sigma = 1/(9 × 50) = 2.2222e-3 S`, so the parallel combination is
**exactly 50 Ω**. The 9 edges are the 9 y-node lines of an 8-cell-wide strip —
the termination spans the full 3.2 mm width. The E_y rails alongside remain
pinned (PEC); what is removed is the longitudinal conduction path.

**openEMS equivalent:** cut the strip at x ∈ [20.0, 20.4] mm (one cell, the
strip is genuinely severed — no metal in the gap), then attach a lumped
element that spans the full strip width in y and lies **one cell along x**,
i.e. `p_dir="x"`.

### 2.1 Why the orientation is not a free choice

A series termination must resist the current flowing **along** the strip. The
two orientations give wildly different answers against the reference's own
recorded wave impedance `Z0 = 47.364067 + j1.644981 Ω`
(`run.station_fit`):

| orientation | formula | \|Γ\| |
|---|---|---|
| **series (p_dir = x)** — correct | `R / (R + 2·Z0)` | **0.3454753** |
| shunt to ground (p_dir = z) | `(R − Z0) / (R + Z0)` | 0.027073 |
| edge-to-edge transverse (p_dir = y) | degenerates to a shunt between the E_y rails | ≈ 0.027 |

The artefact's own anchor is **0.34465**, which sits on the series branch, not
the shunt branch. Choosing `p_dir="z"` or `p_dir="y"` would produce ≈ 0.027
and be wrong by a factor of 12 in |Γ| while looking superficially reasonable.
This check — `0.3455` vs `0.0271` — is the reason the load orientation, and the
acceptance of `p_dir="x"`, is settled rather than assumed.

---

## 3. Boundary conditions

The dispatch specified "PML 6 cells". **openEMS has no 6-cell PML.** Its only
accepted tokens are `PML_8`, `PML_3`, `PML_0`, `PEC`, `PMC`, `MUR`
(`'PML'`, `'PML-8'`, `'PML_6'`, `'periodic'`, `'PEC_0'`, `'MUR_0'` and any
lowercase form all raise). A `PML_8` also eats 8 **cells** per side, not 8 mm.

The resolution keeps the grid exactly as derived in §1 — it changes only which
absorbing scheme is applied at each face, and records the deviation per face.

| face | choice | reasoning |
|---|---|---|
| `xmin` | **`PML_3`** | **Forced.** `PML_8` would consume columns 0–7; the launch port sits at column 8 (`ix_port = 8`). There is no freedom here — `PML_8` would absorb the port. |
| `xmax` | `PML_8` | The strip runs into it; the clean tail behind the load shrinks from 6.4 mm to 5.6 mm, still ahead of the PML start. |
| `ymin` | `PML_8` | 96 clean cells (38.4 mm) of margin outboard of the strip; ample. |
| `ymax` | `PML_8` | Symmetric with `ymin`. |
| `zmin` | **`PEC`** | This face **is** the ground plane of the reference model (z = 0 PEC wall). An absorber here would be physically wrong, not merely inaccurate. |
| `zmax` | `PML_8` | Consumes 8 of 22 cells, so it starts at z = 5.6 mm — **4.0 mm above the strip**, clear of the field. `lambda_g/10 = 2.8 mm` at the operating point, so the clearance is adequate. |

### 3.1 MUR rejected

`MUR` (first-order ABC) was measured, during the smoke test
(`docker/openems/smoke_solve.py`), to leave an energy floor of **−18.58 dB**.
That is far above the −60 dB floor this comparison needs, so `MUR` is rejected
outright. It is not used on any face, in any combination.

### 3.2 Convergence bounds

- `SetEndCriteria(1e-6)` — set **explicitly**, never relying on the default.
  openEMS takes a *linear* ratio and renders it as `10*log10`, so `1e-6`
  is the −60 dB floor.
- `SetNumberOfTimeSteps(40000)` — a hard cap. The artefact's own `dt` is
  `7.6263e-13 s`, so its 2400 steps correspond to ≈16 700 openEMS steps at the
  same `dt`; 40 000 leaves comfortable headroom.
- **If the time-step cap fires before the end criterion, the run must be
  reported NON-CONVERGED.** Do not silently accept the truncated result.

---

## 4. Extraction plan

### 4.1 Port type

**`AddLumpedPort`, exclusively.** This is the only port type proven to work in
this image (smoke test). `AddMSLPort` is rejected: it requires the metal to be
a CSX *property* rather than a geometry, it relocates the reference plane, and
its `Z_ref` comes from an internal quasi-static solve whose behaviour here is
unverified. The two port types must not be mixed in one model.

| port | definition |
|---|---|
| 1 (launch) | `AddLumpedPort(1, 50, start=[3.2e-3, 40.8e-3, 0], stop=[3.2e-3, 44.0e-3, 1.6e-3], p_dir="z", excite=1.0)` — ground wall up to the strip |
| 2 (load + probe) | `AddLumpedPort(2, 50.0, start=[20.0e-3, 40.8e-3, 1.6e-3], stop=[20.4e-3, 44.0e-3, 1.6e-3], p_dir="x", excite=0)` — the termination itself, unexcited, doubling as the V/I probe via `port_ut_2`/`port_it_2` |

### 4.2 S11

```
U  = DFT(port_ut_1, f)
I  = DFT(port_it_1, f)
S11 = (U/Z_ref − I) / (U/Z_ref + I),      Z_ref = 50 Ω
```

with

```
f = 5.827786408327286e9 Hz
```

That frequency is **not a free choice**. It is the artefact's own operating
point, and it equals exactly `8/(1800·dt)` — the eighth DFT bin of the settled
1800-step window of the reference run. Sampling both engines on the same bin is
the only way the comparison is like-for-like. Note this is **not** the sweep's
`f_target` of 6.0 GHz; taking 6.0 GHz would compare two different operating
points.

### 4.3 Why de-embedding is off the critical path

The referee's reference plane is x = 3.2 mm; the artefact's extraction plane is
x = 20.4 mm (`s21_plane_index = 51`), **17.2 mm apart**. At
`beta = 231.553 rad/m` that is a one-way electrical length of
`beta·0.0172 = 3.982717 rad = 228.19°`, i.e. 0.634 of a turn — more than half a
cycle, so the phase reference is effectively random. (The figure usually quoted
for this build, `2·beta·0.0168 = 7.780191 rad = 445.77°`, is the **round trip**
over the artefact's own 16.8 mm port → load span, not the one-way de-embed
distance; do not use it as a phase correction.)
**Phase is therefore not comparable** and no attempt is made to compare it.

But **|S11| is a magnitude**, and a magnitude is invariant under a shift of the
reference plane. Since the entire purpose of this referee is a *magnitude*
comparison (0.32556), de-embedding adds nothing to the critical path and is
correctly omitted. The script states this explicitly rather than leaving the
reader to infer it.

### 4.4 What |S21| would need

|S21| is **not** obtainable from this model. It requires:

1. a second lumped port downstream at ≈ x = 24 mm;
2. a de-embed from that port back to x = 20.4 mm over 3.6 mm
   (`exp(+j·beta·0.0036)`);
3. the same reference-plane correction on the launch side.

That is a separate build. It must use `AddLumpedPort` again — not a mixed
MSL/lumped model — and it should be a distinct script so this one stays a
single-purpose magnitude referee.

---

## 5. BLOCKER

**DATED CORRECTION -- 2026-11-09 18:59 local (17:59 UTC). The environment
blocker below still stands for THIS workspace, but the referee itself has
now run ONCE, on the operator's host, by hand.**

- Provenance: `docker/openems/build_A_referee.py` as committed here is the
  invocation source; the run stopped on the -60 dB end criterion
  (10647 timesteps) after ~73 s wall. Its output is the six files in
  `evidence/referee/` (`et`, `ht`, `port_ut_1`, `port_it_1`, `port_ut_2`,
  `port_it_2`). Those files are that run's output. They are NOT anomalous
  and NOT unexplained.
- What actually failed was the EXTRACTION, not the solve. The port records
  are extension-less ASCII (`%`-prefixed header lines), and the extraction
  plan assumed h5-suffixed files, so nothing could be read back.
- Reader fixed the same day: `read_port()` now tries the extension-less
  file first (ASCII, `np.loadtxt(..., comments="%")`), falls back to
  `<name>.h5`, and raises `FileNotFoundError` naming BOTH paths if neither
  exists. `dft_at()` and `extract_s11()` were added next to it so the
  extraction plan is executable rather than prose.
- First extraction result, and the caveat that goes with it: LENGTH is
  adequate (820 samples, 8.2018 ns = 47.8 periods at 5.8278 GHz, tail at
  1.2e-8 of peak, full-record and first-half results agreeing to 6e-7) but
  the record is NOT bin-aligned (47.8 periods is not an integer), and the
  number it yields is |S11| = 1.0003 -- i.e. an OPEN port, not ~0.33. So
  the referee has still NOT produced a usable S11. Details and the
  diagnostic that localises the anomaly to port 1 are in
  `evidence/referee/s11_extraction.json`. One run is not a convergence
  study either way.
- Provenance drift, recorded so the numbers above cannot be misread: the port
  records under `evidence/referee/` were REWRITTEN after this extraction, by a
  later host-side write whose headers are stamped `Mon Nov  9 19:21:08 2026`
  local. That snapshot is 813 samples / 8.1316 ns / 47.39 periods rather than
  820 / 8.2018 ns / 47.80 periods, and the extracted S11 reproduces from it to
  8-9 significant digits. So the length verdict holds on either snapshot, while
  the exact row count above is a property of the snapshot that was measured.
- Reconciliation, because the two spans look contradictory and are not: the
  port records are written every 13th timestep, so their 10.014 ps spacing is
  13 x 7.70333e-13 s -- the CFL step for the 0.4 mm uniform cell -- and 819
  intervals x 13 = 10647 exactly, with 819 x 10.014 ps = 8.201738195 ns
  against the recorded 8.201738196 ns (1.6e-10 relative). All 639 `et`
  timestamps are integer multiples of that solver step to within 3.8e-16 s,
  i.e. print rounding, and `ht` sits on half-integer multiples (Yee stagger).
  An earlier reading that the stored records contradict the stated run is
  therefore retracted, in favour of the records. Not explained, and not needed
  for the S11 number: `et`/`ht` cover only the first 0.4915 ns (5.99 % of the
  run) and carry no header lines at all, so the files alone cannot say whether
  that window was configured or truncated. For a re-run, note that the port
  record is a 13:1 decimated series: `SetPortDataCounter(1)` would store 10647
  samples over 106.6 ns (621 periods) rather than 820 over 8.20 ns (47.8) --
  a data-density improvement, not a fix for |S11| ~ 1, which is not a
  truncation effect.
- SUPERSEDED below, as of 2026-11-09: "solver path never ran",
  "AUTHORED-UNEXERCISED", "nothing executed", "no result of this referee
  exists". These were true when written and are kept for the record; read
  them as "no EXTRACTION had succeeded and no validated S11 existed then".

**openEMS cannot be executed in this environment. This is a hard, verified
environment limitation, not a modelling difficulty.**

Evidence, all directly observed:

- **No docker binary** on the host — `docker` is not on `PATH`.
- **No docker socket** — `/var/run/docker.sock` does not exist.
- **`host_bash` permission is `banned`** — the supervised host shell cannot be
  invoked, so the daemon cannot be reached by any other route either.
- **Network is `banned`** (effective) — no image pull, no remote solver, no
  fallback.
- The session also reports `allow_host_resources: false`, and the available
  exec image is `python:3.12-slim`, which contains neither a docker client nor
  the openEMS bindings.

Consequences that must be carried forward:

- The status of the image **`openems:bookworm` is UNKNOWN and unverifiable from
  here.** It may build from `docker/openems/Dockerfile`; it may not. Nothing in
  this document asserts that it does.
- **`docker/openems/build_A_referee.py` is AUTHORED-UNEXERCISED.** It has never
  been executed against openEMS. Its `--dry-run` geometry echo is pure
  arithmetic and *is* checkable without the bindings; the solver path is not.
  No reader may mistake this script for a validated model.
- **No result of this referee exists.** The reference |S11| = 0.32556 remains
  `s11.validation_status = "UNVALIDATED"`. This work does not change that.

The two commands an operator with a working Docker daemon would run:

```sh
docker build -t openems:bookworm docker/openems
mkdir -p evidence/referee
docker run --rm -v "$PWD/evidence/referee:/work/out" openems:bookworm \
    python3 /work/build_A_referee.py --out /work/out
```

With the `COPY build_A_referee.py /work/` line now in `docker/openems/Dockerfile`,
that is the primary path: the script is baked into the image at
`/work/build_A_referee.py`, so
`docker run --rm openems:bookworm python3 /work/build_A_referee.py --out /work/out`
finds it with no mount at all — the `-v` above mounts only the output directory.
The build context is `docker/openems`, which is why the `COPY` source is
`build_A_referee.py` and not `docker/openems/build_A_referee.py`.

If the `openems:bookworm` tag predates that line, or the image cannot be rebuilt
here, the script can instead be supplied at run time. This works with the
already-built image and needs no rebuild:

```sh
docker run --rm \
    -v "$PWD/evidence/referee:/work/out" \
    -v "$PWD/docker/openems/build_A_referee.py:/work/build_A_referee.py:ro" \
    openems:bookworm python3 /work/build_A_referee.py --out /work/out
```

The `:ro` is deliberate: the referee is a read-only entry point, nothing in it
writes next to itself, and a read-only bind cannot mutate the host working tree
by accident.

And, before either of those, the harmless check that needs no bindings at all:

```sh
python3 docker/openems/build_A_referee.py --dry-run
```

---

## 6. Open risks

### 6.1 The recorded anchor is not reproducible from the file

The artefact quotes an anchor `|Γ| = 0.34465`. Inverting the series formula
`|Γ| = R/(R+2·Z0)` for `R = 50` gives **`Z0 = 47.537 Ω`**, and **that value
appears nowhere in the artefact.** The nearest recorded impedance,
`run.station_fit.z0_re = 47.364067` (with `z0_im = 1.644981`), yields
`0.3454753` — a difference of 8.3e-4 in |Γ|, small but not zero.

Until the provenance of `0.34465` is identified, the anchor should be treated
as *approximately* corroborating the series topology (it clearly is not the
shunt branch, 0.027) rather than as an exact check.

### 6.2 Three different Z0 values in one artefact

| source | value | implied \|Γ\| for R = 50 |
|---|---|---|
| `run.station_fit.z0` | 47.364067 + j1.644981 | 0.345475 |
| `line.z0` | 42.437862 − 15.727993j | 0.361023 |
| `z0_model` | 48.0987 | 0.342003 |

These differ by enough to move the anchor check past any tight tolerance. Any
future claim that "the referee agrees with the anchor" must name **which** Z0
it used. The referee script uses `run.station_fit` for reporting only; it does
not assert against any of them.

### 6.3 Power bookkeeping does not add up — do not use it as a check

`|S11|² + |S21|² = 0.105993 + 0.584335 = 0.690328`. Nearly a third of the
incident power is unaccounted for.

For a lossless structure this should be 1.0. It is not, so either the structure
is lossy (the substrate has no recorded loss tangent, but the load dissipates
by construction), or the extraction loses power to the load itself (the
termination absorbs, by design), or the two S-parameters were referenced to
inconsistent planes.

**Consequence: do not use power conservation as a referee acceptance test on
this artefact.** A correct independent model will *also* show ≈0.69, because the
50 Ω termination consumes the balance by construction. Comparing
`|S11|²+|S21|²` between engines tells you nothing about correctness here.
Compare `|S11|` alone.

### 6.4 Other carried risks

- **Phase is not comparable** across the two reference planes without
  de-embedding (§4.3). Only magnitude is being refereed.
- **`eps_eff` is inconsistent within the artefact**: `eps_eff` is `None`,
  `eps_eff_model = 3.34394`, and the recorded `beta = 231.553 rad/m` implies
  `eps_eff ≈ 3.594` — i.e. `beta` sits 3.67 % above `beta_model` (223.353).
  The referee does not depend on `eps_eff`, but any comparison of propagation
  constant would inherit this 3.67 % discrepancy unexplained.
- **`PML_3` at `xmin` is a genuine deviation** from the dispatch's "6-cell PML"
  (§3). It is forced by the port position, but it does mean the feed side has
  less absorbing margin than the other five faces, and any reflection from it
  lands directly on the measurement plane.
- **The load is modelled as an ideal lumped element** in openEMS, whereas the
  reference implements it as distributed conductivity over 9 E_x edges. Both
  give 50 Ω at DC and low frequency; their behaviour at 5.83 GHz is not
  guaranteed identical.
