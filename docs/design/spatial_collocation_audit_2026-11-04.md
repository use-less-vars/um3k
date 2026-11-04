# Spatial collocation audit — is Im(Z0) a Yee-staggering artefact?

Read-only (tree reading + one arithmetic pass). No source change, no run, no commit. Line numbers HEAD, `emfit/studies.py` unless named.
Quantity audited: `run.station_fit.z0 = 47.364066848187235 + 1.6449807931078728j` (`arg +1.9891 deg`, `|Z0| = 47.3926`) — the object of
`z0_provenance_and_twin_2026-11-04.md` Task A, reproduced there from `/s11/station_phasors`. Brackets **A1-A3 are LOCAL to this doc** (§7).

## 1. Where the station voltage is sampled, axially
`studies.py:2993` `column_path(cc, int(ix), j_centre, 0, k_strip)`; `ports.py:253-311` returns `cc.idx_ez(ix, iy, arange(lo,hi))` (`:311`) —
an `ez` column on ONE (x,y) point layer, all signs +1, summed unweighted at `ports.py:107` `float(np.sum(s * e[idx]))`. A forward wave's
left-edge and right-edge sums are equal, so V is the line integral at **x = ix*cell exactly** (`station_x = js * cell`, `:2992`) — no interpolation, no shift.

## 2. Where the station current is sampled, axially
`ports.py:395-468` `plate_current(h, cc, ix, iz)`: `ix = _node_index("ix", ix, cc.nx)` (`:464`), `faces = cc.idx_fy(ix, ...)` (`:467`),
`float(h[faces].sum())` (`:468`) — an `x` CELL index (docstring `:412-414`); the `H_y` faces of cell `ix` are those of a cell centred half a
cell along, i.e. at `x = (ix + 0.5)*cell` (`:3194-3196` states exactly this). `y_extent`/`_y_columns` (`ports.py:351-392`) truncates the y
sum only; nothing selects an x layer, and no `js_layer`/`ks_layer` knob exists in `emfit/` (grep: zero hits).
`studies.py:3201-3204`: `signals[n_currents+i] = 0.5*(plate_current(...,ix-1,...) + plate_current(...,ix,...))`.

## 3. The separation, read off the code
The two straddling faces are at `(ix-0.5)*cell` and `(ix+0.5)*cell`; the arithmetic mean of the conjugate pair `exp(-+j*beta*cell/2)` is
`cos(beta*cell/2) * exp(0)` — **the axial separation is 0 mm = 0 cells**, and the residual is AMPLITUDE only: `cos = 0.998928`
(`beta*cell/2 = 2.6534 deg`), so `|Z| = |Z_true|/cos`, +0.1073 % on `Re(Z0)` = +0.0508 ohm. Phase error: exactly zero.
The comment at `:3193-3199` states the intent ("interpolates the current back onto the node to second order; without it the ratio would carry
beta*cell/2 of spurious phase, about 2.7 deg"); 2.6534 deg is exactly what an uncompensated read would have carried.

## 4. Does the fit hide or add a per-series offset?
`ports.py:1429-1530`: `plane = float(x[0])`, `u = x - plane` (`:1507-1508`), `_two_wave_fit` on `v` (`:1511`) and on `i` (`:1512`),
`z0 = complex(amp_v[0]/amp_i[0])` (`:1516`); the design (`ports.py:804-820`) is the two wave terms only — no per-series phase-offset column,
no extra degree of freedom. So the fit cannot CORRECT a mis-collocation, but cannot be blamed for one either: a station-independent per-series
phase lands wholly in `amp_v[0]/amp_i[0]`, invisible to the residual — and the offset is already zero (§3). Convention (`ports.py:1702-1703`,
`:1716-1719`, `:1729-1730`): forward wave `exp(-j*beta*x)`, so a current sampled `d` DOWNSTREAM gives `arg(Z0) = +beta*d` — positive, as observed.

## 5. Magnitude table — offset -> predicted Im contribution, `|Z0|*tan(beta*d)`, sign +
| offset | cells | phase | Im loaded | Im twin | predicted/observed (l / t) |
|---|---|---|---|---|---|
| 0 — what the code does (§3) | 0 | 0 | 0 | 0 | 0.000 / 0.000 |
| half cell = 0.2 mm, uncompensated read | 0.5 | 2.6534 deg | 2.1964 | 2.2004 | 1.335 / 1.140 |
| one cell = 0.4 mm | 1.0 | 5.3068 deg | 4.4022 | 4.4102 | 2.676 / 2.284 |
| half dt — TEMPORAL, 0.0603 mm | 0.151 | 0.8000 deg | 0.6618 | 0.6643 | 0.402 / 0.344 |
| one dt — TEMPORAL, 0.1206 mm | 0.301 | 1.6000 deg | 1.3238 | 1.3289 | 0.805 / 0.688 |

Observed: +1.6450 (loaded, 1.9891 deg), +1.9309 (twin, 2.3260 deg). The offset the observation would REQUIRE is 0.14993 mm = 0.3748 cell
= 0.75 half-step (twin 0.17568 mm = 0.4392 cell). Last two rows are TEMPORAL (E at n, H at n+1/2), not axial: uncompensated in the tree, the only staggering the scheme offers — restated so they are not read as axial. They must not flip §6.

## 6. Brackets, local to this doc
**A1 — the code samples I a distance ~0.15-0.2 mm off V's plane and compensates nothing. VERDICT: does not fire.** The only candidate
constant in the tree is half a cell (0.2 mm), and it is compensated at `:3201-3204`; an uncompensated 0.5-cell read would also overshoot
the observation by 33 % (2.196 against 1.645).
**A2 — V and I are collocated, or the pair is interpolated back onto one plane, so the axial term is zero. VERDICT: FIRES.** Offset
0 mm = 0 cell, predicted Im contribution 0 (ratio 0.000); the residual is the 0.107 % modulus factor of §3, which does not touch the phase.
**A3 — other/ambiguous. VERDICT: does not fire** — the A2 reading is a three-line code read, not an inference.
Consequence: on the spatial leg the Im(Z0) hypothesis is **dead** for `station_fit.z0`; the +1.645 ohm must be attributed elsewhere. Temporal
staggering covers at most 40 % of it, and `z0_provenance_and_twin_2026-11-04.md` §1 already excludes it as the source; nothing here reopens that.

## 7. An A1-shaped offset in the same file, on a DIFFERENT quantity
`line.z0 = -v_port/i_trunc` (`:3553`) — the record's other Z0 — is NOT compensated: `v_port = port.voltage(e)` (`:3189`) on `port_column = column_path(cc, ix_port, ...)` (`:2994`),
i.e. x = ix_port*cell, against `i_trunc = plate_current(h, cc, ix_port, 0, y_extent=y_half)` (`:3191-3192`), i.e. x = (ix_port + 0.5)*cell — **+0.5 cell = +0.2 mm downstream,
uncompensated** (the station pair gets the average at `:3201-3204`; the port current does not). Predicted phase +2.648 deg: twin `line.z0` arg +18.2860 deg less 2.648 = +15.64 deg vs
the "about +17 deg" port excess phase at `:3550`. An A1-shaped offset on the port-plane V/I, NOT on `station_fit.z0`; §6's A2 must not be extended to it. `:4796-4806` already refuses it for loaded runs.
§6's A2 must not be extended to it. `:4796-4806` already refuses this quantity for loaded runs.

## 8. Namespace caution
`A1`-`A3` here are LOCAL: they ask the SPATIAL question (are V and I sampled on the same x plane?). The committed
`z0_provenance_and_twin_2026-11-04.md` uses the same labels `A1`-`A3` for the TEMPORAL question (`:29-46`) and `B1`-`B3` for the two-Z0-pairs
question (`:58-67`); its A2 firing is about phasor timing and the twin, not this doc's A2, and its A1 is not this doc's A1. `B1` is overloaded a
third time: `deflation_v2_preregistration.md` uses `B1`-`B6` for other criteria. Quote a bracket with its doc name or not at all.

## 9. What this settles
`station_fit.z0`'s Im is not a spatial Yee-staggering artefact: the code removes the half-cell offset before the fit, and the fit would be
blind to it if it did not. Nothing here explains the +1.645 ohm; nothing here excludes the temporal leg. No write outside this file.
